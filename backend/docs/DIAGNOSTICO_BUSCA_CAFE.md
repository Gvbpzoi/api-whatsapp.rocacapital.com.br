# Diagnóstico: Por que o bot não encontra produtos de café?

**Data:** 2026-02-12
**Status:** 🔴 PROBLEMA IDENTIFICADO

---

## 🔍 Problema

O usuário testou a busca no WhatsApp com "cafes" mas o bot respondeu:
> "Puxa, não encontrei nenhum produto com esse termo não."

Mesmo tendo sincronizado com sucesso 29 produtos, incluindo 9 produtos de café:
- "1Kg Cafe Torrado Em Graos - Perfil Chocolate"
- "Café Roça Capital Melodia - 250g"
- E outros 7 produtos de café

---

## 🧪 Análise Técnica

### 1. Como funciona a busca

O método `buscar_produtos()` em `supabase_produtos.py` (linhas 96-98):

```python
if apenas_disponiveis:
    query += " AND ativo = TRUE AND estoque_disponivel = TRUE"
```

**Isso significa:** A busca **só retorna produtos que estão ativos E com estoque disponível.**

### 2. Como os produtos são sincronizados

No `tiny_products_client.py` (linha 261):

```python
"ativo": produto.get("situacao") == "A"
```

**Produtos são marcados como ativos apenas se `situacao = "A"` no Tiny.**

No `sync_produtos_tiny.py` (linha 150):

```python
estoque_disponivel = produto["estoque"] > 0
```

**Produtos só têm estoque disponível se quantidade > 0 no Tiny.**

---

## 🎯 Causa Raiz (Provável)

Os produtos de café estão no Supabase, **MAS**:

### Hipótese 1: Produtos inativos no Tiny
- Os produtos de café têm `situacao = "I"` (Inativo) no Tiny ERP
- Foram sincronizados com `ativo = FALSE` no Supabase
- A busca filtra por `ativo = TRUE` → **produtos não aparecem**

### Hipótese 2: Produtos sem estoque
- Os produtos de café têm `estoque = 0` no Tiny ERP
- Foram sincronizados com `estoque_disponivel = FALSE` no Supabase
- A busca filtra por `estoque_disponivel = TRUE` → **produtos não aparecem**

### Hipótese 3: Problema com acentuação
- Usuário digitou "cafes" (sem acento)
- Produtos estão como "Café" (com acento) no banco
- PostgreSQL sem extensão `unaccent` → **busca LIKE não encontra**

---

## ✅ Como Confirmar

Execute esta query SQL no Supabase para verificar:

```sql
-- 1. Ver TODOS os produtos de café (ativos ou não)
SELECT
    nome,
    ativo,
    estoque_disponivel,
    quantidade_estoque,
    categoria
FROM produtos_site
WHERE LOWER(nome) LIKE '%café%' OR LOWER(nome) LIKE '%cafe%'
ORDER BY ativo DESC, estoque_disponivel DESC;

-- 2. Contar por status
SELECT
    ativo,
    estoque_disponivel,
    COUNT(*) as total
FROM produtos_site
WHERE LOWER(nome) LIKE '%café%' OR LOWER(nome) LIKE '%cafe%'
GROUP BY ativo, estoque_disponivel;
```

---

## 🛠️ Soluções

### Solução 1: Ativar produtos no Tiny ERP

**Se o problema for produtos inativos:**

1. Abrir Tiny ERP
2. Ir em Produtos → Localizar produtos de café
3. Mudar `Situação` de "Inativo" para "Ativo"
4. Rodar sincronização novamente:
   ```bash
   docker exec -it <container> python backend/scripts/sync_produtos_tiny.py
   ```

### Solução 2: Atualizar estoque no Tiny ERP

**Se o problema for estoque zerado:**

1. Abrir Tiny ERP
2. Ir em Estoque → Atualizar quantidade dos produtos de café
3. Rodar sincronização novamente

### Solução 3: Modificar filtros da busca (TEMPORÁRIO)

**Para testar se os produtos estão lá mas apenas inativos/sem estoque:**

Editar `src/orchestrator/tools_helper.py` linha ~250:

```python
# ANTES (só produtos ativos com estoque)
produtos = self.produtos_service.buscar_produtos(
    termo=termo,
    limite=limite,
    apenas_disponiveis=True  # <-- MUDAR PARA FALSE
)

# DEPOIS (todos os produtos, mesmo inativos)
produtos = self.produtos_service.buscar_produtos(
    termo=termo,
    limite=limite,
    apenas_disponiveis=False  # <-- PERMITE INATIVOS E SEM ESTOQUE
)
```

⚠️ **Atenção:** Isso vai mostrar produtos sem estoque para o cliente, o que não é ideal.

### Solução 4: Ativar extensão UNACCENT (Recomendado)

**Para resolver problema de acentuação:**

Execute no Supabase SQL Editor:

```sql
CREATE EXTENSION IF NOT EXISTS unaccent;
```

Depois, modificar `supabase_produtos.py` linhas 107-112:

```python
# ANTES
query += """
    AND (
        LOWER(nome) LIKE LOWER(%s)
        OR LOWER(descricao) LIKE LOWER(%s)
        OR LOWER(categoria) LIKE LOWER(%s)
    )
"""

# DEPOIS (ignora acentos)
query += """
    AND (
        unaccent(LOWER(nome)) LIKE unaccent(LOWER(%s))
        OR unaccent(LOWER(descricao)) LIKE unaccent(LOWER(%s))
        OR unaccent(LOWER(categoria)) LIKE unaccent(LOWER(%s))
    )
"""
```

Isso permite que "cafes" encontre "Café", "queijo" encontre "Queijão", etc.

### Solução 5: Normalizar busca no código

**Alternativa à extensão UNACCENT:**

Criar função para remover acentos no Python antes de buscar:

```python
import unicodedata

def normalizar_termo(texto: str) -> str:
    """Remove acentos e normaliza texto para busca"""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    ).lower()

# Uso na busca
termo_normalizado = normalizar_termo(termo)
```

---

## 🎯 Recomendação Final

**Passo a passo:**

1. ✅ **Executar query SQL** para confirmar causa raiz
2. ✅ **Se produtos inativos:** Ativar no Tiny + re-sync
3. ✅ **Se sem estoque:** Atualizar estoque no Tiny + re-sync
4. ✅ **Instalar UNACCENT** no PostgreSQL (1 comando SQL)
5. ✅ **Modificar busca** para usar `unaccent()`
6. ✅ **Testar** novamente no WhatsApp

---

## 📊 Script de Teste

Execute para verificar status dos produtos:

```bash
docker exec -it <container> python backend/scripts/test_busca_cafe.py
```

Este script vai mostrar:
- Total de produtos ativos
- Todos os produtos no banco
- Resultados de busca com "cafe" (sem acento)
- Resultados de busca com "café" (com acento)
- Produtos inativos ou sem estoque

---

## 📝 Notas

- **Sync funcionou:** 29 produtos foram sincronizados com sucesso
- **Produtos existem:** Logs mostram produtos de café foram processados
- **Busca não retorna:** Filtros de `ativo` e `estoque_disponivel` estão bloqueando
- **Próximo passo:** Verificar status no Supabase com query SQL

---

**Desenvolvido com ❤️ para a Roça Capital**
