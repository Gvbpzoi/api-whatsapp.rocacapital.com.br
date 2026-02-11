"""
Sistema de Busca em Memória - Roça Capital
Busca simples por palavras-chave
"""

from typing import List, Dict, Any
from memory import load_memory_data


def memory_search(
    query: str,
    type: str = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Busca na memória por palavras-chave.

    Args:
        query: Termo de busca (ex: "cliente:5531999999999 preferencias")
        type: Filtrar por tipo (opcional)
        limit: Máximo de resultados

    Returns:
        Lista de entries relevantes

    Example:
        >>> results = memory_search("queijo")
        >>> results = memory_search("cliente:5531999999999 preferencias")
    """
    data = load_memory_data()

    # Normalizar query
    query_lower = query.lower()
    query_terms = query_lower.split()

    results = []

    # Coletar entries
    all_entries = []
    if type:
        all_entries = data.get(f"{type}s", [])  # preferences, learnings, etc
    else:
        all_entries = (
            data["preferences"] +
            data["learnings"] +
            data["patterns"] +
            data["facts"]
        )

    # Buscar
    for entry in all_entries:
        score = 0

        # Buscar em content
        content_lower = entry["content"].lower()
        for term in query_terms:
            if term in content_lower:
                score += 2

        # Buscar em tags
        for tag in entry.get("tags", []):
            tag_lower = tag.lower()
            for term in query_terms:
                if term in tag_lower:
                    score += 3  # Tags têm peso maior

        if score > 0:
            results.append({
                **entry,
                "score": score
            })

    # Ordenar por score (maior primeiro)
    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:limit]


def hybrid_search(
    query: str,
    tags: List[str] = None,
    type: str = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Busca híbrida: query + tags + type.

    Args:
        query: Termo de busca
        tags: Tags específicas
        type: Tipo específico
        limit: Máximo de resultados

    Returns:
        Lista de entries relevantes

    Example:
        >>> results = hybrid_search(
        ...     query="queijo",
        ...     tags=["cliente:5531999999999"],
        ...     type="preference"
        ... )
    """
    # Primeiro: busca básica
    results = memory_search(query, type, limit * 2)  # Pegar mais para filtrar

    # Filtrar por tags se especificado
    if tags:
        filtered = []
        for entry in results:
            entry_tags = entry.get("tags", [])
            if any(tag in entry_tags for tag in tags):
                # Boost score se tag match
                entry["score"] += 5
                filtered.append(entry)

        # Re-ordenar
        filtered.sort(key=lambda x: x["score"], reverse=True)
        results = filtered

    return results[:limit]


# CLI para testes
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso:")
        print("  python search.py <query> [limit]")
        print("\nExemplos:")
        print("  python search.py queijo")
        print("  python search.py 'cliente:5531999999999 preferencias' 10")
        sys.exit(1)

    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    results = memory_search(query, limit=limit)

    print(f"🔍 Busca: '{query}'")
    print(f"📊 Encontrados: {len(results)} resultados\n")

    for i, entry in enumerate(results, 1):
        print(f"{i}. [{entry['type']}] {entry['content']}")
        print(f"   Score: {entry['score']}")
        if entry.get('tags'):
            print(f"   Tags: {', '.join(entry['tags'])}")
        print()
