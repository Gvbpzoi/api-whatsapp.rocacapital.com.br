"""
Tests for the ResponseEvaluator
"""
import pytest
from datetime import datetime

from src.orchestrator.response_evaluator import (
    ResponseEvaluator,
    ConversationStage,
    EvaluationResult,
)


@pytest.fixture
def evaluator():
    return ResponseEvaluator()


PHONE = "5531999999999"


class TestConversationStageTracking:
    """Tests for conversation stage tracking"""

    def test_initial_stage_is_idle(self, evaluator):
        assert evaluator.get_stage(PHONE) == ConversationStage.IDLE

    def test_greeting_intent_sets_greeting_stage(self, evaluator):
        evaluator.update_stage(PHONE, "atendimento_inicial")
        assert evaluator.get_stage(PHONE) == ConversationStage.GREETING

    def test_busca_sets_browsing_stage(self, evaluator):
        evaluator.update_stage(PHONE, "busca_produto")
        assert evaluator.get_stage(PHONE) == ConversationStage.BROWSING

    def test_adicionar_carrinho_sets_carting_stage(self, evaluator):
        evaluator.update_stage(PHONE, "adicionar_carrinho")
        assert evaluator.get_stage(PHONE) == ConversationStage.CARTING

    def test_ver_carrinho_sets_reviewing_stage(self, evaluator):
        evaluator.update_stage(PHONE, "ver_carrinho")
        assert evaluator.get_stage(PHONE) == ConversationStage.REVIEWING_CART

    def test_finalizar_sets_checkout_stage(self, evaluator):
        evaluator.update_stage(PHONE, "finalizar_pedido")
        assert evaluator.get_stage(PHONE) == ConversationStage.CHECKOUT

    def test_info_intents_set_asking_info_stage(self, evaluator):
        for intent in [
            "informacao_entrega",
            "informacao_loja",
            "informacao_pagamento",
            "armazenamento_queijo",
            "embalagem_presente",
        ]:
            evaluator.update_stage(PHONE, intent)
            assert evaluator.get_stage(PHONE) == ConversationStage.ASKING_INFO

    def test_reset_stage(self, evaluator):
        evaluator.update_stage(PHONE, "busca_produto")
        assert evaluator.get_stage(PHONE) == ConversationStage.BROWSING
        evaluator.reset_stage(PHONE)
        assert evaluator.get_stage(PHONE) == ConversationStage.IDLE

    def test_full_purchase_flow(self, evaluator):
        """Test a realistic purchase flow: greeting → browse → cart → checkout"""
        evaluator.update_stage(PHONE, "atendimento_inicial")
        assert evaluator.get_stage(PHONE) == ConversationStage.GREETING

        evaluator.update_stage(PHONE, "busca_produto")
        assert evaluator.get_stage(PHONE) == ConversationStage.BROWSING

        evaluator.update_stage(PHONE, "adicionar_carrinho")
        assert evaluator.get_stage(PHONE) == ConversationStage.CARTING

        evaluator.update_stage(PHONE, "ver_carrinho")
        assert evaluator.get_stage(PHONE) == ConversationStage.REVIEWING_CART

        evaluator.update_stage(PHONE, "finalizar_pedido")
        assert evaluator.get_stage(PHONE) == ConversationStage.CHECKOUT


