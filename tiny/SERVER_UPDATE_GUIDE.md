# Server.ts Update Guide

## How to Enable Tiny OAuth V3 in Your Server

### Option 1: Replace Old Routes (Recommended)

Replace the old Tiny routes import with the new V3 routes:

```typescript
// OLD (remove or comment out)
// import tinyRoutes from './routes/tinyRoutes';

// NEW (add this)
import tinyRoutesV3 from './routes/tinyRoutesV3';

// Register routes
app.use('/api/tiny', tinyRoutesV3);
```

### Option 2: Run Both (Backward Compatible)

Keep both old and new routes running side-by-side:

```typescript
// Old routes
import tinyRoutes from './routes/tinyRoutes';
app.use('/api/tiny', tinyRoutes);

// New V3 routes on different path
import tinyRoutesV3 from './routes/tinyRoutesV3';
app.use('/api/tiny/v3', tinyRoutesV3);
```

Then gradually migrate to V3 routes.

### Enable OAuth Cleanup Job

Add this after your app initialization:

```typescript
import { startOAuthCleanup } from './jobs/oauthCleanup';

// Start OAuth cleanup job (runs hourly)
startOAuthCleanup();
console.log('✅ OAuth cleanup job started');
```

### Full Example

```typescript
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import dotenv from 'dotenv';

// Load environment
dotenv.config();

// Initialize app
const app = express();

// Middleware
app.use(cors());
app.use(helmet());
app.use(express.json());

// Routes
import authRoutes from './routes/authRoutes';
import productRoutes from './routes/productRoutes';
import orderRoutes from './routes/orderRoutes';
import customerRoutes from './routes/customerRoutes';

// OLD Tiny routes (optional - for backward compatibility)
// import tinyRoutes from './routes/tinyRoutes';
// app.use('/api/tiny', tinyRoutes);

// NEW Tiny OAuth V3 routes
import tinyRoutesV3 from './routes/tinyRoutesV3';
app.use('/api/tiny', tinyRoutesV3);

// Register other routes
app.use('/api/auth', authRoutes);
app.use('/api/products', productRoutes);
app.use('/api/orders', orderRoutes);
app.use('/api/customers', customerRoutes);

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Start OAuth cleanup job
import { startOAuthCleanup } from './jobs/oauthCleanup';
startOAuthCleanup();
console.log('✅ OAuth cleanup job started');

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🚀 Server running on port ${PORT}`);
  console.log(`📡 API Base: http://localhost:${PORT}/api`);
  console.log(`🔐 Tiny OAuth: http://localhost:${PORT}/api/tiny/auth/start`);
});
```

### Testing After Update

1. **Start server:**
   ```bash
   npm run dev
   ```

2. **Test health:**
   ```bash
   curl http://localhost:3000/api/tiny/health
   ```

3. **Check cleanup job:**
   Look for log: `[OAuthCleanup] Scheduled to run every hour`

4. **Start OAuth flow:**
   ```bash
   curl http://localhost:3000/api/tiny/auth/start
   ```

### Troubleshooting

#### "Cannot find module './routes/tinyRoutesV3'"

**Solution**: Make sure the file exists:
```bash
ls pdv-system/apps/backend/src/routes/tinyRoutesV3.ts
```

#### "Cannot find module './jobs/oauthCleanup'"

**Solution**: Make sure the file exists:
```bash
ls pdv-system/apps/backend/src/jobs/oauthCleanup.ts
```

#### Server crashes on startup

**Check**:
1. All dependencies installed: `npm install`
2. Prisma generated: `npx prisma generate`
3. Environment variables set in `.env`
4. Migration applied: `npx prisma migrate deploy`

#### OAuth cleanup job not running

**Check**:
1. `startOAuthCleanup()` is called in server.ts
2. Look for logs: `[OAuthCleanup] Scheduled to run every hour`
3. Check cron format: `0 * * * *` (every hour at minute 0)

### Migration Checklist

- [ ] New routes file exists
- [ ] New controller file exists
- [ ] All service files exist
- [ ] Migration applied
- [ ] Dependencies installed
- [ ] Environment variables set
- [ ] Server.ts updated
- [ ] Server restarts without errors
- [ ] Health check passes
- [ ] OAuth flow works
- [ ] Cleanup job logs appear

### Rollback Plan

If something goes wrong:

1. **Revert server.ts changes:**
   ```typescript
   // Use old routes
   import tinyRoutes from './routes/tinyRoutes';
   app.use('/api/tiny', tinyRoutes);
   
   // Comment out new imports
   // import tinyRoutesV3 from './routes/tinyRoutesV3';
   // import { startOAuthCleanup } from './jobs/oauthCleanup';
   ```

2. **Restart server:**
   ```bash
   npm run dev
   ```

3. **Database is safe** - migration is non-destructive
4. **Old tokens still work** - backward compatible

### Support

For help, check:
- `docs/integrations/TINY_V3_OAUTH_SETUP.md` - Complete setup guide
- `docs/integrations/TINY_V3_IMPLEMENTATION_SUMMARY.md` - Implementation details
- `scripts/verify-tiny-oauth-setup.sh` - Setup verification
