# 🚀 Deploy no EasyPanel - Agente WhatsApp

## 📋 Como Adicionar no App "gestor-roca-capital" Existente

### **Opção 1: Adicionar como Serviço no Projeto Existente** (Recomendado)

#### Passo 1: Acessar o Projeto no EasyPanel

1. Login no EasyPanel do Hostinger
2. Abrir projeto **"gestor-roca-capital"**
3. Clicar na aba **"Services"**

#### Passo 2: Adicionar Novo Serviço

1. Clicar em **"Add Service"** ou **"+"**
2. Selecionar **"GitHub"** como source
3. Configurar:
   - **Name:** `agente-whatsapp`
   - **Repository:** `Gvbpzoi/api-whatsapp.rocacapital.com.br`
   - **Branch:** `main`
   - **Build Type:** `Docker Compose`
   - **Compose File:** `/docker-compose.yml`

#### Passo 3: Configurar Variáveis de Ambiente

Adicionar as seguintes variáveis (provavelmente já existem no projeto):

```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua_chave_anon_key
TINY_TOKEN=seu_token_tiny
N8N_WEBHOOK_URL=https://seu-n8n.com/webhook/whatsapp-reply
LOG_LEVEL=INFO
```

**Nota:** Como você já tem o gestor usando o mesmo Supabase, essas variáveis provavelmente já estão configuradas no projeto. O EasyPanel compartilha variáveis entre serviços do mesmo projeto.

#### Passo 4: Configurar Domínio

1. Na aba **"Domains"** do serviço `agente-whatsapp`
2. Adicionar domínio:
   - **Domínio customizado:** `api-whatsapp.rocacapital.com.br`
   - **OU usar subdomínio do EasyPanel:** `agente-whatsapp.easypanel.host`
