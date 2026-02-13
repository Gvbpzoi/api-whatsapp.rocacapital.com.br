"""
Tools Helper - Wrappers simplificados para as ferramentas GOTCHA
Versão rápida para deploy inicial - AGORA COM PRODUTOS REAIS DO SUPABASE
"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Importar serviço de produtos Supabase
try:
    from ..services.supabase_produtos import get_supabase_produtos
    SUPABASE_PRODUTOS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Módulo supabase_produtos não disponível - usando mock: {e}")
    SUPABASE_PRODUTOS_AVAILABLE = False


class ToolsHelper:
    """Helper para executar tools do GOTCHA de forma simplificada"""

    def __init__(self, supabase_client=None, tiny_client=None):
        """
        Inicializa helper com clientes opcionais.

        Args:
            supabase_client: Cliente Supabase (opcional - deprecated)
            tiny_client: Cliente Tiny (opcional)
        """
        self.tiny = tiny_client

        # Novo serviço de produtos (direto com psycopg2)
        if SUPABASE_PRODUTOS_AVAILABLE:
            self.produtos_service = get_supabase_produtos()
            logger.info("✅ Usando produtos reais do Supabase")
        else:
            self.produtos_service = None
            logger.info("⚠️ Usando mock de produtos")

        # Mock data para fallback (se Supabase não disponível)
        self.mock_produtos = [
            {
                "id": "1",
                "nome": "Queijo Canastra Meia-Cura 500g",
                "preco": 45.00,
                "quantidade_estoque": 15,
                "categoria": "queijos"
            },
            {
                "id": "2",
                "nome": "Queijo Prato Artesanal 400g",
                "preco": 35.00,
                "quantidade_estoque": 8,
                "categoria": "queijos"
            },
            {
                "id": "3",
                "nome": "Doce de Leite Tradicional 300g",
                "preco": 18.00,
                "quantidade_estoque": 20,
                "categoria": "doces"
            },
            {
                "id": "4",
                "nome": "Azeite Extra Virgem Mineiro 250ml",
                "preco": 42.00,
                "quantidade_estoque": 12,
                "categoria": "azeites"
            },
            {
                "id": "5",
                "nome": "Cachaça Artesanal de Alambique 700ml",
                "preco": 85.00,
                "quantidade_estoque": 10,
                "categoria": "bebidas"
            },
            {
                "id": "6",
                "nome": "Café Especial Torrado em Grão 250g",
                "preco": 28.00,
                "quantidade_estoque": 25,
                "categoria": "cafes"
            },
            {
                "id": "7",
                "nome": "Mel de Abelha Silvestre 500g",
                "preco": 32.00,
                "quantidade_estoque": 18,
                "categoria": "doces"
            },
            {
                "id": "8",
                "nome": "Goiabada Cascão 600g",
                "preco": 22.00,
                "quantidade_estoque": 14,
                "categoria": "doces"
            }
        ]

        # Carrinhos temporários (em memória)
        self.carrinhos = {}

    def buscar_produtos(self, termo: str, limite: int = 10) -> Dict[str, Any]:
        """
        Busca produtos por termo (AGORA COM DADOS REAIS DO SUPABASE).

        Args:
            termo: Termo de busca
            limite: Máximo de resultados

        Returns:
            Dict com produtos encontrados
        """
        try:
            logger.info(f"🔍 Buscando: '{termo}'")

            # Tentar usar serviço de produtos Supabase
            if self.produtos_service:
                try:
                    produtos = self.produtos_service.buscar_produtos(
                        termo=termo,
                        limite=limite,
                        apenas_disponiveis=True
                    )

                    if produtos:
                        logger.info(f"✅ Supabase: {len(produtos)} produtos encontrados")
                        return {
                            "status": "success",
                            "produtos": produtos,
                            "source": "supabase",
                            "total": len(produtos)
                        }
                    else:
                        logger.info("ℹ️ Nenhum produto encontrado no Supabase")
                        return {
                            "status": "success",
                            "produtos": [],
                            "source": "supabase",
                            "total": 0,
                            "message": "Nenhum produto encontrado"
                        }

                except Exception as e:
                    logger.warning(f"⚠️ Erro no Supabase, usando fallback mock: {e}")

            # Fallback: busca em mock data
            termo_lower = termo.lower()
            produtos_encontrados = [
                p for p in self.mock_produtos
                if termo_lower in p["nome"].lower() or termo_lower in p.get("categoria", "").lower()
            ][:limite]

            logger.info(f"⚠️ Mock fallback: {len(produtos_encontrados)} produtos")

            return {
                "status": "success",
                "produtos": produtos_encontrados,
                "source": "mock",
                "total": len(produtos_encontrados)
            }

        except Exception as e:
            logger.error(f"❌ Erro na busca: {e}")
            return {"status": "error", "message": str(e)}

    def adicionar_carrinho(self, telefone: str, produto_id: str, quantidade: int = 1) -> Dict[str, Any]:
        """
        Adiciona produto ao carrinho (AGORA COM PRODUTOS REAIS).

        Args:
            telefone: Telefone do cliente
            produto_id: ID do produto (UUID ou tiny_id)
            quantidade: Quantidade

        Returns:
            Dict com resultado
        """
        try:
            logger.info(f"🛒 Adicionando produto {produto_id} (qty: {quantidade}) para {telefone}")

            # Criar carrinho se não existe
            if telefone not in self.carrinhos:
                self.carrinhos[telefone] = []

            # Buscar produto no Supabase
            produto = None
            if self.produtos_service:
                try:
                    produto = self.produtos_service.buscar_produto_por_id(produto_id)
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao buscar produto {produto_id}: {e}")

            # Fallback: buscar em mock
            if not produto:
                produto = next((p for p in self.mock_produtos if str(p["id"]) == str(produto_id)), None)

            if not produto:
                return {"status": "error", "message": "Produto não encontrado"}

            # Verificar estoque
            estoque = produto.get("quantidade_estoque", 0)
            if estoque < quantidade:
                return {
                    "status": "estoque_insuficiente",
                    "produto": produto,
                    "quantidade_solicitada": quantidade,
                    "quantidade_disponivel": estoque,
                    "message": "Estoque insuficiente para a quantidade solicitada"
                }

            # Usar preço promocional se disponível
            preco = produto.get("preco_promocional") or produto.get("preco", 0)

            # Verificar se produto já está no carrinho
            item_existente = None
            for item in self.carrinhos[telefone]:
                if str(item["produto_id"]) == str(produto_id):
                    item_existente = item
                    break
            
            if item_existente:
                # Produto já existe: somar quantidade
                nova_quantidade = item_existente["quantidade"] + quantidade
                
                # Verificar estoque para nova quantidade total
                if estoque < nova_quantidade:
                    return {
                        "status": "estoque_insuficiente",
                        "produto": produto,
                        "quantidade_solicitada": nova_quantidade,
                        "quantidade_disponivel": estoque,
                        "message": f"Você já tem {item_existente['quantidade']} no carrinho. Não há estoque para mais {quantidade}."
                    }
                
                # Atualizar quantidade e subtotal
                item_existente["quantidade"] = nova_quantidade
                item_existente["subtotal"] = float(preco) * nova_quantidade
                logger.info(f"✅ Quantidade atualizada: {item_existente['nome']} -> {nova_quantidade} un")
            else:
                # Produto novo: adicionar ao carrinho
                self.carrinhos[telefone].append({
                    "produto_id": str(produto.get("id")),
                    "nome": produto.get("nome"),
                    "preco_unitario": float(preco),
                    "quantidade": quantidade,
                    "subtotal": float(preco) * quantidade
                })
                logger.info(f"✅ Produto adicionado: {produto.get('nome')}")

            return {
                "status": "success",
                "carrinho": self.carrinhos[telefone],
                "total_itens": len(self.carrinhos[telefone])
            }

        except Exception as e:
            logger.error(f"❌ Erro ao adicionar: {e}")
            return {"status": "error", "message": str(e)}

    def ver_carrinho(self, telefone: str) -> Dict[str, Any]:
        """
        Visualiza carrinho do cliente.

        Args:
            telefone: Telefone do cliente

        Returns:
            Dict com carrinho
        """
        try:
            logger.info(f"👀 Ver carrinho: {telefone}")

            carrinho = self.carrinhos.get(telefone, [])

            if not carrinho:
                return {
                    "status": "success",
                    "carrinho": [],
                    "total": 0,
                    "vazio": True
                }

            total = sum(item["subtotal"] for item in carrinho)

            return {
                "status": "success",
                "carrinho": carrinho,
                "total": total,
                "total_itens": len(carrinho),
                "vazio": False
            }

        except Exception as e:
            logger.error(f"❌ Erro ao ver carrinho: {e}")
            return {"status": "error", "message": str(e)}

    def finalizar_pedido(self, telefone: str, metodo_pagamento: str = "pix") -> Dict[str, Any]:
        """
        Finaliza pedido.

        Args:
            telefone: Telefone do cliente
            metodo_pagamento: Método de pagamento

        Returns:
            Dict com pedido criado
        """
        try:
            logger.info(f"💳 Finalizando pedido: {telefone} ({metodo_pagamento})")

            carrinho = self.carrinhos.get(telefone, [])

            if not carrinho:
                return {"status": "error", "message": "Carrinho vazio"}

            total = sum(item["subtotal"] for item in carrinho)

            # Criar pedido (mock)
            pedido = {
                "numero": f"#{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "telefone": telefone,
                "itens": carrinho,
                "total": total,
                "metodo_pagamento": metodo_pagamento,
                "status": "aguardando_pagamento",
                "criado_em": datetime.now().isoformat()
            }

            # Limpar carrinho
            self.carrinhos[telefone] = []

            logger.info(f"✅ Pedido {pedido['numero']} criado")

            return {
                "status": "success",
                "pedido": pedido
            }

        except Exception as e:
            logger.error(f"❌ Erro ao finalizar: {e}")
            return {"status": "error", "message": str(e)}

    def consultar_pedidos(self, telefone: str) -> Dict[str, Any]:
        """
        Consulta pedidos do cliente.

        Args:
            telefone: Telefone do cliente

        Returns:
            Dict com pedidos
        """
        try:
            logger.info(f"📦 Consultando pedidos: {telefone}")

            # TODO: Integrar com Tiny ERP ou Supabase para buscar pedidos reais
            # Por enquanto, retornar lista vazia (sem pedidos)
            
            return {
                "status": "success",
                "pedidos": [],
                "total": 0
            }

        except Exception as e:
            logger.error(f"❌ Erro ao consultar: {e}")
            return {"status": "error", "message": str(e)}


# Singleton global
_tools_instance: Optional[ToolsHelper] = None


def get_tools_helper() -> ToolsHelper:
    """
    Retorna instância singleton do ToolsHelper.

    Returns:
        ToolsHelper instance
    """
    global _tools_instance

    if _tools_instance is None:
        _tools_instance = ToolsHelper()

    return _tools_instance


# Para testes
if __name__ == "__main__":
    print("🧪 Testando ToolsHelper\n")

    tools = ToolsHelper()

    # Teste 1: Buscar produtos
    print("1️⃣ Buscar queijo:")
    result = tools.buscar_produtos("queijo")
    print(f"   Status: {result['status']}")
    print(f"   Produtos: {len(result.get('produtos', []))}")
    print()

    # Teste 2: Adicionar ao carrinho
    print("2️⃣ Adicionar ao carrinho:")
    result = tools.adicionar_carrinho("5531999999999", "1", 2)
    print(f"   Status: {result['status']}")
    print(f"   Total itens: {result.get('total_itens', 0)}")
    print()

    # Teste 3: Ver carrinho
    print("3️⃣ Ver carrinho:")
    result = tools.ver_carrinho("5531999999999")
    print(f"   Status: {result['status']}")
    print(f"   Total: R$ {result.get('total', 0):.2f}")
    print()

    # Teste 4: Finalizar pedido
    print("4️⃣ Finalizar pedido:")
    result = tools.finalizar_pedido("5531999999999", "pix")
    print(f"   Status: {result['status']}")
    if result['status'] == 'success':
        print(f"   Pedido: {result['pedido']['numero']}")
    print()

    print("✅ Todos os testes concluídos!")
