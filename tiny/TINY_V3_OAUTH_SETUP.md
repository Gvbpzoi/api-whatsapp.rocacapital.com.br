# Tiny API V3 OAuth2 - Setup Guide

## Overview

Integração OAuth2 segura e robusta com Tiny ERP API V3, implementando:

- **Backend Express** gerencia todos os fluxos OAuth e tokens
- **PostgreSQL** armazena tokens com criptografia AES-256-GCM
- **CSRF protection** com state parameter
- **PostgreSQL advisory locks** para concorrência
- **Cache em memória** (node-cache) - sem dependência de Redis
- **Singleflight pattern** para evitar refreshes duplicados
- **Mobile** nunca vê client_secret

## Architecture

```
┌─────────────┐       ┌──────────────┐       ┌─────────────┐
│   Mobile    │◄─────►│   Backend    │◄─────►│  Tiny API   │
│   (React    │       │  (Express +  │       │    (OAuth   │
│   Native)   │       │   PostgreSQL)│       │     V3)     │
└─────────────┘       └──────────────┘       └─────────────┘
                              │
                              ▼
                      ┌──────────────┐
                      │  PostgreSQL  │
                      │  (Encrypted  │
                      │   Tokens)    │
                      └──────────────┘
```

## Prerequisites

- Node.js 18+
- PostgreSQL 14+
- Tiny ERP account with API access
- Tiny OAuth2 credentials (client_id + client_secret)

## Installation

### 1. Database Migration

A migration já foi aplicada:

```bash
cd pdv-system/apps/backend
npx prisma migrate deploy
```

Isso cria:
- Tabela `oauth_states` (CSRF protection)
- Colunas adicionais em `oauth_tokens` (enhanced tracking)

### 2. Install Dependencies

```bash
cd pdv-system/apps/backend
npm install node-cache @types/node-cache
```

Dependências já incluídas:
- `express-rate-limit` ✅
- `node-cron` ✅
- `axios` ✅

### 3. Environment Variables

Adicione ao `.env` do backend:

```bash
# Tiny OAuth V3
TINY_AUTH_URL=https://accounts.tiny.com.br/realms/tiny/protocol/openid-connect/auth
TINY_TOKEN_URL=https://accounts.tiny.com.br/realms/tiny/protocol/openid-connect/token
TINY_API_BASE=https://api.tiny.com.br/public-api/v3
TINY_CLIENT_ID=your_client_id_here
TINY_CLIENT_SECRET=your_client_secret_here
TINY_REDIRECT_URI=http://localhost:3000/api/tiny/callback
TINY_SCOPE=openid

# Token Encryption (gerar com comando abaixo)
TOKEN_ENCRYPTION_KEY=your_64_hex_char_key_here
```

**Gerar TOKEN_ENCRYPTION_KEY:**

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

### 4. Update Server to Use New Routes

Edite `pdv-system/apps/backend/src/server.ts`:

```typescript
// Import new routes
import tinyRoutesV3 from './routes/tinyRoutesV3';

// Register routes
app.use('/api/tiny', tinyRoutesV3);

// Start OAuth cleanup job
import { startOAuthCleanup } from './jobs/oauthCleanup';
startOAuthCleanup();
```

## OAuth Flow

### First Time Setup (Admin Only)

1. **Start OAuth Flow:**

```bash
GET /api/tiny/auth/start
```

Response:
```json
{
  "success": true,
  "data": {
    "authUrl": "https://accounts.tiny.com.br/...",
    "state": "abc123..."
  }
}
```

2. **Redirect user to authUrl** (open in browser)

3. **User authorizes** → Tiny redirects to `/api/tiny/callback`

4. **Backend exchanges code** for tokens and saves encrypted

5. **Done!** All future requests use auto-refreshed tokens

### Token Management

Tokens são gerenciados automaticamente:

- **Auto-refresh**: Quando faltam 10% do tempo de vida
- **Retry on 401**: Tenta refresh + retry uma vez
- **Concurrency safe**: PostgreSQL locks previnem race conditions
- **Singleflight**: Evita múltiplos refreshes simultâneos

## API Endpoints

### Auth Routes (Admin)

```
GET  /api/tiny/auth/start          - Start OAuth (get auth URL)
GET  /api/tiny/callback            - OAuth callback
POST /api/tiny/bootstrap/exchange-code - Manual code exchange
POST /api/tiny/auth/revoke         - Force reauth
```

### Health & Cache

```
GET    /api/tiny/health            - Token status + diagnostics
DELETE /api/tiny/cache/:key        - Invalidate cache pattern
DELETE /api/tiny/cache             - Clear all cache
```

### Proxy Routes (Auto-authenticated)

```
GET /api/tiny/categorias           - Get categories (cached 30min)
GET /api/tiny/produtos?offset=0&limit=50 - Get products
GET /api/tiny/produtos/:id         - Get single product
ALL /api/tiny/proxy/*              - Generic proxy (whitelist)
```

## Security Features

1. **Encryption**: Refresh tokens encrypted with AES-256-GCM
2. **CSRF**: State parameter validated on callback
3. **Concurrency**: PostgreSQL advisory locks
4. **Path Safety**: Whitelist + path normalization
5. **Rate Limit**: 30 req/min on proxy routes
6. **Anti-Loop**: Max 1 refresh retry per request
7. **Logging**: Sensitive data masked

