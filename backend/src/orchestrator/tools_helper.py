"""
Tools Helper - Wrappers simplificados para as ferramentas GOTCHA
Versão rápida para deploy inicial
"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ToolsHelper:
    """Helper para executar tools do GOTCHA de forma simplificada"""

    def __init__(self, supabase_client=None, tiny_client=None):
        """
        Inicializa helper com clientes opcionais.

        Args:
            supabase_client: Cliente Supabase (opcional)
            tiny_client: Cliente Tiny (opcional)
        """
        self.supabase = supabase_client
        self.tiny = tiny_client

        # Mock data para desenvolvimento
        self.mock_produtos = [
            {
                "id": "1",
                "nome": "Queijo Canastra Meia-Cura 500g",
                "preco": 45.00,
                "estoque_atual": 15,
                "categoria": "queijos"
            },
            {
                "id": "2",
                "nome": "Queijo Prato Artesanal 400g",
                "preco": 35.00,
                "estoque_atual": 8,
                "categoria": "queijos"
            },
            {
                "id": "3",
                "nome": "Doce de Leite Tradicional 300g",
                "preco": 18.00,
                "estoque_atual": 20,
                "categoria": "doces"
            },
            {
                "id": "4",
                "nome": "Cachaça Artesanal Ouro 700ml",
                "preco": 65.00,
                "estoque_atual": 10,
                "categoria": "bebidas"
            },
            {
                "id": "5",
                "nome": "Café Torrado Moído Serra da Canastra 500g",
                "preco": 32.00,
                "estoque_atual": 12,
                "categoria": "bebidas"
            }
        ]

        # Carrinhos temporários (em memória)
        self.carrinhos = {}

    def buscar_produtos(self, termo: str, limite: int = 10) -> Dict[str, Any]:
        """
        Busca produtos por termo.

        Args:
            termo: Termo de busca
            limite: Máximo de resultados

        Returns:
            Dict com produtos encontrados
        """
        try:
            logger.info(f"🔍 Buscando: {termo}")

            # Se temos Supabase, usar ele
            if self.supabase:
                try:
                    result = self.supabase.table("produtos").select("*").ilike("nome", f"%{termo}%").limit(limite).execute()
                    produtos = result.data if result.data else []

                    if produtos:
                        logger.info(f"✅ Supabase: {len(produtos)} produtos")
                        return {"status": "success", "produtos": produtos, "source": "supabase"}
                except Exception as e:
                    logger.warning(f"⚠️ Supabase falhou, usando mock: {e}")

            # Fallback: busca em mock data
            termo_lower = termo.lower()
            produtos_encontrados = [
                p for p in self.mock_produtos
                if termo_lower in p["nome"].lower() or termo_lower in p["categoria"].lower()
            ][:limite]

            logger.info(f"✅ Mock: {len(produtos_encontrados)} produtos")

            return {
                "status": "success",
                "produtos": produtos_encontrados,
                "source": "mock"
            }

        except Exception as e:
            logger.error(f"❌ Erro na busca: {e}")
            return {"status": "error", "message": str(e)}

    def adicionar_carrinho(self, telefone: str, produto_id: str, quantidade: int = 1) -> Dict[str, Any]:
        """
        Adiciona produto ao carrinho.

        Args:
            telefone: Telefone do cliente
            produto_id: ID do produto
            quantidade: Quantidade

        Returns:
            Dict com resultado
        """
        try:
            logger.info(f"🛒 Adicionando produto {produto_id} (qty: {quantidade}) para {telefone}")

            # Criar carrinho se não existe
            if telefone not in self.carrinhos:
                self.carrinhos[telefone] = []

            # Buscar produto
            produto = next((p for p in self.mock_produtos if p["id"] == produto_id), None)

            if not produto:
                return {"status": "error", "message": "Produto não encontrado"}

            # Verificar estoque
            if produto["estoque_atual"] < quantidade:
                return {
                    "status": "error",
                    "message": f"Estoque insuficiente. Disponível: {produto['estoque_atual']}"
                }

            # Adicionar ao carrinho
            self.carrinhos[telefone].append({
                "produto": produto,
                "quantidade": quantidade,
                "subtotal": produto["preco"] * quantidade
            })

            logger.info(f"✅ Produto adicionado. Total itens: {len(self.carrinhos[telefone])}")

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

            # Mock: retornar pedido de exemplo
            pedidos_mock = [
                {
                    "numero": "#20260210123456",
                    "total": 108.00,
                    "status": "enviado",
                    "criado_em": "2026-02-10T10:30:00"
                }
            ]

            return {
                "status": "success",
                "pedidos": pedidos_mock,
                "total": len(pedidos_mock)
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
