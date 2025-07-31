from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Twilio Configuration
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str
    
    # OpenAI Configuration
    openai_api_key: str
    
    # ElevenLabs Configuration
    elevenlabs_api_key: str
    
    # Database Configuration
    database_url: str
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    
    # Restaurant Configuration
    restaurant_name: str = "Sample Restaurant"
    restaurant_hours: str = "Monday-Sunday: 11:00 AM - 10:00 PM"
    human_fallback_number: Optional[str] = None
    
    # AI Configuration
    max_retry_attempts: int = 2
    call_recording_consent_text: str = "This call may be recorded for quality assurance and to help us provide better service."
    sms_consent_text: str = "Would you like to receive a text message confirmation of your reservation?"
    
    class Config:
        env_file = ".env"


settings = Settings() 