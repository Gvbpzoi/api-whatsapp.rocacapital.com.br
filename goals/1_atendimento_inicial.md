# Goal 1: Atendimento Inicial

## Objetivo

Recepcionar o cliente de forma calorosa, identificá-lo e iniciar uma sessão de atendimento personalizada.

---

## Quando Executar

- Cliente envia primeira mensagem do dia
- Cliente envia mensagem após > 2 horas de inatividade
- Nova sessão é iniciada

---

## Entradas

| Campo | Tipo | Descrição | Obrigatório |
|-------|------|-----------|-------------|
| `telefone` | string | Telefone do cliente (5531999999999) | ✅ |
| `mensagem` | string | Primeira mensagem do cliente | ✅ |
| `horario` | datetime | Timestamp da mensagem | ✅ |

---

## Processo

### Passo 1: Verificar Cliente Existente

**Tool:** `tools/session/check_client.py`

```python
cliente = check_client(telefone)

if cliente:
    # Cliente conhecido
    nome = cliente.nome
    historico = cliente.ultima_compra
else:
    # Cliente novo
    nome = None
    historico = None
```

### Passo 2: Carregar Memória (se existir)

**Tool:** `memory/search.py`

```python
# Buscar preferências do cliente
preferencias = memory_search(f"cliente:{telefone}")

# Exemplos de memória:
# - "Cliente prefere queijos meia-cura"
# - "Cliente sempre pede entrega para Savassi"
# - "Cliente perguntou sobre mel último mês"
```

### Passo 3: Escolher Saudação Apropriada

**Tool:** `tools/whatsapp/format_response.py`

**Regras:**
- Cliente novo → Saudação formal + apresentação
- Cliente conhecido → Saudação personalizada + última compra
- Horário 6h-12h → "Bom dia"
- Horário 12h-18h → "Boa tarde"
- Horário 18h-23h → "Boa noite"

**Usar template:** `hardprompts/saudacao.txt`

### Passo 4: Criar/Atualizar Sessão

**Tool:** `tools/session/create_or_update.py`

```python
sessao = create_session(
    telefone=telefone,
    nome=nome or "Cliente",
    modo="agent",  # Inicia com bot
    canal="whatsapp"
)
```

### Passo 5: Enviar Saudação

**Tool:** `tools/whatsapp/send_message.py`

```python
response = format_saudacao(
    nome=nome,
    horario=horario,
    historico=historico,
    preferencias=preferencias
)

send_message(telefone, response)
```

---

## Tools Necessários

| Tool | Função | Localização |
|------|--------|-------------|
| `check_client` | Verificar se cliente existe | `tools/session/check_client.py` |
| `memory_search` | Buscar preferências | `memory/search.py` |
| `format_response` | Formatar resposta | `tools/whatsapp/format_response.py` |
| `create_session` | Criar sessão | `tools/session/create_or_update.py` |
| `send_message` | Enviar WhatsApp | `tools/whatsapp/send_message.py` |

---

## Saídas

### Sucesso

```json
{
  "status": "success",
  "sessao_id": "uuid",
  "cliente": {
    "telefone": "5531999999999",
    "nome": "João Silva",
    "conhecido": true
  },
  "mensagem_enviada": "Oi João! Tudo bem? Vi que você comprou queijo canastra conosco mês passado. Como posso ajudar hoje? 😊"
}
```

### Cliente Novo

```json
{
  "status": "success",
  "sessao_id": "uuid",
  "cliente": {
    "telefone": "5531999999999",
    "nome": null,
    "conhecido": false
  },
  "mensagem_enviada": "Olá! Seja bem-vindo à Roça Capital! 🌾 Somos uma loja especializada em produtos artesanais mineiros no Mercado Central de BH. Como posso ajudar você hoje?"
}
```

---

## Tratamento de Erros

### Erro: Cliente Bloqueado

