# 🔍 Filtro de Produtos Kit - Tiny ERP

**Data:** 12/01/2026  
**Versão:** 1.0.0  
**Status:** ✅ Implementado

---

## 📋 Resumo

Implementado filtro na sincronização de produtos do Tiny ERP para **não importar produtos do tipo Kit** no PDV.

### Motivação

Produtos do tipo "Kit" no Tiny ERP são conjuntos/pacotes de outros produtos. Esses produtos não devem ser baixados no PDV pois:

1. **Kit não é vendido diretamente** - É apenas uma composição de produtos
2. **Contém lista de itens** (`kit[].item`) que são os produtos reais
3. **Gerenciamento complexo** - Estoque e preço são calculados a partir dos itens
4. **PDV vende os itens individuais** - Não o kit em si

### Documentação Oficial

Baseado na API Tiny ERP: https://api.tiny.com.br/docs/api2/produtos/obter-produto

```
retorno.produto.classe_produto (9)	string	1	obrigatório	Classificação do produto.

Valores possíveis:
- S = Simples
- K = Kit         ← NÃO QUEREMOS ESTE
- V = Com variações
- F = Fabricado
- M = Matéria-prima

retorno.produto.kit[] (10)	list	-	condicional [0..n]	Lista contendo os itens do kit do produto.
retorno.produto.kit[].item	object	-	condicional	Elemento utilizado para representar um item do kit.
retorno.produto.kit[].item.id_produto	int	-	obrigatório	Número de identificação do produto na Olist.
retorno.produto.kit[].item.quantidade	decimal	-	obrigatório	Quantidade do produto dentro do kit.
```

---

## ✅ Mudanças Implementadas

### 1. TinyServiceV3.ts (API v3)

**Arquivo:** `pdv-system/apps/backend/src/integrations/tiny/TinyServiceV3.ts`

**Mudança:** Linha ~326

```typescript
// ANTES: Filtrava apenas por tipo (S, P, K, V, E)
const produtosValidos = produtos.filter((p: any) => {
  const tipo = (p.tipo || 'S').toUpperCase();
  const isValido = tipo === 'S' || tipo === 'P' || tipo === '';
  const isRejeitado = tipo === 'K' || tipo === 'V' || tipo === 'E';
  return isValido && !isRejeitado;
});

// DEPOIS: Filtra por tipoVariacao E classe_produto
const produtosValidos = produtos.filter((p: any) => {
  const tipoVariacao = (p.tipoVariacao || p.tipo || 'N').toUpperCase();
  const classeProduto = (p.classe_produto || 'S').toUpperCase();
  
  // FILTRO 1: Tipo de variação - Aceitar apenas "N" (Normal)
  const isTipoValido = tipoVariacao === 'N' || tipoVariacao === '';
  
  // FILTRO 2: Classe de produto - Rejeitar "K" (Kit)
  const isKit = classeProduto === 'K';
  
  // FILTRO 3: Rejeitar variações (tipo V ou P)
  const isVariacao = tipoVariacao === 'V' || tipoVariacao === 'P';
  
  // Aceitar se: é tipo Normal E não é Kit E não é Variação
  return isTipoValido && !isKit && !isVariacao;
});
```

### 2. TinyService.ts (API v2)

**Arquivo:** `pdv-system/apps/backend/src/integrations/tiny/TinyService.ts`

**Mudança:** Linha ~878

```typescript
// ANTES: Filtros comentados/desabilitados
// const tipoVariacao = p.tipoVariacao || p.tipo;
// if (tipoVariacao && tipoVariacao !== 'N') {
//   result.skipped++;
//   continue;
// }

// DEPOIS: Filtros ativos para kit e variações
const tipoVariacao = (p.tipoVariacao || p.tipo || 'N').toUpperCase();
const classeProduto = (p.classe_produto || 'S').toUpperCase();

// REGRA 1: Rejeitar produtos do tipo Kit (classe_produto = 'K')
if (classeProduto === 'K') {
  console.log(`[TinyService] ⏭️ Produto ${produto.codigo} pulado: classe_produto = "K" (Kit - não baixar no PDV)`);
  result.skipped++;
  result.details.push({
    code: produto.codigo,
    status: 'skipped',
    error: `Produto do tipo Kit - Não é baixado no PDV`,
  });
  continue;
}

// REGRA 2: Rejeitar produtos que são variações (tipoVariacao != 'N')
if (tipoVariacao !== 'N' && tipoVariacao !== '') {
  console.log(`[TinyService] ⏭️ Produto ${produto.codigo} pulado: tipoVariacao = "${tipoVariacao}" (não é Normal)`);
  result.skipped++;
  result.details.push({
    code: produto.codigo,
    status: 'skipped',
    error: `Tipo de variação "${tipoVariacao}" - Apenas produtos normais (N) são importados`,
  });
  continue;
}
```

