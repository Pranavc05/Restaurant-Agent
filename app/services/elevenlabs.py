import elevenlabs
from app.config import settings
import logging
import tempfile
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Configure ElevenLabs - API key is set via environment variable
import os
os.environ["ELEVEN_API_KEY"] = settings.elevenlabs_api_key


class ElevenLabsService:
    def __init__(self):
        self.voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice (professional, friendly)
        self.model_id = "eleven_monolingual_v1"
    
    async def text_to_speech(self, text: str, voice_id: Optional[str] = None) -> bytes:
        """
        Convert text to speech using ElevenLabs API
        """
        try:
            # Use default voice if none specified
            if not voice_id:
                voice_id = self.voice_id
            
            # Generate audio using the new API
            audio = elevenlabs.generate(
                text=text,
                voice=voice_id,
                model=self.model_id
            )
            
            return audio
            
        except Exception as e:
            logger.error(f"Error generating speech with ElevenLabs: {e}")
            # Return empty bytes if generation fails
            return b""
    
    async def save_audio_file(self, text: str, filename: str, voice_id: Optional[str] = None) -> str:
        """
        Convert text to speech and save to file
        """
        try:
            # Use default voice if none specified
            if not voice_id:
                voice_id = self.voice_id
            
            # Generate and save audio
            audio = elevenlabs.generate(
                text=text,
                voice=voice_id,
                model=self.model_id
            )
            
            # Save to file
            elevenlabs.save(audio, filename)
            
            return filename
            
        except Exception as e:
            logger.error(f"Error saving audio file: {e}")
            return ""
    
    def get_available_voices(self):
        """
        Get list of available voices
        """
        try:
            available_voices = elevenlabs.voices()
            return [{"id": voice.voice_id, "name": voice.name} for voice in available_voices]
        except Exception as e:
            logger.error(f"Error getting available voices: {e}")
            return []
    
    def set_voice(self, voice_id: str):
        """
        Set the default voice for the service
        """
        self.voice_id = voice_id 