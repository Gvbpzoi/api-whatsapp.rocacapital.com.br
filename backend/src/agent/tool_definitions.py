"""
Definições de Tools para OpenAI Function Calling.
Cada tool é um dict seguindo o schema OpenAI tools.
"""
from typing import List, Dict


def get_tool_definitions() -> List[Dict]:
    """Retorna lista de definições de tools OpenAI."""
    return [
        BUSCAR_PRODUTOS,
        ADD_TO_CART,
        REMOVER_DO_CARRINHO,
        ALTERAR_QUANTIDADE,
        VIEW_CART,
        LIMPAR_CARRINHO,
        GERAR_PIX,
        GERAR_PAGAMENTO,
        ENVIAR_QR_CODE_PIX,
        ENVIAR_FOTO_PRODUTO,
        CALCULAR_FRETE,
        CONFIRMAR_FRETE,
        SALVAR_ENDERECO,
        BUSCAR_HISTORICO_COMPRAS,
        VERIFICAR_STATUS_PEDIDO,
        ESCALAR_ATENDIMENTO,
    ]


BUSCAR_PRODUTOS = {
    "type": "function",
    "function": {
        "name": "buscar_produtos",
        "description": "Busca produtos no catalogo da Roca Capital. Use quando cliente perguntar sobre produtos, precos ou disponibilidade.",
        "parameters": {
            "type": "object",
            "properties": {
                "termo": {
                    "type": "string",
                    "description": "Termo de busca (ex: 'queijo canastra', 'azeite', 'cafe', 'doce de leite')",
                },
                "limite": {
                    "type": "integer",
                    "description": "Numero maximo de resultados",
                    "default": 10,
                },
            },
            "required": ["termo"],
        },
    },
}

ADD_TO_CART = {
    "type": "function",
    "function": {
        "name": "add_to_cart",
        "description": "Adiciona produto ao carrinho APOS confirmacao do cliente. NUNCA chame sem o cliente ter confirmado que quer o produto.",
        "parameters": {
            "type": "object",
            "properties": {
                "produto_nome": {
                    "type": "string",
                    "description": "Nome EXATO do produto retornado pelo buscar_produtos. NUNCA abrevie.",
                },
                "preco": {
                    "type": "number",
                    "description": "Preco unitario como numero decimal (ex: 85.00). NUNCA passe como string.",
                },
                "quantidade": {
                    "type": "integer",
                    "description": "Quantidade de unidades. Padrao 1.",
                    "default": 1,
                },
                "produto_id": {
                    "type": "string",
                    "description": "ID do produto retornado pelo buscar_produtos.",
                },
            },
            "required": ["produto_nome", "preco", "produto_id"],
        },
    },
}

REMOVER_DO_CARRINHO = {
    "type": "function",
    "function": {
        "name": "remover_do_carrinho",
        "description": "Remove um produto do carrinho do cliente.",
        "parameters": {
            "type": "object",
            "properties": {
                "produto_nome": {
                    "type": "string",
                    "description": "Nome do produto a remover do carrinho.",
                },
            },
            "required": ["produto_nome"],
        },
    },
}

ALTERAR_QUANTIDADE = {
    "type": "function",
    "function": {
        "name": "alterar_quantidade",
        "description": "Altera a quantidade de um produto no carrinho.",
        "parameters": {
            "type": "object",
            "properties": {
                "produto_nome": {
                    "type": "string",
                    "description": "Nome do produto no carrinho.",
                },
                "quantidade": {
                    "type": "integer",
                    "description": "Nova quantidade desejada.",
                },
            },
            "required": ["produto_nome", "quantidade"],
        },
    },
}

