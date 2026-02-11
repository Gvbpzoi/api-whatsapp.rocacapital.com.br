"""
Cliente da API Tiny ERP V3 com OAuth 2.0

Documentação: https://erp.tiny.com.br/public-api/v3/swagger/
"""
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger

from ..models.tiny_models import (
    TinyProduct, TinyOrder, TinyContact,
    TinyOrderCreate, TinyContactCreate
)


class TinyAPIClient:
    """
    Cliente para API Tiny ERP V3

    Features:
    - OAuth 2.0 authentication
    - Rate limiting handling
    - Retry logic
    - Response parsing
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token

        self.base_url = "https://erp.tiny.com.br/public-api/v3"
        self.oauth_url = "https://erp.tiny.com.br/auth"

        self.token_expires_at: Optional[datetime] = None
        self._client = httpx.AsyncClient(timeout=30.0)

    # ==================== Auth ====================

    async def get_auth_url(self, redirect_uri: str, state: str) -> str:
        """
        Gera URL para autorização OAuth

        Args:
            redirect_uri: URL de callback
            state: String aleatória para segurança

        Returns:
            URL para redirecionar usuário
        """
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": state
        }

        url = f"{self.oauth_url}/authorize?"
        url += "&".join([f"{k}={v}" for k, v in params.items()])

        return url

    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str
    ) -> Dict[str, Any]:
        """
        Troca código de autorização por access_token

        Args:
            code: Código retornado na URL de callback
            redirect_uri: Mesma URL usada na autorização

        Returns:
            {
                "access_token": "...",
                "refresh_token": "...",
                "expires_in": 3600,
                "token_type": "Bearer"
            }
        """
        response = await self._client.post(
            f"{self.oauth_url}/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
        )

        response.raise_for_status()
        data = response.json()

        # Salvar tokens
        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token")
        self.token_expires_at = datetime.now() + timedelta(seconds=data["expires_in"])

        logger.info("✅ Token obtido com sucesso")

        return data

    async def refresh_access_token(self) -> Dict[str, Any]:
        """Renova access_token usando refresh_token"""
        if not self.refresh_token:
            raise ValueError("Refresh token não disponível")

        response = await self._client.post(
            f"{self.oauth_url}/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
        )

        response.raise_for_status()
        data = response.json()

        # Atualizar tokens
        self.access_token = data["access_token"]
        if "refresh_token" in data:
            self.refresh_token = data["refresh_token"]
        self.token_expires_at = datetime.now() + timedelta(seconds=data["expires_in"])

        logger.info("✅ Token renovado")

        return data

    async def ensure_valid_token(self):
        """Garante que o token está válido, renovando se necessário"""
        if not self.access_token:
            raise ValueError("Access token não configurado")

        # Renovar se expirar em menos de 5 minutos
        if self.token_expires_at:
            expires_soon = datetime.now() + timedelta(minutes=5)
            if expires_soon >= self.token_expires_at:
                await self.refresh_access_token()

    # ==================== HTTP Helpers ====================

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Faz requisição HTTP com autenticação e retry"""
        await self.ensure_valid_token()

        url = f"{self.base_url}{endpoint}"

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        headers["Content-Type"] = "application/json"

        try:
            response = await self._client.request(
                method=method,
                url=url,
                headers=headers,
                **kwargs
            )

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                # Token inválido, tentar renovar
                await self.refresh_access_token()
                return await self._request(method, endpoint, **kwargs)
            raise

    # ==================== Produtos ====================

    async def list_products(
        self,
        nome: Optional[str] = None,
        codigo: Optional[str] = None,
        situacao: str = "A",  # A=Ativo, I=Inativo
        limit: int = 100,
        offset: int = 0
    ) -> List[TinyProduct]:
        """
        Lista produtos

        Args:
            nome: Filtrar por nome
            codigo: Filtrar por código/SKU
            situacao: A (Ativo), I (Inativo), E (Excluído)
            limit: Máximo de resultados (max: 100)
            offset: Posição inicial

        Returns:
            Lista de produtos
        """
        params = {
            "situacao": situacao,
            "limit": limit,
            "offset": offset
        }

        if nome:
            params["nome"] = nome
        if codigo:
            params["codigo"] = codigo

        data = await self._request("GET", "/produtos", params=params)

        # Parse response
        products = []
        for item in data.get("data", []):
            products.append(TinyProduct(**item))

        logger.info(f"📦 Listados {len(products)} produtos do Tiny")

        return products

    async def get_product(self, product_id: int) -> TinyProduct:
        """
        Busca detalhes completos de um produto (inclui estoque)

        Args:
            product_id: ID do produto no Tiny

        Returns:
            Produto com todos os dados
        """
        data = await self._request("GET", f"/produtos/{product_id}")

        return TinyProduct(**data)

    async def get_product_stock(self, product_id: int) -> Dict[str, Any]:
        """
        Busca estoque de um produto

        Returns:
            {
                "saldo": 10.0,
                "reservado": 2.0,
                "disponivel": 8.0,
                "depositos": [...]
            }
        """
        data = await self._request("GET", f"/estoque/{product_id}")

        return data

    # ==================== Pedidos ====================

    async def list_orders(
        self,
        data_inicial: Optional[str] = None,
        data_final: Optional[str] = None,
        situacao: Optional[int] = None,
        numero_pedido_ecommerce: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Lista pedidos

        Args:
            data_inicial: Data inicial (YYYY-MM-DD)
            data_final: Data final (YYYY-MM-DD)
            situacao: 0=Aberta, 1=Faturada, 2=Cancelada, etc
            numero_pedido_ecommerce: Número do pedido externo
            limit: Máximo de resultados
            offset: Posição inicial

        Returns:
            Lista de pedidos
        """
        params = {
            "limit": limit,
            "offset": offset
        }

        if data_inicial:
            params["dataInicial"] = data_inicial
        if data_final:
            params["dataFinal"] = data_final
        if situacao is not None:
            params["situacao"] = situacao
        if numero_pedido_ecommerce:
            params["numeroPedidoEcommerce"] = numero_pedido_ecommerce

        data = await self._request("GET", "/pedidos", params=params)

        logger.info(f"📋 Listados {len(data.get('data', []))} pedidos")

        return data.get("data", [])

    async def create_order(self, order: TinyOrderCreate) -> Dict[str, Any]:
        """
        Cria um novo pedido no Tiny

        Args:
            order: Dados do pedido

        Returns:
            {
                "id": 123456,
                "numero": "12345",
                "mensagem": "Pedido incluído com sucesso"
            }
        """
        data = await self._request(
            "POST",
            "/pedidos",
            json=order.dict(exclude_none=True)
        )

        logger.info(f"✅ Pedido criado no Tiny: ID {data.get('id')}")

        return data

    async def update_order_status(
        self,
        order_id: int,
        situacao: int
    ) -> Dict[str, Any]:
        """
        Atualiza status de um pedido

        Args:
            order_id: ID do pedido
            situacao: Nova situação (0-9)

        Returns:
            Resposta da API
        """
        data = await self._request(
            "PUT",
            f"/pedidos/{order_id}/situacao",
            json={"situacao": situacao}
        )

        logger.info(f"✅ Status do pedido {order_id} atualizado")

        return data

    # ==================== Contatos (Clientes) ====================

    async def list_contacts(
        self,
        nome: Optional[str] = None,
        cpf_cnpj: Optional[str] = None,
        celular: Optional[str] = None,
        situacao: str = "B",  # B=Ativo
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Lista contatos (clientes/fornecedores)

        Args:
            nome: Filtrar por nome
            cpf_cnpj: Filtrar por CPF/CNPJ
            celular: Filtrar por celular
            situacao: B (Ativo), I (Inativo), E (Excluído)
            limit: Máximo de resultados
            offset: Posição inicial

        Returns:
            Lista de contatos
        """
        params = {
            "situacao": situacao,
            "limit": limit,
            "offset": offset
        }

        if nome:
            params["nome"] = nome
        if cpf_cnpj:
            params["cpfCnpj"] = cpf_cnpj
        if celular:
            params["celular"] = celular

        data = await self._request("GET", "/contatos", params=params)

        return data.get("data", [])

    async def create_contact(self, contact: TinyContactCreate) -> Dict[str, Any]:
        """
        Cria um novo contato (cliente)

        Args:
            contact: Dados do contato

        Returns:
            {
                "id": 12345,
                "mensagem": "Contato incluído com sucesso"
            }
        """
        data = await self._request(
            "POST",
            "/contatos",
            json=contact.dict(exclude_none=True)
        )

        logger.info(f"✅ Contato criado no Tiny: ID {data.get('id')}")

        return data

    async def update_contact(
        self,
        contact_id: int,
        contact: TinyContactCreate
    ) -> Dict[str, Any]:
        """Atualiza um contato existente"""
        data = await self._request(
            "PUT",
            f"/contatos/{contact_id}",
            json=contact.dict(exclude_none=True)
        )

        logger.info(f"✅ Contato {contact_id} atualizado")

        return data

    # ==================== Health Check ====================

    async def health_check(self) -> bool:
        """Verifica se a conexão está OK"""
        try:
            await self._request("GET", "/produtos", params={"limit": 1})
            return True
        except Exception as e:
            logger.error(f"❌ Health check falhou: {e}")
            return False

    # ==================== Cleanup ====================

    async def close(self):
        """Fecha conexões HTTP"""
        await self._client.aclose()
