# Setup de Carrinhos Persistentes

## **O que isso resolve**

Antes: Carrinhos eram perdidos no redeploy (armazenados em RAM)
Depois: Carrinhos persistem no Supabase (sobrevivem a redeploys)

## **Passo 1: Executar Migration no Supabase**

1. Acesse seu projeto no Supabase: https://supabase.com/dashboard
2. Vá em **SQL Editor**
3. Cole o conteúdo de `backend/migrations/002_carrinhos_persistentes.sql`
4. Execute (Run)

Isso cria:
- Tabela `carrinhos` - carrinhos persistentes
- Tabela `sessoes_contexto` - contexto de produtos mostrados
- Triggers automáticos de atualização
- Função de limpeza de dados antigos

## **Passo 2: Configurar Variável de Ambiente**

No EasyPanel, adicione:

```bash
SUPABASE_DB_URL=postgresql://postgres.[SEU-PROJETO]:[SUA-SENHA]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

**Como obter a URL:**
1. No Supabase, vá em **Settings** → **Database**
2. Em **Connection String**, copie a **Transaction** (pooler mode)
3. Substitua `[YOUR-PASSWORD]` pela sua senha do banco

## **Passo 3: Rebuild no EasyPanel**

Após adicionar a variável, faça rebuild da aplicação.

## **Como Funciona**

### **Carrinho Persistente (Supabase)**

Quando `SUPABASE_DB_URL` está configurada:

```python
# Cliente adiciona produto
tools_helper.adicionar_carrinho(phone, produto_id, quantidade)
→ Salva no Supabase (tabela carrinhos)

# Redeploy acontece
→ Carrinho continua no banco

# Cliente pede para ver carrinho
tools_helper.ver_carrinho(phone)
→ Busca do Supabase
→ Mostra produtos corretos!
```

### **Fallback para Memória**

Se `SUPABASE_DB_URL` não estiver configurada, usa modo antigo (RAM):

```python
# Carrinhos em memória (self.carrinhos = {})
# ⚠️ Perdidos no redeploy
```

## **Logs para Verificar**

```bash
✅ Conectado ao Supabase para carrinhos persistentes
✅ Usando carrinhos persistentes (Supabase)
```

Se ver:
```bash
⚠️ Supabase não disponível, usando carrinhos em memória
```

→ Verifique se `SUPABASE_DB_URL` está correta

## **Manutenção**

### **Limpar Carrinhos Antigos**

Execute manualmente no Supabase (SQL Editor):

```sql
SELECT limpar_dados_antigos();
```

Isso remove:
- Carrinhos não atualizados há mais de 7 dias
- Sessões expiradas (>30 minutos)

### **Ver Carrinhos Ativos**

```sql
SELECT telefone, COUNT(*) as itens, SUM(subtotal) as total
FROM carrinhos
GROUP BY telefone
ORDER BY atualizado_em DESC;
```

### **Ver Sessões Ativas**

```sql
SELECT telefone, ultima_busca, atualizado_em
FROM sessoes_contexto
WHERE expira_em > NOW()
ORDER BY atualizado_em DESC;
```

## **Benefícios**

✅ **Carrinhos sobrevivem a redeploys**
✅ **Cliente pode fechar WhatsApp e voltar depois**
✅ **Múltiplos servidores compartilham dados**
✅ **Backup automático do Supabase**
✅ **Fallback para memória se Supabase não disponível**

## **Próximos Passos (Opcional)**

1. **Integração com Tiny ERP**: salvar pedidos finalizados
2. **Redis para cache**: histórico de conversa
3. **Webhooks**: notificar quando produto voltar ao estoque
