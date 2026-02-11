# Goal 7: Controle Humano-Agente

## Objetivo

Gerenciar transição entre atendimento humano e bot automaticamente, garantindo experiência fluida.

---

## Quando Executar

- **Sempre ativo** - Verifica em cada mensagem
- Humano assume conversa
- Bot retoma após inatividade
- Cliente solicita atendente humano

---

## Entradas

| Campo | Descrição |
|-------|-----------|
| `telefone` | Telefone do cliente |
| `mensagem` | Conteúdo da mensagem |
| `remetente` | "cliente" ou "atendente" |
| `atendente_id` | ID do atendente (se humano) |

---

## Processo

### Passo 1: Verificar Sessão Atual

**Tool:** `backend/src/services/session_manager.py`

```python
sessao = get_session(telefone)

# Estados possíveis:
# - "agent": Bot atendendo
# - "human": Humano atendendo
# - None: Nova sessão
```

### Passo 2: Detectar Controle Humano

**3 Métodos de Detecção:**

#### Método 1: Detecção Automática (Prefixo)

```python
HUMAN_INDICATORS = [
    r"^\[HUMANO\]",
    r"^\[ATENDENTE\]",
    r"^\[MANUAL\]",
    r"^\[H\]"
]

for pattern in HUMAN_INDICATORS:
    if re.match(pattern, mensagem, re.IGNORECASE):
        # Humano está respondendo!
        takeover_session(telefone, atendente_id="auto_detected")
        return {"should_agent_respond": False, "reason": "human_prefix"}
```

#### Método 2: Comandos Explícitos

```python
COMMANDS = {
    "/pausar": "Pausa bot",
    "/retomar": "Retoma bot",
    "/assumir": "Humano assume",
    "/liberar": "Libera para bot",
    "/status": "Ver quem está atendendo"
}

if mensagem in COMMANDS:
    handle_command(telefone, mensagem, atendente_id)
    return {"should_agent_respond": False, "reason": "command"}
```

#### Método 3: API (Dashboard Web)

```python
# POST /api/session/{telefone}/takeover
# Body: {"attendant_id": "joao@rocacapital.com"}

@app.post("/api/session/{telefone}/takeover")
async def takeover(telefone: str, attendant_id: str):
    session_manager.takeover(telefone, attendant_id)
    return {"status": "taken_over"}
```

### Passo 3: Auto-Retomada

**Tool:** `backend/src/services/session_manager.py`

```python
# Se humano não responde por 5 minutos
AUTO_RESUME_TIMEOUT = 300  # segundos

if sessao.modo == "human":
    tempo_inativo = now() - sessao.ultima_msg_atendente

    if tempo_inativo > AUTO_RESUME_TIMEOUT:
        # Retomar automaticamente
        release_session(telefone)

        # Avisar cliente
        send_message(
            telefone,
            "Oi! Voltei para continuar te ajudando. 😊 Em que posso ajudar?"
        )

        return {"should_agent_respond": True, "reason": "auto_resumed"}
```

### Passo 4: Decidir Quem Responde

**Tool:** `backend/src/services/session_manager.py`

```python
should_respond, reason = session_manager.process_message(
    phone=telefone,
    message=mensagem,
    source="whatsapp",
    attendant_id=atendente_id
)

if should_respond:
    # Bot responde
    response = await agent.run(mensagem)
    send_message(telefone, response)
else:
    # Humano no controle, bot não responde
    log_info(f"Humano atendendo {telefone}: {reason}")
```

---

## Tools Necessários

- `backend/src/services/session_manager.py` - Core (já implementado!)
- `tools/session/takeover.py` - Assumir sessão
- `tools/session/release.py` - Liberar sessão
- `tools/session/check_status.py` - Ver status

---

## Saídas

### Bot Pausado (Comando /pausar)

```
✅ Bot pausado para este cliente.

Você pode responder manualmente agora.

Para retomar o bot: /retomar
```

### Bot Retomado (Comando /retomar)

```
✅ Bot retomado!

Voltarei a responder automaticamente.
```

### Status (Comando /status)

