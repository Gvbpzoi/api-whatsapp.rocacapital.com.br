"""
Intent Handlers - Individual handler functions for each intent.

Each handler:
- Takes a HandlerContext with all shared state
- Returns a response string
- Is independently testable (no global state)

The dispatcher in zapi_webhook.py creates the context and calls
the appropriate handler via the INTENT_HANDLERS dict.
"""

from dataclasses import dataclass
from typing import Optional, Any, Dict, Callable
from loguru import logger
import re

from . import respostas_roca_capital as resp


# ==================== Shared Context ====================

@dataclass
class HandlerContext:
    """Context passed to every intent handler"""
    phone: str
    message: str
    hora_mensagem: int
    is_nova_conversa: bool
    nome_cliente: Optional[str]
    comeca_com_saudacao: bool
    eh_so_saudacao: bool
    # Service instances (injected, not imported)
    session_manager: Any = None
    intent_classifier: Any = None
    tools_helper: Any = None


# ==================== Detection Utilities ====================
# Moved here from zapi_webhook.py so handlers can use them
# without circular imports.

def detectar_saudacao_inicial(message: str) -> bool:
    """Detecta se a mensagem começa com uma saudação."""
    mensagem_lower = message.lower().strip()
    saudacoes = [
        "oi", "olá", "ola", "bom dia", "boa tarde",
        "boa noite", "hey", "alo", "alô", "opa",
    ]
    return any(mensagem_lower.startswith(s) for s in saudacoes)


def eh_apenas_saudacao(message: str) -> bool:
    """Verifica se a mensagem é APENAS uma saudação."""
    mensagem_limpa = (
        message.lower().strip()
        .replace("!", "").replace("?", "")
        .replace(".", "").replace(",", "")
    )
    saudacoes_completas = [
        "oi", "olá", "ola", "bom dia", "boa tarde", "boa noite",
        "hey", "alo", "alô", "opa", "e ai", "e aí", "eai",
        "oi tudo bem", "ola tudo bem", "olá tudo bem",
    ]
    return mensagem_limpa in saudacoes_completas


def detectar_localizacao(message: str) -> str:
    """
    Detecta localização na mensagem.
    Returns: "bh", "fora_bh", ou "desconhecido"
    """
    mensagem_lower = message.lower()

    bairros_bh = [
        "pampulha", "savassi", "lourdes", "funcionários", "funcionarios",
        "centro", "barro preto", "santo agostinho", "santa efigênia",
        "santa efigenia", "carlos prates", "lagoinha", "floresta",
        "santa tereza", "santa teresa", "mangabeiras", "belvedere",
        "buritis", "gutierrez", "são bento", "sao bento", "cidade nova",
        "padre eustáquio", "padre eustaquio", "itapoã", "itapoa",
        "castelo", "prado", "calafate", "caiçara", "caiçaras",
        "caicara", "caicaras", "são pedro", "sao pedro", "barreiro",
        "venda nova", "eldorado", "sion",
    ]

    regiao_metropolitana = [
        "nova lima", "sabará", "sabara", "contagem", "betim",
        "ribeirão das neves", "ribeirao das neves", "santa luzia",
        "lagoa santa", "vespasiano", "pedro leopoldo", "raposos",
        "rio acima", "brumadinho", "ibirité", "ibirite",
        "mateus leme", "juatuba", "esmeraldas", "confins", "florestal",
    ]

    for bairro in bairros_bh:
        if bairro in mensagem_lower:
            return "bh"

    for cidade in regiao_metropolitana:
        if cidade in mensagem_lower:
            return "bh"

    if any(t in mensagem_lower for t in ["belo horizonte", "bh", "belô", "belo hte"]):
        return "bh"

    if any(t in mensagem_lower for t in [
        "cep", "são paulo", "rio de janeiro", "minas gerais", "mg", "sp", "rj",
    ]):
        return "fora_bh"

    if re.search(r'\d{5}-?\d{3}', mensagem_lower):
        return "fora_bh"

    return "desconhecido"


