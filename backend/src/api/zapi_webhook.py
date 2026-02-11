"""
Endpoint específico para webhooks da ZAPI
Processa mensagens e responde automaticamente
"""

from fastapi import APIRouter, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from loguru import logger

from ..services.zapi_client import get_zapi_client
from ..services.session_manager import SessionManager
from ..orchestrator.gotcha_engine import GOTCHAEngine
from ..orchestrator.intent_classifier import IntentClassifier
from ..orchestrator.tools_helper import ToolsHelper


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


async def process_and_respond(phone: str, message: str):
    """
    Processa mensagem com o agente e envia resposta via ZAPI.
    Roda em background para não bloquear webhook.
    """
    try:
        logger.info(f"📨 Processando mensagem de {phone[:8]}...")

        # Verificar se agente deve responder
        session = session_manager.get_or_create_session(phone)

        if session.mode != "agent":
            logger.info(f"⏸️  Agente pausado para {phone[:8]}, modo: {session.mode}")
            return

        # Processar com agente
        response_text = await _process_with_agent(phone, message)

        if not response_text:
            logger.warning(f"⚠️ Nenhuma resposta gerada para {phone[:8]}")
            return

        # Enviar resposta via ZAPI
        zapi = get_zapi_client()
        result = zapi.send_text(phone, response_text)

        if result["success"]:
            logger.info(f"✅ Resposta enviada para {phone[:8]}")
        else:
            logger.error(f"❌ Falha ao enviar resposta: {result.get('error')}")

    except Exception as e:
        logger.error(f"❌ Erro ao processar mensagem: {e}")


async def _process_with_agent(phone: str, message: str) -> str:
    """
    Processa mensagem com o agente (GOTCHA Engine).

    Returns:
        Texto da resposta
    """
    try:
        # Classificar intent
        intent = intent_classifier.classify(message)
        logger.info(f"🎯 Intent classificado: {intent}")

        # Processar baseado no intent
        if intent == "atendimento_inicial":
            # Saudação personalizada
            response = gotcha_engine.format_saudacao(
                horario="manha",  # TODO: detectar horário
                cliente_conhecido=False
            )

        elif intent == "busca_produto":
            # Buscar produtos
            termo = intent_classifier.extract_search_term(message)
            logger.info(f"🔍 Termo de busca: {termo}")

            result = tools_helper.buscar_produtos(termo or message, limite=5)

            if result["status"] == "success":
                produtos = result["produtos"]

                if not produtos:
                    response = "😅 Não encontrei nenhum produto com esse termo.\n\n"
                    response += "Tente buscar por: queijo, cachaça, doce, café..."
                else:
                    response = f"✨ Encontrei {len(produtos)} produto{'s' if len(produtos) > 1 else ''}!\n\n"

                    for i, p in enumerate(produtos, 1):
                        response += f"{i}️⃣ *{p['nome']}*\n"
                        response += f"   💰 R$ {p['preco']:.2f}\n"
                        response += f"   📦 {int(p['estoque_atual'])} em estoque\n\n"

                    response += "Qual te interessa? Digite o número ou nome! 😊"
            else:
                response = "😔 Ops, tive um problema ao buscar produtos. Tente novamente!"

        elif intent == "adicionar_carrinho":
            # Adicionar ao carrinho
            qtd = intent_classifier.extract_quantity(message)
            result = tools_helper.adicionar_carrinho(phone, "1", qtd)

            if result["status"] == "success":
                response = f"✅ Adicionei {qtd} item(s) ao carrinho!\n\n"
                response += f"🛒 Total de itens: {result['total_itens']}\n\n"
                response += "Quer adicionar mais algo ou ver o carrinho?"
            else:
                response = f"😔 Ops! {result['message']}"

        elif intent == "ver_carrinho":
            # Ver carrinho
            result = tools_helper.ver_carrinho(phone)

            if result["status"] == "success":
                if result["vazio"]:
                    response = "🛒 Seu carrinho está vazio!\n\n"
                    response += "Que tal buscar alguns produtos? 😊"
                else:
                    response = "🛒 *Seu Carrinho:*\n\n"

                    for i, item in enumerate(result["carrinho"], 1):
                        produto = item["produto"]
                        response += f"{i}. *{produto['nome']}*\n"
                        response += f"   Qtd: {item['quantidade']} x R$ {produto['preco']:.2f}\n"
                        response += f"   Subtotal: R$ {item['subtotal']:.2f}\n\n"

                    response += f"💰 *Total: R$ {result['total']:.2f}*\n\n"
                    response += "Quer finalizar o pedido? 😊"
            else:
                response = f"😔 Ops! {result['message']}"

        elif intent == "calcular_frete":
            response = "📦 *Cálculo de Frete*\n\n"
            response += "Para calcular o frete, me informe seu CEP! 📍\n\n"
            response += "Exemplo: 30120-010"

        elif intent == "finalizar_pedido":
            # Finalizar pedido
            result = tools_helper.finalizar_pedido(phone, metodo_pagamento="pix")

            if result["status"] == "success":
                pedido = result["pedido"]
                response = "🎉 *Pedido Finalizado!*\n\n"
                response += f"📋 Número: {pedido['numero']}\n"
                response += f"💰 Total: R$ {pedido['total']:.2f}\n"
                response += f"💳 Pagamento: {pedido['metodo_pagamento'].upper()}\n\n"
                response += "📱 Em instantes você receberá o QR Code PIX para pagamento!\n\n"
                response += "Obrigado pela preferência! 🙏"
            else:
                response = f"😔 Ops! {result['message']}"

        elif intent == "consultar_pedido":
            # Consultar pedido
            result = tools_helper.consultar_pedidos(phone)

            if result["status"] == "success":
                pedidos = result["pedidos"]

                if not pedidos:
                    response = "📦 Você ainda não tem pedidos.\n\n"
                    response += "Que tal fazer seu primeiro pedido? 😊"
                else:
                    response = "📦 *Seus Pedidos:*\n\n"

                    for pedido in pedidos:
                        response += f"🔖 {pedido['numero']}\n"
                        response += f"💰 R$ {pedido['total']:.2f}\n"
                        response += f"📊 Status: {pedido['status']}\n"
                        response += f"📅 {pedido['criado_em'][:10]}\n\n"

                    response += "Alguma dúvida sobre seus pedidos? 😊"
            else:
                response = f"😔 Ops! {result['message']}"

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

        # Processar e responder em background
        background_tasks.add_task(process_and_respond, phone, message)

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
