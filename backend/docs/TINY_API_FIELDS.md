# Mapeamento Completo de Campos - Tiny API v2

**Endpoint:** `https://api.tiny.com.br/api2/produto.obter.php`
**Documentação:** https://tiny.com.br/api-docs/api2-produtos-obter

---

## Estrutura da Resposta

```json
{
  "retorno": {
    "status": "OK",
    "produto": {
      // CAMPOS AQUI
    }
  }
}
```

---

## Campos Principais (retorno.produto)

### **Identificação**
| Campo | Tipo | Descrição | Exemplo |
|-------|------|-----------|---------|
| `id` | integer | ID único do produto no Tiny | `757165232` |
| `codigo` | string | Código/SKU do produto | `"CAFE001"` |
| `gtin` | string | Código de barras (EAN/UPC) | `"7898954254210"` |
| `ncm` | string | Código fiscal NCM | `"0406.30.00"` |

### **Informações Básicas**
| Campo | Tipo | Descrição | Exemplo |
|-------|------|-----------|---------|
| `nome` | string | Nome do produto | `"Queijo Canastra 500g"` |
| `unidade` | string | Unidade de medida | `"UN"`, `"KG"`, `"LT"` |
| `tipo` | string | Tipo do produto | `"P"` (produto), `"S"` (serviço) |
| `situacao` | string | Situação | `"A"` (ativo), `"I"` (inativo) |
| `classe_produto` | string | Classe do produto | |

### **Descrições** ⭐
| Campo | Tipo | Descrição | Exemplo |
|-------|------|-----------|---------|
| `descricao` | text | Descrição principal do produto | `"Queijo artesanal maturado"` |
| `descricao_complementar` | text | **CAMPO IMPORTANTE** - Descrição detalhada com harmonizações, textura, sabor | `"Intensidade: Média a média-alta..."` |
| `obs` | text | Observações internas | `"site"` (usado para filtrar) |

### **Preços**
| Campo | Tipo | Descrição | Exemplo |
|-------|------|-----------|---------|
| `preco` | decimal | Preço de venda | `45.00` |
| `preco_promocional` | decimal | Preço promocional | `38.00` |
| `preco_custo` | decimal | Preço de custo | `25.00` |
| `preco_custo_medio` | decimal | Preço de custo médio | |

### **Estoque**
| Campo | Tipo | Descrição | Exemplo |
|-------|------|-----------|---------|
| `estoque` | decimal | Quantidade em estoque | `15.00` |
| `estoque_minimo` | decimal | Estoque mínimo | `5.00` |
| `estoque_maximo` | decimal | Estoque máximo | `100.00` |

### **Peso e Dimensões**
| Campo | Tipo | Descrição | Exemplo |
|-------|------|-----------|---------|
| `peso_bruto` | decimal | Peso bruto em kg | `0.550` |
| `peso_liquido` | decimal | Peso líquido em kg | `0.500` |
| `altura` | decimal | Altura em metros | `0.10` |
| `largura` | decimal | Largura em metros | `0.15` |
| `comprimento` | decimal | Comprimento em metros | `0.20` |
| `diametro` | decimal | Diâmetro em metros | |

### **Categoria**
| Campo | Tipo | Descrição | Exemplo |
|-------|------|-----------|---------|
| `categoria` | string | Nome da categoria | `"Queijos"` |
| `id_categoria` | integer | ID da categoria | `123` |

### **Imagens** 📸
| Campo | Tipo | Descrição | Formato |
|-------|------|-----------|---------|
| `imagens` | array | Array de objetos de imagens | Ver estrutura abaixo |

**Estrutura de `imagens`:**
```json
"imagens": [
  {
    "url": "https://example.com/produto.jpg"
  },
  {
    "url": "https://example.com/produto2.jpg"
  }
]
```

### **URL do Produto no Site** 🔗
| Campo | Tipo | Descrição | Exemplo |
|-------|------|-----------|---------|
| `url_produto` | string | **URL do produto no site** | `"https://rocacapital.com.br/produto/queijo-canastra"` |
| `link_produto` | string | Link alternativo (verificar qual existe) | |

### **Fornecedor**
| Campo | Tipo | Descrição | Exemplo |
|-------|------|-----------|---------|
| `id_fornecedor` | integer | ID do fornecedor | |
| `codigo_fornecedor` | string | Código no fornecedor | |

