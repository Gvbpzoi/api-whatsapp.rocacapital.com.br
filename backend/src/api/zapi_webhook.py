"""
Endpoint específico para webhooks da ZAPI
Processa mensagens e responde automaticamente
"""

from fastapi import APIRouter, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger
import re
import asyncio

from ..services.zapi_client import get_zapi_client
from ..services.session_manager import SessionManager
from ..orchestrator.gotcha_engine import GOTCHAEngine
from ..orchestrator.intent_classifier import IntentClassifier
from ..orchestrator.tools_helper import ToolsHelper
from ..orchestrator.response_evaluator import ResponseEvaluator
from . import respostas_roca_capital as resp
from .intent_handlers import (
    HandlerContext,
    INTENT_HANDLERS,
    handle_fallback,
    detectar_saudacao_inicial,
    eh_apenas_saudacao,
    detectar_pergunta_nome,
    extrair_nome_cliente,
    detectar_pergunta_generica_produtos,
    detectar_despedida,
)


router = APIRouter()

# Singletons (serão injetados pelo main.py)
session_manager: Optional[SessionManager] = None
gotcha_engine: Optional[GOTCHAEngine] = None
intent_classifier: Optional[IntentClassifier] = None
tools_helper: Optional[ToolsHelper] = None
response_evaluator: Optional[ResponseEvaluator] = None

# Bug #5: Lock por telefone para evitar race condition no buffer
_phone_locks: Dict[str, asyncio.Lock] = {}


class ZAPIWebhookMessage(BaseModel):
    """
    Formato de webhook da ZAPI
    Documentação: https://developer.z-api.io/webhooks/on-message-received
    """
    phone: str
    text: Optional[Dict[str, str]] = None
    image: Optional[Dict[str, Any]] = None
    isGroup: bool = False
    instanceId: Optional[str] = None
    messageId: Optional[str] = None
    fromMe: bool = False
    momment: Optional[int] = None
    status: Optional[str] = None
    senderName: Optional[str] = None
    photo: Optional[str] = None
    broadcast: Optional[bool] = None
    participantPhone: Optional[str] = None


async def process_and_respond(phone: str, message: str, timestamp: int = None):
    """
    Processa mensagem com o agente e envia resposta via ZAPI.
    Roda em background para não bloquear webhook.
    
    Implementa buffer de mensagens: aguarda 3 segundos para mensagens consecutivas.
    
    Bug #5 corrigido: Usa Lock por telefone para evitar race condition.
    """
    # Obter ou criar lock para este telefone
    if phone not in _phone_locks:
        _phone_locks[phone] = asyncio.Lock()
    
    lock = _phone_locks[phone]
    
    # Apenas uma coroutine por telefone processa por vez
    async with lock:
        try:
            logger.info(f"📨 Processando mensagem de {phone[:8]}...")

            # Adicionar ao buffer
            buffer_result = session_manager.add_to_buffer(phone, message)
            
            # Se deve aguardar mais mensagens, sair (timer vai processar depois)
            if buffer_result["should_wait"]:
                logger.info(f"⏳ Aguardando mais mensagens no buffer ({buffer_result['count']}/3)")
                # Agendar processamento após 3 segundos
                await asyncio.sleep(3.0)
                
                # RE-FETCH buffer após sleep (Bug #5)
                current_buffer = session_manager._message_buffer.get(phone, {})
                messages = current_buffer.get("messages", [])
                
                # Se buffer foi limpo por outra task, skip
                if not messages:
                    logger.info("✅ Buffer já foi processado por outra task")
                    return
                
                # Se chegaram mais mensagens, deixar próximo ciclo processar
                if len(messages) > buffer_result["count"]:
                    logger.info("📬 Novas mensagens chegaram, deixando próximo ciclo processar")
                    return
                
                # Combinar mensagens do buffer atual (extrair texto de cada dict)
                combined_message = " ".join([msg["text"] for msg in messages])
                message_count = len(messages)
            else:
                # Processar imediatamente
                combined_message = buffer_result["combined"]
                message_count = buffer_result["count"]
            
            logger.info(f"📝 Processando {message_count} mensagem(ns): {combined_message[:50]}...")
            
            # Adicionar mensagem combinada ao histórico
            session_manager.add_to_history(phone, "user", combined_message)
            
            # Limpar buffer
            session_manager.clear_buffer(phone)

            # Verificar se agente deve responder
            session = session_manager.get_session(phone)

            if session.mode != "agent":
                logger.info(f"⏸️  Agente pausado para {phone[:8]}, modo: {session.mode}")
                return

            # Processar com agente
            response_text = await _process_with_agent(phone, combined_message, timestamp)

            if not response_text:
                logger.warning(f"⚠️ Nenhuma resposta gerada para {phone[:8]}")
                return

            # Enviar resposta via ZAPI
            zapi = get_zapi_client()
            result = zapi.send_text(phone, response_text)

            if result["success"]:
                # Adicionar resposta do bot ao histórico
                session_manager.add_to_history(phone, "assistant", response_text)
                logger.info(f"✅ Resposta enviada para {phone[:8]}")
            else:
                logger.error(f"❌ Falha ao enviar resposta: {result.get('error')}")

        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem: {e}")


