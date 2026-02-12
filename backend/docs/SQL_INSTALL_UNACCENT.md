# Como Instalar UNACCENT no Supabase

## O que é UNACCENT?

A extensão `unaccent` do PostgreSQL remove acentos de strings, permitindo que buscas ignorem acentuação.

**Exemplo:**
- Busca: `"cafes"` (sem acento)
- Encontra: `"Café Roça Capital"` (com acento) ✅

---

## Instalação no Supabase

### Passo 1: Abrir SQL Editor

1. Acessar [https://supabase.com](https://supabase.com)
2. Selecionar seu projeto
3. Ir em **SQL Editor** (ícone de banco de dados no menu lateral)

### Passo 2: Executar SQL

Copie e cole este comando no editor SQL:

```sql
-- Criar extensão unaccent (se ainda não existir)
CREATE EXTENSION IF NOT EXISTS unaccent;
```

Clique em **Run** (ou Ctrl+Enter).

### Passo 3: Verificar Instalação

Execute para verificar se funcionou:

```sql
-- Testar UNACCENT
SELECT unaccent('Café com açúcar e queijão');
-- Resultado esperado: "Cafe com acucar e queijao"
```

---

## Como Funciona na Busca

### Antes (sem UNACCENT):

```sql
-- Usuário busca "cafes" (sem acento)
SELECT * FROM produtos_site
WHERE LOWER(nome) LIKE '%cafes%';
-- Resultado: 0 produtos (não encontra "Café")
```

### Depois (com UNACCENT):

```sql
-- Usuário busca "cafes" (sem acento)
SELECT * FROM produtos_site
WHERE unaccent(LOWER(nome)) LIKE unaccent(LOWER('%cafes%'));
-- Resultado: 9 produtos ✅ (encontra "Café")
```

---

## Benefícios

✅ Busca "queijo" encontra "Queijão Mineiro"
✅ Busca "acucar" encontra "Açúcar Mascavo"
✅ Busca "cafe" encontra "Café Premium"
✅ Busca "guarana" encontra "Guaraná Antarctica"
✅ Busca "pao" encontra "Pão de Queijo"

---

## Troubleshooting

### Erro: "permission denied to create extension"

**Solução:** No Supabase, você precisa de permissões de admin. Se estiver usando o plano free, a extensão deveria estar disponível. Se não funcionar, entre em contato com o suporte do Supabase.

### Erro: "extension 'unaccent' is not available"

**Solução:** A extensão unaccent é padrão no PostgreSQL 13+. No Supabase, ela já está incluída. Certifique-se de estar conectado ao banco de dados correto.

---

## Próximos Passos

Após instalar o UNACCENT, atualize o código do bot em:
- `backend/src/services/supabase_produtos.py`

O código já está preparado para usar UNACCENT automaticamente.

---

**Desenvolvido com ❤️ para a Roça Capital**
