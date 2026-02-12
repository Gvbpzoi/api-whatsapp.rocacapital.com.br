"""
Script para criar tabelas no Supabase (PostgreSQL)
"""
import os
import sys
from pathlib import Path

# Adicionar root ao path
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
from loguru import logger

# Carregar variáveis de ambiente
env_path = root / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    logger.warning("Arquivo .env não encontrado, usando .env.example")
    load_dotenv(root / ".env.example")


def get_connection():
    """Conecta no PostgreSQL usando DIRECT_URL"""
    database_url = os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL ou DIRECT_URL não configurado no .env")

    conn = psycopg2.connect(database_url)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def list_tables(conn):
    """Lista todas as tabelas existentes"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    tables = cursor.fetchall()
    cursor.close()
    return [table[0] for table in tables]


def create_produtos_site_table(conn):
    """Cria tabela produtos_site"""
    cursor = conn.cursor()

    logger.info("📦 Criando tabela produtos_site...")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos_site (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tiny_id text UNIQUE,
            nome text NOT NULL,
            descricao text,
            preco numeric(10,2),
            preco_promocional numeric(10,2),
            peso text,
            unidade text,
            imagem_url text,
            imagens_adicionais jsonb,
            link_produto text,
            categoria text,
            subcategoria text,
            tags text[],
            estoque_disponivel boolean DEFAULT true,
            quantidade_estoque integer DEFAULT 0,
            ativo boolean DEFAULT true,
            destaque boolean DEFAULT false,
            sincronizado_em timestamp DEFAULT now(),
            created_at timestamp DEFAULT now(),
            updated_at timestamp DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_produtos_site_categoria ON produtos_site(categoria);
        CREATE INDEX IF NOT EXISTS idx_produtos_site_ativo ON produtos_site(ativo);
        CREATE INDEX IF NOT EXISTS idx_produtos_site_tiny_id ON produtos_site(tiny_id);
    """)

    cursor.close()
    logger.info("✅ Tabela produtos_site criada")


def create_pedidos_table(conn):
    """Cria tabela pedidos"""
    cursor = conn.cursor()

    logger.info("📝 Criando tabela pedidos...")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            numero_pedido text UNIQUE,
            phone text NOT NULL,
            nome_cliente text,
            email_cliente text,
            endereco jsonb,
            items jsonb NOT NULL,
            subtotal numeric(10,2) NOT NULL,
            frete numeric(10,2) DEFAULT 0,
            desconto numeric(10,2) DEFAULT 0,
            total numeric(10,2) NOT NULL,
            status text NOT NULL DEFAULT 'carrinho',
            tiny_pedido_id text,
            link_pagamento text,
            observacoes text,
            created_at timestamp DEFAULT now(),
            updated_at timestamp DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_pedidos_phone ON pedidos(phone);
        CREATE INDEX IF NOT EXISTS idx_pedidos_status ON pedidos(status);
        CREATE INDEX IF NOT EXISTS idx_pedidos_tiny_id ON pedidos(tiny_pedido_id);
    """)

    cursor.close()
    logger.info("✅ Tabela pedidos criada")


def create_pagamentos_table(conn):
    """Cria tabela pagamentos"""
    cursor = conn.cursor()

    logger.info("💳 Criando tabela pagamentos...")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagamentos (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            pedido_id uuid REFERENCES pedidos(id) ON DELETE CASCADE,
            status text NOT NULL DEFAULT 'pendente',
            valor numeric(10,2) NOT NULL,
            metodo text,
            gateway text,
            gateway_id text,
            gateway_response jsonb,
            confirmado_em timestamp,
            created_at timestamp DEFAULT now(),
            updated_at timestamp DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_pagamentos_pedido_id ON pagamentos(pedido_id);
        CREATE INDEX IF NOT EXISTS idx_pagamentos_status ON pagamentos(status);
    """)

    cursor.close()
    logger.info("✅ Tabela pagamentos criada")


def create_rastreios_table(conn):
    """Cria tabela rastreios"""
    cursor = conn.cursor()

    logger.info("🚚 Criando tabela rastreios...")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rastreios (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            pedido_id uuid REFERENCES pedidos(id) ON DELETE CASCADE,
            codigo_rastreio text NOT NULL,
            transportadora text,
            status text,
            ultima_atualizacao timestamp,
            historico jsonb,
            notificado boolean DEFAULT false,
            created_at timestamp DEFAULT now(),
            updated_at timestamp DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_rastreios_pedido_id ON rastreios(pedido_id);
        CREATE INDEX IF NOT EXISTS idx_rastreios_codigo ON rastreios(codigo_rastreio);
    """)

    cursor.close()
    logger.info("✅ Tabela rastreios criada")


def main():
    """Executa setup completo do banco"""
    try:
        logger.info("🔌 Conectando no PostgreSQL...")
        conn = get_connection()
        logger.info("✅ Conectado!")

        # Listar tabelas existentes
        logger.info("\n📊 Tabelas existentes:")
        tables = list_tables(conn)
        for table in tables:
            logger.info(f"  - {table}")

        # Criar novas tabelas
        logger.info("\n🏗️  Criando tabelas necessárias...")
        create_produtos_site_table(conn)
        create_pedidos_table(conn)
        create_pagamentos_table(conn)
        create_rastreios_table(conn)

        # Listar tabelas após criação
        logger.info("\n📊 Tabelas após criação:")
        tables = list_tables(conn)
        for table in tables:
            logger.info(f"  - {table}")

        conn.close()
        logger.info("\n✅ Setup do banco concluído com sucesso!")

    except Exception as e:
        logger.error(f"❌ Erro no setup: {e}")
        raise


if __name__ == "__main__":
    main()
