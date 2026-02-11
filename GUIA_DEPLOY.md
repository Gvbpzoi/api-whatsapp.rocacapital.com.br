# 🚀 Guia de Deploy - Agente WhatsApp Roça Capital

## 📋 Pré-requisitos

- [x] Conta no Hostinger com EasyPanel configurado
- [x] Repositório GitHub com o código
- [x] Conta Supabase (opcional - sistema funciona com mocks)
- [x] Token do Tiny ERP (opcional - sistema funciona sem)
- [x] N8N configurado e rodando

---

## 🗂️ Passo 1: Preparar Repositório GitHub

### 1.1. Criar arquivos necessários

**Dockerfile** em `backend/Dockerfile`:
```dockerfile
FROM python:3.11-slim

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Configurar diretório de trabalho
WORKDIR /app

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY . .

# Expor porta
EXPOSE 8000

# Comando para iniciar o servidor
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose.yml** na raiz:
```yaml
version: '3.8'

services:
  api:
    build: ./backend
    container_name: agente-whatsapp-api
    ports:
      - "8000:8000"
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
      - TINY_TOKEN=${TINY_TOKEN}
      - N8N_WEBHOOK_URL=${N8N_WEBHOOK_URL}
    volumes:
      - ./goals:/app/goals:ro
      - ./context:/app/context:ro
      - ./hardprompts:/app/hardprompts:ro
      - ./args:/app/args:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**.dockerignore** na raiz:
```
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/
*.log
.env
.venv
venv/
.git/
.gitignore
README.md
*.md
tests/
.pytest_cache/
```

**GitHub Actions** em `.github/workflows/deploy.yml`:
```yaml
name: Deploy to Hostinger

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Build Docker image
        run: |
          cd backend
          docker build -t agente-whatsapp:latest .

      - name: Deploy to Hostinger via SSH
        uses: appleboy/ssh-action@v0.1.10
        with:
          host: ${{ secrets.HOSTINGER_HOST }}
          username: ${{ secrets.HOSTINGER_USER }}
          password: ${{ secrets.HOSTINGER_PASSWORD }}
          script: |
            cd /var/www/agente-whatsapp
            git pull origin main
            docker-compose down
            docker-compose up -d --build
```

### 1.2. Criar arquivo .env.example

**backend/.env.example**:
```env
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Supabase (opcional - sistema funciona com mocks)
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-chave-anon-publica

# Tiny ERP (opcional - sistema funciona sem)
TINY_TOKEN=seu-token-aqui

# N8N Webhook
N8N_WEBHOOK_URL=https://seu-n8n.com/webhook/whatsapp-reply

# Logging
LOG_LEVEL=INFO
```

### 1.3. Atualizar .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
.venv

# Env
.env
.env.local
.env.*.local

# Logs
*.log
logs/
*.sqlite
*.db

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Testing
.pytest_cache/
.coverage
htmlcov/

# Docker
docker-compose.override.yml
```

### 1.4. Commit e push

```bash
git add .
git commit -m "feat: adicionar configuração de deploy"
git push origin main
```

---

## 🖥️ Passo 2: Configurar Hostinger EasyPanel

### 2.1. Acessar EasyPanel

1. Login no painel Hostinger
2. Ir para "VPS" → "Gerenciar"
3. Abrir EasyPanel

### 2.2. Criar novo projeto

1. Clicar em "New Project"
2. Nome: `agente-whatsapp`
3. Tipo: `Docker Compose`

### 2.3. Conectar ao GitHub

1. Em "Source", clicar em "Connect GitHub"
2. Autorizar EasyPanel no GitHub
3. Selecionar repositório `agente-whatsapp`
4. Branch: `main`
5. Path do docker-compose: `/docker-compose.yml`

### 2.4. Configurar variáveis de ambiente

Na aba "Environment":

```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua_chave_anon
TINY_TOKEN=seu_token_tiny
N8N_WEBHOOK_URL=https://seu-n8n.com/webhook/whatsapp-reply
```

### 2.5. Configurar domínio

1. Ir para "Domains"
2. Adicionar domínio: `api-whatsapp.rocacapital.com.br`
3. Ou usar domínio do EasyPanel: `agente-whatsapp.easypanel.host`
4. Certificado SSL automático (Let's Encrypt)

### 2.6. Deploy

1. Clicar em "Deploy"
2. Aguardar build (2-3 minutos)
3. Verificar logs
4. Testar endpoint: `https://api-whatsapp.rocacapital.com.br/`

---

## 🔗 Passo 3: Configurar N8N

### 3.1. Criar workflow de integração

**Nodes necessários:**

1. **Webhook Trigger** (recebe do WhatsApp)
   - HTTP Method: POST
   - Path: `/webhook/whatsapp-incoming`

2. **HTTP Request** (envia para API)
   - Method: POST
   - URL: `https://api-whatsapp.rocacapital.com.br/webhook/whatsapp`
   - Body:
   ```json
   {
     "phone": "{{ $json.phone }}",
     "message": "{{ $json.message }}",
     "sender_type": "customer"
   }
   ```

3. **IF** (verifica se agente deve responder)
   - Condition: `{{ $json.should_respond }} == true`

4. **HTTP Request** (envia resposta para WhatsApp)
   - Method: POST
   - URL: Endpoint da API do WhatsApp
   - Body:
   ```json
   {
     "phone": "{{ $json.phone }}",
     "message": "{{ $json.response }}"
   }
   ```

### 3.2. Configurar webhook do WhatsApp

