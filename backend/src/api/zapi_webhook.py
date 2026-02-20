"""
Webhook ZAPI: recebe mensagens WhatsApp, processa mídia, bufferiza e chama AI Agent.
"""

from fastapi import APIRouter, Request
from typing import Optional, Dict
from datetime import datetime
from loguru import logger
import asyncio
import os

from ..services.zapi_client import get_zapi_client
from ..services.session_manager import SessionManager
from ..models.session import SessionMode
from ..services.media_processor import MediaProcessor
from ..agent.ai_agent import AIAgent


router = APIRouter()

# Singletons (injetados pelo main.py)
session_manager: Optional[SessionManager] = None
ai_agent: Optional[AIAgent] = None
media_processor: Optional[MediaProcessor] = None

# Feature flag para migração zero-downtime
USE_AI_AGENT = os.getenv("USE_AI_AGENT", "true").lower() == "true"


# Lock por telefone para evitar race condition no buffer
_phone_locks: Dict[str, asyncio.Lock] = {}


def _extract_media(data: dict) -> tuple[str, str, Optional[str]]:
    """
    Extrai tipo de mídia, texto e URL do payload ZAPI.

    Returns:
        (media_type, message_text, media_url)
    """
    # Áudio
    audio = data.get("audio")
    if audio:
        audio_url = audio.get("audioUrl") or audio.get("url")
        return "audio", "", audio_url

    # Imagem
    image = data.get("image")
    if image:
        image_url = image.get("imageUrl") or image.get("url")
        caption = image.get("caption", "")
        return "image", caption, image_url

    # Documento (PDF, etc)
    document = data.get("document")
    if document:
        doc_url = document.get("documentUrl") or document.get("url")
        caption = document.get("caption", "")
        return "document", caption, doc_url

    # Texto padrão
    text_data = data.get("text", {})
    message = text_data.get("message", "") if text_data else ""
    return "text", message, None


def _split_response(text: str, max_len: int = 1000) -> list[str]:
    """
    Divide resposta longa em partes menores para WhatsApp.
    Tenta quebrar em parágrafos (\\n\\n) para ficar natural.
    """
    if len(text) <= max_len:
        return [text]

    parts = []
    remaining = text

    while remaining:
        if len(remaining) <= max_len:
            parts.append(remaining)
            break

        # Tentar quebrar em \n\n
        cut = remaining[:max_len].rfind("\n\n")
        if cut > max_len * 0.3:
            parts.append(remaining[:cut].rstrip())
            remaining = remaining[cut:].lstrip()
        else:
            # Fallback: quebrar em \n
            cut = remaining[:max_len].rfind("\n")
            if cut > max_len * 0.3:
                parts.append(remaining[:cut].rstrip())
                remaining = remaining[cut:].lstrip()
            else:
                # Último recurso: quebrar em espaço
                cut = remaining[:max_len].rfind(" ")
                if cut > 0:
                    parts.append(remaining[:cut])
                    remaining = remaining[cut:].lstrip()
                else:
                    parts.append(remaining[:max_len])
                    remaining = remaining[max_len:]

    return [p for p in parts if p.strip()]


