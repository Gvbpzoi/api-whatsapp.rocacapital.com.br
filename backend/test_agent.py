"""
Script de teste para o agente WhatsApp
Simula conversas completas do cliente
"""

import requests
import json
from time import sleep

BASE_URL = "http://localhost:8000"

def send_message(phone: str, message: str, sender_type: str = "customer"):
    """Envia mensagem para o webhook"""
    payload = {
        "phone": phone,
        "message": message,
        "sender_type": sender_type
    }

    response = requests.post(f"{BASE_URL}/webhook/whatsapp", json=payload)
    return response.json()


def print_response(response: dict, message: str):
    """Imprime resposta formatada"""
    print(f"\n{'='*60}")
    print(f"👤 Cliente: {message}")
    print(f"{'='*60}")

    if response.get("should_respond"):
        print(f"🤖 Agente: {response.get('response', 'Sem resposta')}")
    else:
        print(f"⏸️  Agente pausado: {response.get('reason')}")

    print(f"📊 Modo: {response.get('session_mode')}")


def test_conversation_1():
    """Teste 1: Fluxo completo de compra"""
    print("\n" + "="*60)
    print("🧪 TESTE 1: Fluxo Completo de Compra")
    print("="*60)

    phone = "5531999999999"

    # 1. Saudação
    resp = send_message(phone, "Oi, bom dia!")
    print_response(resp, "Oi, bom dia!")
    sleep(1)

    # 2. Buscar produto
    resp = send_message(phone, "Quero queijo canastra")
    print_response(resp, "Quero queijo canastra")
    sleep(1)

    # 3. Adicionar ao carrinho
    resp = send_message(phone, "Adiciona 2 unidades")
    print_response(resp, "Adiciona 2 unidades")
    sleep(1)

    # 4. Ver carrinho
    resp = send_message(phone, "Ver meu carrinho")
    print_response(resp, "Ver meu carrinho")
    sleep(1)

    # 5. Finalizar pedido
    resp = send_message(phone, "Quero finalizar o pedido")
    print_response(resp, "Quero finalizar o pedido")
    sleep(1)


def test_conversation_2():
    """Teste 2: Busca de múltiplos produtos"""
    print("\n" + "="*60)
    print("🧪 TESTE 2: Busca de Produtos")
    print("="*60)

    phone = "5531988888888"

    # Buscar diferentes categorias
    termos = ["queijo", "cachaça", "doce de leite", "café"]

    for termo in termos:
        resp = send_message(phone, f"Tem {termo}?")
        print_response(resp, f"Tem {termo}?")
        sleep(1)


def test_conversation_3():
    """Teste 3: Consulta de pedidos"""
    print("\n" + "="*60)
    print("🧪 TESTE 3: Consulta de Pedidos")
    print("="*60)

    phone = "5531977777777"

    resp = send_message(phone, "Cadê meu pedido?")
    print_response(resp, "Cadê meu pedido?")


def test_human_takeover():
    """Teste 4: Takeover humano"""
    print("\n" + "="*60)
    print("🧪 TESTE 4: Human Takeover")
    print("="*60)

    phone = "5531966666666"

    # Mensagem inicial do cliente
    resp = send_message(phone, "Oi, preciso de ajuda")
    print_response(resp, "Oi, preciso de ajuda")
    sleep(1)

    # Humano assume
    print("\n👨 Humano assume a conversa...")
    takeover_resp = requests.post(
        f"{BASE_URL}/session/{phone}/takeover",
        params={"attendant_id": "joao@empresa.com"}
    )
    print(f"   Resultado: {takeover_resp.json()}")
    sleep(1)

    # Cliente envia nova mensagem (agente não deve responder)
    resp = send_message(phone, "Qual o prazo de entrega?")
    print_response(resp, "Qual o prazo de entrega?")
    sleep(1)

    # Humano libera
    print("\n👨 Humano libera conversa...")
    release_resp = requests.post(f"{BASE_URL}/session/{phone}/release")
    print(f"   Resultado: {release_resp.json()}")
    sleep(1)

    # Cliente envia mensagem (agente volta a responder)
    resp = send_message(phone, "Obrigado!")
    print_response(resp, "Obrigado!")


def check_server():
    """Verifica se servidor está rodando"""
    try:
        resp = requests.get(f"{BASE_URL}/")
        return resp.json().get("status") == "online"
    except:
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 TESTE DO AGENTE WHATSAPP")
    print("="*60)

    if not check_server():
        print("\n❌ Servidor não está rodando!")
        print("   Execute: cd backend && uvicorn src.api.main:app --reload")
        exit(1)

    print("\n✅ Servidor online!\n")

    # Executar testes
    try:
        test_conversation_1()
        sleep(2)

        test_conversation_2()
        sleep(2)

        test_conversation_3()
        sleep(2)

        test_human_takeover()

        print("\n" + "="*60)
        print("✅ TODOS OS TESTES CONCLUÍDOS!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
