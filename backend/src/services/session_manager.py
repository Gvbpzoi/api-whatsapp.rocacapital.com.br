"""
Gerenciador de sessões para controle humano-agente.

Funcionalidades mantidas:
- Controle de modo (AGENT/HUMAN/PAUSED)
- Buffer de mensagens (mensagens rápidas consecutivas)
- Comandos de controle (/pausar, /retomar, /assumir, /liberar, /status, /help)
- Detecção de indicadores humanos ([HUMANO], [ATENDENTE])
- Auto-resume após inatividade do humano
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from loguru import logger

from ..models.session import (
    SessionStatus,
    SessionMode,
    MessageSource,
    CommandResult,
)


class SessionManager:
    """Gerenciador de sessões de atendimento."""

    COMMANDS = {
        "/pausar": "Pausa o agente para essa conversa",
        "/retomar": "Retoma o agente para essa conversa",
        "/status": "Mostra status atual da sessao",
        "/assumir": "Humano assume o atendimento",
        "/liberar": "Libera conversa de volta para o agente",
        "/help": "Lista comandos disponiveis",
    }

    HUMAN_INDICATORS = [
        r"^\[HUMANO\]",
        r"^\[ATENDENTE\]",
        r"^@agente pause",
        r"^@bot pare",
    ]

    def __init__(self):
        self._sessions: Dict[str, SessionStatus] = {}
        self._auto_pause_timeout = 300  # 5min sem resposta do humano -> retoma bot
        self._message_buffer: Dict[str, dict] = {}

    # ==================== Sessão ====================

    def get_session(self, phone: str) -> SessionStatus:
        """Obtém ou cria status de sessão."""
        if phone not in self._sessions:
            self._sessions[phone] = SessionStatus(
                phone=phone, mode=SessionMode.AGENT
            )
        return self._sessions[phone]

    def is_agent_active(self, phone: str) -> bool:
        return self.get_session(phone).mode == SessionMode.AGENT

    def is_human_active(self, phone: str) -> bool:
        return self.get_session(phone).mode == SessionMode.HUMAN

    # ==================== Buffer de Mensagens ====================

    def add_to_buffer(self, phone: str, message: str) -> dict:
        """
        Adiciona mensagem ao buffer de espera.
        Aguarda mensagens consecutivas antes de processar.
        """
        now = datetime.utcnow()

        if phone not in self._message_buffer:
            self._message_buffer[phone] = {
                "messages": [],
                "first_message_time": now,
            }

        buffer = self._message_buffer[phone]
        buffer["messages"].append({"text": message, "timestamp": now})

        time_since_first = (now - buffer["first_message_time"]).total_seconds()
        should_wait = len(buffer["messages"]) < 3 and time_since_first < 5.0
        combined = " ".join([msg["text"] for msg in buffer["messages"]])

        logger.info(
            f"Buffer {phone[:8]}: {len(buffer['messages'])} msgs, aguardar={should_wait}"
        )

        return {
            "messages": buffer["messages"],
            "should_wait": should_wait,
            "combined": combined,
            "count": len(buffer["messages"]),
        }

    def clear_buffer(self, phone: str):
        """Limpa buffer de mensagens."""
        if phone in self._message_buffer:
            del self._message_buffer[phone]

    # ==================== Detecção Humana ====================

    def detect_human_interference(self, message: str) -> bool:
        """Detecta se mensagem indica interferência humana."""
        for pattern in self.HUMAN_INDICATORS:
            if re.match(pattern, message, re.IGNORECASE):
                logger.info(f"Detectada interferencia humana: {pattern}")
                return True
        return False

    def process_message(
        self,
        phone: str,
        message: str,
        source: MessageSource,
        attendant_id: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Processa mensagem e determina se agente deve responder.

        Returns:
            (should_agent_respond, reason)
        """
        session = self.get_session(phone)
        now = datetime.utcnow()

        if source == MessageSource.CUSTOMER:
            session.last_customer_message = now
        elif source == MessageSource.HUMAN:
            session.last_human_message = now
        elif source == MessageSource.AGENT:
            session.last_agent_message = now

        # Comando
        if message.startswith("/"):
            self._process_command(phone, message, attendant_id)
            return False, "comando processado"

        # Humano enviando mensagem
        if source == MessageSource.HUMAN:
            if session.mode != SessionMode.HUMAN:
                self._set_mode(phone, SessionMode.HUMAN, attendant_id)
            return False, "humano esta atendendo"

        # Indicador de humano no texto
        if self.detect_human_interference(message):
            self._set_mode(phone, SessionMode.HUMAN, "auto-detected")
            return False, "interferencia humana detectada"

        # Cliente + humano ativo
        if source == MessageSource.CUSTOMER and session.mode == SessionMode.HUMAN:
            if self._should_auto_resume(session):
                self._set_mode(phone, SessionMode.AGENT)
                return True, None
            return False, "aguardando humano"

        # Cliente + agente ativo
        if source == MessageSource.CUSTOMER and session.mode == SessionMode.AGENT:
            return True, None

        # Pausado
        if session.mode == SessionMode.PAUSED:
            return False, "sessao pausada"

        return False, "modo desconhecido"

    # ==================== Comandos ====================

    def _process_command(
        self,
        phone: str,
        command: str,
        attendant_id: Optional[str] = None,
    ) -> CommandResult:
        cmd = command.split()[0].lower()

        handlers = {
            "/pausar": self._cmd_pause,
            "/retomar": self._cmd_resume,
            "/assumir": self._cmd_takeover,
            "/liberar": self._cmd_resume,
            "/status": lambda p, a: self._cmd_status(p),
            "/help": lambda p, a: self._cmd_help(),
        }

        handler = handlers.get(cmd)
        if handler:
            return handler(phone, attendant_id)

        return CommandResult(
            success=False,
            message=f"Comando desconhecido: {cmd}\nUse /help para ver comandos.",
        )

    def _cmd_pause(self, phone: str, attendant_id: Optional[str]) -> CommandResult:
        session = self.get_session(phone)
        previous = session.mode
        session.mode = SessionMode.PAUSED
        session.paused_at = datetime.utcnow()
        session.paused_by = attendant_id
        logger.info(f"Sessao pausada: {phone} por {attendant_id}")
        return CommandResult(
            success=True,
            message="Agente pausado. Use /retomar para reativar.",
            previous_mode=previous,
            current_mode=SessionMode.PAUSED,
        )

    def _cmd_resume(self, phone: str, attendant_id: Optional[str]) -> CommandResult:
        session = self.get_session(phone)
        previous = session.mode
        self._set_mode(phone, SessionMode.AGENT, attendant_id)
        logger.info(f"Agente retomado: {phone} por {attendant_id}")
        return CommandResult(
            success=True,
            message="Agente retomado. Voltarei a responder automaticamente.",
            previous_mode=previous,
            current_mode=SessionMode.AGENT,
        )

    def _cmd_takeover(self, phone: str, attendant_id: Optional[str]) -> CommandResult:
        session = self.get_session(phone)
        previous = session.mode
        self._set_mode(phone, SessionMode.HUMAN, attendant_id)
        logger.info(f"Humano assumiu: {phone} ({attendant_id})")
        return CommandResult(
            success=True,
            message=f"Atendimento assumido por {attendant_id or 'humano'}. Agente pausado.",
            previous_mode=previous,
            current_mode=SessionMode.HUMAN,
        )

    def _cmd_status(self, phone: str) -> CommandResult:
        session = self.get_session(phone)
        mode_emoji = {
            SessionMode.AGENT: "BOT",
            SessionMode.HUMAN: "HUMANO",
            SessionMode.PAUSED: "PAUSADO",
        }
        status_msg = (
            f"Status da Sessao\n"
            f"Cliente: {phone}\n"
            f"Modo: {mode_emoji.get(session.mode, '?')}\n"
            f"Atendente: {session.human_attendant or 'Nenhum'}\n"
            f"Ultima msg cliente: {self._format_time(session.last_customer_message)}\n"
            f"Ultima msg agente: {self._format_time(session.last_agent_message)}\n"
            f"Ultima msg humano: {self._format_time(session.last_human_message)}"
        )
        return CommandResult(
            success=True,
            message=status_msg,
            current_mode=session.mode,
            data=session.dict(),
        )

    def _cmd_help(self) -> CommandResult:
        help_msg = "Comandos Disponiveis\n\n"
        for cmd, desc in self.COMMANDS.items():
            help_msg += f"{cmd} - {desc}\n"
        return CommandResult(success=True, message=help_msg.strip())

    # ==================== Helpers ====================

    def _set_mode(
        self,
        phone: str,
        mode: SessionMode,
        attendant_id: Optional[str] = None,
    ):
        session = self.get_session(phone)
        session.mode = mode
        if mode == SessionMode.HUMAN and attendant_id:
            session.human_attendant = attendant_id
        elif mode == SessionMode.AGENT:
            session.human_attendant = None
            session.paused_at = None
            session.paused_by = None

    def _should_auto_resume(self, session: SessionStatus) -> bool:
        if session.mode != SessionMode.HUMAN:
            return False
        if not session.last_human_message:
            return False
        inactive_time = datetime.utcnow() - session.last_human_message
        return inactive_time > timedelta(seconds=self._auto_pause_timeout)

    def _format_time(self, dt: Optional[datetime]) -> str:
        if not dt:
            return "Nunca"
        delta = datetime.utcnow() - dt
        if delta.seconds < 60:
            return "Agora"
        elif delta.seconds < 3600:
            return f"{delta.seconds // 60}min atras"
        elif delta.days == 0:
            return f"{delta.seconds // 3600}h atras"
        else:
            return f"{delta.days}d atras"
