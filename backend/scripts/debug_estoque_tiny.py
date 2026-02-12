#!/usr/bin/env python3
"""
Debug: Investigar como o estoque está sendo retornado pela API Tiny
"""
import sys
from pathlib import Path
import asyncio

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
from src.services.tiny_products_client import get_tiny_products_client
from loguru import logger

load_dotenv()

async def main():
    print("="*70)
    print("🔍 DEBUG: ESTOQUE DA API TINY")
    print("="*70)

    client = get_tiny_products_client()

    # 1. Listar produtos do site
    print("\n1️⃣ Listando produtos com 'site' nas observações...")
    produtos = await client.listar_produtos(limite=50, filtrar_site=True)

    print(f"\n📦 Total de produtos encontrados: {len(produtos)}")

    # 2. Filtrar produtos de café
    produtos_cafe = [p for p in produtos if "cafe" in p["nome"].lower() or "café" in p["nome"].lower()]

    print(f"☕ Produtos de café encontrados: {len(produtos_cafe)}")

    if not produtos_cafe:
        print("❌ Nenhum produto de café encontrado!")
        return

    # 3. Analisar estoque de cada produto
    print("\n" + "="*70)
    print("📊 ANÁLISE DE ESTOQUE")
    print("="*70)

    for produto in produtos_cafe[:10]:  # Primeiros 10
        print(f"\n🔸 {produto['nome']}")
        print(f"   Tiny ID: {produto['tiny_id']}")
        print(f"   Código: {produto['codigo']}")

        # Obter detalhes completos do produto
        print(f"\n   📥 Buscando detalhes completos do produto {produto['tiny_id']}...")
        produto_completo = await client.obter_produto(produto['tiny_id'])

        if not produto_completo:
            print(f"   ❌ Não foi possível obter detalhes do produto")
            continue

        # Campos relacionados ao estoque
        campos_estoque = [
            "estoque",
            "estoque_atual",
            "saldo",
            "quantidade",
            "qtd_estoque",
            "estoque_minimo",
            "estoque_maximo",
            "situacao",
            "ativo"
        ]

        print("\n   📋 Campos de estoque retornados pela API:")
        for campo in campos_estoque:
            valor = produto_completo.get(campo)
            if valor is not None:
                print(f"      {campo}: {valor} (tipo: {type(valor).__name__})")

        # Verificar estrutura de estoque (pode vir como objeto)
        if "estoque_atual" in produto_completo and isinstance(produto_completo["estoque_atual"], dict):
            print("\n   🔍 estoque_atual é um objeto:")
            for k, v in produto_completo["estoque_atual"].items():
                print(f"      {k}: {v} (tipo: {type(v).__name__})")

        # Valor normalizado
        estoque_normalizado = produto.get("estoque", 0)
        print(f"\n   ✅ Estoque normalizado: {estoque_normalizado}")
        print(f"   🔢 Tipo do estoque: {type(estoque_normalizado).__name__}")

        # Verificar se é string com vírgula
        estoque_raw = produto_completo.get("estoque", "")
        if isinstance(estoque_raw, str):
            print(f"   ⚠️ ATENÇÃO: Estoque veio como STRING: '{estoque_raw}'")
            if "," in estoque_raw:
                print(f"   🔴 PROBLEMA: Vírgula detectada! Precisa converter para ponto")
                try:
                    estoque_corrigido = float(estoque_raw.replace(",", "."))
                    print(f"   ✅ Estoque corrigido: {estoque_corrigido}")
                except ValueError as e:
                    print(f"   ❌ Erro ao converter: {e}")

        print("\n" + "-"*70)

    # 4. Resumo
    print("\n" + "="*70)
    print("📊 RESUMO")
    print("="*70)

    estoques = [p.get("estoque", 0) for p in produtos_cafe]
    estoque_total = sum(estoques)
    estoque_zerado = sum(1 for e in estoques if e == 0)
    estoque_positivo = sum(1 for e in estoques if e > 0)

    print(f"Total de produtos café: {len(produtos_cafe)}")
    print(f"Com estoque > 0: {estoque_positivo}")
    print(f"Com estoque = 0: {estoque_zerado}")
    print(f"Estoque total: {estoque_total}")

    if estoque_zerado == len(produtos_cafe):
        print("\n🔴 PROBLEMA CONFIRMADO: Todos os produtos têm estoque = 0")
        print("   Possíveis causas:")
        print("   1. API retorna estoque como string com vírgula (ex: '10,5')")
        print("   2. API retorna estoque em campo diferente (ex: 'saldo', 'estoque_atual')")
        print("   3. API retorna estoque negativo sendo convertido para 0")
        print("   4. Campo 'estoque' está vazio ou null na API")

    print("\n" + "="*70)

if __name__ == "__main__":
    asyncio.run(main())
