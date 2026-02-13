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

    @staticmethod
    def _converter_estoque(produto: Dict) -> float:
        """
        Converte estoque da API Tiny para float, tratando vários formatos

        A API do Tiny pode retornar estoque em diferentes formatos:
        - String com vírgula: "10,5" → 10.5
        - String com ponto: "10.5" → 10.5
        - Número: 10.5 → 10.5
        - Negativo: -5 → 0 (não existe estoque negativo)
        - None/vazio: → 0
        - Pode estar em campos: "estoque", "saldo", "estoque_atual"

        Args:
            produto: Dicionário do produto retornado pela API Tiny

        Returns:
            Estoque como float (sempre >= 0)
        """
        # Tentar vários campos possíveis
        campos_estoque = ["estoque", "saldo", "estoque_atual", "quantidade"]

        for campo in campos_estoque:
            valor = produto.get(campo)

            if valor is None or valor == "":
                continue

            try:
                # Se for string, substituir vírgula por ponto
                if isinstance(valor, str):
                    valor = valor.strip().replace(",", ".")

                # Converter para float
                estoque_float = float(valor)

                # Estoque negativo vira 0
                if estoque_float < 0:
                    logger.warning(
                        f"⚠️ Estoque negativo detectado ({estoque_float}) para produto "
                        f"{produto.get('id', '?')} - campo '{campo}'. Usando 0."
                    )
                    return 0.0

                # Sucesso!
                if estoque_float > 0:
                    logger.debug(
                        f"✅ Estoque obtido do campo '{campo}': {estoque_float} "
                        f"(produto {produto.get('id', '?')})"
                    )
                return estoque_float

            except (ValueError, TypeError) as e:
                logger.debug(
                    f"⚠️ Erro ao converter estoque do campo '{campo}': {valor} - {e}"
                )
                continue

        # Nenhum campo funcionou
        logger.warning(
            f"⚠️ Nenhum campo de estoque válido encontrado para produto "
            f"{produto.get('id', '?')} ({produto.get('nome', '?')})"
        )
        return 0.0

    def _get_headers(self) -> Dict[str, str]:
        """Retorna headers para requisições"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    async def obter_produto(self, produto_id: str) -> Optional[Dict]:
        """
        Obtém detalhes completos de um produto (incluindo observacoes)

        Args:
            produto_id: ID do produto no Tiny

        Returns:
            Dados completos do produto ou None se erro
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/produto.obter.php",
                    data={
                        "token": self.token,
                        "id": produto_id,
                        "formato": "JSON"
                    }
                )

                if response.status_code != 200:
                    logger.error(f"❌ Erro ao obter produto {produto_id}: {response.status_code}")
                    return None

                data = response.json()

                if data.get("retorno", {}).get("status") == "OK":
                    return data.get("retorno", {}).get("produto", {})
                else:
                    logger.error(f"❌ Erro Tiny produto {produto_id}: {data.get('retorno', {}).get('erro')}")
                    return None

        except Exception as e:
            logger.error(f"❌ Exceção ao obter produto {produto_id}: {e}")
            return None

    async def obter_estoque(self, produto_id: str) -> Optional[float]:
        """
        Obtém estoque de um produto usando endpoint específico

        Endpoint: /produto.obter.estoque.php
        Retorna apenas o saldo (estoque atual) do produto

        Args:
            produto_id: ID do produto no Tiny

        Returns:
            Saldo (estoque) como float ou None se erro
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/produto.obter.estoque.php",
                    data={
                        "token": self.token,
                        "id": produto_id,
                        "formato": "JSON"
                    }
                )

                if response.status_code != 200:
                    logger.error(f"❌ Erro ao obter estoque produto {produto_id}: {response.status_code}")
                    return None

                data = response.json()

                if data.get("retorno", {}).get("status") == "OK":
                    produto = data.get("retorno", {}).get("produto", {})

                    # Tentar campo "saldo" (mais comum) ou "estoque"
                    saldo = produto.get("saldo") or produto.get("estoque")

                    if saldo is not None:
                        # Usar método existente para converter
                        return self._converter_estoque({"saldo": saldo})
                    else:
                        logger.warning(f"⚠️ Produto {produto_id} não tem campo saldo/estoque")
                        return 0.0
                else:
                    logger.error(f"❌ Erro Tiny estoque {produto_id}: {data.get('retorno', {}).get('erro')}")
                    return None

        except Exception as e:
            logger.error(f"❌ Exceção ao obter estoque {produto_id}: {e}")
            return None

    async def obter_produto_completo(self, produto_id: str) -> Optional[Dict]:
        """
        Obtém produto completo COM estoque

        Faz 2 chamadas em paralelo:
        1. produto.obter.php - Detalhes do produto
        2. produto.obter.estoque.php - Estoque atual

        Args:
            produto_id: ID do produto no Tiny

        Returns:
            Dicionário com dados do produto + estoque atualizado
        """
        import asyncio

        # Buscar produto e estoque em paralelo
        produto_task = self.obter_produto(produto_id)
        estoque_task = self.obter_estoque(produto_id)

        produto, estoque = await asyncio.gather(produto_task, estoque_task)

        if not produto:
            return None

        # Adicionar estoque ao produto
        if estoque is not None:
            produto["saldo"] = estoque
            produto["estoque"] = estoque
            logger.debug(f"✅ Produto {produto_id} com estoque: {estoque}")
        else:
            produto["saldo"] = 0
            produto["estoque"] = 0
            logger.warning(f"⚠️ Produto {produto_id} sem estoque disponível")

        return produto

    async def listar_produtos(self, limite: int = 50, filtrar_site: bool = True) -> List[Dict]:
        """
        Lista produtos do Tiny ERP

        Args:
            limite: Número máximo de produtos a buscar
            filtrar_site: Se True, filtra apenas produtos com "site" nas obs

        Returns:
            Lista de produtos (filtrados ou todos, dependendo do parâmetro)
        """
        if filtrar_site:
            logger.info("🔍 Buscando produtos do Tiny ERP (apenas com 'site')...")
        else:
            logger.info("🔍 Buscando TODOS os produtos do Tiny ERP (sem filtro)...")

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

                # Processar produtos
                produtos_processados = []
                total = len(produtos_raw)
                ignorados = 0

                logger.info(f"📦 Processando {min(len(produtos_raw), limite)} produtos...")

                for item in produtos_raw[:limite]:
                    produto_resumo = item.get("produto", {})
                    produto_id = produto_resumo.get("id")

                    if not produto_id:
                        logger.warning(f"⚠️ Produto sem ID: {produto_resumo.get('codigo')}")
                        ignorados += 1
                        continue

                    # Buscar detalhes completos (com observacoes + estoque)
                    produto_completo = await self.obter_produto_completo(produto_id)

                    if not produto_completo:
                        ignorados += 1
                        continue

                    # Se filtrar_site=True, verificar se tem "site" nas obs
                    # Se filtrar_site=False, aceitar todos
                    if filtrar_site:
                        if await self._eh_produto_site_async(produto_completo):
                            produtos_processados.append(self._normalizar_produto(produto_completo))
                        else:
                            ignorados += 1
                    else:
                        # Aceitar TODOS sem filtro
                        produtos_processados.append(self._normalizar_produto(produto_completo))

                if filtrar_site:
                    logger.info(
                        f"✅ Sincronização concluída: {len(produtos_processados)} produtos do site, "
                        f"{ignorados} ignorados de {total} total"
                    )
                else:
                    logger.info(
                        f"✅ Sincronização concluída: {len(produtos_processados)} produtos total"
                    )

                return produtos_processados

        except Exception as e:
            logger.error(f"❌ Erro ao buscar produtos: {e}")
            return []

    async def _eh_produto_site_async(self, produto: Dict) -> bool:
        """
        NOVA REGRA: Verifica campo "observacoes" (detalhes completos)
        ✅ IMPORTA: Se "observacoes" contém "site"
        ❌ IGNORA: Se NÃO contém

        Args:
            produto: Dados COMPLETOS do produto (de obter_produto)

        Returns:
            True se produto deve ser importado
        """
        # Tentar vários nomes possíveis do campo
        obs = (
            produto.get("observacoes") or
            produto.get("observacao") or
            produto.get("obs") or
            ""
        ).lower().strip()

        produto_id = produto.get("id", "?")
        codigo = produto.get("codigo") or "-"

        # Log para debug
        logger.debug(f"🔍 id={produto_id} codigo={codigo} | obs='{obs[:50] if obs else 'VAZIO'}'")

        if "site" in obs:
            logger.info(f"✅ SITE: id={produto_id} codigo={codigo}")
            return True

        logger.debug(f"⏭️ Ignorando: id={produto_id} (sem 'site')")
        return False

    def _normalizar_produto(self, produto: Dict) -> Dict:
        """
        Normaliza dados do Tiny para formato Supabase (tabela produtos_site)

        Estrutura da resposta Tiny:
        - anexos: [{"anexo": "url"}]
        - imagens_externas: [{"imagem_externa": {"url": "url"}}]
        - descricao_complementar: texto com harmonizações, textura, etc

        Args:
            produto: Produto do Tiny (retorno completo de produto.obter.php)

        Returns:
            Produto normalizado para schema Supabase
        """
        # Processar imagens do Tiny (anexos + imagens_externas)
        imagens_urls = []

        # Anexos (imagens do Tiny)
        anexos = produto.get("anexos", [])
        if isinstance(anexos, list):
            for item in anexos:
                if isinstance(item, dict):
                    url = item.get("anexo", "")
                    if url:
                        imagens_urls.append(url)

        # Imagens externas
        imagens_ext = produto.get("imagens_externas", [])
        if isinstance(imagens_ext, list):
            for item in imagens_ext:
                if isinstance(item, dict):
                    img_obj = item.get("imagem_externa", {})
                    if isinstance(img_obj, dict):
                        url = img_obj.get("url", "")
                        if url:
                            imagens_urls.append(url)

        return {
            "tiny_id": int(produto.get("id", 0)),
            "codigo": produto.get("codigo", ""),
            "nome": produto.get("nome", ""),
            "descricao": produto.get("descricao", ""),
            "descricao_complementar": produto.get("descricao_complementar", ""),
            "preco": float(produto.get("preco", 0) or 0),
            "preco_custo": float(produto.get("preco_custo", 0) or 0),
            "preco_promocional": float(produto.get("preco_promocional", 0) or 0),
            "unidade": produto.get("unidade", "UN"),
            "peso_bruto": float(produto.get("peso_bruto", 0) or 0),
            "peso_liquido": float(produto.get("peso_liquido", 0) or 0),
            "gtin": produto.get("gtin", ""),
            "categoria": produto.get("categoria", ""),
            "ncm": produto.get("ncm", ""),
            "estoque": self._converter_estoque(produto),  # Converte com tratamento robusto
            "imagens": imagens_urls,  # Array de URLs processado de anexos + imagens_externas
            "url_produto": produto.get("url_produto", ""),
            "link_produto": produto.get("link_produto", ""),
            "ativo": produto.get("situacao") == "A"
        }


def get_tiny_products_client() -> TinyProductsClient:
    """Factory function para criar cliente Tiny"""
    return TinyProductsClient()
