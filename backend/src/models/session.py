"""
Modelos de dados para controle de sessão humano-agente
"""
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class SessionMode(str, Enum):
    """Modo de atendimento da sessão"""
    AGENT = "agent"      # Bot atendendo
    HUMAN = "human"      # Humano atendendo
    PAUSED = "paused"    # Pausado (aguardando)


class SessionStatus(BaseModel):
    """Status de uma sessão de atendimento"""
    phone: str = Field(..., description="Telefone do cliente")
    mode: SessionMode = Field(default=SessionMode.AGENT, description="Modo atual")
    last_agent_message: Optional[datetime] = None
    last_human_message: Optional[datetime] = None
    last_customer_message: Optional[datetime] = None
    human_attendant: Optional[str] = Field(None, description="ID/nome do atendente")
    paused_at: Optional[datetime] = None
    paused_by: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class MessageSource(str, Enum):
    """Origem da mensagem"""
    CUSTOMER = "customer"  # Cliente
    AGENT = "agent"        # Bot
    HUMAN = "human"        # Atendente humano
    SYSTEM = "system"      # Sistema (comandos)


class WhatsAppMessage(BaseModel):
    """Mensagem do WhatsApp"""
    phone: str
    message: str
    source: MessageSource
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    attendant_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CommandResult(BaseModel):
    """Resultado de execução de comando"""
    success: bool
    message: str
    previous_mode: Optional[SessionMode] = None
    current_mode: Optional[SessionMode] = None
    data: Dict[str, Any] = Field(default_factory=dict)
