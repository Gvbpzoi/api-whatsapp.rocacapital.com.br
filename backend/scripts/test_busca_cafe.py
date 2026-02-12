#!/usr/bin/env python3
"""
Script para debugar busca de café especificamente
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

load_dotenv()

DROP_QS_KEYS = {"pgbouncer", "connection_limit"}

def sanitize_pg_dsn(database_url: str) -> str:
    u = urlparse(database_url)
    qs = dict(parse_qsl(u.query, keep_blank_values=True))
    for k in list(qs.keys()):
        if k in DROP_QS_KEYS:
            qs.pop(k, None)
    new_query = urlencode(qs, doseq=True)
    return urlunparse((u.scheme, u.netloc, u.path, u.params, new_query, u.fragment))

def main():
    database_url = os.getenv("DATABASE_URL") or os.getenv("DIRECT_URL")
    if not database_url:
        print("❌ DATABASE_URL não configurado")
        return

    database_url = sanitize_pg_dsn(database_url)

    try:
        conn = psycopg2.connect(database_url, sslmode="require")
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Contar total de produtos
        print("="*70)
        print("📊 ESTATÍSTICAS")
        print("="*70)
        cursor.execute("SELECT COUNT(*) as total FROM produtos_site WHERE ativo = TRUE")
        total = cursor.fetchone()["total"]
        print(f"Total de produtos ativos: {total}")

        # 2. Listar TODOS os produtos (apenas nomes)
        print("\n" + "="*70)
        print("📋 TODOS OS PRODUTOS NO BANCO")
        print("="*70)
        cursor.execute("""
            SELECT nome, categoria, estoque_disponivel, ativo
            FROM produtos_site
            ORDER BY nome
            LIMIT 50
        """)
        produtos = cursor.fetchall()
        for p in produtos:
            status = "✅" if p["estoque_disponivel"] else "❌"
            ativo = "🟢" if p["ativo"] else "🔴"
            print(f"{status} {ativo} {p['nome']} ({p['categoria']})")

        # 3. Buscar produtos que contêm "cafe" (qualquer variação)
        print("\n" + "="*70)
        print("🔍 TESTE 1: Busca com 'cafe' (sem acento)")
        print("="*70)
        cursor.execute("""
            SELECT nome, categoria, ativo, estoque_disponivel
            FROM produtos_site
            WHERE LOWER(nome) LIKE LOWER(%s)
            AND ativo = TRUE
            AND estoque_disponivel = TRUE
        """, ("%cafe%",))
        resultados = cursor.fetchall()
        print(f"Encontrados: {len(resultados)} produtos")
        for r in resultados:
            print(f"  - {r['nome']}")

        # 4. Buscar com "café" (com acento)
        print("\n" + "="*70)
        print("🔍 TESTE 2: Busca com 'café' (com acento)")
        print("="*70)
        cursor.execute("""
            SELECT nome, categoria, ativo, estoque_disponivel
            FROM produtos_site
            WHERE LOWER(nome) LIKE LOWER(%s)
            AND ativo = TRUE
            AND estoque_disponivel = TRUE
        """, ("%café%",))
        resultados = cursor.fetchall()
        print(f"Encontrados: {len(resultados)} produtos")
        for r in resultados:
            print(f"  - {r['nome']}")

        # 5. Buscar com unaccent (se disponível)
        print("\n" + "="*70)
        print("🔍 TESTE 3: Busca com UNACCENT (ignora acentos)")
        print("="*70)
        try:
            cursor.execute("""
                SELECT nome, categoria
                FROM produtos_site
                WHERE unaccent(LOWER(nome)) LIKE unaccent(LOWER(%s))
                AND ativo = TRUE
                AND estoque_disponivel = TRUE
            """, ("%cafe%",))
            resultados = cursor.fetchall()
            print(f"Encontrados: {len(resultados)} produtos")
            for r in resultados:
                print(f"  - {r['nome']}")
        except Exception as e:
            print(f"⚠️ UNACCENT não disponível: {e}")
            print("Solução: Instalar extensão unaccent no PostgreSQL")

        # 6. Verificar produtos inativos ou sem estoque
        print("\n" + "="*70)
        print("⚠️ PRODUTOS COM 'CAFÉ' INATIVOS OU SEM ESTOQUE")
        print("="*70)
        cursor.execute("""
            SELECT nome, ativo, estoque_disponivel, quantidade_estoque
            FROM produtos_site
            WHERE LOWER(nome) LIKE LOWER(%s)
            AND (ativo = FALSE OR estoque_disponivel = FALSE)
        """, ("%café%",))
        inativos = cursor.fetchall()
        if inativos:
            for p in inativos:
                print(f"  - {p['nome']}")
                print(f"    Ativo: {p['ativo']} | Estoque disponível: {p['estoque_disponivel']} | Qtd: {p['quantidade_estoque']}")
        else:
            print("  Nenhum produto inativo/sem estoque encontrado")

        cursor.close()
        conn.close()

        print("\n" + "="*70)
        print("✅ Testes concluídos")
        print("="*70)

    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
