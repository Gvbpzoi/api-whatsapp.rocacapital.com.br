"""
Script de teste para o FreteService (Lalamove + Correios + Nominatim).

Execução:
    cd backend
    python -m scripts.test_frete
"""
import asyncio
import os
import sys
from pathlib import Path

# Adicionar raiz ao path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv()

from loguru import logger
from src.services.frete_service import FreteService


async def test_nominatim():
    """Testa geocoding com Nominatim."""
    logger.info("=" * 60)
    logger.info("TESTE 1: Nominatim Geocoding")
    logger.info("=" * 60)

    from src.services.frete_service import NominatimClient
    client = NominatimClient()

    # Teste BH
    coords = await client.geocode("Savassi, Belo Horizonte, MG")
    if coords:
        logger.info(f"✅ Savassi, BH → lat={coords[0]}, lng={coords[1]}")
    else:
        logger.error("❌ Falha no geocoding de Savassi")

    # Teste São Paulo
    coords = await client.geocode("Rua Augusta, 500, São Paulo, SP")
    if coords:
        logger.info(f"✅ Rua Augusta, SP → lat={coords[0]}, lng={coords[1]}")
    else:
        logger.error("❌ Falha no geocoding de SP")

    return True


async def test_lalamove():
    """Testa cotação Lalamove."""
    logger.info("=" * 60)
    logger.info("TESTE 2: Lalamove Quotation (Sandbox)")
    logger.info("=" * 60)

    from src.services.frete_service import LalamoveClient
    client = LalamoveClient()

    if not client.api_key:
        logger.warning("⚠️ LALAMOVE_API_KEY não configurada, pulando teste")
        return False

    # Destino: Savassi (coordenadas aproximadas)
    result = await client.get_quotation(
        dest_lat="-19.9354",
        dest_lng="-43.9322",
        dest_address="Rua Pernambuco, 1000 - Savassi, Belo Horizonte",
    )

    if result:
        logger.info(f"✅ Lalamove cotação: R${result['preco']:.2f}")
        logger.info(f"   Quotation ID: {result.get('quotation_id', 'N/A')}")
    else:
        logger.error("❌ Falha na cotação Lalamove")

    return result is not None


async def test_correios():
    """Testa cálculo SEDEX Correios."""
    logger.info("=" * 60)
    logger.info("TESTE 3: Correios SEDEX")
    logger.info("=" * 60)

    from src.services.frete_service import CorreiosClient
    client = CorreiosClient()

    if not client.token:
        logger.warning("⚠️ CORREIOS_TOKEN não configurado, pulando teste")
        return False

    # Teste BH → BH (SEDEX rápido)
    result = await client.calcular_sedex("30160011", 1000)  # 1kg
    if result:
        logger.info(f"✅ SEDEX BH→BH: R${result['preco']:.2f}, {result['prazo_dias']} dias")
    else:
        logger.error("❌ Falha SEDEX BH→BH")

    # Teste BH → SP (SEDEX mais longe)
    result_sp = await client.calcular_sedex("01304001", 1000)  # 1kg
    if result_sp:
        logger.info(f"✅ SEDEX BH→SP: R${result_sp['preco']:.2f}, {result_sp['prazo_dias']} dias")
    else:
        logger.error("❌ Falha SEDEX BH→SP")

    return result is not None


async def test_frete_service_bh():
    """Testa FreteService com endereço em BH."""
    logger.info("=" * 60)
    logger.info("TESTE 4: FreteService - Endereço em BH com CEP")
    logger.info("=" * 60)

    service = FreteService()
    result = await service.calcular(
        endereco="Rua da Bahia, 1000 - Savassi, BH - 30160-011",
        valor_pedido=150.0,
        peso_kg=1.5,
    )

    logger.info(f"Endereço: {result['endereco']}")
    logger.info(f"Opções: {len(result['opcoes_frete'])}")
    for op in result["opcoes_frete"]:
        logger.info(f"  {op['nome']}: R${op['valor']:.2f} ({op['prazo']})")
        if "observacao" in op:
            logger.info(f"    Obs: {op['observacao']}")

    return len(result["opcoes_frete"]) > 0


