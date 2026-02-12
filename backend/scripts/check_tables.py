#!/usr/bin/env python3
"""
Script para verificar quais tabelas existem no Supabase
"""
import os
import psycopg2
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


def main():
    # Pegar URL do ambiente
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL não configurado")
        return

    # Sanitizar
    database_url = sanitize_pg_dsn(database_url)

    try:
        # Conectar
        conn = psycopg2.connect(database_url, sslmode="require")
        cursor = conn.cursor()

        # Listar tabelas
        cursor.execute("""
            SELECT table_schema, table_name,
                   (SELECT COUNT(*) FROM information_schema.columns c
                    WHERE c.table_schema = t.table_schema
                    AND c.table_name = t.table_name) as num_colunas
            FROM information_schema.tables t
            WHERE table_type = 'BASE TABLE'
            AND table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name
        """)

        tables = cursor.fetchall()

        print("=" * 70)
        print("📊 TABELAS NO SUPABASE")
        print("=" * 70)

        if not tables:
            print("⚠️ Nenhuma tabela encontrada!")
        else:
            for schema, table, num_cols in tables:
                print(f"  {schema}.{table:<30} ({num_cols} colunas)")

        print("=" * 70)
        print(f"Total: {len(tables)} tabelas")
        print("=" * 70)

        # Verificar especificamente a tabela produtos
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'produtos'
            ORDER BY ordinal_position
        """)

        produtos_cols = cursor.fetchall()

        if produtos_cols:
            print("\n✅ Tabela 'produtos' existe!")
            print("=" * 70)
            print("Colunas:")
            for col_name, data_type, nullable in produtos_cols:
                null_str = "NULL" if nullable == "YES" else "NOT NULL"
                print(f"  - {col_name:<30} {data_type:<20} {null_str}")
            print("=" * 70)
        else:
            print("\n❌ Tabela 'produtos' NÃO existe no schema 'public'")
            print("   Você precisa executar o supabase_schema.sql")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ Erro: {e}")


if __name__ == "__main__":
    main()
