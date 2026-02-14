"""
Testes para o SessionManager
"""
import pytest
from datetime import datetime, timedelta

from src.services.session_manager import SessionManager
from src.models.session import SessionMode, MessageSource


@pytest.fixture
def manager():
    """Fixture que cria um SessionManager para cada teste"""
    return SessionManager()


class TestSessionManager:
    """Testes do gerenciador de sessões"""

    def test_get_session_creates_new(self, manager):
        """Testa que get_session cria nova sessão se não existir"""
        phone = "5531999999999"
        session = manager.get_session(phone)

        assert session.phone == phone
        assert session.mode == SessionMode.AGENT
        assert session.human_attendant is None

    def test_is_agent_active_default(self, manager):
        """Testa que agente está ativo por padrão"""
        phone = "5531999999999"
        assert manager.is_agent_active(phone) is True

    def test_process_customer_message_agent_responds(self, manager):
        """Testa que agente responde quando ativo"""
        phone = "5531999999999"

        should_respond, reason = manager.process_message(
            phone=phone,
            message="Oi, quero queijo",
            source=MessageSource.CUSTOMER
        )

        assert should_respond is True
        assert reason is None

    def test_process_human_message_pauses_agent(self, manager):
        """Testa que mensagem de humano pausa o agente"""
        phone = "5531999999999"

        # Humano manda mensagem
        should_respond, reason = manager.process_message(
            phone=phone,
            message="Vou atender esse cliente",
            source=MessageSource.HUMAN,
            attendant_id="joao@empresa.com"
        )

        assert should_respond is False
        assert reason == "humano esta atendendo"

        # Verifica que modo mudou
        session = manager.get_session(phone)
        assert session.mode == SessionMode.HUMAN
        assert session.human_attendant == "joao@empresa.com"

    def test_detect_human_interference_with_prefix(self, manager):
        """Testa detecção de interferência com prefixo [HUMANO]"""
        message = "[HUMANO] Olá, sou o atendente"
        assert manager.detect_human_interference(message) is True

    def test_detect_human_interference_with_atendente(self, manager):
        """Testa detecção com prefixo [ATENDENTE]"""
        message = "[ATENDENTE] Vou ajudar você"
        assert manager.detect_human_interference(message) is True

    def test_no_interference_on_normal_message(self, manager):
        """Testa que mensagem normal não é detectada como interferência"""
        message = "Oi, quero comprar queijo"
        assert manager.detect_human_interference(message) is False

    def test_command_pausar(self, manager):
        """Testa comando /pausar"""
        phone = "5531999999999"

        result = manager._process_command(
            phone=phone,
            command="/pausar",
            attendant_id="maria@empresa.com"
        )

        assert result.success is True
        assert result.current_mode == SessionMode.PAUSED

        session = manager.get_session(phone)
        assert session.mode == SessionMode.PAUSED
        assert session.paused_by == "maria@empresa.com"
        assert session.paused_at is not None

    def test_command_retomar(self, manager):
        """Testa comando /retomar"""
        phone = "5531999999999"

        # Pausar primeiro
        manager._process_command(phone, "/pausar", "joao")

        # Retomar
        result = manager._process_command(
            phone=phone,
            command="/retomar",
            attendant_id="joao"
        )

        assert result.success is True
        assert result.current_mode == SessionMode.AGENT

        session = manager.get_session(phone)
        assert session.mode == SessionMode.AGENT

    def test_command_assumir(self, manager):
        """Testa comando /assumir"""
        phone = "5531999999999"

        result = manager._process_command(
            phone=phone,
            command="/assumir",
            attendant_id="pedro@empresa.com"
        )

        assert result.success is True
        assert result.current_mode == SessionMode.HUMAN

        session = manager.get_session(phone)
        assert session.mode == SessionMode.HUMAN
        assert session.human_attendant == "pedro@empresa.com"

    def test_command_liberar(self, manager):
        """Testa comando /liberar"""
        phone = "5531999999999"

        # Assumir primeiro
        manager._process_command(phone, "/assumir", "ana")

        # Liberar
        result = manager._process_command(
            phone=phone,
            command="/liberar",
            attendant_id="ana"
        )

        assert result.success is True
        assert result.current_mode == SessionMode.AGENT

        session = manager.get_session(phone)
        assert session.mode == SessionMode.AGENT
        assert session.human_attendant is None

    def test_command_status(self, manager):
        """Testa comando /status"""
        phone = "5531999999999"

        result = manager._process_command(
            phone=phone,
            command="/status"
        )

        assert result.success is True
        assert "Status da Sessao" in result.message
        assert phone in result.message

    def test_command_help(self, manager):
        """Testa comando /help"""
        result = manager._cmd_help()

        assert result.success is True
        assert "/pausar" in result.message
        assert "/retomar" in result.message
        assert "/assumir" in result.message

    def test_customer_message_blocked_when_human_active(self, manager):
        """Testa que cliente não recebe resposta do bot quando humano ativo"""
        phone = "5531999999999"

        # Humano assume
        manager._set_mode(phone, SessionMode.HUMAN, "carlos")

        # Cliente manda mensagem
        should_respond, reason = manager.process_message(
            phone=phone,
            message="Tem desconto?",
            source=MessageSource.CUSTOMER
        )

        assert should_respond is False
        assert "humano" in reason.lower()

    def test_command_blocks_agent_response(self, manager):
        """Testa que comandos não acionam resposta do agente"""
        phone = "5531999999999"

        should_respond, reason = manager.process_message(
            phone=phone,
            message="/status",
            source=MessageSource.CUSTOMER
        )

        assert should_respond is False
        assert reason == "comando processado"

    def test_paused_session_blocks_agent(self, manager):
        """Testa que sessão pausada bloqueia agente"""
        phone = "5531999999999"

        # Pausar
        manager._set_mode(phone, SessionMode.PAUSED)

        # Cliente manda mensagem
        should_respond, reason = manager.process_message(
            phone=phone,
            message="Oi",
            source=MessageSource.CUSTOMER
        )

        assert should_respond is False
        assert reason == "sessao pausada"

    def test_auto_resume_not_triggered_immediately(self, manager):
        """Testa que auto-retomada não acontece imediatamente"""
        phone = "5531999999999"

        # Humano assume
        manager._set_mode(phone, SessionMode.HUMAN, "luiz")

        # Atualiza timestamp de mensagem humana
        session = manager.get_session(phone)
        session.last_human_message = datetime.utcnow()

        # Cliente manda mensagem logo depois
        should_respond, reason = manager.process_message(
            phone=phone,
            message="Oi",
            source=MessageSource.CUSTOMER
        )

        # Não deve retomar (humano acabou de responder)
        assert should_respond is False
        assert session.mode == SessionMode.HUMAN


class TestAutoResume:
    """Testes específicos de auto-retomada"""

    def test_auto_resume_after_timeout(self, manager):
        """Testa auto-retomada após timeout"""
        phone = "5531999999999"

        # Humano assume
        manager._set_mode(phone, SessionMode.HUMAN, "fernanda")

        # Simula mensagem humana há 6 minutos (> 5min timeout)
        session = manager.get_session(phone)
        session.last_human_message = datetime.utcnow() - timedelta(minutes=6)

        # Cliente manda mensagem
        should_respond, reason = manager.process_message(
            phone=phone,
            message="Tem alguém aí?",
            source=MessageSource.CUSTOMER
        )

        # Deve retomar automaticamente
        assert should_respond is True
        assert session.mode == SessionMode.AGENT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
