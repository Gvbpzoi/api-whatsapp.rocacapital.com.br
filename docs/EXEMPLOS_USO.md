# 💡 Exemplos de Uso do Sistema

## 🎯 Casos de Uso Reais

### 1. Integração com WhatsApp Business API

```python
# webhook_handler.py
from fastapi import FastAPI, Request
import httpx

app = FastAPI()
BACKEND_URL = "http://localhost:8000"

@app.post("/whatsapp/incoming")
async def handle_whatsapp_message(request: Request):
    """Recebe mensagens do WhatsApp Business API"""
    data = await request.json()

    # Extrair dados
    phone = data['from']
    message = data['text']['body']

    # Enviar para o backend
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BACKEND_URL}/webhook/whatsapp",
            json={
                "phone": phone,
                "message": message,
                "sender_type": "customer"
            }
        )

        result = response.json()

        if result['should_respond']:
            # Enviar resposta do bot
            await send_whatsapp_message(phone, result['response'])
        else:
            # Notificar atendente se necessário
            if 'escalation_requested' in result.get('metadata', {}):
                await notify_attendant(phone, message)

    return {"status": "ok"}


async def send_whatsapp_message(phone: str, message: str):
    """Envia mensagem via WhatsApp Business API"""
    # Implementar envio via API do WhatsApp
    pass


async def notify_attendant(phone: str, message: str):
    """Notifica atendente que cliente pediu ajuda"""
    # Enviar notificação para dashboard/slack/email
    pass
```

### 2. Dashboard de Monitoramento (React)

```typescript
// AttendanceDashboard.tsx
import React, { useState, useEffect } from 'react'
import axios from 'axios'

interface Session {
  phone: string
  mode: 'agent' | 'human' | 'paused'
  human_attendant?: string
  last_customer_message?: string
}

export function AttendanceDashboard() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentUser] = useState('joao@empresa.com')

  useEffect(() => {
    const fetchSessions = async () => {
      const { data } = await axios.get('/sessions/active')
      setSessions(data.sessions)
    }

    // Atualizar a cada 3 segundos
    const interval = setInterval(fetchSessions, 3000)
    fetchSessions()

    return () => clearInterval(interval)
  }, [])

  const takeover = async (phone: string) => {
    await axios.post(`/session/${phone}/takeover`, {
      attendant_id: currentUser
    })
  }

  const release = async (phone: string) => {
    await axios.post(`/session/${phone}/release`)
  }

  return (
    <div className="dashboard">
      <h1>Conversas Ativas</h1>

      <div className="sessions-grid">
        {sessions.map(session => (
          <SessionCard
            key={session.phone}
            session={session}
            onTakeover={() => takeover(session.phone)}
            onRelease={() => release(session.phone)}
            currentUser={currentUser}
          />
        ))}
      </div>
    </div>
  )
}

function SessionCard({ session, onTakeover, onRelease, currentUser }) {
  const getModeIcon = () => {
    switch (session.mode) {
      case 'agent': return '🤖'
      case 'human': return '👤'
      case 'paused': return '⏸️'
      default: return '❓'
    }
  }

  const isMySession = session.human_attendant === currentUser

  return (
    <div className="session-card">
      <div className="session-header">
        <span className="mode-icon">{getModeIcon()}</span>
        <span className="phone">{session.phone}</span>
      </div>

      <div className="session-info">
        <div>Modo: <strong>{session.mode}</strong></div>
        {session.human_attendant && (
          <div>Atendente: <strong>{session.human_attendant}</strong></div>
        )}
      </div>

      <div className="session-actions">
        {session.mode === 'agent' && (
          <button onClick={onTakeover} className="btn-takeover">
            Assumir
          </button>
        )}

        {session.mode === 'human' && isMySession && (
          <button onClick={onRelease} className="btn-release">
            Liberar
          </button>
        )}
      </div>
    </div>
  )
}
```

### 3. Sistema de Notificações (Slack)

