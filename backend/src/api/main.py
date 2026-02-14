"""
API FastAPI principal do agente WhatsApp.
Inicializa SessionManager, AIAgent e MediaProcessor.
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from loguru import logger

from ..services.session_manager import SessionManager
from ..services.zapi_client import get_zapi_client
from ..services.media_processor import MediaProcessor
from ..models.session import MessageSource, SessionMode
from ..agent.ai_agent import AIAgent
from . import zapi_webhook


app = FastAPI(
    title="Agente WhatsApp - Roca Capital",
    description="API do agente de atendimento com AI Agent + Human-in-the-Loop",
    version="2.0.0",
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

# Incluir routers
app.include_router(zapi_webhook.router, tags=["ZAPI"])


# ==================== Models ====================


class SendMessageRequest(BaseModel):
    phone: str
    message: str
    source: str = "agent"


class SessionControlRequest(BaseModel):
    phone: str
    command: str
    attendant_id: Optional[str] = None


# ==================== Endpoints ====================


@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "agente-whatsapp",
        "version": "2.0.0",
        "engine": "ai-agent",
    }


@app.post("/control/command")
async def session_command(data: SessionControlRequest):
    """Endpoint para controle de sessao via comandos."""
    try:
        result = session_manager._process_command(
            phone=data.phone,
            command=data.command,
            attendant_id=data.attendant_id,
        )
        return result.dict()
    except Exception as e:
        logger.error(f"Erro no comando: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{phone}/status")
async def get_session_status(phone: str):
    """Obtém status de uma sessão."""
    try:
        session = session_manager.get_session(phone)
        return session.dict()
    except Exception as e:
        logger.error(f"Erro ao obter status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/active")
async def list_active_sessions(mode: Optional[str] = None):
    """Lista todas as sessoes ativas."""
    try:
        sessions = list(session_manager._sessions.values())
        if mode:
            mode_enum = SessionMode(mode)
            sessions = [s for s in sessions if s.mode == mode_enum]
        return {"total": len(sessions), "sessions": [s.dict() for s in sessions]}
    except Exception as e:
        logger.error(f"Erro ao listar sessoes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session/{phone}/takeover")
async def takeover_session(phone: str, attendant_id: str):
    """Humano assume uma conversa."""
    try:
        result = session_manager._process_command(
            phone=phone, command="/assumir", attendant_id=attendant_id
        )
        return result.dict()
    except Exception as e:
        logger.error(f"Erro ao assumir sessao: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session/{phone}/release")
async def release_session(phone: str, attendant_id: Optional[str] = None):
    """Libera conversa de volta para o agente."""
    try:
        result = session_manager._process_command(
            phone=phone, command="/liberar", attendant_id=attendant_id
        )
        return result.dict()
    except Exception as e:
        logger.error(f"Erro ao liberar sessao: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Startup/Shutdown ====================


@app.on_event("startup")
async def startup_event():
    """Inicialização da aplicação."""
    logger.info("Iniciando Agente WhatsApp API v2.0 (AI Agent)...")

    # AI Agent
    try:
        ai_agent = AIAgent()
        logger.info(f"AI Agent inicializado com modelo {ai_agent.model}")
    except Exception as e:
        logger.error(f"Erro ao inicializar AI Agent: {e}")
        ai_agent = None

    # Media Processor
    try:
        media_processor = MediaProcessor()
        logger.info("Media Processor inicializado")
    except Exception as e:
        logger.error(f"Erro ao inicializar Media Processor: {e}")
        media_processor = None

    # ZAPI Client
    try:
        zapi_client = get_zapi_client()
        logger.info("ZAPI Client inicializado")
    except Exception as e:
        logger.error(f"Erro ao inicializar ZAPI Client: {e}")

    # Injetar singletons no webhook
    zapi_webhook.session_manager = session_manager
    zapi_webhook.ai_agent = ai_agent
    zapi_webhook.media_processor = media_processor

    logger.info("Agente WhatsApp API pronto!")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Encerrando Agente WhatsApp API...")
