# 🤖 Agente WhatsApp - Roça Capital

Sistema de atendimento inteligente para WhatsApp com **Human-in-the-Loop** (controle humano-agente).

## 📋 Características

### ✅ Funcionalidades Principais
- **AI Agent** - Atendimento automatizado com GPT-4
- **Human-in-the-Loop** - Controle de quando humano/bot atende
- **Carrinho de Compras** - Gestão de pedidos
- **Pagamentos** - PIX e Cartão (Pagar.me)
- **Cálculo de Frete** - Lalamove e Correios
- **Histórico de Compras** - Recomendações personalizadas
- **Busca Inteligente** - Produtos com matching avançado

### 🎯 Controle Humano-Agente

O sistema permite **interferência humana** de 3 formas:

#### 1️⃣ **Detecção Automática**
O bot detecta automaticamente quando um humano responde:
```
Cliente: Quero comprar queijo
[Bot responde]

Cliente: Tem desconto?
[Humano envia]: [HUMANO] Olá! Sim, temos 10% off...
→ Sistema detecta e PAUSA o bot automaticamente
```

#### 2️⃣ **Comandos Manuais**
Atendente pode controlar via comandos:

```bash
/pausar     # Pausa o bot (você atende manualmente)
/retomar    # Bot volta a responder automaticamente
/assumir    # Você assume explicitamente
/liberar    # Libera de volta para o bot
/status     # Mostra quem está atendendo
```

#### 3️⃣ **API de Controle**
Dashboard ou sistema externo pode controlar via API:

```bash
# Assumir conversa
curl -X POST http://localhost:8000/session/{phone}/takeover \
  -d '{"attendant_id": "joao@empresa.com"}'

# Liberar para bot
curl -X POST http://localhost:8000/session/{phone}/release

# Ver status
curl http://localhost:8000/session/{phone}/status
```

---

## 🏗️ Arquitetura

```
┌─────────────┐
│  WhatsApp   │
└──────┬──────┘
       │
┌──────▼──────────────────────────────────┐
│              n8n                         │
│  (apenas webhook - repassa pro backend)  │
└──────┬───────────────────────────────────┘
       │
┌──────▼──────────────────────────────────┐
│         Backend API (FastAPI)            │
│                                          │
│  ┌────────────────────────────────┐     │
│  │    SessionManager              │     │
│  │  • Detecta interferência       │     │
│  │  • Controla bot vs humano      │     │
│  │  • Processa comandos           │     │
│  └────────────┬───────────────────┘     │
│               │                          │
│  ┌────────────▼───────────────────┐     │
│  │      AI Agent (LangChain)      │     │
│  │  • Busca produtos              │     │
│  │  • Gerencia carrinho           │     │
│  │  • Calcula frete               │     │
│  │  • Gera pagamentos             │     │
│  └────────────────────────────────┘     │
│                                          │
└──────┬───────────────────────────────────┘
       │
┌──────▼──────────────────┬───────────────┐
│      PostgreSQL         │     Redis     │
│  • Produtos             │  • Sessões    │
│  • Pedidos              │  • Cache      │
│  • Clientes             │               │
└─────────────────────────┴───────────────┘
```

### Por que essa arquitetura?

**❌ Antes (só n8n):**
- 100+ nodes
- Lógica espalhada
- Difícil de testar
- Sem versionamento
- Debugging complexo

**✅ Agora (híbrido):**
- Core em código limpo
- Testável e versionado
- n8n só para webhook
- Fácil de escalar
- Logs estruturados

---

## 🚀 Como Usar

### 1. Pré-requisitos

```bash
# Instalar Docker e Docker Compose
docker --version
docker-compose --version

# Clonar/baixar o projeto
cd agente-whatsapp
```

### 2. Configuração

```bash
# Copiar .env de exemplo
cp backend/.env.example backend/.env

# Editar com suas chaves
nano backend/.env
```

Configure:
- `OPENAI_API_KEY` - Sua chave da OpenAI
- `PAGARME_API_KEY` - Chave do Pagar.me
- Outras configurações conforme necessário

### 3. Iniciar Serviços

```bash
# Subir tudo (backend + postgres + redis + n8n)
cd backend
docker-compose up -d

# Ver logs
docker-compose logs -f backend
```

