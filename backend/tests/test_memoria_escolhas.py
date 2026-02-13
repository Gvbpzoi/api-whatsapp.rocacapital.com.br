"""
Testes para verificar sistema de memória de escolhas e contexto conversacional.
Valida correções dos bugs de alucinação.
"""

import sys
import os

# Adicionar path do backend ao PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.session_manager import SessionManager
from src.orchestrator.intent_classifier import IntentClassifier


def test_contexto_conversacional():
    """Testa salvamento e recuperação de contexto conversacional."""
    print("\n🧪 Teste 1: Contexto Conversacional")
    print("=" * 60)
    
    manager = SessionManager()
    phone = "5531999999999"
    
    # Salvar contexto
    produtos = [
        {"id": "1", "nome": "Azeite Extra Virgem", "categoria": "azeites"},
        {"id": "2", "nome": "Azeite de Oliva", "categoria": "azeites"}
    ]
    
    manager.set_conversation_subject(
        phone=phone,
        termo="azeite",
        produtos_ids=["1", "2"],
        produtos=produtos
    )
    
    # Recuperar contexto
    context = manager.get_conversation_subject(phone)
    
    assert context is not None, "❌ Contexto não foi salvo"
    assert context["termo"] == "azeite", "❌ Termo incorreto"
    assert context["categoria"] == "azeites", "❌ Categoria incorreta"
    assert len(context["produtos"]) == 2, "❌ Produtos incorretos"
    
    print("✅ Contexto salvo e recuperado corretamente")
    print(f"   Termo: {context['termo']}")
    print(f"   Categoria: {context['categoria']}")
    print(f"   Produtos: {len(context['produtos'])}")


def test_memoria_escolhas():
    """Testa memória de escolhas por categoria."""
    print("\n🧪 Teste 2: Memória de Escolhas")
    print("=" * 60)
    
    manager = SessionManager()
    phone = "5531999999999"
    
    # Adicionar escolhas de diferentes categorias
    azeite = {
        "id": "1",
        "nome": "Azeite Extra Virgem Mineiro 250ml",
        "preco": 42.00,
        "categoria": "azeites"
    }
    
    queijo = {
        "id": "2",
        "nome": "Queijo Canastra Meia-Cura 500g",
        "preco": 45.00,
        "categoria": "queijos"
    }
    
    # Salvar escolhas
    manager.save_product_choice(phone, azeite, quantidade=2)
    manager.save_product_choice(phone, queijo, quantidade=1)
    
    # Recuperar escolhas
    choice_azeite = manager.get_last_choice_by_category(phone, "azeites")
    choice_queijo = manager.get_last_choice_by_category(phone, "queijos")
    
    assert choice_azeite is not None, "❌ Escolha de azeite não foi salva"
    assert choice_queijo is not None, "❌ Escolha de queijo não foi salva"
    
    assert choice_azeite["produto"]["nome"] == azeite["nome"], "❌ Azeite incorreto"
    assert choice_queijo["produto"]["nome"] == queijo["nome"], "❌ Queijo incorreto"
    
    assert choice_azeite["quantidade_total"] == 2, "❌ Quantidade de azeite incorreta"
    assert choice_queijo["quantidade_total"] == 1, "❌ Quantidade de queijo incorreta"
    
    print("✅ Escolhas salvas corretamente")
    print(f"   Azeites: {choice_azeite['produto']['nome']} (qty: {choice_azeite['quantidade_total']})")
    print(f"   Queijos: {choice_queijo['produto']['nome']} (qty: {choice_queijo['quantidade_total']})")
    
    # Testar atualização de quantidade
    manager.save_product_choice(phone, azeite, quantidade=1)
    choice_azeite_updated = manager.get_last_choice_by_category(phone, "azeites")
    
    assert choice_azeite_updated["quantidade_total"] == 3, "❌ Quantidade não foi atualizada"
    
    print("✅ Quantidade atualizada corretamente (2 + 1 = 3)")


def test_inferir_categoria():
    """Testa inferência de categoria por termo."""
    print("\n🧪 Teste 3: Inferência de Categoria")
    print("=" * 60)
    
    manager = SessionManager()
    
    # Testar inferência por termo
    testes = [
        ("azeite", "azeites"),
        ("azeites", "azeites"),
        ("queijo", "queijos"),
        ("queijos", "queijos"),
        ("café", "cafes"),
        ("vinho", "vinhos"),
        ("cachaça", "cachacas"),
    ]
    
    for termo, categoria_esperada in testes:
        categoria = manager._infer_category_from_term(termo)
        assert categoria == categoria_esperada, f"❌ {termo} → {categoria} (esperado: {categoria_esperada})"
        print(f"✅ {termo:15} → {categoria}")


def test_buscar_escolha_por_termo():
    """Testa busca de escolha por termo."""
    print("\n🧪 Teste 4: Buscar Escolha por Termo")
    print("=" * 60)
    
    manager = SessionManager()
    phone = "5531999999999"
    
    # Salvar escolha
    azeite = {
        "id": "1",
        "nome": "Azeite Extra Virgem",
        "categoria": "azeites"
    }
    manager.save_product_choice(phone, azeite, quantidade=1)
    
    # Buscar por diferentes termos
    termos = ["azeite", "azeites"]
    
    for termo in termos:
        choice = manager.get_last_choice_by_term(phone, termo)
        assert choice is not None, f"❌ Não encontrou escolha para '{termo}'"
        assert choice["produto"]["nome"] == azeite["nome"], f"❌ Produto incorreto para '{termo}'"
        print(f"✅ Termo '{termo}' encontrou: {choice['produto']['nome']}")


