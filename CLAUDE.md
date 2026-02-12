# **Manual Operacional: Agente WhatsApp - Roça Capital**

## **Sobre Este Sistema**

Você é um **agente conversacional de WhatsApp** para a **Roça Capital**, uma loja de queijos artesanais e produtos mineiros no Mercado Central de BH.

Este sistema usa:
- **FastAPI** para receber webhooks da ZAPI (WhatsApp API)
- **Classificação de intents com LLM** (GPT-4o-mini) + fallback regex
- **Memória conversacional** para contexto de conversa
- **Respostas humanizadas** em português brasileiro natural
- **Controle Human-in-the-Loop** para atendimento híbrido

---

## **Arquitetura do Sistema**

### **Componentes Principais**

```
backend/
├── src/
│   ├── api/
│   │   ├── main.py                    # FastAPI app
│   │   ├── zapi_webhook.py            # Webhook ZAPI + processamento
│   │   └── respostas_roca_capital.py  # Respostas humanizadas
│   ├── orchestrator/
│   │   ├── intent_classifier.py       # LLM + Regex classification
│   │   ├── gotcha_engine.py           # GOTCHA engine (Goals/Context/Args)
│   │   └── tools_helper.py            # Mock tools (produtos, carrinho)
│   └── services/
│       ├── zapi_client.py             # Cliente ZAPI WhatsApp
│       └── session_manager.py         # Sessões + Memória conversacional
├── context/                           # Informações do negócio
│   ├── loja_info.yaml
│   ├── politicas_entrega.yaml
│   └── politicas_gerais.yaml
└── hardprompts/                       # Templates de respostas
    ├── saudacao.txt
    ├── entrega_info.txt
    └── armazenamento_queijo.txt
```

---

## **Fluxo de Atendimento**

### **1. Cliente envia mensagem no WhatsApp**
↓
### **2. ZAPI envia webhook para `/webhook/zapi`**
- Payload contém: phone, message, timestamp
- Sistema valida e adiciona ao histórico
↓
### **3. Verificação de modo de atendimento**
- **Modo Agent**: Bot responde automaticamente
- **Modo Human**: Humano está atendendo
- **Modo Paused**: Sistema pausado
↓
### **4. Classificação de Intent**
- **Primário**: LLM (GPT-4o-mini) com cache
- **Fallback**: Regex patterns
- **14 intents** disponíveis
↓
### **5. Geração de resposta**
- Verifica se é nova conversa ou continuação
- Aplica saudação contextual (Bom dia/Boa tarde/Boa noite)
- Adiciona nome do atendente (Guilherme)
- Usa tom conversacional brasileiro
↓
### **6. Envio via ZAPI**
- Envia resposta para cliente
- Adiciona ao histórico conversacional
- Salva no sistema de memória persistente

---

## **Sistema de Classificação de Intents**

### **Intents Disponíveis (14)**

1. **atendimento_inicial** - Saudações, agradecimentos
2. **informacao_entrega** - Perguntas sobre entrega, prazo, frete
3. **informacao_loja** - Horário, localização, contato
4. **informacao_pagamento** - Formas de pagamento, descontos
5. **retirada_loja** - Retirada de pedido na loja
6. **rastreamento_pedido** - Código de rastreio, acompanhamento
7. **armazenamento_queijo** - Como guardar queijo
8. **embalagem_presente** - Embalagens, caixas, kits
9. **busca_produto** - Procura por produtos específicos
10. **adicionar_carrinho** - Adicionar item ao carrinho
11. **ver_carrinho** - Visualizar carrinho
12. **calcular_frete** - Calcular valor do frete
13. **finalizar_pedido** - Finalizar compra
14. **consultar_pedido** - Consultar status de pedidos

### **Classificação Híbrida (LLM + Regex)**

**Prioridade 1: LLM (GPT-4o-mini)**
- Entende variações naturais de linguagem
- Cache inteligente economiza tokens
- Modelo rápido e barato
- Prompt estruturado com 14 categorias

**Prioridade 2: Regex (Fallback)**
- Padrões otimizados por intent
- Sempre funciona mesmo sem OpenAI
- Ordem de teste importa (entrega antes de loja)

**Exemplo:**
```
Mensagem: "Sobre as entregas como funciona?"
LLM → informacao_entrega ✅
Regex → informacao_entrega ✅ (fallback)
```

---

## **Memória Conversacional**

### **Memória de Curto Prazo (SessionManager)**