VIEW_CART = {
    "type": "function",
    "function": {
        "name": "view_cart",
        "description": "Mostra o carrinho atual do cliente com todos os itens e total. SEMPRE use antes de gerar pagamento ou confirmar valores.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

LIMPAR_CARRINHO = {
    "type": "function",
    "function": {
        "name": "limpar_carrinho",
        "description": "Limpa todo o carrinho do cliente. Use APOS gerar pagamento (pix ou cartao).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

GERAR_PIX = {
    "type": "function",
    "function": {
        "name": "gerar_pix",
        "description": "Gera pagamento PIX para o cliente. Use APENAS quando cliente escolher pagar com PIX.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

GERAR_PAGAMENTO = {
    "type": "function",
    "function": {
        "name": "gerar_pagamento",
        "description": "Gera link de pagamento para cartao de credito/debito. Use APENAS quando cliente escolher cartao. NUNCA use para PIX.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

ENVIAR_QR_CODE_PIX = {
    "type": "function",
    "function": {
        "name": "enviar_qr_code_pix",
        "description": "Envia imagem do QR Code PIX para o cliente. So use quando cliente pedir explicitamente o QR Code.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

ENVIAR_FOTO_PRODUTO = {
    "type": "function",
    "function": {
        "name": "enviar_foto_produto",
        "description": "Envia foto de um produto para o cliente via WhatsApp.",
        "parameters": {
            "type": "object",
            "properties": {
                "produto_id": {
                    "type": "string",
                    "description": "ID do produto retornado pelo buscar_produtos.",
                },
            },
            "required": ["produto_id"],
        },
    },
}

CALCULAR_FRETE = {
    "type": "function",
    "function": {
        "name": "calcular_frete",
        "description": "Calcula o frete de entrega para o endereco do cliente. Sempre use para ter o calculo exato.",
        "parameters": {
            "type": "object",
            "properties": {
                "endereco_completo": {
                    "type": "string",
                    "description": "Endereco completo (rua, numero, bairro, cidade). Aceita tambem CEP.",
                },
                "cep": {
                    "type": "string",
                    "description": "CEP do destino (8 digitos, ex: '30160-011'). Opcional se ja estiver no endereco.",
                },
                "valor_pedido": {
                    "type": "number",
                    "description": "Valor total do pedido em reais.",
                },
                "peso_kg": {
                    "type": "number",
                    "description": "Peso total dos produtos em kg.",
                    "default": 1.0,
                },
            },
            "required": ["endereco_completo", "valor_pedido"],
        },
    },
}

CONFIRMAR_FRETE = {
    "type": "function",
    "function": {
        "name": "confirmar_frete",
        "description": "Confirma a opcao de frete escolhida pelo cliente e salva no banco.",
        "parameters": {
            "type": "object",
            "properties": {
                "tipo_frete": {
                    "type": "string",
                    "description": "Tipo do frete escolhido (ex: 'lalamove', 'correios_sedex').",
                },
                "valor_frete": {
                    "type": "number",
                    "description": "Valor do frete em reais.",
                },
                "prazo_entrega": {
                    "type": "string",
                    "description": "Prazo de entrega (ex: '45 minutos', '3-5 dias uteis').",
                },
            },
            "required": ["tipo_frete", "valor_frete", "prazo_entrega"],
        },
    },
}

SALVAR_ENDERECO = {
    "type": "function",
    "function": {
        "name": "salvar_endereco",
        "description": "Salva o endereco do cliente no banco de dados.",
        "parameters": {
            "type": "object",
            "properties": {
                "endereco": {
                    "type": "string",
                    "description": "Endereco COMPLETO que o cliente enviou.",
                },
            },
            "required": ["endereco"],
        },
    },
}

BUSCAR_HISTORICO_COMPRAS = {
    "type": "function",
    "function": {
        "name": "buscar_historico_compras",
        "description": "Busca produtos que o cliente ja comprou anteriormente. Use para sugerir recompra ANTES de finalizar pedido.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

VERIFICAR_STATUS_PEDIDO = {
    "type": "function",
    "function": {
        "name": "verificar_status_pedido",
        "description": "Verifica o status de um pedido pelo numero.",
        "parameters": {
            "type": "object",
            "properties": {
                "numero_pedido": {
                    "type": "string",
                    "description": "Numero do pedido a consultar.",
                },
            },
            "required": ["numero_pedido"],
        },
    },
}

ESCALAR_ATENDIMENTO = {
    "type": "function",
    "function": {
        "name": "escalar_atendimento",
        "description": "Transfere a conversa para atendimento humano. Use quando: cliente pede para falar com pessoa, voce nao consegue resolver, ou cliente esta frustrado. IMPORTANTE: inclua o nome do cliente (se souber) e um resumo da conversa para dar contexto a vendedora.",
        "parameters": {
            "type": "object",
            "properties": {
                "motivo": {
                    "type": "string",
                    "description": "Motivo da escalacao: 'pediu_humano', 'erro_agente', 'erro_consecutivo'.",
                    "enum": ["pediu_humano", "erro_agente", "erro_consecutivo"],
                },
                "descricao": {
                    "type": "string",
                    "description": "Descricao breve do motivo da escalacao.",
                },
                "nome_cliente": {
                    "type": "string",
                    "description": "Nome do cliente, se mencionado na conversa.",
                },
                "resumo_conversa": {
                    "type": "string",
                    "description": "Resumo breve da conversa ate o momento: o que o cliente pediu, o que foi feito, e por que precisa de ajuda humana.",
                },
            },
            "required": ["motivo", "descricao", "resumo_conversa"],
        },
    },
}
