# **FC Agent - Agente WhatsApp Roca Capital**

## **Sobre Este Sistema**

Sistema de atendimento via WhatsApp para a **Roca Capital**, loja de queijos artesanais e produtos mineiros no Mercado Central de BH.

**Arquitetura: FC Agent (Function Calling Agent)**

O FC Agent e uma arquitetura replicavel de agente conversacional baseada em OpenAI Function Calling. A LLM e o agente: ela entende contexto, decide quais ferramentas usar, em que ordem, e gera respostas naturais.

**Stack:**
- **FastAPI** para webhooks da ZAPI (WhatsApp API)
- **OpenAI Function Calling** (GPT-4.1-mini) como motor do agente
- **Postgres** para historico conversacional persistente
- **Supabase** para produtos e carrinho
- **Whisper** para transcricao de audio
- **GPT-4o-mini Vision** para analise de imagens
- **Controle Human-in-the-Loop** para atendimento hibrido

---

## **Arquitetura FC Agent**

### **Principio Central**

A LLM **e** o agente. Nao existe classificador de intents, nao existe handler por categoria, nao existe avaliador de resposta. O modelo recebe:
1. System prompt com personalidade + regras + descricao das 16 tools
2. Historico completo da conversa (Postgres)
3. Mensagem do usuario

E decide sozinho: qual tool chamar, em que ordem, quando parar, como responder.

### **Componentes**

```
backend/
├── src/
│   ├── agent/                         # FC Agent Core
│   │   ├── ai_agent.py                # Loop do agente (GENERICO)
│   │   ├── chat_history.py            # Historico Postgres (GENERICO)
│   │   ├── system_prompt.py           # Prompt do negocio (ESPECIFICO)
│   │   ├── tool_definitions.py        # 16 schemas OpenAI (ESPECIFICO)
│   │   └── tool_executor.py           # Implementacao tools (ESPECIFICO)
│   ├── api/
│   │   ├── main.py                    # FastAPI app + startup
│   │   └── zapi_webhook.py            # Webhook ZAPI + buffer + midia
│   ├── services/
│   │   ├── session_manager.py         # Controle AGENT/HUMAN/PAUSED
│   │   ├── media_processor.py         # Audio/Imagem/PDF
│   │   ├── zapi_client.py             # Cliente ZAPI WhatsApp
│   │   ├── supabase_produtos.py       # Busca produtos Postgres
│   │   └── supabase_carrinho.py       # Carrinho persistente
│   └── models/
│       └── session.py                 # Models de sessao
├── scripts/
│   └── migrate_chat_history.py        # Migration tabela chat_history
└── tests/
    └── test_session_manager.py        # Testes do session manager
```

### **Replicabilidade**

Para usar o FC Agent em outro projeto, copie os genericos e reescreva os especificos:

| Componente | Arquivo | Reusa? |
|---|---|---|
| Agent Loop | `ai_agent.py` | Copia igual |
| Chat History | `chat_history.py` | Copia igual |
| Session Control | `session_manager.py` | Copia igual |
| Media Processor | `media_processor.py` | Copia igual |
| Webhook | `zapi_webhook.py` | Adapta canal |
| **System Prompt** | `system_prompt.py` | **Reescreve** |
| **Tool Schemas** | `tool_definitions.py` | **Reescreve** |
| **Tool Executor** | `tool_executor.py` | **Reescreve** |

---

## **Fluxo de Atendimento**

### **1. Cliente envia mensagem no WhatsApp**

### **2. ZAPI envia webhook para `/webhook/zapi`**
- Detecta tipo de midia: texto, audio, imagem, documento
- Processa midia (Whisper/Vision/PDF) antes do buffer

### **3. Buffer de mensagens**
- Aguarda 3 segundos por mensagens consecutivas
- Combina mensagens rapidas em uma so
- Lock por telefone evita race condition