### **Tributação**
| Campo | Tipo | Descrição | Exemplo |
|-------|------|-----------|---------|
| `origem` | string | Origem do produto (0-8) | `"0"` (Nacional) |
| `cest` | string | Código CEST | |
| `classe_ipi` | string | Classe de IPI | |

### **Variações**
| Campo | Tipo | Descrição | Formato |
|-------|------|-----------|---------|
| `variacoes` | array | Variações do produto | Ver documentação Tiny |

### **Outros Campos**
| Campo | Tipo | Descrição | Exemplo |
|-------|------|-----------|---------|
| `garantia` | string | Garantia do produto | `"12 meses"` |
| `localizacao` | string | Localização no estoque | `"Prateleira A1"` |
| `marca` | string | Marca do produto | |
| `modelo` | string | Modelo do produto | |
| `seo_title` | string | Título SEO | |
| `seo_description` | string | Descrição SEO | |
| `seo_keywords` | string | Palavras-chave SEO | |

---

## Campos Críticos para o Bot WhatsApp

### **OBRIGATÓRIOS para funcionalidade completa:**

1. ✅ **`id`** - Identificação única
2. ✅ **`nome`** - Nome do produto
3. ✅ **`descricao`** - Descrição básica
4. ⭐ **`descricao_complementar`** - **ESSENCIAL** para harmonizações e detalhes
5. ✅ **`preco`** - Preço de venda
6. ✅ **`preco_promocional`** - Preço promocional (se houver)
7. ✅ **`estoque`** - Quantidade disponível
8. ✅ **`imagens`** - Fotos do produto
9. ⭐ **`url_produto`** - **ESSENCIAL** para compartilhar link com cliente
10. ✅ **`categoria`** - Categorização
11. ✅ **`unidade`** - Unidade de venda
12. ✅ **`peso_bruto/peso_liquido`** - Para cálculo de frete

### **ÚTEIS mas não críticos:**
- `obs` - Usado para filtrar produtos com "site"
- `codigo` - SKU para referência
- `gtin` - Código de barras
- `situacao` - Ativo/Inativo

---

## Como Usar no Código

### **1. Buscar produto completo:**
```python
produto_completo = await client.obter_produto(produto_id)
# Retorna TODOS os campos de retorno.produto
```

### **2. Acessar campos:**
```python
descricao = produto_completo.get("descricao", "")
descricao_complementar = produto_completo.get("descricao_complementar", "")
url_site = produto_completo.get("url_produto", "")
imagens = produto_completo.get("imagens", [])
```

### **3. Imagens:**
```python
imagens = produto_completo.get("imagens", [])
primeira_imagem = imagens[0]["url"] if imagens else None
```

---

## Notas Importantes

1. **Campos condicionais:** Alguns campos só aparecem se preenchidos no Tiny
2. **descricao_complementar:** Campo text-condicional - pode não existir se vazio
3. **imagens:** Sempre verificar se array não está vazio
4. **url_produto vs link_produto:** Verificar qual campo o Tiny retorna (pode variar)
5. **Observações:** Campo `obs` é usado para filtrar produtos que devem aparecer no site

---

## Mapeamento para produtos_site (Supabase)

| Tiny API | produtos_site | Transformação |
|----------|---------------|---------------|
| `id` | `tiny_id` | Converter para text |
| `codigo` | - | (não usado) |
| `nome` | `nome` | Direto |
| `descricao` + `descricao_complementar` | `descricao` | Combinar com "\n\n" |
| `preco` | `preco` | Direto |
| `preco_promocional` | `preco_promocional` | Direto |
| `peso_bruto` ou `peso_liquido` | `peso` | Converter para text |
| `unidade` | `unidade` | Direto |
| `imagens[0]["url"]` | `imagem_url` | Primeira imagem |
| `imagens` | `imagens_adicionais` | Array completo (jsonb) |
| `url_produto` | `link_produto` | Direto |
| `categoria` | `categoria` | Direto |
| `estoque` > 0 | `estoque_disponivel` | Boolean |
| `estoque` | `quantidade_estoque` | Integer |
| `situacao` == "A" | `ativo` | Boolean |

---

**Última atualização:** 2026-02-12
**Referência:** https://tiny.com.br/api-docs/api2-produtos-obter
