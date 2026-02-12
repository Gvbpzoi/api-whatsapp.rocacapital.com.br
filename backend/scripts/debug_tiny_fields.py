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

    # Mostrar TODOS os campos retornados
    print(f"\n✅ RESPOSTA COMPLETA DA API (produto.obter.php):")
    print("=" * 80)
    print(json.dumps(produto_completo, indent=2, ensure_ascii=False))
    print("=" * 80)

    # Listar TODOS os campos disponíveis
    print(f"\n📋 CAMPOS DISPONÍVEIS ({len(produto_completo)} total):")
    print("=" * 80)
    for key in sorted(produto_completo.keys()):
        value = produto_completo[key]
        if isinstance(value, str):
            if len(value) > 100:
                print(f"   {key:<30} = {value[:100]}... (texto longo)")
            else:
                print(f"   {key:<30} = {value}")
        elif isinstance(value, (list, dict)):
            print(f"   {key:<30} = {type(value).__name__} com {len(value)} items")
        else:
            print(f"   {key:<30} = {value}")
    print("=" * 80)

    # Destacar campos importantes
    print(f"\n🔑 CAMPOS CRÍTICOS PARA O BOT:")
    print("=" * 80)
    print(f"   ID: {produto_completo.get('id')}")
    print(f"   Código: {produto_completo.get('codigo')}")
    print(f"   Nome: {produto_completo.get('nome')}")
    print(f"   ")
    print(f"   📝 DESCRIÇÕES:")
    desc = produto_completo.get('descricao', '')
    print(f"   - descricao: {desc[:150] if desc else 'VAZIO'}...")
    desc_comp = produto_completo.get('descricao_complementar', '')
    print(f"   - descricao_complementar: {desc_comp[:150] if desc_comp else 'VAZIO'}...")
    obs = produto_completo.get('observacoes', '') or produto_completo.get('observacao', '') or produto_completo.get('obs', '')
    print(f"   - observacoes: {obs[:150] if obs else 'VAZIO'}...")
    print(f"   ")
    print(f"   🔗 URLS:")
    print(f"   - url_produto: {produto_completo.get('url_produto', 'N/A')}")
    print(f"   - link_produto: {produto_completo.get('link_produto', 'N/A')}")
    print(f"   ")
    print(f"   📸 IMAGENS:")
    imagens = produto_completo.get('imagens', [])
    if isinstance(imagens, list) and imagens:
        print(f"   - Total: {len(imagens)} imagens")
        for i, img in enumerate(imagens[:3], 1):
            if isinstance(img, dict):
                print(f"   - Imagem {i}: {img.get('url', 'N/A')}")
    else:
        print(f"   - Imagens: VAZIO ou não é array")
    print("=" * 80)

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
