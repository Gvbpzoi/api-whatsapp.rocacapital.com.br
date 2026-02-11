# 📱 Guia de Comandos - Controle Humano-Agente

## Como Funciona?

O sistema permite que **humanos e bots** trabalhem juntos no atendimento. Você pode:
- ✅ Deixar o bot atender automaticamente
- ✅ Assumir uma conversa quando necessário
- ✅ Pausar/retomar o bot quando quiser
- ✅ O sistema detecta automaticamente quando você interfere

---

## 🎯 3 Formas de Controlar

### 1️⃣ Detecção Automática (Mais Fácil)

Basta começar sua mensagem com `[HUMANO]`:

```
Cliente: Quero fazer um pedido grande
Bot: Olá! Me diz o que precisa...

Você: [HUMANO] Oi! Sou o João, vou te ajudar...
→ Bot PARA automaticamente! ✅
```

**Outros prefixos que funcionam:**
- `[HUMANO]`
- `[ATENDENTE]`
- `@agente pause`
- `@bot pare`

Quando terminar, envie `/liberar` para o bot voltar.

---

### 2️⃣ Comandos Manuais (Mais Controle)

Digite os comandos diretamente no chat:

#### `/pausar`
Pausa o bot. Nada acontece até você `/retomar`.

```
Você: /pausar
→ Bot pausado ⏸️
→ Cliente manda mensagem = nada acontece
→ Você atende manualmente
```

#### `/retomar`
Bot volta a responder automaticamente.

```
Você: /retomar
→ Bot ativo 🤖
→ Próxima mensagem do cliente = bot responde
```

#### `/assumir`
Você assume explicitamente a conversa.

```
Você: /assumir
→ Você está atendendo 👤
→ Bot NÃO responde
→ Sistema registra seu nome
```

#### `/liberar`
Libera conversa de volta para o bot.

```
Você: /liberar
→ Bot volta a atender 🤖
→ Sistema limpa atendente
```

#### `/status`
Mostra status atual da conversa.

```
Você: /status

📊 Status da Sessão
━━━━━━━━━━━━━━━━
📞 Cliente: 5531999999999
🤖 Modo: AGENT
👤 Atendente: Nenhum
⏰ Última msg cliente: 2min atrás
🤖 Última msg agente: 2min atrás
👨 Última msg humano: Nunca
```

#### `/help`
Lista todos os comandos.

---

### 3️⃣ Via Dashboard / API (Para Sistemas)

Se você tem um sistema de atendimento:

```bash
# Ver todas conversas ativas
GET /sessions/active

# Assumir conversa
POST /session/5531999999999/takeover
{
  "attendant_id": "joao@empresa.com"
}

# Liberar conversa
POST /session/5531999999999/release

# Ver status
GET /session/5531999999999/status
```

---

## 📝 Exemplos Práticos

### Exemplo 1: Cliente Pede Atendimento Humano

```
Cliente: Quero falar com um vendedor
Bot: Vou te conectar com um de nossos vendedores...
     [Sistema marca "escalation_requested"]

[Você vê no dashboard que tem uma solicitação]

Você: /assumir
Bot: [silêncio]

Você: Oi! Sou o João, como posso ajudar?
Cliente: Quero fazer um pedido corporativo...
[Conversa continua com você]

Você: Pronto! Pedido registrado 😊
Você: /liberar

Bot: Oi novamente! Estou aqui se precisar de algo mais!
```

### Exemplo 2: Assumir Conversa Complexa

```
Cliente: Tenho um problema com meu pedido anterior
Bot: Deixa eu verificar... [busca histórico]
Bot: Encontrei seu último pedido #12345...

Cliente: Não chegou ainda e já faz 3 dias
Bot: Vou verificar o status de entrega...

[Você vê que é um problema e decide assumir]

Você: [HUMANO] Oi! Vi que seu pedido atrasou...
→ Bot para automaticamente

Você: Vou verificar com a transportadora agora mesmo
Cliente: Ok, obrigado!
[Você resolve o problema]

Você: /liberar
Bot: 😊 Qualquer outra coisa, estou aqui!
```

### Exemplo 3: Pausar Durante Horário de Almoço

