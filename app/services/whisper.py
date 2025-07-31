import openai
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Configure OpenAI client
openai.api_key = settings.openai_api_key


class WhisperService:
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.openai_api_key)
    
    async def transcribe_audio(self, audio_data: bytes) -> str:
        """
        Transcribe audio data using OpenAI Whisper API
        """
        try:
            response = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=("audio.wav", audio_data, "audio/wav"),
                response_format="text"
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return ""
    
    async def transcribe_chunk(self, audio_chunk: bytes) -> str:
        """
        Transcribe a single audio chunk
        """
        try:
            response = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=("chunk.wav", audio_chunk, "audio/wav"),
                response_format="text"
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Error transcribing audio chunk: {e}")
            return "" 