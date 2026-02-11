# 📚 Tiny API V3 - Referência Completa

## Visão Geral

Este documento é um **resumo prático** da API V3 do Tiny ERP (focado no que o PDV usa), baseado no Swagger oficial.

## 📄 OpenAPI (Swagger) completo

- **Arquivo (importável)**: `docs/integrations/TINY_V3_OPENAPI.json`
- **Endpoint no backend**: `GET /api/tiny/openapi.json`
- **Fonte oficial**: `https://erp.tiny.com.br/public-api/v3/swagger/`

### Como importar

- **Postman/Insomnia**: importe o arquivo `docs/integrations/TINY_V3_OPENAPI.json`.
- **Via backend**: importe a URL `GET /api/tiny/openapi.json` (útil para manter sempre atualizado no ambiente).

## 🔐 Autenticação

A API V3 usa **OAuth 2.0** com Bearer Token.

```bash
Authorization: Bearer {access_token}
```

> Para mais detalhes (schemas, endpoints e parâmetros), use o **OpenAPI completo** acima.

## 📦 Endpoints de Estoque

### GET `/estoque/{idProduto}`
Obtém informações de estoque de um produto.

**Response:**
```json
{
  "id": 0,
  "nome": "string",
  "codigo": "string",
  "unidade": "string",
  "saldo": 0,
  "reservado": 0,
  "disponivel": 0,
  "depositos": [
    {
      "id": 0,
      "nome": "string",
      "desconsiderar": true,
      "saldo": 0,
      "reservado": 0,
      "disponivel": 0
    }
  ]
}
```

### POST `/estoque/{idProduto}`
Atualiza o estoque de um produto.

**Request Body:**
```json
{
  "deposito": {
    "id": 0
  },
  "tipo": "B",  // B=Balanço, E=Entrada, S=Saída
  "data": "2024-01-01",
  "quantidade": 10.5,
  "precoUnitario": 25.00,
  "observacoes": "Ajuste de inventário"
}
```

**Tipos de operação:**
- `B` - Balanço (define quantidade exata)
- `E` - Entrada (adiciona ao estoque)
- `S` - Saída (remove do estoque)

## 👥 Endpoints de Contatos

### GET `/contatos`
Lista todos os contatos (clientes/fornecedores).

**Query Parameters:**
- `nome` - Pesquisa por nome
- `codigo` - Pesquisa por código
- `cpfCnpj` - Pesquisa por CPF/CNPJ
- `celular` - Pesquisa por celular
- `situacao` - B (Ativo), A (Ativo com acesso), I (Inativo), E (Excluído)
- `limit` - Limite (default: 100)
- `offset` - Offset (default: 0)

### POST `/contatos`
Cria um novo contato.

**Request Body:**
```json
{
  "nome": "Nome do Cliente",
  "codigo": "CLI001",
  "tipoPessoa": "J",  // F=Física, J=Jurídica
  "cpfCnpj": "12345678000190",
  "ie": "123456789",
  "rg": "string",
  "email": "email@exemplo.com",
  "fone": "31999999999",
  "celular": "31999999999",
  "endereco": {
    "endereco": "Rua Exemplo",
    "numero": "123",
    "complemento": "Sala 1",
    "bairro": "Centro",
    "cep": "30000000",
    "municipio": "Belo Horizonte",
    "uf": "MG"
  },
  "situacao": "B"
}
```

### PUT `/contatos/{idContato}`
Atualiza um contato existente.

### DELETE `/contatos/{idContato}/pessoas/{idPessoa}`
Remove uma pessoa do contato.

## 📋 Endpoints de Pedidos

### GET `/pedidos`
Lista pedidos.

**Query Parameters:**
- `numero` - Número do pedido
- `nomeCliente` - Nome do cliente
- `codigoCliente` - Código do cliente
- `cnpj` - CPF/CNPJ
- `dataInicial` - Data inicial
- `dataFinal` - Data final
- `situacao` - Situação (ver enum abaixo)
- `numeroPedidoEcommerce` - Número do e-commerce
- `idVendedor` - ID do vendedor
- `limit` - Limite (default: 100)
- `offset` - Offset (default: 0)

**Situações do Pedido (enum int):**
| Código | Descrição |
|--------|-----------|
| 0 | Aberta |
| 1 | Faturada |
| 2 | Cancelada |
| 3 | Aprovada |
| 4 | Preparando Envio |
| 5 | Enviada |
| 6 | Entregue |
| 7 | Pronto Envio |
| 8 | Dados Incompletos |
| 9 | Não Entregue |

### POST `/pedidos`
Cria um novo pedido.

