#!/usr/bin/env python3
"""
Script de teste para integração Supabase + Bot WhatsApp
Testa busca de produtos reais
"""
import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from loguru import logger
from dotenv import load_dotenv
from src.services.supabase_produtos import get_supabase_produtos
from src.orchestrator.tools_helper import get_tools_helper

# Carregar variáveis de ambiente
load_dotenv()


def test_busca_direta():
    """Teste 1: Busca direta no Supabase"""
    print("=" * 70)
    print("🧪 TESTE 1: Busca Direta no Supabase")
    print("=" * 70)

    service = get_supabase_produtos()

    # Teste 1.1: Buscar "cafe"
    print("\n1.1. Buscar 'cafe':")
    produtos = service.buscar_produtos(termo="cafe", limite=5)
    print(f"   Encontrados: {len(produtos)} produtos")
    for p in produtos:
        preco = p.get("preco_promocional") or p.get("preco", 0)
        print(f"   - {p['nome']} | R$ {preco:.2f} | Estoque: {p.get('quantidade_estoque', 0)}")

    # Teste 1.2: Buscar "queijo"
    print("\n1.2. Buscar 'queijo':")
    produtos = service.buscar_produtos(termo="queijo", limite=5)
    print(f"   Encontrados: {len(produtos)} produtos")
    for p in produtos:
        preco = p.get("preco_promocional") or p.get("preco", 0)
        print(f"   - {p['nome']} | R$ {preco:.2f}")

    # Teste 1.3: Buscar "azeite"
    print("\n1.3. Buscar 'azeite':")
    produtos = service.buscar_produtos(termo="azeite", limite=5)
    print(f"   Encontrados: {len(produtos)} produtos")
    for p in produtos:
        preco = p.get("preco_promocional") or p.get("preco", 0)
        print(f"   - {p['nome']} | R$ {preco:.2f}")

    # Teste 1.4: Listar categorias
    print("\n1.4. Listar categorias:")
    categorias = service.listar_categorias()
    print(f"   Total: {len(categorias)} categorias")
    print(f"   Categorias: {', '.join(categorias[:10])}")

    print("\n" + "=" * 70)


def test_tools_helper():
    """Teste 2: Busca via ToolsHelper (como o bot usa)"""
    print("\n" + "=" * 70)
    print("🧪 TESTE 2: Busca via ToolsHelper (Bot WhatsApp)")
    print("=" * 70)

    tools = get_tools_helper()

    # Teste 2.1: Buscar "cafe"
    print("\n2.1. Buscar 'cafe' (como bot WhatsApp):")
    result = tools.buscar_produtos("cafe", limite=3)
    print(f"   Status: {result['status']}")
    print(f"   Source: {result.get('source', 'unknown')}")
    print(f"   Total: {result.get('total', 0)} produtos")

    if result['status'] == 'success' and result.get('produtos'):
        for p in result['produtos']:
            preco = p.get("preco_promocional") or p.get("preco", 0)
            print(f"   - {p['nome']} | R$ {preco:.2f}")

    # Teste 2.2: Buscar "bacon"
    print("\n2.2. Buscar 'bacon':")
    result = tools.buscar_produtos("bacon", limite=3)
    print(f"   Status: {result['status']}")
    print(f"   Source: {result.get('source', 'unknown')}")
    print(f"   Total: {result.get('total', 0)} produtos")

    if result['status'] == 'success' and result.get('produtos'):
        for p in result['produtos']:
            preco = p.get("preco_promocional") or p.get("preco", 0)
            print(f"   - {p['nome']} | R$ {preco:.2f}")

    # Teste 2.3: Adicionar ao carrinho
    print("\n2.3. Testar adicionar ao carrinho:")
    if result['status'] == 'success' and result.get('produtos'):
        primeiro_produto = result['produtos'][0]
        produto_id = str(primeiro_produto.get('id'))

        print(f"   Adicionando: {primeiro_produto['nome']}")
        add_result = tools.adicionar_carrinho("5531999999999", produto_id, quantidade=1)
        print(f"   Status: {add_result['status']}")
        if add_result['status'] == 'success':
            print(f"   Total itens no carrinho: {add_result.get('total_itens', 0)}")

    print("\n" + "=" * 70)


def test_estatisticas():
    """Teste 3: Estatísticas gerais"""
    print("\n" + "=" * 70)
    print("🧪 TESTE 3: Estatísticas do Catálogo")
    print("=" * 70)

    service = get_supabase_produtos()

    # Total de produtos
    print("\n3.1. Total de produtos disponíveis:")
    todos = service.buscar_produtos(termo="", limite=1000, apenas_disponiveis=True)
    print(f"   Total: {len(todos)} produtos")

    # Produtos em destaque
    print("\n3.2. Produtos em destaque:")
    destaques = service.buscar_produtos_em_destaque(limite=5)
    print(f"   Total: {len(destaques)} produtos")
    for p in destaques:
        print(f"   - {p['nome']}")

    # Categorias
    print("\n3.3. Categorias:")
    categorias = service.listar_categorias()
    print(f"   Total: {len(categorias)} categorias")
    for cat in categorias:
        produtos_cat = service.buscar_produtos(categoria=cat, limite=1000)
        print(f"   - {cat}: {len(produtos_cat)} produtos")

    print("\n" + "=" * 70)


def main():
    """Executa todos os testes"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "🧪 TESTE DE INTEGRAÇÃO SUPABASE" + " " * 20 + "║")
    print("║" + " " * 15 + "Bot WhatsApp + Produtos Reais" + " " * 21 + "║")
    print("╚" + "=" * 68 + "╝")
    print("\n")

    try:
        # Teste 1: Busca direta
        test_busca_direta()

        # Teste 2: ToolsHelper
        test_tools_helper()

        # Teste 3: Estatísticas
        test_estatisticas()

        print("\n")
        print("╔" + "=" * 68 + "╗")
        print("║" + " " * 20 + "✅ TODOS OS TESTES PASSARAM!" + " " * 21 + "║")
        print("╚" + "=" * 68 + "╝")
        print("\n")

    except Exception as e:
        print(f"\n❌ ERRO NOS TESTES: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
