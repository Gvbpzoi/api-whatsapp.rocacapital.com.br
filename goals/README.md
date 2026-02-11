# 🎯 Goals - Processos de Negócio

## O Que São Goals?

Goals são **processos de negócio documentados** que definem:
- **O QUÊ** precisa ser feito
- **QUANDO** executar
- **QUAIS** tools usar
- **QUAL** output esperar

A IA (orquestrador) lê os goals e decide como executá-los usando os tools disponíveis.

---

## Goals Disponíveis

| ID | Goal | Descrição | Frequência |
|----|------|-----------|------------|
| 1 | `atendimento_inicial.md` | Saudação e identificação do cliente | Sempre |
| 2 | `busca_produtos.md` | Busca inteligente de produtos | Sob demanda |
| 3 | `gestao_carrinho.md` | Adicionar, remover, visualizar carrinho | Sob demanda |
| 4 | `calculo_frete.md` | Calcular e confirmar frete | Sob demanda |
| 5 | `finalizacao_pedido.md` | Pagamento e confirmação | Sob demanda |
| 6 | `consulta_pedido.md` | Status e rastreio | Sob demanda |
| 7 | `controle_humano_agente.md` | Transição humano ↔ bot | Automático |

---

## Como Usar Goals

### 1. Verificar Goals Disponíveis
```bash
cat goals/README.md
```

### 2. Ler Goal Específico
```bash
cat goals/1_atendimento_inicial.md
```

### 3. Executar Goal
A IA lê o goal e:
1. Identifica tools necessários
2. Executa na ordem correta
3. Trata erros conforme documentado
4. Retorna output esperado

---

## Estrutura de um Goal

Cada goal segue este formato:

```markdown
# Goal: [Nome do Processo]

## Objetivo
[O que este processo faz]

## Quando Executar
[Triggers que acionam este goal]

## Entradas
[Dados necessários]

## Processo
[Passos detalhados]

## Tools Necessários
[Lista de tools usados]

## Saídas
[O que o goal produz]

## Tratamento de Erros
[Como lidar com falhas]

## Exemplos
[Casos de uso reais]
```

---

## Regras de Operação

### ✅ Sempre Faça

1. **Leia o goal completo** antes de começar
2. **Verifique se os tools existem** (`cat tools/README.md`)
3. **Execute na ordem documentada**
4. **Trate erros conforme especificado**
5. **Logue todas operações importantes**

### ⚠️ Nunca Faça

1. Pular etapas do goal
2. Inventar tools que não existem
3. Ignorar tratamento de erros
4. Modificar o goal sem documentar

---

## Adicionando Novo Goal

1. Criar arquivo: `goals/N_nome_processo.md`
2. Seguir estrutura padrão
3. Documentar tools necessários
4. Adicionar à tabela acima
5. Testar completamente

---

## Debug de Goals

Se um goal falhar:

1. **Ver logs:**
   ```bash
   grep "Goal: nome_goal" logs/app.log
   ```

2. **Identificar tool que falhou:**
   ```
   [Goal: finalizar_pedido]
   → Tool: payments.generate_pix → ERRO
   ```

3. **Corrigir o tool:**
   ```bash
   nano tools/payments/generate_pix.py
   ```

4. **Testar novamente:**
   ```bash
   pytest tools/payments/test_generate_pix.py
   ```

---

**Última atualização:** 11/02/2026
**Versão:** 2.0.0-GOTCHA
