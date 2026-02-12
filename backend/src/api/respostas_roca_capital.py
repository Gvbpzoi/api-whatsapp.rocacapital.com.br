"""
Respostas personalizadas da Roça Capital (sem emojis)
"""

from datetime import datetime


def gerar_saudacao_contextual(hora_atual: int = None, tem_pedido: bool = False) -> str:
    """
    Gera saudação contextual baseada no horário e se a pessoa já fez um pedido.

    Args:
        hora_atual: Hora do dia (0-23). Se None, usa hora atual.
        tem_pedido: Se True, a pessoa já disse o que quer. Se False, só mandou saudação.

    Returns:
        Saudação personalizada
    """
    if hora_atual is None:
        hora_atual = datetime.now().hour

    # Determinar saudação
    if 5 <= hora_atual < 12:
        saudacao = "Bom dia"
    elif 12 <= hora_atual < 18:
        saudacao = "Boa tarde"
    else:
        saudacao = "Boa noite"

    # Nome do atendente
    atendente = "Guilherme"

    # Se a pessoa já disse o que quer, não pergunta "como posso ajudar"
    if tem_pedido:
        return f"{saudacao}! Você tá falando hoje com o {atendente}."
    else:
        # Se só mandou "bom dia" ou similar, pergunta o que precisa
        return f"{saudacao}! Você tá falando hoje com o {atendente}. Como é que eu posso te ajudar?"


SAUDACAO = """Oi, tudo bem? Bem-vindo à Roça Capital!

A gente está aqui no Mercado Central de BH, bem na entrada da Av. Augusto de Lima com Curitiba.

Trabalhamos com queijos artesanais mineiros, produtos sem conservantes e muito carinho em cada pedido que sai daqui.

Me conta, como posso te ajudar hoje?"""


INFORMACAO_LOJA = """Olha, a gente está localizado no Mercado Central de BH, bem na entrada da Av. Augusto de Lima com Curitiba. É bem fácil de achar!

Nosso horário de funcionamento:
- Segunda a sexta: 8h às 18h
- Feriados: 8h às 13h

Se precisar falar com a gente:
WhatsApp: (31) 9 9847-21890
E-mail: sac@rocacapital.com.br
Site: https://rocacapital.com.br

Quer saber mais alguma coisa?"""


INFORMACAO_ENTREGA_BH = """A gente faz entrega aí na sua região sim!

Nossas entregas em BH funcionam assim:
Se a compra for feita até 16h (segunda a sexta), ela sai no mesmo dia. Pedidos depois desse horário, a gente entrega no dia seguinte.

A entrega acontece entre 8h e 18h em rota otimizada. A gente não tem horário fixo, a não ser que você tenha pedido entrega urgente, combinado?

Quando o pedido sair daqui da loja, a gente avisa você por WhatsApp e e-mail, tranquilo?"""

INFORMACAO_ENTREGA_FORA_BH = """A gente entrega sim pra fora de BH, mas depende da região.

Me passa seu CEP que eu verifico o prazo e o valor do frete pra você, beleza?

Só um detalhe importante: se o prazo de entrega ultrapassar 3 dias, a gente não recomenda enviar queijo não, sabe? É que nossos queijos são artesanais, sem conservantes, então a gente prefere garantir que ele chegue perfeito até você."""

INFORMACAO_ENTREGA_GERAL = """A gente faz entrega sim!

Você é de Belo Horizonte?"""


RETIRADA_LOJA = """Maravilha! Você pode retirar aqui na loja sim.

Geralmente em 1 hora depois da compra o pedido já está liberado pra você pegar. A última separação do dia a gente faz às 17h, beleza?

A gente está no Mercado Central de Belo Horizonte, na Av. Augusto de Lima esquina com Curitiba - bem na entrada mesmo, é fácil de achar!"""


RASTREAMENTO = """Ah sim! Olha, assim que a gente posta o pedido, você recebe o código de rastreio por e-mail. É só acompanhar pelo link que a gente envia.

Me dá só um minutinho? Me passa as seguintes informações que eu consulto aqui no sistema pra você:
- Seu nome completo
- O número do pedido

Já já eu te passo as informações, combinado?"""


INFORMACAO_PAGAMENTO = """Olha, sobre pagamento:

Se você pagar no Pix e a compra for acima de R$ 499,90, a gente dá 5% de desconto. Vale a pena, né?

Sobre vale-alimentação: infelizmente a gente ainda não aceita, mas estamos trabalhando nisso!

Ah, e se você não recebeu o e-mail de confirmação de pagamento, me passa o número do pedido que eu verifico aqui pra você, tranquilo?"""