def detectar_pergunta_nome(message: str) -> bool:
    """Detecta se o cliente está perguntando o nome do atendente."""
    mensagem_lower = message.lower()
    padroes = [
        r"com quem (eu )?falo",
        r"com quem (eu )?to falando",
        r"com quem (eu )?estou falando",
        r"qual (o |é o )?seu nome",
        r"quem (é|e) (você|voce|vc)",
        r"você (é|e) quem",
        r"seu nome",
        r"como.*você.*chama",
        r"como.*voce.*chama",
        r"como.*vc.*chama",
    ]
    return any(re.search(p, mensagem_lower) for p in padroes)


def extrair_nome_cliente(message: str, historico: list) -> Optional[str]:
    """
    Detecta se a mensagem é uma resposta com o nome do cliente.
    Returns: Nome do cliente ou None
    """
    if not historico:
        return None

    ultima_msg_bot = None
    for msg in reversed(historico):
        if msg["role"] == "assistant":
            ultima_msg_bot = msg["content"].lower()
            break

    if not ultima_msg_bot or "qual é o seu nome" not in ultima_msg_bot:
        return None

    mensagem = message.strip()
    padroes = [
        r"(?:meu nome (?:é|e)|me chamo|sou(?: o| a)?) ([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ][a-záàâãéèêíïóôõöúçñ]+)",
        r"^(?:é|e) ([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ][a-záàâãéèêíïóôõöúçñ]+)",
        r"^([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ][a-záàâãéèêíïóôõöúçñ]+)$",
    ]
    for padrao in padroes:
        match = re.search(padrao, mensagem, re.IGNORECASE)
        if match:
            return match.group(1).capitalize()
    return None


def detectar_pergunta_generica_produtos(message: str) -> bool:
    """Detecta pergunta genérica sobre produtos."""
    mensagem_lower = message.lower()
    padroes = [
        r"quais? queijos? (você |voce |vc )?tem",
        r"que queijos? (você |voce |vc )?tem",
        r"o que (você |voce |vc )?tem",
        r"tem quai(s|l)",
        r"(o que|que) .*disponível",
        r"(o que|que) .*disponiveis",
        r"teria alguma sugest(ão|ao)",
        r"pode sugerir",
        r"me sugere",
        r"tipos? de queijo",
        r"variedades? de queijo",
        r"opcoes de queijo",
        r"opções de queijo",
        r"(pode\s+)?(mostrar|mostra|listar)\s+(os\s+)?que",
        r"os\s+que\s+(você|voce|vc)\s+(tem|têm)",
        r"\btem\s+mais\b",
        r"\boutros?\b",
        r"\boutras?\s+op[cç][oõ]es\b",
    ]
    return any(re.search(p, mensagem_lower) for p in padroes)


def detectar_referencia_a_escolha(message: str) -> bool:
    """Detecta referência a produto escolhido antes."""
    mensagem_lower = message.lower()
    patterns = [
        r"\bmais\s+(um|uma|dois|duas|\d+)\s+\w+",
        r"\boutr[oa]\s+\w+",
        r"\baquele\s+\w+",
        r"\bmesm[oa]\s+\w+",
    ]
    return any(re.search(p, mensagem_lower) for p in patterns)


def detectar_despedida(message: str) -> bool:
    """Detecta despedida."""
    mensagem_lower = message.lower()
    padroes = [
        r"vou (dar uma )?olha(r|da)",
        r"vou ver",
        r"vou olhar (o |os )?produtos?",
        r"vou olhar (o |no )?site",
        r"vou pensar",
        r"depois (eu )?volto",
        r"(até|ate) (logo|mais|breve)",
        r"tchau",
        r"obrigad[oa].*tchau",
        r"falou",
        r"valeu.*tchau",
        r"vo(u|lto) (mais tarde|depois)",
    ]
    return any(re.search(p, mensagem_lower) for p in padroes)