Serviços disponíveis:
- **Backend API**: http://localhost:8000
- **Docs (Swagger)**: http://localhost:8000/docs
- **n8n**: http://localhost:5678 (user: admin, pass: admin123)
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### 4. Importar Workflow n8n

1. Acesse http://localhost:5678
2. Login: `admin` / `admin123`
3. Importe o arquivo: `n8n/webhook_whatsapp_simples.json`
4. Ative o workflow

### 5. Testar

```bash
# Health check
curl http://localhost:8000/

# Simular mensagem do WhatsApp
curl -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "5531999999999",
    "message": "Oi, quero comprar queijo",
    "sender_type": "customer"
  }'

# Ver status da sessão
curl http://localhost:8000/session/5531999999999/status
```

---

## 📱 Exemplos de Uso

### Cenário 1: Atendimento Normal (Bot)

```
Cliente: Oi, quero queijo canastra
Bot: Olá! Temos 3 opções de queijo canastra:
     1. Canastra Tradicional 1kg - R$ 85,00
     2. Canastra Curado 500g - R$ 45,00
     3. Canastra Premiado 1kg - R$ 120,00
     Qual te interessa?

Cliente: O número 1
Bot: Ótimo! Queijo Canastra Tradicional 1kg por R$ 85,00.
     Confirma?

Cliente: Sim
Bot: ✅ Adicionado ao carrinho! Total: R$ 85,00
     Quer mais alguma coisa?
```

### Cenário 2: Humano Assume (Manual)

```
Cliente: Oi, quero fazer um pedido grande
Bot: Olá! Claro, me diz o que precisa...

[Atendente vê e decide assumir]
Atendente envia: /assumir

Cliente: Quero 50kg de queijo
[Bot NÃO responde - humano assumiu]

Atendente: Perfeito! Vou te passar um orçamento...
[Conversa continua com humano]

[Quando terminar]
Atendente envia: /liberar
Bot: ✅ Voltei! Estou aqui se precisar.
```

### Cenário 3: Detecção Automática

```
Cliente: Quanto custa o queijo do Onésio?
Bot: O Queijo do Onésio 1kg custa R$ 125,00

Cliente: Vocês entregam hoje?
[Um vendedor vê e responde manualmente]
Vendedor: [HUMANO] Sim! Entregamos em até 2h na região...

→ Sistema detecta [HUMANO] e PAUSA o bot automaticamente

Cliente: Ótimo, então quero 2kg
Vendedor: Perfeito! Vou gerar o pedido...
[Conversa continua com humano]
```

### Cenário 4: Via API (Dashboard)

```javascript
// No seu dashboard de atendimento

// Listar conversas em andamento
const sessions = await fetch('http://localhost:8000/sessions/active')

// Cliente pede algo complexo? Assumir via dashboard
await fetch(`http://localhost:8000/session/${phone}/takeover`, {
  method: 'POST',
  body: JSON.stringify({ attendant_id: 'maria@empresa.com' })
})

// Quando terminar, liberar de volta
await fetch(`http://localhost:8000/session/${phone}/release`, {
  method: 'POST'
})
```

---

## 🔧 Desenvolvimento

### Estrutura de Pastas

```
agente-whatsapp/
├── backend/
│   ├── src/
│   │   ├── agent/              # Core do agente IA
│   │   │   ├── core.py         # Agente LangChain
│   │   │   ├── tools.py        # Ferramentas do agente
│   │   │   └── prompts.py      # System prompts
│   │   ├── services/
│   │   │   ├── session_manager.py  # 🔥 Controle humano-agente
│   │   │   ├── database.py     # ORM / queries
│   │   │   ├── whatsapp.py     # Cliente WhatsApp
│   │   │   ├── payments.py     # Pagar.me
│   │   │   └── shipping.py     # Cálculo frete
│   │   ├── models/
│   │   │   ├── session.py      # Modelos de sessão
│   │   │   └── ...
│   │   ├── api/
│   │   │   └── main.py         # FastAPI endpoints
│   │   └── utils/
│   ├── tests/                  # Testes unitários
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── requirements.txt
├── n8n/                        # Workflows n8n
│   └── webhook_whatsapp_simples.json
└── docs/                       # Documentação extra
```

### Executar Localmente (sem Docker)

```bash
# Criar virtualenv
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Subir apenas Postgres e Redis
docker-compose up -d postgres redis