```python
if cliente.bloqueado:
    log_warning(f"Cliente bloqueado: {telefone}")
    send_message(telefone, "Desculpe, não podemos atendê-lo no momento. Entre em contato pelo telefone (31) 3274-xxxx.")
    return {"status": "blocked"}
```

### Erro: Falha na Busca de Memória

```python
try:
    preferencias = memory_search(f"cliente:{telefone}")
except Exception as e:
    log_error(f"Falha ao buscar memória: {e}")
    preferencias = None  # Continua sem personalização
```

### Erro: Falha no Envio WhatsApp

```python
try:
    send_message(telefone, response)
except WhatsAppAPIError as e:
    log_error(f"Falha WhatsApp: {e}")
    # Salvar mensagem pendente no banco
    save_pending_message(telefone, response)
    # Alertar humano
    notify_admin(f"WhatsApp falhou para {telefone}")
    return {"status": "error", "reason": "whatsapp_api_failed"}
```

---

## Exemplos de Uso

### Exemplo 1: Cliente Novo (8h da manhã)

**Entrada:**
```json
{
  "telefone": "5531988887777",
  "mensagem": "Oi, vocês têm queijo?",
  "horario": "2026-02-11T08:15:00"
}
```

**Processo:**
1. check_client → null (cliente não existe)
2. memory_search → [] (sem histórico)
3. Saudação: "Bom dia" + apresentação formal
4. create_session → nova sessão
5. send_message → saudação enviada

**Saída:**
```
Bom dia! 😊 Seja bem-vindo à Roça Capital!

Somos uma loja especializada em produtos artesanais mineiros no Mercado Central de BH. Temos queijos, cachaças, doces, cafés e muito mais!

Sobre queijos, temos várias opções deliciosas. Quer que eu te mostre alguns?
```

---

### Exemplo 2: Cliente Conhecido (14h)

**Entrada:**
```json
{
  "telefone": "5531999999999",
  "mensagem": "Oi!",
  "horario": "2026-02-11T14:30:00"
}
```

**Processo:**
1. check_client → João Silva (última compra: 15/01/2026)
2. memory_search → ["prefere queijos meia-cura", "entrega Savassi"]
3. Saudação: "Boa tarde" + nome + última compra
4. update_session → sessão atualizada
5. send_message → saudação personalizada

**Saída:**
```
Boa tarde, João! Tudo bem? 😊

Vi que você comprou queijo canastra meia-cura conosco em janeiro. Gostou?

Como posso ajudar você hoje?
```

---

### Exemplo 3: Cliente Retornando (após 3 horas)

**Entrada:**
```json
{
  "telefone": "5531988886666",
  "mensagem": "voltei",
  "horario": "2026-02-11T16:00:00"
}
```

**Processo:**
1. check_client → Maria (sessão anterior às 13h)
2. Verificar: última_msg > 2h → nova saudação
3. memory_search → carrinho anterior (ainda ativo?)
4. Saudação: "Boa tarde de novo" + contexto anterior
5. update_session → sessão reativada

**Saída:**
```
Boa tarde de novo, Maria! 😊

Vi que você estava olhando nossos queijos mais cedo. Ainda posso ajudar com isso?

(Seu carrinho com 2 itens ainda está aqui, caso queira continuar!)
```

---

## Contexto Necessário

- `context/frases_atendimento.yaml` - Frases de saudação
- `context/politicas_loja.yaml` - Horário de funcionamento
- `hardprompts/saudacao.txt` - Template de saudação

---

## Métricas

- **Tempo médio:** 2-3 segundos
- **Taxa de sucesso:** > 99%
- **Falhas comuns:** WhatsApp API timeout (<1%)

---

## Melhorias Futuras

- [ ] Detectar idioma do cliente (PT/EN/ES)
- [ ] Integrar com CRM para dados mais ricos
- [ ] A/B test de saudações
- [ ] Análise de sentimento na primeira mensagem

---

**Última atualização:** 11/02/2026
**Versão:** 2.0.0-GOTCHA
