"""
Cliente para integração com API do Tiny ERP v3 - Produtos Site

Responsável por:
- Autenticação OAuth com Tiny
- Busca de produtos
- Filtragem de produtos com "site" nas observações
- Normalização de dados para Supabase
"""

import os
import re
import asyncio
import httpx
from html import unescape
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
    def _limpar_html(texto: str) -> str:
        """
        Remove tags HTML e normaliza whitespace de descricao_complementar.

        O Tiny retorna HTML rico (com <p>, <span>, estilos CSS).
        Esta função converte para texto puro legível.

        Args:
            texto: String com possível HTML

        Returns:
            Texto puro sem tags HTML, com whitespace normalizado
        """
        if not texto:
            return ""
        # Remover tags HTML
        limpo = re.sub(r"<[^>]+>", " ", texto)
        # Decodificar entidades HTML (&amp; → &, etc)
        limpo = unescape(limpo)
        # Normalizar whitespace (múltiplos espaços/newlines → espaço único)
        limpo = re.sub(r"\s+", " ", limpo).strip()
        return limpo

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

    def _extrair_erro(self, data: Dict) -> str:
        """Extrai mensagem de erro da resposta da API Tiny v2"""
        retorno = data.get("retorno", {})
        # Tentar campo 'erro' (string)
        erro = retorno.get("erro")
        if erro:
            return str(erro)
        # Tentar campo 'erros' (array)
        erros = retorno.get("erros", [])
        if erros:
            msgs = []
            for e in erros:
                if isinstance(e, dict):
                    msgs.append(e.get("erro", str(e)))
                else:
                    msgs.append(str(e))
            return " | ".join(msgs)
        return f"status={retorno.get('status')}, codigo={retorno.get('codigo_erro')}"

    async def _chamar_api_com_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        data: Dict,
        max_tentativas: int = 3
    ) -> Optional[Dict]:
        """
        Chama API do Tiny com retry e backoff para rate limiting

        Args:
            client: httpx client
            url: URL do endpoint
            data: Dados do POST
            max_tentativas: Numero maximo de tentativas

        Returns:
            JSON da resposta ou None se falhou
        """
        for tentativa in range(max_tentativas):
            try:
                response = await client.post(url, data=data)

                if response.status_code != 200:
                    logger.error(f"HTTP {response.status_code} em {url}")
                    return None

                result = response.json()
                retorno = result.get("retorno", {})

                # Rate limiting (codigo_erro 6)
                codigo_erro = retorno.get("codigo_erro")
                if codigo_erro == 6:
                    wait = (tentativa + 1) * 5  # 5s, 10s, 15s
                    logger.warning(
                        f"Rate limit atingido (tentativa {tentativa + 1}/{max_tentativas}), "
                        f"aguardando {wait}s..."
                    )
                    await asyncio.sleep(wait)
                    continue

                return result

            except Exception as e:
                logger.error(f"Excecao em {url}: {e}")
                if tentativa < max_tentativas - 1:
                    await asyncio.sleep(2)
                    continue
                return None

        return None

    async def obter_produto(self, produto_id: str, client: Optional[httpx.AsyncClient] = None) -> Optional[Dict]:
        """
        Obtém detalhes completos de um produto (incluindo observacoes)

        Args:
            produto_id: ID do produto no Tiny
            client: httpx client reutilizavel (opcional)

        Returns:
            Dados completos do produto ou None se erro
        """
        async def _fetch(c: httpx.AsyncClient):
            data = await self._chamar_api_com_retry(
                c,
                f"{self.BASE_URL}/produto.obter.php",
                {"token": self.token, "id": produto_id, "formato": "JSON"}
            )

            if not data:
                return None

            retorno = data.get("retorno", {})
            if retorno.get("status") == "OK":
                return retorno.get("produto", {})
            else:
                erro = self._extrair_erro(data)
                logger.debug(f"Produto {produto_id} indisponivel: {erro}")
                return None

        if client:
            return await _fetch(client)
        else:
            async with httpx.AsyncClient(timeout=30.0) as c:
                return await _fetch(c)

    async def obter_estoque(self, produto_id: str, client: Optional[httpx.AsyncClient] = None) -> Optional[float]:
        """
        Obtém estoque de um produto usando endpoint específico

        Args:
            produto_id: ID do produto no Tiny
            client: httpx client reutilizavel (opcional)

        Returns:
            Saldo (estoque) como float ou None se erro
        """
        async def _fetch(c: httpx.AsyncClient):
            data = await self._chamar_api_com_retry(
                c,
                f"{self.BASE_URL}/produto.obter.estoque.php",
                {"token": self.token, "id": produto_id, "formato": "JSON"}
            )

            if not data:
                return None

            retorno = data.get("retorno", {})
            if retorno.get("status") == "OK":
                produto = retorno.get("produto", {})
                saldo = produto.get("saldo") or produto.get("estoque")
                if saldo is not None:
                    return self._converter_estoque({"saldo": saldo})
                else:
                    return 0.0
            else:
                erro = self._extrair_erro(data)
                logger.debug(f"Estoque {produto_id} indisponivel: {erro}")
                return None

        if client:
            return await _fetch(client)
        else:
            async with httpx.AsyncClient(timeout=30.0) as c:
                return await _fetch(c)

    async def obter_produto_completo(
        self,
        produto_id: str,
        client: Optional[httpx.AsyncClient] = None
    ) -> Optional[Dict]:
        """
        Obtém produto completo COM estoque

        Busca detalhes e estoque sequencialmente (evita rate limiting)

        Args:
            produto_id: ID do produto no Tiny
            client: httpx client reutilizavel (opcional)

        Returns:
            Dicionário com dados do produto + estoque atualizado
        """
        async def _fetch(c: httpx.AsyncClient):
            # Buscar detalhes primeiro
            produto = await self.obter_produto(produto_id, client=c)

            if not produto:
                return None

            # Delay entre chamadas (usa metade do rate limit: 60 req/min = 1s entre chamadas)
            await asyncio.sleep(1.0)

            # Buscar estoque
            estoque = await self.obter_estoque(produto_id, client=c)

            if estoque is not None:
                produto["saldo"] = estoque
                produto["estoque"] = estoque
            else:
                produto["saldo"] = 0
                produto["estoque"] = 0

            return produto

        if client:
            return await _fetch(client)
        else:
            async with httpx.AsyncClient(timeout=30.0) as c:
                return await _fetch(c)

    async def _buscar_pagina(self, client: httpx.AsyncClient, pagina: int) -> List[Dict]:
        """
        Busca uma pagina de produtos da API Tiny (com retry)

        Args:
            client: httpx client reutilizavel
            pagina: Numero da pagina (1-based)

        Returns:
            Lista de produtos raw da pagina, ou lista vazia se nao ha mais
        """
        data = await self._chamar_api_com_retry(
            client,
            f"{self.BASE_URL}/produtos.pesquisa.php",
            {"token": self.token, "formato": "JSON", "pagina": str(pagina)}
        )

        if not data:
            return []

        retorno = data.get("retorno", {})
        status = retorno.get("status")

        if status != "OK":
            erro = self._extrair_erro(data)
            # "Nao existem registros" = acabaram as paginas
            if "registro" in erro.lower() or "nao ha" in erro.lower():
                logger.info(f"Pagina {pagina}: sem mais registros")
                return []
            logger.error(f"Erro Tiny pagina {pagina}: {erro}")
            return []

        produtos = retorno.get("produtos", [])
        numero_paginas = retorno.get("numero_paginas", 1)

        logger.info(f"Pagina {pagina}/{numero_paginas}: {len(produtos)} produtos")
        return produtos

    async def listar_produtos(
        self,
        limite: int = 0,
        filtrar_site: bool = True,
        delay_entre_detalhes: float = 1.0
    ) -> List[Dict]:
        """
        Lista produtos do Tiny ERP com paginacao automatica

        A API v2 do Tiny retorna no maximo 20 produtos por pagina.
        Este metodo percorre todas as paginas automaticamente.

        Args:
            limite: Maximo de produtos (0 = todos)
            filtrar_site: Se True, filtra apenas produtos com "site" nas obs
            delay_entre_detalhes: Delay entre chamadas de detalhe (rate limiting)

        Returns:
            Lista de produtos normalizados
        """
        modo = "apenas com 'site'" if filtrar_site else "TODOS"
        logger.info(f"Buscando produtos do Tiny ERP ({modo})...")

        try:
            todos_produtos_raw = []

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Buscar primeira pagina para saber total
                primeira_pagina = await self._buscar_pagina(client, 1)

                if not primeira_pagina:
                    logger.warning("Nenhum produto encontrado no Tiny")
                    return []

                todos_produtos_raw.extend(primeira_pagina)

                # Buscar paginas restantes
                pagina = 2
                while True:
                    # Rate limiting entre paginas (usa metade do rate limit: 60 req/min)
                    await asyncio.sleep(1.0)

                    produtos_pagina = await self._buscar_pagina(client, pagina)

                    if not produtos_pagina:
                        break

                    todos_produtos_raw.extend(produtos_pagina)
                    pagina += 1

                    # Safety: maximo 100 paginas (2000 produtos)
                    if pagina > 100:
                        logger.warning("Limite de 100 paginas atingido")
                        break

            total_raw = len(todos_produtos_raw)
            logger.info(f"Total bruto: {total_raw} produtos em {pagina - 1} paginas")

            # Aplicar limite se especificado
            if limite > 0:
                todos_produtos_raw = todos_produtos_raw[:limite]

            # Processar cada produto (buscar detalhes + estoque)
            # Reutiliza httpx client para todas as chamadas
            produtos_processados = []
            ignorados = 0
            erros_api = 0

            async with httpx.AsyncClient(timeout=30.0) as detail_client:
                for idx, item in enumerate(todos_produtos_raw, 1):
                    produto_resumo = item.get("produto", {})
                    produto_id = produto_resumo.get("id")
                    produto_nome = produto_resumo.get("descricao", produto_resumo.get("nome", "?"))

                    if not produto_id:
                        ignorados += 1
                        continue

                    # Log de progresso a cada 50 produtos
                    if idx % 50 == 0 or idx == 1:
                        logger.info(
                            f"Processando {idx}/{len(todos_produtos_raw)} "
                            f"({len(produtos_processados)} ok, {erros_api} erros)..."
                        )

                    # Buscar detalhes completos (com observacoes + estoque)
                    produto_completo = await self.obter_produto_completo(
                        produto_id, client=detail_client
                    )

                    if not produto_completo:
                        erros_api += 1
                        continue

                    if filtrar_site:
                        if await self._eh_produto_site_async(produto_completo):
                            produtos_processados.append(self._normalizar_produto(produto_completo))
                        else:
                            ignorados += 1
                    else:
                        produtos_processados.append(self._normalizar_produto(produto_completo))

                    # Rate limiting entre chamadas de detalhe
                    if delay_entre_detalhes > 0:
                        await asyncio.sleep(delay_entre_detalhes)

            logger.info(
                f"Sincronizacao concluida: {len(produtos_processados)} produtos processados, "
                f"{ignorados} sem filtro 'site', {erros_api} erros API, de {total_raw} total"
            )

            return produtos_processados

        except Exception as e:
            logger.error(f"Erro ao buscar produtos: {e}")
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

        # Usar descricao_complementar como descricao principal (campo descricao do Tiny vem vazio)
        descricao_complementar = self._limpar_html(produto.get("descricao_complementar", ""))
        descricao_simples = produto.get("descricao", "")
        descricao_final = descricao_complementar or descricao_simples

        return {
            "tiny_id": int(produto.get("id", 0)),
            "codigo": produto.get("codigo", ""),
            "nome": produto.get("nome", ""),
            "descricao": descricao_final,
            "observacoes": produto.get("obs", "") or produto.get("observacoes", "") or "",
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
