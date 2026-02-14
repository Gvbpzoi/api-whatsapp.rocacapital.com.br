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
            r"\b(pedido|compra)\s+#?\d+",  # Pedido específico com número
            r"\b(meu|meus)\s+pedidos?\s+(passado|anterior|antigo)",  # Pedidos passados
            r"\baqui\s+est[aã]o\s+seus\s+pedidos\b",  # Contexto de lista de pedidos
            r"\bpedidos?\s+(feito|realizado|antigo)",  # Pedidos já feitos
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

        # Remover item do carrinho
        "remover_item": [
            r"\b(tira|remove|retira|elimina|exclui)\s+(o|a|do|da|esse|essa|isso|isto|item)",
            r"\bn[aã]o\s+(quero|preciso)\s+mais\b",
            r"\bcancela\s+(esse|essa|o|a|item)\b",
            r"\b(tira|remove|retira)\s+(do|da)\s*(carrinho)\b",
            r"\b(remove|tira|retira)\s+(o|a)\s+\w+\s+(do\s+carrinho)\b",
        ],

        # Alterar quantidade de item no carrinho
        "alterar_quantidade": [
            r"\bs[oó]\s+quero\s+(\d+|um|uma|dois|duas|tr[eê]s|quatro|cinco)\s+(unidade|un\b)",
            r"\b(muda|altera|troca)\s+(pra|para|a\s+quantidade)\b",
            r"\b(diminui|reduz|aumenta)\s+(pra|para|a\s+quantidade)\b",
            r"\bquero\s+s[oó]\s+(\d+|um|uma|dois|duas)\b",
            r"\bcoloca\s+s[oó]\s+(\d+|um|uma|dois|duas)\b",
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
            r"o que (eu|j[aá]|voc[eê])\s+(tenho|pedi|coloc|adicion)",
            r"\b(qual|quanto)\s+(o\s+|[eé]\s+o\s+)?(valor|total|pre[cç]o)",  # "qual o valor total"
            r"\btotal\s+(da\s+)?(minha\s+)?(compra|pedido|carrinho)",  # "total da minha compra"
            r"\b(j[aá]\s+)?gast(ei|amos|ou)",  # "já gastei", "quanto gastou"
            r"(at[eé]|agora).*total",  # "até agora total"
            r"(mostra|me\s+mostra).*(carrinho|no\s+carrinho)",  # "me mostra o carrinho"
        ],

        # Busca produto (DEFAULT - por último)
        "busca_produto": [
            r"\b(quero|busco|procuro|tem|vende)\s+(queijo|cacha[cç]a|doce|caf[eé]|mel)",
            r"\b(queijo|cacha[cç]a|doce|caf[eé]|mel|geleia|p[aã]o|biscoito)\b",
            r"\b(produtos|cat[aá]logo|card[aá]pio|op[cç][oõ]es)\b",
            r"o que voc[eê]s? (t[eê]m|vende)",
            # Padrões genéricos de busca
            r"(os\s+)?que\s+(voc[eê]|voce|vc)\s+(tem|t[eê]m|vende)",
            r"pode\s+(mostrar|mostra|listar)\s+(os\s+)?que",
            r"(mostrar|mostra|listar)\s+(os\s+)?que\s+(voc[eê]|voce)\s+(tem|t[eê]m)",
            r"\btem\s+mais\b",
            r"\boutros?\b",
            r"\boutras?\s+op[cç][oõ]es\b",
        ],
    }

    def _normalize_message(self, message: str) -> str:
        """Normaliza mensagem para usar como chave de cache"""
        return message.lower().strip()

    def _stem_portuguese_plural(self, word: str) -> str:
        """
        Remove plural em português (stemming básico).
        
        Args:
            word: Palavra em português
        
        Returns:
            Palavra no singular (aproximado)
        
        Example:
            >>> classifier = IntentClassifier()
            >>> classifier._stem_portuguese_plural("azeites")
            'azeite'
            >>> classifier._stem_portuguese_plural("queijos")
            'queijo'
        """
        word_lower = word.lower()
        
        # Regra 1: palavras terminadas em "ões" -> "ão" (ex: limões -> limão)
        if word_lower.endswith("ões"):
            return word_lower[:-3] + "ão"
        
        # Regra 2: palavras terminadas em "ães" -> "ão" (ex: pães -> pão)
        if word_lower.endswith("ães"):
            return word_lower[:-3] + "ão"
        
        # Regra 3: palavras terminadas em "ais" -> "al" (ex: especiais -> especial)
        if word_lower.endswith("ais"):
            return word_lower[:-2] + "l"
        
        # Regra 4: palavras terminadas em "eis" -> "el" ou "il" (ex: papéis -> papel)
        # Simplificado: remove "is"
        if word_lower.endswith("eis") and len(word_lower) > 4:
            return word_lower[:-2] + "l"
        
        # Regra 5: palavras terminadas em "is" -> remover "s" (ex: barris -> barril)
        if word_lower.endswith("is") and len(word_lower) > 3:
            return word_lower[:-1]
        
        # Regra 6: palavras terminadas em "es"
        # Se o caractere antes de "es" é vogal, o plural é apenas "s" (azeite→azeites)
        # Se é consoante, o plural é "es" (flor→flores)
        if word_lower.endswith("es") and len(word_lower) > 4:
            char_before_es = word_lower[-3]
            if char_before_es in "aeiouáéíóúâêîôû":
                return word_lower[:-1]  # "azeites" → "azeite"
            else:
                return word_lower[:-2]  # "flores" → "flor"
        
        # Regra 7: palavras terminadas em "s" (mais comum) -> remover "s"
        if word_lower.endswith("s") and len(word_lower) > 3:
            return word_lower[:-1]
        
        # Sem plural detectado, retornar palavra original
        return word_lower

    def classify_with_llm(self, message: str, context: Optional[Dict] = None, conversation_history: list = None) -> Optional[str]:
        """
        Classifica intent usando LLM (OpenAI).

        Args:
            message: Mensagem do usuário
            context: Contexto da conversa (opcional)
            conversation_history: Recent conversation messages (optional)

        Returns:
            Nome do intent ou None se falhar
        """
        if not self.openai_client:
            return None

        # Cache: skip for short ambiguous messages (<=3 words) since they
        # depend heavily on context ("otimo", "beleza", "dois")
        cache_key = self._normalize_message(message)
        word_count = len(cache_key.split())
        if word_count > 3 and cache_key in self._classification_cache:
            cached_intent = self._classification_cache[cache_key]
            logger.info(f"💾 Intent recuperado do cache: {cached_intent}")
            return cached_intent

        try:
            # Adicionar contexto ao prompt se disponível
            context_info = ""
            if context:
                assunto = context.get("assunto", "")
                categoria = context.get("categoria", "")
                if assunto:
                    context_info = f"\n\nCONTEXTO: Cliente está vendo produtos de '{assunto}' (categoria: {categoria})."

            # Build conversation history context
            history_info = ""
            if conversation_history:
                recent = conversation_history[-5:]
                history_lines = []
                for msg in recent:
                    role = "Cliente" if msg.get("role") == "user" else "Atendente"
                    content = str(msg.get("content", ""))[:150]
                    history_lines.append(f"  {role}: {content}")
                history_info = "\n\nHISTÓRICO RECENTE DA CONVERSA:\n" + "\n".join(history_lines)

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
- busca_produto: procura por produtos específicos OU perguntas genéricas sobre produtos disponíveis (ex: "tem queijo canastra?", "quero cachaça", "pode mostrar os que você tem?", "tem mais?", "outros?")
- adicionar_carrinho: adicionar item ao carrinho (ex: "adiciona 2 queijos", "quero mais um azeite")
- remover_item: remover item do carrinho (ex: "tira esse", "não quero mais", "remove o azeite", "cancela esse item")
- alterar_quantidade: mudar quantidade de item no carrinho (ex: "só quero 2 unidades", "diminui pra 1", "muda a quantidade")
- ver_carrinho: visualizar carrinho ATUAL, perguntas sobre total/valor da compra EM ANDAMENTO (ex: "ver meu carrinho", "qual o valor total?", "quanto já gastei?")
- calcular_frete: calcular valor do frete (ex: "quanto custa o frete?")
- finalizar_pedido: finalizar compra/pedido (ex: "quero finalizar", "fechar pedido")
- consultar_pedido: consultar status de pedidos JÁ FINALIZADOS/PASSADOS, com número de pedido (ex: "meus pedidos antigos", "pedido #123456", "status do pedido enviado")

