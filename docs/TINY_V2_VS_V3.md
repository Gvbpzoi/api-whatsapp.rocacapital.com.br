# 🔄 Tiny API - V2 vs V3 com Fallback Automático

**Problema:** Algumas funções da API V3 não funcionam (ex: telefone)
**Solução:** Cliente híbrido que tenta V3 → fallback V2 automático

---

## 📋 Diferenças Principais

| Aspecto | V2 (antiga) | V3 (nova) |
|---------|-------------|-----------|
| **URL Base** | `api.tiny.com.br/api2` | `erp.tiny.com.br/public-api/v3` |
| **Auth** | Token simples no body | OAuth 2.0 Bearer Token |
| **Método HTTP** | Sempre POST | GET/POST/PUT/DELETE |
| **Formato** | XML ou JSON | JSON |
| **Resposta** | `{"retorno": {...}}` | Direto `{...}` |
| **Estabilidade** | ✅ Mais estável | ⚠️ Algumas funções falham |
| **Modernidade** | ❌ Antiga | ✅ Moderna |

---

## 🎯 Cliente Híbrido

### Como Funciona

```python
from src.services.tiny_hybrid_client import TinyHybridClient

# Inicializar com ambas as versões
client = TinyHybridClient(
    # V3 (OAuth)
    client_id="seu-client-id",
    client_secret="seu-secret",
    access_token="token-v3",

    # V2 (fallback)
    v2_token="seu-token-v2"
)

# Usar normalmente - fallback é automático!
produtos = await client.list_products(nome="queijo")
# ↑ Tenta V3 primeiro, se falhar usa V2

pedido = await client.create_order(order_data)
# ↑ IMPORTANTE: telefone às vezes falha na V3
# Cliente detecta e automaticamente usa V2
```

### Fluxo de Fallback

```
┌─────────────────────────────────────┐
│  Operação: create_order()           │
└──────────┬──────────────────────────┘
           │
           ▼
    ┌──────────────┐
    │ Tentar V3?   │──── Não configurado ──────┐
    └──────┬───────┘                            │
           │ Sim                                │
           ▼                                    │
    ┌──────────────┐                            │
    │  Chamar V3   │                            │
    └──────┬───────┘                            │
           │                                    │
     ┌─────▼─────┐                              │
     │  Sucesso? │                              │
     └─────┬─────┘                              │
           │                                    │
      ┌────┴────┐                               │
      │         │                               │
     Sim       Não                              │
      │         │                               │
      │    ┌────▼────────────┐                  │
      │    │ Log warning     │                  │
      │    │ "V3 falhou"     │                  │
      │    └────┬────────────┘                  │
      │         │                               │
      │         ▼                               │
      │    ┌──────────────┐                     │
      │    │  Chamar V2   │◄────────────────────┘
      │    └──────┬───────┘
      │           │
      │      ┌────▼────┐
      │      │ Sucesso?│
      │      └────┬────┘
      │           │
      │      ┌────┴────┐
      │      │         │
      │     Sim       Não
      │      │         │
      └──────┼─────────┼───────► Retornar resultado
             │         │
             │    ┌────▼─────┐
             │    │  Erro!   │
             │    └──────────┘
             │
        ┌────▼──────────────────┐
        │ Registrar estatística │
        │ (V3 ou V2 funcionou)  │
        └───────────────────────┘
```

---

## 📝 Endpoints Mapeados

### Produtos

| Operação | V3 | V2 | Fallback? |
|----------|----|----|-----------|
| Listar | `GET /produtos` | `POST /produtos.pesquisa.php` | ✅ Sim |
| Detalhes | `GET /produtos/{id}` | `POST /produto.obter.php` | ✅ Sim |
| Estoque | `GET /estoque/{id}` | `POST /produto.obter.estoque.php` | ✅ Sim |

### Pedidos

| Operação | V3 | V2 | Fallback? |
|----------|----|----|-----------|
| Criar | `POST /pedidos` | `POST /pedido.incluir.php` | ✅ **Sim (telefone!)** |
| Listar | `GET /pedidos` | `POST /pedidos.pesquisa.php` | ✅ Sim |
| Atualizar status | `PUT /pedidos/{id}/situacao` | `POST /pedido.alterar.situacao.php` | ✅ Sim |

### Contatos (Clientes)

| Operação | V3 | V2 | Fallback? |
|----------|----|----|-----------|
| Criar | `POST /contatos` | `POST /cliente.incluir.php` | ✅ Sim |
| Listar | `GET /contatos` | `POST /contatos.pesquisa.php` | ✅ Sim |

---

## 🔧 Diferenças de Formato

### 1. Datas

**V3:**
```json
"data": "2026-02-11"  // YYYY-MM-DD
```

**V2:**
```json
"data_pedido": "11/02/2026"  // DD/MM/YYYY
```

**Conversão automática no cliente híbrido!** ✅

---

### 2. Estrutura de Pedido

**V3:**
```json
{
  "idContato": 12345,
  "enderecoEntrega": {
    "endereco": "Rua X",
    "enderecoNro": "123"
  },
  "itens": [
    {
      "produto": {"id": 100},
      "quantidade": 2,
      "valorUnitario": 50.00
    }
  ]
}
```

**V2:**
```json
{
  "codigo_cliente": 12345,
  "endereco_destinatario": "Rua X",
  "numero_destinatario": "123",
  "itens": [
    {
      "item": {
        "codigo_produto": 100,
        "quantidade": 2,
        "valor_unitario": 50.00
      }
    }
  ]
}
```