ARMAZENAMENTO_QUEIJO = """Que bom que você perguntou! Olha, os nossos queijos são artesanais, sem conservantes. Ele é um alimento vivo - e isso é o que faz ele ser tão especial, sabe?

O segredo pra conservar bem é controlar a temperatura e a umidade. Deixa eu te explicar:

QUEIJOS SEMI-DUROS E DUROS:
A gente recomenda guardar numa vasilha plástica com tampa, com papel-toalha no fundo pra absorver o excesso de umidade. Guarda na geladeira, beleza?

Você pode usar plástico filme se for consumir rápido, mas ele costuma ressecar mais o queijo. Ah, e por favor, NÃO congela, combinado?

QUEIJOS CREMOSOS E FRESCOS:
Esses você guarda na geladeira (entre 5º e 7º), num recipiente plástico com uma leve abertura pra circular o ar. Papel-toalha no fundo também, pra absorver a umidade. E não congela também, viu?

QUEIJO MINAS ARTESANAL (tipo Canastra):
Agora, se você mora num lugar mais fresco, pode até deixar ele fora da geladeira:
- Deixa sobre uma tábua de madeira
- Cobre com uma queijeira
- Vira ele a cada 2 dias
- Controla bem a umidade

Assim ele vai maturando, ganhando textura e sabor. Fica uma delícia!

Qualquer dúvida, pode perguntar!"""


EMBALAGEM_PRESENTE = """Temos sim! A gente trabalha com caixas personalizadas com a logo da loja.

Vou te mandar um link aqui que tem todos os modelos que a gente trabalha:
https://rocacapital.com.br/collections/embalagens-para-presente

Se você quiser ver também nossas cestas e kits prontos, olha aqui:
https://rocacapital.com.br/collections/kit

Dá uma olhada e me fala qual te interessa!"""


CATALOGO = """Olha, nosso catálogo completo está aqui:
https://rocacapital.com.br/collections

Tem bastante coisa legal pra você ver!

Ah, e se você quiser saber sobre bolos, broas e massa de pão de queijo, é melhor falar direto com o Eder: (31) 9 9511-5678

Ele cuida dessa parte com muito carinho!"""


def formatar_produto_sem_emoji(produtos: list) -> str:
    """Formata lista de produtos sem emojis"""
    if not produtos:
        return """Puxa, não encontrei nenhum produto com esse termo não.

Tenta buscar por: queijo, cachaça, doce, café...

Ou então dá uma olhada no nosso catálogo completo: https://rocacapital.com.br/collections"""

    if len(produtos) == 1:
        response = "Olha, encontrei esse aqui:\n\n"
    else:
        response = f"Opa! Encontrei {len(produtos)} produtos:\n\n"

    for i, p in enumerate(produtos, 1):
        response += f"{i}. *{p['nome']}*\n"
        response += f"   R$ {p['preco']:.2f}\n"
        response += f"   {int(p['estoque_atual'])} em estoque\n\n"

    response += "Qual desses te interessa? Me fala o número ou o nome que eu te ajudo."

    return response


def formatar_carrinho_sem_emoji(carrinho_data: dict) -> str:
    """Formata carrinho sem emojis"""
    if carrinho_data.get("vazio"):
        return """Olha, seu carrinho está vazio ainda.

Que tal dar uma olhada nos nossos produtos?
https://rocacapital.com.br/collections"""

    response = "*Aqui está seu carrinho:*\n\n"

    for i, item in enumerate(carrinho_data["carrinho"], 1):
        produto = item["produto"]
        response += f"{i}. *{produto['nome']}*\n"
        response += f"   Qtd: {item['quantidade']} x R$ {produto['preco']:.2f}\n"
        response += f"   Subtotal: R$ {item['subtotal']:.2f}\n\n"

    response += f"*Total: R$ {carrinho_data['total']:.2f}*\n\n"
    response += "E aí, quer finalizar o pedido?"

    return response


def formatar_pedido_finalizado_sem_emoji(pedido: dict) -> str:
    """Formata confirmação de pedido sem emojis"""
    return f"""*Maravilha! Seu pedido foi finalizado!*

Número do pedido: {pedido['numero']}
Total: R$ {pedido['total']:.2f}
Forma de pagamento: {pedido['metodo_pagamento'].upper()}

Em instantes você vai receber o QR Code PIX para fazer o pagamento, combinado?

Muito obrigado pela preferência! A gente se vê em breve."""


def formatar_pedidos_sem_emoji(pedidos: list) -> str:
    """Formata lista de pedidos sem emojis"""
    if not pedidos:
        return """Olha, você ainda não tem nenhum pedido com a gente.

Que tal fazer seu primeiro pedido? Vai ser um prazer te atender!
https://rocacapital.com.br/collections"""

    response = "*Aqui estão seus pedidos:*\n\n"

    for pedido in pedidos:
        response += f"Pedido: {pedido['numero']}\n"
        response += f"Valor: R$ {pedido['total']:.2f}\n"
        response += f"Status: {pedido['status']}\n"
        response += f"Data: {pedido['criado_em'][:10]}\n\n"

    response += "Tem alguma dúvida sobre algum desses pedidos? Pode perguntar!"

    return response
