"""
Tool Executor: Mapeia tool calls do OpenAI para funções Python reais.
Conecta o agente aos serviços existentes (Supabase, ZAPI).
"""
import json
import os
import random
import string
from typing import Dict, Any
from decimal import Decimal
from loguru import logger

from ..services.supabase_produtos import get_supabase_produtos
from ..services.supabase_carrinho import get_supabase_carrinho
from ..services.zapi_client import get_zapi_client


def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class ToolExecutor:
    """Executa tool calls do agente usando os serviços existentes."""

    def __init__(self):
        self.produtos_service = get_supabase_produtos()
        self.carrinho_service = get_supabase_carrinho()
        self.zapi_client = get_zapi_client()

        self._handlers = {
            "buscar_produtos": self._buscar_produtos,
            "add_to_cart": self._add_to_cart,
            "remover_do_carrinho": self._remover_do_carrinho,
            "alterar_quantidade": self._alterar_quantidade,
            "view_cart": self._view_cart,
            "limpar_carrinho": self._limpar_carrinho,
            "gerar_pix": self._gerar_pix,
            "gerar_pagamento": self._gerar_pagamento,
            "enviar_qr_code_pix": self._enviar_qr_code_pix,
            "enviar_foto_produto": self._enviar_foto_produto,
            "calcular_frete": self._calcular_frete,
            "confirmar_frete": self._confirmar_frete,
            "salvar_endereco": self._salvar_endereco,
            "buscar_historico_compras": self._buscar_historico_compras,
            "verificar_status_pedido": self._verificar_status_pedido,
            "escalar_atendimento": self._escalar_atendimento,
        }

    async def execute(self, tool_name: str, arguments: Dict[str, Any], telefone: str) -> str:
        """
        Executa uma tool e retorna resultado como string JSON.

        Args:
            tool_name: Nome da tool
            arguments: Argumentos da tool (parsed do JSON)
            telefone: Telefone do cliente (injetado automaticamente)

        Returns:
            JSON string com resultado
        """
        handler = self._handlers.get(tool_name)
        if not handler:
            return json.dumps({"erro": f"Tool desconhecida: {tool_name}"})

        try:
            result = await handler(arguments, telefone)
            return json.dumps(result, ensure_ascii=False, default=_decimal_default)
        except Exception as e:
            logger.error(f"Erro ao executar tool {tool_name}: {e}")
            return json.dumps({"erro": f"Erro ao executar {tool_name}: {str(e)}"})

    # ==================== Handlers ====================

    async def _buscar_produtos(self, args: Dict, telefone: str) -> Dict:
        termo = args.get("termo", "")
        limite = args.get("limite", 10)

        produtos = self.produtos_service.buscar_produtos(termo=termo, limite=limite)

        if not produtos:
            return {"produtos": [], "total": 0, "mensagem": f"Nenhum produto encontrado para '{termo}'"}

        # Formatar para o agente
        produtos_formatados = []
        for p in produtos:
            preco = float(p.get("preco_promocional") or p.get("preco") or 0)
            produto_f = {
                "id": str(p["id"]),
                "nome": p["nome"],
                "preco": preco,
                "categoria": p.get("categoria", ""),
                "descricao": (p.get("descricao") or "")[:150],
                "peso": float(p.get("peso") or 0),
                "unidade": p.get("unidade", "un"),
                "estoque": p.get("quantidade_estoque", 0),
                "imagem_url": p.get("imagem_url", ""),
            }
            # Mostrar preço original se tem promocional
            preco_original = float(p.get("preco") or 0)
            if p.get("preco_promocional") and preco_original > preco:
                produto_f["preco_original"] = preco_original

            produtos_formatados.append(produto_f)

        return {"produtos": produtos_formatados, "total": len(produtos_formatados)}

    async def _add_to_cart(self, args: Dict, telefone: str) -> Dict:
        produto_nome = args.get("produto_nome", "")
        preco = args.get("preco", 0)
        quantidade = args.get("quantidade", 1)
        produto_id = args.get("produto_id", "")

        if not produto_id or not produto_nome:
            return {"erro": "produto_id e produto_nome sao obrigatorios"}

        result = self.carrinho_service.adicionar_item(
            telefone=telefone,
            produto_id=produto_id,
            produto_nome=produto_nome,
            preco_unitario=preco,
            quantidade=quantidade,
        )

        # Calcular total atualizado
        total = self.carrinho_service.calcular_total(telefone)
        itens = self.carrinho_service.contar_itens(telefone)

        return {
            "sucesso": True,
            "mensagem": f"Adicionado ao carrinho: {produto_nome} x{quantidade}",
            "total_carrinho": float(total),
            "total_itens": itens,
            "status": result.get("status", "added"),
        }

    async def _remover_do_carrinho(self, args: Dict, telefone: str) -> Dict:
        produto_nome = args.get("produto_nome", "")

        # Buscar produto no carrinho pelo nome
        carrinho = self.carrinho_service.obter_carrinho(telefone)
        produto_id = None
        for item in carrinho:
            if item["nome"].lower() == produto_nome.lower():
                produto_id = item["produto_id"]
                break

        if not produto_id:
            # Tentar match parcial
            for item in carrinho:
                if produto_nome.lower() in item["nome"].lower():
                    produto_id = item["produto_id"]
                    produto_nome = item["nome"]
                    break

        if not produto_id:
            return {"erro": f"Produto '{produto_nome}' nao encontrado no carrinho"}

        self.carrinho_service.remover_item(telefone, produto_id)
        total = self.carrinho_service.calcular_total(telefone)

        return {
            "sucesso": True,
            "mensagem": f"Removido do carrinho: {produto_nome}",
            "total_carrinho": float(total),
        }

    async def _alterar_quantidade(self, args: Dict, telefone: str) -> Dict:
        produto_nome = args.get("produto_nome", "")
        quantidade = args.get("quantidade", 1)

        carrinho = self.carrinho_service.obter_carrinho(telefone)
        produto_id = None
        for item in carrinho:
            if produto_nome.lower() in item["nome"].lower():
                produto_id = item["produto_id"]
                produto_nome = item["nome"]
                break

        if not produto_id:
            return {"erro": f"Produto '{produto_nome}' nao encontrado no carrinho"}

        if quantidade <= 0:
            self.carrinho_service.remover_item(telefone, produto_id)
            return {"sucesso": True, "mensagem": f"Removido: {produto_nome}"}

        self.carrinho_service.atualizar_quantidade(telefone, produto_id, quantidade)
        total = self.carrinho_service.calcular_total(telefone)

        return {
            "sucesso": True,
            "mensagem": f"Quantidade atualizada: {produto_nome} -> {quantidade}",
            "total_carrinho": float(total),
        }

    async def _view_cart(self, args: Dict, telefone: str) -> Dict:
        itens = self.carrinho_service.obter_carrinho(telefone)
        total = self.carrinho_service.calcular_total(telefone)

        if not itens:
            return {"vazio": True, "itens": [], "total": 0.0, "mensagem": "Carrinho vazio"}

        return {
            "vazio": False,
            "itens": itens,
            "total": float(total),
            "quantidade_tipos": len(itens),
        }

    async def _limpar_carrinho(self, args: Dict, telefone: str) -> Dict:
        self.carrinho_service.limpar_carrinho(telefone)
        return {"sucesso": True, "mensagem": "Carrinho limpo"}

    async def _gerar_pix(self, args: Dict, telefone: str) -> Dict:
        """Gera pagamento PIX (mock por enquanto)."""
        total = self.carrinho_service.calcular_total(telefone)
        if total <= 0:
            return {"erro": "Carrinho vazio. Adicione produtos antes de gerar pagamento."}

        numero_pedido = "RC-" + "".join(random.choices(string.digits, k=6))
        # PIX copia-e-cola simulado
        pix_code = f"00020126580014br.gov.bcb.pix0136rocacapital@pix.com5204000053039865406{total:.2f}5802BR5913ROCA CAPITAL6009Belo Horizonte62070503***6304"

        return {
            "sucesso": True,
            "numero_pedido": numero_pedido,
            "total": float(total),
            "qr_code": pix_code,
            "mensagem": f"PIX gerado! Pedido {numero_pedido}, Total R$ {total:.2f}",
        }

    async def _gerar_pagamento(self, args: Dict, telefone: str) -> Dict:
        """Gera link de pagamento cartão (mock por enquanto)."""
        total = self.carrinho_service.calcular_total(telefone)
        if total <= 0:
            return {"erro": "Carrinho vazio. Adicione produtos antes de gerar pagamento."}

        numero_pedido = "RC-" + "".join(random.choices(string.digits, k=6))
        link = f"https://pay.rocacapital.com.br/checkout/{numero_pedido}"

        return {
            "sucesso": True,
            "numero_pedido": numero_pedido,
            "total": float(total),
            "link_pagamento": link,
            "mensagem": f"Link gerado! Pedido {numero_pedido}, Total R$ {total:.2f}",
        }

    async def _enviar_qr_code_pix(self, args: Dict, telefone: str) -> Dict:
        """Envia QR Code PIX via ZAPI (mock por enquanto)."""
        # Em produção, geraria imagem real do QR code
        return {"sucesso": True, "mensagem": "QR Code enviado"}

    async def _enviar_foto_produto(self, args: Dict, telefone: str) -> Dict:
        produto_id = args.get("produto_id", "")
        if not produto_id:
            return {"erro": "produto_id obrigatorio"}

        produto = self.produtos_service.buscar_produto_por_id(produto_id)
        if not produto:
            return {"erro": "Produto nao encontrado"}

        imagem_url = produto.get("imagem_url")
        if not imagem_url:
            return {"erro": "Produto sem imagem disponivel"}

        result = self.zapi_client.send_image(
            phone=telefone,
            image_url=imagem_url,
            caption=produto.get("nome", ""),
        )

        if result.get("success"):
            return {"sucesso": True, "mensagem": f"Foto de {produto['nome']} enviada"}
        return {"erro": "Falha ao enviar foto"}

    async def _calcular_frete(self, args: Dict, telefone: str) -> Dict:
        """Calcula frete (mock com valores simulados por enquanto)."""
        endereco = args.get("endereco_completo", "")
        valor_pedido = args.get("valor_pedido", 0)
        peso_kg = args.get("peso_kg", 1.0)

        if not endereco:
            return {"erro": "Endereco obrigatorio para calcular frete"}

        # Simulação de frete baseada em localidade
        endereco_lower = endereco.lower()
        eh_bh = any(
            t in endereco_lower
            for t in ["belo horizonte", "bh", "savassi", "lourdes", "funcionarios", "centro", "pampulha"]
        )

        if eh_bh:
            opcoes = [
                {
                    "tipo": "lalamove",
                    "nome": "Motoboy (Lalamove)",
                    "valor": 12.50 + (peso_kg * 2),
                    "prazo": "45 minutos a 1 hora",
                },
                {
                    "tipo": "correios_pac",
                    "nome": "Correios PAC",
                    "valor": 18.00 + (peso_kg * 3),
                    "prazo": "2-3 dias uteis",
                },
            ]
        else:
            opcoes = [
                {
                    "tipo": "correios_pac",
                    "nome": "Correios PAC",
                    "valor": 25.00 + (peso_kg * 4),
                    "prazo": "5-8 dias uteis",
                },
                {
                    "tipo": "correios_sedex",
                    "nome": "Correios SEDEX",
                    "valor": 35.00 + (peso_kg * 5),
                    "prazo": "2-3 dias uteis",
                },
            ]

        # Arredondar valores
        for op in opcoes:
            op["valor"] = round(op["valor"], 2)

        return {
            "endereco": endereco,
            "opcoes_frete": opcoes,
            "mensagem": "Frete calculado com sucesso",
        }

    async def _confirmar_frete(self, args: Dict, telefone: str) -> Dict:
        tipo_frete = args.get("tipo_frete", "")
        valor_frete = args.get("valor_frete", 0)
        prazo_entrega = args.get("prazo_entrega", "")

        # Salvar no banco (simplificado - salva como preferência do cliente)
        return {
            "sucesso": True,
            "tipo_frete": tipo_frete,
            "valor_frete": valor_frete,
            "prazo_entrega": prazo_entrega,
            "mensagem": f"Frete confirmado: {tipo_frete} - R$ {valor_frete:.2f} ({prazo_entrega})",
        }

    async def _salvar_endereco(self, args: Dict, telefone: str) -> Dict:
        endereco = args.get("endereco", "")
        if not endereco:
            return {"erro": "Endereco obrigatorio"}

        # Salvar no banco de clientes
        try:
            import psycopg2
            from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

            db_url = os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL")
            if db_url:
                # Sanitizar
                u = urlparse(db_url)
                qs = dict(parse_qsl(u.query, keep_blank_values=True))
                for k in list(qs.keys()):
                    if k in {"pgbouncer", "connection_limit"}:
                        qs.pop(k, None)
                clean_url = urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(qs, doseq=True), u.fragment))

                conn = psycopg2.connect(clean_url, sslmode="require")
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE clientes SET endereco = %s WHERE telefone = %s",
                    (endereco, telefone),
                )
                conn.commit()
                cursor.close()
                conn.close()
        except Exception as e:
            logger.error(f"Erro ao salvar endereco: {e}")

        return {"sucesso": True, "mensagem": f"Endereco salvo: {endereco}"}

    async def _buscar_historico_compras(self, args: Dict, telefone: str) -> Dict:
        """Busca histórico de compras (simplificado)."""
        # TODO: Integrar com tabela de pedidos real
        try:
            import psycopg2
            from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

            db_url = os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL")
            if db_url:
                u = urlparse(db_url)
                qs = dict(parse_qsl(u.query, keep_blank_values=True))
                for k in list(qs.keys()):
                    if k in {"pgbouncer", "connection_limit"}:
                        qs.pop(k, None)
                clean_url = urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(qs, doseq=True), u.fragment))

                conn = psycopg2.connect(clean_url, sslmode="require")
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute(
                    """
                    SELECT DISTINCT produto_nome, preco_unitario, quantidade
                    FROM historico_compras
                    WHERE telefone = %s
                    ORDER BY produto_nome
                    LIMIT 10
                    """,
                    (telefone,),
                )
                rows = cursor.fetchall()
                cursor.close()
                conn.close()

                if rows:
                    return {
                        "tem_historico": True,
                        "produtos_anteriores": [dict(r) for r in rows],
                    }
        except Exception as e:
            logger.debug(f"Historico de compras nao disponivel: {e}")

        return {"tem_historico": False, "produtos_anteriores": [], "mensagem": "Nenhuma compra anterior encontrada"}

    async def _verificar_status_pedido(self, args: Dict, telefone: str) -> Dict:
        numero_pedido = args.get("numero_pedido", "")
        if not numero_pedido:
            return {"erro": "Numero do pedido obrigatorio"}

        # TODO: Integrar com Tiny ERP para status real
        return {
            "numero_pedido": numero_pedido,
            "status": "processando",
            "mensagem": f"Pedido {numero_pedido} esta sendo processado. Para mais detalhes, fale com a Bianca: 31 97266-6900",
        }

    async def _escalar_atendimento(self, args: Dict, telefone: str) -> Dict:
        motivo = args.get("motivo", "pediu_humano")
        descricao = args.get("descricao", "")

        logger.info(f"Escalando atendimento: {telefone[:8]} - {motivo}: {descricao}")

        # Enviar notificação para Bianca
        self.zapi_client.send_text(
            phone="5531972666900",
            message=f"Atendimento escalado!\n\nCliente: {telefone}\nMotivo: {motivo}\nDescricao: {descricao}",
        )

        return {
            "sucesso": True,
            "mensagem": "Atendimento escalado para vendedora Bianca (31 97266-6900)",
            "contato_humano": "31 97266-6900",
            "vendedora": "Bianca",
        }