**Conversão automática na função `_convert_order_v3_to_v2()`!** ✅

---

### 3. Resposta

**V3:**
```json
{
  "id": 12345,
  "numero": "67890"
}
```

**V2:**
```json
{
  "retorno": {
    "status_processamento": "1",  // 1=OK, 3=Erro
    "status": "OK",
    "id": 12345,
    "numero": "67890"
  }
}
```

**Cliente híbrido normaliza a resposta!** ✅

---

## 📊 Estatísticas de Uso

O cliente rastreia automaticamente qual versão funciona melhor:

```python
# Após usar por um tempo
stats = client.get_version_stats()

print(stats)
# {
#     "create_order": {
#         "v2": 15,  # ← V2 funcionou 15 vezes
#         "v3": 2,   # ← V3 funcionou apenas 2 vezes
#         "errors": 1
#     },
#     "list_products": {
#         "v2": 5,
#         "v3": 20,  # ← V3 funciona bem aqui!
#         "errors": 0
#     }
# }
```

**Use essas estatísticas** para decidir se vale a pena manter V3 ou migrar para V2!

---

## 🚨 Problemas Conhecidos da V3

### 1. Telefone em Pedidos

**Sintoma:** Erro ao criar pedido com telefone no endereço

**Solução:** Cliente híbrido detecta e usa V2 automaticamente

```python
# Você não precisa fazer nada diferente!
pedido = await client.create_order(order_data)
# ↑ Se V3 falhar por causa do telefone, V2 assume
```

### 2. Campos Opcionais

**Sintoma:** V3 reclama de campos ausentes mesmo sendo opcionais

**Solução:** V2 é mais tolerante, fallback resolve

---

## ⚙️ Configuração

### .env

```bash
# V3 (OAuth) - tente usar sempre que possível
TINY_CLIENT_ID=seu-client-id
TINY_CLIENT_SECRET=seu-secret
TINY_ACCESS_TOKEN=seu-access-token
TINY_REFRESH_TOKEN=seu-refresh-token

# V2 (fallback) - para quando V3 falhar
TINY_V2_TOKEN=9f7e446bd44a35cd735b143c4682dc9a6c321be78ade1fa362fe977280daf0bc
```

### Inicialização

```python
from src.services.tiny_hybrid_client import TinyHybridClient
import os

client = TinyHybridClient(
    # V3
    client_id=os.getenv("TINY_CLIENT_ID"),
    client_secret=os.getenv("TINY_CLIENT_SECRET"),
    access_token=os.getenv("TINY_ACCESS_TOKEN"),
    refresh_token=os.getenv("TINY_REFRESH_TOKEN"),

    # V2 (fallback)
    v2_token=os.getenv("TINY_V2_TOKEN")
)
```

---

## 🧪 Teste de Saúde

```python
# Verificar se ambas as versões funcionam
health = await client.health_check()

print(health)
# {
#     "v3": True,   # ✅ V3 está OK
#     "v2": True    # ✅ V2 está OK (fallback pronto)
# }

# Se v3=False, todas operações usarão V2
# Se v2=False, não tem fallback (erro se V3 falhar)
```

---

## 🎯 Recomendações

### ✅ Use V3 quando:
- Listar produtos
- Buscar estoque
- Listar pedidos
- Operações de leitura em geral

### ⚠️ Use V2 quando:
- Criar pedidos (telefone problemático na V3)
- Criar clientes com campos especiais
- Operação já falhou na V3 antes

### 🔄 Deixe o Híbrido Decidir:
- Cliente tenta V3 automaticamente
- Fallback para V2 se falhar
- Melhor dos dois mundos! ✅

---

## 📈 Migração Gradual

```python
# 1. Comece com ambas configuradas
client = TinyHybridClient(v3=..., v2=...)

# 2. Use por 1 semana

# 3. Veja estatísticas
stats = client.get_version_stats()

# 4. Se V3 tem muitos erros, considere:
#    - Reportar bugs para Tiny
#    - Ou usar só V2 temporariamente

# 5. Quando Tiny corrigir V3, desabilite V2
client = TinyHybridClient(v3=..., v2=None)  # Sem fallback
```

---

## 🐛 Troubleshooting

### "V3 sempre falha"

```python
# Ver logs
import logging
logging.basicConfig(level=logging.DEBUG)

# Vai mostrar:
# 🔵 Tentando create_order via V3...
# ⚠️ V3 falhou: [erro exato]
# 🔄 Tentando fallback para V2...
# ✅ create_order via V2 OK
```

### "V2 também falha"

```python
# Verificar token V2
health = await client.health_check()

if not health["v2"]:
    print("❌ Token V2 inválido!")
    # Gerar novo token em: https://www.tiny.com.br/
```

---

## 📞 Suporte

**V3 com bug?**
- Reporte para Tiny: https://ajuda.tiny.com.br/
- Use V2 como workaround temporário

**V2 deprecated?**
- Tiny ainda não anunciou descontinuação
- V2 é mais estável que V3 atualmente
- Use híbrido para garantir!

---

**Desenvolvido com ❤️ por:** Claude + Guilherme Vieira
**Data:** 11/02/2026
**Versão:** 2.0.0

**Fallback automático = produção estável!** 🚀
