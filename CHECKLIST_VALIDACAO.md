# 🧪 Checklist de Validação - Bugs de Alucinação

Use este checklist para validar se as correções estão funcionando em produção.

## ✅ Validação Manual no WhatsApp

### Teste 1: Pergunta Genérica ✓
**Objetivo:** Verificar se "pode mostrar os que você tem?" é classificado corretamente

```
📱 Você: "tem azeite?"
🤖 Bot: [Lista 5 azeites]

📱 Você: "pode mostrar os que você tem?"
🤖 Bot: [Lista mais 5 azeites]  ← ESPERADO

❌ ERRO SE: Bot responder "Adicionei ao carrinho"
```

**Status:** [ ] Passou  [ ] Falhou

---

### Teste 2: Busca por Relevância ✓
**Objetivo:** Verificar se busca "azeite" não retorna produtos errados

```
📱 Você: "tem azeite?"
🤖 Bot: [Lista produtos]

✅ ESPERADO:
- Azeite Extra Virgem
- Azeite de Oliva
- Azeite Italiano
...

❌ ERRO SE:
- Aparecer "Abobora C/Coco"
- Aparecer produtos que só têm "azeite" na descrição
```

**Status:** [ ] Passou  [ ] Falhou

---

### Teste 3: Contexto Conversacional ✓
**Objetivo:** Verificar se "tem mais?" usa contexto

```
📱 Você: "tem azeite?"
🤖 Bot: [Lista 5 azeites]

📱 Você: "tem mais?"
🤖 Bot: [Lista mais 5 azeites]  ← ESPERADO (mantém contexto)

❌ ERRO SE: Bot perguntar "tem mais de quê?"
```

**Status:** [ ] Passou  [ ] Falhou

---

### Teste 4: Adicionar por Nome ✓
**Objetivo:** Verificar se "dois azeites" adiciona azeite (não queijo)

```
📱 Você: "quero dois azeites"
🤖 Bot: "Adicionei 2 item(s) ao carrinho!"

📱 Você: "ver meu carrinho"
🤖 Bot: [Mostra carrinho]

✅ ESPERADO:
- Produto: Azeite [algum tipo]
- Quantidade: 2

❌ ERRO SE:
- Produto: Queijo Canastra (ID 1 default)
- Quantidade errada
```

**Status:** [ ] Passou  [ ] Falhou

---

### Teste 5: Total de Quantidade ✓
**Objetivo:** Verificar se total mostra quantidade correta

```
📱 Você: "adiciona 2 queijos"
🤖 Bot: "Adicionei 2 item(s) ao carrinho! Total: 2 produto(s)"  ← ESPERADO

❌ ERRO SE: Mostrar "Total de itens: 1"
```

**Status:** [ ] Passou  [ ] Falhou

---

### Teste 6: Memória de Escolhas 🆕✓
**Objetivo:** Verificar se bot lembra produto escolhido anteriormente

```
📱 Você: "tem azeite?"
🤖 Bot: [Lista 5 azeites]

📱 Você: "vou querer o 3"
🤖 Bot: "Adicionei 1 item ao carrinho!"
       [Sistema salva: azeites → Azeite Extra Virgem]

📱 Você: "me mostra uns vinhos"
🤖 Bot: [Lista vinhos]

📱 Você: "coloca mais um azeite pra mim"
🤖 Bot: "Adicionei 1x Azeite Extra Virgem..., aquele que você escolheu antes."  ← ESPERADO

✅ ESPERADO:
- Bot adiciona o MESMO azeite que foi escolhido antes
- Mensagem confirma: "aquele que você escolheu antes"

❌ ERRO SE:
- Bot perguntar "qual azeite?"
- Bot adicionar azeite diferente
- Bot adicionar produto ID 1 (default)
```

**Status:** [ ] Passou  [ ] Falhou

---

### Teste 7: Múltiplas Categorias em Paralelo ✓
**Objetivo:** Verificar se bot mantém escolhas de diferentes categorias

```
📱 Você: "tem azeite?"
🤖 Bot: [Lista azeites]

📱 Você: "vou querer o 2"
🤖 Bot: "Adicionado!"
       [Salva: azeites → Azeite de Oliva]

📱 Você: "tem queijo?"
🤖 Bot: [Lista queijos]

📱 Você: "quero o 1"
🤖 Bot: "Adicionado!"
       [Salva: queijos → Queijo Canastra]

📱 Você: "coloca mais um azeite"
🤖 Bot: "Adicionei 1x Azeite de Oliva..."  ← ESPERADO (lembra azeite)

📱 Você: "e mais um queijo também"
🤖 Bot: "Adicionei 1x Queijo Canastra..."  ← ESPERADO (lembra queijo)

✅ ESPERADO:
- Sistema mantém 2 escolhas simultâneas (azeites + queijos)
- Cada categoria lembra seu produto

❌ ERRO SE:
- Sistema esquece escolha anterior
- Confunde azeite com queijo
```

