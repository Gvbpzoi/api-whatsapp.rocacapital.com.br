# Goal 3: Gestão de Carrinho

## Objetivo

Gerenciar carrinho do cliente: adicionar, remover, visualizar e calcular total.

---

## Quando Executar

- Cliente quer adicionar produto: "adiciona 2", "quero esse"
- Cliente quer remover: "tira o queijo", "remove item 1"
- Cliente quer ver carrinho: "ver carrinho", "o que eu tenho?"
- Cliente quer limpar: "limpa tudo", "começa de novo"

---

## Entradas

| Campo | Descrição |
|-------|-----------|
| `telefone` | Telefone do cliente |
| `acao` | add, remove, view, clear |
| `produto_id` | UUID do produto (se add/remove) |
| `quantidade` | Quantidade (se add) |

---

## Processo

### Adicionar Item

**Tools:**
- `tools/cart/add_item.py`
- `tools/cart/calculate_total.py`

```python
# 1. Validar estoque
produto = get_product(produto_id)
if produto.estoque < quantidade:
    return erro_estoque_insuficiente()

# 2. Adicionar ao carrinho
carrinho = add_to_cart(telefone, produto_id, quantidade)

# 3. Calcular total
total = calculate_cart_total(carrinho)

# 4. Responder
return format_item_added(produto, quantidade, total)
```

### Ver Carrinho

**Tools:**
- `tools/cart/view_cart.py`
- `tools/cart/calculate_total.py`

```python
carrinho = get_cart(telefone)

if not carrinho.itens:
    return "Seu carrinho está vazio! 🛒"

# Formatar lista de itens
response = format_cart_view(carrinho)
return response
```

### Remover Item

**Tools:**
- `tools/cart/remove_item.py`

```python
remove_from_cart(telefone, produto_id)
carrinho = get_cart(telefone)
total = calculate_cart_total(carrinho)

return format_item_removed(total)
```

### Limpar Carrinho

**Tools:**
- `tools/cart/clear_cart.py`

```python
clear_cart(telefone)
return "Carrinho limpo! Podemos começar de novo. 😊"
```

---

## Tools Necessários

- `tools/cart/add_item.py`
- `tools/cart/remove_item.py`
- `tools/cart/view_cart.py`
- `tools/cart/clear_cart.py`
- `tools/cart/calculate_total.py`

---

## Saídas

### Adicionar Item

```
✅ Adicionei ao carrinho:

🧀 Queijo Canastra 500g
📦 Quantidade: 2 un.
💰 Subtotal: R$ 90,00

🛒 Carrinho atual:
   2 itens | Total: R$ 90,00

Quer adicionar mais algo ou calcular o frete?
```

### Ver Carrinho

```
🛒 Seu Carrinho:

1️⃣ Queijo Canastra 500g
   2 un. × R$ 45,00 = R$ 90,00

2️⃣ Doce de Leite 300g
   1 un. × R$ 18,00 = R$ 18,00

━━━━━━━━━━━━━━━━━
💰 Total: R$ 108,00
(frete não incluído)

Pronto para finalizar? Digite "calcular frete"
```

---

## Tratamento de Erros

### Estoque Insuficiente

```python
if produto.estoque < quantidade:
    return f"Ops! Temos apenas {produto.estoque} unidades de {produto.nome} disponíveis. Quer ajustar a quantidade?"
```

### Produto Variável (kg)

```python
if produto.requer_pesagem:
    return "Este produto é vendido por peso (kg). Quantos quilos você quer aproximadamente?"
```

---

**Última atualização:** 11/02/2026