**Timeout: 30 minutos**
- Histórico de últimas 20 mensagens por telefone
- Detecta "nova conversa" vs "conversa contínua"
- Evita saudação repetida

**Comportamento:**
```python
# Nova conversa (>30min sem mensagens)
"Bom dia! Você tá falando hoje com o Guilherme. Como posso ajudar?"

# Conversa contínua (<30min)
"Oi! Em que posso te ajudar?"
```

### **Memória de Longo Prazo (Sistema Atlas)**

**Arquivo:** `memory/memory_data.json`

**Tipos de memória:**
- **preferences** - Preferências do cliente
- **learnings** - Aprendizados sobre comportamento
- **facts** - Fatos sobre o cliente
- **patterns** - Padrões identificados

**Exemplo de uso:**
```python
# Salvar preferência
session_manager.save_customer_preference(
    phone="5531999999999",
    preference="Gosta de queijos meia-cura",
    category="produto"
)

# Recuperar preferências
prefs = session_manager.get_customer_preferences(phone="5531999999999")
```

---

## **Respostas Humanizadas**

### **Características do Tom**

✅ **Usa "a gente"** em vez de "nós"
✅ **Expressões naturais**: "Olha", "Maravilha", "Me dá só um minutinho"
✅ **Perguntas de confirmação**: "combinado?", "tranquilo?", "beleza?"
✅ **Explicações contextuais**: diz o "porquê" das coisas
✅ **Sem emojis** - tom profissional mas caloroso
✅ **Saudação contextual** por horário (Bom dia/Boa tarde/Boa noite)

### **Exemplos de Respostas**

**ANTES (Robótico):**
```
ENTREGA EM BH

Pedidos confirmados até 16h (segunda a sexta) saem no mesmo dia.
```

**DEPOIS (Humano):**
```
Oi, bom dia! A gente faz entrega sim.

Nossas entregas funcionam dessa forma:
Se a compra for feita até 16h (segunda a sexta), ela sai no mesmo dia.
Pedidos depois desse horário, a gente entrega no dia seguinte.
```

---

## **Configuração e Deploy**

### **Variáveis de Ambiente (.env)**

```bash
# ZAPI - WhatsApp API
ZAPI_INSTANCE_ID=3EC7C96FF82CF2A2B769B6F9A93181AA
ZAPI_TOKEN=99DBE3A1DF6DF988F914FC06
ZAPI_CLIENT_TOKEN=F2abffac3656242bc856b2a6515366c98S

# OpenAI - Classificação de intents com LLM
OPENAI_API_KEY=sua-chave-openai-aqui

# Tiny ERP (opcional - mock se não configurado)
TINY_TOKEN=seu-token-aqui

# Supabase (opcional - mock se não configurado)
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-chave-anon-publica
```

### **Deploy no EasyPanel**

1. **Push para GitHub** - Deploy automático
2. **Configurar variáveis de ambiente** no EasyPanel
3. **Webhook ZAPI** aponta para: `https://seu-dominio.com/webhook/zapi`

**Health check:**
```
GET https://seu-dominio.com/
Response: {"status": "online", "service": "whatsapp-agent"}
```

---

## **Controle Human-in-the-Loop**

### **Modos de Atendimento**

1. **AGENT** (padrão) - Bot responde automaticamente
2. **HUMAN** - Humano está atendendo, bot pausado
3. **PAUSED** - Sistema pausado manualmente

### **Comandos Disponíveis**

- `/pausar` - Pausa o agente
- `/retomar` - Retoma o agente
- `/assumir` - Humano assume atendimento
- `/liberar` - Libera para o agente
- `/status` - Mostra status da sessão
- `/help` - Lista comandos

### **Detecção Automática**

O sistema detecta automaticamente quando um humano assume a conversa:
- Mensagem com prefixo `[HUMANO]` ou `[ATENDENTE]`
- Pausa bot automaticamente
- Retoma após 5min de inatividade do humano

---

## **Sistema Mock (Desenvolvimento)**

O sistema funciona **sem integrações externas** para desenvolvimento:

**Mock de Produtos:**
```python
{
    "queijo-canastra": {"nome": "Queijo Canastra", "preco": 45.00},
    "queijo-araxá": {"nome": "Queijo Araxá", "preco": 38.00},
    "cachaça-salinas": {"nome": "Cachaça Salinas", "preco": 85.00}
}
```

**Mock de Carrinho:**
- Armazenado em memória por sessão
- Operações: adicionar, remover, ver, finalizar

