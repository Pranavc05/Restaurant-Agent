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
    restaurant_name: str = "Bella Vista Italian Restaurant"
    restaurant_hours: str = "Monday-Sunday: 11:00 AM - 10:00 PM"
    restaurant_address: str = "123 Main Street, Downtown, CA 90210"
    restaurant_phone: str = "(555) 123-4567"
    restaurant_website: str = "www.bellavista.com"
    human_fallback_number: Optional[str] = None
    
    # Menu Information (for AI responses)
    restaurant_menu: str = """
    APPETIZERS:
    - Bruschetta ($12) - Toasted bread with fresh tomatoes, basil, and mozzarella
    - Calamari ($16) - Crispy fried squid with marinara sauce
    - Caprese Salad ($14) - Fresh mozzarella, tomatoes, and basil
    
    PASTAS:
    - Spaghetti Carbonara ($22) - Pasta with eggs, cheese, pancetta, and black pepper
    - Fettuccine Alfredo ($20) - Pasta with creamy parmesan sauce
    - Penne Arrabbiata ($18) - Spicy tomato sauce with garlic and red chili
    
    MAIN COURSES:
    - Chicken Parmesan ($28) - Breaded chicken with marinara and mozzarella
    - Grilled Salmon ($32) - Fresh salmon with seasonal vegetables
    - Beef Tenderloin ($38) - 8oz tenderloin with roasted potatoes
    
    DESSERTS:
    - Tiramisu ($12) - Classic Italian coffee-flavored dessert
    - Cannoli ($10) - Crispy shells filled with sweet ricotta
    - Gelato ($8) - House-made Italian ice cream
    """
    
    # Special Features
    restaurant_features: str = """
    - Private dining room available for groups of 8-20 people
    - Outdoor patio seating (weather permitting)
    - Full bar with extensive wine list
    - Live music on Friday and Saturday evenings
    - Catering services available for events
    - Happy hour Monday-Friday 4-6 PM
    - Kids menu available
    - Vegetarian and gluten-free options
    """
    
    # AI Configuration
    max_retry_attempts: int = 2
    call_recording_consent_text: str = "This call may be recorded for quality assurance and to help us provide better service."
    sms_consent_text: str = "Would you like to receive a text message confirmation of your reservation?"
    
    class Config:
        env_file = ".env"


settings = Settings() 