## Mobile Usage

```typescript
import { tinyApi } from '@/services/tinyApi';

// Check health
const health = await tinyApi.checkHealth();

// Get categories
const categories = await tinyApi.listCategorias();

// Get products
const products = await tinyApi.listProdutos(0, 50);

// Handle reauth (automatic via interceptor)
// User sees alert: "Tiny ERP - Reautorização Necessária"
```

## Monitoring

### Health Check

```bash
curl http://localhost:3000/api/tiny/health
```

Response:
```json
{
  "success": true,
  "data": {
    "connected": true,
    "configured": true,
    "expiresAt": "2026-01-17T10:30:00.000Z",
    "needsRefresh": false,
    "needsReauth": false,
    "cacheStats": {
      "keys": 5,
      "hits": 120,
      "misses": 8
    }
  }
}
```

### Cache Stats

```bash
curl -X DELETE http://localhost:3000/api/tiny/cache/produtos \
  -H "Authorization: Bearer YOUR_JWT"
```

## Troubleshooting

### "TINY_NEEDS_REAUTH" Error

**Causa**: Token refresh falhou 3+ vezes ou token revogado

**Solução**:
```bash
curl http://localhost:3000/api/tiny/auth/start
# Open authUrl in browser and reauthorize
```

### "Path not in whitelist"

**Causa**: Tentativa de acesso a endpoint não autorizado

**Solução**: Adicione path ao whitelist em `TinyProxyService.ts`:

```typescript
private allowedPaths: string[] = [
  '/categorias',
  '/produtos',
  '/your-new-path', // Add here
];
```

### Token Encryption Errors

**Causa**: TOKEN_ENCRYPTION_KEY inválida ou ausente

**Solução**:
```bash
# Generate new key
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"

# Add to .env
TOKEN_ENCRYPTION_KEY=generated_key_here
```

### High Cache Misses

**Causa**: Cache está sendo invalidado muito frequentemente

**Solução**: Ajuste TTL em `TinyControllerV3.ts`:

```typescript
// Increase cache time
cache.set(CacheKeys.TINY_CATEGORIES, data, 60 * 60); // 1 hour
```

## Cron Jobs

### OAuth State Cleanup

Roda a cada hora para limpar states expirados:

```typescript
// Automatically started in server.ts
import { startOAuthCleanup } from './jobs/oauthCleanup';
startOAuthCleanup();
```

Logs:
```
[OAuthCleanup] Starting cleanup...
[OAuthCleanup] Before: 10 total, 5 expired
[OAuthCleanup] Deleted: 5 expired states
[OAuthCleanup] Completed in 45ms
```

## Testing Checklist

- [ ] Health check returns correct status
- [ ] State generation and validation works
- [ ] Code exchange saves encrypted tokens
- [ ] Token refresh acquires lock correctly
- [ ] Concurrent refreshes don't duplicate
- [ ] 401 triggers refresh and retry once
- [ ] Persistent 401 marks needsReauth
- [ ] Generic proxy respects whitelist
- [ ] Rate limiter blocks excessive requests
- [ ] Cache reduces Tiny API calls
- [ ] Mobile can load categories
- [ ] Mobile shows reauth alert

## Performance Tuning

### Cache Strategy

```typescript
// High-traffic endpoints: longer cache
CacheKeys.TINY_CATEGORIES: 30 minutes
CacheKeys.TINY_PRODUCTS_PAGE: 5 minutes
CacheKeys.TINY_PRODUCT: 10 minutes
```

### Rate Limiting

```typescript
// Adjust in tinyRoutesV3.ts
const proxyRateLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 30, // Increase if needed
});
```

### PostgreSQL Locks

```typescript
// Lock timeout (if needed)
await prisma.$queryRaw`
  SELECT pg_try_advisory_lock(${lockId}, 5000) -- 5s timeout
`;
```

## Migration from Old System

Se você está usando o TinyOAuthService antigo:

1. **Backup tokens atuais**:
```sql
SELECT * FROM oauth_tokens WHERE provider = 'tiny' AND is_active = true;
```

2. **Apply migration**:
```bash
npx prisma migrate deploy
```

3. **Update server.ts** para usar novos routes

4. **Restart server**

5. **Test health**:
```bash
curl http://localhost:3000/api/tiny/health
```

6. **Se needsReauth=true**, reautorize:
```bash
curl http://localhost:3000/api/tiny/auth/start
```

## Support

Para problemas:

1. Check logs: `[TinyOAuth]`, `[TokenStore]`, `[OAuthStateManager]`
2. Run diagnostics: `GET /api/tiny/health`
3. Check database: `SELECT * FROM oauth_tokens WHERE provider = 'tiny'`
4. Verify .env: All TINY_* variables set
5. Test encryption: TOKEN_ENCRYPTION_KEY is 64 hex chars

## References

- [Tiny API V3 Docs](https://developer.tiny.com.br/)
- [OAuth 2.0 RFC](https://tools.ietf.org/html/rfc6749)
- [PostgreSQL Advisory Locks](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)
