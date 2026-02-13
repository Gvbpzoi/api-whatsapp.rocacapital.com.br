"""
Endpoint específico para webhooks da ZAPI
Processa mensagens e responde automaticamente
"""

from fastapi import APIRouter, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger
import re
import asyncio

from ..services.zapi_client import get_zapi_client
from ..services.session_manager import SessionManager
from ..orchestrator.gotcha_engine import GOTCHAEngine
from ..orchestrator.intent_classifier import IntentClassifier
from ..orchestrator.tools_helper import ToolsHelper
from ..orchestrator.response_evaluator import ResponseEvaluator
from . import respostas_roca_capital as resp


router = APIRouter()

# Singletons (serão injetados pelo main.py)
session_manager: Optional[SessionManager] = None
gotcha_engine: Optional[GOTCHAEngine] = None
intent_classifier: Optional[IntentClassifier] = None
tools_helper: Optional[ToolsHelper] = None
response_evaluator: Optional[ResponseEvaluator] = None

# Bug #5: Lock por telefone para evitar race condition no buffer
_phone_locks: Dict[str, asyncio.Lock] = {}


class ZAPIWebhookMessage(BaseModel):
    """
    Formato de webhook da ZAPI
    Documentação: https://developer.z-api.io/webhooks/on-message-received
    """
    phone: str
    text: Optional[Dict[str, str]] = None
    image: Optional[Dict[str, Any]] = None
    isGroup: bool = False
    instanceId: Optional[str] = None
    messageId: Optional[str] = None
    fromMe: bool = False
    momment: Optional[int] = None
    status: Optional[str] = None
    senderName: Optional[str] = None
    photo: Optional[str] = None
    broadcast: Optional[bool] = None
    participantPhone: Optional[str] = None


async def process_and_respond(phone: str, message: str, timestamp: int = None):
    """
    Processa mensagem com o agente e envia resposta via ZAPI.
    Roda em background para não bloquear webhook.
    
    Implementa buffer de mensagens: aguarda 3 segundos para mensagens consecutivas.
    
    Bug #5 corrigido: Usa Lock por telefone para evitar race condition.
    """
    # Obter ou criar lock para este telefone
    if phone not in _phone_locks:
        _phone_locks[phone] = asyncio.Lock()
    
    lock = _phone_locks[phone]
    
    # Apenas uma coroutine por telefone processa por vez
    async with lock:
        try:
            logger.info(f"📨 Processando mensagem de {phone[:8]}...")

            # Adicionar ao buffer
            buffer_result = session_manager.add_to_buffer(phone, message)
            
            # Se deve aguardar mais mensagens, sair (timer vai processar depois)
            if buffer_result["should_wait"]:
                logger.info(f"⏳ Aguardando mais mensagens no buffer ({buffer_result['count']}/3)")
                # Agendar processamento após 3 segundos
                await asyncio.sleep(3.0)
                
                # RE-FETCH buffer após sleep (Bug #5)
                current_buffer = session_manager._message_buffer.get(phone, {})
                messages = current_buffer.get("messages", [])
                
                # Se buffer foi limpo por outra task, skip
                if not messages:
                    logger.info("✅ Buffer já foi processado por outra task")
                    return
                
                # Se chegaram mais mensagens, deixar próximo ciclo processar
                if len(messages) > buffer_result["count"]:
                    logger.info("📬 Novas mensagens chegaram, deixando próximo ciclo processar")
                    return
                
                # Combinar mensagens do buffer atual (extrair texto de cada dict)
                combined_message = " ".join([msg["text"] for msg in messages])
                message_count = len(messages)
            else:
                # Processar imediatamente
                combined_message = buffer_result["combined"]
                message_count = buffer_result["count"]
            
            logger.info(f"📝 Processando {message_count} mensagem(ns): {combined_message[:50]}...")
            
            # Adicionar mensagem combinada ao histórico
            session_manager.add_to_history(phone, "user", combined_message)
            
            # Limpar buffer
            session_manager.clear_buffer(phone)

            # Verificar se agente deve responder
            session = session_manager.get_session(phone)

            if session.mode != "agent":
                logger.info(f"⏸️  Agente pausado para {phone[:8]}, modo: {session.mode}")
                return

            # Processar com agente
            response_text = await _process_with_agent(phone, combined_message, timestamp)

            if not response_text:
                logger.warning(f"⚠️ Nenhuma resposta gerada para {phone[:8]}")
                return

            # Enviar resposta via ZAPI
            zapi = get_zapi_client()
            result = zapi.send_text(phone, response_text)

            if result["success"]:
                # Adicionar resposta do bot ao histórico
                session_manager.add_to_history(phone, "assistant", response_text)
                logger.info(f"✅ Resposta enviada para {phone[:8]}")
            else:
                logger.error(f"❌ Falha ao enviar resposta: {result.get('error')}")

        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem: {e}")


