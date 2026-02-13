# Correção de Bugs de Alucinação - Implementado

## 📅 Data: 2026-02-13

## ✅ Implementações Concluídas

### 1. **Sistema de Contexto Conversacional** (`session_manager.py`)

#### Adicionado:
- `_conversation_subject`: Rastreia assunto da conversa atual (termo, produtos mostrados, categoria)
- `_product_choices_history`: Histórico de produtos adicionados ao carrinho por categoria

#### Novos Métodos:
- `set_conversation_subject()` - Salva assunto atual da conversa
- `get_conversation_subject()` - Recupera assunto (timeout 10min)
- `get_context_for_classification()` - Retorna contexto resumido para classificador
- `save_product_choice()` - Salva produto adicionado ao carrinho
- `get_last_choice_by_category()` - Recupera última escolha por categoria
- `get_last_choice_by_term()` - Busca escolha por termo de busca
- `_infer_category_from_product()` - Infere categoria do produto
- `_infer_category_from_term()` - Infere categoria do termo de busca

#### Timeout de Contexto:
- **Assunto da conversa**: 10 minutos (600s)
- **Histórico de escolhas**: 30 minutos (1800s)

---

### 2. **Classificação Melhorada com Contexto** (`intent_classifier.py`)

#### Atualizações:
- Método `classify()` agora aceita parâmetro `context`
- Método `classify_with_llm()` agora aceita parâmetro `context`
- Prompt do LLM atualizado com contexto conversacional

#### Novos Padrões Regex para `busca_produto`:
```python
r"(os\s+)?que\s+(voc[eê]|voce|vc)\s+(tem|t[eê]m|vende)",
r"pode\s+(mostrar|mostra|listar)\s+(os\s+)?que",
r"(mostrar|mostra|listar)\s+(os\s+)?que\s+(voc[eê]|voce)\s+(tem|t[eê]m)",
r"\btem\s+mais\b",
r"\boutros?\b",
r"\boutras?\s+op[cç][oõ]es\b",
```

#### Stop Words Atualizadas:
- Adicionado: "você", "voce", "vc", "vocês", "voces", "vcs"
- **Fix**: "pode mostrar os que você tem?" agora extrai corretamente (antes retornava "você")

---

### 3. **Busca com Relevância** (`supabase_produtos.py`)

#### Ordenação por Relevância:
```sql
ORDER BY
    CASE WHEN nome LIKE termo THEN 0 ELSE 1 END,      -- Prioridade 1: Nome
    CASE WHEN categoria LIKE termo THEN 0 ELSE 1 END, -- Prioridade 2: Categoria
    CASE WHEN tags LIKE termo THEN 0 ELSE 1 END,      -- Prioridade 3: Tags
    nome ASC
```

#### Campos de Busca:
1. **Nome** (maior peso)
2. **Categoria**
3. **Tags** (agora incluído)
4. **Descrição** (menor peso)

**Fix**: "azeite" não retorna mais "Abobora C/Coco" (que tinha "azeite" na descrição)

---

### 4. **Ferramentas Aprimoradas** (`tools_helper.py`)

#### Novo Método:
- `adicionar_por_termo()` - Busca produto por termo e adiciona ao carrinho

#### Melhorias:
- `adicionar_carrinho()` retorna `quantidade_total` (soma das quantidades)
- `ver_carrinho()` retorna `quantidade_total` além de `total_itens`

**Fix**: Mensagem agora mostra "Total: 3 produto(s)" em vez de "Total de itens: 1"

---

### 5. **Fluxo Contextual Completo** (`zapi_webhook.py`)

#### Pré-Checagem de Intent:
```python
if _detectar_pergunta_generica_produtos(message):
    intent = "busca_produto"
else:
    context = session_manager.get_context_for_classification(phone)
    intent = intent_classifier.classify(message, context)
```

#### Novo: Detecção de Referência a Escolha:
```python
def _detectar_referencia_a_escolha(message: str) -> bool:
    patterns = [
        r"\bmais\s+(um|uma|dois|duas|\d+)\s+\w+",  # "mais um azeite"
        r"\boutr[oa]\s+\w+",                        # "outro queijo"
        r"\baquele\s+\w+",                          # "aquele azeite"
        r"\bmesm[oa]\s+\w+",                        # "mesmo queijo"
    ]
```

#### Ordem de Resolução do Produto (adicionar_carrinho):

**a) Número explícito**
- "3" → Produto #3 da lista mostrada
- "quero o 2" → Produto #2

**b) Termo específico**
- "dois azeites" → Busca "azeites" e adiciona
- "3 queijos canastra" → Busca "queijos canastra"
- **Detecta referência a escolha**: "mais um azeite" → verifica histórico primeiro

**c) Histórico de escolhas** (NOVO)
- "coloca mais um azeite" → usa "Azeite Extra Virgem" do histórico
- Confirmação proativa: "Adicionei 1x Azeite Extra Virgem Mineiro, aquele que você escolheu antes."

**d) Único produto no contexto**
- Se só mostrou 1 produto → adiciona esse

#### Salvamento de Contexto:
- **Busca de produtos**: salva assunto da conversa
- **Adicionar ao carrinho**: salva escolha no histórico

---

## 🎯 Problemas Corrigidos

### ❌ Antes → ✅ Depois

1. **"pode mostrar os que você tem?"**
   - ❌ Classificado como `adicionar_carrinho` → adicionava produto errado
   - ✅ Classificado como `busca_produto` → mostra produtos

2. **"azeite"**
   - ❌ Retornava "Abobora C/Coco" (tinha "azeite" na descrição)
   - ✅ Retorna produtos com "azeite" no nome primeiro

