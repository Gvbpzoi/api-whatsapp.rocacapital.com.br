# 🚀 Guia de Migração para GOTCHA - Roça Capital

**Data:** 11/02/2026
**Versão:** 2.0.0-GOTCHA
**Status:** Pronto para Implementação

---

## 📋 O Que Foi Criado

### ✅ Estrutura Completa GOTCHA

```
agente-whatsapp/
├── goals/              # 7 processos documentados
├── tools/              # Manifest + estrutura modular
├── context/            # 3 arquivos de conhecimento
├── hardprompts/        # 4 templates de resposta
├── args/               # 2 arquivos de configuração
└── memory/             # Sistema de memória (CRUD + busca)
```

**Total:** 25+ arquivos criados

---

## 🎯 Próximos Passos (Ordem Recomendada)

### Fase 1: Integração Básica (2-4 horas)

#### 1. Criar Orquestrador GOTCHA

Criar: `backend/src/orchestrator/gotcha_engine.py`

```python
"""
GOTCHA Engine - Orquestrador Principal
"""

from typing import Dict, Any
import yaml
import logging

logger = logging.getLogger(__name__)


class GOTCHAEngine:
    """Orquestrador que executa Goals usando Tools"""

    def __init__(self):
        self.goals = self._load_goals()
        self.tools = self._load_tools()
        self.context = self._load_context()
        self.args = self._load_args()

    def _load_goals(self) -> Dict:
        """Carrega todos os goals disponíveis"""
        # TODO: Implementar leitura de goals/
        return {}

    def _load_tools(self) -> Dict:
        """Carrega todos os tools disponíveis"""
        # TODO: Implementar import dinâmico de tools/
        return {}

    def _load_context(self) -> Dict:
        """Carrega contexto de negócio"""
        context = {}
        context['produtos'] = yaml.safe_load(open('context/produtos_destaque.yaml'))
        context['frases'] = yaml.safe_load(open('context/frases_atendimento.yaml'))
        context['politicas'] = yaml.safe_load(open('context/politicas_loja.yaml'))
        return context

    def _load_args(self) -> Dict:
        """Carrega configurações"""
        args = {}
        args['comportamento'] = yaml.safe_load(open('args/comportamento_agente.yaml'))
        args['limites'] = yaml.safe_load(open('args/limites_operacionais.yaml'))
        return args

    async def execute_goal(
        self,
        goal_name: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executa um goal.

        Args:
            goal_name: Nome do goal (ex: "busca_produtos")
            input_data: Dados de entrada

        Returns:
            Resultado da execução
        """
        logger.info(f"🎯 Executando Goal: {goal_name}")

        # TODO: Ler goal MD, identificar tools necessários, executar em ordem
        #  Por enquanto, usar lógica existente do backend

        return {"status": "success", "result": "TODO"}

    def get_template(self, template_name: str, variables: Dict = None) -> str:
        """
        Carrega template de hardprompts.

        Args:
            template_name: Nome do template (ex: "saudacao")
            variables: Variáveis para substituir

        Returns:
            Template formatado
        """
        template_path = f"hardprompts/{template_name}.txt"

        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()

        # Substituir variáveis
        if variables:
            for key, value in variables.items():
                template = template.replace(f"{{{key}}}", str(value))

        return template
```

#### 2. Integrar com FastAPI

Atualizar: `backend/src/api/main.py`

```python
from backend.src.orchestrator.gotcha_engine import GOTCHAEngine

# Inicializar
gotcha = GOTCHAEngine()

@app.post("/whatsapp/message")
async def handle_whatsapp_message(request: WhatsAppMessage):
    """Handler principal de mensagens WhatsApp"""

    # 1. Verificar controle humano-agente (Goal 7)
    should_respond, reason = session_manager.process_message(
        phone=request.telefone,
        message=request.mensagem,
        source="whatsapp"
    )

    if not should_respond:
        logger.info(f"Humano atendendo: {reason}")
        return {"status": "human_control"}

    # 2. Identificar intent (qual goal executar)
    intent = identify_intent(request.mensagem)

    # 3. Executar goal apropriado
    if intent == "busca_produto":
        result = await gotcha.execute_goal("busca_produtos", {
            "telefone": request.telefone,
            "termo": extract_search_term(request.mensagem)
        })

    elif intent == "adicionar_carrinho":
        result = await gotcha.execute_goal("gestao_carrinho", {
            "telefone": request.telefone,
            "acao": "add",
            "produto_id": extract_produto_id(request.mensagem)
        })

    # ... outros intents ...

    # 4. Enviar resposta
    send_whatsapp_message(request.telefone, result["message"])

    return {"status": "success"}
```

#### 3. Refatorar Tools Existentes

Migrar: `backend/src/agent/tools.py` → `tools/*/*.py`

**Exemplo:** `tools/products/search.py`

```python
from backend.src.agent.tools import AgentTools

def execute(termo: str, limite: int = 10):
    """Wrapper sobre AgentTools existente"""
    agent_tools = AgentTools(supabase, tiny)
    result = agent_tools.buscar_produtos(termo, limite)
    return {"status": "success", "produtos": result}
```

---

### Fase 2: Melhorias (4-6 horas)

#### 4. Implementar Sistema de Memória

```python
# No orquestrador
from memory import memory_write, memory_search

# Ao processar mensagem
preferencias = memory_search(f"cliente:{telefone} preferencias")

# Ao finalizar pedido
memory_write(
    f"Cliente comprou {produto.nome}",
    type="fact",
    tags=[f"cliente:{telefone}", "compra"]
)
```

#### 5. Usar Templates (Hardprompts)

```python
# Ao enviar saudação
template = gotcha.get_template("saudacao", {
    "saudacao": "Bom dia",
    "nome": cliente.nome,
    "emoji": "☀️"
})

send_message(telefone, template)
```