async def test_frete_service_fora():
    """Testa FreteService com endereço fora de BH."""
    logger.info("=" * 60)
    logger.info("TESTE 5: FreteService - Endereço fora de BH (SP)")
    logger.info("=" * 60)

    service = FreteService()
    result = await service.calcular(
        endereco="Rua Augusta, 500 - São Paulo - 01304-001",
        valor_pedido=200.0,
        peso_kg=2.0,
    )

    logger.info(f"Endereço: {result['endereco']}")
    logger.info(f"Opções: {len(result['opcoes_frete'])}")
    for op in result["opcoes_frete"]:
        logger.info(f"  {op['nome']}: R${op['valor']:.2f} ({op['prazo']})")
        if "observacao" in op:
            logger.info(f"    Obs: {op['observacao']}")

    return len(result["opcoes_frete"]) > 0


async def test_frete_service_sem_cep():
    """Testa FreteService com endereço sem CEP."""
    logger.info("=" * 60)
    logger.info("TESTE 6: FreteService - Endereço sem CEP (só nome)")
    logger.info("=" * 60)

    service = FreteService()
    result = await service.calcular(
        endereco="Savassi, Belo Horizonte",
        valor_pedido=100.0,
        peso_kg=1.0,
    )

    logger.info(f"Endereço: {result['endereco']}")
    logger.info(f"Opções: {len(result['opcoes_frete'])}")
    for op in result["opcoes_frete"]:
        logger.info(f"  {op['nome']}: R${op['valor']:.2f} ({op['prazo']})")
        if "observacao" in op:
            logger.info(f"    Obs: {op['observacao']}")

    return len(result["opcoes_frete"]) > 0


async def main():
    """Executa todos os testes."""
    logger.info("🚀 Testando FreteService (Lalamove + Correios + Nominatim)")
    logger.info("")

    results = {}

    # Teste Nominatim
    try:
        results["nominatim"] = await test_nominatim()
    except Exception as e:
        logger.error(f"❌ Erro no teste Nominatim: {e}")
        results["nominatim"] = False

    # Teste Lalamove
    try:
        results["lalamove"] = await test_lalamove()
    except Exception as e:
        logger.error(f"❌ Erro no teste Lalamove: {e}")
        results["lalamove"] = False

    # Teste Correios
    try:
        results["correios"] = await test_correios()
    except Exception as e:
        logger.error(f"❌ Erro no teste Correios: {e}")
        results["correios"] = False

    # Teste FreteService BH
    try:
        results["frete_bh"] = await test_frete_service_bh()
    except Exception as e:
        logger.error(f"❌ Erro no teste FreteService BH: {e}")
        results["frete_bh"] = False

    # Teste FreteService fora
    try:
        results["frete_fora"] = await test_frete_service_fora()
    except Exception as e:
        logger.error(f"❌ Erro no teste FreteService fora: {e}")
        results["frete_fora"] = False

    # Teste FreteService sem CEP
    try:
        results["frete_sem_cep"] = await test_frete_service_sem_cep()
    except Exception as e:
        logger.error(f"❌ Erro no teste FreteService sem CEP: {e}")
        results["frete_sem_cep"] = False

    # Resumo
    logger.info("")
    logger.info("=" * 60)
    logger.info("📊 RESUMO DOS TESTES")
    logger.info("=" * 60)
    for nome, ok in results.items():
        status = "✅ PASS" if ok else "❌ FAIL"
        logger.info(f"  {status} - {nome}")

    total = len(results)
    ok_count = sum(1 for v in results.values() if v)
    logger.info(f"\n  {ok_count}/{total} testes passaram")


if __name__ == "__main__":
    asyncio.run(main())
