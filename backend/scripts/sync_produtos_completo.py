#!/usr/bin/env python3
"""
Script de sincronização COMPLETA de produtos Tiny → Supabase
Versão otimizada para catálogo completo com rate limiting

Execução:
    python scripts/sync_produtos_completo.py [--all] [--delay SEGUNDOS]

Opções:
    --all           Sincroniza TODOS os produtos (não só os com 'site')
    --delay SECS    Delay entre chamadas API (padrão: 0.5s)
    --batch SIZE    Tamanho do lote (padrão: 100)
    --dry-run       Simula sem gravar no banco

Ambiente:
    - DATABASE_URL
    - TINY_API_TOKEN
"""

import asyncio
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

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
    """Remove query params que psycopg2 não aceita"""
    u = urlparse(database_url)
    qs = dict(parse_qsl(u.query, keep_blank_values=True))

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

    database_url = sanitize_pg_dsn(database_url)
    return psycopg2.connect(database_url, sslmode="require")


async def sincronizar_produtos(
    sync_all: bool = False,
    delay: float = 0.5,
    batch_size: int = 100,
    dry_run: bool = False
):
    """
    Sincroniza produtos do Tiny para Supabase

    Args:
        sync_all: Se True, sincroniza TODOS (não só os com 'site')
        delay: Segundos de delay entre chamadas API
        batch_size: Tamanho do lote
        dry_run: Se True, não grava no banco
    """
    inicio = datetime.now()
    logger.info("=" * 80)
    logger.info("🚀 SINCRONIZAÇÃO COMPLETA TINY → SUPABASE")
    logger.info("=" * 80)
    logger.info(f"📅 Início: {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🎯 Modo: {'TODOS OS PRODUTOS' if sync_all else 'APENAS PRODUTOS COM SITE'}")
    logger.info(f"⏱️ Delay: {delay}s entre produtos")
    logger.info(f"📦 Batch: {batch_size} produtos por lote")
    logger.info(f"🧪 Dry Run: {'SIM (não grava)' if dry_run else 'NÃO (grava no banco)'}")
    logger.info("=" * 80)

    # Buscar produtos do Tiny
    tiny_client = get_tiny_products_client()

    # Configurar cliente para buscar TODOS ou filtrar
    if sync_all:
        logger.info("🔍 Buscando TODOS os produtos do Tiny (sem filtro, com paginacao)...")
        produtos = await tiny_client.listar_produtos(
            limite=0, filtrar_site=False, delay_entre_detalhes=delay
        )
    else:
        logger.info("🔍 Buscando apenas produtos com 'site' nas observações...")
        produtos = await tiny_client.listar_produtos(
            limite=0, filtrar_site=True, delay_entre_detalhes=delay
        )

    if not produtos:
        logger.warning("⚠️ Nenhum produto encontrado no Tiny")
        return

    logger.info(f"📦 {len(produtos)} produtos encontrados")

    # Conectar ao Supabase (só se não for dry-run)
    conn = None
    cursor = None

    if not dry_run:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        novos = 0
        atualizados = 0
        pulados = 0
        erros = 0

        for idx, produto in enumerate(produtos, 1):
            try:
                # Log de progresso
                if idx % 10 == 0 or idx == 1:
                    logger.info(f"⏳ Processando {idx}/{len(produtos)}...")

                # Preparar dados
                imagens = produto.get("imagens", [])
                imagem_url = imagens[0] if isinstance(imagens, list) and len(imagens) > 0 else None

                peso_bruto = produto.get("peso_bruto", 0)
                peso_liquido = produto.get("peso_liquido", 0)
                peso = str(peso_bruto or peso_liquido or 0)

                if dry_run:
                    logger.debug(f"🧪 [DRY-RUN] {produto['nome']} (ID: {produto['tiny_id']})")
                    pulados += 1
                else:
                    # Verificar se existe
                    cursor.execute(
                        "SELECT id FROM produtos_site WHERE tiny_id = %s",
                        (str(produto["tiny_id"]),)
                    )

                    existe = cursor.fetchone()

                    if existe:
                        # Atualizar
                        cursor.execute("""
                            UPDATE produtos_site SET
                                nome = %s,
                                descricao = %s,
                                preco = %s,
                                preco_promocional = %s,
                                peso = %s,
                                unidade = %s,
                                imagem_url = %s,
                                imagens_adicionais = %s,
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
                            produto["preco"],
                            produto["preco_promocional"],
                            peso,
                            produto.get("unidade", "UN"),
                            imagem_url,
                            Json(imagens) if imagens else None,
                            produto["categoria"],
                            produto["estoque"] > 0,
                            int(produto["estoque"]),
                            produto["ativo"],
                            str(produto["tiny_id"])
                        ))
                        atualizados += 1
                        logger.debug(f"✏️ Atualizado: {produto['nome']}")
                    else:
                        # Inserir
                        cursor.execute("""
                            INSERT INTO produtos_site (
                                tiny_id, nome, descricao,
                                preco, preco_promocional,
                                peso, unidade,
                                imagem_url, imagens_adicionais,
                                categoria,
                                estoque_disponivel, quantidade_estoque,
                                ativo, destaque,
                                sincronizado_em, created_at, updated_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                NOW(), NOW(), NOW()
                            )
                        """, (
                            str(produto["tiny_id"]),
                            produto["nome"],
                            produto["descricao"],
                            produto["preco"],
                            produto["preco_promocional"],
                            peso,
                            produto.get("unidade", "UN"),
                            imagem_url,
                            Json(imagens) if imagens else None,
                            produto["categoria"],
                            produto["estoque"] > 0,
                            int(produto["estoque"]),
                            produto["ativo"],
                            False  # destaque
                        ))
                        novos += 1
                        logger.debug(f"➕ Novo: {produto['nome']}")

                    conn.commit()

                # Rate limiting: aguardar antes do próximo
                if delay > 0 and idx < len(produtos):
                    await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"❌ Erro ao processar {produto.get('nome')}: {e}")
                erros += 1
                if conn:
                    conn.rollback()

        # Resumo final
        fim = datetime.now()
        duracao = (fim - inicio).total_seconds()

        logger.info("=" * 80)
        logger.info("✅ SINCRONIZAÇÃO CONCLUÍDA!")
        logger.info("=" * 80)
        logger.info(f"📊 Total processado: {len(produtos)}")
        logger.info(f"➕ Novos: {novos}")
        logger.info(f"✏️ Atualizados: {atualizados}")
        logger.info(f"⏭️ Pulados (dry-run): {pulados}")
        logger.info(f"❌ Erros: {erros}")
        logger.info(f"⏱️ Duração: {duracao:.2f}s ({duracao/60:.2f} min)")
        logger.info(f"⚡ Velocidade: {len(produtos)/duracao:.2f} produtos/segundo")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Erro na sincronização: {e}")
        raise

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


async def main():
    """Função principal com argumentos CLI"""
    parser = argparse.ArgumentParser(
        description="Sincronização completa de produtos Tiny → Supabase"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Sincroniza TODOS os produtos (não só os com 'site')"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay em segundos entre produtos (padrão: 0.5)"
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=100,
        help="Tamanho do lote (padrão: 100)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula sem gravar no banco"
    )

    args = parser.parse_args()

    await sincronizar_produtos(
        sync_all=args.all,
        delay=args.delay,
        batch_size=args.batch,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    asyncio.run(main())
