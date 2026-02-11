# Goal 5: Finalização de Pedido

## Objetivo

Criar pedido oficial no Tiny ERP, gerar pagamento (PIX/Cartão) e confirmar com cliente.

---

## Quando Executar

- Cliente confirma: "quero finalizar", "fechar pedido"
- Carrinho preenchido + frete calculado
- Cliente pronto para pagar

---

## Entradas

| Campo | Descrição |
|-------|-----------|
| `telefone` | Telefone do cliente |
| `metodo_pagamento` | pix, cartao, dinheiro |
| `cpf_cnpj` | CPF/CNPJ para NF (opcional) |

---

## Processo

### Passo 1: Validar Pré-requisitos

**Tool:** `tools/orders/validate_prerequisites.py`

```python
# Verificar carrinho
carrinho = get_cart(telefone)
if not carrinho.itens:
    return "Carrinho vazio!"

# Verificar frete confirmado
frete = get_confirmed_shipping(telefone)
if not frete:
    return "Calcule o frete primeiro!"

# Verificar dados cliente
cliente = get_client_data(telefone)
if not cliente.nome or not cliente.endereco:
    return "Preciso de seus dados completos..."
```

### Passo 2: Criar Pedido no Supabase (Backup)

**Tool:** `tools/orders/create.py`

```python
pedido_supabase = create_order_supabase(
    telefone=telefone,
    itens=carrinho.itens,
    frete=frete,
    total=carrinho.total + frete.preco,
    metodo_pagamento=metodo_pagamento,
    canal="whatsapp"
)

# Retorna pedido_id (UUID)
```

### Passo 3: Criar Pedido no Tiny ERP (Oficial)

**Tool:** `backend/src/services/tiny_hybrid_client.py`

```python
# Usa cliente híbrido (V3 → V2 fallback)
pedido_tiny = tiny_client.create_order({
    "cliente": cliente,
    "itens": convert_items_to_tiny_format(carrinho.itens),
    "frete": frete.preco,
    "metodo_pagamento": metodo_pagamento
})

# Atualizar Supabase com tiny_pedido_id
update_order_tiny_id(pedido_supabase.id, pedido_tiny.id)
```

### Passo 4: Gerar Pagamento

**Tool:** `tools/payments/generate_pix.py` ou `tools/payments/process_card.py`

#### PIX
```python
if metodo_pagamento == "pix":
    pix = generate_pix_payment(
        valor=total,
        pedido_id=pedido_supabase.id,
        cliente_nome=cliente.nome
    )

    # Retorna:
    # {
    #   "qr_code_url": "data:image/png;base64...",
    #   "pix_copia_cola": "00020126...",
    #   "expira_em": "2026-02-11T15:00:00"
    # }
```

#### Cartão
```python
if metodo_pagamento == "cartao":
    link_pagamento = generate_payment_link(
        valor=total,
        pedido_id=pedido_supabase.id,
        descricao="Pedido Roça Capital"
    )

    # Retorna:
    # {
    #   "payment_url": "https://pagar.me/checkout/...",
    #   "expira_em": "2026-02-11T18:00:00"
    # }
```

### Passo 5: Enviar Confirmação

**Tool:** `tools/whatsapp/send_message.py`

**Template:** `hardprompts/confirmacao_pedido.txt`

```python
response = format_order_confirmation(
    pedido=pedido_supabase,
    pagamento=pix or link_pagamento,
    metodo=metodo_pagamento
)

send_message(telefone, response)

# Se PIX, enviar imagem QR Code
if metodo_pagamento == "pix":
    send_image(telefone, pix.qr_code_url)
```

### Passo 6: Limpar Carrinho

**Tool:** `tools/cart/clear_cart.py`

```python
clear_cart(telefone)
```

---

## Tools Necessários

- `tools/orders/validate_prerequisites.py`
- `tools/orders/create.py`
- `backend/src/services/tiny_hybrid_client.py`
- `tools/payments/generate_pix.py`
- `tools/payments/process_card.py`
- `tools/whatsapp/send_message.py`
- `tools/cart/clear_cart.py`

---

## Saídas

### Pedido Criado (PIX)

```
✅ Pedido #1234 Criado com Sucesso!

📦 Resumo:
━━━━━━━━━━━━━━━━━
🧀 Queijo Canastra 500g (2x) - R$ 90,00
🍯 Doce de Leite 300g (1x) - R$ 18,00
📍 Frete (Lalamove) - R$ 15,00
━━━━━━━━━━━━━━━━━
💰 Total: R$ 123,00

💳 Pagamento: PIX

[QR CODE aparece aqui]

Ou copie e cole:
00020126580014br.gov.bcb.pix...

⏰ Válido por 30 minutos

Assim que o pagamento for confirmado, você receberá um aviso e o pedido entrará em preparação! 🚀
```

### Pedido Criado (Cartão)

```
✅ Pedido #1234 Criado com Sucesso!

📦 Total: R$ 123,00
💳 Pagamento: Cartão de Crédito

🔗 Link para pagamento:
https://pagar.me/checkout/abc123

Clique no link, preencha os dados do cartão e pronto!

O link expira em 3 horas.
```

---

## Tratamento de Erros

### Erro: Tiny API Falhou

```python
try:
    pedido_tiny = tiny_client.create_order(...)
except Exception as e:
    log_error(f"Tiny falhou: {e}")

    # Salvar no Supabase como "pendente_tiny"
    update_order_status(pedido_id, "pendente_tiny_sync")

    # Notificar admin
    notify_admin(f"Pedido {pedido_id} criado no Supabase mas falhou no Tiny")

    # Continuar fluxo (pagamento ainda funciona)
    # Sync manual depois
```

### Erro: Geração de PIX Falhou

```python
try:
    pix = generate_pix_payment(...)
except Exception as e:
    log_error(f"PIX falhou: {e}")

    # Oferecer alternativa
    return "Ops! PIX temporariamente indisponível. Quer pagar com cartão ou na entrega?"
```

### Erro: Estoque Alterou Durante Processo

```python
# Revalidar estoque antes de criar pedido
for item in carrinho.itens:
    produto_atual = get_product(item.produto_id)
    if produto_atual.estoque < item.quantidade:
        return f"Ops! O estoque de {produto_atual.nome} mudou. Temos apenas {produto_atual.estoque} unidades agora. Quer ajustar?"
```

---

## Contexto Necessário

- `context/politicas_loja.yaml` - Políticas de troca/devolução
- `hardprompts/confirmacao_pedido.txt` - Template confirmação
- `hardprompts/pagamento_pix.txt` - Instruções PIX

---

## Métricas

- **Tempo médio:** 3-5 segundos
- **Taxa de sucesso:** > 95%
- **Conversão checkout:** ~85% (dos que chegam aqui)

---

**Última atualização:** 11/02/2026