def _detectar_saudacao_inicial(message: str) -> bool:
    """
    Detecta se a mensagem começa com uma saudação.
    """
    mensagem_lower = message.lower().strip()
    saudacoes = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "hey", "alo", "alô", "opa"]

    # Verifica se começa com alguma saudação
    for saudacao in saudacoes:
        if mensagem_lower.startswith(saudacao):
            return True
    return False


def _eh_apenas_saudacao(message: str) -> bool:
    """
    Verifica se a mensagem é APENAS uma saudação, sem conteúdo adicional.
    """
    mensagem_lower = message.lower().strip()
    # Remove pontuação
    mensagem_limpa = mensagem_lower.replace("!", "").replace("?", "").replace(".", "").replace(",", "")

    saudacoes_completas = [
        "oi", "olá", "ola", "bom dia", "boa tarde", "boa noite",
        "hey", "alo", "alô", "opa", "e ai", "e aí", "eai",
        "oi tudo bem", "ola tudo bem", "olá tudo bem"
    ]

    return mensagem_limpa in saudacoes_completas


def _detectar_localizacao(message: str) -> str:
    """
    Detecta se a mensagem contém informação de localização.

    Returns:
        "bh" - Cliente está em Belo Horizonte ou região metropolitana
        "fora_bh" - Cliente está fora de BH
        "desconhecido" - Não mencionou localização
    """
    mensagem_lower = message.lower()

    # Bairros de BH
    bairros_bh = [
        "pampulha", "savassi", "lourdes", "funcionários", "funcionarios",
        "centro", "barro preto", "santo agostinho", "santa efigênia", "santa efigenia",
        "carlos prates", "lagoinha", "floresta", "santa tereza", "santa teresa",
        "mangabeiras", "belvedere", "buritis", "gutierrez", "são bento", "sao bento",
        "cidade nova", "padre eustáquio", "padre eustaquio", "itapoã", "itapoa",
        "castelo", "prado", "calafate", "caiçara", "caiçaras", "caicara", "caicaras",
        "são pedro", "sao pedro", "barreiro", "venda nova", "eldorado", "sion"
    ]

    # Cidades da região metropolitana de BH
    regiao_metropolitana = [
        "nova lima", "sabará", "sabara", "contagem", "betim", "ribeirão das neves",
        "ribeirao das neves", "santa luzia", "lagoa santa", "vespasiano",
        "pedro leopoldo", "raposos", "rio acima", "brumadinho", "ibirité", "ibirite",
        "mateus leme", "juatuba", "esmeraldas", "confins", "florestal"
    ]

    # Verifica bairros de BH
    for bairro in bairros_bh:
        if bairro in mensagem_lower:
            return "bh"

    # Verifica região metropolitana
    for cidade in regiao_metropolitana:
        if cidade in mensagem_lower:
            return "bh"

    # Verifica se menciona BH explicitamente
    if any(termo in mensagem_lower for termo in ["belo horizonte", "bh", "belô", "belo hte"]):
        return "bh"

    # Verifica se menciona CEP ou cidade de fora
    if any(termo in mensagem_lower for termo in ["cep", "são paulo", "rio de janeiro", "minas gerais", "mg", "sp", "rj"]):
        return "fora_bh"

    # Verifica padrão de CEP (nnnnn-nnn ou nnnnnnnnn)
    import re
    if re.search(r'\d{5}-?\d{3}', mensagem_lower):
        return "fora_bh"

    return "desconhecido"