```python
# notifications.py
import asyncio
from slack_sdk.web.async_client import AsyncWebClient
from src.services.session_manager import SessionManager

slack_client = AsyncWebClient(token="xoxb-your-token")
CHANNEL_ID = "C12345678"

async def notify_escalation(phone: str, message: str):
    """Notifica no Slack quando cliente pede atendimento humano"""
    await slack_client.chat_postMessage(
        channel=CHANNEL_ID,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🆘 *Cliente solicitou atendimento humano*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Telefone:*\n{phone}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Mensagem:*\n{message}"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Assumir"},
                        "action_id": f"takeover_{phone}",
                        "style": "primary"
                    }
                ]
            }
        ]
    )


async def notify_mode_change(phone: str, old_mode: str, new_mode: str, attendant: str):
    """Notifica mudanças de modo"""
    emoji = "🤖" if new_mode == "agent" else "👤"

    await slack_client.chat_postMessage(
        channel=CHANNEL_ID,
        text=f"{emoji} {phone}: {old_mode} → {new_mode} ({attendant})"
    )
```

### 4. Webhook n8n Completo com Logs

```javascript
// n8n Code Node: "Processar Webhook"
const incoming = $input.first().json;
const phone = incoming.phone || incoming.from;
const message = incoming.message || incoming.text;

// Log estruturado
console.log(JSON.stringify({
  event: 'whatsapp_message_received',
  phone: phone,
  message_preview: message.substring(0, 50),
  timestamp: new Date().toISOString()
}));

// Enviar para backend
const response = await $http.post('http://backend:8000/webhook/whatsapp', {
  phone: phone,
  message: message,
  sender_type: 'customer',
  metadata: {
    n8n_execution_id: $executionId,
    received_at: new Date().toISOString()
  }
});

// Log da decisão
console.log(JSON.stringify({
  event: 'backend_decision',
  phone: phone,
  should_respond: response.should_respond,
  reason: response.reason,
  mode: response.session_mode
}));

return [response];
```

### 5. Script de Monitoramento (Python)

```python
# monitor.py
"""
Script para monitorar sessões ativas e enviar alertas
"""
import asyncio
import httpx
from datetime import datetime, timedelta

BACKEND_URL = "http://localhost:8000"
CHECK_INTERVAL = 10  # segundos

async def monitor_sessions():
    """Monitora sessões e envia alertas"""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                # Buscar sessões ativas
                response = await client.get(f"{BACKEND_URL}/sessions/active")
                sessions = response.json()['sessions']

                for session in sessions:
                    # Verificar se cliente está aguardando há muito tempo
                    if session['mode'] == 'paused':
                        await check_paused_session(session)

                    # Verificar se humano está inativo
                    if session['mode'] == 'human':
                        await check_inactive_human(session)

            except Exception as e:
                print(f"❌ Erro no monitoramento: {e}")

            await asyncio.sleep(CHECK_INTERVAL)


async def check_paused_session(session):
    """Alerta se sessão pausada há muito tempo"""
    if not session.get('paused_at'):
        return

    paused_at = datetime.fromisoformat(session['paused_at'])
    delta = datetime.utcnow() - paused_at

    if delta > timedelta(minutes=10):
        print(f"⚠️ Sessão {session['phone']} pausada há {delta.seconds//60}min!")
        # Enviar alerta


async def check_inactive_human(session):
    """Alerta se humano está inativo há muito tempo"""
    if not session.get('last_human_message'):
        return

    last_msg = datetime.fromisoformat(session['last_human_message'])
    delta = datetime.utcnow() - last_msg

    if delta > timedelta(minutes=3):
        print(f"⚠️ Atendente inativo há {delta.seconds//60}min: {session['phone']}")
        # Enviar alerta


if __name__ == "__main__":
    asyncio.run(monitor_sessions())
```

### 6. CLI de Administração

