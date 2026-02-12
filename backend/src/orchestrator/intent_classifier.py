"""
Intent Classifier - Identifica qual Goal executar
Usa LLM (OpenAI) para classificação robusta com fallback para regex
"""

import re
import os
import logging
from typing import Optional, Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)


class IntentClassifier:
    """Classifica intenção do usuário e mapeia para Goals"""

    def __init__(self):
        """Inicializa o classificador com cache e cliente OpenAI"""
        # Cache de classificações para economizar tokens
        # Key: mensagem normalizada, Value: intent classificado
        self._classification_cache: Dict[str, str] = {}

        # Cliente OpenAI (None se não configurado)
        self.openai_client = None
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and api_key != "sua-chave-openai-aqui":
            try:
                self.openai_client = OpenAI(api_key=api_key)
                logger.info("✅ OpenAI configurado para classificação de intents")
            except Exception as e:
                logger.warning(f"⚠️ Falha ao inicializar OpenAI: {e}")
                self.openai_client = None
        else:
            logger.info("ℹ️ OpenAI não configurado, usando apenas regex")

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

        # Informação sobre entrega (ANTES de informacao_loja para prioridade)
        "informacao_entrega": [
            r"\bentreg(a|as|ar|am|amos)\b",  # Qualquer menção a "entrega"
            r"\b(prazo|tempo|quanto\s+tempo|demora).*(entrega|entregar)\b",
            r"\bentreg.*hoje|hoje.*entrega\b",
            r"\bentrega.*(r[aá]pida|urgente|express|funciona|demora)\b",
            r"\b(sobre|como|informa[cç][aã]o|informa[cç][oõ]es).*(entrega|entregar)\b",
            r"\bfora\s+de\s+bh\b",
            r"\b(faz|fazem|tem|voc[eê]s?.*faz).*(entrega|entregar)\b",
            r"\bentrega.*(bh|belo\s+horizonte)\b",
            r"entrega.*funciona",  # "como a entrega funciona"
        ],

        # Informação sobre loja (horário, localização, contato)
        "informacao_loja": [
            r"\b(hor[aá]rio|abre|fecha)\b",  # Removido "funciona" genérico
            r"\bhor[aá]rio.*funciona(mento)?\b",  # "horário de funcionamento"
            r"\b(como|sobre).*(loja|estabelecimento).*funciona\b",  # "como a loja funciona"
            r"\bfunciona.*loja\b",  # "funciona a loja"
            r"\bonde\s+(fica|[eé]|est[aá])\s+(a\s+)?(loja|voc[eê]s?)\b",
            r"\bendereco|endereço\b",
            r"\b(telefone|whatsapp|contato)\b",
            r"\b(mercado\s+central|localiza[cç][aã]o)\b",
            r"\binforma[cç][aã]o.*loja\b",
        ],

        # Rastreamento de pedido
        "rastreamento_pedido": [
            r"\b(c[oó]digo|rastreio|rastreamento)\b",
            r"\bacompanhar\s+pedido\b",
            r"onde\s+(est[aá]|t[aá])\s+meu\s+pedido",
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

    def _normalize_message(self, message: str) -> str:
        """Normaliza mensagem para usar como chave de cache"""
        return message.lower().strip()

    def classify_with_llm(self, message: str) -> Optional[str]:
        """
        Classifica intent usando LLM (OpenAI).

        Args:
            message: Mensagem do usuário

        Returns:
            Nome do intent ou None se falhar
        """
        if not self.openai_client:
            return None

        # Verificar cache
        cache_key = self._normalize_message(message)
        if cache_key in self._classification_cache:
            cached_intent = self._classification_cache[cache_key]
            logger.info(f"💾 Intent recuperado do cache: {cached_intent}")
            return cached_intent

        try:
            # Prompt estruturado com todos os intents
            prompt = f"""Você é um assistente que classifica mensagens de clientes da Roça Capital (loja de queijos e produtos artesanais).

Classifique a mensagem abaixo em UMA dessas categorias (responda APENAS com o nome da categoria):

- atendimento_inicial: saudações simples, agradecimentos (ex: "oi", "bom dia", "obrigado")
- informacao_entrega: perguntas sobre entrega, prazo, frete, envio (ex: "como funciona a entrega?", "fazem entrega?")
- informacao_loja: horário de funcionamento, localização, contato (ex: "qual o horário?", "onde fica?")
- informacao_pagamento: formas de pagamento, desconto PIX, vale-alimentação (ex: "aceitam PIX?", "tem desconto?")
- retirada_loja: retirada de pedido na loja (ex: "posso retirar na loja?")
- rastreamento_pedido: código de rastreio, acompanhamento (ex: "onde está meu pedido?", "rastreamento")
- armazenamento_queijo: como guardar/conservar queijo (ex: "como guardar o queijo?")
- embalagem_presente: embalagens, caixas, presentes, kits (ex: "tem embalagem de presente?")
- busca_produto: procura por produtos específicos (ex: "tem queijo canastra?", "quero cachaça")
- adicionar_carrinho: adicionar item ao carrinho (ex: "adiciona 2 queijos")
- ver_carrinho: visualizar carrinho (ex: "ver meu carrinho")
- calcular_frete: calcular valor do frete (ex: "quanto custa o frete?")
- finalizar_pedido: finalizar compra/pedido (ex: "quero finalizar", "fechar pedido")
- consultar_pedido: consultar status de pedidos (ex: "meus pedidos", "status do pedido")

Mensagem do cliente: "{message}"

Categoria:"""

            # Chamar OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Modelo rápido e barato
                messages=[
                    {"role": "system", "content": "Você classifica mensagens em categorias predefinidas. Responda APENAS com o nome da categoria, sem explicações."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,  # Determinístico
                max_tokens=20,  # Resposta curta
            )

            intent = response.choices[0].message.content.strip().lower()

            # Validar se é um intent válido
            valid_intents = list(self.INTENT_PATTERNS.keys())
            if intent in valid_intents:
                # Salvar no cache
                self._classification_cache[cache_key] = intent
                logger.info(f"🤖 Intent classificado por LLM: {intent}")
                return intent
            else:
                logger.warning(f"⚠️ LLM retornou intent inválido: {intent}")
                return None

        except Exception as e:
            logger.error(f"❌ Erro ao classificar com LLM: {e}")
            return None

    def classify_with_regex(self, message: str) -> str:
        """
        Classifica intent usando regex (método tradicional).

        Args:
            message: Mensagem do usuário

        Returns:
            Nome do intent
        """
        message_lower = message.lower().strip()

        # Testar cada intent em ordem de prioridade
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    logger.info(f"🎯 Intent detectado (regex): {intent}")
                    return intent

        # Fallback: busca de produto
        logger.info("🤷 Intent não identificado (regex), usando fallback: busca_produto")
        return "busca_produto"

    def classify(self, message: str) -> str:
        """
        Classifica mensagem usando LLM (se disponível) com fallback para regex.

        Args:
            message: Mensagem do usuário

        Returns:
            Nome do intent

        Example:
            >>> classifier = IntentClassifier()
            >>> intent = classifier.classify("Quero queijo canastra")
            >>> print(intent)  # "busca_produto"
        """
        # Tentar LLM primeiro
        if self.openai_client:
            llm_intent = self.classify_with_llm(message)
            if llm_intent:
                return llm_intent
            logger.warning("⚠️ LLM falhou, usando fallback regex")

        # Fallback: regex
        return self.classify_with_regex(message)

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
    # Testes
    test_cases = [
        "Oi, bom dia!",
        "Sobre as entregas como funciona?",
        "Quero queijo canastra",
        "Adiciona 2 unidades",
        "Ver meu carrinho",
        "Quanto fica o frete?",
        "Quero finalizar o pedido",
        "Cadê meu pedido?",
        "Vocês fazem entrega?",
        "Qual o horário de funcionamento?",
    ]

    print("🧪 Testando Intent Classifier:\n")

    # Testar com LLM (se disponível)
    classifier = IntentClassifier()
    print(f"🤖 OpenAI disponível: {'Sim' if classifier.openai_client else 'Não'}\n")

    for message in test_cases:
        intent = classifier.classify(message)
        context = classifier.get_intent_context(intent)

        print(f"📝 Mensagem: \"{message}\"")
        print(f"   🎯 Intent: {intent}")
        print(f"   📄 Goal: {context.get('goal_file')}")
        print()
