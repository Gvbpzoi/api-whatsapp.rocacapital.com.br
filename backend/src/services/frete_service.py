"""
Serviço de Frete: Integração real com Lalamove e Correios SEDEX.
Usa Nominatim para geocoding (gratuito).

Fluxo:
1. Extrair CEP do endereço
2. Determinar região (BH metro ou fora)
3. Se BH: Lalamove (motoboy) + SEDEX
4. Se fora: só SEDEX
5. Fallback com valores estimados se API falhar
"""
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from typing import Dict, Any, Optional, Tuple, List

import httpx
from loguru import logger


# ==================== Constantes ====================

# Mercado Central de BH - Origem
ORIGIN_LAT = "-19.919044"
ORIGIN_LNG = "-43.938769"
ORIGIN_ADDRESS = "Av. Augusto de Lima, 744 - Centro, Belo Horizonte - MG"

# CEP Origem (Mercado Central)
CEP_ORIGEM = "30190922"

# Correios - Código SEDEX
SEDEX_CODE = "03220"

# Dimensões padrão do pacote (cm)
DEFAULT_COMPRIMENTO = 30
DEFAULT_ALTURA = 10
DEFAULT_LARGURA = 20

# CEPs da Região Metropolitana de BH
BH_CEP_RANGES = [
    (30000000, 31999999),  # BH
    (32000000, 32999999),  # Contagem
    (32600000, 32699999),  # Betim (subrange de Contagem)
    (33000000, 33199999),  # Santa Luzia
    (33200000, 33299999),  # Vespasiano
    (33800000, 33899999),  # Ribeirão das Neves
    (34000000, 34099999),  # Nova Lima
    (34500000, 34599999),  # Sabará
    (32400000, 32499999),  # Ibirité
]

# Bairros/cidades conhecidos de BH (fallback quando não tem CEP)
BH_KEYWORDS = [
    "belo horizonte", "bh", "savassi", "lourdes", "funcionarios",
    "centro", "pampulha", "serra", "sion", "santa efigenia",
    "gutierrez", "buritis", "belvedere", "mangabeiras", "anchieta",
    "santo antonio", "carmo", "cidade nova", "floresta", "horto",
    "santa tereza", "padre eustaquio", "carlos prates", "caiçara",
    "nova suiça", "barroca", "nova granada", "sagrada familia",
    "lagoinha", "barro preto", "santo agostinho", "cruzeiro",
    "contagem", "betim", "nova lima", "sabara", "santa luzia",
    "ibirite", "ribeirao das neves", "vespasiano",
]


# ==================== Nominatim (Geocoding) ====================

