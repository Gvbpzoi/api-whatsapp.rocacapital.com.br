"""
Serviço para gerenciar carrinhos persistentes no Supabase
Garante que carrinhos sobrevivem a redeploys
"""

import os
import json
from typing import Dict, List, Optional, Any
from decimal import Decimal
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from loguru import logger


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


class SupabaseCarrinho:
    """Gerenciador de carrinhos persistentes no Supabase"""

    def __init__(self):
        """Inicializa conexão com Supabase"""
        self.db_url = os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL")
        self._pool = None

        if self.db_url:
            try:
                sanitized_url = sanitize_pg_dsn(self.db_url)
                self.db_url = sanitized_url
                self._pool = pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=5,
                    dsn=sanitized_url,
                    sslmode="require",
                )
                logger.info("Connection pool Carrinho criado (1-5 conexoes)")
            except Exception as e:
                logger.error(f"❌ Erro ao criar pool carrinho: {e}")
                self._pool = None
        else:
            logger.warning("⚠️ Nenhuma variável de DB configurada (DIRECT_URL ou DATABASE_URL)")

    def _get_connection(self):
        """Obtém conexão do pool, com fallback para conexão direta"""
        if self._pool:
            try:
                return self._pool.getconn()
            except Exception as e:
                logger.warning(f"Pool carrinho falhou, tentando conexao direta: {e}")
        if self.db_url:
            try:
                return psycopg2.connect(self.db_url, sslmode="require")
            except Exception as e:
                logger.error(f"Erro ao conectar diretamente (carrinho): {e}")
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
        try:
            conn.close()
        except Exception:
            pass

    def _execute(self, query: str, params: tuple = None, fetch: bool = True) -> Optional[List[Dict]]:
        """Executa query no banco com conexão do pool"""
        conn = self._get_connection()
        if not conn:
            logger.error("Sem conexao disponivel para carrinho")
            return None

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)

                if fetch:
                    result = cursor.fetchall()
                    self._put_connection(conn)
                    return [dict(row) for row in result] if result else []
                else:
                    conn.commit()
                    self._put_connection(conn)
                    return []
        except Exception as e:
            logger.error(f"❌ Erro ao executar query carrinho: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
            self._put_connection(conn)
            return None

    def adicionar_item(
        self,
        telefone: str,
        produto_id: str,
        produto_nome: str,
        preco_unitario: float,
        quantidade: int
    ) -> Dict[str, Any]:
        """
        Adiciona ou atualiza item no carrinho.
        Se item já existe, soma a quantidade.

        Returns:
            Dict com status da operação
        """
        try:
            subtotal = preco_unitario * quantidade

            # Verificar se produto já está no carrinho
            query = """
                SELECT quantidade, preco_unitario
                FROM carrinhos
                WHERE telefone = %s AND produto_id = %s::uuid
            """
            result = self._execute(query, (telefone, produto_id))

            if result and len(result) > 0:
                # Item já existe: atualizar quantidade
                quantidade_atual = result[0]["quantidade"]
                nova_quantidade = quantidade_atual + quantidade
                novo_subtotal = preco_unitario * nova_quantidade

                update_query = """
                    UPDATE carrinhos
                    SET quantidade = %s,
                        subtotal = %s,
                        atualizado_em = NOW()
                    WHERE telefone = %s AND produto_id = %s::uuid
                """
                self._execute(
                    update_query,
                    (nova_quantidade, novo_subtotal, telefone, produto_id),
                    fetch=False
                )

                logger.info(f"✅ Quantidade atualizada: {produto_nome} -> {nova_quantidade} un")
                return {
                    "status": "updated",
                    "quantidade_anterior": quantidade_atual,
                    "quantidade_nova": nova_quantidade
                }
            else:
                # Item novo: inserir
                insert_query = """
                    INSERT INTO carrinhos (telefone, produto_id, produto_nome, preco_unitario, quantidade, subtotal)
                    VALUES (%s, %s::uuid, %s, %s, %s, %s)
                """
                self._execute(
                    insert_query,
                    (telefone, produto_id, produto_nome, preco_unitario, quantidade, subtotal),
                    fetch=False
                )

                logger.info(f"✅ Item adicionado ao carrinho: {produto_nome}")
                return {"status": "added"}

        except Exception as e:
            logger.error(f"❌ Erro ao adicionar item: {e}")
            return {"status": "error", "message": str(e)}

    def obter_carrinho(self, telefone: str) -> List[Dict[str, Any]]:
        """
        Obtém todos os itens do carrinho de um cliente.

        Returns:
            Lista de itens do carrinho
        """
        try:
            query = """
                SELECT produto_id, produto_nome, preco_unitario, quantidade, subtotal
                FROM carrinhos
                WHERE telefone = %s
                ORDER BY criado_em ASC
            """
            result = self._execute(query, (telefone,))

            if result:
                # Converter Decimal para float para JSON
                items = []
                for item in result:
                    items.append({
                        "produto_id": str(item["produto_id"]),
                        "nome": item["produto_nome"],
                        "preco_unitario": float(item["preco_unitario"]),
                        "quantidade": item["quantidade"],
                        "subtotal": float(item["subtotal"])
                    })
                return items

            return []

        except Exception as e:
            logger.error(f"❌ Erro ao obter carrinho: {e}")
            return []

    def calcular_total(self, telefone: str) -> float:
        """Calcula total do carrinho"""
        try:
            query = """
                SELECT SUM(subtotal) as total
                FROM carrinhos
                WHERE telefone = %s
            """
            result = self._execute(query, (telefone,))

            if result and result[0]["total"]:
                return float(result[0]["total"])

            return 0.0

        except Exception as e:
            logger.error(f"❌ Erro ao calcular total: {e}")
            return 0.0

    def limpar_carrinho(self, telefone: str) -> bool:
        """Limpa todos os itens do carrinho"""
        try:
            query = "DELETE FROM carrinhos WHERE telefone = %s"
            self._execute(query, (telefone,), fetch=False)
            logger.info(f"🗑️ Carrinho limpo para {telefone[:8]}...")
            return True

        except Exception as e:
            logger.error(f"❌ Erro ao limpar carrinho: {e}")
            return False

    def remover_item(self, telefone: str, produto_id: str) -> bool:
        """Remove item específico do carrinho"""
        try:
            query = "DELETE FROM carrinhos WHERE telefone = %s AND produto_id = %s::uuid"
            self._execute(query, (telefone, produto_id), fetch=False)
            logger.info(f"🗑️ Item removido do carrinho: {produto_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Erro ao remover item: {e}")
            return False

    def atualizar_quantidade(self, telefone: str, produto_id: str, nova_quantidade: int) -> bool:
        """Atualiza quantidade de um item no carrinho"""
        try:
            query = """
                UPDATE carrinhos
                SET quantidade = %s,
                    subtotal = preco_unitario * %s,
                    atualizado_em = NOW()
                WHERE telefone = %s AND produto_id = %s::uuid
            """
            self._execute(query, (nova_quantidade, nova_quantidade, telefone, produto_id), fetch=False)
            logger.info(f"✏️ Quantidade atualizada: {produto_id} -> {nova_quantidade}")
            return True

        except Exception as e:
            logger.error(f"❌ Erro ao atualizar quantidade: {e}")
            return False

    def contar_itens(self, telefone: str) -> int:
        """Conta número de tipos de itens diferentes no carrinho"""
        try:
            query = "SELECT COUNT(*) as count FROM carrinhos WHERE telefone = %s"
            result = self._execute(query, (telefone,))

            if result:
                return result[0]["count"]

            return 0

        except Exception as e:
            logger.error(f"❌ Erro ao contar itens: {e}")
            return 0

    # ==================== Frete Confirmado ====================

    def salvar_frete(self, telefone: str, tipo_frete: str, valor_frete: float, prazo_entrega: str) -> bool:
        """Salva ou atualiza o frete confirmado para o cliente"""
        try:
            query = """
                INSERT INTO frete_confirmado (telefone, tipo_frete, valor_frete, prazo_entrega, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (telefone)
                DO UPDATE SET
                    tipo_frete = EXCLUDED.tipo_frete,
                    valor_frete = EXCLUDED.valor_frete,
                    prazo_entrega = EXCLUDED.prazo_entrega,
                    updated_at = NOW()
            """
            self._execute(query, (telefone, tipo_frete, valor_frete, prazo_entrega), fetch=False)
            logger.info(f"✅ Frete salvo: {tipo_frete} R$ {valor_frete:.2f} para {telefone[:8]}...")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao salvar frete: {e}")
            return False

    def obter_frete(self, telefone: str) -> Optional[Dict]:
        """Obtém o frete confirmado do cliente"""
        try:
            query = """
                SELECT tipo_frete, valor_frete, prazo_entrega
                FROM frete_confirmado
                WHERE telefone = %s
            """
            result = self._execute(query, (telefone,))
            if result and len(result) > 0:
                return {
                    "tipo_frete": result[0]["tipo_frete"],
                    "valor_frete": float(result[0]["valor_frete"]),
                    "prazo_entrega": result[0]["prazo_entrega"],
                }
            return None
        except Exception as e:
            logger.error(f"❌ Erro ao obter frete: {e}")
            return None

    def limpar_frete(self, telefone: str) -> bool:
        """Remove o frete confirmado do cliente"""
        try:
            query = "DELETE FROM frete_confirmado WHERE telefone = %s"
            self._execute(query, (telefone,), fetch=False)
            logger.info(f"🗑️ Frete limpo para {telefone[:8]}...")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao limpar frete: {e}")
            return False


# Singleton global
_carrinho_service: Optional[SupabaseCarrinho] = None


def get_supabase_carrinho() -> SupabaseCarrinho:
    """
    Retorna instância singleton do serviço de carrinhos.

    Returns:
        SupabaseCarrinho instance
    """
    global _carrinho_service

    if _carrinho_service is None:
        _carrinho_service = SupabaseCarrinho()

    return _carrinho_service
