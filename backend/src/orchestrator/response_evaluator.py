"""
Response Evaluator - Validates agent responses before sending.

Evaluates responses against conversation context to catch:
1. Empty or broken responses
2. Repeated greetings in continuous conversations
3. Product claims that don't match actual data
4. Cart operations without product context
5. Intent/response mismatches
6. Exposed internal IDs
7. Policy violations (emojis, response length)

Also tracks conversation stage (browsing → selecting → carting → checkout)
so the controller knows WHERE the customer is in their journey.
"""

import re
from enum import Enum
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


class ConversationStage(str, Enum):
    """Where the customer is in their purchase journey"""
    IDLE = "idle"
    GREETING = "greeting"
    BROWSING = "browsing"
    PRODUCT_SELECTED = "product_selected"
    CARTING = "carting"
    REVIEWING_CART = "reviewing_cart"
    CHECKOUT = "checkout"
    POST_PURCHASE = "post_purchase"
    ASKING_INFO = "asking_info"


# Valid stage transitions - prevents impossible jumps
VALID_TRANSITIONS = {
    ConversationStage.IDLE: {
        ConversationStage.GREETING,
        ConversationStage.BROWSING,
        ConversationStage.ASKING_INFO,
        ConversationStage.CARTING,
        ConversationStage.REVIEWING_CART,
        ConversationStage.POST_PURCHASE,
    },
    ConversationStage.GREETING: {
        ConversationStage.BROWSING,
        ConversationStage.ASKING_INFO,
        ConversationStage.CARTING,
        ConversationStage.REVIEWING_CART,
        ConversationStage.POST_PURCHASE,
        ConversationStage.IDLE,
    },
    ConversationStage.BROWSING: {
        ConversationStage.PRODUCT_SELECTED,
        ConversationStage.CARTING,
        ConversationStage.ASKING_INFO,
        ConversationStage.BROWSING,
        ConversationStage.REVIEWING_CART,
        ConversationStage.GREETING,
        ConversationStage.IDLE,
    },
    ConversationStage.PRODUCT_SELECTED: {
        ConversationStage.CARTING,
        ConversationStage.BROWSING,
        ConversationStage.ASKING_INFO,
        ConversationStage.REVIEWING_CART,
        ConversationStage.IDLE,
    },
    ConversationStage.CARTING: {
        ConversationStage.REVIEWING_CART,
        ConversationStage.BROWSING,
        ConversationStage.CARTING,
        ConversationStage.CHECKOUT,
        ConversationStage.ASKING_INFO,
        ConversationStage.IDLE,
    },
    ConversationStage.REVIEWING_CART: {
        ConversationStage.CHECKOUT,
        ConversationStage.BROWSING,
        ConversationStage.CARTING,
        ConversationStage.ASKING_INFO,
        ConversationStage.IDLE,
    },
    ConversationStage.CHECKOUT: {
        ConversationStage.POST_PURCHASE,
        ConversationStage.BROWSING,
        ConversationStage.REVIEWING_CART,
        ConversationStage.IDLE,
    },
    ConversationStage.POST_PURCHASE: {
        ConversationStage.BROWSING,
        ConversationStage.ASKING_INFO,
        ConversationStage.GREETING,
        ConversationStage.IDLE,
    },
    ConversationStage.ASKING_INFO: {
        ConversationStage.BROWSING,
        ConversationStage.CARTING,
        ConversationStage.ASKING_INFO,
        ConversationStage.REVIEWING_CART,
        ConversationStage.CHECKOUT,
        ConversationStage.GREETING,
        ConversationStage.IDLE,
    },
}

# Intent → stage mapping
INTENT_STAGE_MAP = {
    "atendimento_inicial": ConversationStage.GREETING,
    "busca_produto": ConversationStage.BROWSING,
    "adicionar_carrinho": ConversationStage.CARTING,
    "remover_item": ConversationStage.REVIEWING_CART,
    "alterar_quantidade": ConversationStage.REVIEWING_CART,
    "ver_carrinho": ConversationStage.REVIEWING_CART,
    "finalizar_pedido": ConversationStage.CHECKOUT,
    "consultar_pedido": ConversationStage.POST_PURCHASE,
    "rastreamento_pedido": ConversationStage.POST_PURCHASE,
    "informacao_entrega": ConversationStage.ASKING_INFO,
    "informacao_loja": ConversationStage.ASKING_INFO,
    "informacao_pagamento": ConversationStage.ASKING_INFO,
    "retirada_loja": ConversationStage.ASKING_INFO,
    "armazenamento_queijo": ConversationStage.ASKING_INFO,
    "embalagem_presente": ConversationStage.ASKING_INFO,
    "calcular_frete": ConversationStage.ASKING_INFO,
}