3. **"dois azeites"**
   - ❌ Adicionava "Queijo Canastra" (produto ID "1" como fallback)
   - ✅ Busca "azeites" e adiciona o correto

4. **"tem mais?"**
   - ❌ Não entendia o contexto
   - ✅ Usa assunto da conversa anterior

5. **"Adicionei 2 item(s). Total: 1"**
   - ❌ Contava linhas do carrinho, não quantidade total
   - ✅ "Adicionei 2 item(s). Total: 2 produto(s)"

6. **"coloca mais um azeite"** (NOVO)
   - ❌ Não lembrava qual azeite foi escolhido
   - ✅ Usa azeite do histórico de escolhas
   - ✅ Confirma: "...aquele que você escolheu antes"

---

## 🧪 Testes Recomendados

### Cenário 1: Busca Genérica Contextual
```
Cliente: "tem azeite?"
Bot: [mostra 5 azeites]

Cliente: "tem mais?"
Bot: [mostra mais azeites] ✅ Usa contexto
```

### Cenário 2: Adicionar por Nome
```
Cliente: "quero dois azeites"
Bot: [busca "azeites" → adiciona 2x Azeite Extra Virgem] ✅
```

### Cenário 3: Relevância da Busca
```
Cliente: "azeite"
Bot: [produtos com "azeite" no NOME aparecem primeiro] ✅
```

### Cenário 4: Total Correto
```
Cliente: "adiciona 2 queijos"
Bot: "Total: 2 produto(s)" ✅ (não "Total: 1")
```

### Cenário 5: Memória de Escolhas (NOVO)
```
Cliente: "tem azeite?"
Bot: [mostra azeites]

Cliente: "vou querer o 3"
Bot: "Adicionei!" [salva: categoria="azeites", produto=Azeite Extra Virgem]

[conversa sobre outros assuntos]

Cliente: "coloca mais um azeite"
Bot: "Adicionei 1x Azeite Extra Virgem Mineiro, aquele que você escolheu antes."
     "Total: 2 produto(s)" ✅
```

### Cenário 6: Múltiplos Assuntos
```
Cliente: "tem azeite?"
Bot: [mostra azeites]
Cliente: "vou querer esse" [adiciona Azeite Extra Virgem]

Cliente: "me mostra uns vinhos"
Bot: [mostra vinhos]
Cliente: "vou querer esse tinto" [adiciona Vinho Tinto]

Cliente: "coloca mais um azeite" 
Bot: [usa Azeite Extra Virgem do histórico] ✅
```

---

## 📊 Métricas de Sucesso

- ✅ "pode mostrar os que você tem?" → `busca_produto`
- ✅ "azeite" → não retorna "Abobora C/Coco"
- ✅ "dois azeites" → adiciona azeite (não queijo)
- ✅ "tem mais?" → usa contexto
- ✅ Total de quantidade correto
- ✅ **"coloca mais um azeite" → usa escolha anterior**
- ✅ **Confirmação proativa quando usar histórico**
- ✅ **Múltiplas escolhas por categoria mantidas**

---

## 🔄 Arquitetura do Sistema

```
Mensagem WhatsApp
    ↓
Pré-checagem (perguntas genéricas)
    ↓
Classificação com Contexto (LLM + Regex)
    ↓
Busca de Produtos (com relevância)
    ↓ [salva assunto + produtos]
Resolução de Produto (4 métodos)
    ↓
Adicionar ao Carrinho
    ↓ [salva escolha por categoria]
Confirmação Proativa (se usar histórico)
```

---

## 💾 Estrutura de Memória

### Contexto de Assunto
```python
{
  "55319999999": {
    "termo": "azeite",
    "timestamp": datetime,
    "produtos_ids": ["uuid-1", "uuid-2", ...],
    "produtos": [{...}, {...}, ...],
    "categoria": "azeites"
  }
}
```

### Histórico de Escolhas
```python
{
  "55319999999": {
    "azeites": {
      "produto": {"id": "uuid-123", "nome": "Azeite Extra Virgem Mineiro", ...},
      "timestamp": datetime,
      "quantidade_total": 3
    },
    "vinhos": {
      "produto": {...},
      "timestamp": datetime,
      "quantidade_total": 2
    }
  }
}
```

---

## 🚀 Próximos Passos (Não Implementado Ainda)

1. **Confirmação com Estado**
   - Implementar estado de "aguardando confirmação"
   - Cliente responde "sim" ou "não" para confirmação proativa

2. **Timeout Visual**
   - Avisar cliente quando escolha está antiga (>30min)
   - "Última vez você escolheu [produto], mas foi há 45 minutos. Quer esse mesmo?"

3. **Integração com Carrinho Persistente**
   - Verificar quantidade já no carrinho ao adicionar
   - Evitar duplicação de mensagens de estoque

4. **Análise de Performance**
   - Medir taxa de acerto LLM vs Regex
   - Tempo médio de resposta
   - Taxa de uso do cache

---

## ⚙️ Configuração

Nenhuma configuração adicional necessária. O sistema usa as mesmas variáveis de ambiente:

```bash
OPENAI_API_KEY=sua-chave-openai
DATABASE_URL=postgresql://...
```

---

## 📝 Notas Técnicas

- **Compatibilidade**: Totalmente compatível com código anterior
- **Performance**: Cache de classificações reduz custo de tokens
- **Memória**: Contexto e escolhas são mantidos apenas em RAM (não persiste em redeploy)
- **Fallback**: Sistema funciona mesmo sem OpenAI (usa apenas regex)

---

**Status**: ✅ Implementado e testado (sintaxe OK)
**Próximo**: Testar em ambiente de desenvolvimento
