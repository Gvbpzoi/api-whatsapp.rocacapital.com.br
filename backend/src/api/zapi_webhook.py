"""
Endpoint específico para webhooks da ZAPI
Processa mensagens e responde automaticamente
"""

from fastapi import APIRouter, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from ..services.zapi_client import get_zapi_client
from ..services.session_manager import SessionManager
from ..orchestrator.gotcha_engine import GOTCHAEngine
from ..orchestrator.intent_classifier import IntentClassifier
from ..orchestrator.tools_helper import ToolsHelper
from . import respostas_roca_capital as resp


router = APIRouter()

# Singletons (serão injetados pelo main.py)
session_manager: Optional[SessionManager] = None
gotcha_engine: Optional[GOTCHAEngine] = None
intent_classifier: Optional[IntentClassifier] = None
tools_helper: Optional[ToolsHelper] = None


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
    """
    try:
        logger.info(f"📨 Processando mensagem de {phone[:8]}...")

        # Adicionar mensagem do usuário ao histórico
        session_manager.add_to_history(phone, "user", message)

        # Verificar se agente deve responder
        session = session_manager.get_session(phone)

        if session.mode != "agent":
            logger.info(f"⏸️  Agente pausado para {phone[:8]}, modo: {session.mode}")
            return

        # Processar com agente
        response_text = await _process_with_agent(phone, message, timestamp)

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


def _detectar_saudacao_inicial(message: str) -> bool:
    """
    Detecta se a mensagem começa com uma saudação.
    """
    mensagem_lower = message.lower().strip()
    saudacoes = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "hey", "alo", "alô", "opa"]

    # Verifica se começa com alguma saudação
    for saudacao in saudacoes:
        if mensagem_lower.startswith(saudacao):
            return True
    return False


def _eh_apenas_saudacao(message: str) -> bool:
    """
    Verifica se a mensagem é APENAS uma saudação, sem conteúdo adicional.
    """
    mensagem_lower = message.lower().strip()
    # Remove pontuação
    mensagem_limpa = mensagem_lower.replace("!", "").replace("?", "").replace(".", "").replace(",", "")

    saudacoes_completas = [
        "oi", "olá", "ola", "bom dia", "boa tarde", "boa noite",
        "hey", "alo", "alô", "opa", "e ai", "e aí", "eai",
        "oi tudo bem", "ola tudo bem", "olá tudo bem"
    ]

    return mensagem_limpa in saudacoes_completas


async def _process_with_agent(phone: str, message: str, timestamp: int = None) -> str:
    """
    Processa mensagem com o agente (GOTCHA Engine).

    Returns:
        Texto da resposta
    """
    try:
        # Calcular hora da mensagem
        if timestamp:
            # Timestamp da ZAPI está em milissegundos
            hora_mensagem = datetime.fromtimestamp(timestamp / 1000).hour
        else:
            hora_mensagem = datetime.now().hour

        # Verificar se é nova conversa ou continuação
        is_nova_conversa = session_manager.is_new_conversation(phone)
        logger.info(f"{'🆕 Nova conversa' if is_nova_conversa else '💬 Conversa contínua'} com {phone[:8]}")

        # Classificar intent
        intent = intent_classifier.classify(message)
        logger.info(f"🎯 Intent classificado: {intent}")

        # Detectar se começa com saudação
        comeca_com_saudacao = _detectar_saudacao_inicial(message)
        eh_so_saudacao = _eh_apenas_saudacao(message)

        # Processar baseado no intent
        if intent == "atendimento_inicial":
            # Se é conversa contínua e só saudação, responde de forma simples
            if not is_nova_conversa and eh_so_saudacao:
                response = "Oi! Em que posso te ajudar?"
            else:
                # Nova conversa ou saudação com pedido: saudação completa
                response = resp.gerar_saudacao_contextual(hora_mensagem, tem_pedido=False)

        elif intent == "informacao_loja":
            if comeca_com_saudacao and not eh_so_saudacao:
                response = resp.gerar_saudacao_contextual(hora_mensagem, tem_pedido=True) + "\n\n"
            else:
                response = ""
            response += resp.INFORMACAO_LOJA

        elif intent == "informacao_entrega":
            # Já tem "Oi, bom dia!" na resposta de entrega, então não duplica
            response = resp.INFORMACAO_ENTREGA

        elif intent == "retirada_loja":
            if comeca_com_saudacao and not eh_so_saudacao:
                response = resp.gerar_saudacao_contextual(hora_mensagem, tem_pedido=True) + "\n\n"
            else:
                response = ""
            response += resp.RETIRADA_LOJA

        elif intent == "rastreamento_pedido":
            if comeca_com_saudacao and not eh_so_saudacao:
                response = resp.gerar_saudacao_contextual(hora_mensagem, tem_pedido=True) + "\n\n"
            else:
                response = ""
            response += resp.RASTREAMENTO

        elif intent == "informacao_pagamento":
            if comeca_com_saudacao and not eh_so_saudacao:
                response = resp.gerar_saudacao_contextual(hora_mensagem, tem_pedido=True) + "\n\n"
            else:
                response = ""
            response += resp.INFORMACAO_PAGAMENTO

        elif intent == "armazenamento_queijo":
            # Já tem "Que bom que você perguntou!" na resposta, não adiciona saudação
            response = resp.ARMAZENAMENTO_QUEIJO

        elif intent == "embalagem_presente":
            # Já tem "Temos sim!" na resposta, não adiciona saudação
            response = resp.EMBALAGEM_PRESENTE

        elif intent == "busca_produto":
            # Se começou com saudação, adiciona saudação contextual primeiro
            if comeca_com_saudacao and not eh_so_saudacao:
                saudacao = resp.gerar_saudacao_contextual(hora_mensagem, tem_pedido=True)
                response = saudacao + "\n\n"
            else:
                response = ""

            termo = intent_classifier.extract_search_term(message)
            logger.info(f"Termo de busca: {termo}")

            result = tools_helper.buscar_produtos(termo or message, limite=5)

            if result["status"] == "success":
                # Adiciona uma introdução mais natural
                if comeca_com_saudacao and not eh_so_saudacao:
                    response += f"Vou te mandar a lista de {termo or 'produtos'}:\n\n"
                response += resp.formatar_produto_sem_emoji(result["produtos"])
            else:
                response += "Ops, tive um problema ao buscar produtos. Tente novamente."

        elif intent == "adicionar_carrinho":
            qtd = intent_classifier.extract_quantity(message)
            result = tools_helper.adicionar_carrinho(phone, "1", qtd)

            if result["status"] == "success":
                response = f"Adicionei {qtd} item(s) ao carrinho!\n\n"
                response += f"Total de itens: {result['total_itens']}\n\n"
                response += "Quer adicionar mais algo ou ver o carrinho?"
            else:
                response = f"Ops! {result['message']}"

        elif intent == "ver_carrinho":
            result = tools_helper.ver_carrinho(phone)

            if result["status"] == "success":
                response = resp.formatar_carrinho_sem_emoji(result)
            else:
                response = f"Ops! {result['message']}"

        elif intent == "calcular_frete":
            response = "*Cálculo de Frete*\n\n"
            response += "Para calcular o frete, me informe seu CEP.\n\n"
            response += "Exemplo: 30120-010"

        elif intent == "finalizar_pedido":
            result = tools_helper.finalizar_pedido(phone, metodo_pagamento="pix")

            if result["status"] == "success":
                response = resp.formatar_pedido_finalizado_sem_emoji(result["pedido"])
            else:
                response = f"Ops! {result['message']}"

        elif intent == "consultar_pedido":
            result = tools_helper.consultar_pedidos(phone)

            if result["status"] == "success":
                response = resp.formatar_pedidos_sem_emoji(result["pedidos"])
            else:
                response = f"Ops! {result['message']}"

        else:
            response = "Desculpe, não entendi. Como posso ajudar?"

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