# Expected content markers per intent (for coherence checks)
COHERENCE_MARKERS = {
    "informacao_entrega": ["entrega", "frete", "envio", "cep", "prazo", "bh"],
    "informacao_loja": [
        "horario", "horário", "localiz", "mercado central",
        "endereco", "endereço", "contato", "funcionamento",
    ],
    "informacao_pagamento": ["pix", "pagamento", "desconto", "vale"],
    "armazenamento_queijo": [
        "guardar", "conservar", "geladeira", "temperatura", "armazen", "umidade",
    ],
    "embalagem_presente": ["embalagem", "presente", "caixa", "kit", "cesta"],
    "ver_carrinho": ["carrinho", "total", "pedido", "vazio"],
    "retirada_loja": ["retirar", "retir", "loja", "pegar", "mercado"],
    "rastreamento_pedido": ["rastreio", "rastreamento", "código", "pedido", "acompanhar"],
}


@dataclass
class EvaluationResult:
    """Result of evaluating a response"""
    passed: bool
    score: float  # 0.0 to 1.0
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    adjusted_response: Optional[str] = None
    stage: Optional[ConversationStage] = None


class ResponseEvaluator:
    """
    Evaluates agent responses for quality and coherence before sending.

    Tracks conversation stage per customer and validates that responses
    make sense given the current context.
    """

    def __init__(self):
        self._stages: Dict[str, ConversationStage] = {}
        self._stage_history: Dict[str, List[dict]] = {}

    def get_stage(self, phone: str) -> ConversationStage:
        """Get current conversation stage for a customer"""
        return self._stages.get(phone, ConversationStage.IDLE)

    def update_stage(self, phone: str, intent: str):
        """
        Update conversation stage based on the intent.

        Args:
            phone: Customer phone
            intent: Classified intent
        """
        current = self.get_stage(phone)
        new_stage = INTENT_STAGE_MAP.get(intent, current)

        if new_stage == current:
            return

        # Check if transition is valid
        valid = VALID_TRANSITIONS.get(current, set())
        if new_stage not in valid:
            logger.warning(
                f"Invalid stage transition for {phone[:8]}: "
                f"{current.value} -> {new_stage.value} (intent: {intent}). Allowing anyway."
            )

        # Record transition
        if phone not in self._stage_history:
            self._stage_history[phone] = []
        self._stage_history[phone].append({
            "from": current.value,
            "to": new_stage.value,
            "intent": intent,
            "timestamp": datetime.utcnow(),
        })

        # Keep history bounded
        if len(self._stage_history[phone]) > 20:
            self._stage_history[phone] = self._stage_history[phone][-20:]

        logger.info(f"Stage {phone[:8]}: {current.value} -> {new_stage.value}")
        self._stages[phone] = new_stage

    def reset_stage(self, phone: str):
        """Reset conversation stage for new conversations"""
        if phone in self._stages:
            del self._stages[phone]
        if phone in self._stage_history:
            del self._stage_history[phone]

    def evaluate(
        self,
        phone: str,
        message: str,
        intent: str,
        response: str,
        conversation_history: List[dict],
        is_new_conversation: bool,
        products_in_context: Optional[List[dict]] = None,
    ) -> EvaluationResult:
        """
        Evaluate a response before sending.

        Args:
            phone: Customer phone
            message: Customer's original message
            intent: Classified intent
            response: Generated response text
            conversation_history: Recent conversation messages
            is_new_conversation: Whether this is a new conversation (>30min gap)
            products_in_context: Products currently shown to this customer

        Returns:
            EvaluationResult with pass/fail, score, issues, and optional adjusted response
        """
        issues = []
        suggestions = []
        score = 1.0
        adjusted_response = None

        # --- Check 1: Empty response ---
        if not response or not response.strip():
            issues.append("empty_response")
            score = 0.0
            adjusted_response = (
                "Desculpe, tive um problema ao processar sua mensagem. "
                "Pode repetir?"
            )
            return EvaluationResult(
                passed=False,
                score=0.0,
                issues=issues,
                adjusted_response=adjusted_response,
                stage=self.get_stage(phone),
            )

        # --- Check 2: Repeated greeting in continuous conversation ---
        if not is_new_conversation and self._has_full_greeting(response):
            recent_greetings = self._count_recent_greetings(conversation_history)
            if recent_greetings > 0:
                issues.append("repeated_greeting")
                score -= 0.3
                suggestions.append(
                    "Greeting already sent in this conversation. "
                    "Stripped greeting prefix."
                )
                adjusted_response = self._strip_greeting(response)

        # --- Check 3: Product search claims vs reality ---
        if intent == "busca_produto" and products_in_context is not None:
            if len(products_in_context) == 0 and "encontrei" in response.lower():
                issues.append("claims_products_found_but_empty")
                score -= 0.5
                suggestions.append(
                    "Response says products were found but product list is empty."
                )

        # --- Check 4: Cart add without product context ---
        if intent == "adicionar_carrinho":
            stage = self.get_stage(phone)
            if (
                stage in (ConversationStage.IDLE, ConversationStage.GREETING)
                and not products_in_context
            ):
                issues.append("cart_add_without_browsing")
                score -= 0.2
                suggestions.append(
                    "Customer hasn't browsed products yet. "
                    "Consider asking what they want first."
                )

        # --- Check 5: Intent/response coherence ---
        coherence = self._check_coherence(intent, response)
        if not coherence["coherent"]:
            issues.append(f"intent_response_mismatch:{intent}")
            score -= 0.4
            suggestions.append(coherence["reason"])

        # --- Check 6: Exposed internal data ---
        if re.search(r"produto_id|item_id|uuid", response.lower()):
            issues.append("exposed_internal_id")
            score -= 0.5
            suggestions.append("Response contains internal IDs visible to customer.")

        # --- Check 7: Response length ---
        if len(response) > 2000:
            issues.append("response_too_long")
            score -= 0.1
            suggestions.append("Response exceeds 2000 chars. Consider splitting.")

        # --- Check 8: No-emoji policy ---
        if self._contains_emoji(response):
            issues.append("contains_emoji")
            score -= 0.1
            suggestions.append("Store policy: no emojis in responses.")

        # --- Check 9: Generic error exposed ---
        error_patterns = [
            r"traceback",
            r"exception",
            r"error.*line \d+",
            r"keyerror",
            r"typeerror",
            r"nonetype",
        ]
        response_lower = response.lower()
        for pattern in error_patterns:
            if re.search(pattern, response_lower):
                issues.append("exposed_error_message")
                score -= 0.5
                adjusted_response = (
                    "Desculpe, tive um problema ao processar sua mensagem. "
                    "Pode tentar novamente?"
                )
                break

        # Update stage
        self.update_stage(phone, intent)

        # Clamp score
        score = max(0.0, min(1.0, score))
        passed = score >= 0.5 and "empty_response" not in issues

        if issues:
            logger.warning(
                f"Response eval {phone[:8]}: issues={issues} score={score:.2f}"
            )
        else:
            logger.info(
                f"Response eval {phone[:8]}: OK score={score:.2f} "
                f"stage={self.get_stage(phone).value}"
            )

        return EvaluationResult(
            passed=passed,
            score=score,
            issues=issues,
            suggestions=suggestions,
            adjusted_response=adjusted_response if adjusted_response else None,
            stage=self.get_stage(phone),
        )

    def _has_full_greeting(self, response: str) -> bool:
        """Check if response contains a full greeting with attendant name"""
        patterns = [
            r"Bom dia.*Guilherme",
            r"Boa tarde.*Guilherme",
            r"Boa noite.*Guilherme",
            r"Voc[eê] t[aá] falando.*com o Guilherme",
        ]
        return any(re.search(p, response) for p in patterns)

    def _count_recent_greetings(self, history: List[dict]) -> int:
        """Count full greetings in recent bot messages"""
        count = 0
        for msg in history[-5:]:
            if (
                msg.get("role") == "assistant"
                and self._has_full_greeting(msg.get("content", ""))
            ):
                count += 1
        return count

    def _strip_greeting(self, response: str) -> str:
        """Remove greeting prefix, keep content after it"""
        parts = response.split("\n\n", 1)
        if len(parts) > 1 and self._has_full_greeting(parts[0]):
            return parts[1]
        return response

    def _check_coherence(self, intent: str, response: str) -> dict:
        """Check if response content matches the expected intent"""
        if intent not in COHERENCE_MARKERS:
            return {"coherent": True, "reason": None}

        markers = COHERENCE_MARKERS[intent]
        response_lower = response.lower()

        # Normalize accented characters for matching
        response_normalized = (
            response_lower
            .replace("á", "a").replace("à", "a").replace("ã", "a").replace("â", "a")
            .replace("é", "e").replace("ê", "e")
            .replace("í", "i")
            .replace("ó", "o").replace("ô", "o").replace("õ", "o")
            .replace("ú", "u").replace("ç", "c")
        )

        found = any(
            m in response_lower or m in response_normalized
            for m in markers
        )

        if not found:
            return {
                "coherent": False,
                "reason": (
                    f"Response for '{intent}' missing expected content. "
                    f"Expected one of: {markers}"
                ),
            }

        return {"coherent": True, "reason": None}

    def _contains_emoji(self, text: str) -> bool:
        """Check if text contains emoji characters"""
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE,
        )
        return bool(emoji_pattern.search(text))
