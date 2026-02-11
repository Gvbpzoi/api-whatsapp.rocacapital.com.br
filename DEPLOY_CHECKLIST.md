# ✅ Checklist de Deploy - Agente WhatsApp Roça Capital

**Data:** 11/02/2026
**Versão:** 2.0.0
**Destino:** Hostinger + EasyPanel + GitHub CI/CD

---

## 📋 Pré-Deploy (Configurações)

### 1. Supabase

- [ ] Criar projeto no Supabase
- [ ] Executar schema: `backend/scripts/supabase_schema.sql`
- [ ] Copiar `SUPABASE_URL` e `SUPABASE_KEY`
- [ ] Testar conexão: `psql $DATABASE_URL -c "\dt"`
- [ ] Verificar tabelas criadas (7 tabelas)

### 2. Tiny ERP

**V3 (OAuth):**
- [ ] Acessar https://erp.tiny.com.br/
- [ ] Criar aplicação OAuth
- [ ] Copiar `CLIENT_ID` e `CLIENT_SECRET`
- [ ] Gerar `ACCESS_TOKEN` e `REFRESH_TOKEN`

**V2 (Fallback):**
- [ ] Gerar token V2 em: https://www.tiny.com.br/ajuda/api/api2
- [ ] Copiar `TINY_V2_TOKEN`

**Testar:**
- [ ] Listar produtos (V3)
- [ ] Criar pedido de teste (V2)

### 3. OpenAI

- [ ] Criar conta em https://platform.openai.com
- [ ] Gerar API key
- [ ] Copiar `OPENAI_API_KEY`
- [ ] Verificar créditos disponíveis

### 4. Pagar.me

- [ ] Criar conta em https://pagar.me
- [ ] Gerar `PAGARME_API_KEY`
- [ ] Gerar `PAGARME_SECRET_KEY`
- [ ] Configurar webhook de pagamento

### 5. GitHub

- [ ] Criar repositório: `agente-whatsapp`
- [ ] Fazer primeiro commit
- [ ] Configurar GitHub Container Registry (GHCR)

---

## 🔑 Secrets do GitHub

Ir em: **Settings → Secrets and variables → Actions**

- [ ] `HOSTINGER_HOST` = IP ou domínio do servidor
- [ ] `HOSTINGER_USER` = root (ou seu usuário SSH)
- [ ] `HOSTINGER_SSH_KEY` = Chave privada SSH
- [ ] `HOSTINGER_PORT` = 22 (ou porta SSH customizada)
- [ ] `DOCKER_REGISTRY` = ghcr.io/seu-usuario
- [ ] `DOCKER_USERNAME` = seu-usuario-github
- [ ] `DOCKER_PASSWORD` = GitHub Personal Access Token

**Gerar chave SSH:**
```bash
ssh-keygen -t ed25519 -C "github-actions"
ssh-copy-id root@seu-servidor.hostinger.com
cat ~/.ssh/id_ed25519  # Copiar para HOSTINGER_SSH_KEY
```

---

## 🖥️ Servidor Hostinger

### 1. Acessar VPS

```bash
ssh root@seu-servidor.hostinger.com
```

### 2. Atualizar Sistema

```bash
apt update && apt upgrade -y
```

### 3. Instalar EasyPanel

```bash
curl -sSL https://get.easypanel.io | sh
```

- [ ] Aguardar instalação (2-3 min)
- [ ] Acessar: https://seu-ip:3000
- [ ] Criar conta admin
- [ ] Configurar domínio (opcional)

### 4. Instalar Dependências

```bash
apt install -y docker.io docker-compose git
systemctl enable docker
systemctl start docker
```

### 5. Clonar Repositório

```bash
mkdir -p /var/www
cd /var/www
git clone https://github.com/seu-usuario/agente-whatsapp.git
cd agente-whatsapp
```

### 6. Configurar .env

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

**Preencher TODAS as variáveis:**
- Supabase (URL + Key)
- Tiny V3 (OAuth)
- Tiny V2 (Token)
- OpenAI (API Key)
- Pagar.me (Keys)
- n8n (opcional)

### 7. Testar Local

```bash
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
docker-compose logs -f backend
```

- [ ] Backend iniciou sem erros
- [ ] Health check: `curl http://localhost:8000/`
- [ ] Ver logs: sem erros críticos

```bash
docker-compose down
```

---

## 🚀 Deploy Automático (CI/CD)

### 1. Fazer Primeiro Deploy

```bash
git add .
git commit -m "feat: configuração inicial"
git push origin main
```

### 2. Acompanhar GitHub Actions

- [ ] Ir em: **Actions** no GitHub
- [ ] Ver workflow rodando
- [ ] Aguardar conclusão (~5 min)

**Etapas do workflow:**
1. ✅ Build da imagem Docker
2. ✅ Push para GHCR
3. ✅ SSH para Hostinger
4. ✅ Pull da imagem
5. ✅ Restart dos containers
6. ✅ Health check

### 3. Verificar Deploy

```bash
# No servidor
docker ps
docker-compose logs -f backend

# Testar API
curl https://api.seudominio.com/
```

---

## 🌐 Domínio e SSL

### Opção A: Via EasyPanel (Recomendado)

