# 🧪 Guia de Testes - Integração Tiny ERP

**Objetivo:** Testar a integração end-to-end do PDV com Tiny ERP

---

## ✅ Pré-requisitos

- [ ] Docker rodando (PostgreSQL)
- [ ] Backend iniciado (`npm run dev`)
- [ ] Mobile conectado via Expo Go
- [ ] Token do Tiny ERP configurado no `.env`
- [ ] Login como ADMIN no app

---

## 🚀 Teste 1: Conexão com Tiny

### Objetivo
Verificar se o sistema consegue se comunicar com a API do Tiny ERP.

### Passos
1. Abrir app mobile
2. Login como Admin (admin@pdv.com / PIN: 1234)
3. Clicar em "Sincronização" (card azul 🔄)
4. Clicar em "Testar Conexão"

### Resultado Esperado
✅ Alert mostrando: "Conexão com Tiny ERP estabelecida com sucesso"

### Se Falhar
❌ Verificar:
- Token correto no `.env`
- Backend rodando
- Internet funcionando

---

## 📦 Teste 2: Sincronizar Produtos

### Objetivo
Importar catálogo de produtos do Tiny para o PDV.

### Passos
1. Na tela "Sincronização"
2. Clicar em "Sincronizar Produtos"
3. Confirmar no alert
4. Aguardar processamento (pode levar 1-2 minutos)
5. Ver resultado do sync

### Resultado Esperado
✅ Alert com estatísticas:
```
✅ X produtos sincronizados
❌ Y erros
📦 Z total
```

### Verificar
1. Voltar para Home
2. Ir em "Produtos"
3. Ver lista de produtos sincronizados
4. Cada produto deve ter dados do Tiny (preço, estoque, categoria)

### Se Falhar
❌ Ir em Sincronização → Logs → Ver erros
❌ Verificar se produtos têm preço e código no Tiny

---

## 👥 Teste 3: Criar Cliente e Sincronizar

### Objetivo
Criar cliente no PDV e verificar sincronização automática com Tiny.

### Passos
1. Ir em "Clientes"
2. Clicar "+ Novo Cliente"
3. Preencher dados:
   - Nome: "Cliente Teste Sync"
   - Telefone: "11987654321"
   - Email: "teste@pdv.com"
   - CPF: "123.456.789-00"
4. Salvar

### Resultado Esperado
✅ Cliente criado com sucesso
✅ No backend console: "Cliente X sincronizado com Tiny: [tinyId]"

### Verificar no Banco
```sql
SELECT id, name, phone, tiny_id 
FROM customers 
WHERE phone = '11987654321';
```
- `tiny_id` deve estar preenchido

### Verificar no Tiny ERP
1. Acessar painel do Tiny
2. Ir em Clientes
3. Buscar por "Cliente Teste Sync"
4. Confirmar que existe

### Se Falhar
❌ Cliente criado localmente mas sem `tiny_id`
❌ Ver logs: Sincronização → Logs → Filtrar por "customer"
❌ Pode sincronizar manualmente depois

---

## 🛒 Teste 4: Fazer Venda e Sincronizar Pedido

### Objetivo
Realizar venda completa e verificar sincronização automática do pedido.

### Parte A: Preparação
1. Certifique-se que tem produtos sincronizados (Teste 2)
2. Certifique-se que tem cliente (pode usar o do Teste 3)

### Parte B: Fazer Venda
1. Ir em "PDV"
2. Adicionar 2-3 produtos ao carrinho
3. Clicar "Selecionar Cliente"
4. Escolher "Cliente Teste Sync"
5. Clicar "Finalizar"
6. Confirmar método de pagamento (DINHEIRO)
7. Confirmar venda

### Resultado Esperado
✅ Venda finalizada com sucesso
✅ No backend console:
```
✅ PEDIDO COMPLETADO COM SUCESSO!
🔄 Sincronizando pedido com Tiny ERP...
✅ Pedido sincronizado com Tiny: [tinyId]
```

### Verificar no Banco
```sql
SELECT id, order_number, tiny_id, status, total 
FROM orders 
WHERE status = 'COMPLETED'
ORDER BY completed_at DESC 
LIMIT 1;
```
- `tiny_id` deve estar preenchido

### Verificar no Tiny ERP
1. Acessar painel do Tiny
2. Ir em Pedidos
3. Buscar pelo número do pedido (ex: 260110-0001)
4. Confirmar que existe com:
   - Cliente correto
   - Produtos corretos
   - Valor correto

### Se Falhar
❌ Pedido finalizado localmente mas sem `tiny_id`
❌ Ir em Sincronização → Pedidos Pendentes
❌ Clicar "Sincronizar Agora" no pedido

---

## 📊 Teste 5: Verificar Logs e Status