### **4. Verificacao de modo**
- **AGENT**: Bot responde automaticamente
- **HUMAN**: Humano esta atendendo, bot pausado
- **PAUSED**: Sistema pausado manualmente

### **5. AI Agent processa**
- Carrega system prompt + ultimas 30 mensagens do Postgres
- Envia para GPT-4.1-mini com 16 tools disponiveis
- Modelo decide: responder direto ou chamar tools
- Se chamou tools: executa, retorna resultado, modelo decide de novo
- Loop ate resposta final de texto (max 10 iteracoes)

### **6. Envio via ZAPI**
- Divide respostas longas em partes (max 1000 chars)
- Quebra em paragrafos para ficar natural
- Delay de 1 segundo entre partes

---

## **16 Tools Disponiveis**

| # | Tool | Funcao |
|---|---|---|
| 1 | `buscar_produtos` | Busca produtos por termo/categoria |
| 2 | `add_to_cart` | Adiciona item ao carrinho |
| 3 | `remover_do_carrinho` | Remove item do carrinho |
| 4 | `alterar_quantidade` | Altera quantidade de item |
| 5 | `view_cart` | Visualiza carrinho completo |
| 6 | `limpar_carrinho` | Esvazia carrinho |
| 7 | `gerar_pix` | Gera pagamento PIX |
| 8 | `gerar_pagamento` | Gera link cartao de credito |
| 9 | `enviar_qr_code_pix` | Envia QR Code via WhatsApp |
| 10 | `enviar_foto_produto` | Envia foto do produto |
| 11 | `calcular_frete` | Calcula frete por CEP |
| 12 | `confirmar_frete` | Confirma opcao de frete |
| 13 | `salvar_endereco` | Salva endereco do cliente |
| 14 | `buscar_historico_compras` | Busca compras anteriores |
| 15 | `verificar_status_pedido` | Status do pedido |
| 16 | `escalar_atendimento` | Escala para atendente humano |

---

## **Historico Conversacional (Postgres)**

### **Tabela: chat_history**

```sql
CREATE TABLE chat_history (
    id BIGSERIAL PRIMARY KEY,
    telefone TEXT NOT NULL,
    role TEXT NOT NULL,          -- 'user', 'assistant', 'tool'
    content TEXT,
    tool_calls JSONB,           -- Array de tool_calls do assistant
    tool_call_id TEXT,           -- ID da tool call (para role='tool')
    name TEXT,                   -- Nome da funcao (para role='tool')
    media_type TEXT DEFAULT 'text',
    media_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chat_history_phone_time ON chat_history(telefone, created_at DESC);
```

### **Comportamento**
- Salva TODAS as mensagens: user, assistant, tool_calls, tool results
- Carrega ultimas 30 mensagens por conversa
- Formato OpenAI nativo (replay exato no proximo turno)
- Detecta nova conversa se >30min sem mensagens

---

## **Processamento de Midia**

| Tipo | Processamento | Modelo |
|---|---|---|
| Audio | Transcricao automatica | Whisper |
| Imagem | Analise contextual | GPT-4o-mini Vision |
| PDF | Extracao de texto | PyPDF2 |

O resultado do processamento e injetado como texto na mensagem do usuario antes de ir para o agente.

---

## **Configuracao e Deploy**

### **Variaveis de Ambiente (.env)**

```bash
# OpenAI - Motor do agente
OPENAI_API_KEY=sua-chave-openai
OPENAI_MODEL=gpt-4.1-mini        # Opcional, default: gpt-4.1-mini

# ZAPI - WhatsApp API
ZAPI_INSTANCE_ID=xxx
ZAPI_TOKEN=xxx
ZAPI_CLIENT_TOKEN=xxx

# Banco de dados (Supabase Postgres)
DATABASE_URL=postgresql://...     # Pooler (para app)
DIRECT_URL=postgresql://...       # Direto (para migrations)

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=sua-chave-anon
```

### **Deploy no EasyPanel**