def detectar_urgencia(message: str) -> bool:
    """Detecta urgência."""
    mensagem_lower = message.lower()
    padroes = [
        r"\bhoje\b", r"\bagora\b", r"\bjá\b", r"\bja\b",
        r"\burgente\b", r"\burgência\b", r"\bpra\s+hoje\b",
        r"\bpara\s+hoje\b", r"\brápido\b", r"\brapido\b",
        r"\blogo\b", r"\bjá\s+já\b",
    ]
    return any(re.search(p, mensagem_lower) for p in padroes)


def detectar_data_futura(message: str) -> bool:
    """Detecta data futura."""
    mensagem_lower = message.lower()
    padroes = [
        r"\bamanhã\b", r"\bamanha\b", r"\bsemana\s+que\s+vem\b",
        r"\bpróxima\s+semana\b", r"\bproxima\s+semana\b",
        r"\bmês\s+que\s+vem\b", r"\bmes\s+que\s+vem\b",
        r"\bdaqui\s+\d+\s+dia", r"\bsegunda\b", r"\bterça\b",
        r"\bquarta\b", r"\bquinta\b", r"\bsexta\b",
        r"\bsábado\b", r"\bsabado\b", r"\bdomingo\b",
        r"\bdentro\s+de\s+\d+\s+dia", r"\d{1,2}/\d{1,2}",
    ]
    return any(re.search(p, mensagem_lower) for p in padroes)


# ==================== Greeting Prefix Helper ====================

def _greeting_prefix(ctx: HandlerContext) -> str:
    """Generate greeting prefix for info responses."""
    if ctx.comeca_com_saudacao and not ctx.eh_so_saudacao:
        return resp.gerar_saudacao_contextual(
            ctx.hora_mensagem, tem_pedido=True, nome_cliente=ctx.nome_cliente,
        ) + "\n\n"
    return ""


# ==================== Intent Handlers ====================


def handle_atendimento_inicial(ctx: HandlerContext) -> str:
    """Handle greetings and initial contact"""
    if not ctx.is_nova_conversa:
        # Mirror the client's greeting when in a continuous conversation
        msg = ctx.message.lower().strip()
        if "bom dia" in msg:
            return "Bom dia! Em que posso te ajudar?"
        elif "boa tarde" in msg:
            return "Boa tarde! Em que posso te ajudar?"
        elif "boa noite" in msg:
            return "Boa noite! Em que posso te ajudar?"
        return "Oi! Em que posso te ajudar?"
    return resp.gerar_saudacao_contextual(
        ctx.hora_mensagem, tem_pedido=False, nome_cliente=ctx.nome_cliente,
    )


def handle_informacao_loja(ctx: HandlerContext) -> str:
    """Handle store info questions (hours, location, contact)"""
    return _greeting_prefix(ctx) + resp.INFORMACAO_LOJA


def handle_informacao_entrega(ctx: HandlerContext) -> str:
    """Handle delivery info questions"""
    localizacao = detectar_localizacao(ctx.message)
    logger.info(f"Localização detectada: {localizacao}")

    if ctx.is_nova_conversa:
        prefix = resp.gerar_saudacao_contextual(
            ctx.hora_mensagem, tem_pedido=True, nome_cliente=ctx.nome_cliente,
        ) + "\n\n"
    else:
        prefix = ""

    if localizacao == "bh":
        return prefix + resp.INFORMACAO_ENTREGA_BH
    elif localizacao == "fora_bh":
        return prefix + resp.INFORMACAO_ENTREGA_FORA_BH
    else:
        return prefix + resp.INFORMACAO_ENTREGA_GERAL


def handle_retirada_loja(ctx: HandlerContext) -> str:
    """Handle store pickup questions"""
    return _greeting_prefix(ctx) + resp.RETIRADA_LOJA


def handle_rastreamento_pedido(ctx: HandlerContext) -> str:
    """Handle order tracking questions"""
    return _greeting_prefix(ctx) + resp.RASTREAMENTO


def handle_informacao_pagamento(ctx: HandlerContext) -> str:
    """Handle payment info questions"""
    return _greeting_prefix(ctx) + resp.INFORMACAO_PAGAMENTO


