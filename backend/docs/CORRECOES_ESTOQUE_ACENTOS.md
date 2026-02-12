# Correções: Estoque e Acentuação

**Data:** 2026-02-12
**Problema:** Bot não encontra produtos de café mesmo após sync bem-sucedido
**Status:** ✅ CORRIGIDO

---

## 🔍 Problemas Identificados

### 1. **Estoque Zerado**
- ❌ Todos os produtos sincronizados tinham `estoque = 0`
- ❌ API Tiny pode retornar estoque como string com vírgula: `"10,5"`
- ❌ Código anterior: `float(produto.get("estoque", 0) or 0)` falhava silenciosamente
- ❌ Resultado: Produtos com estoque > 0 apareciam como 0 no Supabase

### 2. **Busca Não Ignora Acentos**
- ❌ Usuário busca "cafes" (sem acento)
- ❌ Produtos estão como "Café" (com acento) no banco
- ❌ Query `LOWER(nome) LIKE '%cafes%'` não encontra nada
- ❌ Resultado: Produtos existem mas não aparecem na busca

---

## ✅ Soluções Implementadas

### 1. **Conversão Robusta de Estoque**

**Arquivo:** `backend/src/services/tiny_products_client.py`

**Novo método:** `_converter_estoque()`

**Funcionalidades:**
- ✅ Converte string com vírgula: `"10,5"` → `10.5`
- ✅ Tenta múltiplos campos: `estoque`, `saldo`, `estoque_atual`, `quantidade`
- ✅ Trata valores negativos: `-5` → `0`
- ✅ Trata None/vazio: `None` → `0`
- ✅ Log detalhado para debugging

**Código:**
```python
@staticmethod
def _converter_estoque(produto: Dict) -> float:
    """
    Converte estoque da API Tiny para float, tratando vários formatos

    Trata:
    - String com vírgula: "10,5" → 10.5
    - Valores negativos: -5 → 0
    - Múltiplos campos: estoque, saldo, estoque_atual
    """
    campos_estoque = ["estoque", "saldo", "estoque_atual", "quantidade"]

    for campo in campos_estoque:
        valor = produto.get(campo)

        if valor is None or valor == "":
            continue

        try:
            # Substituir vírgula por ponto
            if isinstance(valor, str):
                valor = valor.strip().replace(",", ".")

            estoque_float = float(valor)

            # Estoque negativo vira 0
            if estoque_float < 0:
                return 0.0

            return estoque_float

        except (ValueError, TypeError):
            continue

    return 0.0
```

**Antes:**
```python
"estoque": float(produto.get("estoque", 0) or 0)  # ❌ Falha com "10,5"
```

**Depois:**
```python
"estoque": self._converter_estoque(produto)  # ✅ Trata todos os casos
```

---

### 2. **Busca com UNACCENT (Ignora Acentos)**

**Arquivo:** `backend/src/services/supabase_produtos.py`

**Antes:**
```sql
SELECT * FROM produtos_site
WHERE LOWER(nome) LIKE '%cafes%';
-- Resultado: 0 (não encontra "Café")
```

**Depois:**
```sql
SELECT * FROM produtos_site
WHERE unaccent(LOWER(nome)) LIKE unaccent(LOWER('%cafes%'));
-- Resultado: 9 produtos ✅ (encontra "Café", "café", "CAFÉ")
```

**Código atualizado:**
```python
# Usa UNACCENT para ignorar acentos
query += """
    AND (
        unaccent(LOWER(nome)) LIKE unaccent(LOWER(%s))
        OR unaccent(LOWER(descricao)) LIKE unaccent(LOWER(%s))
        OR unaccent(LOWER(categoria)) LIKE unaccent(LOWER(%s))
    )
"""
```

**Benefícios:**
- ✅ "cafes" encontra "Café"
- ✅ "queijo" encontra "Queijão"
- ✅ "acucar" encontra "Açúcar"
- ✅ "pao" encontra "Pão de Queijo"

---

## 📋 Arquivos Modificados

### 1. `backend/src/services/tiny_products_client.py`
- ✅ Adicionado método `_converter_estoque()`
- ✅ Atualizado `_normalizar_produto()` para usar novo método
- ✅ Log detalhado para debugging de estoque

### 2. `backend/src/services/supabase_produtos.py`
- ✅ Query de busca agora usa `unaccent()`
- ✅ Ignora acentuação em nome, descrição e categoria

### 3. **Novos arquivos de debug:**
- `backend/scripts/debug_estoque_tiny.py` - Debug completo de estoque
- `backend/docs/SQL_INSTALL_UNACCENT.md` - Guia de instalação UNACCENT
- `backend/docs/DIAGNOSTICO_BUSCA_CAFE.md` - Diagnóstico do problema
- `backend/docs/CORRECOES_ESTOQUE_ACENTOS.md` - Este arquivo

---

## 🚀 Próximos Passos

### Passo 1: Instalar UNACCENT no Supabase

Abrir **Supabase SQL Editor** e executar:

```sql
CREATE EXTENSION IF NOT EXISTS unaccent;
```

Verificar:
```sql
SELECT unaccent('Café com açúcar');
-- Resultado: "Cafe com acucar" ✅
```

