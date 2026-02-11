# ⚡ Referência Rápida - Agente WhatsApp

**Comandos essenciais e informações rápidas para o dia a dia**

---

## 🚀 Quick Start (5 minutos)

```bash
# 1. Clonar
git clone https://github.com/seu-usuario/agente-whatsapp.git
cd agente-whatsapp

# 2. Configurar
cp backend/.env.example backend/.env
nano backend/.env  # Preencher TODAS as variáveis

# 3. Subir
docker-compose up -d

# 4. Testar
curl http://localhost:8000/
```

---

## 🔑 Variáveis de Ambiente Essenciais

```bash
# OBRIGATÓRIAS
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-chave

TINY_CLIENT_ID=seu-client-id
TINY_CLIENT_SECRET=seu-secret
TINY_ACCESS_TOKEN=seu-token
TINY_REFRESH_TOKEN=seu-refresh
TINY_V2_TOKEN=seu-token-v2

OPENAI_API_KEY=sk-sua-key

PAGARME_API_KEY=sua-key
PAGARME_SECRET_KEY=seu-secret
```

---

## 🎮 Comandos Docker

```bash
# Subir ambiente
docker-compose up -d

# Ver logs
docker-compose logs -f backend

# Reiniciar
docker-compose restart backend

# Parar tudo
docker-compose down

# Rebuild
docker-compose up -d --build

# Ver uso de recursos
docker stats
```

---

## 👤 Controle Humano-Agente

### Via WhatsApp

```
/pausar   → Bot para de responder
/retomar  → Bot volta a responder
/assumir  → Você assume explicitamente
/liberar  → Devolve para o bot
/status   → Ver quem está atendendo
```

### Detecção Automática

Basta começar mensagem com:
- `[HUMANO]`
- `[ATENDENTE]`
- `[MANUAL]`

Exemplo:
```
[HUMANO] Olá! Sou o João, como posso ajudar?
```

### Via API

```bash
# Assumir conversa
curl -X POST http://localhost:8000/session/5531999999999/takeover \
  -H "Content-Type: application/json" \
  -d '{"attendant_id": "joao@rocacapital.com"}'

# Liberar
curl -X POST http://localhost:8000/session/5531999999999/release
```

---

## 📊 Consultas SQL Úteis

### Pedidos Hoje

```sql
SELECT canal, COUNT(*), SUM(total)
FROM pedidos
WHERE DATE(criado_em) = CURRENT_DATE
GROUP BY canal;
```

### Buscar Cliente

```sql
SELECT * FROM clientes
WHERE telefone = '5531999999999'
   OR cpf_cnpj = '12345678900';
```

### Pedidos Não Sincronizados

```sql
SELECT id, numero_pedido, criado_em
FROM pedidos
WHERE tiny_sincronizado = false
  AND criado_em < NOW() - INTERVAL '10 minutes';
```

### Últimas Sincronizações

```sql
SELECT * FROM sync_log
ORDER BY criado_em DESC
LIMIT 20;
```

### Produtos Mais Vendidos (30 dias)

```sql
SELECT
  p.nome,
  COUNT(DISTINCT ped.id) as pedidos,
  SUM((item->>'quantidade')::decimal) as qtd_total
FROM pedidos ped
CROSS JOIN LATERAL jsonb_array_elements(ped.itens) as item
JOIN produtos p ON (item->'produto'->>'id')::uuid = p.id
WHERE ped.criado_em >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY p.id, p.nome
ORDER BY pedidos DESC
LIMIT 10;
```

---

## 🔄 Sincronização Manual

### Produtos (Tiny → Supabase)

```bash
# Full sync (todos os produtos)
curl -X POST http://localhost:8000/api/sync/products

# Ver resultado
docker-compose logs backend | grep sync_products
```

### Status de Pedidos

```bash
# Atualizar status dos pedidos
curl -X POST http://localhost:8000/api/sync/orders-status

# Ver logs
docker-compose logs backend | grep sync_orders
```

---

## 🧪 Testes Rápidos

### Health Check

```bash
curl http://localhost:8000/
# Esperado: {"status": "ok"}
```

### Listar Produtos

```bash
curl http://localhost:8000/api/products?limit=5
```

### Buscar Pedido

```bash
curl http://localhost:8000/api/orders/search?phone=5531999999999
```

### Criar Pedido de Teste

```bash
curl -X POST http://localhost:8000/api/orders \
  -H "Content-Type: application/json" \
  -d @backend/tests/fixtures/pedido_teste.json
```

---

## 🐛 Troubleshooting Rápido

### Backend não inicia

```bash
# Ver logs detalhados
docker-compose logs backend

# Verificar configuração
docker-compose config

# Reiniciar
docker-compose restart backend
```

### Erro de conexão Supabase

```bash
# Testar manualmente
psql "postgresql://postgres:[senha]@[projeto].supabase.co:5432/postgres"

# Ver erro específico
docker-compose logs backend | grep supabase
```

### Erro na API Tiny