def handle_armazenamento_queijo(ctx: HandlerContext) -> str:
    """Handle cheese storage questions"""
    return resp.ARMAZENAMENTO_QUEIJO


def handle_embalagem_presente(ctx: HandlerContext) -> str:
    """Handle gift wrapping questions"""
    return resp.EMBALAGEM_PRESENTE


def handle_busca_produto(ctx: HandlerContext) -> str:
    """Handle product search"""
    sm = ctx.session_manager
    ic = ctx.intent_classifier
    th = ctx.tools_helper

    # Generic product question (no specific term)
    if detectar_pergunta_generica_produtos(ctx.message):
        logger.info("Pergunta genérica sobre produtos")
        return resp.RESPOSTA_PRODUTOS_DISPONIVEIS

    # Extract search term
    termo = ic.extract_search_term(ctx.message)

    # Fallback to conversation context
    if not termo or not termo.strip():
        context = sm.get_conversation_subject(ctx.phone)
        if context and context.get("termo"):
            termo = context["termo"]
            logger.info(f"Usando termo do contexto: {termo}")

    logger.info(f"Termo de busca: {termo}")

    result = th.buscar_produtos(termo or ctx.message, limite=5)

    if result["status"] != "success":
        return "Ops, tive um problema ao buscar produtos. Tente novamente."

    # Save context
    sm.set_last_products_shown(ctx.phone, result["produtos"])
    sm.set_conversation_subject(
        phone=ctx.phone,
        termo=termo or ctx.message,
        produtos_ids=[p["id"] for p in result["produtos"]],
        produtos=result["produtos"],
    )

    # Build response with appropriate prefix
    if ctx.is_nova_conversa:
        prefix = (
            "Oiê, tudo bem? Meu nome é Guilherme. "
            "Peraí, que eu vou te mandar os produtos que eu tenho "
            "disponíveis aqui hoje.\n\n"
        )
    elif ctx.comeca_com_saudacao and not ctx.eh_so_saudacao:
        prefix = "Opa! "
    else:
        prefix = ""

    return prefix + resp.formatar_produto_sem_emoji(result["produtos"])


def handle_adicionar_carrinho(ctx: HandlerContext) -> str:
    """Handle add-to-cart actions"""
    sm = ctx.session_manager
    ic = ctx.intent_classifier
    th = ctx.tools_helper

    qtd = ic.extract_quantity(ctx.message)
    produto_escolhido = None
    usar_confirmacao_proativa = False

    # a) Customer mentioned a number (1-5)
    numero_produto = ic.extract_product_number(ctx.message)
    if numero_produto:
        produto_escolhido = sm.get_product_by_number(ctx.phone, numero_produto)
        if produto_escolhido:
            logger.info(f"Cliente escolheu #{numero_produto}: {produto_escolhido.get('nome')}")

    # b) Specific term in message
    if not produto_escolhido:
        termo = ic.extract_search_term(ctx.message)
        if termo and termo.strip():
            # Check if it references a previous choice
            if detectar_referencia_a_escolha(ctx.message):
                logger.info(f"Referência a escolha anterior: '{termo}'")
                last_choice = sm.get_last_choice_by_term(ctx.phone, termo)
                if last_choice:
                    produto_escolhido = last_choice["produto"]
                    usar_confirmacao_proativa = True

            # Search for product if not found in history
            if not produto_escolhido:
                result_busca = th.buscar_produtos(termo, limite=1)
                if result_busca["produtos"]:
                    produto_escolhido = result_busca["produtos"][0]

    # c) Single product in context
    if not produto_escolhido:
        produtos_contexto = sm.get_last_products_shown(ctx.phone)
        if len(produtos_contexto) == 1:
            produto_escolhido = produtos_contexto[0]

    # d) Can't determine product — ask instead of guessing
    if not produto_escolhido:
        produtos_contexto = sm.get_last_products_shown(ctx.phone)
        if produtos_contexto:
            return "Qual desses produtos você quer adicionar? Me fala o número ou o nome."
        return "Qual produto você quer adicionar ao carrinho? Me fala o nome que eu busco pra você."

    # Add to cart
    result = th.adicionar_carrinho(ctx.phone, str(produto_escolhido["id"]), qtd)

    if result["status"] == "success":
        sm.save_product_choice(ctx.phone, produto_escolhido, qtd)

        if usar_confirmacao_proativa:
            response = f"Adicionei {qtd}x {produto_escolhido['nome']}, aquele que você escolheu antes.\n\n"
        else:
            response = f"Adicionei {qtd} item(s) ao carrinho!\n\n"

        quantidade_total = result.get(
            "quantidade_total",
            sum(item["quantidade"] for item in result.get("carrinho", [])),
        )
        response += f"Total: {quantidade_total} produto(s)\n\n"
        response += "Quer adicionar mais algo ou ver o carrinho?"
        return response

    elif result["status"] == "estoque_insuficiente":
        return _handle_estoque_insuficiente(ctx, result)

    return f"Ops! {result['message']}"