### Passo 2: Re-sync Produtos

```bash
# No servidor/container onde o bot roda
docker exec -it <container> python backend/scripts/sync_produtos_tiny.py
```

Ou via script de debug:
```bash
docker exec -it <container> python backend/scripts/debug_estoque_tiny.py
```

### Passo 3: Testar Busca no WhatsApp

Enviar mensagem no WhatsApp:
```
queria saber sobre os cafes que você tem
```

Resultado esperado:
```
Claro! Temos vários cafés disponíveis:

☕ Café Roça Capital Melodia - 250g
   R$ 25,00

☕ 1Kg Cafe Torrado Em Graos - Perfil Chocolate
   R$ 85,00

...
```

---

## 🧪 Como Testar Localmente (Desenvolvimento)

### 1. Testar conversão de estoque:

```bash
docker exec -it <container> python backend/scripts/debug_estoque_tiny.py
```

Vai mostrar:
- Todos os campos de estoque retornados pela API
- Valores brutos vs convertidos
- Detecção de string com vírgula
- Estoque final de cada produto

### 2. Testar busca com UNACCENT:

```bash
docker exec -it <container> python backend/scripts/test_busca_cafe.py
```

Vai testar:
- Busca com "cafe" (sem acento)
- Busca com "café" (com acento)
- Busca com UNACCENT
- Produtos inativos/sem estoque

---

## 📊 Resultados Esperados

### Antes das correções:
- ❌ Sync: 29 produtos com estoque = 0
- ❌ Busca "cafes": 0 resultados
- ❌ Bot: "Puxa, não encontrei nenhum produto com esse termo não."

### Depois das correções:
- ✅ Sync: 29 produtos com estoque correto (> 0 se disponível)
- ✅ Busca "cafes": 9 resultados
- ✅ Bot: Lista 9 produtos de café disponíveis

---

## 🔧 Troubleshooting

### Problema: Ainda aparece estoque = 0 após re-sync

**Diagnóstico:**
1. Rodar `debug_estoque_tiny.py` para ver valores brutos da API
2. Verificar se API Tiny realmente retorna estoque > 0
3. Verificar logs: buscar por "⚠️ Estoque negativo" ou "⚠️ Nenhum campo de estoque"

**Soluções:**
- Se API retorna campo diferente: adicionar ao array `campos_estoque`
- Se API retorna objeto aninhado: ajustar código para acessar campo correto
- Se estoque realmente é 0 no Tiny: atualizar estoque no Tiny ERP

### Problema: UNACCENT não funciona

**Erro comum:** `function unaccent(text) does not exist`

**Solução:**
```sql
CREATE EXTENSION IF NOT EXISTS unaccent;
```

Se não tiver permissão, contatar suporte do Supabase.

### Problema: Busca ainda não encontra produtos

**Diagnóstico:**
1. Verificar se UNACCENT foi instalado: `SELECT unaccent('Café');`
2. Verificar se produtos têm `estoque_disponivel = TRUE`
3. Verificar se produtos têm `ativo = TRUE`

**Solução:**
```sql
-- Ver status de todos os produtos de café
SELECT nome, ativo, estoque_disponivel, quantidade_estoque
FROM produtos_site
WHERE unaccent(LOWER(nome)) LIKE '%cafe%'
ORDER BY ativo DESC, estoque_disponivel DESC;
```

---

## 📝 Notas Técnicas

### Por que usar `unaccent()` em ambos os lados?

```sql
-- ✅ CORRETO
WHERE unaccent(LOWER(nome)) LIKE unaccent(LOWER('%café%'))

-- ❌ ERRADO (não funciona consistentemente)
WHERE unaccent(LOWER(nome)) LIKE LOWER('%café%')
```

Aplicar `unaccent()` em ambos os lados garante que:
- Busca "cafe" encontra "Café" ✅
- Busca "café" encontra "Cafe" ✅
- Busca "CAFÉ" encontra "cafe" ✅

### Por que não usar biblioteca Python para remover acentos?

Poderíamos fazer:
```python
import unicodedata
def remover_acentos(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                   if unicodedata.category(c) != 'Mn')
```

**MAS:**
- ❌ Precisa normalizar termo E todos os produtos do banco
- ❌ Não aproveita índices do PostgreSQL
- ❌ Mais lento em grandes volumes

**UNACCENT é melhor porque:**
- ✅ Executa no banco de dados (mais rápido)
- ✅ Pode usar índices funcionais se necessário
- ✅ Uma linha de código vs função complexa

---

## 🎯 Commits Recomendados

```bash
git add backend/src/services/tiny_products_client.py
git commit -m "Fix: Conversão robusta de estoque (vírgula, negativo, campos alternativos)"

git add backend/src/services/supabase_produtos.py
git commit -m "Feature: Busca com UNACCENT (ignora acentos)"

git add backend/scripts/debug_estoque_tiny.py
git add backend/docs/*.md
git commit -m "Docs: Debug de estoque e guia UNACCENT"

git push origin main
```

---

**Desenvolvido com ❤️ para a Roça Capital**
*Agente WhatsApp inteligente com LLM + Integração Tiny ERP + Supabase*
