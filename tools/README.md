# 🔧 Tools - Executores Modulares

## O Que São Tools?

Tools são **executores** que realizam tarefas específicas. Cada tool:
- Faz **UMA coisa** e faz bem
- Tem interface clara (input/output)
- É **testável** independentemente
- Pode ser **reusado** por múltiplos goals

---

## Estrutura de Tools

```
tools/
├── whatsapp/           # Comunicação WhatsApp
│   ├── send_message.py
│   ├── receive_message.py
│   └── format_response.py
│
├── products/           # Gestão de produtos
│   ├── search.py
│   ├── get_details.py
│   └── recommend.py
│
├── cart/               # Carrinho de compras
│   ├── add_item.py
│   ├── remove_item.py
│   ├── view_cart.py
│   ├── clear_cart.py
│   └── calculate_total.py
│
├── shipping/           # Frete e entrega
│   ├── validate_cep.py
│   ├── calculate.py
│   └── confirm.py
│
├── orders/             # Gestão de pedidos
│   ├── create.py
│   ├── search.py
│   ├── track.py
│   └── validate_prerequisites.py
│
├── payments/           # Pagamentos
│   ├── generate_pix.py
│   ├── process_card.py
│   └── check_status.py
│
└── session/            # Controle de sessão
    ├── check_client.py
    ├── create_or_update.py
    ├── takeover.py
    └── release.py
```

---

## Manifest de Tools

| Tool | Descrição | Input | Output | Goal(s) |
|------|-----------|-------|--------|---------|
| **whatsapp/send_message** | Envia mensagem WhatsApp | telefone, mensagem | success/error | Todos |
| **whatsapp/format_response** | Formata resposta amigável | dados, template | mensagem_formatada | Todos |
| **products/search** | Busca produtos (Supabase) | termo, limite | lista_produtos | 2 |
| **products/get_details** | Detalhes do produto | produto_id | produto_completo | 2 |
| **cart/add_item** | Adiciona ao carrinho | telefone, produto_id, qtd | carrinho_atualizado | 3 |
| **cart/view_cart** | Visualiza carrinho | telefone | carrinho_completo | 3 |
| **cart/calculate_total** | Calcula total | carrinho | valor_total | 3, 5 |
| **shipping/calculate** | Calcula frete | cep, peso, valor | opcoes_frete | 4 |
| **shipping/confirm** | Confirma frete | telefone, opcao_id | frete_confirmado | 4 |
| **orders/create** | Cria pedido | dados_pedido | pedido_criado | 5 |
| **orders/search** | Busca pedidos | telefone/cpf | lista_pedidos | 6 |
| **orders/track** | Rastreia pedido | codigo_rastreio | status_rastreio | 6 |
| **payments/generate_pix** | Gera PIX | valor, pedido_id | qr_code, copia_cola | 5 |
| **payments/process_card** | Processa cartão | dados_cartao, valor | payment_link | 5 |
| **session/takeover** | Humano assume | telefone, atendente_id | sessao_atualizada | 7 |
| **session/release** | Libera para bot | telefone | sessao_atualizada | 7 |

---

## Como Criar um Tool

### Estrutura Padrão

```python
"""
Tool: [Nome]
Goal: [Goal(s) que usa]
Descrição: [O que faz]
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def execute(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o tool.

    Args:
        input_data: Dados de entrada

    Returns:
        Resultado da execução

    Raises:
        ValueError: Se input inválido
        Exception: Se falha na execução
    """
    try:
        # 1. Validar input
        _validate_input(input_data)

        # 2. Executar lógica principal
        result = _execute_logic(input_data)

        # 3. Formatar output
        output = _format_output(result)

        logger.info(f"Tool executado com sucesso: {output}")
        return {"status": "success", **output}

    except ValueError as e:
        logger.error(f"Input inválido: {e}")
        return {"status": "error", "reason": "invalid_input", "message": str(e)}

    except Exception as e:
        logger.error(f"Erro na execução: {e}")
        return {"status": "error", "reason": "execution_failed", "message": str(e)}


def _validate_input(data: Dict[str, Any]) -> None:
    """Valida dados de entrada"""
    required_fields = ["field1", "field2"]
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Campo obrigatório: {field}")


def _execute_logic(data: Dict[str, Any]) -> Any:
    """Lógica principal do tool"""
    # Implementação aqui
    pass


def _format_output(result: Any) -> Dict[str, Any]:
    """Formata output"""
    return {"result": result}


# Para testes
if __name__ == "__main__":
    # Test case
    test_input = {"field1": "value1", "field2": "value2"}
    print(execute(test_input))
```

---

## Regras de Tools

### ✅ Sempre Faça

1. **Uma responsabilidade** - Tool faz UMA coisa
2. **Input validado** - Verificar todos os campos obrigatórios
3. **Output consistente** - Sempre retornar dict com "status"
4. **Logging** - Logar sucesso e erros
5. **Docstring** - Documentar claramente
6. **Testável** - Pode ser testado isoladamente

### ⚠️ Nunca Faça

1. Tool chamar outro tool diretamente (use goal para orquestrar)
2. Tool ter lógica de negócio complexa (split em sub-tools)
3. Tool depender de estado global
4. Tool sem tratamento de erro
5. Tool sem validação de input

---

## Integrando Tools com Backend

Os tools são **thin wrappers** sobre o código existente no backend:

```python
# tools/products/search.py

from backend.src.agent.tools import AgentTools

agent_tools = AgentTools(supabase_client, tiny_client)


def execute(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Busca produtos"""
    termo = input_data["termo"]
    limite = input_data.get("limite", 10)

    # Usa método existente
    result = agent_tools.buscar_produtos(termo, limite)

    return {"status": "success", "produtos": result}
```

---

## Testando Tools

### Test Unitário

```python
# tools/products/test_search.py

import pytest
from tools.products import search


def test_search_success():
    input_data = {"termo": "queijo", "limite": 5}
    result = search.execute(input_data)

    assert result["status"] == "success"
    assert "produtos" in result
    assert len(result["produtos"]) <= 5


def test_search_invalid_input():
    input_data = {}  # Faltando "termo"
    result = search.execute(input_data)

    assert result["status"] == "error"
    assert result["reason"] == "invalid_input"
```

### Test de Integração

```bash
# Run all tool tests
pytest tools/ -v

# Run specific module
pytest tools/products/ -v
```

---

## Debug de Tools

Se um tool falhar:

1. **Ver logs:**
   ```bash
   grep "Tool: product/search" logs/app.log
   ```

2. **Testar isoladamente:**
   ```bash
   python tools/products/search.py
   ```

3. **Validar input:**
   ```python
   print(json.dumps(input_data, indent=2))
   ```

4. **Verificar dependências:**
   - Supabase conectado?
   - Tiny API funcional?
   - Redis ativo?

---

## Métricas de Tools

- **Total de tools:** 20+
- **Cobertura de testes:** > 90%
- **Tempo médio execução:** < 500ms
- **Taxa de sucesso:** > 98%

---

**Última atualização:** 11/02/2026
**Versão:** 2.0.0-GOTCHA