```python
# cli.py
"""
CLI para administração do sistema
"""
import typer
import httpx

app = typer.Typer()
BACKEND_URL = "http://localhost:8000"

@app.command()
def list_sessions(mode: str = None):
    """Lista sessões ativas"""
    url = f"{BACKEND_URL}/sessions/active"
    if mode:
        url += f"?mode={mode}"

    response = httpx.get(url)
    sessions = response.json()['sessions']

    typer.echo(f"\n📊 Total: {len(sessions)} sessões\n")

    for session in sessions:
        mode_emoji = {"agent": "🤖", "human": "👤", "paused": "⏸️"}
        typer.echo(
            f"{mode_emoji.get(session['mode'], '❓')} "
            f"{session['phone']} - {session['mode'].upper()}"
        )
        if session.get('human_attendant'):
            typer.echo(f"   → Atendente: {session['human_attendant']}")


@app.command()
def takeover(phone: str, attendant: str):
    """Assume uma conversa"""
    response = httpx.post(
        f"{BACKEND_URL}/session/{phone}/takeover",
        params={"attendant_id": attendant}
    )
    result = response.json()

    if result['success']:
        typer.echo(f"✅ {result['message']}")
    else:
        typer.echo(f"❌ {result['message']}", err=True)


@app.command()
def release(phone: str):
    """Libera uma conversa"""
    response = httpx.post(f"{BACKEND_URL}/session/{phone}/release")
    result = response.json()

    if result['success']:
        typer.echo(f"✅ {result['message']}")
    else:
        typer.echo(f"❌ {result['message']}", err=True)


@app.command()
def status(phone: str):
    """Mostra status de uma sessão"""
    response = httpx.get(f"{BACKEND_URL}/session/{phone}/status")
    session = response.json()

    typer.echo(f"\n📊 Status: {session['phone']}")
    typer.echo(f"🔧 Modo: {session['mode'].upper()}")
    if session.get('human_attendant'):
        typer.echo(f"👤 Atendente: {session['human_attendant']}")


if __name__ == "__main__":
    app()
```

**Uso:**
```bash
python cli.py list-sessions
python cli.py list-sessions --mode=human
python cli.py takeover 5531999999999 joao@empresa.com
python cli.py release 5531999999999
python cli.py status 5531999999999
```

### 7. Webhook de Teste (Curl)

```bash
# test_webhook.sh

#!/bin/bash

# Variáveis
BACKEND="http://localhost:8000"
PHONE="5531999999999"

# 1. Cliente manda mensagem
echo "1. Cliente: Quero queijo canastra"
curl -s -X POST $BACKEND/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d "{
    \"phone\": \"$PHONE\",
    \"message\": \"Quero queijo canastra\",
    \"sender_type\": \"customer\"
  }" | jq

sleep 2

# 2. Humano assume
echo -e "\n2. Atendente assume"
curl -s -X POST $BACKEND/session/$PHONE/takeover?attendant_id=teste@email.com | jq

sleep 2

# 3. Cliente manda outra mensagem (bot NÃO responde)
echo -e "\n3. Cliente: Quanto custa?"
curl -s -X POST $BACKEND/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d "{
    \"phone\": \"$PHONE\",
    \"message\": \"Quanto custa?\",
    \"sender_type\": \"customer\"
  }" | jq

sleep 2

# 4. Ver status
echo -e "\n4. Status da sessão"
curl -s $BACKEND/session/$PHONE/status | jq

sleep 2

# 5. Liberar
echo -e "\n5. Liberar conversa"
curl -s -X POST $BACKEND/session/$PHONE/release | jq

sleep 2

# 6. Cliente manda mensagem (bot RESPONDE)
echo -e "\n6. Cliente: Ainda tem?"
curl -s -X POST $BACKEND/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d "{
    \"phone\": \"$PHONE\",
    \"message\": \"Ainda tem?\",
    \"sender_type\": \"customer\"
  }" | jq
```

---

## 🎓 Tutoriais

### Como criar um novo comando

1. Adicionar no `SessionManager.COMMANDS`:
```python
COMMANDS = {
    # ... existentes
    "/meucomando": "Descrição do comando"
}
```

2. Criar método handler:
```python
def _cmd_meucomando(self, phone: str, attendant_id: Optional[str]) -> CommandResult:
    # Sua lógica
    return CommandResult(
        success=True,
        message="Comando executado!"
    )
```

3. Adicionar no `_process_command`:
```python
elif cmd == "/meucomando":
    return self._cmd_meucomando(phone, attendant_id)
```

### Como adicionar metadados customizados

```python
# Ao processar mensagem
session = manager.get_session(phone)
session.metadata['custom_field'] = 'valor'
session.metadata['priority'] = 'high'

# Depois recuperar
if session.metadata.get('priority') == 'high':
    # Tratamento especial
    pass
```

---

## 📞 Dúvidas?

Abra uma issue no GitHub ou entre em contato!