class TestResponseEvaluation:
    """Tests for response quality evaluation"""

    def test_good_response_passes(self, evaluator):
        result = evaluator.evaluate(
            phone=PHONE,
            message="Vocês fazem entrega?",
            intent="informacao_entrega",
            response="A gente faz entrega sim! Você é de Belo Horizonte?",
            conversation_history=[],
            is_new_conversation=True,
        )
        assert result.passed is True
        assert result.score >= 0.8
        assert len(result.issues) == 0

    def test_empty_response_fails(self, evaluator):
        result = evaluator.evaluate(
            phone=PHONE,
            message="Oi",
            intent="atendimento_inicial",
            response="",
            conversation_history=[],
            is_new_conversation=True,
        )
        assert result.passed is False
        assert "empty_response" in result.issues
        assert result.adjusted_response is not None

    def test_none_response_fails(self, evaluator):
        result = evaluator.evaluate(
            phone=PHONE,
            message="Oi",
            intent="atendimento_inicial",
            response=None,
            conversation_history=[],
            is_new_conversation=True,
        )
        assert result.passed is False
        assert "empty_response" in result.issues

    def test_repeated_greeting_detected(self, evaluator):
        history = [
            {
                "role": "assistant",
                "content": "Bom dia! Você tá falando hoje com o Guilherme. Como é que eu posso te ajudar?",
                "timestamp": datetime.utcnow(),
            },
            {
                "role": "user",
                "content": "quero queijo",
                "timestamp": datetime.utcnow(),
            },
        ]

        result = evaluator.evaluate(
            phone=PHONE,
            message="oi bom dia",
            intent="informacao_loja",
            response="Bom dia! Você tá falando com o Guilherme.\n\nNosso horário de funcionamento...",
            conversation_history=history,
            is_new_conversation=False,
        )

        assert "repeated_greeting" in result.issues
        assert result.adjusted_response is not None
        # Adjusted response should not contain the greeting
        assert "Guilherme" not in result.adjusted_response

    def test_greeting_ok_for_new_conversation(self, evaluator):
        result = evaluator.evaluate(
            phone=PHONE,
            message="oi",
            intent="atendimento_inicial",
            response="Bom dia! Você tá falando hoje com o Guilherme. Como é que eu posso te ajudar?",
            conversation_history=[],
            is_new_conversation=True,
        )
        assert "repeated_greeting" not in result.issues

    def test_intent_response_coherence_entrega(self, evaluator):
        """Response for delivery intent should mention delivery-related terms"""
        result = evaluator.evaluate(
            phone=PHONE,
            message="Como funciona a entrega?",
            intent="informacao_entrega",
            response="A gente faz entrega sim!",
            conversation_history=[],
            is_new_conversation=False,
        )
        assert result.passed is True

    def test_intent_response_incoherent(self, evaluator):
        """Response for delivery intent shouldn't talk about cheese storage"""
        result = evaluator.evaluate(
            phone=PHONE,
            message="Como funciona a entrega?",
            intent="informacao_entrega",
            response="Guarde o queijo na geladeira numa vasilha com tampa.",
            conversation_history=[],
            is_new_conversation=False,
        )
        has_mismatch = any("intent_response_mismatch" in i for i in result.issues)
        assert has_mismatch

    def test_exposed_error_detected(self, evaluator):
        result = evaluator.evaluate(
            phone=PHONE,
            message="quero queijo",
            intent="busca_produto",
            response="TypeError: NoneType has no attribute 'get'",
            conversation_history=[],
            is_new_conversation=False,
        )
        assert "exposed_error_message" in result.issues
        assert result.adjusted_response is not None

    def test_exposed_internal_id_detected(self, evaluator):
        result = evaluator.evaluate(
            phone=PHONE,
            message="adiciona",
            intent="adicionar_carrinho",
            response="Adicionei produto_id 12345 ao carrinho!",
            conversation_history=[],
            is_new_conversation=False,
        )
        assert "exposed_internal_id" in result.issues

    def test_long_response_flagged(self, evaluator):
        long_response = "A" * 2100
        result = evaluator.evaluate(
            phone=PHONE,
            message="oi",
            intent="atendimento_inicial",
            response=long_response,
            conversation_history=[],
            is_new_conversation=True,
        )
        assert "response_too_long" in result.issues

    def test_cart_add_without_context_flagged(self, evaluator):
        """Adding to cart when customer hasn't browsed should be flagged"""
        # Stage is IDLE (no browsing happened)
        result = evaluator.evaluate(
            phone=PHONE,
            message="adiciona 2",
            intent="adicionar_carrinho",
            response="Adicionei 2 item(s) ao carrinho!",
            conversation_history=[],
            is_new_conversation=True,
            products_in_context=None,
        )
        assert "cart_add_without_browsing" in result.issues

    def test_cart_add_with_context_ok(self, evaluator):
        """Adding to cart after browsing should be fine"""
        # First browse
        evaluator.update_stage(PHONE, "busca_produto")

        products = [{"id": "1", "nome": "Queijo Canastra", "preco": 45.0}]
        result = evaluator.evaluate(
            phone=PHONE,
            message="adiciona o 1",
            intent="adicionar_carrinho",
            response="Adicionei 1 item(s) ao carrinho!",
            conversation_history=[],
            is_new_conversation=False,
            products_in_context=products,
        )
        assert "cart_add_without_browsing" not in result.issues

    def test_product_claims_without_data(self, evaluator):
        """Saying 'encontrei' with an empty product list is flagged"""
        result = evaluator.evaluate(
            phone=PHONE,
            message="tem queijo?",
            intent="busca_produto",
            response="Opa! Encontrei 3 produtos!",
            conversation_history=[],
            is_new_conversation=False,
            products_in_context=[],
        )
        assert "claims_products_found_but_empty" in result.issues

    def test_evaluation_returns_stage(self, evaluator):
        result = evaluator.evaluate(
            phone=PHONE,
            message="quero queijo",
            intent="busca_produto",
            response="Encontrei queijo canastra!",
            conversation_history=[],
            is_new_conversation=False,
            products_in_context=[{"id": "1", "nome": "Queijo", "preco": 45.0}],
        )
        assert result.stage == ConversationStage.BROWSING


