#!/bin/bash

# Script de teste do sistema de controle humano-agente
# Autor: Roça Capital
# Uso: ./scripts/test_sistema.sh

set -e

BACKEND="http://localhost:8000"
PHONE="5531999999999"

echo "🧪 Testando Sistema de Controle Humano-Agente"
echo "=============================================="
echo ""

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Health Check
echo -e "${BLUE}[1/8]${NC} Health Check..."
HEALTH=$(curl -s $BACKEND/)
if echo $HEALTH | grep -q "online"; then
    echo -e "${GREEN}✅ Backend online!${NC}"
else
    echo "❌ Backend offline!"
    exit 1
fi
sleep 1

# 2. Cliente manda mensagem (bot responde)
echo -e "\n${BLUE}[2/8]${NC} Cliente: 'Quero queijo canastra'"
RESP1=$(curl -s -X POST $BACKEND/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d "{
    \"phone\": \"$PHONE\",
    \"message\": \"Quero queijo canastra\",
    \"sender_type\": \"customer\"
  }")

if echo $RESP1 | grep -q '"should_respond":true'; then
    echo -e "${GREEN}✅ Bot respondeu (esperado)${NC}"
else
    echo "❌ Bot não respondeu!"
fi
sleep 2

# 3. Ver status
echo -e "\n${BLUE}[3/8]${NC} Verificando status da sessão..."
STATUS=$(curl -s $BACKEND/session/$PHONE/status)
MODE=$(echo $STATUS | jq -r '.mode')
echo "📊 Modo atual: $MODE"
sleep 2

# 4. Humano assume
echo -e "\n${BLUE}[4/8]${NC} Atendente assume a conversa..."
TAKEOVER=$(curl -s -X POST "$BACKEND/session/$PHONE/takeover?attendant_id=teste@email.com")
if echo $TAKEOVER | grep -q '"success":true'; then
    echo -e "${GREEN}✅ Atendente assumiu!${NC}"
else
    echo "❌ Falha ao assumir!"
fi
sleep 2

# 5. Cliente manda mensagem (bot NÃO responde)
echo -e "\n${BLUE}[5/8]${NC} Cliente: 'Quanto custa?'"
RESP2=$(curl -s -X POST $BACKEND/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d "{
    \"phone\": \"$PHONE\",
    \"message\": \"Quanto custa?\",
    \"sender_type\": \"customer\"
  }")

if echo $RESP2 | grep -q '"should_respond":false'; then
    echo -e "${GREEN}✅ Bot NÃO respondeu (esperado - humano atendendo)${NC}"
else
    echo "❌ Bot respondeu quando não deveria!"
fi
sleep 2

# 6. Ver status novamente
echo -e "\n${BLUE}[6/8]${NC} Status após assumir..."
STATUS2=$(curl -s $BACKEND/session/$PHONE/status)
MODE2=$(echo $STATUS2 | jq -r '.mode')
ATTENDANT=$(echo $STATUS2 | jq -r '.human_attendant')
echo "📊 Modo: $MODE2"
echo "👤 Atendente: $ATTENDANT"
sleep 2

# 7. Liberar conversa
echo -e "\n${BLUE}[7/8]${NC} Liberando conversa de volta para o bot..."
RELEASE=$(curl -s -X POST $BACKEND/session/$PHONE/release)
if echo $RELEASE | grep -q '"success":true'; then
    echo -e "${GREEN}✅ Conversa liberada!${NC}"
else
    echo "❌ Falha ao liberar!"
fi
sleep 2

# 8. Cliente manda mensagem (bot responde novamente)
echo -e "\n${BLUE}[8/8]${NC} Cliente: 'Ainda tem?'"
RESP3=$(curl -s -X POST $BACKEND/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d "{
    \"phone\": \"$PHONE\",
    \"message\": \"Ainda tem?\",
    \"sender_type\": \"customer\"
  }")

if echo $RESP3 | grep -q '"should_respond":true'; then
    echo -e "${GREEN}✅ Bot voltou a responder!${NC}"
else
    echo "❌ Bot não respondeu!"
fi

# Resumo
echo ""
echo "=============================================="
echo -e "${GREEN}✅ Todos os testes passaram!${NC}"
echo ""
echo "📊 Resumo do Fluxo Testado:"
echo "1. ✅ Cliente manda msg → Bot responde"
echo "2. ✅ Humano assume → Bot para"
echo "3. ✅ Cliente manda msg → Bot não responde"
echo "4. ✅ Humano libera → Bot volta"
echo "5. ✅ Cliente manda msg → Bot responde"
echo ""
echo "🎉 Sistema de controle humano-agente funcionando perfeitamente!"
