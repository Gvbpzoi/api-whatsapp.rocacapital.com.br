```markdown
# 🏗️ Arquitetura Completa - Agente WhatsApp Roça Capital

**Data:** 11/02/2026
**Versão:** 2.0.0
**Status:** ✅ Pronto para Implementação

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura de Dados](#arquitetura-de-dados)
3. [Fluxos Principais](#fluxos-principais)
4. [Integrações](#integrações)
5. [Controle Humano-Agente](#controle-humano-agente)
6. [Deploy e Configuração](#deploy-e-configuração)

---

## 🎯 Visão Geral

### O Problema Resolvido

Você tinha um agente WhatsApp no n8n com **100+ nodes**, difícil de manter e sem controle humano.

### A Solução

Arquitetura híbrida moderna:
- **Backend Python/FastAPI** - Core do agente
- **Supabase** - Cache/backup rápido (evita rate limit do Tiny)
- **Tiny ERP** - Fonte da verdade (todos os pedidos convergem aqui)
- **n8n** - Apenas webhooks simples
- **Controle Humano-Agente** - Você pode assumir conversas quando necessário

---

## 🏛️ Arquitetura de Dados

### 3 Canais de Venda → 1 Sistema Unificado

```
┌─────────────────────────────────────────────────────────────┐
│                    TINY ERP                                 │
│              (Fonte da Verdade)                             │
│  • Status oficial dos pedidos                               │
│  • Gestão de estoque                                        │
│  • Nota fiscal                                              │
│  • Rastreamento                                             │
└──────▲────────────▲────────────▲───────────────────────────┘
       │            │            │
       │            │            │
┌──────┴───────┐ ┌──┴────────┐ ┌┴────────────┐
│  1. PDV/Loja │ │ 2.WhatsApp│ │ 3. Site     │
│    Física    │ │  (Agente) │ │ (E-commerce)│
└──────┬───────┘ └──┬────────┘ └┬────────────┘
       │            │            │
       └────────────▼────────────┘
                    │
       ┌────────────▼─────────────────────────┐
       │        SUPABASE                       │
       │      (Cache/Backup)                   │
       │                                       │
       │ • Busca instantânea (<100ms)          │
       │ • Sem limite de requisições           │
       │ • Backup redundante                   │
       │ • Relatórios rápidos                  │
       └───────────────────────────────────────┘
```

### Por Que Supabase Como Cache?

| Aspecto | Direto no Tiny | Com Supabase Cache |
|---------|---------------|-------------------|
| **Busca pedido** | 2-5s | <100ms ⚡ |
| **Rate limit** | Risco em horário pico | Sem risco ✅ |
| **Relatórios** | Lento | Instantâneo 📊 |
| **Backup** | Só no Tiny | Redundante ✅ |
| **Busca complexa** | Difícil | SQL direto 🚀 |

---

## 🔄 Fluxos Principais

### 1️⃣ Cliente Compra via WhatsApp

```
Cliente: "Quero queijo canastra"
   ↓
Bot busca no SUPABASE (instantâneo ⚡)
   ↓
Bot: "Temos 3 opções: 1kg (R$125), 500g (R$65)..."
   ↓
Cliente: "O de 1kg"
   ↓
Bot adiciona ao carrinho (SUPABASE)
   ↓
Cliente: "Quero finalizar"
   ↓
Bot: "Qual seu endereço para calcular frete?"
   ↓
Cliente informa endereço
   ↓
Bot calcula frete
   ↓
Bot: "Quer pagar PIX ou Cartão?"
   ↓
Cliente: "PIX"
   ↓
-------------------------------------------
BACKEND PROCESSA:
1. Cria pedido no SUPABASE (backup imediato)
2. Gera PIX (Pagar.me)
3. Envia para TINY ERP
4. Atualiza SUPABASE com tiny_pedido_id
-------------------------------------------
   ↓
Bot: "Pedido #PED-WPP-001 criado! QR Code: [pix]"
```

**Vantagens:**
- ✅ Pedido salvo em 2 lugares (Supabase + Tiny)
- ✅ Se Tiny cair, pedido não se perde
- ✅ Cliente pode consultar depois (busca rápida no Supabase)

---

### 2️⃣ Cliente Consulta Pedido

```
Cliente: "Cadê meu pedido?"
   ↓
Bot: "Me passa seu telefone, CPF ou número do pedido"
   ↓
Cliente: "31 99999-9999"
   ↓
Bot busca no SUPABASE (instantâneo - não consome API Tiny!)
   ↓
Bot: "📦 Encontrei 2 pedidos:

      🚚 Pedido #PED-SITE-12345
         Status: ENVIADO
         Rastreio: BR123456789BR

      ✅ Pedido #PED-WPP-00123
         Status: CONFIRMADO"
```

**Vantagens:**
- ⚡ Resposta instantânea (não espera API Tiny)
- 🚀 Não consome limite de requisições do Tiny
- 📊 Pode buscar por telefone, CPF, número do pedido ou nome

---

### 3️⃣ Sincronização Periódica (n8n scheduled)

**A cada 5 minutos:**

```
n8n Cron Job (5min)
   ↓
