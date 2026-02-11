"""
Tool: products/search
Goal: 2 (Busca de Produtos)
Descrição: Busca produtos no Supabase usando full-text search
"""

import os
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


def execute(
    termo: str,
    limite: int = 10,
    supabase_client = None
) -> Dict[str, Any]:
    """
    Busca produtos no catálogo.

    Args:
        termo: Termo de busca (ex: "queijo", "cachaça")
        limite: Número máximo de resultados
        supabase_client: Cliente Supabase (opcional)

    Returns:
        {
            "status": "success",
            "produtos": [...],
            "total": int
        }

    Example:
        >>> result = execute("queijo canastra", limite=5)
        >>> print(result["total"])
        3
    """
    try:
        # Se não forneceu cliente, criar um
        if supabase_client is None:
            try:
                from supabase import create_client

                supabase_url = os.getenv("SUPABASE_URL")
                supabase_key = os.getenv("SUPABASE_KEY")

                if not supabase_url or not supabase_key:
                    return {
                        "status": "error",
                        "reason": "missing_config",
                        "message": "SUPABASE_URL e SUPABASE_KEY não configurados"
                    }

                supabase_client = create_client(supabase_url, supabase_key)
            except ImportError:
                return {
                    "status": "error",
                    "reason": "missing_dependency",
                    "message": "supabase-py não instalado. Execute: pip install supabase"
                }

        # Buscar produtos usando RPC (função do Supabase)
        try:
            result = supabase_client.rpc(
                "buscar_produtos",
                {"termo_busca": termo, "limite": limite}
            ).execute()

            produtos = result.data if result.data else []

            logger.info(f"✅ Busca '{termo}': {len(produtos)} produtos encontrados")

            return {
                "status": "success",
                "produtos": produtos,
                "total": len(produtos),
                "termo_busca": termo
            }

        except Exception as e:
            # Se RPC falhou, tentar busca direta na tabela
            logger.warning(f"RPC falhou, tentando busca direta: {e}")

            result = supabase_client.table("produtos").select("*").ilike("nome", f"%{termo}%").limit(limite).execute()

            produtos = result.data if result.data else []

            return {
                "status": "success",
                "produtos": produtos,
                "total": len(produtos),
                "termo_busca": termo
            }

    except Exception as e:
        logger.error(f"❌ Erro na busca: {e}")
        return {
            "status": "error",
            "reason": "search_failed",
            "message": str(e)
        }


def format_produtos_response(produtos: List[Dict]) -> str:
    """
    Formata lista de produtos em resposta amigável.

    Args:
        produtos: Lista de produtos

    Returns:
        Texto formatado
    """
    if not produtos:
        return "Nenhum produto encontrado. 😅"

    response = f"Encontrei {len(produtos)} produto{'s' if len(produtos) > 1 else ''}! ✨\n\n"

    for i, produto in enumerate(produtos, 1):
        nome = produto.get("nome", "Sem nome")
        preco = produto.get("preco", 0)
        estoque = produto.get("estoque_atual", 0)

        response += f"{i}️⃣ {nome}\n"
        response += f"   💰 R$ {preco:.2f}\n"
        response += f"   📦 {int(estoque)} {'unidade' if estoque == 1 else 'unidades'} disponíveis\n\n"

    response += "Qual te interessa? 😊"

    return response


# CLI para testes
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python search.py <termo> [limite]")
        print("\nExemplo:")
        print("  python search.py queijo 5")
        print("\nNota: Configure SUPABASE_URL e SUPABASE_KEY no .env")
        sys.exit(1)

    termo = sys.argv[1]
    limite = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    print(f"🔍 Buscando: '{termo}' (limite: {limite})\n")

    result = execute(termo, limite)

    print(f"Status: {result['status']}")

    if result['status'] == 'success':
        print(f"\n{format_produtos_response(result['produtos'])}")
    else:
        print(f"❌ Erro: {result.get('message', 'Desconhecido')}")