**Request Body:**
```json
{
  "dataPrevista": "2024-01-15",
  "dataEnvio": "2024-01-10",
  "observacoes": "Pedido urgente",
  "observacoesInternas": "Verificar estoque",
  "situacao": 0,
  "data": "2024-01-01",
  "dataEntrega": "2024-01-20",
  "numeroOrdemCompra": "OC-001",
  "valorDesconto": 10.00,
  "valorFrete": 15.00,
  "valorOutrasDespesas": 5.00,
  "idContato": 12345,
  "listaPreco": {
    "id": 1
  },
  "naturezaOperacao": {
    "id": 1
  },
  "vendedor": {
    "id": 1
  },
  "enderecoEntrega": {
    "endereco": "Rua Entrega",
    "enderecoNro": "100",
    "complemento": "Apt 101",
    "bairro": "Centro",
    "municipio": "São Paulo",
    "cep": "01000000",
    "uf": "SP",
    "fone": "11999999999",
    "nomeDestinatario": "João Silva",
    "cpfCnpj": "12345678901",
    "tipoPessoa": "F",
    "ie": ""
  },
  "ecommerce": {
    "id": 1,
    "numeroPedidoEcommerce": "PDV-001"
  },
  "transportador": {
    "id": 1,
    "fretePorConta": "R",
    "formaEnvio": {
      "id": 1
    },
    "formaFrete": {
      "id": 1
    },
    "codigoRastreamento": "BR123456789",
    "urlRastreamento": "https://rastreio.com/BR123456789"
  },
  "pagamento": {
    "formaPagamento": {
      "id": 1
    },
    "meioPagamento": {
      "id": 1
    },
    "parcelas": [
      {
        "dias": 30,
        "data": "2024-02-01",
        "valor": 100.00,
        "observacoes": "1ª parcela"
      }
    ]
  },
  "itens": [
    {
      "produto": {
        "id": 12345
      },
      "quantidade": 2,
      "valorUnitario": 50.00,
      "infoAdicional": "Cor: Azul"
    }
  ]
}
```

### POST `/pedidos/{idPedido}/lancar-estoque`
Lança o estoque do pedido.

### POST `/pedidos/{idPedido}/estornar-estoque`
Estorna o estoque do pedido.

### PUT `/pedidos/{idPedido}/situacao`
Atualiza a situação do pedido.

## 📦 Endpoints de Produtos

### GET `/produtos`
Lista produtos.

**Query Parameters:**
- `nome` - Pesquisa por nome
- `codigo` - Pesquisa por código (SKU)
- `gtin` - Pesquisa por GTIN
- `situacao` - A (Ativo), I (Inativo), E (Excluído)
- `dataCriacao` - Data de criação
- `dataAlteracao` - Data de alteração
- `limit` - Limite (default: 100)
- `offset` - Offset (default: 0)

**⚠️ IMPORTANTE:** A listagem NÃO retorna estoque. Use `GET /estoque/{idProduto}` ou `GET /produtos/{idProduto}` para detalhes com estoque.

### GET `/produtos/{idProduto}`
Obtém detalhes completos do produto (inclui estoque).

### POST `/produtos`
Cria um novo produto.

### PUT `/produtos/{idProduto}`
Atualiza um produto.

### PUT `/produtos/{idProduto}/preco`
Atualiza apenas o preço do produto.

## 📄 Endpoints de Notas Fiscais

### GET `/notas`
Lista notas fiscais.

### POST `/notas/{idNota}/lancar-estoque`
Lança o estoque da nota fiscal.

## 🏷️ Endpoints de Categorias

### GET `/categorias`
Lista categorias de produtos.

## 🛒 Frete Por Conta (enum)

| Código | Descrição |
|--------|-----------|
| R | Remetente |
| D | Destinatário |
| T | Terceiros |
| 3 | Próprio Remetente |
| 4 | Próprio Destinatário |
| S | Sem Transporte |

## 📊 Paginação

Todos os endpoints de listagem suportam paginação com:
- `limit` - Número máximo de resultados (default: 100, max: 100)
- `offset` - Posição inicial (default: 0)
- `orderBy` - Ordenação: `asc` ou `desc`

## 🔄 Rotas Implementadas no PDV

| Rota | Método | Descrição |
|------|--------|-----------|
| `/api/tiny/sync/products` | POST | Sincroniza produtos do Tiny → PDV |
| `/api/tiny/sync/customers` | POST | Sincroniza clientes do Tiny → PDV |
| `/api/tiny/sync/orders/:id` | POST | Envia pedido do PDV → Tiny |
| `/api/tiny/sync/stock` | POST | Sincroniza estoque do Tiny → PDV |
| `/api/tiny/sync/quick` | POST | Sync rápido (só preços) |
| `/api/tiny/sync/enrich` | POST | Enriquece produtos sem estoque |
| `/api/tiny/stock/:productId` | GET | Busca estoque de produto específico |
| `/api/tiny/export/customer/:id` | POST | Exporta cliente do PDV → Tiny |
| `/api/tiny/health` | GET | Status da conexão OAuth |

## 📖 Documentação Oficial

- Swagger: https://erp.tiny.com.br/public-api/v3/swagger/
- Portal do Desenvolvedor: https://tiny.com.br/desenvolvedores

---

*Documentação gerada em: Janeiro 2026*
