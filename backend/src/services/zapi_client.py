"""
Cliente para integração com ZAPI (Z-API WhatsApp)
https://developer.z-api.io/
"""

import os
import requests
from typing import Dict, Any, Optional
from loguru import logger


class ZAPIClient:
    """
    Cliente para enviar mensagens via ZAPI.

    Documentação: https://developer.z-api.io/
    """

    def __init__(
        self,
        instance_id: Optional[str] = None,
        token: Optional[str] = None,
        base_url: str = "https://api.z-api.io"
    ):
        """
        Inicializa cliente ZAPI.

        Args:
            instance_id: ID da instância ZAPI (ou usa env ZAPI_INSTANCE_ID)
            token: Token da instância (ou usa env ZAPI_TOKEN)
            base_url: URL base da API
        """
        self.instance_id = instance_id or os.getenv("ZAPI_INSTANCE_ID")
        self.token = token or os.getenv("ZAPI_TOKEN")
        self.base_url = base_url

        if not self.instance_id or not self.token:
            logger.warning("⚠️ ZAPI credentials não configuradas")
        else:
            logger.info(f"✅ ZAPI Client inicializado: {self.instance_id[:8]}...")

    def _get_url(self, endpoint: str) -> str:
        """Constrói URL completa para endpoint."""
        return f"{self.base_url}/instances/{self.instance_id}/token/{self.token}/{endpoint}"

    def send_text(self, phone: str, message: str) -> Dict[str, Any]:
        """
        Envia mensagem de texto.

        Args:
            phone: Número do telefone (5531999999999)
            message: Texto da mensagem

        Returns:
            Resposta da API

        Example:
            >>> client = ZAPIClient()
            >>> result = client.send_text("5531999999999", "Olá!")
            >>> print(result)
            {"success": True, "messageId": "..."}
        """
        url = self._get_url("send-text")

        payload = {
            "phone": phone,
            "message": message
        }

        try:
            logger.info(f"📤 Enviando mensagem ZAPI para {phone[:8]}...")

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            data = response.json()
            logger.info(f"✅ Mensagem enviada com sucesso!")

            return {
                "success": True,
                "data": data
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao enviar mensagem ZAPI: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def send_image(
        self,
        phone: str,
        image_url: str,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envia imagem.

        Args:
            phone: Número do telefone
            image_url: URL da imagem
            caption: Legenda opcional

        Returns:
            Resposta da API
        """
        url = self._get_url("send-image")

        payload = {
            "phone": phone,
            "image": image_url
        }

        if caption:
            payload["caption"] = caption

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            return {
                "success": True,
                "data": response.json()
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao enviar imagem ZAPI: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def send_link(
        self,
        phone: str,
        url: str,
        title: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envia link com preview.

        Args:
            phone: Número do telefone
            url: URL do link
            title: Título do link
            description: Descrição opcional

        Returns:
            Resposta da API
        """
        endpoint = self._get_url("send-link")

        payload = {
            "phone": phone,
            "message": url,
            "image": "",
            "linkUrl": url,
            "title": title,
            "linkDescription": description or ""
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=10)
            response.raise_for_status()

            return {
                "success": True,
                "data": response.json()
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao enviar link ZAPI: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_instance_status(self) -> Dict[str, Any]:
        """
        Verifica status da instância.

        Returns:
            Status da instância (connected, disconnected, etc)
        """
        url = self._get_url("status")

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()

            return {
                "success": True,
                "status": data.get("connected", False),
                "data": data
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao verificar status ZAPI: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Singleton global
_zapi_client = None


def get_zapi_client() -> ZAPIClient:
    """Retorna instância global do cliente ZAPI."""
    global _zapi_client
    if _zapi_client is None:
        _zapi_client = ZAPIClient()
    return _zapi_client
