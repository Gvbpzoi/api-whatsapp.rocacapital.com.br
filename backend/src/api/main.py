"""
API FastAPI principal do agente WhatsApp
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from loguru import logger

from ..services.session_manager import SessionManager
from ..services.zapi_client import get_zapi_client
from ..models.session import MessageSource, SessionMode
from ..orchestrator.gotcha_engine import GOTCHAEngine
from ..orchestrator.intent_classifier import IntentClassifier
from ..orchestrator.tools_helper import ToolsHelper
from ..orchestrator.response_evaluator import ResponseEvaluator
from . import zapi_webhook


app = FastAPI(
    title="Agente WhatsApp - Roça Capital",
    description="API de controle do agente de atendimento com Human-in-the-Loop",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singletons
session_manager = SessionManager()
gotcha_engine = None  # Inicializado no startup
intent_classifier = None  # Inicializado no startup
tools_helper = None  # Inicializado no startup

# Incluir routers
app.include_router(zapi_webhook.router, tags=["ZAPI"])


# ==================== Models ====================

class WhatsAppWebhook(BaseModel):
    """Webhook recebido do n8n"""
    phone: str
    message: str
    sender_type: str = "customer"  # customer, human, agent
    attendant_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


class SendMessageRequest(BaseModel):
    """Requisição para enviar mensagem"""
    phone: str
    message: str
    source: str = "agent"  # agent, human, system


class SessionControlRequest(BaseModel):
    """Requisição de controle de sessão"""
    phone: str
    command: str  # /pausar, /retomar, /assumir, /liberar
    attendant_id: Optional[str] = None


# ==================== Endpoints ====================

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "online",
        "service": "agente-whatsapp",
        "version": "1.0.0"
    }


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    data: WhatsAppWebhook,
    background_tasks: BackgroundTasks
):
    """
    Webhook principal - recebe mensagens do WhatsApp via n8n

    Fluxo:
    1. Recebe mensagem
    2. Verifica com SessionManager se agente deve responder
    3. Se sim, processa com agente IA
    4. Se não, apenas loga (humano está atendendo)

    Returns:
        - should_respond: bool - Se agente deve responder
        - reason: str - Motivo da decisão
        - response: str - Resposta do agente (se aplicável)
    """
    try:
        logger.info(f"📥 Webhook: {data.phone} - {data.message[:50]}...")

        # Mapear tipo de sender
        source_map = {
            "customer": MessageSource.CUSTOMER,
            "human": MessageSource.HUMAN,
            "agent": MessageSource.AGENT
        }
        source = source_map.get(data.sender_type, MessageSource.CUSTOMER)

        # Processa mensagem com SessionManager
        should_respond, reason = session_manager.process_message(
            phone=data.phone,
            message=data.message,
            source=source,
            attendant_id=data.attendant_id
        )

        logger.info(f"🤔 Decisão: should_respond={should_respond}, reason={reason}")

        if not should_respond:
            return {
                "should_respond": False,
                "reason": reason,
                "session_mode": session_manager.get_session(data.phone).mode.value
            }

        # Agente deve responder - processar com IA
        # TODO: Integrar com LangChain Agent aqui
        response = await _process_with_agent(data.phone, data.message)

        return {
            "should_respond": True,
            "reason": "agent active",
            "response": response,
            "session_mode": SessionMode.AGENT.value
        }

    except Exception as e:
        logger.error(f"❌ Erro no webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/control/command")
async def session_command(data: SessionControlRequest):
    """
    Endpoint para controle de sessão via comandos

    Comandos disponíveis:
    - /pausar - Pausa o agente
    - /retomar - Retoma o agente
    - /assumir - Humano assume
    - /liberar - Libera para agente
    - /status - Mostra status

    Exemplo:
        POST /control/command
        {
            "phone": "5531999999999",
            "command": "/pausar",
            "attendant_id": "joao@empresa.com"
        }
    """
    try:
        result = session_manager._process_command(
            phone=data.phone,
            command=data.command,
            attendant_id=data.attendant_id
        )

        return result.dict()

    except Exception as e:
        logger.error(f"❌ Erro no comando: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{phone}/status")
async def get_session_status(phone: str):
    """
    Obtém status de uma sessão

    Returns informações como:
    - Modo atual (agent/human/paused)
    - Último atendente
    - Timestamps de mensagens
    """
    try:
        session = session_manager.get_session(phone)
        return session.dict()

    except Exception as e:
        logger.error(f"❌ Erro ao obter status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/active")
async def list_active_sessions(mode: Optional[str] = None):
    """
    Lista todas as sessões ativas

    Query params:
    - mode: Filtrar por modo (agent, human, paused)

    Returns:
        Lista de sessões com seus status
    """
    try:
        sessions = session_manager._sessions.values()

        if mode:
            mode_enum = SessionMode(mode)
            sessions = [s for s in sessions if s.mode == mode_enum]

        return {
            "total": len(sessions),
            "sessions": [s.dict() for s in sessions]
        }

    except Exception as e:
        logger.error(f"❌ Erro ao listar sessões: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session/{phone}/takeover")
async def takeover_session(phone: str, attendant_id: str):
    """
    Atalho para humano assumir uma conversa

    Equivalente a enviar comando /assumir
    """
    try:
        result = session_manager._process_command(
            phone=phone,
            command="/assumir",
            attendant_id=attendant_id
        )

        return result.dict()

    except Exception as e:
        logger.error(f"❌ Erro ao assumir sessão: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session/{phone}/release")
async def release_session(phone: str, attendant_id: Optional[str] = None):
    """
    Atalho para liberar conversa de volta para o agente

    Equivalente a enviar comando /liberar
    """
    try:
        result = session_manager._process_command(
            phone=phone,
            command="/liberar",
            attendant_id=attendant_id
        )

        return result.dict()

    except Exception as e:
        logger.error(f"❌ Erro ao liberar sessão: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Helpers ====================

async def _process_with_agent(phone: str, message: str) -> str:
    """
    Processa mensagem com o agente IA usando GOTCHA Engine

    Fluxo:
    1. Classifica intent (qual goal executar)
    2. Usa templates e context do GOTCHA Engine
    3. Processa com ferramentas apropriadas
    4. Retorna resposta formatada
    """
    try:
        if not intent_classifier or not gotcha_engine:
            logger.warning("⚠️ GOTCHA não inicializado, usando fallback")
            return "Desculpe, sistema temporariamente indisponível. Tente novamente em instantes."

        # 1. Classificar intent
        intent = intent_classifier.classify(message)
        logger.info(f"🎯 Intent detectado: {intent}")

        # 2. Processar baseado no intent
        if intent == "atendimento_inicial":
            # Saudação personalizada
            # TODO: Buscar dados do cliente no Supabase
            response = gotcha_engine.format_saudacao(
                nome=None,  # Buscar do banco
                horario="manha",  # Detectar horário atual
                cliente_conhecido=False,
                historico=None
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
            logger.info(f"🛒 Quantidade: {qtd}")

            # Por enquanto, adicionar o primeiro produto mock para demonstração
            # TODO: Implementar seleção de produto baseada na conversa anterior
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
            # Calcular frete
            # TODO: Implementar cálculo de frete real
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
            # Fallback
            response = "Desculpe, não entendi. Pode reformular?"

        return response

    except Exception as e:
        logger.error(f"❌ Erro ao processar com agente: {e}")
        return "Desculpe, ocorreu um erro. Por favor, tente novamente."


# ==================== Startup/Shutdown ====================

@app.on_event("startup")
async def startup_event():
    """Inicialização da aplicação"""
    global gotcha_engine, intent_classifier, tools_helper, response_evaluator

    logger.info("🚀 Iniciando Agente WhatsApp API...")
    logger.info("📊 SessionManager inicializado")

    # Inicializar GOTCHA Engine
    try:
        gotcha_engine = GOTCHAEngine()
        logger.info(f"🎯 GOTCHA Engine inicializado: {gotcha_engine}")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar GOTCHA Engine: {e}")
        gotcha_engine = None

    # Inicializar Intent Classifier
    try:
        intent_classifier = IntentClassifier()
        logger.info("🧠 Intent Classifier inicializado")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar Intent Classifier: {e}")
        intent_classifier = None

    # Inicializar Tools Helper
    try:
        tools_helper = ToolsHelper()
        logger.info("🔧 Tools Helper inicializado")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar Tools Helper: {e}")
        tools_helper = None

    # Inicializar Response Evaluator
    try:
        response_evaluator = ResponseEvaluator()
        logger.info("Response Evaluator inicializado")
    except Exception as e:
        logger.error(f"Erro ao inicializar Response Evaluator: {e}")
        response_evaluator = None

    # Injetar singletons no router ZAPI
    zapi_webhook.session_manager = session_manager
    zapi_webhook.gotcha_engine = gotcha_engine
    zapi_webhook.intent_classifier = intent_classifier
    zapi_webhook.tools_helper = tools_helper
    zapi_webhook.response_evaluator = response_evaluator

    # Inicializar ZAPI Client
    try:
        zapi_client = get_zapi_client()
        logger.info("📱 ZAPI Client inicializado")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar ZAPI Client: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Finalização da aplicação"""
    logger.info("👋 Encerrando Agente WhatsApp API...")