```
📊 Status da Sessão:

👤 Cliente: 5531999999999
🤖 Modo: Humano atendendo
👨‍💼 Atendente: João Silva
⏰ Assumiu há: 3 minutos
🔄 Auto-retomada em: 2 minutos

Digite /liberar para devolver ao bot.
```

### Auto-Retomada

```
[Para o atendente no sistema]
⚠️ Sessão 5531999999999 retomada automaticamente (inatividade > 5 min)

[Para o cliente no WhatsApp]
Oi! Voltei para continuar te ajudando. 😊 Em que posso ajudar?
```

---

## Tratamento de Erros

### Múltiplos Atendentes

```python
if sessao.atendente_id and atendente_id != sessao.atendente_id:
    return f"⚠️ Cliente já está sendo atendido por {sessao.atendente_nome}. Espere ele liberar!"
```

### Comando Inválido

```python
if mensagem.startswith("/") and mensagem not in COMMANDS:
    return f"Comando '{mensagem}' não reconhecido. Comandos disponíveis: /pausar, /retomar, /status"
```

### Sessão Expirada

```python
if sessao.criado_em < datetime.now() - timedelta(hours=24):
    # Limpar sessão antiga
    delete_session(telefone)
    # Criar nova
    create_session(telefone)
```

---

## Fluxos Completos

### Fluxo 1: Humano Assume via Prefixo

```
[Bot] Cliente: "Quero queijo canastra"
[Bot] Agent: "Temos 3 opções de Canastra..."

[Cliente] "Quero o de 1kg"
[Humano] "[HUMANO] Oi! Sou o João, vou te ajudar pessoalmente!"

→ session_manager detecta [HUMANO]
→ Muda modo para "human"
→ Bot para de responder
→ João conversa manualmente

[João] "Cliente resolvido, pode liberar"
[João] "/liberar"

→ session_manager muda modo para "agent"
→ Bot retoma
[Bot] "Oi! Voltei para continuar te ajudando. 😊"
```

### Fluxo 2: Auto-Retomada

```
[Humano] João assume às 14:00
[Cliente] "Obrigado pela ajuda!"
[João] "De nada! :-)"

[14:02] Cliente sem resposta
[14:03] Cliente sem resposta
[14:04] Cliente sem resposta
[14:05] João sem responder (5 min!)

→ session_manager: AUTO_RESUME_TIMEOUT atingido
→ Muda modo para "agent"
→ Log: "Sessão auto-retomada por inatividade"

[Cliente] "Você ainda está aí?"
[Bot] "Oi! Voltei para continuar te ajudando. 😊 Em que posso ajudar?"
```

### Fluxo 3: Cliente Pede Humano

```
[Cliente] "Quero falar com um atendente"

[Bot] "Claro! Vou chamar um atendente humano para você. Um momento! ⏰"

→ Bot notifica dashboard: "Cliente 5531999999999 solicita humano"
→ Bot pausa automaticamente
→ Aguarda atendente assumir

[João no dashboard] Clica em "Assumir"
→ API: POST /session/{telefone}/takeover
→ session_manager muda para "human"

[João] "Oi! Sou o João, como posso ajudar?"
```

---

## Contexto Necessário

- `backend/src/services/session_manager.py` - Core já implementado
- `backend/src/models/session.py` - Modelos de sessão
- `args/comportamento_agente.yaml` - Timeout de auto-retomada

---

## Métricas

- **Taxa de takeover:** ~5% das conversas
- **Tempo médio humano:** 8 minutos
- **Taxa de auto-retomada:** ~30% dos takevers
- **Satisfação cliente (humano):** 4.8/5.0

---

## Configurações

```yaml
# args/comportamento_agente.yaml

session_manager:
  auto_resume_timeout: 300  # 5 minutos
  human_indicators:
    - "[HUMANO]"
    - "[ATENDENTE]"
    - "[MANUAL]"
  commands:
    - "/pausar"
    - "/retomar"
    - "/assumir"
    - "/liberar"
    - "/status"
```

---

**Última atualização:** 11/02/2026
**Versão:** 2.0.0-GOTCHA