async def _process_with_agent(phone: str, message: str, timestamp: int = None) -> str:
    """
    Processa mensagem com o agente (GOTCHA Engine).

    Flow:
    1. Pre-checks (name extraction, goodbye, name question)
    2. Intent classification (LLM + regex, stage-aware)
    3. Dispatch to handler function
    4. Evaluate response before returning

    Returns:
        Response text
    """
    try:
        # Calcular hora da mensagem
        if timestamp:
            hora_mensagem = datetime.fromtimestamp(timestamp / 1000).hour
        else:
            hora_mensagem = datetime.now().hour

        # Verificar se é nova conversa ou continuação
        is_nova_conversa = session_manager.is_new_conversation(phone)
        logger.info(f"{'🆕 Nova conversa' if is_nova_conversa else '💬 Conversa contínua'} com {phone[:8]}")

        # Reset conversation stage tracking on new conversations
        if is_nova_conversa and response_evaluator:
            response_evaluator.reset_stage(phone)

        # Clear stale cart on new conversation (>30min gap)
        if is_nova_conversa and tools_helper:
            cart = tools_helper.ver_carrinho(phone)
            if cart.get("status") == "success" and not cart.get("vazio"):
                logger.info(f"🗑️ Limpando carrinho antigo de {phone[:8]} (nova conversa)")
                tools_helper.limpar_carrinho(phone)

        # Recuperar nome do cliente da memória
        nome_cliente_salvo = None
        preferencias = session_manager.get_customer_preferences(phone, limit=5)
        for pref in preferencias:
            if pref.get("content", "").startswith("Nome: "):
                nome_cliente_salvo = pref["content"].replace("Nome: ", "")
                logger.info(f"👤 Nome recuperado: {nome_cliente_salvo}")
                break

        # === PRE-CHECKS (short-circuit before intent classification) ===

        # 1. Customer replying with their name
        historico = session_manager.get_conversation_history(phone, limit=5)
        nome_cliente = extrair_nome_cliente(message, historico)
        if nome_cliente:
            session_manager.save_customer_preference(
                phone=phone,
                preference=f"Nome: {nome_cliente}",
                category="identidade",
            )
            return f"Prazer, {nome_cliente}! Fico à disposição sempre que precisar."

        # 2. Special context detection
        pergunta_nome = detectar_pergunta_nome(message)
        despedida = detectar_despedida(message)

        if pergunta_nome and despedida:
            return resp.RESPOSTA_NOME_E_DESPEDIDA
        if pergunta_nome:
            return resp.RESPOSTA_NOME_ATENDENTE
        if despedida:
            return resp.RESPOSTA_DESPEDIDA

        # === INTENT CLASSIFICATION ===

        if detectar_pergunta_generica_produtos(message):
            intent = "busca_produto"
        else:
            context = session_manager.get_context_for_classification(phone)
            # Pass conversation stage and history for context-aware classification
            stage = response_evaluator.get_stage(phone) if response_evaluator else None
            intent = intent_classifier.classify(
                message, context, stage=stage, conversation_history=historico
            )
            logger.info(f"🎯 Intent: {intent}")

        # === DISPATCH TO HANDLER ===

        ctx = HandlerContext(
            phone=phone,
            message=message,
            hora_mensagem=hora_mensagem,
            is_nova_conversa=is_nova_conversa,
            nome_cliente=nome_cliente_salvo,
            comeca_com_saudacao=detectar_saudacao_inicial(message),
            eh_so_saudacao=eh_apenas_saudacao(message),
            session_manager=session_manager,
            intent_classifier=intent_classifier,
            tools_helper=tools_helper,
        )

        handler = INTENT_HANDLERS.get(intent, handle_fallback)
        response = handler(ctx)

        # === EVALUATE RESPONSE BEFORE SENDING ===

        if response_evaluator:
            historico = session_manager.get_conversation_history(phone, limit=5)
            produtos_contexto = session_manager.get_last_products_shown(phone) or None

            evaluation = response_evaluator.evaluate(
                phone=phone,
                message=message,
                intent=intent,
                response=response,
                conversation_history=historico,
                is_new_conversation=is_nova_conversa,
                products_in_context=produtos_contexto,
            )

            if not evaluation.passed and evaluation.adjusted_response:
                logger.warning(
                    f"Response adjusted: issues={evaluation.issues} "
                    f"score={evaluation.score:.2f}"
                )
                response = evaluation.adjusted_response
            elif evaluation.adjusted_response:
                response = evaluation.adjusted_response

        return response

    except Exception as e:
        logger.error(f"❌ Erro ao processar com agente: {e}")
        return "Desculpe, tive um problema ao processar sua mensagem. Tente novamente!"


