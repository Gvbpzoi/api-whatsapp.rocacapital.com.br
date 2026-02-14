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

# Importar serviço de carrinhos Supabase
try:
    from ..services.supabase_carrinho import get_supabase_carrinho
    SUPABASE_CARRINHO_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Módulo supabase_carrinho não disponível - usando mock: {e}")
    SUPABASE_CARRINHO_AVAILABLE = False


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
        
        # Novo serviço de carrinhos persistentes
        if SUPABASE_CARRINHO_AVAILABLE:
            self.carrinho_service = get_supabase_carrinho()
            if self.carrinho_service.connection:
                logger.info("✅ Usando carrinhos persistentes (Supabase)")
                self.use_persistent_cart = True
            else:
                logger.warning("⚠️ Supabase não disponível, usando carrinhos em memória")
                self.use_persistent_cart = False
                self.carrinhos = {}  # Fallback para memória
        else:
            self.carrinho_service = None
            self.use_persistent_cart = False
            self.carrinhos = {}  # Fallback para memória
            logger.info("⚠️ Usando carrinhos em memória (não persistem em redeploy)")

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

    def contar_por_termos(self, termos: list) -> Dict[str, int]:
        """
        Conta produtos disponíveis para cada termo de busca.
        Usado para responder perguntas multi-categoria como "tem doce e cafe?"

        Args:
            termos: Lista de termos (ex: ["doce", "cafe"])

        Returns:
            Dict com {termo: contagem} (ex: {"doce": 12, "cafe": 8})
        """
        resultado = {}
        try:
            if self.produtos_service and self.produtos_service.database_url:
                for termo in termos:
                    contagem = self.produtos_service.contar_por_termo(termo)
                    resultado[termo] = contagem
                    logger.info(f"📊 '{termo}': {contagem} produtos")
            else:
                # Mock fallback — partial match (termo in nome/categoria)
                for termo in termos:
                    termo_lower = termo.lower()
                    count = sum(
                        1 for p in self.mock_produtos
                        if termo_lower in p["nome"].lower()
                        or termo_lower in p.get("categoria", "").lower()
                        or p["nome"].lower().startswith(termo_lower)
                        or p.get("categoria", "").lower().startswith(termo_lower)
                    )
                    resultado[termo] = count
        except Exception as e:
            logger.error(f"❌ Erro ao contar por termos: {e}")

        return resultado

    def adicionar_carrinho(self, telefone: str, produto_id: str, quantidade: int = 1) -> Dict[str, Any]:
        """
        Adiciona produto ao carrinho (AGORA COM PERSISTÊNCIA).

        Args:
            telefone: Telefone do cliente
            produto_id: ID do produto (UUID ou tiny_id)
            quantidade: Quantidade

        Returns:
            Dict com resultado
        """
        try:
            logger.info(f"🛒 Adicionando produto {produto_id} (qty: {quantidade}) para {telefone}")

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
            
            # Se usar carrinho persistente, verificar quantidade já no carrinho
            if self.use_persistent_cart:
                items_carrinho = self.carrinho_service.obter_carrinho(telefone)
                quantidade_no_carrinho = 0
                for item in items_carrinho:
                    if str(item["produto_id"]) == str(produto_id):
                        quantidade_no_carrinho = item["quantidade"]
                        break
                
                quantidade_total = quantidade_no_carrinho + quantidade
                
                if estoque < quantidade_total:
                    return {
                        "status": "estoque_insuficiente",
                        "produto": produto,
                        "quantidade_solicitada": quantidade_total,
                        "quantidade_disponivel": estoque,
                        "message": f"Você já tem {quantidade_no_carrinho} no carrinho. Não há estoque para mais {quantidade}."
                    }
            else:
                # Modo memória (antigo)
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

            # ADICIONAR AO CARRINHO (persistente ou memória)
            if self.use_persistent_cart:
                # Usar carrinho persistente (Supabase)
                result = self.carrinho_service.adicionar_item(
                    telefone=telefone,
                    produto_id=str(produto.get("id")),
                    produto_nome=produto.get("nome"),
                    preco_unitario=float(preco),
                    quantidade=quantidade
                )
                
                if result["status"] == "error":
                    return result
                
                # Obter carrinho atualizado
                carrinho = self.carrinho_service.obter_carrinho(telefone)
                total_itens = len(carrinho)
                
            else:
                # Usar carrinho em memória (fallback)
                if telefone not in self.carrinhos:
                    self.carrinhos[telefone] = []
                
                # Verificar se produto já está no carrinho
                item_existente = None
                for item in self.carrinhos[telefone]:
                    if str(item["produto_id"]) == str(produto_id):
                        item_existente = item
                        break
                
                if item_existente:
                    # Atualizar quantidade
                    nova_quantidade = item_existente["quantidade"] + quantidade
                    item_existente["quantidade"] = nova_quantidade
                    item_existente["subtotal"] = float(preco) * nova_quantidade
                    logger.info(f"✅ Quantidade atualizada: {item_existente['nome']} -> {nova_quantidade} un")
                else:
                    # Adicionar novo item
                    self.carrinhos[telefone].append({
                        "produto_id": str(produto.get("id")),
                        "nome": produto.get("nome"),
                        "preco_unitario": float(preco),
                        "quantidade": quantidade,
                        "subtotal": float(preco) * quantidade
                    })
                    logger.info(f"✅ Produto adicionado: {produto.get('nome')}")
                
                carrinho = self.carrinhos[telefone]
                total_itens = len(carrinho)

            return {
                "status": "success",
                "carrinho": carrinho,
                "total_itens": total_itens,
                "quantidade_total": sum(item.get("quantidade", 0) for item in carrinho)
            }

        except Exception as e:
            logger.error(f"❌ Erro ao adicionar: {e}")
            return {"status": "error", "message": str(e)}
    
    def adicionar_por_termo(self, telefone: str, termo: str, quantidade: int = 1) -> Dict[str, Any]:
        """
        Busca produto por termo e adiciona ao carrinho.
        
        Args:
            telefone: Telefone do cliente
            termo: Termo de busca
            quantidade: Quantidade
            
        Returns:
            Dict com resultado
        """
        try:
            logger.info(f"🔍➕ Buscando e adicionando: '{termo}' (qty: {quantidade})")
            
            # Buscar produto
            result = self.buscar_produtos(termo, limite=1)
            
            if result["status"] != "success" or not result["produtos"]:
                return {"status": "error", "message": "Produto não encontrado"}
            
            produto = result["produtos"][0]
            produto_id = str(produto.get("id"))
            
            # Adicionar ao carrinho
            return self.adicionar_carrinho(telefone, produto_id, quantidade)
            
        except Exception as e:
            logger.error(f"❌ Erro ao adicionar por termo: {e}")
            return {"status": "error", "message": str(e)}

    def remover_item(self, telefone: str, produto_id: str) -> Dict[str, Any]:
        """
        Remove item do carrinho.

        Args:
            telefone: Telefone do cliente
            produto_id: ID do produto a remover

        Returns:
            Dict com resultado
        """
        try:
            logger.info(f"🗑️ Removendo produto {produto_id} do carrinho de {telefone}")

            if self.use_persistent_cart:
                success = self.carrinho_service.remover_item(telefone, produto_id)
                if not success:
                    return {"status": "error", "message": "Erro ao remover item"}
                carrinho = self.carrinho_service.obter_carrinho(telefone)
            else:
                carrinho = self.carrinhos.get(telefone, [])
                item_encontrado = None
                for item in carrinho:
                    if str(item["produto_id"]) == str(produto_id):
                        item_encontrado = item
                        break
                if not item_encontrado:
                    return {"status": "error", "message": "Item não encontrado no carrinho"}
                carrinho = [item for item in carrinho if str(item["produto_id"]) != str(produto_id)]
                self.carrinhos[telefone] = carrinho

            return {
                "status": "success",
                "carrinho": carrinho,
                "total_itens": len(carrinho),
                "quantidade_total": sum(item.get("quantidade", 0) for item in carrinho),
            }

        except Exception as e:
            logger.error(f"❌ Erro ao remover item: {e}")
            return {"status": "error", "message": str(e)}

    def alterar_quantidade(self, telefone: str, produto_id: str, nova_quantidade: int) -> Dict[str, Any]:
        """
        Altera a quantidade de um item no carrinho.

        Args:
            telefone: Telefone do cliente
            produto_id: ID do produto
            nova_quantidade: Nova quantidade desejada

        Returns:
            Dict com resultado
        """
        try:
            logger.info(f"✏️ Alterando quantidade de {produto_id} para {nova_quantidade}")

            if nova_quantidade <= 0:
                return self.remover_item(telefone, produto_id)

            if self.use_persistent_cart:
                success = self.carrinho_service.atualizar_quantidade(telefone, produto_id, nova_quantidade)
                if not success:
                    return {"status": "error", "message": "Erro ao alterar quantidade"}
                carrinho = self.carrinho_service.obter_carrinho(telefone)
            else:
                carrinho = self.carrinhos.get(telefone, [])
                item_encontrado = None
                for item in carrinho:
                    if str(item["produto_id"]) == str(produto_id):
                        item_encontrado = item
                        break
                if not item_encontrado:
                    return {"status": "error", "message": "Item não encontrado no carrinho"}
                item_encontrado["quantidade"] = nova_quantidade
                item_encontrado["subtotal"] = item_encontrado["preco_unitario"] * nova_quantidade

            return {
                "status": "success",
                "carrinho": carrinho,
                "total_itens": len(carrinho),
                "quantidade_total": sum(item.get("quantidade", 0) for item in carrinho),
            }

        except Exception as e:
            logger.error(f"❌ Erro ao alterar quantidade: {e}")
            return {"status": "error", "message": str(e)}

    def limpar_carrinho(self, telefone: str) -> Dict[str, Any]:
        """
        Limpa todos os itens do carrinho.

        Args:
            telefone: Telefone do cliente

        Returns:
            Dict com resultado
        """
        try:
            logger.info(f"🗑️ Limpando carrinho de {telefone[:8]}")
            if self.use_persistent_cart:
                self.carrinho_service.limpar_carrinho(telefone)
            else:
                self.carrinhos.pop(telefone, None)
            return {"status": "success"}
        except Exception as e:
            logger.error(f"❌ Erro ao limpar carrinho: {e}")
            return {"status": "error", "message": str(e)}

    def ver_carrinho(self, telefone: str) -> Dict[str, Any]:
        """
        Visualiza carrinho do cliente (PERSISTENTE).

        Args:
            telefone: Telefone do cliente

        Returns:
            Dict com carrinho
        """
        try:
            logger.info(f"👀 Ver carrinho: {telefone}")

            if self.use_persistent_cart:
                # Carrinho persistente
                carrinho = self.carrinho_service.obter_carrinho(telefone)
                total = self.carrinho_service.calcular_total(telefone)
            else:
                # Carrinho em memória
                carrinho = self.carrinhos.get(telefone, [])
                total = sum(item["subtotal"] for item in carrinho)

            if not carrinho:
                return {
                    "status": "success",
                    "carrinho": [],
                    "total": 0,
                    "vazio": True
                }

            return {
                "status": "success",
                "carrinho": carrinho,
                "total": total,
                "total_itens": len(carrinho),
                "quantidade_total": sum(item.get("quantidade", 0) for item in carrinho),
                "vazio": False
            }

        except Exception as e:
            logger.error(f"❌ Erro ao ver carrinho: {e}")
            return {"status": "error", "message": str(e)}

    def finalizar_pedido(self, telefone: str, metodo_pagamento: str = "pix") -> Dict[str, Any]:
        """
        Finaliza pedido (LIMPA CARRINHO PERSISTENTE).

        Args:
            telefone: Telefone do cliente
            metodo_pagamento: Método de pagamento

        Returns:
            Dict com pedido criado
        """
        try:
            logger.info(f"💳 Finalizando pedido: {telefone} ({metodo_pagamento})")

            if self.use_persistent_cart:
                carrinho = self.carrinho_service.obter_carrinho(telefone)
                total = self.carrinho_service.calcular_total(telefone)
            else:
                carrinho = self.carrinhos.get(telefone, [])
                total = sum(item["subtotal"] for item in carrinho)

            if not carrinho:
                return {"status": "error", "message": "Carrinho vazio"}

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
            if self.use_persistent_cart:
                self.carrinho_service.limpar_carrinho(telefone)
            else:
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