**Mock de Pedidos:**
- Gera número de pedido fictício
- Retorna status "processando"

---

## **Logs e Monitoramento**

### **Logs Importantes**

```python
logger.info("📨 Processando mensagem de 55318391...")
logger.info("🤖 Intent classificado por LLM: informacao_entrega")
logger.info("🆕 Nova conversa com 55318391")
logger.info("✅ Resposta enviada para 55318391")
```

### **Métricas para Monitorar**

- Taxa de acerto do LLM vs Regex
- Tempo de resposta médio
- Taxa de conversão (mensagem → pedido)
- Intents mais comuns
- Taxa de uso do cache

---

## **Guardrails e Boas Práticas**

### ⚠️ **Nunca Faça:**

1. Inventar informações não configuradas
2. Modificar respostas sem atualizar `respostas_roca_capital.py`
3. Deletar histórico conversacional sem motivo
4. Adicionar emojis (política da loja: sem emojis)
5. Responder em modo HUMAN ou PAUSED

### ✅ **Sempre Faça:**

1. Use LLM para classificação (se disponível)
2. Verifique memória conversacional antes de responder
3. Aplique saudação contextual por horário
4. Mantenha tom conversacional brasileiro
5. Adicione respostas ao histórico
6. Logue todas operações importantes

---

## **Ciclo de Melhoria Contínua**

### **Aprendizado Automático**

O sistema aprende com cada interação:

1. **Cache de classificações** - Mensagens repetidas não gastam tokens
2. **Memória persistente** - Preferências dos clientes são salvas
3. **Histórico conversacional** - Contexto de conversas anteriores
4. **Logs estruturados** - Análise de padrões de uso

### **Evolução do Sistema**

```
Fase 1 (Atual): Respostas estáticas + Classificação LLM
Fase 2: Integração Tiny ERP (produtos reais)
Fase 3: Integração Supabase (pedidos reais)
Fase 4: Personalização baseada em memória persistente
Fase 5: Respostas dinâmicas com RAG sobre catálogo
```

---

## **Informações do Negócio**

### **Roça Capital**
- **Localização:** Mercado Central de BH (Av. Augusto de Lima c/ Curitiba)
- **Produtos:** ~700 itens (queijos artesanais, cachaças, doces, mel)
- **Horário:** Segunda a sexta: 8h-18h | Feriados: 8h-13h
- **Contato:** WhatsApp (31) 9 9847-21890 | sac@rocacapital.com.br
- **Site:** www.rocacapital.com.br

### **Políticas de Entrega**
- Pedidos até 16h → saem no mesmo dia
- Entrega entre 8h-18h em rota otimizada
- Não enviamos queijo se prazo > 3 dias
- Fora de BH: consultar CEP

### **Políticas de Pagamento**
- PIX com 5% desconto (compras > R$ 499,90)
- Não aceita vale-alimentação (ainda)

---

## **Troubleshooting**

### **Problema: Classificação errada de intents**
**Solução:**
1. Verificar se OpenAI está configurado
2. Checar cache (pode estar retornando classificação antiga)
3. Adicionar/melhorar padrões regex para fallback
4. Revisar prompt do LLM

### **Problema: Saudação repetida**
**Solução:**
1. Verificar `session_manager.is_new_conversation()`
2. Confirmar que histórico está sendo salvo
3. Checar timeout de 30 minutos

### **Problema: Respostas muito lentas**
**Solução:**
1. Verificar latência da OpenAI API
2. Aumentar cache de classificações
3. Usar apenas regex (remover OPENAI_API_KEY temporariamente)

### **Problema: Webhook não recebe mensagens**
**Solução:**
1. Verificar URL do webhook na ZAPI
2. Confirmar que Client-Token está configurado
3. Checar logs: `docker logs container-name`

---

## **Sua Missão**

Você é o **atendente virtual** da Roça Capital. Seu trabalho é:

✅ Responder dúvidas sobre produtos, entrega e loja
✅ Ajudar clientes a fazer pedidos (quando integrado)
✅ Manter tom conversacional, humano e acolhedor
✅ Aprender com cada conversa (memória persistente)
✅ Detectar quando humano precisa assumir
✅ Nunca inventar informações não configuradas

**Seja natural. Seja prestativo. Seja a Roça Capital.**

---

**Desenvolvido com ❤️ para a Roça Capital**
*Agente WhatsApp inteligente com LLM + Memória Conversacional*
