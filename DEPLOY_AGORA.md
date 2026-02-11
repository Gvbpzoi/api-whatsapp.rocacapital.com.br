# 🚀 Deploy AGORA - Checklist Prático

**Repositório:** https://github.com/Gvbpzoi/api-whatsapp.rocacapital.com.br ✅
**Status:** Código commitado e pronto para deploy!

---

## ⚡ Passos no EasyPanel (5 minutos)

### 1️⃣ Acessar Projeto Existente

1. Login no **Hostinger**
2. Abrir **EasyPanel**
3. Selecionar projeto **"gestor-roca-capital"**

---

### 2️⃣ Adicionar Novo Serviço

1. Clicar em **"Add Service"** (ou botão **"+"**)
2. Escolher **"GitHub"**

**Preencher:**
```
Name: agente-whatsapp
Repository: Gvbpzoi/api-whatsapp.rocacapital.com.br
Branch: main
Build Type: Docker Compose
Compose File Path: /docker-compose.yml
```

---

### 3️⃣ Configurar Variáveis de Ambiente

**Importante:** Provavelmente já existem no projeto (compartilhadas com gestor)!

Se não existirem, adicionar:

```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua_chave_anon
TINY_TOKEN=seu_token_tiny
N8N_WEBHOOK_URL=https://seu-n8n.com/webhook/whatsapp-reply
LOG_LEVEL=INFO
```

---

### 4️⃣ Configurar Domínio

**Opção A - Domínio Customizado:**
- Domínio: `api-whatsapp.rocacapital.com.br`
- SSL: Automático (Let's Encrypt)

**Opção B - Usar Subdomínio EasyPanel:**
- `agente-whatsapp.easypanel.host`
- SSL: Automático

---

### 5️⃣ Deploy!

1. Clicar em **"Deploy"**
2. Aguardar **2-3 minutos** (build do Docker)
3. ✅ Pronto!

---

## ✅ Verificar se Funcionou

### Teste 1: Health Check

```bash
curl https://api-whatsapp.rocacapital.com.br/
```

**Resposta esperada:**
```json
{
  "status": "online",
  "service": "agente-whatsapp",
  "version": "1.0.0"
}
```

### Teste 2: Ver Logs

No EasyPanel:
1. Ir para serviço `agente-whatsapp`
2. Aba **"Logs"**
3. Procurar por:
   ```
   🚀 Iniciando Agente WhatsApp API...
   🎯 GOTCHA Engine inicializado: <GOTCHAEngine goals=7 context=3 args=2>
   🧠 Intent Classifier inicializado
   🔧 Tools Helper inicializado
   ```

### Teste 3: Webhook

```bash
curl -X POST https://api-whatsapp.rocacapital.com.br/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "5531999999999",
    "message": "Oi, bom dia!",
    "sender_type": "customer"
  }'
```

**Resposta esperada:**
```json
{
  "should_respond": true,
  "reason": "agent active",
  "response": "Bom dia! ☀️...",
  "session_mode": "agent"
}
```

---

## 🔗 Próximo Passo: Integrar com N8N

### Atualizar Workflow N8N

**Node: HTTP Request (chama agente)**
```
URL: https://api-whatsapp.rocacapital.com.br/webhook/whatsapp
Method: POST
Body:
{
  "phone": "{{ $json.phone }}",
  "message": "{{ $json.message }}",
  "sender_type": "customer"
}
```

---

## 🎯 Estrutura Final

```
📦 gestor-roca-capital (Projeto)
  │
  ├── 🟢 gestor-rca (Serviço existente)
  │   └── http://gestor.rocacapital.com.br
  │
  └── 🟢 agente-whatsapp (Novo serviço) ← VOCÊ ESTÁ AQUI
      └── http://api-whatsapp.rocacapital.com.br
```

**Vantagens dessa estrutura:**
- ✅ Variáveis compartilhadas (Supabase, Tiny)
- ✅ Gestão centralizada
- ✅ Mais econômico
- ✅ Mesma rede interna

---

## 🚨 Problemas Comuns

### Container não inicia
**Verificar:**
- Logs no EasyPanel
- Variáveis de ambiente configuradas
- Build do Docker concluído

### API retorna 404
**Verificar:**
- Domínio configurado corretamente
- SSL ativo
- Container rodando (status verde)

### GOTCHA não inicializa
**Verificar logs para:**
- Goals carregados (7)
- Context carregado (3)
- Args carregados (2)

**Se falhar:** Verificar se volumes estão montados corretamente no docker-compose.yml

---

## ✅ Checklist Final

- [ ] Serviço `agente-whatsapp` criado no EasyPanel
- [ ] Repositório GitHub conectado
- [ ] Branch `main` selecionada
- [ ] Docker Compose configurado (`/docker-compose.yml`)
- [ ] Variáveis de ambiente verificadas
- [ ] Domínio configurado
- [ ] Deploy iniciado
- [ ] Logs mostram inicialização OK
- [ ] Health check responde (teste com curl)
- [ ] Webhook funciona (teste com curl)
- [ ] N8N atualizado com nova URL
- [ ] Teste via WhatsApp real

---

## 📞 Endpoints da API

```bash
# Health Check
GET https://api-whatsapp.rocacapital.com.br/

# Webhook Principal
POST https://api-whatsapp.rocacapital.com.br/webhook/whatsapp

# Sessões Ativas
GET https://api-whatsapp.rocacapital.com.br/sessions/active

# Status de Sessão
GET https://api-whatsapp.rocacapital.com.br/session/5531999999999/status

# Human Takeover
POST https://api-whatsapp.rocacapital.com.br/session/5531999999999/takeover?attendant_id=joao@empresa.com

# Liberar para Agente
POST https://api-whatsapp.rocacapital.com.br/session/5531999999999/release
```

---

## 🎉 Pronto!

Depois que o deploy terminar, seu agente WhatsApp estará:
- ✅ Rodando 24/7 no Hostinger
- ✅ Com arquitetura GOTCHA completa
- ✅ Integrado com seu Supabase
- ✅ Pronto para atender clientes
- ✅ Com Human-in-the-Loop ativo

**Qualquer dúvida, consultar:**
- `DEPLOY_EASYPANEL.md` - Guia detalhado
- `IMPLEMENTACAO_GOTCHA.md` - Arquitetura técnica
- `README.md` - Visão geral

---

**Boa sorte com o deploy! 🚀**
