"""
Serviço de produtos do Supabase
Substitui os mocks por dados reais da tabela produtos_site
"""
import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Optional
from loguru import logger
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse


DROP_QS_KEYS = {"pgbouncer", "connection_limit"}


def sanitize_pg_dsn(database_url: str) -> str:
    """Remove parâmetros incompatíveis com psycopg2"""
    u = urlparse(database_url)
    qs = dict(parse_qsl(u.query, keep_blank_values=True))
    for k in list(qs.keys()):
        if k in DROP_QS_KEYS:
            qs.pop(k, None)
    new_query = urlencode(qs, doseq=True)
    return urlunparse((u.scheme, u.netloc, u.path, u.params, new_query, u.fragment))


class SupabaseProdutos:
    """Cliente para buscar produtos do Supabase"""

    def __init__(self):
        """Inicializa conexão com Supabase"""
        self.database_url = os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL")
        if not self.database_url:
            logger.warning("⚠️ DATABASE_URL não configurado - usando modo mock")
            self.database_url = None
            self._pool = None
        else:
            self.database_url = sanitize_pg_dsn(self.database_url)
            try:
                self._pool = pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=5,
                    dsn=self.database_url,
                    sslmode="require",
                )
                logger.info("Connection pool Produtos criado (1-5 conexoes)")
            except Exception as e:
                logger.error(f"Erro ao criar pool produtos: {e}")
                self._pool = None

    def _get_connection(self):
        """Obtém conexão do pool, com fallback para conexão direta"""
        if self._pool:
            try:
                return self._pool.getconn()
            except Exception as e:
                logger.warning(f"Pool falhou, tentando conexao direta: {e}")
        # Fallback: conexão direta
        if self.database_url:
            try:
                return psycopg2.connect(self.database_url, sslmode="require")
            except Exception as e:
                logger.error(f"Erro ao conectar diretamente: {e}")
        return None

    def _put_connection(self, conn):
        """Devolve conexão ao pool ou fecha se foi direta"""
        if not conn:
            return
        if self._pool:
            try:
                self._pool.putconn(conn)
                return
            except Exception:
                pass
        # Fallback: fechar conexão direta
        try:
            conn.close()
        except Exception:
            pass

    def buscar_produtos(
        self,
        termo: Optional[str] = None,
        categoria: Optional[str] = None,
        limite: int = 20,
        apenas_disponiveis: bool = True
    ) -> List[Dict]:
        """
        Busca produtos no Supabase

        Args:
            termo: Termo de busca (busca em nome, descrição, categoria)
            categoria: Filtrar por categoria específica
            limite: Número máximo de resultados
            apenas_disponiveis: Se True, retorna apenas produtos ativos com estoque

        Returns:
            Lista de produtos encontrados
        """
        if not self.database_url:
            logger.warning("⚠️ Sem conexão com Supabase - retornando lista vazia")
            return []

        try:
            conn = self._get_connection()
            if not conn:
                logger.error("Sem conexao disponivel para buscar produtos")
                return []
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Construir query SQL
            query = """
                SELECT
                    id,
                    tiny_id,
                    nome,
                    descricao,
                    preco,
                    preco_promocional,
                    peso,
                    unidade,
                    imagem_url,
                    link_produto,
                    categoria,
                    subcategoria,
                    tags,
                    estoque_disponivel,
                    quantidade_estoque,
                    ativo
                FROM produtos_site
                WHERE 1=1
            """
            params = []

            # Filtro: apenas ativos
            if apenas_disponiveis:
                query += " AND ativo = TRUE AND estoque_disponivel = TRUE"

            # Filtro: categoria
            if categoria:
                query += " AND LOWER(categoria) = LOWER(%s)"
                params.append(categoria)

            # Filtro: termo de busca (nome, descrição, categoria, tags)
            # Usa UNACCENT para ignorar acentos: "cafes" encontra "Café" ✅
            #
            # Strategy for multi-word terms:
            # 1. Try full phrase match first ("%doce de leite%")
            #    → best for compound terms like "doce de leite", "queijo canastra"
            # 2. If no results, fall back to AND logic (every word must match somewhere)
            #    → good for "cafe especial" where both words must be present
            # NEVER use OR for filtering — it returns random products
            if termo:
                palavras = termo.strip().split()
                if len(palavras) > 1:
                    # Multi-word: search as full phrase across all fields
                    termo_like = f"%{termo}%"
                    query += """
                        AND (
                            unaccent(LOWER(nome)) LIKE unaccent(LOWER(%s))
                            OR unaccent(LOWER(categoria)) LIKE unaccent(LOWER(%s))
                            OR unaccent(LOWER(tags::text)) LIKE unaccent(LOWER(%s))
                            OR unaccent(LOWER(descricao)) LIKE unaccent(LOWER(%s))
                        )
                    """
                    params.extend([termo_like, termo_like, termo_like, termo_like])
                else:
                    # Single word: busca simples
                    termo_like = f"%{termo}%"
                    query += """
                        AND (
                            unaccent(LOWER(nome)) LIKE unaccent(LOWER(%s))
                            OR unaccent(LOWER(categoria)) LIKE unaccent(LOWER(%s))
                            OR unaccent(LOWER(tags::text)) LIKE unaccent(LOWER(%s))
                            OR unaccent(LOWER(descricao)) LIKE unaccent(LOWER(%s))
                        )
                    """
                    params.extend([termo_like, termo_like, termo_like, termo_like])

            # Ordenar por relevância: prioriza match em nome, depois categoria, depois tags
            if termo:
                palavras = termo.strip().split()
                if len(palavras) > 1:
                    # For multi-word: prioritize full-phrase match in nome
                    termo_like = f"%{termo}%"
                    query += """
                        ORDER BY
                            CASE WHEN unaccent(LOWER(nome)) LIKE unaccent(LOWER(%s)) THEN 0 ELSE 1 END,
                            CASE WHEN unaccent(LOWER(categoria)) LIKE unaccent(LOWER(%s)) THEN 0 ELSE 1 END,
                            CASE WHEN unaccent(LOWER(tags::text)) LIKE unaccent(LOWER(%s)) THEN 0 ELSE 1 END,
                            nome ASC
                        LIMIT %s
                    """
                    params.extend([termo_like, termo_like, termo_like])
                    params.append(limite)
                else:
                    query += """
                        ORDER BY
                            CASE WHEN unaccent(LOWER(nome)) LIKE unaccent(LOWER(%s)) THEN 0 ELSE 1 END,
                            CASE WHEN unaccent(LOWER(categoria)) LIKE unaccent(LOWER(%s)) THEN 0 ELSE 1 END,
                            CASE WHEN unaccent(LOWER(tags::text)) LIKE unaccent(LOWER(%s)) THEN 0 ELSE 1 END,
                            nome ASC
                        LIMIT %s
                    """
                    termo_like = f"%{termo}%"
                    params.extend([termo_like, termo_like, termo_like])
                    params.append(limite)
            else:
                # Se não tem termo, usar valores neutros para ordenação
                query += """
                    ORDER BY
                        CASE WHEN unaccent(LOWER(nome)) LIKE unaccent(LOWER(%s)) THEN 0 ELSE 1 END,
                        CASE WHEN unaccent(LOWER(categoria)) LIKE unaccent(LOWER(%s)) THEN 0 ELSE 1 END,
                        CASE WHEN unaccent(LOWER(tags::text)) LIKE unaccent(LOWER(%s)) THEN 0 ELSE 1 END,
                        nome ASC
                    LIMIT %s
                """
                params.extend(["%", "%", "%"])
                params.append(limite)

            cursor.execute(query, params)
            produtos = cursor.fetchall()

            # Fallback for multi-word: if phrase match found nothing,
            # retry with AND logic (every word must match somewhere)
            if not produtos and termo:
                palavras = termo.strip().split()
                if len(palavras) > 1:
                    logger.info(f"🔄 Phrase search found 0, retrying with AND logic: {palavras}")
                    query2 = """
                        SELECT id, tiny_id, nome, descricao,
                               preco, preco_promocional,
                               peso, unidade, imagem_url, link_produto, categoria,
                               subcategoria, tags, estoque_disponivel, quantidade_estoque, ativo
                        FROM produtos_site
                        WHERE 1=1
                    """
                    params2 = []
                    if apenas_disponiveis:
                        query2 += " AND ativo = TRUE AND estoque_disponivel = TRUE"
                    if categoria:
                        query2 += " AND LOWER(categoria) = LOWER(%s)"
                        params2.append(categoria)

                    # AND: every word must appear somewhere in the product
                    for palavra in palavras:
                        palavra_like = f"%{palavra}%"
                        query2 += """
                            AND (
                                unaccent(LOWER(nome)) LIKE unaccent(LOWER(%s))
                                OR unaccent(LOWER(categoria)) LIKE unaccent(LOWER(%s))
                                OR unaccent(LOWER(tags::text)) LIKE unaccent(LOWER(%s))
                                OR unaccent(LOWER(descricao)) LIKE unaccent(LOWER(%s))
                            )
                        """
                        params2.extend([palavra_like, palavra_like, palavra_like, palavra_like])

                    query2 += " ORDER BY nome ASC LIMIT %s"
                    params2.append(limite)
                    cursor2 = conn.cursor(cursor_factory=RealDictCursor)
                    cursor2.execute(query2, params2)
                    produtos = cursor2.fetchall()
                    cursor2.close()
                    logger.info(f"🔄 AND fallback: {len(produtos)} products found")

            cursor.close()
            self._put_connection(conn)

            # Converter RealDictRow para dict normal
            return [dict(p) for p in produtos]

        except Exception as e:
            logger.error(f"❌ Erro ao buscar produtos: {e}")
            if conn:
                self._put_connection(conn)
            return []

    def buscar_produto_por_id(self, produto_id: str) -> Optional[Dict]:
        """
        Busca produto por ID (UUID ou tiny_id)

        Args:
            produto_id: ID do produto (UUID ou tiny_id)

        Returns:
            Dados do produto ou None se não encontrado
        """
        if not self.database_url:
            return None

        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Tentar buscar por UUID ou tiny_id
            cursor.execute("""
                SELECT
                    id,
                    tiny_id,
                    nome,
                    descricao,
                    preco,
                    preco_promocional,
                    peso,
                    unidade,
                    imagem_url,
                    imagens_adicionais,
                    categoria,
                    subcategoria,
                    tags,
                    estoque_disponivel,
                    quantidade_estoque,
                    ativo,
                    link_produto
                FROM produtos_site
                WHERE id::text = %s OR tiny_id = %s
                LIMIT 1
            """, (produto_id, produto_id))

            produto = cursor.fetchone()

            cursor.close()
            self._put_connection(conn)

            return dict(produto) if produto else None

        except Exception as e:
            logger.error(f"❌ Erro ao buscar produto {produto_id}: {e}")
            if conn:
                self._put_connection(conn)
            return None

    def listar_categorias(self) -> List[str]:
        """
        Lista todas as categorias disponíveis

        Returns:
            Lista de nomes de categorias
        """
        if not self.database_url:
            return []

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT DISTINCT categoria
                FROM produtos_site
                WHERE categoria IS NOT NULL
                AND categoria != ''
                AND ativo = TRUE
                ORDER BY categoria ASC
            """)

            categorias = [row[0] for row in cursor.fetchall()]

            cursor.close()
            self._put_connection(conn)

            return categorias

        except Exception as e:
            logger.error(f"❌ Erro ao listar categorias: {e}")
            if conn:
                self._put_connection(conn)
            return []

    def contar_por_termo(self, termo: str) -> int:
        """
        Conta quantos produtos disponíveis casam com um termo de busca.

        Args:
            termo: Termo de busca (ex: "doce", "cafe", "azeite")

        Returns:
            Número de produtos encontrados
        """
        if not self.database_url:
            return 0

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            termo_like = f"%{termo}%"
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM produtos_site
                WHERE ativo = TRUE
                AND estoque_disponivel = TRUE
                AND (
                    unaccent(LOWER(nome)) LIKE unaccent(LOWER(%s))
                    OR unaccent(LOWER(categoria)) LIKE unaccent(LOWER(%s))
                    OR unaccent(LOWER(tags::text)) LIKE unaccent(LOWER(%s))
                    OR unaccent(LOWER(descricao)) LIKE unaccent(LOWER(%s))
                )
            """, (termo_like, termo_like, termo_like, termo_like))

            result = cursor.fetchone()
            cursor.close()
            self._put_connection(conn)

            return result[0] if result else 0

        except Exception as e:
            logger.error(f"❌ Erro ao contar produtos para '{termo}': {e}")
            if conn:
                self._put_connection(conn)
            return 0

    def buscar_produtos_em_destaque(self, limite: int = 10) -> List[Dict]:
        """
        Busca produtos em destaque

        Args:
            limite: Número máximo de produtos

        Returns:
            Lista de produtos em destaque
        """
        if not self.database_url:
            return []

        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT
                    id,
                    tiny_id,
                    nome,
                    descricao,
                    preco,
                    preco_promocional,
                    imagem_url,
                    categoria
                FROM produtos_site
                WHERE ativo = TRUE
                AND estoque_disponivel = TRUE
                AND destaque = TRUE
                ORDER BY nome ASC
                LIMIT %s
            """, (limite,))

            produtos = cursor.fetchall()

            cursor.close()
            self._put_connection(conn)

            return [dict(p) for p in produtos]

        except Exception as e:
            logger.error(f"❌ Erro ao buscar produtos em destaque: {e}")
            if conn:
                self._put_connection(conn)
            return []


# Singleton global
_supabase_produtos_instance = None


def get_supabase_produtos() -> SupabaseProdutos:
    """Factory function para obter instância do serviço"""
    global _supabase_produtos_instance
    if _supabase_produtos_instance is None:
        _supabase_produtos_instance = SupabaseProdutos()
    return _supabase_produtos_instance
