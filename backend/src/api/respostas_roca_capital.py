"""
Respostas personalizadas da Roça Capital (sem emojis)
"""

SAUDACAO = """Olá! Bem-vindo à Roça Capital.

Estamos no Mercado Central de BH, bem na entrada da Augusto de Lima com Curitiba.

Temos queijos artesanais mineiros, produtos sem conservantes e muito carinho em cada pedido.

Como posso te ajudar hoje?"""


INFORMACAO_LOJA = """ROÇA CAPITAL - Mercado Central de BH

LOCALIZAÇÃO
Av. Augusto de Lima esquina com Curitiba
Bem na entrada do Mercado Central

HORÁRIO
Segunda a sexta: 8h às 18h
Feriados: 8h às 13h

CONTATOS
WhatsApp: (31) 9 9847-21890
E-mail: sac@rocacapital.com.br
Site: https://rocacapital.com.br"""


INFORMACAO_ENTREGA = """ENTREGA EM BH

Pedidos confirmados até 16h (segunda a sexta) saem no mesmo dia.

A entrega acontece entre 8h e 18h em rota otimizada. Não temos horário fixo, a não ser que você tenha solicitado entrega urgente.

Quando o pedido sair da loja, avisamos por WhatsApp e e-mail, combinado?

ENTREGA FORA DE BH

Entregamos sim, mas depende da região. Me envia seu CEP que verifico pra você.

Detalhe importante: Se o prazo ultrapassar 3 dias, não recomendamos enviar queijo, para garantir que ele chegue perfeito até você."""


RETIRADA_LOJA = """RETIRADA NA LOJA

Geralmente em 1 hora após a compra já está liberado.

A última separação do dia acontece às 17h.

ONDE ESTAMOS
Mercado Central de Belo Horizonte
Av. Augusto de Lima esquina com Curitiba - bem na entrada"""


RASTREAMENTO = """CÓDIGO DE RASTREIO

Assim que o pedido é postado, você recebe o código de rastreio por e-mail. É só acompanhar pelo link enviado.

Me informa por favor:
- Seu nome completo
- O número do pedido

Que eu verifico no sistema pra você rapidinho."""


INFORMACAO_PAGAMENTO = """FORMAS DE PAGAMENTO

DESCONTO NO PIX
5% de desconto no Pix para compras acima de R$ 499,90

VALE-ALIMENTAÇÃO
Ainda não aceitamos vale-alimentação, infelizmente.

CONFIRMAÇÃO DE PAGAMENTO
Se você não recebeu o e-mail de confirmação, me passa o número do pedido que eu verifico para você."""


ARMAZENAMENTO_QUEIJO = """COMO ARMAZENAR SEU QUEIJO

Você está levando um queijo artesanal, sem conservantes. Ele é um alimento vivo - e isso é o que faz ele ser especial.

O segredo é controlar temperatura e umidade.

QUEIJOS SEMI-DUROS E DUROS
- Vasilha plástica com tampa
- Papel-toalha no fundo para absorver excesso de umidade
- Guardar na geladeira
- Pode usar plástico filme se for consumir rápido, mas ele costuma ressecar mais
- NÃO congelar

QUEIJOS CREMOSOS E FRESCOS
- Guardar na geladeira (5º a 7º)
- Recipiente plástico com leve abertura para circular o ar
- Papel-toalha no fundo para absorver excesso de umidade
- NÃO congelar

QUEIJO MINAS ARTESANAL (ex: Canastra)
Se você mora em um lugar mais fresco, pode deixar fora da geladeira:
- Sobre tábua de madeira
- Coberto com queijeira
- Virar a cada 2 dias
- Controlar a umidade

Assim ele vai maturando, ganhando textura e sabor."""


EMBALAGEM_PRESENTE = """EMBALAGENS E PRESENTES

CAIXAS PERSONALIZADAS
Temos caixas personalizadas com a logo da loja.

Você também pode comprar embalagens aqui:
https://rocacapital.com.br/collections/embalagens-para-presente

CESTAS E KITS
Olha nossas opções aqui:
https://rocacapital.com.br/collections/kit"""


CATALOGO = """CATÁLOGO COMPLETO

Nosso catálogo completo está aqui:
https://rocacapital.com.br/collections

BOLOS, BROAS E MASSA DE PÃO DE QUEIJO
Fala direto com o Eder: (31) 9 9511-5678"""


def formatar_produto_sem_emoji(produtos: list) -> str:
    """Formata lista de produtos sem emojis"""
    if not produtos:
        return """Não encontrei nenhum produto com esse termo.

Tente buscar por: queijo, cachaça, doce, café...

Ou veja nosso catálogo completo: https://rocacapital.com.br/collections"""

    response = f"Encontrei {len(produtos)} produto{'s' if len(produtos) > 1 else ''}:\n\n"

    for i, p in enumerate(produtos, 1):
        response += f"{i}. *{p['nome']}*\n"
        response += f"   R$ {p['preco']:.2f}\n"
        response += f"   {int(p['estoque_atual'])} em estoque\n\n"

    response += "Qual te interessa? Digite o número ou nome."

    return response


def formatar_carrinho_sem_emoji(carrinho_data: dict) -> str:
    """Formata carrinho sem emojis"""
    if carrinho_data.get("vazio"):
        return """Seu carrinho está vazio.

Que tal buscar alguns produtos?
https://rocacapital.com.br/collections"""

    response = "*Seu Carrinho:*\n\n"

    for i, item in enumerate(carrinho_data["carrinho"], 1):
        produto = item["produto"]
        response += f"{i}. *{produto['nome']}*\n"
        response += f"   Qtd: {item['quantidade']} x R$ {produto['preco']:.2f}\n"
        response += f"   Subtotal: R$ {item['subtotal']:.2f}\n\n"

    response += f"*Total: R$ {carrinho_data['total']:.2f}*\n\n"
    response += "Quer finalizar o pedido?"

    return response


def formatar_pedido_finalizado_sem_emoji(pedido: dict) -> str:
    """Formata confirmação de pedido sem emojis"""
    return f"""*Pedido Finalizado!*

Número: {pedido['numero']}
Total: R$ {pedido['total']:.2f}
Pagamento: {pedido['metodo_pagamento'].upper()}

Em instantes você receberá o QR Code PIX para pagamento.

Obrigado pela preferência!"""


def formatar_pedidos_sem_emoji(pedidos: list) -> str:
    """Formata lista de pedidos sem emojis"""
    if not pedidos:
        return """Você ainda não tem pedidos.

Que tal fazer seu primeiro pedido?
https://rocacapital.com.br/collections"""

    response = "*Seus Pedidos:*\n\n"

    for pedido in pedidos:
        response += f"{pedido['numero']}\n"
        response += f"R$ {pedido['total']:.2f}\n"
        response += f"Status: {pedido['status']}\n"
        response += f"Data: {pedido['criado_em'][:10]}\n\n"

    response += "Alguma dúvida sobre seus pedidos?"

    return response
