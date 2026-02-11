"""
Modelos de dados da API Tiny ERP V3
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date


# ==================== Produtos ====================

class TinyProduct(BaseModel):
    """Produto do Tiny ERP"""
    id: int
    codigo: str  # SKU
    nome: str
    unidade: str = "UN"
    preco: Decimal
    preco_custo: Optional[Decimal] = None
    peso_liquido: Optional[Decimal] = None
    peso_bruto: Optional[Decimal] = None
    estoque_atual: Optional[Decimal] = None
    estoque_minimo: Optional[Decimal] = None
    ncm: Optional[str] = None
    origem: Optional[int] = None
    gtin: Optional[str] = None  # Código de barras
    situacao: str = "A"  # A=Ativo, I=Inativo
    tipo: Optional[str] = None  # S=Simples, K=Kit
    categoria_id: Optional[int] = None
    descricao_complementar: Optional[str] = None
    anexos: Optional[List[Dict[str, Any]]] = []

    # Campos SEO (e-commerce)
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    link_video: Optional[str] = None


# ==================== Pedidos ====================

class TinyOrderItem(BaseModel):
    """Item de um pedido"""
    produto: Dict[str, int]  # {"id": 12345}
    quantidade: Decimal
    valor_unitario: Decimal
    info_adicional: Optional[str] = None


class TinyOrderPaymentInstallment(BaseModel):
    """Parcela de pagamento"""
    dias: Optional[int] = None
    data: Optional[date] = None
    valor: Decimal
    observacoes: Optional[str] = None


class TinyOrderPayment(BaseModel):
    """Dados de pagamento"""
    forma_pagamento: Dict[str, int]  # {"id": 1}
    meio_pagamento: Optional[Dict[str, int]] = None
    parcelas: List[TinyOrderPaymentInstallment]


class TinyOrderAddress(BaseModel):
    """Endereço de entrega"""
    endereco: str
    endereco_nro: str
    complemento: Optional[str] = None
    bairro: str
    municipio: str
    cep: str
    uf: str
    fone: Optional[str] = None
    nome_destinatario: str
    cpf_cnpj: str
    tipo_pessoa: str  # F=Física, J=Jurídica
    ie: Optional[str] = None


class TinyOrderTransport(BaseModel):
    """Dados de transporte"""
    id: Optional[int] = None
    frete_por_conta: str = "R"  # R=Remetente, D=Destinatário
    forma_envio: Optional[Dict[str, int]] = None
    forma_frete: Optional[Dict[str, int]] = None
    codigo_rastreamento: Optional[str] = None
    url_rastreamento: Optional[str] = None


class TinyOrderEcommerce(BaseModel):
    """Dados de e-commerce"""
    id: Optional[int] = None
    numero_pedido_ecommerce: str  # Número do pedido externo


class TinyOrderCreate(BaseModel):
    """Dados para criar pedido no Tiny"""
    data: date
    data_prevista: Optional[date] = None
    data_entrega: Optional[date] = None
    observacoes: Optional[str] = None
    observacoes_internas: Optional[str] = None
    situacao: int = 0  # 0=Aberta, 1=Faturada, etc
    valor_desconto: Optional[Decimal] = None
    valor_frete: Optional[Decimal] = None
    valor_outras_despesas: Optional[Decimal] = None
    id_contato: int  # ID do cliente
    endereco_entrega: TinyOrderAddress
    ecommerce: Optional[TinyOrderEcommerce] = None
    transportador: Optional[TinyOrderTransport] = None
    pagamento: TinyOrderPayment
    itens: List[TinyOrderItem]


class TinyOrder(TinyOrderCreate):
    """Pedido completo (com ID)"""
    id: int
    numero: str


# ==================== Contatos (Clientes) ====================

class TinyContactAddress(BaseModel):
    """Endereço de contato"""
    endereco: str
    numero: str
    complemento: Optional[str] = None
    bairro: str
    cep: str
    municipio: str
    uf: str


class TinyContactCreate(BaseModel):
    """Dados para criar contato (cliente)"""
    nome: str
    codigo: Optional[str] = None
    tipo_pessoa: str  # F=Física, J=Jurídica
    cpf_cnpj: str
    ie: Optional[str] = None
    rg: Optional[str] = None
    email: Optional[str] = None
    fone: Optional[str] = None
    celular: str
    endereco: TinyContactAddress
    situacao: str = "B"  # B=Ativo


class TinyContact(TinyContactCreate):
    """Contato completo (com ID)"""
    id: int


# ==================== Estoque ====================

class TinyStockDeposit(BaseModel):
    """Depósito de estoque"""
    id: int
    nome: str
    desconsiderar: bool = False
    saldo: Decimal
    reservado: Decimal
    disponivel: Decimal


class TinyStock(BaseModel):
    """Estoque de produto"""
    id: int
    nome: str
    codigo: str
    unidade: str
    saldo: Decimal
    reservado: Decimal
    disponivel: Decimal
    depositos: List[TinyStockDeposit]


class TinyStockUpdate(BaseModel):
    """Atualização de estoque"""
    deposito: Dict[str, int]  # {"id": 1}
    tipo: str  # B=Balanço, E=Entrada, S=Saída
    data: date
    quantidade: Decimal
    preco_unitario: Optional[Decimal] = None
    observacoes: Optional[str] = None
