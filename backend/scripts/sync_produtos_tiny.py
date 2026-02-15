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
from psycopg2.extras import RealDictCursor, Json
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
    produtos = await tiny_client.listar_produtos(limite=0, delay_entre_detalhes=1.0)

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
                # Preparar dados para produtos_site
                # Pegar primeira imagem para imagem_url
                imagens = produto.get("imagens", [])
                imagem_url = imagens[0] if isinstance(imagens, list) and len(imagens) > 0 else None

                # Converter peso para texto
                peso_bruto = produto.get("peso_bruto", 0)
                peso_liquido = produto.get("peso_liquido", 0)
                peso = str(peso_bruto or peso_liquido or 0)

                # Verificar se produto já existe (tiny_id é TEXT)
                cursor.execute(
                    "SELECT id FROM produtos_site WHERE tiny_id = %s",
                    (str(produto["tiny_id"]),)
                )

                existe = cursor.fetchone()

                # Extrair observacoes
                observacoes = produto.get("observacoes", "") or ""

                if existe:
                    # Atualizar produto existente
                    # descricao já vem unificada do tiny_products_client
                    cursor.execute("""
                        UPDATE produtos_site SET
                            nome = %s,
                            descricao = %s,
                            observacoes = %s,
                            preco = %s,
                            preco_promocional = %s,
                            peso = %s,
                            unidade = %s,
                            imagem_url = %s,
                            imagens_adicionais = %s,
                            link_produto = %s,
                            categoria = %s,
                            estoque_disponivel = %s,
                            quantidade_estoque = %s,
                            ativo = %s,
                            sincronizado_em = NOW(),
                            updated_at = NOW()
                        WHERE tiny_id = %s
                    """, (
                        produto["nome"],
                        produto["descricao"],
                        observacoes,
                        produto["preco"],
                        produto["preco_promocional"],
                        peso,
                        produto.get("unidade", "UN"),
                        imagem_url,
                        Json(imagens) if imagens else None,
                        produto.get("url_produto") or produto.get("link_produto", ""),
                        produto["categoria"],
                        produto["estoque"] > 0,
                        int(produto["estoque"]),
                        produto["ativo"],
                        str(produto["tiny_id"])
                    ))
                    atualizados += 1
                    logger.debug(f"✏️ Atualizado: {produto['nome']}")

                else:
                    # Inserir novo produto
                    # descricao já vem unificada do tiny_products_client
                    cursor.execute("""
                        INSERT INTO produtos_site (
                            tiny_id, nome, descricao,
                            observacoes,
                            preco, preco_promocional,
                            peso, unidade,
                            imagem_url, imagens_adicionais,
                            link_produto,
                            categoria,
                            estoque_disponivel, quantidade_estoque,
                            ativo, destaque,
                            sincronizado_em, created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW()
                        )
                    """, (
                        str(produto["tiny_id"]),
                        produto["nome"],
                        produto["descricao"],
                        observacoes,
                        produto["preco"],
                        produto["preco_promocional"],
                        peso,
                        produto.get("unidade", "UN"),
                        imagem_url,
                        Json(imagens) if imagens else None,
                        produto.get("url_produto") or produto.get("link_produto", ""),
                        produto["categoria"],
                        produto["estoque"] > 0,
                        int(produto["estoque"]),
                        produto["ativo"],
                        False  # destaque
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