### 3. Documentação Atualizada

**Arquivo:** `docs/integrations/TINY_ERP.md`

Adicionado:
- ✅ Seção explicando tipos de produtos aceitos vs. rejeitados
- ✅ Tabela com campo `classe_produto` e seus valores
- ✅ Tabela com campo `tipoVariacao` e seus valores
- ✅ Exemplos de logs de sincronização
- ✅ Motivos para rejeição de cada tipo

---

## 📊 Regras de Negócio

### Produtos Aceitos ✅

| Campo | Valor | Descrição |
|-------|-------|-----------|
| `tipoVariacao` | **N** | Normal (produto simples) |
| `classe_produto` | **S** | Simples |
| `classe_produto` | **F** | Fabricado/Manufaturado |
| `classe_produto` | **M** | Matéria-prima |

### Produtos Rejeitados ❌

| Campo | Valor | Descrição | Motivo |
|-------|-------|-----------|--------|
| `classe_produto` | **K** | Kit | Conjunto de produtos - não vende direto |
| `tipoVariacao` | **P** | Pai | Produto pai de variações |
| `tipoVariacao` | **V** | Variação | Variação de um produto pai |
| `classe_produto` | **V** | Com variações | Produto com variações |

### Campos Ignorados (SEO)

Não são importados para o PDV:
- ❌ `seo_title`
- ❌ `seo_keywords`
- ❌ `seo_description`
- ❌ `slug`
- ❌ `link_video`

---

## 🧪 Como Testar

### 1. Sincronizar Produtos

```bash
# Via API
curl -X POST http://localhost:3000/api/tiny/sync/products \
  -H "Authorization: Bearer seu_token_jwt"

# Via Mobile
1. Login como Admin
2. Ir em "Sincronização"
3. Clicar "Sincronizar Produtos"
4. Ver resultado: X importados, Y ignorados (kits/variações)
```

### 2. Verificar Logs

Os logs mostrarão produtos ignorados:

```
[TinyServiceV3] ✅ Página 1: 45 produtos válidos, 5 ignorados
[TinyServiceV3] ⏭️ Produto KIT-001 pulado: classe_produto = "K" (Kit - não baixar no PDV)
[TinyServiceV3] ⏭️ Produto VAR-PAI pulado: tipoVariacao = "P" (Pai de variação)
[TinyServiceV3] ⏭️ Produto VAR-001 pulado: tipoVariacao = "V" (Variação)
```

### 3. Verificar Banco de Dados

```sql
-- Ver produtos importados
SELECT id, code, name, tiny_id, category 
FROM products 
WHERE tiny_id IS NOT NULL
ORDER BY created_at DESC
LIMIT 20;

-- Nenhum produto com classe_produto = 'K' deve existir
-- (Não temos esse campo no banco, pois rejeitamos antes de salvar)
```

### 4. Verificar Sync Logs

```sql
-- Ver logs de sincronização
SELECT 
  operation,
  entity,
  status,
  error_msg,
  created_at
FROM sync_logs
WHERE operation = 'import_products'
  AND status = 'SUCCESS'
ORDER BY created_at DESC
LIMIT 10;
```

---

## 📝 Exemplos

### Exemplo 1: Produto Simples ✅ ACEITO

```json
{
  "id": "123456",
  "descricao": "Camiseta Básica Preta",
  "sku": "CAM-001",
  "classe_produto": "S",
  "tipoVariacao": "N",
  "situacao": "A",
  "precos": {
    "preco": 49.90
  }
}
```

**Resultado:** ✅ Importado com sucesso

---

### Exemplo 2: Produto Kit ❌ REJEITADO

```json
{
  "id": "789012",
  "descricao": "Kit Presente - 3 Camisetas",
  "sku": "KIT-001",
  "classe_produto": "K",
  "tipoVariacao": "N",
  "situacao": "A",
  "kit": [
    {
      "item": {
        "id_produto": 123456,
        "quantidade": 3
      }
    }
  ],
  "precos": {
    "preco": 129.90
  }
}
```