def _handle_estoque_insuficiente(ctx: HandlerContext, result: dict) -> str:
    """Handle insufficient stock sub-flow"""
    tem_urgencia = detectar_urgencia(ctx.message)
    tem_data_futura = detectar_data_futura(ctx.message)

    historico_recente = ctx.session_manager.get_conversation_history(ctx.phone, limit=3)
    perguntou_data = any(
        msg["role"] == "assistant"
        and "para que dia você precisa" in msg["content"].lower()
        for msg in historico_recente
    )

    if perguntou_data and tem_urgencia:
        return resp.resposta_encomenda_urgente(result["quantidade_disponivel"])
    elif perguntou_data and tem_data_futura:
        return resp.resposta_encomenda_futura()
    else:
        return resp.formatar_estoque_insuficiente(
            result["produto"]["nome"],
            result["quantidade_solicitada"],
            result["quantidade_disponivel"],
        )


def _extrair_multiplos_numeros(message: str) -> list:
    """
    Extract multiple item numbers from a message.
    Ex: "quero tirar o 1 e o 2" → [1, 2]
    Ex: "remove item 1, 2 e 3" → [1, 2, 3]
    Ex: "somente o 1 e o 2" → [1, 2]
    """
    msg = message.lower()
    numeros = []

    # Match all digits in context of item selection
    for match in re.finditer(r'\b(\d+)\b', msg):
        num = int(match.group(1))
        if 1 <= num <= 20:  # reasonable cart size
            numeros.append(num)

    # Also match written-out numbers
    escritos = {
        "primeiro": 1, "primeira": 1,
        "segundo": 2, "segunda": 2,
        "terceiro": 3, "terceira": 3,
        "quarto": 4, "quarta": 4,
        "quinto": 5, "quinta": 5,
    }
    for palavra, num in escritos.items():
        if palavra in msg and num not in numeros:
            numeros.append(num)

    return sorted(set(numeros))