async def process_and_respond(
    phone: str,
    message: str,
    media_type: str = "text",
    media_url: Optional[str] = None,
):
    """
    Processa mensagem com buffer, mídia e AI Agent.
    Roda em background para não bloquear webhook.
    """
    # Obter ou criar lock para este telefone
    if phone not in _phone_locks:
        _phone_locks[phone] = asyncio.Lock()

    lock = _phone_locks[phone]

    async with lock:
        try:
            logger.info(f"Processando mensagem de {phone[:8]}... tipo={media_type}")

            # === Processar mídia antes do buffer ===
            processed_message = message
            if media_type == "audio" and media_url and media_processor:
                logger.info(f"Transcrevendo audio de {phone[:8]}...")
                processed_message = await media_processor.transcribe_audio(media_url)
                logger.info(f"Transcricao: {processed_message[:80]}...")
            elif media_type == "image" and media_url and media_processor:
                logger.info(f"Analisando imagem de {phone[:8]}...")
                descricao = await media_processor.analyze_image(media_url, message)
                processed_message = f"[Imagem enviada: {descricao}]"
                if message:
                    processed_message += f"\nLegenda: {message}"
            elif media_type == "document" and media_url and media_processor:
                logger.info(f"Extraindo PDF de {phone[:8]}...")
                texto_pdf = await media_processor.extract_pdf_text(media_url)
                processed_message = f"[Documento enviado: {texto_pdf[:500]}]"
                if message:
                    processed_message += f"\nMensagem: {message}"

            if not processed_message:
                logger.warning(f"Mensagem vazia apos processamento para {phone[:8]}")
                return

            # === Buffer de mensagens ===
            buffer_result = session_manager.add_to_buffer(phone, processed_message)
            my_count = buffer_result["count"]

            if buffer_result["should_wait"]:
                logger.info(f"Aguardando mais mensagens no buffer ({my_count})")
                await asyncio.sleep(3.0)

                # Re-fetch buffer após sleep
                current_buffer = session_manager._message_buffer.get(phone, {})
                messages = current_buffer.get("messages", [])

                if not messages:
                    logger.info("Buffer ja processado por outra task")
                    return

                # Se chegaram mais mensagens durante o sleep, SÓ a última task processa
                if len(messages) > my_count:
                    logger.info(f"Novas mensagens chegaram ({len(messages)} > {my_count}), deixando proximo ciclo processar")
                    return

                combined_message = " ".join([msg["text"] for msg in messages])
            else:
                combined_message = buffer_result["combined"]

            # Limpar buffer
            session_manager.clear_buffer(phone)

            logger.info(f"Processando: {combined_message[:60]}...")

            # === Verificar kill switch global ===
            if not session_manager.is_globally_active():
                logger.info(f"Agente desativado globalmente, ignorando {phone[:8]}")
                return

            # === Verificar modo da sessão ===
            session = session_manager.get_session(phone)
            logger.info(f"Modo sessao {phone[:8]}: {session.mode}")
            if session.mode != "agent":
                logger.info(f"Agente pausado para {phone[:8]}, modo: {session.mode}. Ignorando mensagem.")
                return

            # === Chamar AI Agent ===
            if not ai_agent:
                logger.error("AI Agent nao inicializado")
                return

            response_text = await ai_agent.process_message(
                telefone=phone,
                user_message=combined_message,
                media_type=media_type,
                media_url=media_url,
            )

            if not response_text:
                logger.warning(f"Nenhuma resposta gerada para {phone[:8]}")
                return

            # === Enviar resposta via ZAPI ===
            zapi = get_zapi_client()
            parts = _split_response(response_text)

            for i, part in enumerate(parts):
                result = zapi.send_text(phone, part)
                if result["success"]:
                    logger.info(f"Resposta {i + 1}/{len(parts)} enviada para {phone[:8]}")
                else:
                    logger.error(f"Falha ao enviar resposta: {result.get('error')}")

                # Delay entre mensagens consecutivas
                if i < len(parts) - 1:
                    await asyncio.sleep(1.0)

        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}")


@router.post("/webhook/zapi")
async def zapi_webhook(request: Request):
    """
    Webhook para receber mensagens da ZAPI.
    Processa texto, áudio, imagem e documentos.
    """
    try:
        data = await request.json()
        logger.info(f"Webhook ZAPI recebido: {data}")

        phone = data.get("phone", "")
        from_me = data.get("fromMe", False)
        is_group = data.get("isGroup", False)

        # Ignorar mensagens de grupo
        if is_group:
            return {"success": True, "message": "Mensagem de grupo ignorada"}
        if not phone:
            return {"success": False, "error": "Telefone nao identificado"}

        # Extrair texto bruto
        text_data = data.get("text", {})
        raw_text = text_data.get("message", "") if text_data else ""

        logger.debug(f"Webhook: phone={phone[:8]}, fromMe={from_me}, raw_text='{raw_text[:50]}'")

        # === Mensagens do operador (fromMe=True) ===
        if from_me:
            # Comandos do operador: /assumir, /liberar, /pausar, etc.
            if raw_text.startswith("/"):
                result = session_manager._process_command(phone, raw_text)
                # Enviar resposta do comando de volta no WhatsApp
                zapi = get_zapi_client()
                zapi.send_text(phone, result.message)
                logger.info(f"Comando operador {raw_text} para {phone[:8]}: {result.message}")
                return {"success": True, "message": "Comando operador processado"}

            # Detectar indicadores de humano ([HUMANO], [ATENDENTE])
            if session_manager.detect_human_interference(raw_text):
                session_manager._set_mode(phone, SessionMode.HUMAN, "operador")
                logger.info(f"Operador assumiu via indicador para {phone[:8]}")
                return {"success": True, "message": "Humano detectado"}

            # Mensagem normal do operador: ignorar (não processar pelo bot)
            return {"success": True, "message": "Mensagem propria ignorada"}

        # === Mensagens do cliente (fromMe=False) ===

        # Extrair mídia
        media_type, message, media_url = _extract_media(data)

        if not message and media_type == "text":
            return {"success": True, "message": "Mensagem vazia ignorada"}

        # Processar em background (asyncio.create_task para rodar em paralelo)
        asyncio.create_task(
            process_and_respond(phone, message, media_type, media_url)
        )

        return {"success": True, "message": "Mensagem recebida e sendo processada"}

    except Exception as e:
        logger.error(f"Erro no webhook ZAPI: {e}")
        return {"success": False, "error": str(e)}


@router.get("/webhook/zapi")
async def zapi_webhook_get():
    """Endpoint GET para verificar se webhook está ativo."""
    return {
        "status": "online",
        "webhook": "zapi",
        "message": "Webhook ZAPI ativo e pronto para receber mensagens",
    }
