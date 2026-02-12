#!/usr/bin/env python3
"""
Script para debugar campos retornados pela API Tiny
"""
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from loguru import logger
from dotenv import load_dotenv
from src.services.tiny_products_client import get_tiny_products_client
import json

load_dotenv()


async def main():
    """Busca 1 produto e mostra TODOS os campos"""
    client = get_tiny_products_client()

    # Buscar lista de produtos
    print("🔍 Buscando lista de produtos...")
    produtos = await client.listar_produtos(limite=1, filtrar_site=True)

    if not produtos:
        print("❌ Nenhum produto encontrado")
        return

    primeiro = produtos[0]
    produto_id = primeiro.get("tiny_id")

    print(f"\n📦 Buscando detalhes completos do produto ID: {produto_id}")
    print("=" * 80)

    # Buscar produto completo
    produto_completo = await client.obter_produto(str(produto_id))

    if not produto_completo:
        print("❌ Erro ao buscar produto completo")
        return

    # Mostrar TODOS os campos
    print(f"\n✅ CAMPOS RETORNADOS PELA API TINY:")
    print("=" * 80)
    print(json.dumps(produto_completo, indent=2, ensure_ascii=False))
    print("=" * 80)

    # Destacar campos importantes
    print(f"\n🔑 CAMPOS-CHAVE:")
    print(f"   ID: {produto_completo.get('id')}")
    print(f"   Nome: {produto_completo.get('nome')}")
    print(f"   Descrição: {produto_completo.get('descricao', '')[:100]}...")
    print(f"   Descrição Complementar: {produto_completo.get('descricao_complementar', '')[:100]}...")
    print(f"   URL Produto: {produto_completo.get('url_produto', 'N/A')}")
    print(f"   Link Produto: {produto_completo.get('link_produto', 'N/A')}")
    print(f"   Observações: {produto_completo.get('observacoes', '')[:100]}...")

    # Listar TODOS os campos disponíveis
    print(f"\n📋 TODOS OS CAMPOS ({len(produto_completo)} total):")
    for key in sorted(produto_completo.keys()):
        value = produto_completo[key]
        if isinstance(value, str) and len(value) > 50:
            print(f"   - {key}: {value[:50]}... (truncado)")
        else:
            print(f"   - {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