POST /api/sync/orders-status
   ↓
Backend:
  1. Busca pedidos atualizados no Tiny (últimos 10min)
  2. Para cada pedido:
     - Verifica se existe no Supabase
     - Se existe: UPDATE status
     - Se não existe: INSERT (pedido veio do site)
  3. Atualiza rastreio, NF, status
   ↓
Logs salvos em sync_log
```

**Resultado:**
- Status sempre atualizado
- Pedidos do site aparecem no Supabase
- Histórico completo unificado

---

### 4️⃣ Produtos Vendidos por Peso (Variáveis)

**Caso especial: Queijo Canastra do Onésio**

```
Cliente: "Quero queijo do Onésio"
   ↓
Bot busca produto (tem flag requer_pesagem=true)
   ↓
Bot: "Queijo Canastra do Onésio:
      • 1kg (aprox.) - R$ 125,00 ⚖️
      • 500g (aprox.) - R$ 62,50 ⚖️

      ⚖️ Peso aproximado. Após pesagem:
      • Se pesar menos → complementamos com outro item
      • Se pesar mais → estornamos diferença

      Qual prefere?"
   ↓
Cliente: "O de 1kg"
   ↓
Bot adiciona com peso_aproximado=1.0, requer_pesagem=true
   ↓
[Pedido criado no Tiny com observação]
   ↓
[VOCÊ pesa o queijo = 1.05kg]
   ↓
[VOCÊ ajusta no Tiny ou gera complemento]
```

---

## 🔌 Integrações

### Tiny ERP (API V3 com OAuth 2.0)

**Endpoints Usados:**

```python
# Produtos
GET /produtos              # Listar
GET /produtos/{id}         # Detalhes + estoque
GET /estoque/{id}          # Estoque detalhado

# Pedidos
POST /pedidos              # Criar pedido
GET /pedidos               # Listar/buscar
PUT /pedidos/{id}/situacao # Atualizar status

# Contatos (Clientes)
POST /contatos             # Criar cliente
GET /contatos              # Buscar por CPF/telefone
```

**Autenticação:**
- OAuth 2.0 com refresh token automático
- Token renova automaticamente antes de expirar

**Rate Limiting:**
- Evitado usando Supabase como cache
- Apenas operações críticas usam API Tiny

---

### Supabase (PostgreSQL + APIs)

**Tabelas Principais:**

```sql
produtos              -- Cache de produtos (Tiny/Site)
clientes              -- Clientes WhatsApp
carrinhos             -- Carrinhos temporários
pedidos               -- TODOS os pedidos (3 canais)
sessoes               -- Controle humano-agente
mensagens             -- Histórico de conversa
sync_log              -- Auditoria de syncs
```

**Funcionalidades:**
- ✅ Full-text search em português
- ✅ Índices otimizados
- ✅ Triggers automáticos (updated_at)
- ✅ Views para relatórios
- ✅ Função de busca inteligente

**Exemplo de Busca:**

```sql
-- Cliente busca "queijo canastra curado"
SELECT * FROM buscar_produtos('queijo canastra curado', 20);

-- Retorna produtos ordenados por relevância
-- Busca em: nome, descrição, SKU, tags
-- Filtros: apenas ativos e disponíveis para WhatsApp
```

---

### Pagar.me (Pagamentos)

**PIX:**
```python
# Gerar QR Code PIX
qr_code = await pagarme.create_pix_payment(
    amount=12500,  # R$ 125,00 em centavos
    customer=customer_data
)

# Retorna:
{
    "qr_code": "00020126...",
    "qr_code_url": "https://...",
    "expires_at": "2026-02-11T15:30:00Z"
}
```

**Cartão:**
```python
# Gerar link de pagamento
link = await pagarme.create_card_payment_link(
    amount=12500,
    customer=customer_data,
    items=order_items
)

# Cliente clica, preenche dados do cartão
# Webhook notifica quando pago
```

---

## 👤 Controle Humano-Agente

### Como Funciona

O sistema detecta **automaticamente** quando você quer assumir uma conversa:

**3 Formas de Controlar:**

#### 1. Detecção Automática
```
Cliente: Preciso de ajuda urgente!
Bot: Como posso ajudar?

[Você vê e decide assumir]
Você: [HUMANO] Olá! Sou o João, vou te ajudar...

→ Sistema detecta [HUMANO] e PAUSA o bot ✅
→ Cliente vê sua mensagem
→ Bot fica em silêncio até você /liberar
```

#### 2. Comandos no WhatsApp
```
/pausar   → Bot para (nada acontece)
/retomar  → Bot volta a responder
/assumir  → Você assume explicitamente
/liberar  → Devolve para o bot
/status   → Ver quem está atendendo
```

#### 3. API (Dashboard)
```javascript
// Assumir conversa
await fetch('/session/5531999999999/takeover', {
  method: 'POST',
  body: JSON.stringify({
    attendant_id: 'joao@rocacapital.com'
  })
})

