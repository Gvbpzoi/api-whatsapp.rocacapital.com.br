# 🧠 Memória do Sistema - Roça Capital

**Data de Criação:** 11/02/2026
**Última Atualização:** 11/02/2026

---

## 📚 Base de Conhecimento

### Produtos Mais Vendidos

1. **Queijo Canastra Meia-Cura 500g**
   - Preço: R$ 45,00
   - Giro: ~50 unidades/semana
   - Perfil: Turistas e moradores de BH
   - Observação: Produto-âncora, sempre manter estoque alto

2. **Doce de Leite Tradicional 300g**
   - Preço: R$ 18,00
   - Giro: ~40 unidades/semana
   - Perfil: Presente/lembrança
   - Observação: Combina bem com queijos

3. **Café Serra da Canastra 500g**
   - Preço: R$ 32,00
   - Giro: ~30 unidades/semana
   - Perfil: Apreciadores de café especial
   - Observação: Cliente geralmente volta para recompra

### Preferências de Clientes (Exemplos)

**Cliente: João Silva (5531999999999)**
- Prefere: Queijos meia-cura
- Frequência: Mensal
- Ticket médio: R$ 150
- Última compra: 15/01/2026
- Endereço preferido: Savassi

**Cliente: Maria Santos (5531988888888)**
- Prefere: Doces e geleias
- Frequência: Semanal
- Ticket médio: R$ 80
- Última compra: 08/02/2026
- Observação: Sempre pede entrega rápida (Lalamove)

### Padrões Identificados

#### Horários de Pico
- Manhã: 8h-10h (pedidos para entrega no almoço)
- Tarde: 14h-16h (pedidos para entrega à noite)
- Fim de semana: Sábado 10h-12h (pedidos grandes)

#### Produtos que Vendem Juntos
- Queijo + Doce de Leite (45% das vezes)
- Cachaça + Limão (30% das vezes)
- Café + Pão de Queijo (60% das vezes)

#### Comportamento de Compra
- 70% dos clientes compram 2-4 itens
- 20% compram apenas 1 item
- 10% compram 5+ itens (cestas/presentes)

### Problemas Comuns e Soluções

**Problema:** Cliente reclama de frete caro
**Solução:** Oferecer retirada na loja ou sugerir compra maior (frete grátis > R$ 150)

**Problema:** Produto em falta
**Solução:** Sugerir similar + avisar quando chegar

**Problema:** Dúvida sobre validade
**Solução:** Sempre informar validade + garantir qualidade

### Sazonalidade

**Janeiro-Fevereiro:** Queijos e doces (verão, turismo alto)
**Março-Maio:** Estável
**Junho-Julho:** Quentão, vinho quente, pamonha (festa junina)
**Agosto-Outubro:** Estável
**Novembro-Dezembro:** Cestas natalinas, tender, panetone

### Fornecedores Principais

- **Queijos:** Fazenda Serra Dourada (entrega terças e quintas)
- **Doces:** Dona Maria Artesanal (entrega sextas)
- **Cachaças:** Alambique Morro Azul (entrega quinzenal)
- **Cafés:** Cooperativa Café Montanhas (entrega semanais)

### Aprendizados

**#001 - 2026-01-15**
Cliente pediu "queijo do mato". Não encontramos porque buscamos literal. Aprendizado: "queijo do mato" = "queijo minas frescal"

**#002 - 2026-01-20**
Cliente desistiu da compra porque frete ficou caro (R$ 35 para Contagem). Solução: Oferecer PAC (mais barato) primeiro.

**#003 - 2026-02-05**
Cliente não sabia que tínhamos produtos veganos. Solução: Mencionar proativamente quando cliente busca produtos específicos.

---

## 🔄 Histórico de Alterações

### 2026-02-11
- Criação do sistema de memória
- Base de conhecimento inicial
- Estrutura GOTCHA implementada

---

## 📝 Como Usar Esta Memória

### Para Adicionar Conhecimento
```python
from memory import memory_write

memory_write(
    content="Cliente prefere queijos curados",
    type="preference",
    tags=["cliente:5531999999999", "queijos"]
)
```

### Para Buscar
```python
from memory import memory_search

results = memory_search("cliente:5531999999999 preferencias")
```

### Para Atualizar
Edite diretamente este arquivo ou use API de memória.

---

**Desenvolvido com ❤️ para a Roça Capital**
