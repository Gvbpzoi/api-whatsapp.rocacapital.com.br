"""
Media Processor: Processa áudio (Whisper), imagem (GPT-4o-mini vision) e PDF.
"""
import os
import tempfile
from typing import Optional
from loguru import logger
from openai import AsyncOpenAI
import httpx


class MediaProcessor:
    """Processa mensagens multimídia do WhatsApp."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def transcribe_audio(self, audio_url: str) -> str:
        """
        Baixa áudio e transcreve com Whisper.

        Args:
            audio_url: URL do áudio da ZAPI

        Returns:
            Texto transcrito
        """
        try:
            async with httpx.AsyncClient(timeout=30) as http:
                response = await http.get(audio_url)
                response.raise_for_status()
                audio_data = response.content

            # Salvar em arquivo temporário
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name

            try:
                with open(temp_path, "rb") as audio_file:
                    transcription = await self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="pt",
                    )
                return transcription.text
            finally:
                os.unlink(temp_path)

        except Exception as e:
            logger.error(f"Erro ao transcrever audio: {e}")
            return "[Nao foi possivel transcrever o audio]"

    async def analyze_image(self, image_url: str, caption: Optional[str] = None) -> str:
        """
        Analisa imagem com GPT-4o-mini vision.

        Args:
            image_url: URL da imagem
            caption: Legenda opcional do WhatsApp

        Returns:
            Descrição/análise da imagem
        """
        try:
            prompt = "O usuario enviou esta imagem. Descreva o que voce ve de forma util para um atendente de loja de queijos e produtos mineiros."
            if caption:
                prompt += f"\n\nMensagem do usuario junto a imagem: {caption}"

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                max_tokens=500,
            )
            return response.choices[0].message.content or "[Imagem analisada sem descricao]"

        except Exception as e:
            logger.error(f"Erro ao analisar imagem: {e}")
            return "[Nao foi possivel analisar a imagem]"

    async def extract_pdf_text(self, document_url: str) -> str:
        """
        Baixa PDF e extrai texto.

        Args:
            document_url: URL do documento da ZAPI

        Returns:
            Texto extraído do PDF
        """
        try:
            async with httpx.AsyncClient(timeout=30) as http:
                response = await http.get(document_url)
                response.raise_for_status()
                pdf_data = response.content

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(pdf_data)
                temp_path = f.name

            try:
                from PyPDF2 import PdfReader

                reader = PdfReader(temp_path)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text.strip() if text.strip() else "[PDF sem texto extraivel]"
            finally:
                os.unlink(temp_path)

        except ImportError:
            logger.error("PyPDF2 nao instalado - instale com: pip install PyPDF2")
            return "[Erro: PyPDF2 nao instalado]"
        except Exception as e:
            logger.error(f"Erro ao extrair PDF: {e}")
            return "[Nao foi possivel extrair texto do PDF]"