class NominatimClient:
    """Geocoding gratuito via OpenStreetMap Nominatim."""

    BASE_URL = "https://nominatim.openstreetmap.org/search"
    USER_AGENT = "RocaCapital/1.0 (sac@rocacapital.com.br)"

    async def geocode(self, endereco: str) -> Optional[Tuple[str, str]]:
        """
        Converte endereço em coordenadas (lat, lng).

        Returns:
            Tuple (lat, lng) como strings, ou None se falhar.
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    self.BASE_URL,
                    params={
                        "q": endereco,
                        "format": "json",
                        "limit": 1,
                        "countrycodes": "br",
                    },
                    headers={"User-Agent": self.USER_AGENT},
                )
                response.raise_for_status()
                data = response.json()

                if data and len(data) > 0:
                    lat = data[0]["lat"]
                    lng = data[0]["lon"]
                    logger.debug(f"Geocoding '{endereco}' → ({lat}, {lng})")
                    return (str(lat), str(lng))

                logger.warning(f"Geocoding sem resultado para: {endereco}")
                return None

        except Exception as e:
            logger.error(f"Erro no geocoding: {e}")
            return None


# ==================== Lalamove ====================

class LalamoveClient:
    """Cliente para API Lalamove (cotação de entrega)."""

    def __init__(self):
        self.api_key = os.getenv("LALAMOVE_API_KEY", "")
        self.api_secret = os.getenv("LALAMOVE_API_SECRET", "")
        self.base_url = os.getenv("LALAMOVE_BASE_URL", "https://rest.sandbox.lalamove.com")
        self.market = "BR"

        if not self.api_key or not self.api_secret:
            logger.warning("LALAMOVE_API_KEY/SECRET não configuradas - cotação Lalamove desabilitada")

    def _sign_request(self, method: str, path: str, body: str) -> Dict[str, str]:
        """
        Gera headers com HMAC-SHA256 para autenticação Lalamove.

        Formato: {timestamp}\r\n{method}\r\n{path}\r\n\r\n{body}
        """
        timestamp = str(int(time.time() * 1000))
        raw_signature = f"{timestamp}\r\n{method}\r\n{path}\r\n\r\n{body}"

        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            raw_signature.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        token = f"{self.api_key}:{timestamp}:{signature}"

        return {
            "Authorization": f"hmac {token}",
            "Content-Type": "application/json",
            "Market": self.market,
            "Request-ID": str(uuid.uuid4()),
        }

    async def get_quotation(
        self, dest_lat: str, dest_lng: str, dest_address: str
    ) -> Optional[Dict[str, Any]]:
        """
        Solicita cotação de entrega Lalamove.

        Args:
            dest_lat: Latitude do destino
            dest_lng: Longitude do destino
            dest_address: Endereço de destino (texto)

        Returns:
            Dict com preço e detalhes, ou None se falhar.
        """
        if not self.api_key or not self.api_secret:
            return None

        path = "/v3/quotations"
        payload = {
            "data": {
                "serviceType": "LALAGO",
                "language": "pt_BR",
                "specialRequests": ["THERMAL_BAG_1"],
                "stops": [
                    {
                        "coordinates": {"lat": ORIGIN_LAT, "lng": ORIGIN_LNG},
                        "address": ORIGIN_ADDRESS,
                    },
                    {
                        "coordinates": {"lat": dest_lat, "lng": dest_lng},
                        "address": dest_address,
                    },
                ],
                "isRouteOptimized": False,
            }
        }

        body = json.dumps(payload, separators=(",", ":"))
        headers = self._sign_request("POST", path, body)
        url = f"{self.base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(url, content=body, headers=headers)

                if response.status_code in (200, 201):
                    data = response.json()
                    # Extrair preço da resposta
                    total_fee = data.get("data", {}).get("priceBreakdown", {}).get("total", "0")
                    currency = data.get("data", {}).get("priceBreakdown", {}).get("currency", "BRL")

                    logger.info(f"Lalamove cotação: R${total_fee} {currency}")

                    return {
                        "preco": float(total_fee),
                        "currency": currency,
                        "quotation_id": data.get("data", {}).get("quotationId", ""),
                        "raw": data,
                    }
                else:
                    error_body = response.text
                    logger.error(
                        f"Lalamove API erro {response.status_code}: {error_body}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Erro na cotação Lalamove: {e}")
            return None


# ==================== Correios ====================

class CorreiosClient:
    """Cliente para API Correios (cálculo de frete SEDEX)."""

    BASE_URL_PRECO = "https://api.correios.com.br/preco/v1/nacional"
    BASE_URL_PRAZO = "https://api.correios.com.br/prazo/v1/nacional"

    def __init__(self):
        self.token = os.getenv("CORREIOS_TOKEN", "")
        self.cep_origem = os.getenv("CORREIOS_CEP_ORIGEM", CEP_ORIGEM)

        if not self.token:
            logger.warning("CORREIOS_TOKEN não configurado - cálculo Correios desabilitado")

    async def calcular_sedex(
        self, cep_destino: str, peso_gramas: int
    ) -> Optional[Dict[str, Any]]:
        """
        Calcula frete SEDEX via API Correios.

        Args:
            cep_destino: CEP de destino (8 dígitos, sem hífen)
            peso_gramas: Peso em gramas

        Returns:
            Dict com preço e prazo, ou None se falhar.
        """
        if not self.token:
            return None

        # Garantir CEP limpo (só dígitos)
        cep_limpo = re.sub(r"\D", "", cep_destino)
        if len(cep_limpo) != 8:
            logger.error(f"CEP inválido: {cep_destino}")
            return None

        # Peso mínimo 300g para Correios
        peso = max(peso_gramas, 300)

        # Produto vai no path, não no query params
        url_preco = f"{self.BASE_URL_PRECO}/{SEDEX_CODE}"

        params_preco = {
            "cepOrigem": self.cep_origem,
            "cepDestino": cep_limpo,
            "psObjeto": str(peso),
            "comprimento": str(DEFAULT_COMPRIMENTO),
            "altura": str(DEFAULT_ALTURA),
            "largura": str(DEFAULT_LARGURA),
            "tpObjeto": "2",  # Pacote
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Buscar preço
                response = await client.get(
                    url_preco, params=params_preco, headers=headers
                )

                preco = 0.0
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        item = data[0]
                    else:
                        item = data
                    preco_str = item.get("pcFinal", item.get("pcBase", "0"))
                    preco = float(str(preco_str).replace(",", "."))
                else:
                    logger.error(
                        f"Correios preço erro {response.status_code}: {response.text}"
                    )
                    return None

                # Buscar prazo
                prazo = 0
                try:
                    url_prazo = f"{self.BASE_URL_PRAZO}/{SEDEX_CODE}"
                    params_prazo = {
                        "cepOrigem": self.cep_origem,
                        "cepDestino": cep_limpo,
                    }
                    resp_prazo = await client.get(
                        url_prazo, params=params_prazo, headers=headers
                    )
                    if resp_prazo.status_code == 200:
                        data_prazo = resp_prazo.json()
                        if isinstance(data_prazo, list) and len(data_prazo) > 0:
                            prazo = int(data_prazo[0].get("prazoEntrega", 0) or 0)
                        else:
                            prazo = int(data_prazo.get("prazoEntrega", 0) or 0)
                    else:
                        logger.warning(
                            f"Correios prazo erro {resp_prazo.status_code}: {resp_prazo.text[:200]}"
                        )
                except Exception as e:
                    logger.warning(f"Erro ao buscar prazo Correios: {e}")

                logger.info(
                    f"Correios SEDEX {cep_limpo}: R${preco:.2f}, {prazo} dias"
                )

                return {
                    "preco": preco,
                    "prazo_dias": prazo,
                    "raw": data,
                }

        except Exception as e:
            logger.error(f"Erro no cálculo Correios: {e}")
            return None


# ==================== FreteService (Orquestrador) ====================

class FreteService:
    """
    Orquestrador de cálculo de frete.

    Decide qual API chamar com base na localização:
    - BH metro → Lalamove (motoboy) + Correios SEDEX
    - Fora de BH → Correios SEDEX apenas
    """

    def __init__(self):
        self.nominatim = NominatimClient()
        self.lalamove = LalamoveClient()
        self.correios = CorreiosClient()
        logger.info("FreteService inicializado")

    @staticmethod
    def _extrair_cep(endereco: str) -> Optional[str]:
        """Extrai CEP (8 dígitos) de um endereço."""
        match = re.search(r"(\d{5})-?(\d{3})", endereco)
        if match:
            return match.group(1) + match.group(2)
        return None

    @staticmethod
    def _eh_bh_metro(cep: Optional[str] = None, endereco: str = "") -> bool:
        """
        Verifica se o endereço está na região metropolitana de BH.
        Usa CEP (prioritário) ou keywords no endereço.
        """
        # Prioridade: CEP
        if cep:
            cep_num = int(cep)
            for inicio, fim in BH_CEP_RANGES:
                if inicio <= cep_num <= fim:
                    return True
            return False

        # Fallback: keywords
        endereco_lower = endereco.lower()
        return any(kw in endereco_lower for kw in BH_KEYWORDS)

    async def calcular(
        self,
        endereco: str,
        valor_pedido: float = 0,
        peso_kg: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Calcula opções de frete para um endereço.

        Args:
            endereco: Endereço completo ou CEP
            valor_pedido: Valor total do pedido (R$)
            peso_kg: Peso total em kg

        Returns:
            Dict com opcoes_frete, endereco, mensagem
        """
        cep = self._extrair_cep(endereco)
        eh_bh = self._eh_bh_metro(cep=cep, endereco=endereco)
        peso_gramas = int(peso_kg * 1000)

        logger.info(
            f"Calculando frete: endereco='{endereco[:50]}', "
            f"cep={cep}, bh={eh_bh}, peso={peso_kg}kg"
        )

        opcoes: List[Dict[str, Any]] = []

        if eh_bh:
            # BH Metro: Lalamove + SEDEX
            lalamove_result = await self._cotar_lalamove(endereco)
            if lalamove_result:
                opcoes.append(lalamove_result)
            else:
                # Fallback Lalamove
                opcoes.append(self._fallback_lalamove(peso_kg))

            # SEDEX (se tem CEP)
            if cep:
                sedex_result = await self._cotar_sedex(cep, peso_gramas)
                if sedex_result:
                    opcoes.append(sedex_result)
                else:
                    opcoes.append(self._fallback_sedex_bh(peso_kg))
            else:
                opcoes.append(self._fallback_sedex_bh(peso_kg))

        else:
            # Fora de BH: só SEDEX
            if cep:
                sedex_result = await self._cotar_sedex(cep, peso_gramas)
                if sedex_result:
                    # Verificar prazo > 3 dias
                    if sedex_result.get("prazo_dias", 0) > 3:
                        sedex_result["observacao"] = (
                            "Atenção: prazo superior a 3 dias. "
                            "Não enviamos queijo com prazo maior que 3 dias úteis."
                        )
                    opcoes.append(sedex_result)
                else:
                    opcoes.append(self._fallback_sedex_fora(peso_kg))
            else:
                opcoes.append(self._fallback_sedex_fora(peso_kg))

        # Arredondar valores
        for op in opcoes:
            if "valor" in op:
                op["valor"] = round(op["valor"], 2)

        return {
            "endereco": endereco,
            "opcoes_frete": opcoes,
            "mensagem": "Frete calculado com sucesso",
        }

    async def _cotar_lalamove(self, endereco: str) -> Optional[Dict[str, Any]]:
        """Cota entrega Lalamove com geocoding."""
        # Geocodificar destino
        coords = await self.nominatim.geocode(endereco)
        if not coords:
            logger.warning("Geocoding falhou, tentando com 'Belo Horizonte' no endereço")
            # Retry com cidade explícita
            coords = await self.nominatim.geocode(f"{endereco}, Belo Horizonte, MG")

        if not coords:
            logger.warning("Geocoding falhou totalmente para Lalamove")
            return None

        lat, lng = coords

        # Cotar no Lalamove
        result = await self.lalamove.get_quotation(lat, lng, endereco)
        if not result:
            return None

        return {
            "tipo": "lalamove",
            "nome": "Motoboy (Lalamove)",
            "valor": result["preco"],
            "prazo": "45 minutos a 1 hora",
            "observacao": "Entrega no mesmo dia para pedidos até 16h",
        }

    async def _cotar_sedex(
        self, cep: str, peso_gramas: int
    ) -> Optional[Dict[str, Any]]:
        """Cota SEDEX via Correios."""
        result = await self.correios.calcular_sedex(cep, peso_gramas)
        if not result:
            return None

        prazo_dias = result["prazo_dias"]
        prazo_texto = (
            f"{prazo_dias} dia útil" if prazo_dias == 1 else f"{prazo_dias} dias úteis"
        )

        opcao: Dict[str, Any] = {
            "tipo": "correios_sedex",
            "nome": "Correios SEDEX",
            "valor": result["preco"],
            "prazo": prazo_texto,
            "prazo_dias": prazo_dias,
        }

        return opcao

    # ==================== Fallbacks ====================

    @staticmethod
    def _fallback_lalamove(peso_kg: float) -> Dict[str, Any]:
        """Valor estimado para Lalamove quando API falha."""
        valor = 15.00 + (peso_kg * 2.5)
        logger.warning(f"Usando fallback Lalamove: R${valor:.2f}")
        return {
            "tipo": "lalamove",
            "nome": "Motoboy (Lalamove)",
            "valor": round(valor, 2),
            "prazo": "45 minutos a 1 hora",
            "observacao": "Valor estimado (cotação real indisponível no momento)",
        }

    @staticmethod
    def _fallback_sedex_bh(peso_kg: float) -> Dict[str, Any]:
        """Valor estimado para SEDEX BH quando API falha."""
        valor = 25.00 + (peso_kg * 4.0)
        logger.warning(f"Usando fallback SEDEX BH: R${valor:.2f}")
        return {
            "tipo": "correios_sedex",
            "nome": "Correios SEDEX",
            "valor": round(valor, 2),
            "prazo": "1-2 dias úteis",
            "observacao": "Valor estimado (cotação real indisponível no momento)",
        }

    @staticmethod
    def _fallback_sedex_fora(peso_kg: float) -> Dict[str, Any]:
        """Valor estimado para SEDEX fora de BH quando API falha."""
        valor = 35.00 + (peso_kg * 5.0)
        logger.warning(f"Usando fallback SEDEX fora: R${valor:.2f}")
        return {
            "tipo": "correios_sedex",
            "nome": "Correios SEDEX",
            "valor": round(valor, 2),
            "prazo": "2-4 dias úteis",
            "observacao": "Valor estimado. Não enviamos queijo se prazo > 3 dias.",
        }


# ==================== Singleton ====================

_frete_service: Optional[FreteService] = None


def get_frete_service() -> FreteService:
    """Retorna instância singleton do FreteService."""
    global _frete_service
    if _frete_service is None:
        _frete_service = FreteService()
    return _frete_service