```
[12h - horário de almoço da equipe]

Você: /pausar
→ Bot pausado ⏸️

[Clientes mandam mensagem = nada acontece]
[Você vê depois do almoço]

[13h]
Você: /retomar
→ Bot ativo 🤖

[Bot processa mensagens que chegaram]
```

### Exemplo 4: Múltiplos Atendentes

```
Atendente João: /assumir
→ João está atendendo 👤

[João sai para almoço]

Atendente Maria: /assumir
→ Maria está atendendo 👤
→ Sistema registra que Maria assumiu de João

Cliente: [manda mensagem]
→ Vai para Maria (não para João)

Maria: /liberar
→ Bot volta a atender 🤖
```

---

## 🔔 Auto-Retomada

O sistema **retoma automaticamente** o bot se:
- Humano ficou **5 minutos sem responder**
- Cliente mandou nova mensagem
- Ninguém mais `/assumiu`

```
[10h00] Você: /assumir
[10h02] Cliente: Oi, preciso de ajuda
[Você não responde]
[10h07] Cliente: Tem alguém aí?
→ Sistema detecta inatividade (5min)
→ Bot retoma automaticamente! 🤖
→ Bot: Oi! Desculpe a demora, como posso ajudar?
```

**Para desativar auto-retomada:**
```bash
# No .env
AUTO_RESUME_TIMEOUT=0  # 0 = desativado
```

---

## 🎨 Integrações

### WhatsApp Business API

```javascript
// Quando receber mensagem no WhatsApp
async function onMessage(phone, message) {
  const response = await fetch('http://backend:8000/webhook/whatsapp', {
    method: 'POST',
    body: JSON.stringify({
      phone: phone,
      message: message,
      sender_type: 'customer'
    })
  })

  const data = await response.json()

  if (data.should_respond) {
    // Enviar resposta do bot
    await sendWhatsAppMessage(phone, data.response)
  } else {
    // Humano está atendendo ou bot pausado
    console.log(`Não respondendo: ${data.reason}`)
  }
}
```

### Dashboard React

```javascript
import { useState, useEffect } from 'react'

function AttendanceMonitor() {
  const [sessions, setSessions] = useState([])

  useEffect(() => {
    // Atualizar a cada 5 segundos
    const interval = setInterval(async () => {
      const res = await fetch('/sessions/active')
      setSessions(await res.json())
    }, 5000)

    return () => clearInterval(interval)
  }, [])

  async function takeover(phone) {
    await fetch(`/session/${phone}/takeover`, {
      method: 'POST',
      body: JSON.stringify({
        attendant_id: currentUser.email
      })
    })
  }

  return (
    <div>
      {sessions.map(s => (
        <div key={s.phone}>
          <span>{s.phone}</span>
          <span>{s.mode === 'human' ? '👤' : '🤖'}</span>
          {s.mode === 'agent' && (
            <button onClick={() => takeover(s.phone)}>
              Assumir
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
```

---

## ⚠️ Boas Práticas

### ✅ Faça

- Use `/assumir` quando for atender pessoalmente
- Use `/liberar` quando terminar
- Monitore o dashboard para pedidos de humano
- Configure notificações para escalações

### ❌ Não Faça

- Não deixe o bot pausado indefinidamente
- Não assuma sem verificar se já tem alguém atendendo
- Não esqueça de `/liberar` quando terminar
- Não ignore pedidos de atendimento humano

---

## 🆘 Troubleshooting

### Bot não responde

```bash
# Verificar status
curl http://localhost:8000/session/{phone}/status

# Possíveis causas:
# 1. Bot pausado → /retomar
# 2. Humano ativo → /liberar
# 3. Sistema detectou interferência → /liberar
```

### Não consigo assumir

```bash
# Ver quem está atendendo
curl http://localhost:8000/session/{phone}/status

# Se já tem alguém, precisa coordenar com a pessoa
# Ou forçar assumir novamente
```

### Auto-retomada não funciona

```bash
# Verificar configuração
echo $AUTO_RESUME_TIMEOUT

# Se 0, está desativado
# Alterar no .env para 300 (5min)
```

---

## 📞 Contato

Dúvidas sobre os comandos?
- 📱 WhatsApp: (31) 97266-6900
- 📧 Email: dev@rocacapital.com.br