def _detectar_pergunta_nome(message: str) -> bool:
    """
    Detecta se o cliente está perguntando o nome do atendente.
    """
    mensagem_lower = message.lower()
    padroes_nome = [
        r"com quem (eu )?falo",
        r"com quem (eu )?to falando",
        r"com quem (eu )?estou falando",
        r"qual (o |é o )?seu nome",
        r"quem (é|e) (você|voce|vc)",
        r"você (é|e) quem",
        r"seu nome",
        r"como.*você.*chama",  # Mais flexível: pega "como é que você chama"
        r"como.*voce.*chama",
        r"como.*vc.*chama",
    ]

    for padrao in padroes_nome:
        if re.search(padrao, mensagem_lower):
            return True
    return False


def _extrair_nome_cliente(message: str, historico: list) -> Optional[str]:
    """
    Detecta se a mensagem é uma resposta com o nome do cliente.
    Verifica se última mensagem do bot perguntou o nome.

    Returns:
        Nome do cliente ou None
    """
    # Verificar se última mensagem do bot perguntou o nome
    if not historico or len(historico) < 1:
        return None

    ultima_msg_bot = None
    for msg in reversed(historico):
        if msg["role"] == "assistant":
            ultima_msg_bot = msg["content"].lower()
            break

    if not ultima_msg_bot or "qual é o seu nome" not in ultima_msg_bot:
        return None

    # Se chegou aqui, bot perguntou o nome na última mensagem
    # Extrair nome da resposta do cliente
    mensagem = message.strip()

    # Padrões comuns de resposta
    # "Meu nome é João", "É João", "João", "Sou o João", etc
    padroes = [
        r"(?:meu nome (?:é|e)|me chamo|sou(?: o| a)?) ([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ][a-záàâãéèêíïóôõöúçñ]+)",
        r"^(?:é|e) ([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ][a-záàâãéèêíïóôõöúçñ]+)",
        r"^([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ][a-záàâãéèêíïóôõöúçñ]+)$",  # Nome sozinho
    ]

    for padrao in padroes:
        match = re.search(padrao, mensagem, re.IGNORECASE)
        if match:
            nome = match.group(1).capitalize()
            logger.info(f"📝 Nome do cliente extraído: {nome}")
            return nome

    return None


def _detectar_pergunta_generica_produtos(message: str) -> bool:
    """
    Detecta se o cliente está perguntando de forma genérica sobre produtos
    (sem especificar um produto), ex: "quais queijos você tem?", "o que você tem?", "pode mostrar os que você tem?"
    """
    mensagem_lower = message.lower()
    padroes_genericos = [
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
        # NOVOS padrões (do plano)
        r"(pode\s+)?(mostrar|mostra|listar)\s+(os\s+)?que",
        r"os\s+que\s+(você|voce|vc)\s+(tem|têm)",
        r"\btem\s+mais\b",
        r"\boutros?\b",
        r"\boutras?\s+op[cç][oõ]es\b",
    ]

    for padrao in padroes_genericos:
        if re.search(padrao, mensagem_lower):
            return True
    return False


def _detectar_referencia_a_escolha(message: str) -> bool:
    """
    Detecta se mensagem referencia produto escolhido antes.
    Ex: "mais um azeite", "outro queijo", "aquele azeite", "mesmo queijo"
    """
    mensagem_lower = message.lower()
    patterns = [
        r"\bmais\s+(um|uma|dois|duas|\d+)\s+\w+",  # "mais um azeite"
        r"\boutr[oa]\s+\w+",  # "outro queijo"
        r"\baquele\s+\w+",  # "aquele azeite"
        r"\bmesm[oa]\s+\w+",  # "mesmo queijo"
    ]
    return any(re.search(p, mensagem_lower) for p in patterns)


