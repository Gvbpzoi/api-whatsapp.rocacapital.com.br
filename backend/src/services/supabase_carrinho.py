"""
Serviço para gerenciar carrinhos persistentes no Supabase
Garante que carrinhos sobrevivem a redeploys
"""

import os
import json
from typing import Dict, List, Optional, Any
from decimal import Decimal
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger


DROP_QS_KEYS = {"pgbouncer", "connection_limit"}


def sanitize_pg_dsn(database_url: str) -> str:
    """Remove parâmetros incompatíveis com psycopg2"""
    u = urlparse(database_url)
    qs = dict(parse_qsl(u.query, keep_blank_values=True))
    for k in list(qs.keys()):
        if k in DROP_QS_KEYS:
            qs.pop(k, None)
    new_query = urlencode(qs, doseq=True)
    return urlunparse((u.scheme, u.netloc, u.path, u.params, new_query, u.fragment))


class SupabaseCarrinho:
    """Gerenciador de carrinhos persistentes no Supabase"""

    def __init__(self):
        """Inicializa conexão com Supabase"""
        # Tentar variáveis de ambiente na ordem de prioridade:
        # 1. DIRECT_URL (conexão direta, melhor para transações)
        # 2. DATABASE_URL (com pgbouncer, será sanitizado)
        self.db_url = os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL")
        self.connection = None
        
        if self.db_url:
            try:
                # Sanitizar URL para remover parâmetros incompatíveis com psycopg2
                sanitized_url = sanitize_pg_dsn(self.db_url)
                self.connection = psycopg2.connect(sanitized_url, sslmode="require")
                logger.info("✅ Conectado ao Supabase para carrinhos persistentes")
            except Exception as e:
                logger.error(f"❌ Erro ao conectar Supabase: {e}")
                self.connection = None
        else:
            logger.warning("⚠️ Nenhuma variável de DB configurada (DIRECT_URL ou DATABASE_URL), usando carrinhos em memória")

    def _execute(self, query: str, params: tuple = None, fetch: bool = True) -> Optional[List[Dict]]:
        """Executa query no banco"""
        if not self.connection:
            return None

        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                
                if fetch:
                    result = cursor.fetchall()
                    # Converter RealDictRow para dict simples
                    return [dict(row) for row in result] if result else []
                else:
                    self.connection.commit()
                    return []
        except Exception as e:
            logger.error(f"❌ Erro ao executar query: {e}")
            self.connection.rollback()
            return None

    def adicionar_item(
        self,
        telefone: str,
        produto_id: str,
        produto_nome: str,
        preco_unitario: float,
        quantidade: int
    ) -> Dict[str, Any]:
        """
        Adiciona ou atualiza item no carrinho.
        Se item já existe, soma a quantidade.
        
        Returns:
            Dict com status da operação
        """
        try:
            subtotal = preco_unitario * quantidade

            # Verificar se produto já está no carrinho
            query = """
                SELECT quantidade, preco_unitario
                FROM carrinhos
                WHERE telefone = %s AND produto_id = %s::uuid
            """
            result = self._execute(query, (telefone, produto_id))

            if result and len(result) > 0:
                # Item já existe: atualizar quantidade
                quantidade_atual = result[0]["quantidade"]
                nova_quantidade = quantidade_atual + quantidade
                novo_subtotal = preco_unitario * nova_quantidade

                update_query = """
                    UPDATE carrinhos
                    SET quantidade = %s,
                        subtotal = %s,
                        atualizado_em = NOW()
                    WHERE telefone = %s AND produto_id = %s::uuid
                """
                self._execute(
                    update_query,
                    (nova_quantidade, novo_subtotal, telefone, produto_id),
                    fetch=False
                )
                
                logger.info(f"✅ Quantidade atualizada: {produto_nome} -> {nova_quantidade} un")
                return {
                    "status": "updated",
                    "quantidade_anterior": quantidade_atual,
                    "quantidade_nova": nova_quantidade
                }
            else:
                # Item novo: inserir
                insert_query = """
                    INSERT INTO carrinhos (telefone, produto_id, produto_nome, preco_unitario, quantidade, subtotal)
                    VALUES (%s, %s::uuid, %s, %s, %s, %s)
                """
                self._execute(
                    insert_query,
                    (telefone, produto_id, produto_nome, preco_unitario, quantidade, subtotal),
                    fetch=False
                )
                
                logger.info(f"✅ Item adicionado ao carrinho: {produto_nome}")
                return {"status": "added"}

        except Exception as e:
            logger.error(f"❌ Erro ao adicionar item: {e}")
            return {"status": "error", "message": str(e)}

    def obter_carrinho(self, telefone: str) -> List[Dict[str, Any]]:
        """
        Obtém todos os itens do carrinho de um cliente.
        
        Returns:
            Lista de itens do carrinho
        """
        try:
            query = """
                SELECT produto_id, produto_nome, preco_unitario, quantidade, subtotal
                FROM carrinhos
                WHERE telefone = %s
                ORDER BY criado_em ASC
            """
            result = self._execute(query, (telefone,))
            
            if result:
                # Converter Decimal para float para JSON
                items = []
                for item in result:
                    items.append({
                        "produto_id": str(item["produto_id"]),
                        "nome": item["produto_nome"],
                        "preco_unitario": float(item["preco_unitario"]),
                        "quantidade": item["quantidade"],
                        "subtotal": float(item["subtotal"])
                    })
                return items
            
            return []

        except Exception as e:
            logger.error(f"❌ Erro ao obter carrinho: {e}")
            return []

    def calcular_total(self, telefone: str) -> float:
        """Calcula total do carrinho"""
        try:
            query = """
                SELECT SUM(subtotal) as total
                FROM carrinhos
                WHERE telefone = %s
            """
            result = self._execute(query, (telefone,))
            
            if result and result[0]["total"]:
                return float(result[0]["total"])
            
            return 0.0

        except Exception as e:
            logger.error(f"❌ Erro ao calcular total: {e}")
            return 0.0

    def limpar_carrinho(self, telefone: str) -> bool:
        """Limpa todos os itens do carrinho"""
        try:
            query = "DELETE FROM carrinhos WHERE telefone = %s"
            self._execute(query, (telefone,), fetch=False)
            logger.info(f"🗑️ Carrinho limpo para {telefone[:8]}...")
            return True

        except Exception as e:
            logger.error(f"❌ Erro ao limpar carrinho: {e}")
            return False

    def remover_item(self, telefone: str, produto_id: str) -> bool:
        """Remove item específico do carrinho"""
        try:
            query = "DELETE FROM carrinhos WHERE telefone = %s AND produto_id = %s::uuid"
            self._execute(query, (telefone, produto_id), fetch=False)
            logger.info(f"🗑️ Item removido do carrinho: {produto_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Erro ao remover item: {e}")
            return False

    def atualizar_quantidade(self, telefone: str, produto_id: str, nova_quantidade: int) -> bool:
        """Atualiza quantidade de um item no carrinho"""
        try:
            query = """
                UPDATE carrinhos
                SET quantidade = %s,
                    subtotal = preco_unitario * %s,
                    atualizado_em = NOW()
                WHERE telefone = %s AND produto_id = %s::uuid
            """
            self._execute(query, (nova_quantidade, nova_quantidade, telefone, produto_id), fetch=False)
            logger.info(f"✏️ Quantidade atualizada: {produto_id} -> {nova_quantidade}")
            return True

        except Exception as e:
            logger.error(f"❌ Erro ao atualizar quantidade: {e}")
            return False

    def contar_itens(self, telefone: str) -> int:
        """Conta número de tipos de itens diferentes no carrinho"""
        try:
            query = "SELECT COUNT(*) as count FROM carrinhos WHERE telefone = %s"
            result = self._execute(query, (telefone,))

            if result:
                return result[0]["count"]

            return 0

        except Exception as e:
            logger.error(f"❌ Erro ao contar itens: {e}")
            return 0

    # ==================== Frete Confirmado ====================

    def salvar_frete(self, telefone: str, tipo_frete: str, valor_frete: float, prazo_entrega: str) -> bool:
        """Salva ou atualiza o frete confirmado para o cliente"""
        try:
            query = """
                INSERT INTO frete_confirmado (telefone, tipo_frete, valor_frete, prazo_entrega, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (telefone)
                DO UPDATE SET
                    tipo_frete = EXCLUDED.tipo_frete,
                    valor_frete = EXCLUDED.valor_frete,
                    prazo_entrega = EXCLUDED.prazo_entrega,
                    updated_at = NOW()
            """
            self._execute(query, (telefone, tipo_frete, valor_frete, prazo_entrega), fetch=False)
            logger.info(f"✅ Frete salvo: {tipo_frete} R$ {valor_frete:.2f} para {telefone[:8]}...")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao salvar frete: {e}")
            return False

    def obter_frete(self, telefone: str) -> Optional[Dict]:
        """Obtém o frete confirmado do cliente"""
        try:
            query = """
                SELECT tipo_frete, valor_frete, prazo_entrega
                FROM frete_confirmado
                WHERE telefone = %s
            """
            result = self._execute(query, (telefone,))
            if result and len(result) > 0:
                return {
                    "tipo_frete": result[0]["tipo_frete"],
                    "valor_frete": float(result[0]["valor_frete"]),
                    "prazo_entrega": result[0]["prazo_entrega"],
                }
            return None
        except Exception as e:
            logger.error(f"❌ Erro ao obter frete: {e}")
            return None

    def limpar_frete(self, telefone: str) -> bool:
        """Remove o frete confirmado do cliente"""
        try:
            query = "DELETE FROM frete_confirmado WHERE telefone = %s"
            self._execute(query, (telefone,), fetch=False)
            logger.info(f"🗑️ Frete limpo para {telefone[:8]}...")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao limpar frete: {e}")
            return False