**Status:** [ ] Passou  [ ] Falhou

---

## 🔍 Validação Técnica (Logs)

### Verificar nos Logs:

#### 1. Pré-checagem de Intent
```
🔍 Pré-checagem: pergunta genérica sobre produtos → busca_produto
```
**Quando:** Cliente envia "pode mostrar os que você tem?"

---

#### 2. Contexto Salvo
```
💭 Assunto salvo para 5531xxx: 'azeite' (categoria: azeites)
```
**Quando:** Bot mostra produtos de azeite

---

#### 3. Uso do Contexto
```
🔄 Usando termo do contexto: azeite
```
**Quando:** Cliente pergunta "tem mais?" após buscar azeite

---

#### 4. Escolha Salva
```
📝 Primeira escolha (azeites): Azeite Extra Virgem Mineiro
```
**Quando:** Cliente adiciona azeite ao carrinho

---

#### 5. Recuperação de Escolha
```
✅ Usando produto do histórico de escolhas: Azeite Extra Virgem Mineiro
```
**Quando:** Cliente diz "coloca mais um azeite"

---

#### 6. Atualização de Quantidade
```
📝 Escolha atualizada (azeites): 1 → total: 2
```
**Quando:** Cliente adiciona mais unidades do mesmo produto

---

## 📊 Métricas de Sucesso

### Antes das Correções:
- [ ] "tem mais?" → classificado incorretamente
- [ ] Busca "azeite" → produtos errados
- [ ] Perde contexto entre mensagens
- [ ] Adiciona produto errado (ID 1)
- [ ] Total inconsistente
- [ ] Esquece escolhas anteriores

### Depois das Correções:
- [✓] "tem mais?" → busca_produto
- [✓] Busca "azeite" → só azeites (relevância)
- [✓] Mantém contexto conversacional
- [✓] Adiciona produto correto por nome
- [✓] Total de quantidade correto
- [✓] Lembra escolhas por categoria 🎉

---

## 🐛 Como Reportar Problemas

Se algum teste falhar:

### 1. Anote:
- **Teste que falhou:** (ex: Teste 6)
- **Entrada:** Mensagem enviada
- **Esperado:** Comportamento esperado
- **Obtido:** O que aconteceu
- **Logs:** Copie logs relevantes

### 2. Verifique:
- Deploy foi feito com sucesso?
- Todas as variáveis de ambiente configuradas?
- OpenAI API está funcionando? (opcional)

### 3. Debug:
```bash
# Ver logs do container
docker logs [container-name] --tail 100

# Buscar erros
docker logs [container-name] | grep "ERROR\|❌"

# Ver classificações de intent
docker logs [container-name] | grep "🎯 Intent"

# Ver uso de contexto
docker logs [container-name] | grep "💭\|🔄"

# Ver memória de escolhas
docker logs [container-name] | grep "📝"
```

---

## ✅ Checklist Final

### Implementação:
- [✓] SessionManager atualizado
- [✓] IntentClassifier melhorado
- [✓] Webhook ZAPI com fluxo contextual
- [✓] Busca por relevância
- [✓] ToolsHelper com quantidade_total

### Testes:
- [✓] Teste de contexto conversacional
- [✓] Teste de memória de escolhas
- [✓] Teste de inferência de categoria
- [✓] Teste de extração de termo
- [✓] Teste de classificação com contexto
- [✓] Teste de cenário completo

### Deploy:
- [ ] Push para GitHub
- [ ] Deploy no EasyPanel concluído
- [ ] Variáveis de ambiente configuradas
- [ ] Testes manuais no WhatsApp

### Validação:
- [ ] Teste 1: Pergunta genérica
- [ ] Teste 2: Busca por relevância
- [ ] Teste 3: Contexto conversacional
- [ ] Teste 4: Adicionar por nome
- [ ] Teste 5: Total de quantidade
- [ ] Teste 6: Memória de escolhas 🆕
- [ ] Teste 7: Múltiplas categorias

---

## 🎉 Pronto!

Se todos os testes passarem, o sistema está funcionando corretamente e os bugs foram corrigidos! 🚀