1. Acessar EasyPanel: https://seu-ip:3000
2. Ir em: App Settings → Domains
3. Adicionar: `api.seudominio.com`
4. Ativar SSL (Let's Encrypt automático)

### Opção B: Via Nginx Manual

```bash
# Instalar Nginx
apt install -y nginx certbot python3-certbot-nginx

# Configurar
nano /etc/nginx/sites-available/agente-whatsapp
```

```nginx
server {
    listen 80;
    server_name api.seudominio.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Ativar
ln -s /etc/nginx/sites-available/agente-whatsapp /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# SSL
certbot --nginx -d api.seudominio.com
```

- [ ] Domínio apontando para servidor
- [ ] SSL ativado (HTTPS)
- [ ] `https://api.seudominio.com/` funcionando

---

## 🔧 n8n (Workflows)

### 1. Importar Workflows

```bash
cd n8n
# Importar webhook_whatsapp_simples.json no n8n
```

### 2. Configurar Webhooks

**Workflow 1: Sync Status Pedidos**
- Trigger: Schedule (Every 5 minutes)
- HTTP Request: `POST https://api.seudominio.com/api/sync/orders-status`

**Workflow 2: Sync Produtos**
- Trigger: Schedule (Daily at 6am)
- HTTP Request: `POST https://api.seudominio.com/api/sync/products`

- [ ] Workflows importados
- [ ] Webhooks testados
- [ ] Primeira sincronização OK

---

## 📊 Primeira Sincronização

### 1. Sincronizar Produtos

```bash
# Via API
curl -X POST https://api.seudominio.com/api/sync/products

# Ou via Python
python backend/scripts/test_tiny_sync.py
```

- [ ] Produtos importados do Tiny
- [ ] Verificar no Supabase: `SELECT COUNT(*) FROM produtos;`

### 2. Testar Criação de Pedido

```bash
# Via API
curl -X POST https://api.seudominio.com/api/orders \
  -H "Content-Type: application/json" \
  -d @backend/tests/fixtures/pedido_teste.json
```

- [ ] Pedido criado no Supabase
- [ ] Pedido enviado para Tiny
- [ ] `tiny_pedido_id` preenchido

---

## ✅ Testes Finais

### 1. Fluxo Completo WhatsApp

- [ ] Cliente: "Quero queijo canastra"
- [ ] Bot busca produtos (Supabase)
- [ ] Cliente adiciona ao carrinho
- [ ] Cliente finaliza pedido
- [ ] Bot gera PIX/Cartão
- [ ] Pedido criado no Tiny
- [ ] Cliente recebe confirmação

### 2. Consulta de Pedido

- [ ] Cliente: "Cadê meu pedido?"
- [ ] Bot busca no Supabase (rápido!)
- [ ] Exibe status + rastreio

### 3. Controle Humano-Agente

- [ ] Você envia: `/assumir`
- [ ] Bot pausa
- [ ] Você responde cliente
- [ ] Você envia: `/liberar`
- [ ] Bot retoma

### 4. Auto-Resume

- [ ] Você assume conversa
- [ ] Aguarda 5 minutos sem responder
- [ ] Bot retoma automaticamente

---

## 📈 Monitoramento

### 1. Logs

```bash
# Backend
docker-compose logs -f backend

# Todos
docker-compose logs -f

# Filtrar erros
docker-compose logs | grep ERROR
```

### 2. Health Check

```bash
curl https://api.seudominio.com/
```

### 3. Estatísticas (Supabase)

```sql
-- Pedidos hoje
SELECT canal, COUNT(*), SUM(total)
FROM pedidos
WHERE DATE(criado_em) = CURRENT_DATE
GROUP BY canal;

-- Taxa de sync
SELECT
  COUNT(CASE WHEN tiny_sincronizado THEN 1 END) * 100.0 / COUNT(*) as taxa
FROM pedidos;
```

### 4. Uptime Robot (Opcional)

- [ ] Criar conta: https://uptimerobot.com
- [ ] Adicionar monitor: `https://api.seudominio.com/`
- [ ] Receber alertas por email

---

## 🐛 Troubleshooting Comum

### Container não inicia

```bash
docker-compose logs backend
docker-compose config
docker-compose restart backend
```

### Erro de memória

```yaml
# Aumentar em docker-compose.prod.yml
deploy:
  resources:
    limits:
      memory: 2G
```

### SSL não funciona

```bash
certbot --nginx -d api.seudominio.com --force-renewal
nginx -t
systemctl restart nginx
```

### GitHub Actions falha

- [ ] Verificar secrets configurados
- [ ] Testar SSH manualmente: `ssh root@servidor`
- [ ] Ver logs no GitHub Actions

---

## 🔄 Manutenção

### Atualizar Sistema

```bash
cd /var/www/agente-whatsapp
git pull origin main
docker-compose -f docker-compose.prod.yml up -d --build
```

### Backup

```bash
# Redis
docker exec agente-whatsapp-redis redis-cli SAVE
docker cp agente-whatsapp-redis:/data/dump.rdb ./backup/

# Supabase (via dashboard)
# Database → Backups → Download
```

### Rollback

```bash
git log
git checkout <commit-anterior>
docker-compose -f docker-compose.prod.yml up -d --build
```

---

## 🎉 Deploy Completo!

Seu agente está rodando em:
- 🌐 API: `https://api.seudominio.com`
- 📚 Docs: `https://api.seudominio.com/docs`
- 🔧 n8n: `https://n8n.seudominio.com` (se configurado)

**Próximos passos:**
1. ✅ Monitorar logs por 24h
2. ✅ Criar pedidos de teste
3. ✅ Treinar equipe no controle humano-agente
4. ✅ Configurar alertas de uptime
5. ✅ Documentar fluxos específicos da Roça Capital

---

**Desenvolvido com ❤️ por:** Claude + Guilherme Vieira
**Data:** 11/02/2026
**Versão:** 2.0.0

**Sistema profissional, escalável e pronto para produção!** 🚀
