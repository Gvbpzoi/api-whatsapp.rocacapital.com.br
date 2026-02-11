```markdown
# 🚀 Deploy no Hostinger usando EasyPanel + GitHub CI/CD

Guia completo para fazer deploy do agente WhatsApp no Hostinger.

---

## 📋 Pré-requisitos

### 1. Contas Necessárias

- ✅ **Hostinger** com VPS/Cloud
- ✅ **GitHub** (para CI/CD)
- ✅ **Supabase** (banco de dados)
- ✅ **Tiny ERP** (OAuth configurado)
- ✅ **Pagar.me** (pagamentos)
- ✅ **OpenAI** (GPT-4)

### 2. Requisitos do Servidor

**Mínimo recomendado:**
- 2 CPU cores
- 2 GB RAM
- 20 GB SSD
- Ubuntu 22.04 LTS

---

## 🏗️ Parte 1: Configuração Inicial do Servidor

### 1.1 Acessar VPS Hostinger

```bash
# SSH para seu servidor
ssh root@seu-servidor.hostinger.com

# Atualizar sistema
apt update && apt upgrade -y
```

### 1.2 Instalar EasyPanel

```bash
# Instalar EasyPanel (interface visual para Docker)
curl -sSL https://get.easypanel.io | sh

# Aguardar instalação (2-3 minutos)
# Acessar: https://seu-servidor-ip:3000
```

**Configurar EasyPanel:**
1. Criar conta admin
2. Configurar domínio (opcional)
3. Ativar SSL (Let's Encrypt)

### 1.3 Instalar Dependências

```bash
# Docker e Docker Compose (se não instalado pelo EasyPanel)
apt install -y docker.io docker-compose git

# Habilitar Docker
systemctl enable docker
systemctl start docker
```

---

## 🔧 Parte 2: Configuração do Projeto

### 2.1 Clonar Repositório

```bash
# Criar diretório
mkdir -p /var/www
cd /var/www

# Clonar repo
git clone https://github.com/seu-usuario/agente-whatsapp.git
cd agente-whatsapp
```

### 2.2 Configurar Variáveis de Ambiente

```bash
# Criar arquivo .env
cp .env.example .env
nano .env
```

**Configurar `.env`:**

```bash
# ==== SUPABASE ====
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-chave-aqui

# ==== TINY ERP V3 (OAuth) ====
TINY_CLIENT_ID=seu-client-id
TINY_CLIENT_SECRET=seu-secret
TINY_ACCESS_TOKEN=seu-access-token
TINY_REFRESH_TOKEN=seu-refresh-token

# ==== TINY ERP V2 (Fallback) ====
TINY_V2_TOKEN=9f7e446bd44a35cd735b143c4682dc9a6c321be78ade1fa362fe977280daf0bc

# ==== OPENAI ====
OPENAI_API_KEY=sk-seu-key-aqui

# ==== PAGAR.ME ====
PAGARME_API_KEY=sua-key
PAGARME_SECRET_KEY=seu-secret

# ==== n8n (opcional) ====
N8N_PORT=5678
N8N_USER=admin
N8N_PASSWORD=sua-senha-forte
N8N_HOST=n8n.seudominio.com

# ==== CONFIG ====
API_PORT=8000
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### 2.3 Executar Schema do Supabase

```bash
# Instalar Supabase CLI (opcional)
npm install -g supabase

# Ou executar SQL manualmente no dashboard Supabase
cat backend/scripts/supabase_schema.sql
# ↑ Copiar e executar no SQL Editor do Supabase
```

---

## 🐳 Parte 3: Deploy com Docker

### 3.1 Build Local (Teste)

```bash
# Testar build
docker-compose -f docker-compose.prod.yml build

# Testar execução
docker-compose -f docker-compose.prod.yml up -d

# Ver logs
docker-compose logs -f backend

# Se tudo OK, parar
docker-compose down
```

### 3.2 Deploy via EasyPanel

**Opção A: Via Interface EasyPanel**

1. Acesse EasyPanel: `https://seu-servidor-ip:3000`
2. Clicar "New App" → "From Docker Compose"
3. Upload `docker-compose.prod.yml`
4. Configurar variáveis de ambiente
5. Deploy!

**Opção B: Via Command Line**

```bash
# Subir produção
docker-compose -f docker-compose.prod.yml up -d

# Verificar status
docker ps

# Ver logs
docker-compose -f docker-compose.prod.yml logs -f
```

### 3.3 Configurar Domínio e SSL