def handle_remover_item(ctx: HandlerContext) -> str:
    """Handle removing item(s) from the cart.

    IMPORTANT: Numbers always reference CART positions, not search results.
    Supports removing multiple items at once ("remove 1 e 2").
    """
    sm = ctx.session_manager
    ic = ctx.intent_classifier
    th = ctx.tools_helper

    # Get current cart first
    carrinho = th.ver_carrinho(ctx.phone)
    if carrinho["status"] != "success" or carrinho.get("vazio"):
        return "Seu carrinho já está vazio."

    cart_items = carrinho["carrinho"]

    # a) Extract numbers — they reference CART positions
    numeros = _extrair_multiplos_numeros(ctx.message)

    if numeros:
        items_para_remover = []
        numeros_invalidos = []

        for num in numeros:
            if 1 <= num <= len(cart_items):
                items_para_remover.append(cart_items[num - 1])
            else:
                numeros_invalidos.append(num)

        if numeros_invalidos and not items_para_remover:
            items_str = "\n".join(
                f"{i+1}. {item['nome']}"
                for i, item in enumerate(cart_items)
            )
            return (
                f"Não encontrei esses itens no carrinho. "
                f"Aqui estão os itens:\n\n{items_str}"
            )

        # Remove each item
        nomes_removidos = []
        for item in items_para_remover:
            produto_id = str(item.get("produto_id", item.get("id", "")))
            produto_nome = item.get("nome", item.get("produto_nome", ""))
            result = th.remover_item(ctx.phone, produto_id)
            if result["status"] == "success":
                nomes_removidos.append(produto_nome)

        if nomes_removidos:
            carrinho_atualizado = th.ver_carrinho(ctx.phone)
            carrinho_vazio = carrinho_atualizado.get("vazio", True)

            if len(nomes_removidos) == 1:
                return resp.formatar_item_removido(nomes_removidos[0], carrinho_vazio)

            nomes_str = "\n".join(f"- {n}" for n in nomes_removidos)
            if carrinho_vazio:
                return (
                    f"Pronto, tirei esses itens do carrinho:\n{nomes_str}\n\n"
                    f"Seu carrinho ficou vazio. Quer procurar mais algum produto?"
                )
            return (
                f"Pronto, tirei esses itens do carrinho:\n{nomes_str}\n\n"
                f"Quer ver como ficou o carrinho ou precisa de mais alguma coisa?"
            )

        return "Ops, não consegui remover os itens. Tente novamente."

    # b) Search term in message (e.g., "tira o azeite alho")
    termo = ic.extract_search_term(ctx.message)
    if termo and termo.strip():
        items_match = [
            item for item in cart_items
            if termo.lower() in item["nome"].lower()
        ]
        if len(items_match) == 1:
            produto_id = str(items_match[0].get("produto_id", items_match[0].get("id", "")))
            produto_nome = items_match[0].get("nome", "")
            result = th.remover_item(ctx.phone, produto_id)
            if result["status"] == "success":
                carrinho_vazio = result.get("total_itens", 0) == 0
                return resp.formatar_item_removido(produto_nome, carrinho_vazio)
            return f"Ops! {result.get('message', 'Erro ao remover item')}"
        elif len(items_match) > 1:
            items_str = "\n".join(
                f"{i+1}. {item['nome']}"
                for i, item in enumerate(items_match)
            )
            return (
                f"Encontrei mais de um item com esse nome. "
                f"Qual você quer tirar?\n\n{items_str}"
            )

    # c) Single item in cart → auto-select
    if len(cart_items) == 1:
        produto_id = str(cart_items[0].get("produto_id", cart_items[0].get("id", "")))
        produto_nome = cart_items[0].get("nome", "")
        result = th.remover_item(ctx.phone, produto_id)
        if result["status"] == "success":
            return resp.formatar_item_removido(produto_nome, True)
        return f"Ops! {result.get('message', 'Erro ao remover item')}"

    # d) Can't determine — list cart items for customer to choose
    items_str = "\n".join(
        f"{i+1}. {item['nome']}"
        for i, item in enumerate(cart_items)
    )
    return f"Qual item você quer tirar do carrinho?\n\n{items_str}"