**Resultado:** ❌ Ignorado - "Produto do tipo Kit - Não é baixado no PDV"

---

### Exemplo 3: Produto Pai de Variações ❌ REJEITADO

```json
{
  "id": "345678",
  "descricao": "Camiseta Básica (Várias Cores)",
  "sku": "CAM-PAI",
  "classe_produto": "V",
  "tipoVariacao": "P",
  "situacao": "A",
  "variacoes": [
    {
      "variacao": {
        "id": 345679,
        "codigo": "CAM-PRETA",
        "grade": { "Cor": "Preto" }
      }
    },
    {
      "variacao": {
        "id": 345680,
        "codigo": "CAM-BRANCA",
        "grade": { "Cor": "Branco" }
      }
    }
  ]
}
```

**Resultado:** ❌ Ignorado - "Tipo de variação 'P' - Apenas produtos normais (N) são importados"

---

### Exemplo 4: Variação de Produto ❌ REJEITADO

```json
{
  "id": "345679",
  "descricao": "Camiseta Básica Preta",
  "sku": "CAM-PRETA",
  "classe_produto": "V",
  "tipoVariacao": "V",
  "idProdutoPai": 345678,
  "situacao": "A",
  "precos": {
    "preco": 49.90
  }
}
```

**Resultado:** ❌ Ignorado - "Tipo de variação 'V' - Apenas produtos normais (N) são importados"

---

## 🎯 Impacto

### Antes da Mudança

- ⚠️ Importava **TODOS** os produtos (incluindo kits)
- ⚠️ Vendedores viam produtos que não podiam vender diretamente
- ⚠️ Produtos kit causavam confusão no PDV
- ⚠️ Gestão de estoque inconsistente (kit vs. itens do kit)

### Depois da Mudança

- ✅ Importa **apenas produtos vendáveis**
- ✅ PDV mostra apenas produtos simples (N)
- ✅ Kits são ignorados automaticamente
- ✅ Variações de produtos são ignoradas
- ✅ Logs claros sobre produtos rejeitados
- ✅ Sincronização mais rápida (menos produtos)

---

## 🔍 Troubleshooting

### Problema: "Produto X não aparece no PDV"

**Diagnóstico:**
1. Verificar logs de sincronização
2. Buscar pelo código do produto nos logs

**Possíveis causas:**
- Produto é do tipo Kit (`classe_produto = 'K'`)
- Produto é pai de variações (`tipoVariacao = 'P'`)
- Produto é uma variação (`tipoVariacao = 'V'`)

**Solução:**
- Se for kit: Sincronizar os itens do kit individualmente (se forem produtos normais)
- Se for variação: Tiny ERP gerencia variações automaticamente no e-commerce, mas no PDV vende-se o produto pai ou variações como produtos simples separados

---

### Problema: "Quero vender um kit no PDV"

**Resposta:**
Kits não são sincronizados propositalmente. Alternativas:

1. **Opção 1:** Criar o kit manualmente no PDV como um produto normal
2. **Opção 2:** Vender os itens do kit separadamente
3. **Opção 3:** No Tiny, mudar o kit para produto simples (classe_produto = 'S')

---

### Problema: "Como ver quais produtos foram ignorados?"

**Via API:**
```bash
curl http://localhost:3000/api/sync/logs?entity=product&status=SUCCESS \
  -H "Authorization: Bearer seu_token"
```

**Via Logs do Backend:**
```bash
# Ver últimas 50 linhas dos logs
tail -n 50 /tmp/pdv-backend.log | grep "pulado"
```

**Via Banco:**
```sql
SELECT * FROM sync_logs
WHERE operation = 'import_products'
  AND error_msg LIKE '%pulado%'
ORDER BY created_at DESC;
```

---

## 📚 Referências

- [Tiny ERP API - Obter Produto](https://api.tiny.com.br/docs/api2/produtos/obter-produto)
- [Tiny ERP API - Pesquisar Produtos](https://api.tiny.com.br/docs/api2/produtos/pesquisar-produtos)
- [Documentação Integração Tiny ERP](./TINY_ERP.md)
- [Endpoints API](../api/ENDPOINTS.md)

---

## 📅 Histórico de Mudanças

| Data | Versão | Descrição |
|------|--------|-----------|
| 12/01/2026 | 1.0.0 | Implementação inicial do filtro de produtos kit |

---

**Desenvolvido por:** Claude + Guilherme Vieira  
**Última Atualização:** 12/01/2026
