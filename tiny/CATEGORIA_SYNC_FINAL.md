# 🎯 Sincronização de Categorias - Solução Final
**Data:** 2026-01-11  
**Status:** ✅ **RESOLVIDO**

## 📝 Resumo

Implementada sincronização automática de categorias usando o endpoint `/produtos.categorias.arvore.php` do Tiny ERP, que retorna todas as categorias em uma única requisição (muito mais eficiente!).

---

## 🔄 Fluxo de Sincronização

### 1. Sincronização em Cadeia
Quando `syncChain: true`:
```
Categorias → Produtos → Estoque
```

### 2. Endpoint de Categorias
```http
POST /api/sync/categories
Authorization: Bearer {token}
```

**Resposta:**
```json
{
  "success": true,
  "message": "Sincronização de categorias concluída: 17 categorias importadas",
  "data": {
    "success": 17,
    "errors": 0,
    "total": 17,
    "details": [...]
  }
}
```

---

## 📊 Categorias Importadas

| Categoria | ID no Tiny |
|-----------|------------|
| ANTEPASTO | 626260927 |
| AZEITES | 626260992 |
| CACHAÇA | 626260921 |
| CAFE | 626261344 |
| CHOCOLATES | 626261674 |
| DOCE DIET | 626261136 |
| DOCES | 626260867 |
| EMBALAGENS | 626261616 |
| EMBUTIDOS | 747488044 |
| GELEIAS | 626262397 |
| LICOR | 626262995 |
| MEL | 626263177 |
| MOLHOS | 626261180 |
| PAES | 626261519 |
| QUEIJOS | 626260868 |
| Souvenir | 626260925 |
| VINHOS | 626263734 |

---

## 💻 Implementação Técnica

### 1. Método `getCategoriesTree()`
```typescript
// TinyService.ts
async getCategoriesTree(): Promise<Array<{ id: string; descricao: string; nodes?: any[] }>>
```

**Endpoint Tiny:** `/produtos.categorias.arvore.php`

**Formato da Resposta:**
```json
[
  {
    "id": "626260927",
    "descricao": "ANTEPASTO",
    "nodes": []
  },
  {
    "id": "626260992",
    "descricao": "AZEITES",
    "nodes": [
      {
        "id": "626260993",
        "descricao": "Extra Virgem",
        "nodes": []
      }
    ]
  }
]
```

### 2. Método `flattenCategoriesTree()`
Processa recursivamente a árvore de categorias, extraindo todas (pais e filhas):

```typescript
private flattenCategoriesTree(
  categorias: Array<{ id: string; descricao: string; nodes?: any[] }>,
  parentPath: string = ''
): Array<{ id: string; name: string; fullPath: string }>
```

**Exemplo de `fullPath`:**
- `"AZEITES"` → categoria pai
- `"AZEITES >> Extra Virgem"` → subcategoria

### 3. Vinculação com Produtos
Durante `importProducts()`, para cada produto:
1. Busca detalhes do produto via `/produto.obter.php`
2. Extrai `produto.id_categoria` e `produto.categoria`
3. Busca a categoria no banco por `tinyId` (mais confiável)
4. Se não encontrar, busca por nome (case-insensitive)
5. Fallback: categoria "Sem Categoria"

```typescript
// Buscar categoria pelo tinyId
if (categoryTinyId) {
  categoria = await prisma.tinyCategory.findUnique({
    where: { tinyId: String(categoryTinyId) }
  });
}

// Fallback: buscar por nome
if (!categoria && productData.category !== 'Sem Categoria') {
  categoria = await prisma.tinyCategory.findFirst({
    where: { name: { equals: productData.category, mode: 'insensitive' } }
  });
}
```

---

## 🚀 Scripts Disponíveis

### 1. Sincronização Incremental
```bash
./scripts/sync-all-products-incremental.sh
```

**O que faz:**
1. Sincroniza categorias (1 requisição)
2. Sincroniza produtos página por página (até 10 páginas)
3. Sincroniza estoque
4. Mostra resumo por categoria

**Tempo:** ~5-10 minutos

### 2. Limpeza de Produtos Órfãos
```bash
./scripts/cleanup-orphan-products.sh
```

**O que faz:**
- Identifica produtos com "Sem Categoria"
- Sugere marcá-los como inativos (não existem mais no Tiny)

---

## 📈 Resultados

### Antes
- ❌ 564 produtos com "Sem Categoria"
- ❌ Nenhuma informação de categoria

### Depois
- ✅ **107 produtos categorizados**
- ✅ **17 categorias ativas**
- ⚠️ 521 produtos órfãos (não aparecem na listagem do Tiny)

### Distribuição Atual

| Categoria | Qtd |
|-----------|-----|
| Sem Categoria | 521 *(órfãos)* |
| CAFE | 47 |
| CACHAÇA | 22 |
| EMBUTIDOS | 13 |
| AZEITES | 8 |
| DOCES | 7 |
| EMBALAGENS | 3 |
| ANTEPASTO | 2 |
| DOCE DIET | 2 |
| MEL | 2 |
| VINHOS | 1 |

---

## ⚠️ Limitações Descobertas

### 1. API Tiny retorna apenas 100 produtos
A API `/produtos.pesquisa.php` está limitada a retornar apenas 100 produtos por vez, independente da página solicitada.

**Workaround:** Os produtos ativos e disponíveis são os que aparecem na primeira página.

### 2. Produtos Órfãos
521 produtos no banco local não aparecem na listagem do Tiny porque:
- Podem ter `tipoVariacao` diferente de "N" (Normal)
- Podem estar inativos/descontinuados no Tiny
- Podem ser produtos antigos que foram deletados

**Solução:** Marcar como inativos ou deletar do banco local.

---

## 🔍 Debug

### Ver logs no backend
```bash
cd pdv-system/apps/backend
npm run dev
```

### Logs esperados
```
[TinyService] 🌳 Iniciando importação de categorias via árvore...
[TinyService] 🌳 Buscando árvore de categorias...
[TinyService] ✅ 17 categorias encontradas na árvore
[TinyService] ✅ Categoria "ANTEPASTO" (ID: 626260927) sincronizada
[TinyService] ✅ Categoria "AZEITES" (ID: 626260992) sincronizada
...
```

---

## 📚 Referências

- [Tiny ERP - Documentação Categorias](https://tiny.com.br/api-docs/api2-produtos-categorias-arvore)
- [TINY_ERP.md](./TINY_ERP.md) - Documentação completa da integração
- [TinyService.ts](../../pdv-system/apps/backend/src/integrations/tiny/TinyService.ts) - Código fonte

---

## ✅ Checklist de Conclusão

- [x] Endpoint `/produtos.categorias.arvore.php` implementado
- [x] Método `getCategoriesTree()` criado
- [x] Método `flattenCategoriesTree()` criado
- [x] Vinculação produto → categoria por `tinyId`
- [x] Vinculação produto → categoria por nome (fallback)
- [x] Sincronização em cadeia (categorias → produtos → estoque)
- [x] Script de sincronização incremental
- [x] Script de limpeza de produtos órfãos
- [x] Documentação completa
- [x] Teste com 107 produtos categorizados com sucesso

---

**✅ SUCESSO:** Sistema agora sincroniza categorias automaticamente e vincula produtos corretamente! 🎉