```bash
# Ver tentativas V3 e fallback V2
docker-compose logs backend | grep -E "(V3|V2|Tiny)"

# Testar token V2 manualmente
curl -X POST https://api.tiny.com.br/api2/info.php \
  -d "token=SEU_TOKEN_V2&formato=JSON"
```

### Container com alto uso de memória

```bash
# Ver uso atual
docker stats

# Aumentar limite no docker-compose.prod.yml
deploy:
  resources:
    limits:
      memory: 2G
```

---

## 📁 Arquivos Importantes

| Arquivo | Descrição |
|---------|-----------|
| `backend/.env` | **Configurações (NUNCA commitar!)** |
| `backend/src/api/main.py` | API endpoints |
| `backend/src/services/session_manager.py` | Controle humano-agente |
| `backend/src/services/tiny_hybrid_client.py` | Cliente Tiny (V3+V2) |
| `backend/src/agent/tools.py` | Ferramentas do agente |
| `backend/scripts/supabase_schema.sql` | Schema do banco |
| `docker-compose.prod.yml` | Config de produção |
| `.github/workflows/deploy.yml` | CI/CD |

---

## 🌐 URLs Importantes

### Desenvolvimento

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- n8n: http://localhost:5678

### Produção

- API: https://api.seudominio.com
- Docs: https://api.seudominio.com/docs
- n8n: https://n8n.seudominio.com

### Externas

- Tiny ERP: https://erp.tiny.com.br/
- Supabase: https://app.supabase.com/
- OpenAI: https://platform.openai.com/
- Pagar.me: https://dashboard.pagar.me/

---

## 📦 Backup Rápido

```bash
# Backup Redis (sessões)
docker exec agente-whatsapp-redis redis-cli SAVE
docker cp agente-whatsapp-redis:/data/dump.rdb ./backup/redis-$(date +%Y%m%d).rdb

# Backup logs
tar -czf backup/logs-$(date +%Y%m%d).tar.gz backend/logs/

# Backup Supabase
# Fazer no dashboard: Database → Backups → Download
```

---

## 🔄 Deploy Rápido

```bash
# 1. Commitar mudanças
git add .
git commit -m "feat: nova funcionalidade"

# 2. Push (CI/CD automático)
git push origin main

# 3. Acompanhar
# Ir em: https://github.com/seu-usuario/agente-whatsapp/actions

# 4. Verificar deploy
curl https://api.seudominio.com/
```

---

## 🎯 Fluxo de Trabalho Típico

### Adicionar Novo Produto

1. Cadastrar no Tiny ERP
2. Aguardar sync (5min) ou forçar:
   ```bash
   curl -X POST http://localhost:8000/api/sync/products
   ```
3. Verificar no Supabase:
   ```sql
   SELECT * FROM produtos WHERE nome ILIKE '%nome-produto%';
   ```

### Atualizar Estoque

1. Atualizar no Tiny ERP
2. Sync automático (5min) atualiza Supabase
3. Verificar:
   ```sql
   SELECT nome, estoque_atual FROM produtos WHERE sku = 'SKU123';
   ```

### Gerenciar Pedido Problemático

1. Identificar:
   ```sql
   SELECT * FROM pedidos WHERE tiny_sincronizado = false;
   ```
2. Ver erro:
   ```sql
   SELECT * FROM sync_log WHERE referencia_id = 'ID-DO-PEDIDO';
   ```
3. Corrigir no Tiny manualmente ou reprocessar

### Assumir Conversa Urgente

1. Ver mensagens:
   ```sql
   SELECT * FROM mensagens
   WHERE telefone_cliente = '5531999999999'
   ORDER BY criado_em DESC LIMIT 10;
   ```
2. Assumir:
   ```
   [HUMANO] Olá! Como posso ajudar?
   ```
3. Liberar:
   ```
   /liberar
   ```

---

## 📞 Contatos de Suporte

- **Tiny ERP:** https://ajuda.tiny.com.br/
- **Supabase:** https://supabase.com/support
- **EasyPanel:** https://easypanel.io/docs
- **Hostinger:** https://www.hostinger.com.br/ajuda

---

## 🚨 Emergências

### API Caiu

```bash
# 1. Ver logs
docker-compose logs --tail=100 backend

# 2. Reiniciar
docker-compose restart backend

# 3. Se não resolver
docker-compose down
docker-compose up -d

# 4. Último recurso (rebuild)
docker-compose up -d --build
```

### Banco de Dados Corrompido

```bash
# 1. Fazer backup
# 2. Restaurar do backup do Supabase (dashboard)
# 3. Re-executar schema se necessário
```

### CI/CD Falhando

```bash
# 1. Ver erro no GitHub Actions
# 2. Testar SSH manualmente:
ssh root@seu-servidor.hostinger.com

# 3. Verificar secrets no GitHub
# 4. Re-run do workflow
```

---

**Mantenha este arquivo aberto durante o uso diário!** 📌

---

**Atualizado:** 11/02/2026
**Versão:** 2.0.0