# Singleton global
_carrinho_service: Optional[SupabaseCarrinho] = None


def get_supabase_carrinho() -> SupabaseCarrinho:
    """
    Retorna instância singleton do serviço de carrinhos.
    
    Returns:
        SupabaseCarrinho instance
    """
    global _carrinho_service
    
    if _carrinho_service is None:
        _carrinho_service = SupabaseCarrinho()
    
    return _carrinho_service


# Para testes
if __name__ == "__main__":
    print("🧪 Testando SupabaseCarrinho\n")
    
    carrinho = SupabaseCarrinho()
    telefone_teste = "5531999999999"
    
    # Teste 1: Adicionar item
    print("1️⃣ Adicionar item:")
    result = carrinho.adicionar_item(
        telefone=telefone_teste,
        produto_id="11111111-1111-1111-1111-111111111111",
        produto_nome="Queijo Teste",
        preco_unitario=45.00,
        quantidade=2
    )
    print(f"   Status: {result['status']}\n")
    
    # Teste 2: Obter carrinho
    print("2️⃣ Obter carrinho:")
    items = carrinho.obter_carrinho(telefone_teste)
    print(f"   Itens: {len(items)}")
    for item in items:
        print(f"   - {item['nome']}: {item['quantidade']}x R$ {item['preco_unitario']}\n")
    
    # Teste 3: Calcular total
    print("3️⃣ Calcular total:")
    total = carrinho.calcular_total(telefone_teste)
    print(f"   Total: R$ {total:.2f}\n")
    
    # Teste 4: Limpar carrinho
    print("4️⃣ Limpar carrinho:")
    carrinho.limpar_carrinho(telefone_teste)
    print("   ✅ Carrinho limpo\n")
    
    print("✅ Todos os testes concluídos!")