1. Push para GitHub (deploy automatico)
2. Configurar variaveis de ambiente no EasyPanel
3. Rodar migration: `python -m scripts.migrate_chat_history`
4. Webhook ZAPI aponta para: `https://seu-dominio.com/webhook/zapi`

**Health check:**
```
GET /
Response: {"status": "online", "service": "agente-whatsapp", "version": "2.0.0", "engine": "ai-agent"}
```

---

## **Controle Human-in-the-Loop**

### **Modos de Atendimento**

| Modo | Comportamento |
|---|---|
| **AGENT** (padrao) | Bot responde automaticamente |
| **HUMAN** | Humano atendendo, bot pausado |
| **PAUSED** | Sistema pausado manualmente |

### **Comandos**

| Comando | Acao |
|---|---|
| `/pausar` | Pausa o agente |
| `/retomar` | Retoma o agente |
| `/assumir` | Humano assume atendimento |
| `/liberar` | Libera para o agente |
| `/status` | Mostra status da sessao |
| `/help` | Lista comandos |

### **Deteccao Automatica**
- Prefixo `[HUMANO]` ou `[ATENDENTE]` pausa bot automaticamente
- Auto-resume apos 5min de inatividade do humano

---

## **Informacoes do Negocio**

### **Roca Capital**
- **Localizacao:** Mercado Central de BH (Av. Augusto de Lima c/ Curitiba)
- **Produtos:** ~700 itens (queijos artesanais, cachacas, doces, mel)
- **Horario:** Segunda a sexta: 8h-18h | Feriados: 8h-13h
- **Contato:** WhatsApp (31) 9 9847-21890 | sac@rocacapital.com.br
- **Site:** www.rocacapital.com.br

### **Politicas de Entrega**
- Pedidos ate 16h (seg-sex) saem no mesmo dia
- Entrega entre 8h-18h em rota otimizada
- Nao envia queijo se prazo > 3 dias
- BH: Lalamove ou motoboy proprio
- Fora de BH: Correios (consultar CEP)

### **Politicas de Pagamento**
- PIX com 5% desconto (compras > R$ 499,90)
- Cartao de credito via link de pagamento
- Nao aceita boleto, parcelamento ou vale-alimentacao
- Dinheiro somente na loja fisica

---

## **Troubleshooting**

### **Resposta errada ou fora de contexto**
1. Verificar system_prompt.py (regras podem estar ambiguas)
2. Verificar historico no banco (SELECT * FROM chat_history WHERE telefone = 'xxx' ORDER BY created_at DESC LIMIT 30)
3. Testar tool isolada no tool_executor.py

### **Respostas muito lentas**
1. Verificar latencia OpenAI API
2. Checar numero de iteracoes do agent (logs: "Agent iteration X")
3. Verificar se tools estao lentas (busca Postgres, chamadas externas)

### **Webhook nao recebe mensagens**
1. Verificar URL do webhook na ZAPI
2. Confirmar Client-Token configurado
3. Checar logs: `docker logs container-name`

### **Midia nao processada**
1. Audio: Verificar se OPENAI_API_KEY tem acesso ao Whisper
2. Imagem: Verificar se URL da imagem esta acessivel
3. PDF: Verificar se PyPDF2 esta instalado

---

## **Guardrails**

### **Nunca faca:**
1. Inventar informacoes nao configuradas no prompt
2. Modificar ai_agent.py sem necessidade (e generico)
3. Responder em modo HUMAN ou PAUSED
4. Adicionar tools sem schema + executor + descricao no prompt

### **Sempre faca:**
1. Toda tool nova precisa de: schema em tool_definitions.py + handler em tool_executor.py + descricao no system_prompt.py
2. Teste tools isoladas antes de integrar
3. Monitore logs de iteracoes do agente
4. Mantenha historico no Postgres (nao delete sem motivo)

---

**FC Agent v2.0 - Function Calling Agent Architecture**
*Desenvolvido para a Roca Capital*
