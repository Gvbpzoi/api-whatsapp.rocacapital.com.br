# Goal 6: Consulta de Pedido

## Objetivo

Permitir que cliente consulte status e rastreio de seus pedidos.

---

## Quando Executar

- Cliente pergunta: "cadê meu pedido?", "onde está?"
- Cliente quer rastrear: "rastreamento", "código de rastreio"
- Cliente menciona número do pedido

---

## Entradas

| Campo | Descrição |
|-------|-----------|
| `telefone` | Telefone do cliente |
| `pedido_numero` | Número do pedido (opcional) |
| `cpf_cnpj` | CPF/CNPJ (opcional) |

---

## Processo

### Passo 1: Buscar Pedidos

**Tool:** `tools/orders/search.py`

```python
# Buscar no Supabase (rápido!)
pedidos = search_orders(
    telefone=telefone,
    limit=5,
    order_by="criado_em DESC"
)

if not pedidos:
    # Fallback: buscar no Tiny
    pedidos = search_tiny_orders(telefone=telefone)
```

### Passo 2: Formatar Status

**Tool:** `tools/orders/format_status.py`

```python
for pedido in pedidos:
    status = get_friendly_status(pedido.status)

    # Status mapping:
    # - "pendente_pagamento" → "⏳ Aguardando pagamento"
    # - "pago" → "✅ Pago! Em preparação"
    # - "enviado" → "📦 A caminho!"
    # - "entregue" → "🎉 Entregue!"
    # - "cancelado" → "❌ Cancelado"
```

### Passo 3: Buscar Rastreio (se enviado)

**Tool:** `tools/orders/track.py`

```python
if pedido.status == "enviado" and pedido.codigo_rastreio:
    rastreio = get_tracking_info(pedido.codigo_rastreio)

    # Retorna:
    # {
    #   "status_atual": "Em trânsito",
    #   "localizacao": "Centro de Distribuição BH",
    #   "previsao_entrega": "2026-02-12",
    #   "historico": [...]
    # }
```

### Passo 4: Enviar Resposta

**Tool:** `tools/whatsapp/send_message.py`

```python
response = format_order_status(pedidos, rastreio)
send_message(telefone, response)
```

---

## Tools Necessários

- `tools/orders/search.py`
- `tools/orders/track.py`
- `tools/orders/format_status.py`
- `tools/whatsapp/send_message.py`

---

## Saídas

### Pedido Encontrado

```
📦 Seus Pedidos:

━━━━━━━━━━━━━━━━━
🆔 Pedido #1234
📅 Criado: 10/02/2026
💰 Total: R$ 123,00
📍 Status: 📦 A caminho!

🚚 Rastreio: BR123456789BR
📍 Localização atual: Centro de Distribuição BH
📅 Previsão de entrega: Amanhã (12/02)

🔗 Rastrear online:
https://rastreamento.correios.com.br/...

━━━━━━━━━━━━━━━━━

Mais alguma dúvida sobre seu pedido?
```

### Múltiplos Pedidos

```
📦 Encontrei 3 pedidos seus:

1️⃣ Pedido #1234 - 10/02/2026
   💰 R$ 123,00 | 📦 A caminho

2️⃣ Pedido #1198 - 05/02/2026
   💰 R$ 85,00 | ✅ Entregue

3️⃣ Pedido #1145 - 28/01/2026
   💰 R$ 67,00 | ✅ Entregue

Qual você quer acompanhar? Digite o número!
```

### Nenhum Pedido Encontrado

```
🔍 Não encontrei pedidos no seu telefone.

Você fez algum pedido com outro número ou CPF?

Se sim, me passe o CPF ou número do pedido que eu procuro!
```

---

## Tratamento de Erros

### Pedido Muito Antigo

```python
if pedido.criado_em < datetime.now() - timedelta(days=90):
    return "Este pedido é de mais de 90 dias atrás. Para informações detalhadas, entre em contato pelo (31) 3274-xxxx"
```

### Rastreio Indisponível

```python
if pedido.status == "enviado" and not pedido.codigo_rastreio:
    return f"Pedido #{pedido.numero} foi enviado mas o código de rastreio ainda não foi atualizado. Aguarde algumas horas!"
```

---

**Última atualização:** 11/02/2026