Apontar webhook do WhatsApp para:
```
https://seu-n8n.com/webhook/whatsapp-incoming
```

---

## 🧪 Passo 4: Testes Pós-Deploy

### 4.1. Health Check

```bash
curl https://api-whatsapp.rocacapital.com.br/
```

Resposta esperada:
```json
{
  "status": "online",
  "service": "agente-whatsapp",
  "version": "1.0.0"
}
```

### 4.2. Teste de webhook

```bash
curl -X POST https://api-whatsapp.rocacapital.com.br/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "5531999999999",
    "message": "Oi, bom dia!",
    "sender_type": "customer"
  }'
```

Resposta esperada:
```json
{
  "should_respond": true,
  "reason": "agent active",
  "response": "Bom dia! ☀️...",
  "session_mode": "agent"
}
```

### 4.3. Teste via WhatsApp

1. Enviar mensagem para número conectado
2. Verificar resposta do agente
3. Testar fluxo completo:
   - Saudação
   - Busca de produto
   - Adicionar carrinho
   - Finalizar pedido

---

## 📊 Passo 5: Monitoramento

### 5.1. Logs no EasyPanel

1. Ir para projeto `agente-whatsapp`
2. Aba "Logs"
3. Ver logs em tempo real
4. Filtrar por nível: INFO, WARNING, ERROR

### 5.2. Métricas

EasyPanel fornece automaticamente:
- CPU usage
- Memory usage
- Network traffic
- Request rate

### 5.3. Alertas

Configurar alertas para:
- Container down
- High memory usage (> 80%)
- Error rate alto (> 5%)

---

## 🔧 Passo 6: Configurações Avançadas

### 6.1. Habilitar Supabase

1. Criar projeto no Supabase
2. Executar SQL do schema:
```sql
-- Ver backend/database/schema.sql
```

3. Obter credenciais:
   - URL: `https://seu-projeto.supabase.co`
   - Anon key: Em Settings → API

4. Atualizar variáveis no EasyPanel:
```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua_chave_anon
```

5. Redeploy

### 6.2. Habilitar Tiny ERP

1. Obter token do Tiny ERP
2. Atualizar variável no EasyPanel:
```env
TINY_TOKEN=seu_token_aqui
```

3. Redeploy

### 6.3. Scaling

Se necessário escalar:

1. No EasyPanel, ir para "Scaling"
2. Aumentar réplicas: 2-3 containers
3. Configurar load balancer automático
4. Memory per container: 512MB-1GB

---

## 🚨 Troubleshooting

### Problema: Container não inicia

**Solução:**
```bash
# Ver logs
docker logs agente-whatsapp-api

# Verificar variáveis de ambiente
docker exec agente-whatsapp-api env

# Reiniciar container
docker-compose restart
```

### Problema: API retorna 500

**Solução:**
1. Verificar logs no EasyPanel
2. Verificar se Goals/Context estão carregados:
   - Ver logs de startup
   - Procurar por "🎯 GOTCHA Engine inicializado"
3. Verificar estrutura de diretórios no container:
```bash
docker exec agente-whatsapp-api ls -la /app/goals
```

### Problema: N8N não recebe resposta

**Solução:**
1. Verificar se webhook está ativo
2. Testar endpoint diretamente (curl)
3. Verificar firewall/CORS
4. Verificar logs do N8N

### Problema: Agente não responde no WhatsApp

**Solução:**
1. Verificar se webhook do WhatsApp está ativo
2. Verificar se N8N está recebendo mensagens
3. Verificar se API está respondendo
4. Verificar SessionManager (modo agent ativo)

---

## 🔄 Atualizações Futuras

### Deploy de nova versão

1. Commit e push para `main`
2. GitHub Actions faz deploy automático
3. Ou manual via EasyPanel: "Redeploy"

### Rollback

1. No EasyPanel, ir para "Deployments"
2. Selecionar versão anterior
3. Clicar em "Rollback"

---

## ✅ Checklist Final

- [ ] Dockerfile criado
- [ ] docker-compose.yml configurado
- [ ] .env.example criado
- [ ] GitHub Actions configurado (opcional)
- [ ] Código commitado e pushed
- [ ] Projeto criado no EasyPanel
- [ ] Repositório GitHub conectado
- [ ] Variáveis de ambiente configuradas
- [ ] Domínio configurado
- [ ] SSL ativado
- [ ] Deploy realizado
- [ ] Health check OK
- [ ] Teste de webhook OK
- [ ] N8N integrado
- [ ] Teste via WhatsApp OK
- [ ] Logs monitorados
- [ ] Alertas configurados

---

## 📞 Suporte

**Documentação:**
- [Hostinger EasyPanel Docs](https://easypanel.io/docs)
- [Docker Docs](https://docs.docker.com/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)

**Logs importantes:**
- Startup: "🚀 Iniciando Agente WhatsApp API..."
- GOTCHA: "🎯 GOTCHA Engine inicializado"
- Tools: "🔧 Tools Helper inicializado"

**Endpoints úteis:**
- Health: `GET /`
- Sessions: `GET /sessions/active`
- Status: `GET /session/{phone}/status`

---

## 🎉 Conclusão

Seguindo este guia, o sistema estará:
- ✅ Rodando em produção no Hostinger
- ✅ Integrado com N8N e WhatsApp
- ✅ Monitorado e com logs
- ✅ Pronto para escalar conforme necessidade
- ✅ Atualizado automaticamente via GitHub

**Boa sorte com o deploy! 🚀**
