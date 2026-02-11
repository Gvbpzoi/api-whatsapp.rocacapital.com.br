# Goal 2: Busca de Produtos

## Objetivo

Encontrar produtos relevantes baseado na busca do cliente usando full-text search otimizado no Supabase.

---

## Quando Executar

- Cliente menciona produto específico ("queijo", "cachaça", "doce de leite")
- Cliente pergunta "o que vocês têm?"
- Cliente quer ver categoria ("mostre os cafés")

---

## Entradas

| Campo | Tipo | Descrição | Obrigatório |
|-------|------|-----------|-------------|
| `termo_busca` | string | Termo para buscar | ✅ |
| `telefone` | string | Telefone do cliente | ✅ |
| `limite` | int | Máximo de resultados (default: 5) | ❌ |
| `categoria` | string | Filtrar por categoria | ❌ |

---

## Processo

### Passo 1: Normalizar Busca

**Tool:** `tools/products/normalize_search.py`

```python
# Tratar variações e sinônimos
termo_normalizado = normalize_search(termo_busca)

# Exemplos:
# "queijo" → busca também "queijos"
# "cachaça" → busca também "pinga", "branquinha"
# "doce leite" → "doce de leite"
```

### Passo 2: Buscar no Supabase (Cache)

**Tool:** `tools/products/search.py`

```python
produtos = search_products(
    termo=termo_normalizado,
    limite=limite,
    categoria=categoria,
    disponivel=True,  # Apenas produtos em estoque
    canal="whatsapp"   # Disponível para WhatsApp
)
```

**SQL executado:**
```sql
SELECT * FROM buscar_produtos(
  termo_busca := 'queijo',
  limite := 5
);
```

### Passo 3: Enriquecer com Memória

**Tool:** `memory/search.py`

```python
# Buscar preferências do cliente
preferencias = memory_search(f"cliente:{telefone} preferencias")

# Reordenar produtos baseado em histórico
if preferencias:
    produtos = reorder_by_preferences(produtos, preferencias)
```

### Passo 4: Formatar Resposta

**Tool:** `tools/whatsapp/format_response.py`

**Usar template:** `hardprompts/produto_encontrado.txt`

```python
response = format_product_list(
    produtos=produtos,
    termo_busca=termo_busca,
    total_encontrado=len(produtos)
)
```

### Passo 5: Salvar Busca (Analytics)

**Tool:** `tools/analytics/log_search.py`

```python
log_search(
    telefone=telefone,
    termo=termo_busca,
    resultados=len(produtos),
    timestamp=now()
)
```

---

## Tools Necessários

| Tool | Função | Localização |
|------|--------|-------------|
| `normalize_search` | Normalizar termos | `tools/products/normalize_search.py` |
| `search_products` | Buscar no Supabase | `tools/products/search.py` |
| `memory_search` | Buscar preferências | `memory/search.py` |
| `format_product_list` | Formatar lista | `tools/whatsapp/format_response.py` |
| `log_search` | Registrar busca | `tools/analytics/log_search.py` |

---

## Saídas

### Sucesso (Produtos Encontrados)

```json
{
  "status": "success",
  "produtos": [
    {
      "id": "uuid",
      "nome": "Queijo Canastra Meia-Cura 500g",
      "preco": 45.00,
      "estoque": 15,
      "imagem_url": "https://..."
    },
    {
      "id": "uuid",
      "nome": "Queijo Prato Artesanal 400g",
      "preco": 35.00,
      "estoque": 8,
      "imagem_url": "https://..."
    }
  ],
  "total": 2,
  "mensagem_enviada": "Encontrei 2 queijos deliciosos..."
}
```

### Nenhum Produto Encontrado

```json
{
  "status": "not_found",
  "termo_busca": "caviar",
  "mensagem_enviada": "Ops! Não encontrei 'caviar' em nosso estoque no momento..."
}
```

---

## Tratamento de Erros

### Erro: Busca Vazia

```python
if not produtos:
    # Sugerir produtos populares
    populares = get_popular_products(limit=3)

    response = format_no_results(
        termo_busca=termo_busca,
        sugestoes=populares
    )

    # Usar template
    template = load_template("hardprompts/produto_indisponivel.txt")
```

### Erro: Falha no Supabase

```python
try:
    produtos = search_products(termo)
except Exception as e:
    log_error(f"Supabase falhou: {e}")

    # Fallback: buscar direto no Tiny (mais lento)
    produtos = search_tiny_products(termo)

    # Alertar para sync
    notify_admin("Supabase indisponível, usando Tiny")
```

### Erro: Termo Muito Genérico

```python
if termo_normalizado in ["coisa", "produto", "negócio"]:
    response = "Temos muitas opções! Que tipo de produto você procura? Queijos? Cachaças? Doces?"
    return {"status": "too_generic", "mensagem": response}
```

---

## Exemplos de Uso

### Exemplo 1: Busca Específica

**Entrada:**
```json
{
  "termo_busca": "queijo canastra",
  "telefone": "5531999999999",
  "limite": 5
}
```

**Saída:**
```
Encontrei 3 queijos Canastra deliciosos! 🧀

1️⃣ Queijo Canastra Meia-Cura 500g
   💰 R$ 45,00
   📦 15 unidades disponíveis

2️⃣ Queijo Canastra Curado 500g
   💰 R$ 52,00
   📦 8 unidades disponíveis

3️⃣ Queijo Canastra Fresco 500g
   💰 R$ 38,00
   📦 20 unidades disponíveis

Qual deles te interessa? 😊
```

---

### Exemplo 2: Produto Indisponível

**Entrada:**
```json
{
  "termo_busca": "caviar",
  "telefone": "5531988887777"
}
```

**Saída:**
```
Ops! Não encontrei "caviar" em nosso estoque no momento. 😅

Mas temos outros produtos especiais que você pode gostar:

🌟 Mel de Abelha Jataí (produto premium)
🌟 Geleia Artesanal de Jabuticaba
🌟 Azeite Extra Virgem Mineiro

Quer conhecer algum desses?
```

---

### Exemplo 3: Busca por Categoria

**Entrada:**
```json
{
  "termo_busca": "café",
  "telefone": "5531999998888",
  "categoria": "bebidas"
}
```

**Saída:**
```
Temos 5 cafés especiais! ☕

1️⃣ Café Torrado Moído Gourmet 500g - R$ 28,00
2️⃣ Café em Grão Serra da Canastra 500g - R$ 32,00
3️⃣ Café Torrado Moído Tradicional 500g - R$ 22,00
4️⃣ Café em Cápsula (10 un.) - R$ 18,00
5️⃣ Café Solúvel Premium 100g - R$ 15,00

Qual te interessa mais?
```

---

## Contexto Necessário

- `context/produtos_destaque.yaml` - Produtos em destaque
- `context/categorias.yaml` - Mapeamento de categorias
- `context/sinonimos.yaml` - Sinônimos de produtos
- `hardprompts/produto_encontrado.txt` - Template encontrado
- `hardprompts/produto_indisponivel.txt` - Template não encontrado

---

## Métricas

- **Tempo médio:** <100ms (Supabase cache)
- **Taxa de sucesso:** ~85% (produtos encontrados)
- **Buscas mais comuns:** queijo (35%), cachaça (20%), doce (15%)

---

## Melhorias Futuras

- [ ] Busca por imagem (cliente envia foto)
- [ ] Recomendações baseadas em ML
- [ ] Autocomplete de produtos
- [ ] Integração com Google Shopping

---

**Última atualização:** 11/02/2026
**Versão:** 2.0.0-GOTCHA