def test_extract_search_term():
    """Testa extração de termo de busca (com novas stop_words)."""
    print("\n🧪 Teste 5: Extração de Termo de Busca")
    print("=" * 60)
    
    classifier = IntentClassifier()
    
    testes = [
        ("pode mostrar os que você tem?", None),  # "você" agora é stop_word
        ("tem azeite?", "azeite"),
        ("quero queijo canastra", "queijo canastra"),
        ("dois azeites", "dois azeites"),  # mantém número
        ("tem mais?", ""),  # só sobra palavras vazias
    ]
    
    for mensagem, esperado in testes:
        termo = classifier.extract_search_term(mensagem)
        # Aceitar None ou string vazia para casos que não devem retornar termo
        if esperado is None or esperado == "":
            assert not termo or termo.strip() == "", f"❌ '{mensagem}' → '{termo}' (esperado: vazio)"
        else:
            assert termo == esperado, f"❌ '{mensagem}' → '{termo}' (esperado: '{esperado}')"
        
        print(f"✅ '{mensagem}' → '{termo or '(vazio)'}'")


def test_classificacao_com_contexto():
    """Testa classificação de intent com contexto."""
    print("\n🧪 Teste 6: Classificação com Contexto")
    print("=" * 60)
    
    classifier = IntentClassifier()
    
    # Teste 1: "pode mostrar os que você tem?" deve ser busca_produto
    mensagem = "pode mostrar os que você tem?"
    intent = classifier.classify(mensagem)
    
    print(f"Mensagem: '{mensagem}'")
    print(f"Intent: {intent}")
    
    assert intent == "busca_produto", f"❌ Intent incorreto: {intent} (esperado: busca_produto)"
    print("✅ Classificado corretamente como busca_produto")
    
    # Teste 2: Com contexto de azeite
    context = {
        "assunto": "azeite",
        "categoria": "azeites",
        "produtos_mostrados": 5
    }
    
    intent_contextual = classifier.classify("tem mais?", context=context)
    print(f"\nMensagem: 'tem mais?' (contexto: azeite)")
    print(f"Intent: {intent_contextual}")
    
    assert intent_contextual == "busca_produto", f"❌ Intent incorreto com contexto: {intent_contextual}"
    print("✅ Classificado corretamente com contexto")


def test_cenario_completo():
    """Testa cenário completo: busca → adiciona → muda assunto → volta."""
    print("\n🧪 Teste 7: Cenário Completo (Bug Original)")
    print("=" * 60)
    
    manager = SessionManager()
    classifier = IntentClassifier()
    phone = "5531999999999"
    
    print("\n1️⃣ Cliente busca azeite")
    produtos_azeite = [
        {"id": "1", "nome": "Azeite Extra Virgem", "categoria": "azeites"},
        {"id": "2", "nome": "Azeite de Oliva", "categoria": "azeites"}
    ]
    manager.set_conversation_subject(phone, "azeite", ["1", "2"], produtos_azeite)
    print("   ✅ Contexto salvo: azeite")
    
    print("\n2️⃣ Cliente escolhe produto #1")
    manager.save_product_choice(phone, produtos_azeite[0], quantidade=2)
    print("   ✅ Escolha salva: Azeite Extra Virgem (qty: 2)")
    
    print("\n3️⃣ Cliente fala sobre vinhos")
    produtos_vinho = [
        {"id": "3", "nome": "Vinho Tinto", "categoria": "vinhos"}
    ]
    manager.set_conversation_subject(phone, "vinho", ["3"], produtos_vinho)
    print("   ✅ Contexto atualizado: vinho")
    
    print("\n4️⃣ Cliente volta ao azeite: 'coloca mais um azeite'")
    choice = manager.get_last_choice_by_term(phone, "azeite")
    
    assert choice is not None, "❌ Não encontrou escolha anterior de azeite"
    assert choice["produto"]["nome"] == "Azeite Extra Virgem", "❌ Produto incorreto"
    
    print(f"   ✅ Sistema lembrou: {choice['produto']['nome']}")
    print(f"   ✅ Quantidade anterior: {choice['quantidade_total']}")
    
    print("\n5️⃣ Sistema adiciona e atualiza quantidade")
    manager.save_product_choice(phone, choice["produto"], quantidade=1)
    choice_updated = manager.get_last_choice_by_term(phone, "azeite")
    
    assert choice_updated["quantidade_total"] == 3, "❌ Quantidade não foi atualizada"
    print(f"   ✅ Nova quantidade: {choice_updated['quantidade_total']} (2 + 1)")
    
    print("\n✅ Cenário completo passou! Bug corrigido.")


def run_all_tests():
    """Executa todos os testes."""
    print("\n" + "=" * 60)
    print("🚀 TESTES DE MEMÓRIA DE ESCOLHAS E CONTEXTO CONVERSACIONAL")
    print("=" * 60)
    
    try:
        test_contexto_conversacional()
        test_memoria_escolhas()
        test_inferir_categoria()
        test_buscar_escolha_por_termo()
        test_extract_search_term()
        test_classificacao_com_contexto()
        test_cenario_completo()
        
        print("\n" + "=" * 60)
        print("✅ TODOS OS TESTES PASSARAM!")
        print("=" * 60)
        print("\n🎉 Sistema de memória de escolhas funcionando corretamente.")
        print("🐛 Bugs de alucinação corrigidos.")
        
    except AssertionError as e:
        print(f"\n❌ TESTE FALHOU: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
