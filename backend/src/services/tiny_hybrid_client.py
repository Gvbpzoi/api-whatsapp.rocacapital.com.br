"""
Cliente Híbrido Tiny ERP - V3 com fallback para V2

IMPORTANTE: Algumas funções da V3 não funcionam corretamente (ex: telefone).
Este cliente tenta V3 primeiro e automaticamente usa V2 como fallback.

Documentação V2: https://api.tiny.com.br/api2/
Documentação V3: https://erp.tiny.com.br/public-api/v3/
"""
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger
from enum import Enum

from .tiny_client import TinyAPIClient  # Cliente V3
from ..models.tiny_models import TinyOrderCreate, TinyContactCreate


class TinyAPIVersion(str, Enum):
    """Versão da API Tiny"""
    V2 = "v2"
    V3 = "v3"


class TinyHybridClient:
    """
    Cliente Híbrido que suporta V2 e V3

    Estratégia:
    - Tenta V3 primeiro (mais moderna, OAuth)
    - Se falhar, usa V2 (mais estável)
    - Registra qual versão funcionou para cada operação
    """

    def __init__(
        self,
        # V3 (OAuth)
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        # V2 (Token simples)
        v2_token: Optional[str] = None
    ):
        # Cliente V3
        if client_id and client_secret:
            self.v3_client = TinyAPIClient(
                client_id=client_id,
                client_secret=client_secret,
                access_token=access_token,
                refresh_token=refresh_token
            )
        else:
            self.v3_client = None
            logger.warning("⚠️ Cliente V3 não configurado (falta OAuth)")

        # Cliente V2
        self.v2_token = v2_token
        self.v2_base_url = "https://api.tiny.com.br/api2"
        self.v2_client = httpx.AsyncClient(timeout=30.0)

        # Rastreamento de qual versão funciona melhor
        self._version_stats: Dict[str, Dict[str, int]] = {}

    # ==================== API V2 Helpers ====================

    async def _v2_request(
        self,
        endpoint: str,
        method: str = "POST",
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Faz requisição na API V2

        V2 usa formato diferente:
        - URL: /api2/endpoint.php
        - Método: sempre POST
        - Formato: XML ou JSON
        - Auth: token no body
        """
        if not self.v2_token:
            raise ValueError("Token V2 não configurado")

        url = f"{self.v2_base_url}/{endpoint}.php"

        # V2 usa POST para tudo
        payload = {
            "token": self.v2_token,
            "formato": "JSON"
        }

        if data:
            payload.update(data)

        response = await self.v2_client.post(url, data=payload)
        response.raise_for_status()

        data = response.json()

        # V2 retorna {"retorno": {"status": "OK", ...}}
        if data.get("retorno", {}).get("status_processamento") == "3":
            # Erro
            raise Exception(f"Erro V2: {data['retorno'].get('erros')}")

        return data.get("retorno", {})

    # ==================== Produtos (Híbrido) ====================

    async def list_products(
        self,
        nome: Optional[str] = None,
        codigo: Optional[str] = None,
        situacao: str = "A",
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Lista produtos

        Tenta V3 → fallback V2
        """
        operation = "list_products"

        # Tentar V3 primeiro
        if self.v3_client:
            try:
                logger.debug(f"🔵 Tentando {operation} via V3...")
                result = await self.v3_client.list_products(
                    nome=nome,
                    codigo=codigo,
                    situacao=situacao,
                    limit=limit,
                    offset=offset
                )
                self._record_success(operation, TinyAPIVersion.V3)
                logger.info(f"✅ {operation} via V3 OK")
                return [p.dict() for p in result]

            except Exception as e:
                logger.warning(f"⚠️ V3 falhou para {operation}: {e}")
                logger.info(f"🔄 Tentando fallback para V2...")

        # Fallback V2
        try:
            logger.debug(f"🟡 Usando {operation} via V2...")

            # V2: produtos.pesquisa
            v2_data = {
                "pesquisa": nome or codigo or ""
            }

            result = await self._v2_request("produtos.pesquisa", data=v2_data)

            produtos = result.get("produtos", [])

            self._record_success(operation, TinyAPIVersion.V2)
            logger.info(f"✅ {operation} via V2 OK ({len(produtos)} produtos)")

            return produtos

        except Exception as e:
            self._record_failure(operation)
            logger.error(f"❌ {operation} falhou em V2 e V3: {e}")
            raise

    async def get_product(self, product_id: int) -> Dict[str, Any]:
        """
        Busca detalhes de um produto

        V3: GET /produtos/{id}
        V2: POST /produto.obter.php
        """
        operation = "get_product"

        # Tentar V3
        if self.v3_client:
            try:
                logger.debug(f"🔵 {operation} via V3...")
                result = await self.v3_client.get_product(product_id)
                self._record_success(operation, TinyAPIVersion.V3)
                return result.dict()
            except Exception as e:
                logger.warning(f"⚠️ V3 falhou: {e}, tentando V2...")

        # Fallback V2
        try:
            logger.debug(f"🟡 {operation} via V2...")

            result = await self._v2_request("produto.obter", data={
                "id": product_id
            })

            self._record_success(operation, TinyAPIVersion.V2)
            return result.get("produto", {})

        except Exception as e:
            self._record_failure(operation)
            raise

    # ==================== Pedidos (Híbrido) ====================

    async def create_order(self, order: TinyOrderCreate) -> Dict[str, Any]:
        """
        Cria pedido

        IMPORTANTE: V3 às vezes tem problema com telefone!
        Use V2 como fallback

        V3: POST /pedidos
        V2: POST /pedido.incluir.php
        """
        operation = "create_order"

        # Tentar V3
        if self.v3_client:
            try:
                logger.debug(f"🔵 Criando pedido via V3...")
                result = await self.v3_client.create_order(order)
                self._record_success(operation, TinyAPIVersion.V3)
                logger.info(f"✅ Pedido criado via V3: {result}")
                return result

            except Exception as e:
                logger.warning(f"⚠️ V3 falhou ao criar pedido: {e}")
                logger.info(f"🔄 Tentando V2 (telefone pode ter causado o erro)...")

        # Fallback V2
        try:
            logger.debug(f"🟡 Criando pedido via V2...")

            # Converter objeto V3 para formato V2
            v2_order = self._convert_order_v3_to_v2(order)

            result = await self._v2_request("pedido.incluir", data={
                "pedido": v2_order
            })

            self._record_success(operation, TinyAPIVersion.V2)
            logger.info(f"✅ Pedido criado via V2: {result}")

            return {
                "id": result.get("id"),
                "numero": result.get("numero")
            }

        except Exception as e:
            self._record_failure(operation)
            logger.error(f"❌ Erro ao criar pedido em V2 e V3: {e}")
            raise

    def _convert_order_v3_to_v2(self, order: TinyOrderCreate) -> Dict:
        """
        Converte pedido do formato V3 para V2

        V3 e V2 tem estruturas diferentes!
        """
        v2_order = {
            "data_pedido": order.data.strftime("%d/%m/%Y"),
            "data_prevista": order.data_prevista.strftime("%d/%m/%Y") if order.data_prevista else "",
            "observacoes": order.observacoes or "",
            "obs_internas": order.observacoes_internas or "",
            "codigo_cliente": order.id_contato,
            "valor_desconto": float(order.valor_desconto or 0),
            "valor_frete": float(order.valor_frete or 0),

            # Items
            "itens": [
                {
                    "item": {
                        "codigo_produto": item["produto"]["id"],
                        "quantidade": float(item["quantidade"]),
                        "valor_unitario": float(item["valorUnitario"])
                    }
                }
                for item in order.itens
            ]
        }

        # Endereço (V2 tem campos diferentes)
        if order.endereco_entrega:
            end = order.endereco_entrega
            v2_order["nome_destinatario"] = end.nome_destinatario
            v2_order["endereco_destinatario"] = end.endereco
            v2_order["numero_destinatario"] = end.endereco_nro
            v2_order["bairro_destinatario"] = end.bairro
            v2_order["cidade_destinatario"] = end.municipio
            v2_order["uf_destinatario"] = end.uf
            v2_order["cep_destinatario"] = end.cep
            v2_order["fone_destinatario"] = end.fone
            v2_order["cpf_cnpj_destinatario"] = end.cpf_cnpj

        return v2_order

    # ==================== Contatos/Clientes (Híbrido) ====================

    async def create_contact(self, contact: TinyContactCreate) -> Dict[str, Any]:
        """
        Cria cliente

        V3: POST /contatos
        V2: POST /cliente.incluir.php
        """
        operation = "create_contact"

        # Tentar V3
        if self.v3_client:
            try:
                logger.debug(f"🔵 Criando cliente via V3...")
                result = await self.v3_client.create_contact(contact)
                self._record_success(operation, TinyAPIVersion.V3)
                return result

            except Exception as e:
                logger.warning(f"⚠️ V3 falhou: {e}, tentando V2...")

        # Fallback V2
        try:
            logger.debug(f"🟡 Criando cliente via V2...")

            v2_contact = {
                "nome": contact.nome,
                "codigo": contact.codigo or "",
                "tipo_pessoa": contact.tipo_pessoa,
                "cpf_cnpj": contact.cpf_cnpj,
                "email": contact.email or "",
                "fone": contact.fone or "",
                "celular": contact.celular,
                "endereco": contact.endereco.endereco,
                "numero": contact.endereco.numero,
                "bairro": contact.endereco.bairro,
                "cep": contact.endereco.cep,
                "cidade": contact.endereco.municipio,
                "uf": contact.endereco.uf
            }

            result = await self._v2_request("cliente.incluir", data={
                "cliente": v2_contact
            })

            self._record_success(operation, TinyAPIVersion.V2)
            return {
                "id": result.get("id")
            }

        except Exception as e:
            self._record_failure(operation)
            raise

    async def list_orders(
        self,
        data_inicial: Optional[str] = None,
        data_final: Optional[str] = None,
        numero_pedido_ecommerce: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Lista pedidos

        V3: GET /pedidos
        V2: POST /pedidos.pesquisa.php
        """
        operation = "list_orders"

        # Tentar V3
        if self.v3_client:
            try:
                logger.debug(f"🔵 Listando pedidos via V3...")
                result = await self.v3_client.list_orders(
                    data_inicial=data_inicial,
                    data_final=data_final,
                    numero_pedido_ecommerce=numero_pedido_ecommerce,
                    limit=limit
                )
                self._record_success(operation, TinyAPIVersion.V3)
                return result

            except Exception as e:
                logger.warning(f"⚠️ V3 falhou: {e}, tentando V2...")

        # Fallback V2
        try:
            logger.debug(f"🟡 Listando pedidos via V2...")

            # V2 usa formato de data diferente: DD/MM/YYYY
            v2_data = {}
            if data_inicial:
                v2_data["dataInicial"] = datetime.strptime(data_inicial, "%Y-%m-%d").strftime("%d/%m/%Y")
            if data_final:
                v2_data["dataFinal"] = datetime.strptime(data_final, "%Y-%m-%d").strftime("%d/%m/%Y")
            if numero_pedido_ecommerce:
                v2_data["numeroPedidoEcommerce"] = numero_pedido_ecommerce

            result = await self._v2_request("pedidos.pesquisa", data=v2_data)

            pedidos = result.get("pedidos", [])

            self._record_success(operation, TinyAPIVersion.V2)
            return pedidos

        except Exception as e:
            self._record_failure(operation)
            raise

    # ==================== Estatísticas ====================

    def _record_success(self, operation: str, version: TinyAPIVersion):
        """Registra sucesso de uma operação"""
        if operation not in self._version_stats:
            self._version_stats[operation] = {"v2": 0, "v3": 0, "errors": 0}

        self._version_stats[operation][version.value] += 1

    def _record_failure(self, operation: str):
        """Registra falha de uma operação"""
        if operation not in self._version_stats:
            self._version_stats[operation] = {"v2": 0, "v3": 0, "errors": 0}

        self._version_stats[operation]["errors"] += 1

    def get_version_stats(self) -> Dict[str, Dict[str, int]]:
        """
        Retorna estatísticas de uso das versões

        Útil para saber quais operações funcionam melhor em V2 vs V3

        Returns:
            {
                "create_order": {"v2": 15, "v3": 2, "errors": 1},
                "list_products": {"v2": 5, "v3": 20, "errors": 0}
            }
        """
        return self._version_stats

    # ==================== Health Check ====================

    async def health_check(self) -> Dict[str, bool]:
        """Verifica saúde de ambas as versões"""
        health = {
            "v3": False,
            "v2": False
        }

        # Testar V3
        if self.v3_client:
            try:
                await self.v3_client.health_check()
                health["v3"] = True
            except:
                pass

        # Testar V2
        if self.v2_token:
            try:
                await self._v2_request("info", data={})
                health["v2"] = True
            except:
                pass

        return health

    async def close(self):
        """Fecha conexões"""
        if self.v3_client:
            await self.v3_client.close()
        await self.v2_client.aclose()
