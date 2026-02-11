# Goal 4: Cálculo de Frete

## Objetivo

Calcular opções de frete (Lalamove/Correios) e permitir que cliente escolha.

---

## Quando Executar

- Cliente pergunta: "quanto fica o frete?", "entrega em quanto tempo?"
- Após visualizar carrinho
- Antes de finalizar pedido

---

## Entradas

| Campo | Descrição |
|-------|-----------|
| `telefone` | Telefone do cliente |
| `cep` | CEP de entrega |
| `endereco` | Endereço completo (opcional) |

---

## Processo

### Passo 1: Validar CEP

**Tool:** `tools/shipping/validate_cep.py`

```python
endereco_completo = validate_and_complete_cep(cep)

if not endereco_completo:
    return "CEP inválido. Digite novamente?"
```

### Passo 2: Calcular Opções

**Tool:** `tools/shipping/calculate.py`

```python
carrinho = get_cart(telefone)
peso_total = calculate_total_weight(carrinho)
valor_total = calculate_cart_total(carrinho)

opcoes = calculate_shipping_options(
    origem_cep="30180-084",  # Mercado Central BH
    destino_cep=cep,
    peso=peso_total,
    valor=valor_total
)

# Retorna:
# [
#   {
#     "tipo": "lalamove",
#     "nome": "Entrega Rápida (Lalamove)",
#     "preco": 15.00,
#     "prazo": "1-2 horas"
#   },
#   {
#     "tipo": "correios_pac",
#     "nome": "Correios PAC",
#     "preco": 25.00,
#     "prazo": "5-7 dias úteis"
#   },
#   {
#     "tipo": "correios_sedex",
#     "nome": "Correios SEDEX",
#     "preco": 35.00,
#     "prazo": "2-3 dias úteis"
#   }
# ]
```

### Passo 3: Apresentar Opções

**Tool:** `tools/whatsapp/format_response.py`

**Template:** `hardprompts/opcoes_frete.txt`

```python
response = format_shipping_options(opcoes, endereco_completo)
send_message(telefone, response)

# Salvar opções na sessão (para confirmação)
save_shipping_options(telefone, opcoes)
```

---

## Tools Necessários

- `tools/shipping/validate_cep.py`
- `tools/shipping/calculate.py`
- `tools/shipping/confirm.py` (usado no próximo passo)
- `tools/cart/calculate_total.py`

---

## Saídas

```
📍 Endereço de entrega:
Rua das Flores, 123 - Savassi
Belo Horizonte - MG
CEP: 30140-110

📦 Opções de Entrega:

1️⃣ Entrega Rápida (Lalamove)
   💰 R$ 15,00
   ⏰ 1-2 horas
   ⭐ Recomendado!

2️⃣ Correios PAC
   💰 R$ 25,00
   ⏰ 5-7 dias úteis

3️⃣ Correios SEDEX
   💰 R$ 35,00
   ⏰ 2-3 dias úteis

Digite o número da opção que você prefere!
```

---

## Tratamento de Erros

### CEP Fora da Área

```python
if not is_delivery_area(cep):
    return "Infelizmente não entregamos nesta região ainda. Você pode retirar na loja no Mercado Central!"
```

### Falha na API Lalamove

```python
try:
    lalamove_quote = get_lalamove_quote(...)
except Exception:
    # Continua apenas com Correios
    opcoes = calculate_correios_only()
```

---

**Última atualização:** 11/02/2026
