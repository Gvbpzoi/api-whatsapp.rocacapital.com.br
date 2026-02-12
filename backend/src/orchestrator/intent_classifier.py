"""
Intent Classifier - Identifica qual Goal executar
"""

import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class IntentClassifier:
    """Classifica intenção do usuário e mapeia para Goals"""

    # Padrões para cada intent/goal (ordem importa!)
    INTENT_PATTERNS = {
        # Atendimento inicial (testar PRIMEIRO)
        "atendimento_inicial": [
            r"^(oi|ol[aá]|hey|ei|opa)([,!?.\s]+(bom\s+dia|boa\s+tarde|boa\s+noite)?[,!?.\s]*)?$",
            r"^(oi|ol[aá]|hey|ei|opa)[,!?.\s]+(preciso|quero|gostaria|pode).*(ajuda|atend)",
            r"^(bom\s+dia|boa\s+tarde|boa\s+noite)[,!?.\s]*$",
            r"^(help|ajuda|socorro)[,!?.\s]*$",
            r"(obrigad|valeu|thanks|grato|agradeço)",
        ],

        # Finalizar pedido (antes de "ver carrinho")
        "finalizar_pedido": [
            r"\b(finaliz|fecha|fech|conclu|termin|pront)",
            r"\bquero\s+(pagar|finalizar|fechar)",
            r"\b(pagamento|pagar)\b",
        ],

        # Consultar pedido (antes de "ver carrinho")
        "consultar_pedido": [
            r"\b(onde|cad[eê])\s+(est[aá]|t[aá])\s+(o\s+)?(meu\s+)?pedido",
            r"\brastreamento\b",
            r"\bstatus\s+(do\s+)?pedido",
            r"\b(pedido|compra)\s+#?\d+",
            r"\b(meu|meus)\s+pedidos?\b",
        ],

        # Informação sobre loja (horário, localização, contato)
        "informacao_loja": [
            r"\b(hor[aá]rio|abre|fecha|funciona)\b",
            r"\bonde\s+(fica|[eé]|est[aá])\b",
            r"\bendereco|endereço\b",
            r"\b(telefone|whatsapp|contato)\b",
            r"\b(mercado\s+central|localiza[cç][aã]o)\b",
        ],

        # Rastreamento de pedido
        "rastreamento_pedido": [
            r"\b(c[oó]digo|rastreio|rastreamento)\b",
            r"\bacompanhar\s+pedido\b",
            r"onde\s+(est[aá]|t[aá])\s+meu\s+pedido",
        ],

        # Informação sobre entrega
        "informacao_entrega": [
            r"\b(prazo|tempo|quanto\s+tempo|demora)\s+(entrega|entregar)\b",
            r"\bentreg.*hoje|hoje.*entrega\b",
            r"\bentrega\s+(r[aá]pida|urgente|express)\b",
            r"\bfora\s+de\s+bh\b",
        ],

        # Retirada na loja
        "retirada_loja": [
            r"\bretir.*loja\b",
            r"\bpegar\s+(na\s+)?loja\b",
            r"\bbuscar\s+(na\s+)?loja\b",
        ],

        # Informação sobre pagamento
        "informacao_pagamento": [
            r"\b(desconto|promo[cç][aã]o)\b",
            r"\b(pix|cart[aã]o|dinheiro|pagamento)\b",
            r"\bforma.*pagamento\b",
            r"\bvale.*aliment\b",
        ],

        # Armazenamento de queijo
        "armazenamento_queijo": [
            r"\b(armazen|guard|conserv).*queijo\b",
            r"\bcomo\s+guard\b",
            r"\bgeladeira.*queijo|queijo.*geladeira\b",
            r"\b(conserv|dur).*queijo\b",
        ],

        # Embalagem para presente
        "embalagem_presente": [
            r"\b(embalagem|caixa|embalar).*presente\b",
            r"\bpresente\b",
            r"\bcesta|kit\b",
        ],

        # Calcular frete
        "calcular_frete": [
            r"\b(quanto|qual)\s+(fica|[eé]|custa|cobra)\s+(o\s+)?frete",
            r"\bcalcul.*frete\b",
            r"\bcep\b",
            r"meu\s+cep\s+([eé]|:)",
        ],

        # Adicionar carrinho
        "adicionar_carrinho": [
            r"\b(adiciona|coloca|quero)\s+(isso|esse|esta|este|o|a|\d+)",
            r"\b(adiciona|quero)\s+(\d+|um|uma|dois|duas|tr[eê]s)",
            r"\b(\d+)\s*(un|unidade|kg|kilo)",
        ],

        # Ver carrinho
        "ver_carrinho": [
            r"\b(ver|mostre|mostra|exibe)\s+(o\s+)?(meu\s+)?(carrinho|pedido)",
            r"\bmeu\s+carrinho\b",
            r"o que (eu|j[aá])\s+(tenho|pedi)",
        ],

        # Busca produto (DEFAULT - por último)
        "busca_produto": [
            r"\b(quero|busco|procuro|tem|vende)\s+(queijo|cacha[cç]a|doce|caf[eé]|mel)",
            r"\b(queijo|cacha[cç]a|doce|caf[eé]|mel|geleia|p[aã]o|biscoito)\b",
            r"\b(produtos|cat[aá]logo|card[aá]pio|op[cç][oõ]es)\b",
            r"o que voc[eê]s? (t[eê]m|vende)",
        ],
    }

    def classify(self, message: str) -> str:
        """
        Classifica mensagem e retorna intent (goal).

        Args:
            message: Mensagem do usuário

        Returns:
            Nome do goal (ex: "busca_produto")

        Example:
            >>> classifier = IntentClassifier()
            >>> intent = classifier.classify("Quero queijo canastra")
            >>> print(intent)  # "busca_produto"
        """
        message_lower = message.lower().strip()

        # Testar cada intent em ordem de prioridade
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    logger.info(f"🎯 Intent detectado: {intent} (padrão: {pattern[:30]}...)")
                    return intent

        # Fallback: se não identificou nenhum intent específico
        # Assume que é busca de produto (comportamento padrão)
        logger.info("🤷 Intent não identificado, usando fallback: busca_produto")
        return "busca_produto"

    def extract_search_term(self, message: str) -> Optional[str]:
        """
        Extrai termo de busca da mensagem.

        Args:
            message: Mensagem do usuário

        Returns:
            Termo de busca ou None

        Example:
            >>> classifier = IntentClassifier()
            >>> term = classifier.extract_search_term("Quero queijo canastra")
            >>> print(term)  # "queijo canastra"
        """
        message_lower = message.lower().strip()

        # Remover pontuação
        import string
        message_lower = message_lower.translate(str.maketrans('', '', string.punctuation))

        # Remover palavras comuns de busca
        stop_words = [
            "quero", "busco", "procuro", "tem", "têm", "vende", "vendem",
            "gostaria", "poderia", "pode", "me", "mostrar", "ver", "o", "a",
            "um", "uma", "os", "as", "de"
        ]

        words = message_lower.split()
        filtered_words = [w for w in words if w not in stop_words]

        if filtered_words:
            return " ".join(filtered_words)

        return None

    def extract_quantity(self, message: str) -> int:
        """
        Extrai quantidade da mensagem.

        Args:
            message: Mensagem do usuário

        Returns:
            Quantidade (default: 1)

        Example:
            >>> classifier = IntentClassifier()
            >>> qty = classifier.extract_quantity("adiciona 2 queijos")
            >>> print(qty)  # 2
        """
        # Buscar números
        match = re.search(r"\b(\d+)\b", message)
        if match:
            return int(match.group(1))

        # Números por extenso (básico)
        numero_extenso = {
            "um": 1, "uma": 1,
            "dois": 2, "duas": 2,
            "três": 3, "tres": 3,
            "quatro": 4,
            "cinco": 5,
        }

        message_lower = message.lower()
        for palavra, valor in numero_extenso.items():
            if palavra in message_lower:
                return valor

        return 1  # Default

    def get_intent_context(self, intent: str) -> Dict[str, Any]:
        """
        Retorna contexto adicional sobre o intent.

        Args:
            intent: Nome do intent

        Returns:
            Dicionário com contexto

        Example:
            >>> context = classifier.get_intent_context("busca_produto")
            >>> print(context["goal_file"])  # "2_busca_produtos"
        """
        intent_mapping = {
            "atendimento_inicial": {
                "goal_file": "1_atendimento_inicial",
                "priority": "high",
                "requires_auth": False,
            },
            "busca_produto": {
                "goal_file": "2_busca_produtos",
                "priority": "medium",
                "requires_auth": False,
            },
            "adicionar_carrinho": {
                "goal_file": "3_gestao_carrinho",
                "priority": "high",
                "requires_auth": False,
            },
            "ver_carrinho": {
                "goal_file": "3_gestao_carrinho",
                "priority": "medium",
                "requires_auth": False,
            },
            "calcular_frete": {
                "goal_file": "4_calculo_frete",
                "priority": "high",
                "requires_auth": False,
            },
            "finalizar_pedido": {
                "goal_file": "5_finalizacao_pedido",
                "priority": "critical",
                "requires_auth": True,
            },
            "consultar_pedido": {
                "goal_file": "6_consulta_pedido",
                "priority": "medium",
                "requires_auth": False,
            },
        }

        return intent_mapping.get(intent, {
            "goal_file": "unknown",
            "priority": "low",
            "requires_auth": False,
        })


# Para testes
if __name__ == "__main__":
    classifier = IntentClassifier()

    # Testes
    test_cases = [
        "Oi, bom dia!",
        "Quero queijo canastra",
        "Adiciona 2 unidades",
        "Ver meu carrinho",
        "Quanto fica o frete?",
        "Quero finalizar o pedido",
        "Cadê meu pedido?",
    ]

    print("🧪 Testando Intent Classifier:\n")

    for message in test_cases:
        intent = classifier.classify(message)
        context = classifier.get_intent_context(intent)

        print(f"📝 Mensagem: \"{message}\"")
        print(f"   🎯 Intent: {intent}")
        print(f"   📄 Goal: {context.get('goal_file')}")
        print()