def _detectar_despedida(message: str) -> bool:
    """
    Detecta se o cliente está se despedindo ou encerrando conversa.
    """
    mensagem_lower = message.lower()
    padroes_despedida = [
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

    for padrao in padroes_despedida:
        if re.search(padrao, mensagem_lower):
            return True
    return False


def _detectar_urgencia(message: str) -> bool:
    """
    Detecta se o cliente precisa com urgência (hoje, agora, urgente).
    """
    mensagem_lower = message.lower()
    padroes_urgencia = [
        r"\bhoje\b",
        r"\bagora\b",
        r"\bjá\b",
        r"\bja\b",
        r"\burgente\b",
        r"\burgência\b",
        r"\bpra\s+hoje\b",
        r"\bpara\s+hoje\b",
        r"\brápido\b",
        r"\brapido\b",
        r"\blogo\b",
        r"\bjá\s+já\b",
    ]

    for padrao in padroes_urgencia:
        if re.search(padrao, mensagem_lower):
            return True
    return False


def _detectar_data_futura(message: str) -> bool:
    """
    Detecta se o cliente mencionou uma data futura.
    """
    mensagem_lower = message.lower()
    padroes_data_futura = [
        r"\bamanhã\b",
        r"\bamanha\b",
        r"\bsemana\s+que\s+vem\b",
        r"\bpróxima\s+semana\b",
        r"\bproxima\s+semana\b",
        r"\bmês\s+que\s+vem\b",
        r"\bmes\s+que\s+vem\b",
        r"\bdaqui\s+\d+\s+dia",
        r"\bsegunda\b",
        r"\bterça\b",
        r"\bquarta\b",
        r"\bquinta\b",
        r"\bsexta\b",
        r"\bsábado\b",
        r"\bsabado\b",
        r"\bdomingo\b",
        r"\bdentro\s+de\s+\d+\s+dia",
        r"\d{1,2}/\d{1,2}",  # Formato de data: 15/03
    ]

    for padrao in padroes_data_futura:
        if re.search(padrao, mensagem_lower):
            return True
    return False


async def _process_with_agent(phone: str, message: str, timestamp: int = None) -> str:
    """
    Processa mensagem com o agente (GOTCHA Engine).

    Returns:
        Texto da resposta
    """
    try:
        # Calcular hora da mensagem
        if timestamp:
            # Timestamp da ZAPI está em milissegundos
            hora_mensagem = datetime.fromtimestamp(timestamp / 1000).hour
        else:
            hora_mensagem = datetime.now().hour

        # Verificar se é nova conversa ou continuação
        is_nova_conversa = session_manager.is_new_conversation(phone)
        logger.info(f"{'🆕 Nova conversa' if is_nova_conversa else '💬 Conversa contínua'} com {phone[:8]}")

        # Reset conversation stage tracking on new conversations
        if is_nova_conversa and response_evaluator:
            response_evaluator.reset_stage(phone)

        # Recuperar nome do cliente da memória (se existe)
        nome_cliente_salvo = None
        preferencias = session_manager.get_customer_preferences(phone, limit=5)
        for pref in preferencias:
            if pref.get("content", "").startswith("Nome: "):
                nome_cliente_salvo = pref["content"].replace("Nome: ", "")
                logger.info(f"👤 Nome recuperado da memória: {nome_cliente_salvo}")
                break

        # VERIFICAÇÕES ESPECIAIS (antes da classificação de intent)
        # Essas têm prioridade sobre a classificação genérica

        # 1. Verificar se cliente está respondendo com seu nome
        historico = session_manager.get_conversation_history(phone, limit=5)
        nome_cliente = _extrair_nome_cliente(message, historico)
        if nome_cliente:
            # Salvar nome na memória persistente
            session_manager.save_customer_preference(
                phone=phone,
                preference=f"Nome: {nome_cliente}",
                category="identidade"
            )
            logger.info(f"💾 Nome salvo: {nome_cliente}")
            return f"Prazer, {nome_cliente}! Fico à disposição sempre que precisar."

        # 2. Detectar outros contextos especiais
        pergunta_nome = _detectar_pergunta_nome(message)
        despedida = _detectar_despedida(message)

        # Se tem AMBOS (despedida + pergunta nome), responde combinado
        if pergunta_nome and despedida:
            logger.info("👋🏷️ Detectada despedida + pergunta sobre nome")
            return resp.RESPOSTA_NOME_E_DESPEDIDA

        # Se só pergunta nome
        if pergunta_nome:
            logger.info("🏷️ Detectada pergunta sobre nome do atendente")
            return resp.RESPOSTA_NOME_ATENDENTE

        # Se só despedida
        if despedida:
            logger.info("👋 Detectada despedida")
            return resp.RESPOSTA_DESPEDIDA

        # PRÉ-CHECAGEM: Detectar pergunta genérica sobre produtos (antes da classificação)
        if _detectar_pergunta_generica_produtos(message):
            logger.info("🔍 Pré-checagem: pergunta genérica sobre produtos → busca_produto")
            intent = "busca_produto"
        else:
            # Classificar intent COM CONTEXTO
            context = session_manager.get_context_for_classification(phone)
            intent = intent_classifier.classify(message, context)
            logger.info(f"🎯 Intent classificado: {intent}")

        # Detectar se começa com saudação
        comeca_com_saudacao = _detectar_saudacao_inicial(message)
        eh_so_saudacao = _eh_apenas_saudacao(message)

        # Processar baseado no intent
        if intent == "atendimento_inicial":
            # Em conversa contínua, NUNCA dá saudação completa
            if not is_nova_conversa:
                response = "Oi! Em que posso te ajudar?"
            else:
                # Nova conversa: saudação completa
                response = resp.gerar_saudacao_contextual(hora_mensagem, tem_pedido=False, nome_cliente=nome_cliente_salvo)

        elif intent == "informacao_loja":
            if comeca_com_saudacao and not eh_so_saudacao:
                response = resp.gerar_saudacao_contextual(hora_mensagem, tem_pedido=True, nome_cliente=nome_cliente_salvo) + "\n\n"
            else:
                response = ""
            response += resp.INFORMACAO_LOJA

        elif intent == "informacao_entrega":
            # Detectar localização na mensagem
            localizacao = _detectar_localizacao(message)
            logger.info(f"📍 Localização detectada: {localizacao}")

            # Adiciona saudação apenas em nova conversa
            if is_nova_conversa:
                response = resp.gerar_saudacao_contextual(hora_mensagem, tem_pedido=True, nome_cliente=nome_cliente_salvo) + "\n\n"
            else:
                response = ""

            # Escolhe resposta baseada na localização
            if localizacao == "bh":
                response += resp.INFORMACAO_ENTREGA_BH
            elif localizacao == "fora_bh":
                response += resp.INFORMACAO_ENTREGA_FORA_BH
            else:
                # Não mencionou localização: pergunta
                response += resp.INFORMACAO_ENTREGA_GERAL

        elif intent == "retirada_loja":
            if comeca_com_saudacao and not eh_so_saudacao:
                response = resp.gerar_saudacao_contextual(hora_mensagem, tem_pedido=True, nome_cliente=nome_cliente_salvo) + "\n\n"
            else:
                response = ""
            response += resp.RETIRADA_LOJA

        elif intent == "rastreamento_pedido":
            if comeca_com_saudacao and not eh_so_saudacao:
                response = resp.gerar_saudacao_contextual(hora_mensagem, tem_pedido=True, nome_cliente=nome_cliente_salvo) + "\n\n"
            else:
                response = ""
            response += resp.RASTREAMENTO

        elif intent == "informacao_pagamento":
            if comeca_com_saudacao and not eh_so_saudacao:
                response = resp.gerar_saudacao_contextual(hora_mensagem, tem_pedido=True, nome_cliente=nome_cliente_salvo) + "\n\n"
            else:
                response = ""
            response += resp.INFORMACAO_PAGAMENTO

        elif intent == "armazenamento_queijo":
            # Já tem "Que bom que você perguntou!" na resposta, não adiciona saudação
            response = resp.ARMAZENAMENTO_QUEIJO

        elif intent == "embalagem_presente":
            # Já tem "Temos sim!" na resposta, não adiciona saudação
            response = resp.EMBALAGEM_PRESENTE

        elif intent == "busca_produto":
            # Verificar se é pergunta genérica sobre produtos (sem termo específico)
            if _detectar_pergunta_generica_produtos(message):
                logger.info("📦 Detectada pergunta genérica sobre produtos")
                response = resp.RESPOSTA_PRODUTOS_DISPONIVEIS
            else:
                # Enriquecer termo com contexto se necessário
                termo = intent_classifier.extract_search_term(message)
                
                # Se não extraiu termo mas tem contexto, usar o contexto
                if not termo or len(termo.strip()) == 0:
                    context = session_manager.get_conversation_subject(phone)
                    if context and context.get("termo"):
                        termo = context["termo"]
                        logger.info(f"🔄 Usando termo do contexto: {termo}")
                
                logger.info(f"🔍 Termo de busca: {termo}")

                result = tools_helper.buscar_produtos(termo or message, limite=5)

                if result["status"] == "success":
                    # Salvar produtos mostrados no contexto (legado)
                    session_manager.set_last_products_shown(phone, result["produtos"])
                    
                    # NOVO: Salvar assunto da conversa (contexto conversacional)
                    session_manager.set_conversation_subject(
                        phone=phone,
                        termo=termo or message,
                        produtos_ids=[p["id"] for p in result["produtos"]],
                        produtos=result["produtos"]
                    )
                    
                    # Se for nova conversa, saudação completa + introdução
                    if is_nova_conversa:
                        response = "Oiê, tudo bem? Meu nome é Guilherme. Peraí, que eu vou te mandar os produtos que eu tenho disponíveis aqui hoje.\n\n"
                    # Se conversa contínua mas começou com saudação, responde direto
                    elif comeca_com_saudacao and not eh_so_saudacao:
                        response = "Opa! "
                    else:
                        response = ""
                    
                    response += resp.formatar_produto_sem_emoji(result["produtos"])
                else:
                    response = "Ops, tive um problema ao buscar produtos. Tente novamente."

        elif intent == "adicionar_carrinho":
            qtd = intent_classifier.extract_quantity(message)
            
            # NOVO FLUXO: Resolver produto com memória de escolhas
            produto_escolhido = None
            usar_confirmacao_proativa = False
            
            # a) Verificar se cliente mencionou um número (1-5) usando o novo método
            numero_produto = intent_classifier.extract_product_number(message)
            if numero_produto:
                produto_escolhido = session_manager.get_product_by_number(phone, numero_produto)
                if produto_escolhido:
                    logger.info(f"✅ Cliente escolheu produto #{numero_produto}: {produto_escolhido.get('nome')}")
            
            # b) Termo específico na mensagem (ex: "dois azeites", "3 queijos canastra")
            # MAS ANTES: verificar se é referência a escolha anterior
            if not produto_escolhido:
                termo = intent_classifier.extract_search_term(message)
                if termo and len(termo.split()) >= 1:  # tem palavra significativa
                    # Verificar se é referência a escolha anterior (ex: "mais um azeite")
                    if _detectar_referencia_a_escolha(message):
                        logger.info(f"🔄 Detectada referência a escolha anterior: '{termo}'")
                        last_choice = session_manager.get_last_choice_by_term(phone, termo)
                        if last_choice:
                            produto_escolhido = last_choice["produto"]
                            usar_confirmacao_proativa = True
                            logger.info(f"💾 Usando produto do histórico: {produto_escolhido.get('nome')}")
                    
                    # Se não achou no histórico, buscar novo produto
                    if not produto_escolhido:
                        result_busca = tools_helper.buscar_produtos(termo, limite=1)
                        if result_busca["produtos"]:
                            produto_escolhido = result_busca["produtos"][0]
                            logger.info(f"✅ Produto encontrado por busca: {produto_escolhido.get('nome')}")
            
            # c) (removido - agora está incluído em b)
            
            # d) Se ainda não tem produto, verificar se há apenas 1 produto no contexto
            if not produto_escolhido:
                produtos_contexto = session_manager.get_last_products_shown(phone)
                if len(produtos_contexto) == 1:
                    produto_escolhido = produtos_contexto[0]
                    logger.info(f"✅ Usando único produto do contexto: {produto_escolhido.get('nome')}")
            
            # Se ainda não tem produto, pedir esclarecimento em vez de adivinhar
            if not produto_escolhido:
                produtos_contexto = session_manager.get_last_products_shown(phone)
                if produtos_contexto:
                    response = "Qual desses produtos você quer adicionar? Me fala o número ou o nome."
                else:
                    response = "Qual produto você quer adicionar ao carrinho? Me fala o nome que eu busco pra você."
                return response

            produto_id = produto_escolhido.get("id")

            # ADICIONAR AO CARRINHO
            result = tools_helper.adicionar_carrinho(phone, str(produto_id), qtd)

            if result["status"] == "success":
                # NOVO: Salvar escolha no histórico
                if produto_escolhido:
                    session_manager.save_product_choice(phone, produto_escolhido, qtd)
                
                # Resposta com confirmação proativa se usou histórico
                if usar_confirmacao_proativa and produto_escolhido:
                    response = f"Adicionei {qtd}x {produto_escolhido['nome']}, aquele que você escolheu antes.\n\n"
                else:
                    response = f"Adicionei {qtd} item(s) ao carrinho!\n\n"
                
                # Corrigir total (agora mostra quantidade total, não número de linhas)
                quantidade_total = result.get('quantidade_total', sum(item['quantidade'] for item in result.get('carrinho', [])))
                response += f"Total: {quantidade_total} produto(s)\n\n"
                response += "Quer adicionar mais algo ou ver o carrinho?"
            elif result["status"] == "estoque_insuficiente":
                # Verificar se cliente mencionou urgência ou data
                tem_urgencia = _detectar_urgencia(message)
                tem_data_futura = _detectar_data_futura(message)
                
                # Verificar histórico recente para contexto da conversa
                historico_recente = session_manager.get_conversation_history(phone, limit=3)
                perguntou_data = False
                for msg in historico_recente:
                    if msg["role"] == "assistant" and "para que dia você precisa" in msg["content"].lower():
                        perguntou_data = True
                        break
                
                # Fluxo conversacional
                if perguntou_data and tem_urgencia:
                    # Cliente respondeu que precisa com urgência
                    response = resp.resposta_encomenda_urgente(result["quantidade_disponivel"])
                elif perguntou_data and tem_data_futura:
                    # Cliente respondeu com data futura
                    response = resp.resposta_encomenda_futura()
                else:
                    # Primeira vez: perguntar para quando precisa
                    response = resp.formatar_estoque_insuficiente(
                        result["produto"]["nome"],
                        result["quantidade_solicitada"],
                        result["quantidade_disponivel"]
                    )
            else:
                response = f"Ops! {result['message']}"

        elif intent == "ver_carrinho":
            result = tools_helper.ver_carrinho(phone)

            if result["status"] == "success":
                response = resp.formatar_carrinho_sem_emoji(result)
            else:
                response = f"Ops! {result['message']}"

        elif intent == "calcular_frete":
            response = "*Cálculo de Frete*\n\n"
            response += "Para calcular o frete, me informe seu CEP.\n\n"
            response += "Exemplo: 30120-010"

        elif intent == "finalizar_pedido":
            result = tools_helper.finalizar_pedido(phone, metodo_pagamento="pix")

            if result["status"] == "success":
                response = resp.formatar_pedido_finalizado_sem_emoji(result["pedido"])
            else:
                response = f"Ops! {result['message']}"

        elif intent == "consultar_pedido":
            result = tools_helper.consultar_pedidos(phone)

            if result["status"] == "success":
                response = resp.formatar_pedidos_sem_emoji(result["pedidos"])
            else:
                response = f"Ops! {result['message']}"

        else:
            response = """Poxa, não entendi direito o que você precisa.

Pode escrever de novo? Ou me diz o que você tá procurando que eu te ajudo."""

        # === EVALUATE RESPONSE BEFORE SENDING ===
        if response_evaluator:
            historico = session_manager.get_conversation_history(phone, limit=5)
            produtos_contexto = session_manager.get_last_products_shown(phone) or None

            evaluation = response_evaluator.evaluate(
                phone=phone,
                message=message,
                intent=intent,
                response=response,
                conversation_history=historico,
                is_new_conversation=is_nova_conversa,
                products_in_context=produtos_contexto,
            )

            if not evaluation.passed and evaluation.adjusted_response:
                logger.warning(
                    f"Response adjusted by evaluator: "
                    f"issues={evaluation.issues} score={evaluation.score:.2f}"
                )
                response = evaluation.adjusted_response
            elif evaluation.adjusted_response:
                # Passed but has a minor adjustment (e.g. stripped greeting)
                response = evaluation.adjusted_response

        return response

    except Exception as e:
        logger.error(f"❌ Erro ao processar com agente: {e}")
        return "Desculpe, tive um problema ao processar sua mensagem. Tente novamente!"


@router.post("/webhook/zapi")
async def zapi_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Webhook para receber mensagens da ZAPI.

    A ZAPI envia POST com JSON contendo a mensagem.
    Este endpoint processa e responde automaticamente.

    Documentação: https://developer.z-api.io/webhooks/on-message-received
    """
    try:
        data = await request.json()
        logger.info(f"📥 Webhook ZAPI recebido: {data}")

        # Extrair dados da mensagem
        phone = data.get("phone", "")
        from_me = data.get("fromMe", False)
        is_group = data.get("isGroup", False)

        # Ignorar mensagens de grupo e mensagens enviadas por nós
        if is_group:
            logger.info("⏭️ Ignorando mensagem de grupo")
            return {"success": True, "message": "Mensagem de grupo ignorada"}

        if from_me:
            logger.info("⏭️ Ignorando mensagem enviada por mim")
            return {"success": True, "message": "Mensagem própria ignorada"}

        # Extrair texto da mensagem
        text_data = data.get("text", {})
        message = text_data.get("message", "") if text_data else ""

        if not message:
            logger.warning("⚠️ Mensagem vazia recebida")
            return {"success": True, "message": "Mensagem vazia ignorada"}

        if not phone:
            logger.warning("⚠️ Telefone não identificado")
            return {"success": False, "error": "Telefone não identificado"}

        # Extrair timestamp da mensagem
        timestamp = data.get("momment", None)

        # Processar e responder em background
        background_tasks.add_task(process_and_respond, phone, message, timestamp)

        return {
            "success": True,
            "message": "Mensagem recebida e sendo processada"
        }

    except Exception as e:
        logger.error(f"❌ Erro no webhook ZAPI: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/webhook/zapi")
async def zapi_webhook_get():
    """
    Endpoint GET para verificar se webhook está ativo.
    Útil para testar configuração.
    """
    return {
        "status": "online",
        "webhook": "zapi",
        "message": "Webhook ZAPI está ativo e pronto para receber mensagens"
    }