def handle_alterar_quantidade(ctx: HandlerContext) -> str:
    """Handle changing the quantity of an item in the cart"""
    sm = ctx.session_manager
    ic = ctx.intent_classifier
    th = ctx.tools_helper

    # Extract desired quantity
    nova_qtd = ic.extract_quantity(ctx.message)

    # Try to identify which product
    produto_alvo = None

    # a) Search term in message
    termo = ic.extract_search_term(ctx.message)
    if termo and termo.strip():
        carrinho = th.ver_carrinho(ctx.phone)
        if carrinho["status"] == "success" and not carrinho.get("vazio"):
            for item in carrinho["carrinho"]:
                if termo.lower() in item["nome"].lower():
                    produto_alvo = item
                    break

    # b) Single item in cart → auto-select
    if not produto_alvo:
        carrinho = th.ver_carrinho(ctx.phone)
        if carrinho["status"] == "success" and not carrinho.get("vazio"):
            if len(carrinho["carrinho"]) == 1:
                produto_alvo = carrinho["carrinho"][0]

    # c) Last product shown or in context
    if not produto_alvo:
        produtos_contexto = sm.get_last_products_shown(ctx.phone)
        if len(produtos_contexto) == 1:
            # Check if this product is in cart
            carrinho = th.ver_carrinho(ctx.phone)
            if carrinho["status"] == "success" and not carrinho.get("vazio"):
                for item in carrinho["carrinho"]:
                    if str(item.get("produto_id")) == str(produtos_contexto[0].get("id")):
                        produto_alvo = item
                        break

    if not produto_alvo:
        carrinho = th.ver_carrinho(ctx.phone)
        if carrinho["status"] == "success" and not carrinho.get("vazio"):
            items_str = "\n".join(
                f"{i+1}. {item['nome']} (Qtd: {item['quantidade']})"
                for i, item in enumerate(carrinho["carrinho"])
            )
            return f"Qual item você quer alterar a quantidade?\n\n{items_str}"
        return "Seu carrinho está vazio. Quer procurar algum produto?"

    produto_id = str(produto_alvo.get("produto_id", produto_alvo.get("id", "")))
    produto_nome = produto_alvo.get("nome", produto_alvo.get("produto_nome", ""))

    result = th.alterar_quantidade(ctx.phone, produto_id, nova_qtd)

    if result["status"] == "success":
        return resp.formatar_quantidade_alterada(produto_nome, nova_qtd)

    return f"Ops! {result.get('message', 'Erro ao alterar quantidade')}"


def handle_ver_carrinho(ctx: HandlerContext) -> str:
    """Handle view cart"""
    result = ctx.tools_helper.ver_carrinho(ctx.phone)
    if result["status"] == "success":
        return resp.formatar_carrinho_sem_emoji(result)
    return f"Ops! {result['message']}"


def handle_calcular_frete(ctx: HandlerContext) -> str:
    """Handle shipping calculation request"""
    return (
        "*Cálculo de Frete*\n\n"
        "Para calcular o frete, me informe seu CEP.\n\n"
        "Exemplo: 30120-010"
    )


def handle_finalizar_pedido(ctx: HandlerContext) -> str:
    """Handle order finalization"""
    result = ctx.tools_helper.finalizar_pedido(ctx.phone, metodo_pagamento="pix")
    if result["status"] == "success":
        return resp.formatar_pedido_finalizado_sem_emoji(result["pedido"])
    return f"Ops! {result['message']}"


def handle_consultar_pedido(ctx: HandlerContext) -> str:
    """Handle order status query"""
    result = ctx.tools_helper.consultar_pedidos(ctx.phone)
    if result["status"] == "success":
        return resp.formatar_pedidos_sem_emoji(result["pedidos"])
    return f"Ops! {result['message']}"


def handle_fallback(ctx: HandlerContext) -> str:
    """Handle unrecognized intents"""
    return (
        "Poxa, não entendi direito o que você precisa.\n\n"
        "Pode escrever de novo? Ou me diz o que você tá procurando que eu te ajudo."
    )


# ==================== Dispatcher Map ====================

INTENT_HANDLERS: Dict[str, Callable[[HandlerContext], str]] = {
    "atendimento_inicial": handle_atendimento_inicial,
    "informacao_loja": handle_informacao_loja,
    "informacao_entrega": handle_informacao_entrega,
    "retirada_loja": handle_retirada_loja,
    "rastreamento_pedido": handle_rastreamento_pedido,
    "informacao_pagamento": handle_informacao_pagamento,
    "armazenamento_queijo": handle_armazenamento_queijo,
    "embalagem_presente": handle_embalagem_presente,
    "busca_produto": handle_busca_produto,
    "adicionar_carrinho": handle_adicionar_carrinho,
    "remover_item": handle_remover_item,
    "alterar_quantidade": handle_alterar_quantidade,
    "ver_carrinho": handle_ver_carrinho,
    "calcular_frete": handle_calcular_frete,
    "finalizar_pedido": handle_finalizar_pedido,
    "consultar_pedido": handle_consultar_pedido,
}
