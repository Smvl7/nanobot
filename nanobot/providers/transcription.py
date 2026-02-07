"""Voice transcription provider using Groq."""

import os
from pathlib import Path
from typing import Any

import httpx
from loguru import logger


class CloudRuTranscriptionProvider:
    """
    Voice transcription provider using Cloud.ru Whisper API.
    """
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("CLOUDRU_API_KEY")
        self.api_url = "https://foundation-models.api.cloud.ru/v1/audio/transcriptions"
    
    async def transcribe(self, file_path: str | Path) -> str:
        """
        Transcribe an audio file using Cloud.ru.
        
        Args:
            file_path: Path to the audio file.
            
        Returns:
            Transcribed text.
        """
        if not self.api_key:
            logger.warning("Cloud.ru API key not configured for transcription")
            return ""
        
        path = Path(file_path)
        if not path.exists():
            logger.error(f"Audio file not found: {file_path}")
            return ""
        
        try:
            async with httpx.AsyncClient() as client:
                with open(path, "rb") as f:
                    files = {
                        "file": (path.name, f),
                        "model": (None, "openai/whisper-large-v3"),
                        "response_format": (None, "json"),
                        "language": (None, "ru"),
                        "temperature": (None, "0.2"),
                    }
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                    }
                    
                    response = await client.post(
                        self.api_url,
                        headers=headers,
                        files=files,
                        timeout=60.0
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Cloud.ru API error: {response.text}")
                        return ""
                        
                    data = response.json()
                    return data.get("text", "")
                    
        except Exception as e:
            logger.error(f"Cloud.ru transcription error: {e}")
            return ""


class GroqTranscriptionProvider:
    """
    Voice transcription provider using Groq's Whisper API.
    
    Groq offers extremely fast transcription with a generous free tier.
    """
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.api_url = "https://api.groq.com/openai/v1/audio/transcriptions"
    
    async def transcribe(self, file_path: str | Path) -> str:
        """
        Transcribe an audio file using Groq.
        
        Args:
            file_path: Path to the audio file.
            
        Returns:
            Transcribed text.
        """
        if not self.api_key:
            logger.warning("Groq API key not configured for transcription")
            return ""
        
        path = Path(file_path)
        if not path.exists():
            logger.error(f"Audio file not found: {file_path}")
            return ""
        
        try:
            async with httpx.AsyncClient() as client:
                with open(path, "rb") as f:
                    files = {
                        "file": (path.name, f),
                        "model": (None, "whisper-large-v3"),
                    }
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                    }
                    
                    response = await client.post(
                        self.api_url,
                        headers=headers,
                        files=files,
                        timeout=60.0
                    )
                    
                    response.raise_for_status()
                    data = response.json()
                    return data.get("text", "")
                    
        except Exception as e:
            logger.error(f"Groq transcription error: {e}")
            return ""
