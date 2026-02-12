"""
Script de sincronização de produtos Tiny → Supabase

Execução:
    python scripts/sync_produtos_tiny.py

Ambiente:
    Requer variáveis configuradas no .env:
    - DATABASE_URL
    - TINY_CLIENT_ID
    - TINY_CLIENT_SECRET
    - TINY_OAUTH_TOKENS
"""

import asyncio
import os
import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from loguru import logger
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from src.services.tiny_products_client import get_tiny_products_client

# Carregar variáveis de ambiente
load_dotenv()

# Parâmetros que psycopg2 não entende (Supabase específicos)
DROP_QS_KEYS = {"pgbouncer", "connection_limit"}


def sanitize_pg_dsn(database_url: str) -> str:
    """
    Remove query params que psycopg2 não aceita
    (ex: pgbouncer, connection_limit do Supabase)
    """
    u = urlparse(database_url)
    qs = dict(parse_qsl(u.query, keep_blank_values=True))

    # Remover parâmetros incompatíveis
    for k in list(qs.keys()):
        if k in DROP_QS_KEYS:
            qs.pop(k, None)

    new_query = urlencode(qs, doseq=True)
    return urlunparse((u.scheme, u.netloc, u.path, u.params, new_query, u.fragment))


def get_db_connection():
    """Cria conexão com Supabase (PostgreSQL)"""
    database_url = os.getenv("DATABASE_URL") or os.getenv("DIRECT_URL")

    if not database_url:
        raise ValueError("DATABASE_URL ou DIRECT_URL não configurado")

    # Sanitizar URL removendo parâmetros incompatíveis
    database_url = sanitize_pg_dsn(database_url)

    # Supabase geralmente requer SSL
    return psycopg2.connect(database_url, sslmode="require")


async def sincronizar_produtos():
    """Sincroniza produtos do Tiny para Supabase"""
    logger.info("🚀 Iniciando sincronização Tiny → Supabase...")

    # Buscar produtos do Tiny
    tiny_client = get_tiny_products_client()
    produtos = await tiny_client.listar_produtos(limite=50)

    if not produtos:
        logger.warning("⚠️ Nenhum produto encontrado no Tiny")
        return

    logger.info(f"📦 {len(produtos)} produtos encontrados no Tiny")

    # Conectar ao Supabase
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        novos = 0
        atualizados = 0
        erros = 0

        for produto in produtos:
            try:
                # Verificar se produto já existe
                cursor.execute(
                    "SELECT id FROM produtos_site WHERE tiny_id = %s",
                    (produto["tiny_id"],)
                )

                existe = cursor.fetchone()

                if existe:
                    # Atualizar produto existente
                    cursor.execute("""
                        UPDATE produtos_site SET
                            codigo = %s,
                            nome = %s,
                            descricao = %s,
                            preco = %s,
                            preco_custo = %s,
                            preco_promocional = %s,
                            categoria = %s,
                            estoque = %s,
                            estoque_disponivel = %s,
                            ativo = %s,
                            obs = %s,
                            imagens = %s,
                            updated_at = NOW()
                        WHERE tiny_id = %s
                    """, (
                        produto["codigo"],
                        produto["nome"],
                        produto["descricao"],
                        produto["preco"],
                        produto["preco_custo"],
                        produto["preco_promocional"],
                        produto["categoria"],
                        produto["estoque"],
                        produto["estoque_disponivel"],
                        produto["ativo"],
                        produto["obs"],
                        produto.get("imagens"),
                        produto["tiny_id"]
                    ))
                    atualizados += 1
                    logger.debug(f"✏️ Atualizado: {produto['nome']}")

                else:
                    # Inserir novo produto
                    cursor.execute("""
                        INSERT INTO produtos_site (
                            tiny_id, codigo, nome, descricao,
                            preco, preco_custo, preco_promocional,
                            categoria, estoque, estoque_disponivel,
                            ativo, obs, imagens
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        produto["tiny_id"],
                        produto["codigo"],
                        produto["nome"],
                        produto["descricao"],
                        produto["preco"],
                        produto["preco_custo"],
                        produto["preco_promocional"],
                        produto["categoria"],
                        produto["estoque"],
                        produto["estoque_disponivel"],
                        produto["ativo"],
                        produto["obs"],
                        produto.get("imagens")
                    ))
                    novos += 1
                    logger.debug(f"➕ Novo: {produto['nome']}")

                conn.commit()

            except Exception as e:
                logger.error(f"❌ Erro ao processar {produto.get('nome')}: {e}")
                erros += 1
                conn.rollback()

        # Resumo final
        logger.info("=" * 60)
        logger.info(f"✅ Sincronização concluída!")
        logger.info(f"   📊 Total processado: {len(produtos)}")
        logger.info(f"   ➕ Novos: {novos}")
        logger.info(f"   ✏️ Atualizados: {atualizados}")
        logger.info(f"   ❌ Erros: {erros}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Erro na sincronização: {e}")
        raise

    finally:
        cursor.close()
        conn.close()


async def main():
    """Função principal"""
    await sincronizar_produtos()


if __name__ == "__main__":
    asyncio.run(main())