3. SSL automático (Let's Encrypt)

#### Passo 5: Deploy

1. Clicar em **"Deploy"**
2. Aguardar build (2-3 minutos)
3. Verificar logs para confirmar inicialização:
   ```
   🚀 Iniciando Agente WhatsApp API...
   🎯 GOTCHA Engine inicializado: <GOTCHAEngine goals=7 context=3 args=2>
   🧠 Intent Classifier inicializado
   🔧 Tools Helper inicializado
   ```

---

### **Opção 2: Criar Projeto Separado** (Alternativa)

Se preferir isolamento total, pode criar um novo projeto:

1. No EasyPanel, clicar em **"New Project"**
2. Nome: `agente-whatsapp` ou `whatsapp-bot`
3. Seguir mesmos passos de configuração acima
4. **Importante:** Precisará duplicar as variáveis de ambiente (Supabase, Tiny)

---

## 🔧 Estrutura Final no EasyPanel

### Opção 1 - Serviços no Mesmo Projeto:

```
📦 gestor-roca-capital (Projeto)
  ├── 🟢 gestor-rca (Serviço existente)
  │   └── http://gestor.rocacapital.com.br
  │
  └── 🟢 agente-whatsapp (Novo serviço)
      └── http://api-whatsapp.rocacapital.com.br
```

**Vantagens:**
- ✅ Variáveis de ambiente compartilhadas
- ✅ Gestão centralizada
- ✅ Mesma rede (comunicação interna facilitada)
- ✅ Mais econômico

### Opção 2 - Projetos Separados:

```
📦 gestor-roca-capital (Projeto 1)
  └── 🟢 gestor-rca

📦 agente-whatsapp (Projeto 2)
  └── 🟢 api
```

---

## 🧪 Testes Pós-Deploy

### 1. Health Check

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

### 2. Teste de Webhook

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

### 3. Verificar Logs no EasyPanel

1. Ir para serviço `agente-whatsapp`
2. Aba **"Logs"**
3. Procurar por:
   - ✅ `🚀 Iniciando Agente WhatsApp API...`
   - ✅ `🎯 GOTCHA Engine inicializado`
   - ✅ `🧠 Intent Classifier inicializado`
   - ✅ `🔧 Tools Helper inicializado`

---

## 🔗 Integração com N8N

### Atualizar Workflow N8N

**Node 1: Webhook (recebe do WhatsApp)**
```
URL: https://seu-n8n.com/webhook/whatsapp-incoming
Method: POST
```

**Node 2: HTTP Request (chama API do agente)**
```
URL: https://api-whatsapp.rocacapital.com.br/webhook/whatsapp
Method: POST
Body (JSON):
{
  "phone": "{{ $json.phone }}",
  "message": "{{ $json.message }}",
  "sender_type": "customer"
}
```

**Node 3: IF (verifica resposta)**
```
Condition: {{ $json.should_respond }} == true
```

**Node 4: HTTP Request (envia para WhatsApp)**
```
URL: [API do WhatsApp]
Method: POST
Body:
{
  "phone": "{{ $json.phone }}",
  "message": "{{ $json.response }}"
}
```

---

## 📊 Monitoramento

### Métricas Disponíveis no EasyPanel:

1. **Status do Serviço**
   - Container running/stopped
   - Health check status

2. **Performance**
   - CPU usage
   - Memory usage
   - Network traffic

3. **Logs em Tempo Real**
   - INFO: Operações normais
   - WARNING: Problemas não críticos
   - ERROR: Falhas que precisam atenção

### Configurar Alertas (Opcional)

No EasyPanel, você pode configurar alertas para:
- ❌ Container down
- ⚠️ High memory (> 80%)
- ⚠️ High error rate

---

## 🚨 Troubleshooting

### Container não inicia

**Solução:**
1. Verificar logs no EasyPanel
2. Procurar por erros de inicialização
3. Verificar se Goals/Context/Args foram carregados

### API retorna 500

**Possíveis causas:**
- Variáveis de ambiente faltando
- Goals/Context não encontrados
- Erro na inicialização do GOTCHA Engine

**Verificar:**
```bash
# Ver logs do container
docker logs agente-whatsapp-api

# Verificar estrutura de diretórios
docker exec agente-whatsapp-api ls -la /app/
```

### N8N não recebe resposta

**Verificar:**
1. Webhook do N8N está ativo
2. API está respondendo (teste com curl)
3. Firewall/CORS configurado
4. URL correta no N8N

---

## 🔄 Atualizações

### Deploy Manual

1. Fazer commit e push no GitHub
2. No EasyPanel, ir para serviço `agente-whatsapp`
3. Clicar em **"Redeploy"**

### Deploy Automático (CI/CD)

O EasyPanel pode detectar pushes no GitHub automaticamente:

1. No serviço, aba **"Settings"**
2. Habilitar **"Auto Deploy"**
3. Selecionar branch: `main`

**Agora:** Qualquer push para `main` faz deploy automático! 🎉

---

## ✅ Checklist Final

- [ ] Serviço adicionado no EasyPanel
- [ ] Repositório GitHub conectado
- [ ] Variáveis de ambiente configuradas
- [ ] Domínio configurado e SSL ativo
- [ ] Deploy realizado com sucesso
- [ ] Health check OK (`GET /`)
- [ ] Teste de webhook OK
- [ ] N8N integrado e testado
- [ ] Logs monitorados
- [ ] Auto-deploy habilitado (opcional)

---

## 📞 Endpoints Úteis

```
# Health Check
GET https://api-whatsapp.rocacapital.com.br/

# Webhook Principal
POST https://api-whatsapp.rocacapital.com.br/webhook/whatsapp

# Sessões Ativas
GET https://api-whatsapp.rocacapital.com.br/sessions/active

# Status de Sessão
GET https://api-whatsapp.rocacapital.com.br/session/{phone}/status

# Human Takeover
POST https://api-whatsapp.rocacapital.com.br/session/{phone}/takeover
POST https://api-whatsapp.rocacapital.com.br/session/{phone}/release
```

---

## 🎉 Pronto!

Seu agente WhatsApp agora está rodando no EasyPanel junto com o gestor, compartilhando as mesmas configurações e infraestrutura! 🚀

**Próximo passo:** Integrar com N8N e testar via WhatsApp real!