#### 6. Aplicar Args (Configurações)

```python
# Verificar limites
max_itens = gotcha.args['limites']['negocio']['carrinho']['max_itens']

if len(carrinho.itens) >= max_itens:
    return "Carrinho cheio! Máximo de itens atingido."

# Verificar horário
if gotcha.args['comportamento']['horario_atendimento']['sempre_ativo']:
    # Bot sempre ativo
    pass
```

---

### Fase 3: Testes (2-3 horas)

#### 7. Testar Goals Individualmente

```bash
# Testar Goal 1 (Atendimento Inicial)
pytest tests/test_goal_atendimento_inicial.py

# Testar Goal 2 (Busca Produtos)
pytest tests/test_goal_busca_produtos.py
```

#### 8. Testar Tools

```bash
# Testar tool de busca
python tools/products/search.py "queijo" 5

# Testar memória
python memory/memory.py write "Teste de memória" fact
python memory/search.py "teste"
```

#### 9. Testar Fluxo Completo

```bash
# Simular conversa completa
./scripts/test_fluxo_completo.sh
```

---

## 📚 Documentação de Referência

### Goals (Processos)
- `goals/README.md` - Manifest de goals
- `goals/1_atendimento_inicial.md` - Saudação
- `goals/2_busca_produtos.md` - Busca
- `goals/3_gestao_carrinho.md` - Carrinho
- `goals/4_calculo_frete.md` - Frete
- `goals/5_finalizacao_pedido.md` - Pedido
- `goals/6_consulta_pedido.md` - Consulta
- `goals/7_controle_humano_agente.md` - Controle

### Tools (Executores)
- `tools/README.md` - Manifest de tools
- `tools/products/search.py` - Exemplo implementado

### Context (Conhecimento)
- `context/produtos_destaque.yaml` - Produtos principais
- `context/frases_atendimento.yaml` - Frases padrão
- `context/politicas_loja.yaml` - Políticas

### Hardprompts (Templates)
- `hardprompts/saudacao.txt`
- `hardprompts/produto_encontrado.txt`
- `hardprompts/produto_indisponivel.txt`
- `hardprompts/confirmacao_pedido.txt`

### Args (Configurações)
- `args/comportamento_agente.yaml`
- `args/limites_operacionais.yaml`

### Memory (Memória)
- `memory/MEMORY.md` - Base de conhecimento
- `memory/memory.py` - CRUD
- `memory/search.py` - Busca

---

## 🔄 Mig ração Gradual (Recomendado)

### Abordagem Incremental

**Semana 1:** Integrar Goals 1 e 2
- Atendimento inicial
- Busca de produtos

**Semana 2:** Integrar Goals 3, 4, 5
- Gestão de carrinho
- Cálculo de frete
- Finalização de pedido

**Semana 3:** Integrar Goals 6 e 7
- Consulta de pedido
- Controle humano-agente (já funciona!)

**Semana 4:** Melhorias
- Sistema de memória ativo
- Templates personalizados
- Analytics e métricas

---

## ✅ Checklist de Migração

### Preparação
- [ ] Backup do sistema atual
- [ ] Criar branch `feature/gotcha-migration`
- [ ] Ler toda documentação GOTCHA

### Implementação
- [ ] Criar `backend/src/orchestrator/gotcha_engine.py`
- [ ] Integrar com FastAPI (`main.py`)
- [ ] Migrar 1 tool por vez (começar por `products/search`)
- [ ] Testar cada tool isoladamente
- [ ] Implementar intent classifier

### Testes
- [ ] Testes unitários de tools
- [ ] Testes de integração de goals
- [ ] Teste de fluxo completo (ponta a ponta)
- [ ] Teste com usuários reais (beta)

### Deploy
- [ ] Merge para `main`
- [ ] Deploy em staging
- [ ] Monitorar por 24h
- [ ] Deploy em produção
- [ ] Monitorar por 1 semana

---

## 🐛 Troubleshooting

### Problema: Goal não encontra Tool

**Solução:**
```bash
# Verificar se tool existe
ls -la tools/products/search.py

# Verificar import
python -c "from tools.products import search; print(search.execute)"
```

### Problema: Template não carrega

**Solução:**
```bash
# Verificar caminho
cat hardprompts/saudacao.txt

# Verificar encoding
file hardprompts/saudacao.txt  # Deve ser UTF-8
```

### Problema: Memória não persiste

**Solução:**
```bash
# Verificar arquivo JSON
cat memory/memory_data.json

# Testar CRUD
python memory/memory.py write "Teste" fact
python memory/memory.py read
```

---

## 📊 Métricas de Sucesso

**Após migração completa, você deve ter:**
- ✅ 7 goals documentados e funcionais
- ✅ 20+ tools modulares e testados
- ✅ Sistema de memória ativo
- ✅ Templates personalizados
- ✅ Configurações centralizadas
- ✅ Debug facilitado (logs por goal/tool)
- ✅ Manutenibilidade alta (código organizado)
- ✅ Escalabilidade (fácil adicionar novos goals)

---

## 🆘 Suporte

**Dúvidas sobre:**
- **Goals:** Ler `goals/README.md`
- **Tools:** Ler `tools/README.md`
- **Context:** Ler arquivos YAML em `context/`
- **Memória:** Ler `memory/MEMORY.md`

**Precisa de ajuda?**
- Consulte a documentação existente
- Veja exemplos nos goals
- Teste tools isoladamente primeiro

---

**Boa migração! A arquitetura GOTCHA vai deixar seu sistema muito mais organizado e escalável!** 🚀

---

**Desenvolvido com ❤️ para a Roça Capital**
**Data:** 11/02/2026
**Versão:** 2.0.0-GOTCHA
