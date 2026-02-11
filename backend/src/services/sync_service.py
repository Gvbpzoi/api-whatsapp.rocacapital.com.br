"""
Serviço de Sincronização Tiny ↔ Supabase

Responsável por:
- Sincronizar produtos (Tiny/Site → Supabase)
- Criar pedidos (Supabase → Tiny)
- Atualizar status (Tiny → Supabase)
- Manter cache atualizado

Estratégia:
- Supabase = cache rápido (busca instantânea)
- Tiny = fonte da verdade (status oficial)
- Sync periódico a cada 5-10min
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
from supabase import create_client, Client

from .tiny_client import TinyAPIClient
from ..models.tiny_models import TinyOrderCreate


class SyncService:
    """
    Orquestrador de sincronização entre Tiny e Supabase
    """

    def __init__(
        self,
        tiny_client: TinyAPIClient,
        supabase_url: str,
        supabase_key: str
    ):
        self.tiny = tiny_client
        self.supabase: Client = create_client(supabase_url, supabase_key)

    # ==================== Sincronização de Produtos ====================

    async def sync_products_from_tiny(
        self,
        full_sync: bool = False
    ) -> Dict[str, Any]:
        """
        Sincroniza produtos do Tiny → Supabase

        Args:
            full_sync: Se True, sincroniza todos. Se False, apenas alterados

        Returns:
            {
                "success": 15,
                "errors": 2,
                "total": 17,
                "errors_list": [...]
            }
        """
        logger.info("🔄 Iniciando sincronização de produtos do Tiny...")

        success_count = 0
        error_count = 0
        errors_list = []

        try:
            # 1. Buscar produtos do Tiny
            # Se full_sync, pega todos. Senão, apenas os alterados recentemente
            produtos_tiny = []
            offset = 0
            limit = 100

            while True:
                batch = await self.tiny.list_products(
                    situacao="A",  # Apenas ativos
                    limit=limit,
                    offset=offset
                )

                if not batch:
                    break

                produtos_tiny.extend(batch)
                offset += limit

                # Se não é full sync, para após primeira página
                if not full_sync:
                    break

            logger.info(f"📦 Encontrados {len(produtos_tiny)} produtos no Tiny")

            # 2. Para cada produto, buscar detalhes e sincronizar
            for produto in produtos_tiny:
                try:
                    # Buscar detalhes completos (inclui estoque)
                    detalhes = await self.tiny.get_product(produto.id)

                    # Mapear para formato Supabase
                    produto_data = {
                        "tiny_id": detalhes.id,
                        "sku": detalhes.codigo,
                        "nome": detalhes.nome,
                        "descricao": detalhes.descricao_complementar,
                        "preco": float(detalhes.preco),
                        "preco_custo": float(detalhes.preco_custo) if detalhes.preco_custo else None,
                        "estoque_atual": float(detalhes.estoque_atual) if detalhes.estoque_atual else 0,
                        "estoque_minimo": float(detalhes.estoque_minimo) if detalhes.estoque_minimo else 0,
                        "peso_kg": float(detalhes.peso_liquido) if detalhes.peso_liquido else None,
                        "categoria_id": detalhes.categoria_id,
                        "ncm": detalhes.ncm,
                        "gtin": detalhes.gtin,
                        "unidade": detalhes.unidade,
                        "ativo": detalhes.situacao == "A",
                        "disponivel_whatsapp": True,  # Pode filtrar aqui
                        "fonte": "tiny",
                        "ultima_sync_tiny": datetime.now().isoformat()
                    }

                    # 3. Upsert no Supabase
                    result = self.supabase.table("produtos")\
                        .upsert(produto_data, on_conflict="tiny_id")\
                        .execute()

                    success_count += 1
                    logger.debug(f"✅ Produto {detalhes.codigo} sincronizado")

                except Exception as e:
                    error_count += 1
                    error_msg = f"Erro ao sincronizar produto {produto.codigo}: {str(e)}"
                    errors_list.append(error_msg)
                    logger.error(f"❌ {error_msg}")

                    # Registrar erro no log
                    await self._log_sync(
                        operacao="sync_produto",
                        entidade="produto",
                        tiny_id=produto.id,
                        status="error",
                        erro=str(e)
                    )

            # 4. Registrar sync bem-sucedido
            await self._log_sync(
                operacao="sync_produtos_batch",
                entidade="produto",
                status="success",
                mensagem=f"Sincronizados {success_count} de {len(produtos_tiny)} produtos"
            )

            logger.info(f"✅ Sincronização concluída: {success_count} sucesso, {error_count} erros")

            return {
                "success": success_count,
                "errors": error_count,
                "total": len(produtos_tiny),
                "errors_list": errors_list
            }

        except Exception as e:
            logger.error(f"❌ Erro fatal na sincronização de produtos: {e}")
            await self._log_sync(
                operacao="sync_produtos_batch",
                entidade="produto",
                status="error",
                erro=str(e)
            )
            raise

    # ==================== Criação de Pedidos ====================

    async def create_order_in_tiny(
        self,
        pedido_id: str
    ) -> Dict[str, Any]:
        """
        Cria pedido no Tiny a partir de um pedido no Supabase

        Fluxo:
        1. Busca pedido no Supabase
        2. Verifica/cria cliente no Tiny
        3. Formata dados para Tiny
        4. Cria pedido no Tiny
        5. Atualiza Supabase com tiny_pedido_id

        Args:
            pedido_id: UUID do pedido no Supabase

        Returns:
            {
                "tiny_pedido_id": 123456,
                "numero": "12345",
                "success": True
            }
        """
        logger.info(f"📤 Criando pedido {pedido_id} no Tiny...")

        try:
            # 1. Buscar pedido no Supabase
            pedido = self.supabase.table("pedidos")\
                .select("*")\
                .eq("id", pedido_id)\
                .single()\
                .execute()

            if not pedido.data:
                raise ValueError(f"Pedido {pedido_id} não encontrado")

            pedido_data = pedido.data

            # 2. Verificar se cliente tem tiny_id
            cliente = self.supabase.table("clientes")\
                .select("*")\
                .eq("id", pedido_data["cliente_id"])\
                .single()\
                .execute()

            cliente_data = cliente.data
            tiny_cliente_id = cliente_data.get("tiny_id")

            # Se não tem, criar cliente no Tiny
            if not tiny_cliente_id:
                logger.info("👤 Cliente não existe no Tiny, criando...")
                tiny_cliente_id = await self._create_customer_in_tiny(cliente_data)

            # 3. Formatar items para Tiny
            items_tiny = []
            for item in pedido_data["items"]:
                items_tiny.append({
                    "produto": {"id": item["tiny_produto_id"]},
                    "quantidade": item["quantidade"],
                    "valorUnitario": float(item["preco_unitario"])
                })

            # 4. Formatar endereço
            endereco = pedido_data["endereco"]
            endereco_tiny = {
                "endereco": endereco["rua"],
                "enderecoNro": endereco["numero"],
                "complemento": endereco.get("complemento"),
                "bairro": endereco["bairro"],
                "municipio": endereco["cidade"],
                "cep": endereco["cep"],
                "uf": endereco["uf"],
                "fone": pedido_data["telefone"],
                "nomeDestinatario": pedido_data["cliente_nome"],
                "cpfCnpj": pedido_data.get("cliente_cpf", ""),
                "tipoPessoa": "F" if len(pedido_data.get("cliente_cpf", "")) == 11 else "J"
            }

            # 5. Formatar pagamento
            forma_pagamento_map = {
                "pix": 1,
                "cartao": 2,
                "dinheiro": 3,
                "boleto": 4
            }

            pagamento_tiny = {
                "formaPagamento": {"id": forma_pagamento_map.get(pedido_data["pagamento_tipo"], 1)},
                "parcelas": [
                    {
                        "valor": float(pedido_data["total"]),
                        "dias": 0
                    }
                ]
            }

            # 6. Criar objeto TinyOrderCreate
            order_tiny = TinyOrderCreate(
                data=datetime.now().date(),
                observacoes=pedido_data.get("observacoes"),
                observacoesInternas=f"Pedido WhatsApp - Ref: {pedido_data['numero_pedido']}",
                situacao=0,  # Aberta
                valorDesconto=float(pedido_data.get("desconto", 0)),
                valorFrete=float(pedido_data.get("frete_valor", 0)),
                idContato=tiny_cliente_id,
                enderecoEntrega=endereco_tiny,
                ecommerce={
                    "numeroPedidoEcommerce": pedido_data["numero_pedido"]
                },
                pagamento=pagamento_tiny,
                itens=items_tiny
            )

            # 7. Enviar para Tiny
            response = await self.tiny.create_order(order_tiny)

            tiny_pedido_id = response["id"]
            tiny_numero = response.get("numero", "")

            # 8. Atualizar Supabase
            self.supabase.table("pedidos").update({
                "tiny_pedido_id": tiny_pedido_id,
                "tiny_sincronizado": True,
                "tiny_sincronizado_em": datetime.now().isoformat()
            }).eq("id", pedido_id).execute()

            # 9. Registrar log
            await self._log_sync(
                operacao="create_pedido",
                entidade="pedido",
                entidade_id=pedido_id,
                tiny_id=tiny_pedido_id,
                status="success",
                mensagem=f"Pedido criado no Tiny: #{tiny_numero}"
            )

            logger.info(f"✅ Pedido criado no Tiny: ID {tiny_pedido_id}, Número {tiny_numero}")

            return {
                "tiny_pedido_id": tiny_pedido_id,
                "numero": tiny_numero,
                "success": True
            }

        except Exception as e:
            logger.error(f"❌ Erro ao criar pedido no Tiny: {e}")

            # Registrar erro
            await self._log_sync(
                operacao="create_pedido",
                entidade="pedido",
                entidade_id=pedido_id,
                status="error",
                erro=str(e)
            )

            raise

    async def _create_customer_in_tiny(self, cliente_data: Dict) -> int:
        """Cria cliente no Tiny e retorna o ID"""
        from ..models.tiny_models import TinyContactCreate, TinyContactAddress

        endereco = cliente_data.get("endereco", {})

        contact = TinyContactCreate(
            nome=cliente_data["nome"],
            tipoPessoa="F" if len(cliente_data.get("cpf", "")) == 11 else "J",
            cpfCnpj=cliente_data.get("cpf", ""),
            email=cliente_data.get("email"),
            celular=cliente_data["telefone"],
            endereco=TinyContactAddress(
                endereco=endereco.get("rua", ""),
                numero=endereco.get("numero", "S/N"),
                bairro=endereco.get("bairro", ""),
                cep=endereco.get("cep", ""),
                municipio=endereco.get("cidade", ""),
                uf=endereco.get("uf", "MG")
            )
        )

        response = await self.tiny.create_contact(contact)
        tiny_cliente_id = response["id"]

        # Atualizar Supabase
        self.supabase.table("clientes").update({
            "tiny_id": tiny_cliente_id
        }).eq("id", cliente_data["id"]).execute()

        logger.info(f"✅ Cliente criado no Tiny: ID {tiny_cliente_id}")

        return tiny_cliente_id

    # ==================== Sincronização de Status ====================

    async def sync_orders_status_from_tiny(
        self,
        last_minutes: int = 15
    ) -> Dict[str, int]:
        """
        Sincroniza status de pedidos do Tiny → Supabase

        Busca pedidos atualizados nos últimos X minutos
        e atualiza status no Supabase

        Args:
            last_minutes: Sincronizar pedidos dos últimos X minutos

        Returns:
            {
                "updated": 5,
                "errors": 1
            }
        """
        logger.info(f"🔄 Sincronizando status de pedidos (últimos {last_minutes}min)...")

        updated_count = 0
        error_count = 0

        try:
            # 1. Calcular data inicial
            data_inicial = (datetime.now() - timedelta(minutes=last_minutes))\
                .strftime("%Y-%m-%d")

            # 2. Buscar pedidos do Tiny
            pedidos_tiny = await self.tiny.list_orders(
                data_inicial=data_inicial,
                limit=100
            )

            # 3. Para cada pedido, atualizar status no Supabase
            for pedido_tiny in pedidos_tiny:
                try:
                    tiny_id = pedido_tiny.get("id")

                    # Buscar pedido no Supabase
                    pedido_local = self.supabase.table("pedidos")\
                        .select("*")\
                        .eq("tiny_pedido_id", tiny_id)\
                        .execute()

                    if not pedido_local.data:
                        # Pedido não existe localmente (veio do site)
                        # TODO: Criar pedido no Supabase
                        continue

                    # Mapear situação Tiny → status local
                    status_map = {
                        0: "confirmado",      # Aberta
                        1: "confirmado",      # Faturada
                        2: "cancelado",       # Cancelada
                        3: "confirmado",      # Aprovada
                        4: "preparando",      # Preparando Envio
                        5: "enviado",         # Enviada
                        6: "entregue",        # Entregue
                        7: "pronto_envio",    # Pronto Envio
                    }

                    novo_status = status_map.get(pedido_tiny.get("situacao"), "confirmado")

                    # Atualizar
                    self.supabase.table("pedidos").update({
                        "status": novo_status,
                        "tiny_situacao": pedido_tiny.get("situacao"),
                        "rastreio_codigo": pedido_tiny.get("codigoRastreamento"),
                        "rastreio_url": pedido_tiny.get("urlRastreamento"),
                        "nf_numero": pedido_tiny.get("numeroNota"),
                    }).eq("tiny_pedido_id", tiny_id).execute()

                    updated_count += 1

                except Exception as e:
                    error_count += 1
                    logger.error(f"❌ Erro ao atualizar pedido {pedido_tiny.get('id')}: {e}")

            logger.info(f"✅ Status sincronizado: {updated_count} atualizados, {error_count} erros")

            return {
                "updated": updated_count,
                "errors": error_count
            }

        except Exception as e:
            logger.error(f"❌ Erro na sincronização de status: {e}")
            raise

    # ==================== Busca de Pedido ====================

    async def buscar_pedido_cliente(
        self,
        telefone: Optional[str] = None,
        numero_pedido: Optional[str] = None,
        cpf: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Busca pedidos do cliente no Supabase (rápido!)

        Args:
            telefone: Telefone do cliente
            numero_pedido: Número do pedido
            cpf: CPF do cliente

        Returns:
            Lista de pedidos encontrados
        """
        query = self.supabase.table("pedidos").select("*")

        if telefone:
            query = query.eq("telefone", telefone)
        elif numero_pedido:
            query = query.or_(f"numero_pedido.eq.{numero_pedido},tiny_pedido_id.eq.{numero_pedido}")
        elif cpf:
            query = query.eq("cliente_cpf", cpf)
        else:
            raise ValueError("Forneça telefone, numero_pedido ou CPF")

        result = query.order("criado_em", desc=True).limit(5).execute()

        return result.data

    # ==================== Helpers ====================

    async def _log_sync(
        self,
        operacao: str,
        entidade: str,
        entidade_id: Optional[str] = None,
        tiny_id: Optional[int] = None,
        status: str = "success",
        mensagem: Optional[str] = None,
        erro: Optional[str] = None
    ):
        """Registra log de sincronização no Supabase"""
        log_data = {
            "operacao": operacao,
            "entidade": entidade,
            "entidade_id": entidade_id,
            "tiny_id": tiny_id,
            "status": status,
            "mensagem": mensagem,
            "erro": erro,
            "criado_em": datetime.now().isoformat()
        }

        self.supabase.table("sync_log").insert(log_data).execute()