### Objetivo
Confirmar que todas operações estão sendo registradas.

### Passos
1. Ir em "Sincronização"
2. Verificar aba "Status":
   - Estatísticas 24h (sucessos/erros/pendentes)
   - Data da última sincronização de produtos
   - Número de pedidos pendentes

3. Ir na aba "Logs":
   - Ver histórico de operações
   - Identificar sucessos (verde)
   - Identificar erros (vermelho)
   - Se houver erros, clicar "Tentar Novamente"

4. Ir na aba "Pendentes":
   - Ver pedidos não sincronizados
   - Testar sincronização manual

### Resultado Esperado
✅ Logs mostrando operações realizadas
✅ Estatísticas condizentes com testes
✅ Sem pedidos pendentes (ou poucos)

---

## 🔄 Teste 6: Retry de Sincronização

### Objetivo
Verificar que o sistema tenta novamente operações que falharam.

### Cenário A: Simular Erro
1. Desconectar da internet
2. Fazer uma venda
3. Finalizar (vai falhar ao sincronizar)
4. Reconectar internet
5. Ir em Sincronização → Pendentes
6. Sincronizar manualmente

### Cenário B: Usar Log com Erro Existente
1. Ir em Sincronização → Logs
2. Encontrar um log com status ERROR
3. Clicar "Tentar Novamente"
4. Verificar se mudou para SUCCESS

### Resultado Esperado
✅ Operação reprocessada com sucesso
✅ Status atualizado no log

---

## 📋 Checklist Final

Após completar todos os testes:

- [ ] ✅ Conexão com Tiny funcionando
- [ ] ✅ Produtos sincronizados
- [ ] ✅ Cliente criado e sincronizado
- [ ] ✅ Pedido criado e sincronizado
- [ ] ✅ Logs registrando operações
- [ ] ✅ Retry funcionando
- [ ] ✅ Tela de sincronização mostrando dados corretos

---

## 🐛 Problemas Comuns

### "Token inválido"
**Solução:** Regerar token no Tiny e atualizar `.env`

### "Produtos não aparecem"
**Solução:** 
1. Verificar se há produtos no Tiny
2. Ver logs de erro
3. Tentar sincronizar novamente

### "Cliente criado mas sem tinyId"
**Solução:** Normal em caso de erro temporário. Sistema tentará novamente ao finalizar próxima venda desse cliente.

### "Pedido pendente de sincronização"
**Solução:** Usar botão "Sincronizar Agora" na aba Pendentes

---

## 📊 Queries SQL Úteis

### Ver últimas sincronizações
```sql
SELECT 
  operation,
  entity,
  status,
  error_msg,
  created_at
FROM sync_logs
ORDER BY created_at DESC
LIMIT 20;
```

### Ver produtos sincronizados
```sql
SELECT 
  code,
  name,
  tiny_id,
  price,
  stock
FROM products
WHERE tiny_id IS NOT NULL
ORDER BY created_at DESC;
```

### Ver clientes sincronizados
```sql
SELECT 
  name,
  phone,
  tiny_id,
  created_at
FROM customers
WHERE tiny_id IS NOT NULL
ORDER BY created_at DESC;
```

### Ver pedidos sincronizados
```sql
SELECT 
  order_number,
  tiny_id,
  total,
  status,
  completed_at
FROM orders
WHERE tiny_id IS NOT NULL
ORDER BY completed_at DESC;
```

### Ver pedidos pendentes
```sql
SELECT 
  order_number,
  total,
  status,
  created_at
FROM orders
WHERE tiny_id IS NULL 
  AND status = 'COMPLETED'
ORDER BY completed_at DESC;
```

---

## ✅ Critérios de Sucesso

A integração está funcionando corretamente se:

1. ✅ Todos os 6 testes passaram
2. ✅ Logs mostram operações bem-sucedidas
3. ✅ Dados aparecem no Tiny ERP
4. ✅ `tinyId` está preenchido no banco
5. ✅ Retry funciona para erros temporários
6. ✅ Operações locais não são bloqueadas por falhas no Tiny

---

## 📞 Próximos Passos

Após validar a integração:

1. **Usar em produção:**
   - Trocar para token de produção
   - Importar catálogo real
   - Monitorar logs nas primeiras semanas

2. **Monitoramento:**
   - Acompanhar taxa de sucesso
   - Revisar logs de erro regularmente
   - Sincronizar pedidos pendentes manualmente

3. **Manutenção:**
   - Sincronizar produtos 1x por dia
   - Resolver erros de sincronização
   - Atualizar dados no Tiny quando necessário

---

**Data:** 10/01/2026  
**Versão:** 1.0.0  
**Status:** Pronto para Testes! 🚀
