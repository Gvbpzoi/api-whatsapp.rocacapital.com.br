"""
Script de sincronização de produtos Tiny → Supabase
Usa o SyncService existente com filtro para produtos do site

Execução:
    python scripts/sync_produtos_site.py
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from loguru import logger
from dotenv import load_dotenv

from src.services.tiny_client import TinyAPIClient
from src.services.sync_service import SyncService

load_dotenv()


async def main():
    """Sincroniza produtos do site do Tiny para Supabase"""
    logger.info("🚀 Iniciando sincronização de produtos do site...")

    # Configurar cliente Tiny OAuth v3
    tiny_client = TinyAPIClient(
        client_id=os.getenv("TINY_CLIENT_ID"),
        client_secret=os.getenv("TINY_CLIENT_SECRET"),
        access_token=os.getenv("TINY_ACCESS_TOKEN"),
        refresh_token=os.getenv("TINY_REFRESH_TOKEN")
    )

    # Configurar sync service
    sync_service = SyncService(
        tiny_client=tiny_client,
        supabase_url=os.getenv("DATABASE_URL") or os.getenv("DIRECT_URL"),
        supabase_key=os.getenv("SUPABASE_KEY")
    )

    # Executar sincronização
    result = await sync_service.sync_products_from_tiny(full_sync=True)

    logger.info("=" * 60)
    logger.info(f"✅ Sincronização concluída!")
    logger.info(f"   Resultado: {result}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
