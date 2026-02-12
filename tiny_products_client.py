"""
Cliente para API do Tiny ERP - Sincronização de Produtos
"""
import os
import json
import base64
import httpx
from typing import List, Dict, Optional
from loguru import logger
from datetime import datetime


class TinyProductsClient:
    """Cliente para buscar produtos do Tiny ERP via OAuth"""

    def __init__(self):
        # Carregar tokens OAuth
        tokens_b64 = os.getenv("TINY_OAUTH_TOKENS", "")
        if tokens_b64:
            try:
                tokens_json = base64.b64decode(tokens_b64).decode('utf-8')
                self.tokens = json.loads(tokens_json)
                self.access_token = self.tokens.get("access_token")
                logger.info("✅ Tiny OAuth tokens carregados")
            except Exception as e:
                logger.error(f"❌ Erro ao decodificar tokens: {e}")
                self.tokens = {}
                self.access_token = None
        else:
            logger.warning("⚠️ TINY_OAUTH_TOKENS não configurado")
            self.tokens = {}
            self.access_token = None

        self.api_base_url = os.getenv("TINY_API_BASE_URL", "https://api.tiny.com.br/api2")
        self.prefer_v3 = os.getenv("TINY_PREFER_V3", "true").lower() == "true"

    def _get_headers(self) -> Dict[str, str]:
        """Headers para requisições autenticadas"""
        if self.access_token:
            return {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
        return {"Content-Type": "application/json"}

    async def listar_produtos(self, limite: int = 100) -> List[Dict]:
        """
        Lista produtos do Tiny ERP.

        FILTRO APLICADO:
        - Importa APENAS produtos para SITE (kits e variações)
        - NÃO importa produtos normais (são do PDV)

        Returns:
            Lista de produtos filtrados
        """
        logger.info("🔍 Buscando produtos do Tiny ERP...")

        produtos_site = []
        pagina = 1
        total_processados = 0
        total_ignorados = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                try:
                    # API V3 (OAuth)
                    url = f"{self.api_base_url}/produtos"
                    params = {
                        "limite": limite,
                        "pagina": pagina,
                    }

                    response = await client.get(
                        url,
                        headers=self._get_headers(),
                        params=params
                    )

                    if response.status_code != 200:
                        logger.error(f"❌ Erro na API Tiny: {response.status_code}")
                        break

                    data = response.json()
                    produtos_raw = data.get("retorno", {}).get("produtos", [])

                    if not produtos_raw:
                        logger.info("✅ Fim da paginação")
                        break

                    # Processar e filtrar produtos
                    for item in produtos_raw:
                        produto = item.get("produto", {})
                        total_processados += 1

                        # Aplicar filtro: apenas produtos do SITE
                        if self._eh_produto_site(produto):
                            produtos_site.append(self._normalizar_produto(produto))
                        else:
                            total_ignorados += 1
                            logger.debug(
                                f"⏭️ Produto {produto.get('codigo')} ignorado "
                                f"(tipo: {produto.get('tipoVariacao', 'N')}, "
                                f"classe: {produto.get('classe_produto', 'S')})"
                            )

                    logger.info(
                        f"📄 Página {pagina}: {len(produtos_raw)} produtos, "
                        f"{len(produtos_site)} do site"
                    )

                    # Próxima página
                    pagina += 1

                    # Limitar para não processar infinito (remover em produção)
                    if pagina > 10:
                        logger.warning("⚠️ Limite de 10 páginas atingido (dev mode)")
                        break

                except Exception as e:
                    logger.error(f"❌ Erro ao buscar produtos: {e}")
                    break

        logger.info(
            f"✅ Sincronização concluída: {len(produtos_site)} produtos do site, "
            f"{total_ignorados} ignorados de {total_processados} total"
        )

        return produtos_site

    def _eh_produto_site(self, produto: Dict) -> bool:
        """
        Determina se produto é vendido no SITE (não PDV).

        NOVA REGRA SIMPLIFICADA:
        ✅ IMPORTA: Se campo "obs" contém a palavra "site" (case-insensitive)
        ❌ IGNORA: Se campo "obs" NÃO contém "site"

        Exemplo:
        - obs: "Produto para venda no site" → IMPORTA ✅
        - obs: "Produto PDV" → IGNORA ❌
        - obs: "" → IGNORA ❌
        """
        obs = (produto.get("obs") or "").lower()

        # Verificar se contém "site"
        if "site" in obs:
            logger.debug(f"✅ Produto do SITE: {produto.get('codigo')} (obs: {obs[:50]}...)")
            return True

        logger.debug(f"⏭️ Produto PDV: {produto.get('codigo')} (obs: {obs[:50]}...)")
        return False

    def _normalizar_produto(self, produto: Dict) -> Dict:
        """
        Normaliza produto do Tiny para formato do Supabase.
        """
        # Extrair imagens
        imagem_url = None
        imagens_adicionais = []

        anexos = produto.get("anexos", [])
        if anexos:
            # Primeira imagem como principal
            if len(anexos) > 0:
                imagem_url = anexos[0].get("anexo")
            # Demais como adicionais
            if len(anexos) > 1:
                imagens_adicionais = [a.get("anexo") for a in anexos[1:]]

        # Categoria (tentar inferir do nome ou usar campo do Tiny)
        nome = produto.get("nome", "").lower()
        categoria = "outros"
        if "queijo" in nome:
            categoria = "queijo"
        elif "cachaça" in nome or "cachaca" in nome:
            categoria = "cachaça"
        elif "doce" in nome or "geleia" in nome:
            categoria = "doce"
        elif "café" in nome or "cafe" in nome:
            categoria = "café"

        # Montar link do produto (se tiver SKU)
        sku = produto.get("codigo")
        link_produto = None
        if sku:
            # Assumindo padrão Shopify/WooCommerce
            link_produto = f"https://rocacapital.com.br/products/{sku}"

        return {
            "tiny_id": produto.get("id"),
            "nome": produto.get("nome"),
            "descricao": produto.get("descricao") or produto.get("descricao_complementar"),
            "preco": float(produto.get("preco") or 0),
            "preco_promocional": float(produto.get("preco_promocional") or 0) if produto.get("preco_promocional") else None,
            "peso": produto.get("peso_bruto"),
            "unidade": produto.get("unidade"),
            "imagem_url": imagem_url,
            "imagens_adicionais": imagens_adicionais if imagens_adicionais else None,
            "link_produto": link_produto,
            "categoria": categoria,
            "subcategoria": produto.get("classe_produto"),
            "tags": [],
            "estoque_disponivel": float(produto.get("saldo") or 0) > 0,
            "quantidade_estoque": int(float(produto.get("saldo") or 0)),
            "ativo": produto.get("situacao") == "A",
            "destaque": False,
            "sincronizado_em": datetime.now().isoformat(),
        }


# Singleton
_client = None


def get_tiny_products_client() -> TinyProductsClient:
    """Retorna instância singleton do cliente"""
    global _client
    if _client is None:
        _client = TinyProductsClient()
    return _client
