"""
Cliente para integração com API do Tiny ERP v3 - Produtos Site

Responsável por:
- Autenticação OAuth com Tiny
- Busca de produtos
- Filtragem de produtos com "site" nas observações
- Normalização de dados para Supabase
"""

import os
import httpx
from typing import Dict, List, Optional
from loguru import logger

class TinyProductsClient:
    """Cliente para API do Tiny ERP v3"""

    BASE_URL = "https://api.tiny.com.br/api2"

    def __init__(self):
        """Inicializa o cliente com credenciais do ambiente"""
        # API v2 usa token simples, não OAuth
        # Tenta TINY_API_TOKEN primeiro, depois TINY_TOKEN
        self.token = os.getenv("TINY_API_TOKEN") or os.getenv("TINY_TOKEN")

        if not self.token:
            logger.warning("⚠️ TINY_API_TOKEN ou TINY_TOKEN não configurado")
            logger.info("💡 Configure uma dessas variáveis com seu token da API v2 do Tiny")

    def _get_headers(self) -> Dict[str, str]:
        """Retorna headers para requisições"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    async def listar_produtos(self, limite: int = 50) -> List[Dict]:
        """
        Lista produtos do Tiny ERP

        Args:
            limite: Número máximo de produtos a buscar

        Returns:
            Lista de produtos filtrados (apenas produtos com "site" nas obs)
        """
        logger.info("🔍 Buscando produtos do Tiny ERP...")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # API v2 do Tiny usa form-encoded, não JSON
                # Token simples no body
                response = await client.post(
                    f"{self.BASE_URL}/produtos.pesquisa.php",
                    data={
                        "token": self.token,
                        "formato": "JSON"
                    }
                )

                if response.status_code != 200:
                    logger.error(f"❌ Erro na API Tiny: {response.status_code}")
                    logger.error(f"❌ Response: {response.text[:500]}")
                    return []

                data = response.json()

                # Log da resposta completa para debug
                logger.debug(f"📥 Resposta Tiny: {data}")

                if data.get("retorno", {}).get("status") != "OK":
                    logger.error(f"❌ Status: {data.get('retorno', {}).get('status')}")
                    logger.error(f"❌ Erro Tiny: {data.get('retorno', {}).get('erro')}")
                    logger.error(f"❌ Resposta completa: {data}")
                    return []

                produtos_raw = data.get("retorno", {}).get("produtos", [])

                # Filtrar produtos
                produtos_filtrados = []
                total = len(produtos_raw)
                ignorados = 0

                for item in produtos_raw[:limite]:
                    produto = item.get("produto", {})

                    if self._eh_produto_site(produto):
                        produtos_filtrados.append(self._normalizar_produto(produto))
                    else:
                        ignorados += 1
                        logger.debug(f"⏭️ Ignorando: {produto.get('codigo')}")

                logger.info(
                    f"✅ Sincronização concluída: {len(produtos_filtrados)} produtos do site, "
                    f"{ignorados} ignorados de {total} total"
                )

                return produtos_filtrados

        except Exception as e:
            logger.error(f"❌ Erro ao buscar produtos: {e}")
            return []

    def _eh_produto_site(self, produto: Dict) -> bool:
        """
        NOVA REGRA SIMPLIFICADA:
        ✅ IMPORTA: Se campo "obs" contém a palavra "site"
        ❌ IGNORA: Se campo "obs" NÃO contém "site"

        Args:
            produto: Dados do produto do Tiny

        Returns:
            True se produto deve ser importado
        """
        obs = (produto.get("obs") or "").lower()
        codigo = produto.get("codigo", "SEM_CODIGO")

        # Log para debug: mostrar o que vem no campo obs
        logger.debug(f"🔍 Produto {codigo} | obs='{obs[:50] if obs else 'VAZIO'}'")

        if "site" in obs:
            logger.info(f"✅ Produto do SITE: {codigo}")
            return True

        logger.debug(f"⏭️ Ignorando {codigo}: não tem 'site' nas obs")
        return False

    def _normalizar_produto(self, produto: Dict) -> Dict:
        """
        Normaliza dados do Tiny para formato Supabase

        Args:
            produto: Produto do Tiny

        Returns:
            Produto normalizado
        """
        return {
            "tiny_id": str(produto.get("id", "")),
            "codigo": produto.get("codigo", ""),
            "nome": produto.get("nome", ""),
            "descricao": produto.get("descricao", ""),
            "preco": float(produto.get("preco", 0) or 0),
            "preco_custo": float(produto.get("preco_custo", 0) or 0),
            "preco_promocional": float(produto.get("preco_promocional", 0) or 0),
            "unidade": produto.get("unidade", "UN"),
            "peso_bruto": float(produto.get("peso_bruto", 0) or 0),
            "peso_liquido": float(produto.get("peso_liquido", 0) or 0),
            "gtin": produto.get("gtin", ""),
            "gtin_embalagem": produto.get("gtin_embalagem", ""),
            "categoria": produto.get("categoria", ""),
            "ncm": produto.get("ncm", ""),
            "origem": produto.get("origem", ""),
            "estoque": float(produto.get("estoque", 0) or 0),
            "estoque_minimo": float(produto.get("estoque_minimo", 0) or 0),
            "estoque_maximo": float(produto.get("estoque_maximo", 0) or 0),
            "situacao": produto.get("situacao", "A"),
            "tipo": produto.get("tipo", "P"),
            "classe_ipi": produto.get("classe_ipi", ""),
            "codigo_beneficio": produto.get("codigo_beneficio", ""),
            "obs": produto.get("obs", ""),
            "garantia": produto.get("garantia", ""),
            "cest": produto.get("cest", ""),
            "selo_ipi": produto.get("selo_ipi", ""),
            "imagens": produto.get("imagens", []),
            "variacoes": produto.get("variacoes", []),
            "estoque_disponivel": float(produto.get("estoque", 0) or 0) > 0,
            "ativo": produto.get("situacao") == "A"
        }


def get_tiny_products_client() -> TinyProductsClient:
    """Factory function para criar cliente Tiny"""
    return TinyProductsClient()
