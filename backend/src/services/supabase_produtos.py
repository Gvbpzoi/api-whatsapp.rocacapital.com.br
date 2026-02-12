"""
Serviço de produtos do Supabase
Substitui os mocks por dados reais da tabela produtos_site
"""
import os
import psycopg2
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
        self.database_url = os.getenv("DATABASE_URL") or os.getenv("DIRECT_URL")
        if not self.database_url:
            logger.warning("⚠️ DATABASE_URL não configurado - usando modo mock")
            self.database_url = None
        else:
            self.database_url = sanitize_pg_dsn(self.database_url)

    def _get_connection(self):
        """Cria conexão com banco"""
        if not self.database_url:
            return None
        return psycopg2.connect(self.database_url, sslmode="require")

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

            # Filtro: termo de busca (nome, descrição, categoria)
            # Usa UNACCENT para ignorar acentos: "cafes" encontra "Café" ✅
            if termo:
                query += """
                    AND (
                        unaccent(LOWER(nome)) LIKE unaccent(LOWER(%s))
                        OR unaccent(LOWER(descricao)) LIKE unaccent(LOWER(%s))
                        OR unaccent(LOWER(categoria)) LIKE unaccent(LOWER(%s))
                    )
                """
                termo_like = f"%{termo}%"
                params.extend([termo_like, termo_like, termo_like])

            # Ordenar por nome
            query += " ORDER BY nome ASC LIMIT %s"
            params.append(limite)

            cursor.execute(query, params)
            produtos = cursor.fetchall()

            cursor.close()
            conn.close()

            # Converter RealDictRow para dict normal
            return [dict(p) for p in produtos]

        except Exception as e:
            logger.error(f"❌ Erro ao buscar produtos: {e}")
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
            conn.close()

            return dict(produto) if produto else None

        except Exception as e:
            logger.error(f"❌ Erro ao buscar produto {produto_id}: {e}")
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
            conn.close()

            return categorias

        except Exception as e:
            logger.error(f"❌ Erro ao listar categorias: {e}")
            return []

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
            conn.close()

            return [dict(p) for p in produtos]

        except Exception as e:
            logger.error(f"❌ Erro ao buscar produtos em destaque: {e}")
            return []


# Singleton global
_supabase_produtos_instance = None


def get_supabase_produtos() -> SupabaseProdutos:
    """Factory function para obter instância do serviço"""
    global _supabase_produtos_instance
    if _supabase_produtos_instance is None:
        _supabase_produtos_instance = SupabaseProdutos()
    return _supabase_produtos_instance