class TestEmojiDetection:
    """Tests for the no-emoji policy check"""

    def test_no_emoji_passes(self, evaluator):
        result = evaluator.evaluate(
            phone=PHONE,
            message="oi",
            intent="atendimento_inicial",
            response="Oi! Em que posso te ajudar?",
            conversation_history=[],
            is_new_conversation=False,
        )
        assert "contains_emoji" not in result.issues

    def test_emoji_detected(self, evaluator):
        result = evaluator.evaluate(
            phone=PHONE,
            message="oi",
            intent="atendimento_inicial",
            response="Oi! Em que posso te ajudar? 😊",
            conversation_history=[],
            is_new_conversation=False,
        )
        assert "contains_emoji" in result.issues


class TestCoherenceMarkers:
    """Tests for intent-response coherence checking"""

    def test_loja_response_coherent(self, evaluator):
        result = evaluator.evaluate(
            phone=PHONE,
            message="qual o horário?",
            intent="informacao_loja",
            response="Nosso horário de funcionamento é de 8h às 18h.",
            conversation_history=[],
            is_new_conversation=False,
        )
        assert result.passed is True

    def test_pagamento_response_coherent(self, evaluator):
        result = evaluator.evaluate(
            phone=PHONE,
            message="aceita pix?",
            intent="informacao_pagamento",
            response="Se pagar no Pix e a compra for acima de R$ 499, tem 5% de desconto.",
            conversation_history=[],
            is_new_conversation=False,
        )
        assert result.passed is True

    def test_armazenamento_response_coherent(self, evaluator):
        result = evaluator.evaluate(
            phone=PHONE,
            message="como guardar queijo?",
            intent="armazenamento_queijo",
            response="Guarde na geladeira, controle a temperatura e umidade.",
            conversation_history=[],
            is_new_conversation=False,
        )
        assert result.passed is True

    def test_busca_produto_no_coherence_check(self, evaluator):
        """busca_produto doesn't have coherence markers (too varied)"""
        result = evaluator.evaluate(
            phone=PHONE,
            message="tem azeite?",
            intent="busca_produto",
            response="Qualquer coisa aqui, mesmo sem markers.",
            conversation_history=[],
            is_new_conversation=False,
        )
        # No coherence issue because busca_produto has no markers defined
        has_mismatch = any("intent_response_mismatch" in i for i in result.issues)
        assert not has_mismatch


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
