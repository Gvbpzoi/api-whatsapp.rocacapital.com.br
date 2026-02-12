"""
Gerenciador de sessões para controle humano-agente

Funcionalidades:
- Detecta quando humano assume conversa
- Pausa/retoma agente automaticamente
- Processa comandos de controle (/pausar, /retomar, etc)
- Mantém estado de cada sessão
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Dict
from loguru import logger

from ..models.session import (
    SessionStatus, SessionMode, MessageSource,
    CommandResult, WhatsAppMessage
)


class SessionManager:
    """Gerenciador de sessões de atendimento"""

    # Comandos disponíveis (podem ser enviados por humanos)
    COMMANDS = {
        "/pausar": "Pausa o agente para essa conversa",
        "/retomar": "Retoma o agente para essa conversa",
        "/status": "Mostra status atual da sessão",
        "/assumir": "Humano assume o atendimento",
        "/liberar": "Libera conversa de volta para o agente",
        "/help": "Lista comandos disponíveis"
    }

    # Padrões que indicam interferência humana
    HUMAN_INDICATORS = [
        r"^\[HUMANO\]",  # Prefixo explícito
        r"^\[ATENDENTE\]",
        r"^@agente pause",
        r"^@bot pare",
    ]

    def __init__(self, redis_client=None):
        """
        Args:
            redis_client: Cliente Redis para persistência (opcional)
                         Se None, usa dict em memória
        """
        self.redis = redis_client
        self._sessions: Dict[str, SessionStatus] = {}
        self._auto_pause_timeout = 300  # 5min sem resposta do humano -> retoma bot

        # Memória conversacional: histórico de mensagens por telefone
        self._conversation_history: Dict[str, list] = {}
        # Timeout para considerar "nova conversa" (em segundos)
        self._new_conversation_timeout = 1800  # 30 minutos

    # ==================== Controle de Sessão ====================

    def get_session(self, phone: str) -> SessionStatus:
        """Obtém ou cria status de sessão"""
        if phone not in self._sessions:
            self._sessions[phone] = SessionStatus(
                phone=phone,
                mode=SessionMode.AGENT
            )
        return self._sessions[phone]

    # ==================== Memória Conversacional ====================

    def add_to_history(self, phone: str, role: str, message: str):
        """
        Adiciona mensagem ao histórico da conversa.

        Args:
            phone: Número do telefone
            role: "user" ou "assistant"
            message: Conteúdo da mensagem
        """
        if phone not in self._conversation_history:
            self._conversation_history[phone] = []

        self._conversation_history[phone].append({
            "role": role,
            "content": message,
            "timestamp": datetime.utcnow()
        })

        # Manter apenas últimas 20 mensagens para não crescer infinitamente
        if len(self._conversation_history[phone]) > 20:
            self._conversation_history[phone] = self._conversation_history[phone][-20:]

    def is_new_conversation(self, phone: str) -> bool:
        """
        Verifica se é uma nova conversa (sem histórico recente).

        Returns:
            True se é nova conversa ou última mensagem foi há mais de 30min
        """
        if phone not in self._conversation_history:
            return True

        if not self._conversation_history[phone]:
            return True

        last_message = self._conversation_history[phone][-1]
        time_since_last = datetime.utcnow() - last_message["timestamp"]

        return time_since_last.total_seconds() > self._new_conversation_timeout

    def has_recent_conversation(self, phone: str) -> bool:
        """
        Verifica se teve conversa recente (oposto de is_new_conversation).

        Returns:
            True se houve mensagens nos últimos 30 minutos
        """
        return not self.is_new_conversation(phone)

    def get_conversation_history(self, phone: str, limit: int = 10) -> list:
        """
        Retorna histórico da conversa.

        Args:
            phone: Número do telefone
            limit: Número máximo de mensagens a retornar

        Returns:
            Lista de mensagens mais recentes
        """
        if phone not in self._conversation_history:
            return []

        return self._conversation_history[phone][-limit:]

    def clear_conversation(self, phone: str):
        """Limpa histórico de conversa."""
        if phone in self._conversation_history:
            self._conversation_history[phone] = []

    def is_agent_active(self, phone: str) -> bool:
        """Verifica se o agente está ativo para essa conversa"""
        session = self.get_session(phone)
        return session.mode == SessionMode.AGENT

    def is_human_active(self, phone: str) -> bool:
        """Verifica se humano está atendendo"""
        session = self.get_session(phone)
        return session.mode == SessionMode.HUMAN

    # ==================== Detecção Automática ====================

    def detect_human_interference(self, message: str) -> bool:
        """
        Detecta se mensagem indica interferência humana

        Exemplos que detectam:
        - [HUMANO] Olá, sou o João...
        - [ATENDENTE] Vou te ajudar...
        - @agente pause
        """
        message_lower = message.lower().strip()

        for pattern in self.HUMAN_INDICATORS:
            if re.match(pattern, message, re.IGNORECASE):
                logger.info(f"Detectada interferência humana: {pattern}")
                return True

        return False

    def process_message(
        self,
        phone: str,
        message: str,
        source: MessageSource,
        attendant_id: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Processa mensagem e determina se agente deve responder

        Returns:
            (should_agent_respond, reason)

        Exemplos:
            - Cliente manda msg + agente ativo = (True, None)
            - Cliente manda msg + humano ativo = (False, "humano atendendo")
            - Humano manda msg = (False, "detectado humano") + pausa agente
        """
        session = self.get_session(phone)
        now = datetime.utcnow()

        # Atualiza timestamp
        if source == MessageSource.CUSTOMER:
            session.last_customer_message = now
        elif source == MessageSource.HUMAN:
            session.last_human_message = now
        elif source == MessageSource.AGENT:
            session.last_agent_message = now

        # 1. Se é comando, processa e não deixa agente responder
        if message.startswith("/"):
            self._process_command(phone, message, attendant_id)
            return False, "comando processado"

        # 2. Se mensagem é de humano, pausa agente automaticamente
        if source == MessageSource.HUMAN:
            if session.mode != SessionMode.HUMAN:
                logger.info(f"Humano assumiu conversa: {phone}")
                self._set_mode(phone, SessionMode.HUMAN, attendant_id)
            return False, "humano está atendendo"

        # 3. Se detecta interferência humana na mensagem
        if self.detect_human_interference(message):
            logger.warning(f"Detectada interferência humana em: {phone}")
            self._set_mode(phone, SessionMode.HUMAN, "auto-detected")
            return False, "interferência humana detectada"

        # 4. Se é mensagem do cliente e humano está ativo
        if source == MessageSource.CUSTOMER and session.mode == SessionMode.HUMAN:
            # Verifica se humano ficou inativo (auto-retoma)
            if self._should_auto_resume(session):
                logger.info(f"Auto-retomando agente para: {phone}")
                self._set_mode(phone, SessionMode.AGENT)
                return True, None
            return False, "aguardando humano"

        # 5. Se é mensagem do cliente e agente está ativo
        if source == MessageSource.CUSTOMER and session.mode == SessionMode.AGENT:
            return True, None

        # 6. Sessão pausada
        if session.mode == SessionMode.PAUSED:
            return False, "sessão pausada"

        return False, "modo desconhecido"

    # ==================== Comandos ====================

    def _process_command(
        self,
        phone: str,
        command: str,
        attendant_id: Optional[str] = None
    ) -> CommandResult:
        """Processa comandos de controle"""
        cmd = command.split()[0].lower()
        session = self.get_session(phone)

        if cmd == "/pausar":
            return self._cmd_pause(phone, attendant_id)
        elif cmd == "/retomar":
            return self._cmd_resume(phone, attendant_id)
        elif cmd == "/assumir":
            return self._cmd_takeover(phone, attendant_id)
        elif cmd == "/liberar":
            return self._cmd_release(phone, attendant_id)
        elif cmd == "/status":
            return self._cmd_status(phone)
        elif cmd == "/help":
            return self._cmd_help()
        else:
            return CommandResult(
                success=False,
                message=f"Comando desconhecido: {cmd}\nUse /help para ver comandos."
            )

    def _cmd_pause(self, phone: str, attendant_id: Optional[str]) -> CommandResult:
        """Comando: /pausar - Pausa o agente"""
        session = self.get_session(phone)
        previous = session.mode

        session.mode = SessionMode.PAUSED
        session.paused_at = datetime.utcnow()
        session.paused_by = attendant_id

        logger.info(f"Sessão pausada: {phone} por {attendant_id}")

        return CommandResult(
            success=True,
            message="✅ Agente pausado. Use /retomar para reativar.",
            previous_mode=previous,
            current_mode=SessionMode.PAUSED
        )

    def _cmd_resume(self, phone: str, attendant_id: Optional[str]) -> CommandResult:
        """Comando: /retomar - Retoma o agente"""
        session = self.get_session(phone)
        previous = session.mode

        self._set_mode(phone, SessionMode.AGENT, attendant_id)

        logger.info(f"Agente retomado: {phone} por {attendant_id}")

        return CommandResult(
            success=True,
            message="✅ Agente retomado. Voltarei a responder automaticamente.",
            previous_mode=previous,
            current_mode=SessionMode.AGENT
        )

    def _cmd_takeover(self, phone: str, attendant_id: Optional[str]) -> CommandResult:
        """Comando: /assumir - Humano assume"""
        session = self.get_session(phone)
        previous = session.mode

        self._set_mode(phone, SessionMode.HUMAN, attendant_id)

        logger.info(f"Humano assumiu: {phone} ({attendant_id})")

        return CommandResult(
            success=True,
            message=f"✅ Atendimento assumido por {attendant_id or 'humano'}. Agente pausado.",
            previous_mode=previous,
            current_mode=SessionMode.HUMAN
        )

    def _cmd_release(self, phone: str, attendant_id: Optional[str]) -> CommandResult:
        """Comando: /liberar - Libera para o agente"""
        return self._cmd_resume(phone, attendant_id)

    def _cmd_status(self, phone: str) -> CommandResult:
        """Comando: /status - Mostra status"""
        session = self.get_session(phone)

        mode_emoji = {
            SessionMode.AGENT: "🤖",
            SessionMode.HUMAN: "👤",
            SessionMode.PAUSED: "⏸️"
        }

        status_msg = f"""
📊 Status da Sessão
━━━━━━━━━━━━━━━━
📞 Cliente: {phone}
{mode_emoji.get(session.mode, '❓')} Modo: {session.mode.value.upper()}
👤 Atendente: {session.human_attendant or 'Nenhum'}
⏰ Última msg cliente: {self._format_time(session.last_customer_message)}
🤖 Última msg agente: {self._format_time(session.last_agent_message)}
👨 Última msg humano: {self._format_time(session.last_human_message)}
        """.strip()

        return CommandResult(
            success=True,
            message=status_msg,
            current_mode=session.mode,
            data=session.dict()
        )

    def _cmd_help(self) -> CommandResult:
        """Comando: /help - Lista comandos"""
        help_msg = "🔧 Comandos Disponíveis\n━━━━━━━━━━━━━━━━\n\n"

        for cmd, desc in self.COMMANDS.items():
            help_msg += f"{cmd}\n  → {desc}\n\n"

        return CommandResult(
            success=True,
            message=help_msg.strip()
        )

    # ==================== Helpers ====================

    def _set_mode(
        self,
        phone: str,
        mode: SessionMode,
        attendant_id: Optional[str] = None
    ):
        """Define modo da sessão"""
        session = self.get_session(phone)
        session.mode = mode

        if mode == SessionMode.HUMAN and attendant_id:
            session.human_attendant = attendant_id
        elif mode == SessionMode.AGENT:
            session.human_attendant = None
            session.paused_at = None
            session.paused_by = None

    def _should_auto_resume(self, session: SessionStatus) -> bool:
        """
        Verifica se deve retomar agente automaticamente
        (humano ficou inativo por muito tempo)
        """
        if session.mode != SessionMode.HUMAN:
            return False

        if not session.last_human_message:
            return False

        inactive_time = datetime.utcnow() - session.last_human_message

        return inactive_time > timedelta(seconds=self._auto_pause_timeout)

    def _format_time(self, dt: Optional[datetime]) -> str:
        """Formata datetime para exibição"""
        if not dt:
            return "Nunca"

        delta = datetime.utcnow() - dt

        if delta.seconds < 60:
            return "Agora"
        elif delta.seconds < 3600:
            return f"{delta.seconds // 60}min atrás"
        elif delta.days == 0:
            return f"{delta.seconds // 3600}h atrás"
        else:
            return f"{delta.days}d atrás"

    # ==================== Persistência ====================

    def save_session(self, phone: str):
        """Salva sessão no Redis (se disponível)"""
        if not self.redis:
            return

        session = self.get_session(phone)
        # TODO: Implementar salvamento no Redis
        pass

    def load_session(self, phone: str) -> Optional[SessionStatus]:
        """Carrega sessão do Redis"""
        if not self.redis:
            return None

        # TODO: Implementar carregamento do Redis
        return None