@router.post("/webhook/zapi")
async def zapi_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Webhook para receber mensagens da ZAPI.

    A ZAPI envia POST com JSON contendo a mensagem.
    Este endpoint processa e responde automaticamente.

    Documentação: https://developer.z-api.io/webhooks/on-message-received
    """
    try:
        data = await request.json()
        logger.info(f"📥 Webhook ZAPI recebido: {data}")

        # Extrair dados da mensagem
        phone = data.get("phone", "")
        from_me = data.get("fromMe", False)
        is_group = data.get("isGroup", False)

        # Ignorar mensagens de grupo e mensagens enviadas por nós
        if is_group:
            logger.info("⏭️ Ignorando mensagem de grupo")
            return {"success": True, "message": "Mensagem de grupo ignorada"}

        if from_me:
            logger.info("⏭️ Ignorando mensagem enviada por mim")
            return {"success": True, "message": "Mensagem própria ignorada"}

        # Extrair texto da mensagem
        text_data = data.get("text", {})
        message = text_data.get("message", "") if text_data else ""

        if not message:
            logger.warning("⚠️ Mensagem vazia recebida")
            return {"success": True, "message": "Mensagem vazia ignorada"}

        if not phone:
            logger.warning("⚠️ Telefone não identificado")
            return {"success": False, "error": "Telefone não identificado"}

        # Extrair timestamp da mensagem
        timestamp = data.get("momment", None)

        # Processar e responder em background
        background_tasks.add_task(process_and_respond, phone, message, timestamp)

        return {
            "success": True,
            "message": "Mensagem recebida e sendo processada"
        }

    except Exception as e:
        logger.error(f"❌ Erro no webhook ZAPI: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/webhook/zapi")
async def zapi_webhook_get():
    """
    Endpoint GET para verificar se webhook está ativo.
    Útil para testar configuração.
    """
    return {
        "status": "online",
        "webhook": "zapi",
        "message": "Webhook ZAPI está ativo e pronto para receber mensagens"
    }
