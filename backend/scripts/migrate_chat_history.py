"""
Migração: Cria tabela chat_history para memória conversacional persistente.
Armazena mensagens em formato OpenAI para replay exato no agente.

Uso: python -m scripts.migrate_chat_history
"""
import os
import sys
import psycopg2
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

# Adicionar path do projeto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DROP_QS_KEYS = {"pgbouncer", "connection_limit"}


def sanitize_pg_dsn(database_url: str) -> str:
    u = urlparse(database_url)
    qs = dict(parse_qsl(u.query, keep_blank_values=True))
    for k in list(qs.keys()):
        if k in DROP_QS_KEYS:
            qs.pop(k, None)
    new_query = urlencode(qs, doseq=True)
    return urlunparse((u.scheme, u.netloc, u.path, u.params, new_query, u.fragment))


def run_migration():
    db_url = os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        print("Erro: DIRECT_URL ou DATABASE_URL nao configurado")
        sys.exit(1)

    db_url = sanitize_pg_dsn(db_url)

    print(f"Conectando ao banco...")
    conn = psycopg2.connect(db_url, sslmode="require")
    cursor = conn.cursor()

    print("Criando tabela chat_history...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id BIGSERIAL PRIMARY KEY,
            telefone TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            tool_calls JSONB,
            tool_call_id TEXT,
            name TEXT,
            media_type TEXT DEFAULT 'text',
            media_url TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    print("Criando indices...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_history_phone_time
        ON chat_history(telefone, created_at DESC);
    """)

    conn.commit()
    cursor.close()
    conn.close()

    print("Migracao concluida com sucesso!")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    run_migration()