IMPORTANTE:
- "ver_carrinho" é para compra ATUAL (em andamento).
- "consultar_pedido" é para pedidos JÁ FINALIZADOS (histórico).
- "pode mostrar os que você tem?", "tem mais?", "outros?" → busca_produto (não adicionar_carrinho)
- "não quero mais esse", "tira", "remove" → remover_item
- "só quero 2", "diminui", "muda a quantidade" → alterar_quantidade
- Mensagens curtas como "ótimo", "beleza", "ok" após mostrar produtos NÃO são atendimento_inicial — use o histórico para entender o contexto{context_info}{history_info}

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
                # Only cache longer messages (short ones are context-dependent)
                if word_count > 3:
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

    def classify(self, message: str, context: Optional[Dict] = None, stage=None, conversation_history: list = None) -> str:
        """
        Classifica mensagem usando LLM (se disponível) com fallback para regex.

        Stage-aware: when the customer is in BROWSING stage and sends a
        number (1-5), short confirmation, or selection phrase, the intent
        is overridden to adicionar_carrinho — because context tells us
        they're selecting a product, not searching for a new one.

        Args:
            message: Mensagem do usuário
            context: Contexto da conversa (opcional)
            stage: ConversationStage from response_evaluator (opcional)
            conversation_history: Recent messages for LLM context (opcional)

        Returns:
            Nome do intent
        """
        # Stage-aware override: customer just saw products and is selecting
        stage_override = self._check_stage_override(message, stage)
        if stage_override:
            logger.info(f"🎯 Stage override ({stage}): {stage_override}")
            return stage_override

        # Tentar LLM primeiro
        if self.openai_client:
            llm_intent = self.classify_with_llm(message, context, conversation_history)
            if llm_intent:
                return llm_intent
            logger.warning("⚠️ LLM falhou, usando fallback regex")

        # Fallback: regex
        return self.classify_with_regex(message)

    def _check_stage_override(self, message: str, stage) -> Optional[str]:
        """
        Check if conversation stage should override intent classification.

        When customer is BROWSING (just saw product list) and sends:
        - A number: "2", "o 2", "o segundo" → adicionar_carrinho
        - A selection: "esse", "quero esse", "pode ser" → adicionar_carrinho
        - A product-like selection: "o canastra" → adicionar_carrinho

        When customer is in CARTING/REVIEWING_CART and says:
        - "mais", "outro" → adicionar_carrinho (not busca_produto)
        """
        if stage is None:
            return None

        # Import here to avoid circular dependency at module level
        stage_value = stage.value if hasattr(stage, 'value') else str(stage)
        message_lower = message.lower().strip()

        if stage_value == "browsing":
            # Pure number selection: "2", "o 2", "o segundo", "quero o 3"
            if re.match(r'^(o\s+)?(\d+)\.?$', message_lower):
                return "adicionar_carrinho"

            # Ordinal selection: "o primeiro", "o segundo", "o terceiro"
            ordinals = [
                "primeiro", "segunda", "segundo", "terceiro", "terceira",
                "quarto", "quarta", "quinto", "quinta",
            ]
            if any(o in message_lower for o in ordinals):
                return "adicionar_carrinho"

            # Selection phrases
            selection_patterns = [
                r"^(esse|essa|este|esta)\.?$",
                r"^quero\s+(esse|essa|o\s+\d+|a\s+\d+)",
                r"^pode\s+ser\b",
                r"^vou\s+(querer|levar|pegar)\b",
                r"^(quero|leva|pega|manda)\s+(o|a|esse|essa)\b",
            ]
            if any(re.match(p, message_lower) for p in selection_patterns):
                return "adicionar_carrinho"

        elif stage_value in ("carting", "reviewing_cart"):
            # "mais um", "outro" while already in cart flow
            if re.match(r'^mais\s+(um|uma|\d+)\b', message_lower):
                return "adicionar_carrinho"

        return None

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

        # Remover palavras comuns de busca e conversação em português brasileiro
        stop_words = [
            # Verbos de busca/desejo
            "quero", "busco", "procuro", "tem", "têm", "tem", "vende", "vendem",
            "gostaria", "poderia", "pode", "queria", "gostava", "preciso", "necessito",
            "desejo", "tenho", "teria", "haveria",
            # Verbos de ação (NOVO - Bug #2)
            "cola", "coloca", "manda", "envia", "bota", "add", "adiciona",
            # Verbos de disponibilidade/conversa (Bug #7 - "trabalha com azeites?")
            "trabalha", "trabalham", "funciona", "funcionam", "mexe", "mexem",
            "faz", "fazem", "lida", "lidam", "vender", "venda",
            "dizer", "diz", "diga", "falar", "fale", "fala",
            # Verbos de informação
            "saber", "conhecer", "entender", "ver", "mostrar", "informar", "dizer",
            # Preposições e conectivos
            "sobre", "de", "da", "do", "das", "dos", "em", "na", "no", "nas", "nos",
            "para", "pra", "com", "por", "pelo", "pela", "pelos", "pelas", "ao", "aos",
            "a", "à", "às",
            # Artigos
            "o", "a", "os", "as", "um", "uma", "uns", "umas",
            # Pronomes
            "me", "mim", "te", "ti", "se", "si", "nos", "vos", "lhe", "lhes",
            "meu", "minha", "meus", "minhas", "seu", "sua", "seus", "suas",
            "esse", "essa", "esses", "essas", "este", "esta", "estes", "estas",
            "aquele", "aquela", "aqueles", "aquelas", "isso", "isto", "aquilo",
            "você", "voce", "vc",  # ADICIONADO - evita "você" como termo
            # Pronomes adicionais (NOVO - Bug #2)
            "eu", "ele", "ela", "eles", "elas", "nós", "vocês", "voces", "vcs",
            # Palavras interrogativas
            "quais", "qual", "que", "onde", "quando", "como", "porque", "por", "quanto",
            "quantos", "quantas", "quanta",
            # Palavras de cortesia/conversação
            "favor", "obrigado", "obrigada", "obrigados", "obrigadas", "por", "pfv", "pf",
            # Saudações (NOVO - Bug #2)
            "boa", "bom", "tarde", "dia", "noite", "oi", "ola", "olá", "hey", "alo", "alô",
            # Descritores genéricos
            "tipo", "tipos", "opcao", "opcoes", "opção", "opções", "disponivel", "disponiveis",
            "disponível", "disponíveis", "informacao", "informacoes", "informação", "informações",
            "algum", "alguma", "alguns", "algumas", "produto", "produtos", "item", "itens",
            # Advérbios e outros
            "mais", "menos", "muito", "muita", "pouco", "pouca", "bem", "mal", "ja", "já",
            "ainda", "tambem", "também", "so", "só", "somente", "apenas",
        ]

        words = message_lower.split()
        filtered_words = [w for w in words if w not in stop_words]
        
        # Aplicar stemming (plural -> singular) em cada palavra (Bug #3)
        stemmed_words = [self._stem_portuguese_plural(w) for w in filtered_words]

        if stemmed_words:
            return " ".join(stemmed_words)

        return None

    def extract_product_number(self, message: str) -> Optional[int]:
        """
        Extrai número de escolha de produto (1-5) da mensagem.
        Ex: "numero 2", "o 3", "#4", "item 1"
        
        Args:
            message: Mensagem do usuário
        
        Returns:
            Número do produto (1-5) ou None se não encontrado
        
        Example:
            >>> classifier = IntentClassifier()
            >>> num = classifier.extract_product_number("vou querer o numero 2")
            >>> print(num)  # 2
        """
        message_lower = message.lower()
        
        # Padrões para número de escolha (ordem de prioridade)
        patterns = [
            r'n[uú]mero\s+([1-5])',  # "numero 2", "número 3"
            r'num\s+([1-5])',  # "num 2"
            r'n\s+([1-5])',  # "n 2"
            r'#\s*([1-5])',  # "#2", "# 3"
            r'item\s+([1-5])',  # "item 2"
            r'\bo\s+([1-5])\b',  # "o 2" (isolado)
            r'\ba\s+([1-5])\b',  # "a 3" (isolado)
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message_lower)
            if match:
                return int(match.group(1))

        # Numbers by extension: "numero dois", "numero tres", etc.
        extenso_map = [
            (r'n[uú]mero\s+(um|uma)\b', 1),
            (r'n[uú]mero\s+(dois|duas)\b', 2),
            (r'n[uú]mero\s+(tr[eê]s)\b', 3),
            (r'n[uú]mero\s+(quatro)\b', 4),
            (r'n[uú]mero\s+(cinco)\b', 5),
            (r'\bo\s+(primeiro|primeira)\b', 1),
            (r'\bo\s+(segundo|segunda)\b', 2),
            (r'\bo\s+(terceiro|terceira)\b', 3),
            (r'\bo\s+(quarto|quarta)\b', 4),
            (r'\bo\s+(quinto|quinta)\b', 5),
        ]
        for pattern, num in extenso_map:
            if re.search(pattern, message_lower):
                return num

        return None

    def extract_quantity(self, message: str) -> int:
        """
        Extrai quantidade da mensagem com parsing consciente de contexto.
        
        Prioridade:
        1. Padrões "X unidade(s)" ou "X un" (mais específico)
        2. Padrões "mais um/uma/dois/tres"
        3. Números por extenso no início ("dois azeites", "tres queijos")
        4. Números isolados (excluindo números de item: "numero 2", "#3", etc)
        5. Default: 1

        Args:
            message: Mensagem do usuário

        Returns:
            Quantidade (default: 1)

        Example:
            >>> classifier = IntentClassifier()
            >>> qty = classifier.extract_quantity("vou querer o numero 2 3 unidades dele")
            >>> print(qty)  # 3 (não 2!)
        """
        message_lower = message.lower()
        
        # 1. PRIORIDADE ALTA: Padrões explícitos de quantidade
        # "3 unidades", "2 un", "5 unidade"
        match = re.search(r'(\d+)\s*(?:unidades?|un\b|kg|kilo)', message_lower)
        if match:
            return int(match.group(1))
        
        # 2. Padrões "mais um/uma/dois/tres"
        patterns_mais = {
            r'mais\s+um\b': 1,
            r'mais\s+uma\b': 1,
            r'mais\s+dois\b': 2,
            r'mais\s+duas\b': 2,
            r'mais\s+tr[eê]s\b': 3,
            r'mais\s+quatro\b': 4,
            r'mais\s+cinco\b': 5,
        }
        
        for pattern, qty in patterns_mais.items():
            if re.search(pattern, message_lower):
                return qty
        
        # 3. Números por extenso no INÍCIO da mensagem
        # "dois azeites", "tres queijos" (não "numero dois")
        numero_extenso_inicio = {
            r'^(um|uma)\s+\w+': 1,
            r'^(dois|duas)\s+\w+': 2,
            r'^(tr[eê]s)\s+\w+': 3,
            r'^(quatro)\s+\w+': 4,
            r'^(cinco)\s+\w+': 5,
        }
        
        for pattern, qty in numero_extenso_inicio.items():
            if re.search(pattern, message_lower):
                return qty
        
        # 4. EXCLUIR números que são escolhas de item (não quantidade)
        # Padrões a IGNORAR: "numero X", "num X", "n X", "#X", "o X", "item X"
        numero_item_patterns = [
            r'n[uú]mero\s+\d+',
            r'num\s+\d+',
            r'n\s+\d+',
            r'#\s*\d+',
            r'item\s+\d+',
            r'\bo\s+\d+\b',
            r'\ba\s+\d+\b',
        ]
        
        # Remover esses padrões temporariamente da mensagem
        temp_message = message_lower
        for pattern in numero_item_patterns:
            temp_message = re.sub(pattern, '', temp_message)
        
        # Agora buscar número na mensagem limpa
        match = re.search(r'\b(\d+)\b', temp_message)
        if match:
            return int(match.group(1))
        
        # 5. Números por extenso (genérico, sem contexto)
        numero_extenso = {
            "um": 1, "uma": 1,
            "dois": 2, "duas": 2,
            "três": 3, "tres": 3,
            "quatro": 4,
            "cinco": 5,
        }
        
        for palavra, valor in numero_extenso.items():
            if re.search(r'\b' + palavra + r'\b', message_lower):
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