# Rodar API
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Testes

```bash
# Rodar testes
pytest

# Com coverage
pytest --cov=src --cov-report=html

# Ver cobertura
open htmlcov/index.html
```

---

## 📊 Endpoints da API

### Webhook

```http
POST /webhook/whatsapp
Content-Type: application/json

{
  "phone": "5531999999999",
  "message": "Oi, quero queijo",
  "sender_type": "customer"
}

→ Retorna:
{
  "should_respond": true,
  "reason": "agent active",
  "response": "Olá! Como posso ajudar?",
  "session_mode": "agent"
}
```

### Controle de Sessão

```http
# Enviar comando
POST /control/command
{
  "phone": "5531999999999",
  "command": "/pausar",
  "attendant_id": "joao@empresa.com"
}

# Ver status
GET /session/{phone}/status

# Assumir conversa
POST /session/{phone}/takeover?attendant_id=maria@empresa.com

# Liberar conversa
POST /session/{phone}/release

# Listar todas sessões ativas
GET /sessions/active?mode=human
```

---

## 🎨 Integração com Dashboard

Você pode criar um dashboard React/Vue que:

1. **Lista conversas em tempo real**
   ```javascript
   const sessions = await fetch('/sessions/active')
   ```

2. **Mostra quem está atendendo cada uma**
   ```javascript
   sessions.forEach(s => {
     console.log(`${s.phone}: ${s.mode} (${s.human_attendant})`)
   })
   ```

3. **Permite assumir com um clique**
   ```javascript
   async function takeOver(phone) {
     await fetch(`/session/${phone}/takeover`, {
       method: 'POST',
       body: JSON.stringify({ attendant_id: currentUser.email })
     })
   }
   ```

4. **Notifica quando cliente pede humano**
   ```javascript
   // WebSocket ou polling
   if (session.metadata.escalation_requested) {
     showNotification("Cliente solicitou atendimento humano!")
   }
   ```

---

## 🔍 Monitoramento

### Logs

```bash
# Ver logs em tempo real
docker-compose logs -f backend

# Logs salvos em
backend/logs/app.log
```

### Métricas

Os logs incluem:
- ✅ Mensagens recebidas
- ✅ Decisões do SessionManager
- ✅ Mudanças de modo (agent↔human)
- ✅ Comandos executados
- ✅ Erros e exceções

### Health Check

```bash
curl http://localhost:8000/
```

---

## 🚀 Deploy em Produção

### Opção 1: VPS (DigitalOcean, AWS EC2, etc)

```bash
# No servidor
git clone seu-repo
cd agente-whatsapp/backend

# Configurar .env
nano .env

# Subir com Docker
docker-compose up -d

# Configurar nginx reverse proxy (opcional)
```

### Opção 2: Kubernetes

```bash
# TODO: Adicionar manifests K8s
```

### Opção 3: Railway / Render

1. Conectar repositório
2. Definir build command: `docker build`
3. Configurar variáveis de ambiente
4. Deploy!

---

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch: `git checkout -b feature/nova-funcionalidade`
3. Commit: `git commit -am 'Adiciona nova funcionalidade'`
4. Push: `git push origin feature/nova-funcionalidade`
5. Pull Request

---

## 📝 To-Do

- [ ] Implementar core do agente com LangChain
- [ ] Adicionar mais tools (buscar_produtos, add_to_cart, etc)
- [ ] Integração com Pagar.me
- [ ] Cálculo de frete (Lalamove/Correios)
- [ ] Supabase Vector Store (RAG)
- [ ] Painel de controle web
- [ ] Testes unitários completos
- [ ] Documentação da API (Swagger melhorado)
- [ ] CI/CD (GitHub Actions)
- [ ] Monitoring (Prometheus/Grafana)

---

## 📄 Licença

MIT License - veja LICENSE para detalhes.

---

## 💬 Suporte

- 📧 Email: dev@rocacapital.com.br
- 📱 WhatsApp: (31) 97266-6900
- 🐛 Issues: GitHub Issues

---

**Feito com ❤️ para Roça Capital**
