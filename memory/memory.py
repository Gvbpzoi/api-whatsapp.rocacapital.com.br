"""
Sistema de Memória - Roça Capital
CRUD básico para gerenciar conhecimento persistente
"""

import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


MEMORY_FILE = os.path.join(os.path.dirname(__file__), "MEMORY.md")
MEMORY_JSON = os.path.join(os.path.dirname(__file__), "memory_data.json")


def load_memory_data() -> Dict[str, Any]:
    """Carrega dados estruturados da memória"""
    if os.path.exists(MEMORY_JSON):
        with open(MEMORY_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "preferences": [],
        "learnings": [],
        "facts": [],
        "patterns": []
    }


def save_memory_data(data: Dict[str, Any]) -> None:
    """Salva dados estruturados"""
    with open(MEMORY_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def memory_write(
    content: str,
    type: str = "fact",  # fact, preference, learning, pattern
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Adiciona informação à memória.

    Args:
        content: Conteúdo a ser memorizado
        type: Tipo de memória
        tags: Tags para busca (ex: ["cliente:5531999999999", "queijos"])
        metadata: Metadados adicionais

    Returns:
        Entry criada

    Example:
        >>> memory_write(
        ...     "Cliente prefere queijos meia-cura",
        ...     type="preference",
        ...     tags=["cliente:5531999999999", "queijos"]
        ... )
    """
    data = load_memory_data()

    entry = {
        "id": f"{type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "content": content,
        "type": type,
        "tags": tags or [],
        "metadata": metadata or {},
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    # Adicionar ao tipo correspondente
    if type == "preference":
        data["preferences"].append(entry)
    elif type == "learning":
        data["learnings"].append(entry)
    elif type == "pattern":
        data["patterns"].append(entry)
    else:
        data["facts"].append(entry)

    save_memory_data(data)

    # Também adicionar ao MEMORY.md (para referência humana)
    _append_to_memory_md(entry)

    return entry


def memory_read(
    type: Optional[str] = None,
    tags: Optional[List[str]] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Lê memórias com filtros.

    Args:
        type: Filtrar por tipo
        tags: Filtrar por tags
        limit: Máximo de resultados

    Returns:
        Lista de entries

    Example:
        >>> memory_read(type="preference", tags=["cliente:5531999999999"])
    """
    data = load_memory_data()

    results = []

    # Coletar de todos os tipos se não especificado
    if type:
        if type == "preference":
            results = data["preferences"]
        elif type == "learning":
            results = data["learnings"]
        elif type == "pattern":
            results = data["patterns"]
        else:
            results = data["facts"]
    else:
        results = (
            data["preferences"] +
            data["learnings"] +
            data["patterns"] +
            data["facts"]
        )

    # Filtrar por tags se especificado
    if tags:
        results = [
            entry for entry in results
            if any(tag in entry.get("tags", []) for tag in tags)
        ]

    # Ordenar por data (mais recente primeiro)
    results.sort(key=lambda x: x["created_at"], reverse=True)

    return results[:limit]


def memory_update(entry_id: str, updates: Dict[str, Any]) -> bool:
    """
    Atualiza uma entry existente.

    Args:
        entry_id: ID da entry
        updates: Campos a atualizar

    Returns:
        True se atualizado, False se não encontrado
    """
    data = load_memory_data()

    for type_key in ["preferences", "learnings", "patterns", "facts"]:
        for i, entry in enumerate(data[type_key]):
            if entry["id"] == entry_id:
                data[type_key][i].update(updates)
                data[type_key][i]["updated_at"] = datetime.now().isoformat()
                save_memory_data(data)
                return True

    return False


def memory_delete(entry_id: str) -> bool:
    """
    Deleta uma entry.

    Args:
        entry_id: ID da entry

    Returns:
        True se deletado, False se não encontrado
    """
    data = load_memory_data()

    for type_key in ["preferences", "learnings", "patterns", "facts"]:
        for i, entry in enumerate(data[type_key]):
            if entry["id"] == entry_id:
                data[type_key].pop(i)
                save_memory_data(data)
                return True

    return False


def _append_to_memory_md(entry: Dict[str, Any]) -> None:
    """Adiciona entry ao MEMORY.md (para referência humana)"""
    with open(MEMORY_FILE, 'a', encoding='utf-8') as f:
        f.write(f"\n### {entry['type'].title()} - {entry['created_at']}\n")
        f.write(f"{entry['content']}\n")
        if entry['tags']:
            f.write(f"Tags: {', '.join(entry['tags'])}\n")


# CLI para testes
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso:")
        print("  python memory.py write <content> [type] [tags...]")
        print("  python memory.py read [type]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "write":
        content = sys.argv[2]
        type_ = sys.argv[3] if len(sys.argv) > 3 else "fact"
        tags = sys.argv[4:] if len(sys.argv) > 4 else []

        entry = memory_write(content, type_, tags)
        print(f"✅ Memória adicionada: {entry['id']}")

    elif command == "read":
        type_ = sys.argv[2] if len(sys.argv) > 2 else None

        results = memory_read(type_=type_)
        print(f"📚 Encontradas {len(results)} memórias:\n")

        for entry in results:
            print(f"[{entry['type']}] {entry['content']}")
            if entry['tags']:
                print(f"  Tags: {', '.join(entry['tags'])}")
            print()