**No EasyPanel:**
1. App Settings → Domains
2. Adicionar domínio: `api.seudominio.com`
3. Ativar SSL (Let's Encrypt automático)

**Ou via Nginx manual:**

```nginx
# /etc/nginx/sites-available/agente-whatsapp
server {
    listen 80;
    server_name api.seudominio.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Ativar
ln -s /etc/nginx/sites-available/agente-whatsapp /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# SSL com certbot
certbot --nginx -d api.seudominio.com
```

---

## 🔄 Parte 4: CI/CD com GitHub Actions

### 4.1 Configurar Secrets no GitHub

1. Ir no seu repo GitHub
2. Settings → Secrets and variables → Actions
3. Adicionar secrets:

| Secret Name | Valor |
|-------------|-------|
| `HOSTINGER_HOST` | IP ou domínio do servidor |
| `HOSTINGER_USER` | Usuário SSH (geralmente `root`) |
| `HOSTINGER_SSH_KEY` | Chave privada SSH |
| `HOSTINGER_PORT` | Porta SSH (padrão: 22) |

**Gerar chave SSH (se não tiver):**

```bash
# No seu computador
ssh-keygen -t ed25519 -C "github-actions"

# Copiar chave pública para servidor
ssh-copy-id root@seu-servidor.hostinger.com

# Copiar chave PRIVADA para GitHub Secret
cat ~/.ssh/id_ed25519
# ↑ Colar em HOSTINGER_SSH_KEY
```

### 4.2 Habilitar GitHub Container Registry

```bash
# Fazer login (local)
echo $GITHUB_TOKEN | docker login ghcr.io -u seu-usuario --password-stdin

# No servidor
echo $GITHUB_TOKEN | docker login ghcr.io -u seu-usuario --password-stdin
```

### 4.3 Testar CI/CD

```bash
# Fazer um commit
git add .
git commit -m "Test: deploy automático"
git push origin main

# Acompanhar no GitHub
# Ir em: Actions → Ver workflow rodando
```

**Fluxo automático:**
1. ✅ Build da imagem Docker
2. ✅ Push para GitHub Container Registry
3. ✅ SSH para servidor Hostinger
4. ✅ Pull nova imagem
5. ✅ Restart containers
6. ✅ Health check
7. ✅ Notificação (opcional)

---

## 📊 Parte 5: Monitoramento e Logs

### 5.1 Ver Logs

```bash
# Logs do backend
docker-compose logs -f backend

# Logs do Redis
docker-compose logs -f redis

# Logs de todos
docker-compose logs -f

# Filtrar por erro
docker-compose logs | grep ERROR
```

### 5.2 Monitoramento de Recursos

```bash
# Ver uso de CPU/RAM
docker stats

# Ver containers rodando
docker ps

# Ver saúde dos containers
docker-compose ps
```

### 5.3 Configurar Alertas (Opcional)

**Via EasyPanel:**
- Dashboard → Monitoring
- Configurar alertas de CPU/RAM/Disco

**Via Uptime Robot (grátis):**
1. Criar conta em https://uptimerobot.com
2. Adicionar monitor HTTP: `https://api.seudominio.com/`
3. Receber alertas por email se cair

---

## 🔧 Parte 6: Manutenção

### 6.1 Atualizar Sistema

```bash
# Pull última versão
cd /var/www/agente-whatsapp
git pull origin main

# Rebuild e restart
docker-compose -f docker-compose.prod.yml up -d --build
```

### 6.2 Backup

```bash
# Backup do Redis
docker exec agente-whatsapp-redis redis-cli SAVE
docker cp agente-whatsapp-redis:/data/dump.rdb ./backup/

# Backup logs
tar -czf backup/logs-$(date +%Y%m%d).tar.gz backend/logs/

# Backup Supabase (via dashboard)
# Database → Backups → Download
```

### 6.3 Rollback em Caso de Erro

```bash
# Voltar para versão anterior
git log  # Ver commits
git checkout <commit-anterior>

# Rebuild
docker-compose -f docker-compose.prod.yml up -d --build

# Ou usar imagem Docker anterior
docker pull ghcr.io/seu-usuario/agente-whatsapp:<tag-anterior>
```

---

## 🐛 Troubleshooting

### Problema: Container não inicia

```bash
# Ver logs detalhados
docker-compose logs backend

# Verificar configuração
docker-compose config

# Reiniciar
docker-compose restart backend
```

### Problema: Erro de memória

```bash
# Aumentar limite no docker-compose.prod.yml
deploy:
  resources:
    limits:
      memory: 2G  # ← Aumentar aqui

# Ou upgrade do plano Hostinger
```

### Problema: SSL não funciona

```bash
# Reinstalar certificado
certbot --nginx -d api.seudominio.com --force-renewal

# Verificar Nginx
nginx -t
systemctl restart nginx
```

### Problema: GitHub Actions falha

```bash
# Verificar secrets configurados
# Testar SSH manualmente
ssh root@seu-servidor.hostinger.com

# Ver logs do workflow no GitHub Actions
```

---

## ✅ Checklist de Deploy

- [ ] Servidor Hostinger configurado
- [ ] EasyPanel instalado
- [ ] Docker e Docker Compose funcionando
- [ ] Repositório clonado
- [ ] `.env` configurado
- [ ] Supabase schema executado
- [ ] Tiny OAuth configurado
- [ ] Build Docker funcionando
- [ ] Domínio apontando para servidor
- [ ] SSL ativado (HTTPS)
- [ ] GitHub Secrets configurados
- [ ] CI/CD testado (1º deploy)
- [ ] Health check passando
- [ ] Logs sendo gerados
- [ ] Backup configurado
- [ ] Monitoramento ativo

---

## 📞 Suporte

**Problemas com Hostinger:**
- https://www.hostinger.com.br/ajuda

**Problemas com EasyPanel:**
- https://easypanel.io/docs

**Problemas com o projeto:**
- Ver logs: `docker-compose logs -f`
- GitHub Issues

---

## 🎉 Deploy Completo!

Seu agente WhatsApp está rodando em:
- 🌐 API: `https://api.seudominio.com`
- 📚 Docs: `https://api.seudominio.com/docs`
- 🔧 n8n: `https://n8n.seudominio.com` (se configurado)

**Próximos passos:**
1. ✅ Testar endpoints
2. ✅ Configurar n8n workflows
3. ✅ Sincronizar produtos
4. ✅ Criar primeiro pedido de teste
5. ✅ Monitorar logs por 24h

**Deploy profissional completo!** 🚀
```
