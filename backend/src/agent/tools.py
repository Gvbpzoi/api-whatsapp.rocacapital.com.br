"""
Tools do Agente WhatsApp - Roça Capital

Ferramentas que o agente pode usar para atender clientes.
Cada tool é uma função que o LangChain Agent pode chamar.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from loguru import logger

from ..services.sync_service import SyncService
from supabase import Client


# ==================== Tool Schemas ====================

class BuscarProdutosInput(BaseModel):
    """Input para buscar produtos"""
    termo: str = Field(description="Termo de busca (nome do produto, categoria, etc)")
    limite: int = Field(default=10, description="Número máximo de resultados")


class AdicionarCarrinhoInput(BaseModel):
    """Input para adicionar produto ao carrinho"""
    telefone: str = Field(description="Telefone do cliente")
    produto_nome: str = Field(description="Nome EXATO do produto (do buscar_produtos)")
    preco: float = Field(description="Preço unitário como número (ex: 125.00)")
    quantidade: int = Field(default=1, description="Quantidade de unidades")


class VerCarrinhoInput(BaseModel):
    """Input para ver carrinho"""
    telefone: str = Field(description="Telefone do cliente")


class CalcularFreteInput(BaseModel):
    """Input para calcular frete"""
    telefone: str = Field(description="Telefone do cliente")
    endereco: str = Field(description="Endereço completo (rua, número, bairro, cidade, UF)")


class FinalizarPedidoInput(BaseModel):
    """Input para finalizar pedido"""
    telefone: str = Field(description="Telefone do cliente")
    metodo_pagamento: str = Field(description="Método: 'pix' ou 'cartao'")


class BuscarPedidoInput(BaseModel):
    """Input para buscar pedido do cliente"""
    telefone: Optional[str] = Field(None, description="Telefone do cliente")
    numero_pedido: Optional[str] = Field(None, description="Número do pedido")
    cpf: Optional[str] = Field(None, description="CPF do cliente")


# ==================== Tools ====================

class AgentTools:
    """
    Ferramentas disponíveis para o agente
    """

    def __init__(
        self,
        supabase: Client,
        sync_service: SyncService
    ):
        self.supabase = supabase
        self.sync_service = sync_service

    # ==================== 1. Buscar Produtos ====================

    def buscar_produtos(self, termo: str, limite: int = 10) -> str:
        """
        Busca produtos no catálogo usando full-text search.

        Use quando cliente perguntar sobre produtos, preços ou estoque.

        Args:
            termo: Termo de busca (ex: "queijo canastra", "geleia")
            limite: Máximo de resultados (padrão: 10)

        Returns:
            String formatada com produtos encontrados
        """
        try:
            logger.info(f"🔍 Buscando produtos: {termo}")

            # Usar função SQL de busca inteligente
            result = self.supabase.rpc(
                "buscar_produtos",
                {"termo_busca": termo, "limite": limite}
            ).execute()

            produtos = result.data

            if not produtos:
                return f"❌ Não encontrei produtos para '{termo}'. Pode tentar outro termo?"

            # Formatar resposta
            if len(produtos) == 1:
                # 1 produto - mostrar completo
                p = produtos[0]
                resposta = f"📦 **{p['nome']}**\n"
                resposta += f"💰 R$ {float(p['preco']):.2f}\n"

                if p.get('estoque_atual'):
                    resposta += f"📊 Estoque: {int(p['estoque_atual'])} unidades\n"

                if p.get('descricao'):
                    resposta += f"ℹ️ {p['descricao'][:200]}\n"

                return resposta

            elif len(produtos) <= 5:
                # Poucos produtos - mostrar todos
                resposta = f"🔍 Encontrei {len(produtos)} opções:\n\n"

                for i, p in enumerate(produtos, 1):
                    resposta += f"**{i}. {p['nome']}**\n"
                    resposta += f"   💰 R$ {float(p['preco']):.2f}\n"

                    if p.get('estoque_atual') and int(p['estoque_atual']) > 0:
                        resposta += f"   📊 Estoque: {int(p['estoque_atual'])}\n"

                    resposta += "\n"

                resposta += "Qual te interessa?"
                return resposta

            else:
                # Muitos produtos - mostrar resumo
                resposta = f"🔍 Encontrei **{len(produtos)} produtos** para '{termo}':\n\n"

                # Mostrar primeiros 5
                for i, p in enumerate(produtos[:5], 1):
                    resposta += f"{i}. {p['nome']} - R$ {float(p['preco']):.2f}\n"

                resposta += f"\n... e mais {len(produtos) - 5} opções.\n\n"
                resposta += "Quer ver os mais vendidos ou as recomendações da casa?"

                return resposta

        except Exception as e:
            logger.error(f"❌ Erro ao buscar produtos: {e}")
            return f"❌ Ops, tive um problema ao buscar. Pode tentar novamente?"

    # ==================== 2. Adicionar ao Carrinho ====================

    def adicionar_carrinho(
        self,
        telefone: str,
        produto_nome: str,
        preco: float,
        quantidade: int = 1
    ) -> str:
        """
        Adiciona produto ao carrinho do cliente.

        IMPORTANTE:
        - Use o nome EXATO retornado pelo buscar_produtos
        - Passe o preço como número (ex: 125.00, NÃO "R$ 125,00")
        - SEMPRE confirme com cliente ANTES de adicionar

        Args:
            telefone: Telefone do cliente
            produto_nome: Nome EXATO do produto
            preco: Preço unitário como float
            quantidade: Quantidade (padrão: 1)

        Returns:
            String confirmando adição
        """
        try:
            logger.info(f"🛒 Adicionando ao carrinho: {produto_nome} x{quantidade}")

            # 1. Buscar produto no banco para obter detalhes
            produto = self.supabase.table("produtos")\
                .select("*")\
                .ilike("nome", f"%{produto_nome}%")\
                .limit(1)\
                .execute()

            if not produto.data:
                return f"❌ Produto '{produto_nome}' não encontrado. Use o nome exato do buscar_produtos."

            prod_data = produto.data[0]

            # 2. Verificar se carrinho existe
            carrinho = self.supabase.table("carrinhos")\
                .select("*")\
                .eq("telefone", telefone)\
                .eq("ativo", True)\
                .execute()

            # Preparar item
            item = {
                "produto_id": prod_data["id"],
                "sku": prod_data["sku"],
                "nome": prod_data["nome"],
                "quantidade": quantidade,
                "preco_unitario": float(preco),
                "peso_aproximado": float(prod_data.get("peso_kg") or 0),
                "requer_pesagem": prod_data.get("requer_pesagem", False),
                "subtotal": float(preco) * quantidade
            }

            if carrinho.data:
                # Atualizar carrinho existente
                carrinho_atual = carrinho.data[0]
                items_atuais = carrinho_atual.get("items", [])

                # Adicionar novo item
                items_atuais.append(item)

                # Calcular novo total
                total = sum(i["subtotal"] for i in items_atuais)

                self.supabase.table("carrinhos").update({
                    "items": items_atuais,
                    "total_produtos": total,
                    "total_geral": total + carrinho_atual.get("frete_valor", 0)
                }).eq("id", carrinho_atual["id"]).execute()

            else:
                # Criar novo carrinho
                total = item["subtotal"]

                self.supabase.table("carrinhos").insert({
                    "telefone": telefone,
                    "items": [item],
                    "total_produtos": total,
                    "total_geral": total,
                    "ativo": True
                }).execute()

            # 3. Formatar resposta
            resposta = f"✅ **{prod_data['nome']}** adicionado ao carrinho!\n"
            resposta += f"   Quantidade: {quantidade}\n"
            resposta += f"   Valor: R$ {float(preco) * quantidade:.2f}\n"

            if prod_data.get("requer_pesagem"):
                resposta += f"\n⚖️ *Peso aproximado. Valor final ajustado após pesagem.*"

            return resposta

        except Exception as e:
            logger.error(f"❌ Erro ao adicionar ao carrinho: {e}")
            return f"❌ Não consegui adicionar. Tenta de novo?"

    # ==================== 3. Ver Carrinho ====================

    def ver_carrinho(self, telefone: str) -> str:
        """
        Mostra carrinho atual do cliente.

        Args:
            telefone: Telefone do cliente

        Returns:
            String formatada com items do carrinho
        """
        try:
            logger.info(f"👀 Visualizando carrinho: {telefone}")

            # Buscar carrinho
            carrinho = self.supabase.table("carrinhos")\
                .select("*")\
                .eq("telefone", telefone)\
                .eq("ativo", True)\
                .execute()

            if not carrinho.data:
                return "🛒 Seu carrinho está vazio."

            cart = carrinho.data[0]
            items = cart.get("items", [])

            if not items:
                return "🛒 Seu carrinho está vazio."

            # Formatar resposta
            resposta = "🛒 **Seu Carrinho:**\n\n"

            for i, item in enumerate(items, 1):
                resposta += f"{i}. **{item['nome']}**\n"
                resposta += f"   Quantidade: {item['quantidade']}\n"
                resposta += f"   Preço unitário: R$ {float(item['preco_unitario']):.2f}\n"
                resposta += f"   Subtotal: R$ {float(item['subtotal']):.2f}\n"

                if item.get('requer_pesagem'):
                    resposta += f"   ⚖️ *Peso aproximado*\n"

                resposta += "\n"

            resposta += "━━━━━━━━━━━━━━━━\n"
            resposta += f"💰 **Total Produtos:** R$ {float(cart['total_produtos']):.2f}\n"

            if cart.get('frete_valor'):
                resposta += f"🚚 **Frete:** R$ {float(cart['frete_valor']):.2f}\n"
                resposta += f"💵 **Total Geral:** R$ {float(cart['total_geral']):.2f}\n"

            return resposta

        except Exception as e:
            logger.error(f"❌ Erro ao ver carrinho: {e}")
            return "❌ Não consegui ver o carrinho. Tenta de novo?"

    # ==================== 4. Calcular Frete ====================

    def calcular_frete(
        self,
        telefone: str,
        endereco: str
    ) -> str:
        """
        Calcula frete para o pedido.

        IMPORTANTE: Sempre confirme o endereço com o cliente antes!

        Args:
            telefone: Telefone do cliente
            endereco: Endereço completo

        Returns:
            String com opções de frete
        """
        try:
            logger.info(f"🚚 Calculando frete para: {endereco}")

            # 1. Buscar carrinho
            carrinho = self.supabase.table("carrinhos")\
                .select("*")\
                .eq("telefone", telefone)\
                .eq("ativo", True)\
                .execute()

            if not carrinho.data or not carrinho.data[0].get("items"):
                return "❌ Carrinho vazio. Adicione produtos primeiro."

            cart = carrinho.data[0]
            total_pedido = cart["total_produtos"]

            # 2. Calcular peso total
            peso_total = sum(
                item.get("peso_aproximado", 0) * item.get("quantidade", 1)
                for item in cart["items"]
            )

            # 3. Simular cálculo de frete (integrar com API real depois)
            # TODO: Integrar Lalamove e Correios APIs

            # Por enquanto, valores simulados baseados em peso/valor
            opcoes = []

            # Lalamove (região BH)
            if "belo horizonte" in endereco.lower() or "bh" in endereco.lower():
                valor_lalamove = 12.50 if peso_total < 5 else 18.00
                opcoes.append({
                    "tipo": "lalamove",
                    "nome": "Lalamove (Motoboy)",
                    "valor": valor_lalamove,
                    "prazo": "45-60 minutos"
                })

            # Correios PAC
            valor_pac = max(18.00, peso_total * 3.5)
            opcoes.append({
                "tipo": "correios_pac",
                "nome": "Correios PAC",
                "valor": valor_pac,
                "prazo": "3-5 dias úteis"
            })

            # Correios SEDEX
            valor_sedex = max(25.00, peso_total * 5)
            opcoes.append({
                "tipo": "correios_sedex",
                "nome": "Correios SEDEX",
                "valor": valor_sedex,
                "prazo": "1-2 dias úteis"
            })

            # 4. Formatar resposta
            resposta = "📦 **Opções de Entrega:**\n\n"

            for i, opcao in enumerate(opcoes, 1):
                emoji = "🏍️" if "lala" in opcao["tipo"] else "📫"
                resposta += f"{emoji} **{opcao['nome']}**\n"
                resposta += f"   Valor: R$ {opcao['valor']:.2f}\n"
                resposta += f"   Prazo: {opcao['prazo']}\n\n"

            resposta += "Qual você prefere?"

            # 5. Salvar opções no carrinho (metadata)
            self.supabase.table("carrinhos").update({
                "metadata": {"opcoes_frete": opcoes}
            }).eq("id", cart["id"]).execute()

            return resposta

        except Exception as e:
            logger.error(f"❌ Erro ao calcular frete: {e}")
            return "❌ Não consegui calcular o frete. Pode conferir o endereço?"

    # ==================== 5. Confirmar Frete ====================

    def confirmar_frete(
        self,
        telefone: str,
        tipo_frete: str,
        valor_frete: float,
        prazo: str
    ) -> str:
        """
        Confirma escolha de frete e atualiza carrinho.

        Args:
            telefone: Telefone do cliente
            tipo_frete: Tipo escolhido (ex: "lalamove")
            valor_frete: Valor do frete
            prazo: Prazo de entrega

        Returns:
            String de confirmação
        """
        try:
            # Atualizar carrinho com frete
            carrinho = self.supabase.table("carrinhos")\
                .select("*")\
                .eq("telefone", telefone)\
                .eq("ativo", True)\
                .execute()

            if not carrinho.data:
                return "❌ Carrinho não encontrado."

            cart = carrinho.data[0]
            total_produtos = cart["total_produtos"]
            total_geral = total_produtos + valor_frete

            self.supabase.table("carrinhos").update({
                "frete_tipo": tipo_frete,
                "frete_valor": valor_frete,
                "total_geral": total_geral,
                "metadata": {
                    **cart.get("metadata", {}),
                    "frete_prazo": prazo
                }
            }).eq("id", cart["id"]).execute()

            resposta = f"✅ **Frete confirmado!**\n\n"
            resposta += f"🚚 {tipo_frete.replace('_', ' ').title()}\n"
            resposta += f"💰 R$ {valor_frete:.2f}\n"
            resposta += f"⏰ {prazo}\n\n"
            resposta += f"💵 **Total do Pedido:** R$ {total_geral:.2f}"

            return resposta

        except Exception as e:
            logger.error(f"❌ Erro ao confirmar frete: {e}")
            return "❌ Erro ao confirmar frete."

    # ==================== 6. Finalizar Pedido ====================

    async def finalizar_pedido(
        self,
        telefone: str,
        metodo_pagamento: str
    ) -> str:
        """
        Finaliza pedido e cria no Tiny.

        Fluxo:
        1. Valida carrinho
        2. Cria pedido no Supabase
        3. Envia para Tiny
        4. Gera pagamento (PIX/Cartão)
        5. Limpa carrinho

        Args:
            telefone: Telefone do cliente
            metodo_pagamento: 'pix' ou 'cartao'

        Returns:
            String com número do pedido e dados de pagamento
        """
        try:
            logger.info(f"🎯 Finalizando pedido: {telefone}")

            # 1. Buscar carrinho
            carrinho = self.supabase.table("carrinhos")\
                .select("*")\
                .eq("telefone", telefone)\
                .eq("ativo", True)\
                .execute()

            if not carrinho.data or not carrinho.data[0].get("items"):
                return "❌ Carrinho vazio. Adicione produtos primeiro."

            cart = carrinho.data[0]

            if not cart.get("frete_valor"):
                return "❌ Calcule o frete antes de finalizar."

            # 2. Buscar/criar cliente
            cliente = self.supabase.table("clientes")\
                .select("*")\
                .eq("telefone", telefone)\
                .execute()

            if not cliente.data:
                return "❌ Preciso de mais informações. Qual seu nome completo?"

            cliente_data = cliente.data[0]

            # 3. Gerar número do pedido
            numero_pedido = self.supabase.rpc(
                "generate_order_number",
                {"canal_origem": "whatsapp"}
            ).execute()

            # 4. Criar pedido no Supabase
            pedido_data = {
                "numero_pedido": numero_pedido.data,
                "canal": "whatsapp",
                "cliente_id": cliente_data["id"],
                "telefone": telefone,
                "cliente_nome": cliente_data.get("nome", "Cliente"),
                "cliente_cpf": cliente_data.get("cpf"),
                "cliente_email": cliente_data.get("email"),
                "endereco": cliente_data.get("endereco", {}),
                "items": cart["items"],
                "total_produtos": cart["total_produtos"],
                "frete_valor": cart["frete_valor"],
                "frete_tipo": cart["frete_tipo"],
                "total": cart["total_geral"],
                "status": "aguardando_pagamento",
                "pagamento_tipo": metodo_pagamento,
                "observacoes": cart.get("metadata", {}).get("observacoes"),
            }

            pedido_criado = self.supabase.table("pedidos")\
                .insert(pedido_data)\
                .execute()

            pedido_id = pedido_criado.data[0]["id"]

            # 5. Enviar para Tiny (assíncrono)
            try:
                await self.sync_service.create_order_in_tiny(pedido_id)
            except Exception as e:
                logger.error(f"⚠️ Erro ao enviar para Tiny: {e}")
                # Não bloqueia finalização - sync acontece depois

            # 6. Gerar pagamento
            # TODO: Integrar Pagar.me aqui
            if metodo_pagamento == "pix":
                pagamento_info = f"💳 PIX QR Code gerado!\n"
                pagamento_info += f"Pedido: #{numero_pedido.data}\n"
                pagamento_info += f"Total: R$ {cart['total_geral']:.2f}\n\n"
                pagamento_info += f"[QR Code será enviado separadamente]"
            else:
                pagamento_info = f"💳 Link de pagamento:\n"
                pagamento_info += f"[Link será gerado...]\n"
                pagamento_info += f"Total: R$ {cart['total_geral']:.2f}"

            # 7. Limpar carrinho
            self.supabase.table("carrinhos").update({
                "ativo": False
            }).eq("id", cart["id"]).execute()

            resposta = f"✅ **Pedido Criado!**\n\n"
            resposta += f"📝 Número: #{numero_pedido.data}\n"
            resposta += f"💰 Total: R$ {cart['total_geral']:.2f}\n\n"
            resposta += pagamento_info

            return resposta

        except Exception as e:
            logger.error(f"❌ Erro ao finalizar pedido: {e}")
            return f"❌ Erro ao finalizar. Tenta de novo?"

    # ==================== 7. Buscar Pedido ====================

    async def buscar_pedido(
        self,
        telefone: Optional[str] = None,
        numero_pedido: Optional[str] = None,
        cpf: Optional[str] = None
    ) -> str:
        """
        Busca pedidos do cliente.

        Busca no SUPABASE (rápido!) não no Tiny.

        Args:
            telefone: Telefone do cliente
            numero_pedido: Número do pedido
            cpf: CPF do cliente

        Returns:
            String formatada com pedidos encontrados
        """
        try:
            logger.info(f"🔍 Buscando pedido: {telefone or numero_pedido or cpf}")

            # Usar serviço de sync para buscar
            pedidos = await self.sync_service.buscar_pedido_cliente(
                telefone=telefone,
                numero_pedido=numero_pedido,
                cpf=cpf
            )

            if not pedidos:
                return "❌ Não encontrei nenhum pedido com essas informações."

            # Formatar resposta
            resposta = f"📦 **Encontrei {len(pedidos)} pedido(s):**\n\n"

            for pedido in pedidos:
                status_emoji = {
                    "aguardando_pagamento": "⏳",
                    "pago": "✅",
                    "confirmado": "✅",
                    "preparando": "📦",
                    "enviado": "🚚",
                    "entregue": "🎉",
                    "cancelado": "❌"
                }

                emoji = status_emoji.get(pedido["status"], "📋")

                resposta += f"{emoji} **Pedido #{pedido['numero_pedido']}**\n"
                resposta += f"   Status: {pedido['status'].upper()}\n"
                resposta += f"   Total: R$ {float(pedido['total']):.2f}\n"
                resposta += f"   Data: {pedido['criado_em'][:10]}\n"

                if pedido.get("rastreio_codigo"):
                    resposta += f"   📫 Rastreio: {pedido['rastreio_codigo']}\n"

                resposta += "\n"

            return resposta

        except Exception as e:
            logger.error(f"❌ Erro ao buscar pedido: {e}")
            return "❌ Erro ao buscar pedido. Tenta de novo?"


# ==================== Exportar para LangChain ====================

def create_agent_tools(supabase: Client, sync_service: SyncService) -> List:
    """
    Cria lista de tools para o LangChain Agent

    Returns:
        Lista de ferramentas formatadas para LangChain
    """
    tools_instance = AgentTools(supabase, sync_service)

    # Lista de tools disponíveis
    # TODO: Converter para formato LangChain Tool
    tools = [
        tools_instance.buscar_produtos,
        tools_instance.adicionar_carrinho,
        tools_instance.ver_carrinho,
        tools_instance.calcular_frete,
        tools_instance.confirmar_frete,
        tools_instance.finalizar_pedido,
        tools_instance.buscar_pedido
    ]

    return tools