// Liberar
await fetch('/session/5531999999999/release', {
  method: 'POST'
})
```

### Auto-Retomada

Se você assumir e ficar **5 minutos sem responder**, o bot retoma automaticamente:

```
[10h00] Você: /assumir
[10h02] Cliente: Oi, tem desconto?
[Você não responde]
[10h07] Cliente: Alguém aí?

→ Sistema detecta 5min de inatividade
→ Bot retoma automaticamente
→ Bot: "Oi! Desculpe a demora, temos desconto..."
```

---

## ⚙️ Deploy e Configuração

### 1. Configurar Supabase

```bash
# 1. Criar projeto no Supabase
# 2. Executar schema
psql $DATABASE_URL < backend/scripts/supabase_schema.sql

# 3. Configurar .env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-chave-aqui
```

### 2. Configurar Tiny ERP

```bash
# 1. Obter credenciais OAuth no painel Tiny
# 2. Configurar .env
TINY_CLIENT_ID=seu-client-id
TINY_CLIENT_SECRET=seu-secret
TINY_ACCESS_TOKEN=seu-token  # Obtido via OAuth flow
TINY_REFRESH_TOKEN=seu-refresh-token
```

### 3. Subir Backend

```bash
cd backend
docker-compose up -d

# Ou sem Docker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn src.api.main:app --reload
```

### 4. Configurar n8n (Sync Periódico)

**Workflow 1: Sync Status Pedidos**
```json
{
  "trigger": "Schedule - Every 5 minutes",
  "node": "HTTP Request",
  "url": "http://backend:8000/api/sync/orders-status",
  "method": "POST"
}
```

**Workflow 2: Sync Produtos**
```json
{
  "trigger": "Schedule - Daily at 6am",
  "node": "HTTP Request",
  "url": "http://backend:8000/api/sync/products",
  "method": "POST"
}
```

---

## 📊 Monitoramento

### Logs de Sincronização

```sql
-- Ver últimas sincronizações
SELECT * FROM sync_log
ORDER BY criado_em DESC
LIMIT 50;

-- Ver erros
SELECT * FROM sync_log
WHERE status = 'error'
ORDER BY criado_em DESC;

-- Estatísticas do dia
SELECT
  operacao,
  status,
  COUNT(*) as quantidade
FROM sync_log
WHERE DATE(criado_em) = CURRENT_DATE
GROUP BY operacao, status;
```

### Métricas Importantes

```sql
-- Pedidos por canal (hoje)
SELECT canal, COUNT(*), SUM(total)
FROM pedidos
WHERE DATE(criado_em) = CURRENT_DATE
GROUP BY canal;

-- Taxa de sincronização com Tiny
SELECT
  COUNT(CASE WHEN tiny_sincronizado THEN 1 END) * 100.0 / COUNT(*) as taxa_sync
FROM pedidos
WHERE canal = 'whatsapp';

-- Tempo médio de resposta do bot
SELECT
  AVG(EXTRACT(EPOCH FROM (ultima_msg_agente - ultima_msg_cliente))) as avg_seconds
FROM sessoes
WHERE modo = 'agent';
```

---

## 🚀 Próximos Passos

### Implementar Agora

1. ✅ Executar schema no Supabase
2. ✅ Configurar credenciais Tiny
3. ✅ Testar sincronização de produtos
4. ✅ Criar primeiro pedido de teste
5. ✅ Configurar n8n workflows

### Implementar Depois (Tools do Agente)

- [ ] `buscar_produtos` - Busca inteligente no Supabase
- [ ] `add_to_cart` - Gerenciar carrinho
- [ ] `calculate_shipping` - Integração Lalamove/Correios
- [ ] `generate_payment` - PIX/Cartão Pagar.me
- [ ] `create_order` - Criar pedido completo
- [ ] `buscar_pedido` - Consultar status

---

## 📞 Suporte

**Problemas com integração:**
- Ver logs: `docker-compose logs -f backend`
- Ver sync_log no Supabase
- API docs: http://localhost:8000/docs

**Problemas com Tiny:**
- Documentação: https://erp.tiny.com.br/public-api/v3/swagger/
- Suporte: https://ajuda.tiny.com.br/

---

## ✅ Checklist de Implementação

- [ ] Supabase configurado
- [ ] Schema executado
- [ ] Tiny OAuth configurado
- [ ] Backend rodando
- [ ] n8n workflows criados
- [ ] Primeira sincronização de produtos
- [ ] Primeiro pedido de teste criado
- [ ] Controle humano-agente testado
- [ ] Logs de sync funcionando
- [ ] Dashboard de monitoramento (opcional)

---

**Desenvolvido com ❤️ por:** Claude + Guilherme Vieira
**Data:** 11/02/2026
**Versão:** 2.0.0

**Arquitetura robusta, escalável e profissional!** 🚀
```
