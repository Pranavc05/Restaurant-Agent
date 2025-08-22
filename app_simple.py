from fastapi import FastAPI, Request, Form
from fastapi.responses import Response, JSONResponse
import os
import json
import logging
import re
import time
from typing import Optional, Dict, List
from collections import defaultdict
from pydantic import BaseModel
import openai
from elevenlabs import generate, save
import elevenlabs

# Database imports
try:
    from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker, relationship
    from sqlalchemy.sql import func
    import psycopg2
    DATABASE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Database dependencies not available: {e}")
    DATABASE_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Restaurant Agent")

# Load environment variables
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
RESTAURANT_NAME = os.environ.get("RESTAURANT_NAME", "Bella Vista Italian Restaurant")

# Twilio (optional; used for SMS)
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

# Database configuration
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Guarded Twilio import
try:
    from twilio.rest import Client as TwilioClient
    _twilio_import_ok = True
except Exception:
    TwilioClient = None
    _twilio_import_ok = False

# Database setup
engine = None
SessionLocal = None
Base = None

if DATABASE_AVAILABLE and DATABASE_URL:
    try:
        Base = declarative_base()
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logger.info("Database connection established")
    except Exception as e:
        logger.warning(f"Database connection failed: {e}")
        DATABASE_AVAILABLE = False
else:
    logger.info("Database not configured - using in-memory storage")

# Database models (only if database is available)
if DATABASE_AVAILABLE and Base is not None:
    class Call(Base):
        __tablename__ = "calls"
        
        id = Column(Integer, primary_key=True, index=True)
        call_sid = Column(String, unique=True, index=True)
        from_number = Column(String, index=True)
        to_number = Column(String)
        start_time = Column(DateTime(timezone=True), server_default=func.now())
        end_time = Column(DateTime(timezone=True), nullable=True)
        duration = Column(Float, nullable=True)
        escalated = Column(Boolean, default=False)
        status = Column(String, default="in-progress")
        
        # Relationships
        transcripts = relationship("Transcript", back_populates="call")
        reservations = relationship("Reservation", back_populates="call")

    class Transcript(Base):
        __tablename__ = "transcripts"
        
        id = Column(Integer, primary_key=True, index=True)
        call_id = Column(Integer, ForeignKey("calls.id"))
        timestamp = Column(DateTime(timezone=True), server_default=func.now())
        speaker = Column(String)  # "customer" or "ai"
        message = Column(Text)
        confidence = Column(Float, nullable=True)
        
        # Relationships
        call = relationship("Call", back_populates="transcripts")

    class Reservation(Base):
        __tablename__ = "reservations"
        
        id = Column(Integer, primary_key=True, index=True)
        call_id = Column(Integer, ForeignKey("calls.id"))
        customer_name = Column(String)
        customer_phone = Column(String, index=True)
        party_size = Column(Integer)
        reservation_date = Column(DateTime(timezone=True))
        reservation_time = Column(String)
        status = Column(String, default="confirmed")
        sms_consent = Column(Boolean, default=False)
        sms_sent = Column(Boolean, default=False)
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        
        # Relationships
        call = relationship("Call", back_populates="reservations")

    # Create tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.warning(f"Could not create database tables: {e}")
        DATABASE_AVAILABLE = False

# Language detection function
def detect_language(text):
    """
    Detect language from customer input using keyword patterns and OpenAI
    """
    text_lower = text.lower()
    
    # Quick pattern-based detection for common languages
    for lang_code, patterns in LANGUAGE_PATTERNS.items():
        matches = sum(1 for pattern in patterns if pattern in text_lower)
        if matches >= 1:  # If we find at least one keyword match
            return lang_code
    
    # Fallback to OpenAI language detection for more complex cases
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a language detection system. Respond with only the ISO 639-1 language code (2 letters) for the detected language. If unsure, respond with 'en'."
                },
                {
                    "role": "user", 
                    "content": f"Detect the language of this text: '{text}'"
                }
            ],
            max_tokens=10,
            temperature=0
        )
        detected_lang = response.choices[0].message.content.strip().lower()
        
        # Validate that it's a supported language
        if detected_lang in SUPPORTED_LANGUAGES:
            return detected_lang
        
    except Exception as e:
        logger.warning(f"Language detection failed: {e}")
    
    # Default to English if detection fails
    return 'en'

def get_language_specific_voice(language_code):
    """
    Get the appropriate voice for the detected language
    """
    return SUPPORTED_LANGUAGES.get(language_code, SUPPORTED_LANGUAGES['en'])['voice']

def create_multilingual_system_prompt(language_code):
    """
    Create a system prompt in the appropriate language with restaurant knowledge
    """
    lang_info = SUPPORTED_LANGUAGES.get(language_code, SUPPORTED_LANGUAGES['en'])
    lang_name = lang_info['name']
    
    # Base prompt with restaurant knowledge
    if language_code == 'es':
        system_prompt = f"""Eres un asistente de IA profesional para {RESTAURANT_INFO['name']}. Responde SIEMPRE en español de manera natural y amigable.

INFORMACIÓN DEL RESTAURANTE:
- Nombre: {RESTAURANT_INFO['name']}
- Dirección: {RESTAURANT_INFO['address']}

CONOCIMIENTO DEL MENÚ:
Conoces todos los platos del menú incluyendo ingredientes, alérgenos, y preparación.

INFORMACIÓN LOCAL:
- Estacionamiento disponible en Main Street
- Transporte público cerca
- Atracciones cercanas en el centro

REGLAS IMPORTANTES:
1. Siempre responde en español
2. Sé específico sobre ingredientes y alérgenos
3. Ofrece alternativas si algo no está disponible
4. Si necesitas consultar con el chef, di "Déjame consultar con el chef"
5. Para reservas, pregunta: nombre, teléfono, número de personas, fecha, hora
"""
    elif language_code == 'fr':
        system_prompt = f"""Vous êtes un assistant IA professionnel pour {RESTAURANT_INFO['name']}. Répondez TOUJOURS en français de manière naturelle et amicale.

INFORMATIONS DU RESTAURANT:
- Nom: {RESTAURANT_INFO['name']}
- Adresse: {RESTAURANT_INFO['address']}

CONNAISSANCE DU MENU:
Vous connaissez tous les plats du menu, leurs ingrédients, allergènes et préparation.

INFORMATIONS LOCALES:
- Parking disponible sur Main Street
- Transports publics à proximité
- Attractions du centre-ville

RÈGLES IMPORTANTES:
1. Toujours répondre en français
2. Être précis sur les ingrédients et allergènes
3. Proposer des alternatives si nécessaire
4. Si consultation chef nécessaire, dire "Laissez-moi consulter le chef"
5. Pour réservations, demander: nom, téléphone, nombre de personnes, date, heure
"""
    else:
        # Default English prompt with enhanced restaurant knowledge
        system_prompt = f"""You are a professional AI assistant for {RESTAURANT_INFO['name']}. You have extensive knowledge about our restaurant and provide helpful, accurate information.

RESTAURANT INFORMATION:
- Name: {RESTAURANT_INFO['name']}
- Address: {RESTAURANT_INFO['address']}

DETAILED MENU KNOWLEDGE:
You know every dish on our menu including ingredients, allergens, preparation methods, and possible modifications.

LOCAL AREA EXPERTISE:
- Parking available on Main Street (2-hour limit) and nearby lots
- Public transportation accessible via metro and bus lines
- Walking distance to downtown attractions and hotels

IMPORTANT CONVERSATION RULES:
1. Always respond in {lang_name}
2. Be specific about ingredients and allergens when asked
3. Offer alternatives if something isn't available
4. If you need to check with kitchen staff, say "Let me check with the chef about that"
5. For reservations, collect: name, phone, party size, date, time
6. Be warm and welcoming, as if you're a knowledgeable staff member

RESERVATION FLOW:
- Ask for name and phone number first
- Then ask for party size, date, and time
- Confirm availability (use realistic responses)
- Offer alternatives if requested time isn't available
- Ask about special occasions or dietary needs
"""
    
    return system_prompt

# Database session helper
def get_db():
    if not DATABASE_AVAILABLE or not SessionLocal:
        return None
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        return None


def get_twilio_client():
    """Return a Twilio client if env vars and import are available, else None."""
    if not _twilio_import_ok:
        return None
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER):
        return None
    try:
        return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except Exception:
        return None

# Configure OpenAI
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Configure ElevenLabs
if ELEVENLABS_API_KEY:
    os.environ["ELEVEN_API_KEY"] = ELEVENLABS_API_KEY

# Language detection and multilingual support
SUPPORTED_LANGUAGES = {
    'en': {'name': 'English', 'voice': 'Rachel', 'code': 'en-US'},
    'es': {'name': 'Spanish', 'voice': 'Isabella', 'code': 'es-ES'},
    'fr': {'name': 'French', 'voice': 'Charlotte', 'code': 'fr-FR'},
    'de': {'name': 'German', 'voice': 'Giselle', 'code': 'de-DE'},
    'it': {'name': 'Italian', 'voice': 'Giulia', 'code': 'it-IT'},
    'pt': {'name': 'Portuguese', 'voice': 'Camila', 'code': 'pt-BR'},
    'ru': {'name': 'Russian', 'voice': 'Anastasia', 'code': 'ru-RU'},
    'ja': {'name': 'Japanese', 'voice': 'Yuki', 'code': 'ja-JP'},
    'ko': {'name': 'Korean', 'voice': 'Jihyun', 'code': 'ko-KR'},
    'zh': {'name': 'Chinese', 'voice': 'Li Wei', 'code': 'zh-CN'},
    'hi': {'name': 'Hindi', 'voice': 'Aditi', 'code': 'hi-IN'},
    'ar': {'name': 'Arabic', 'voice': 'Amara', 'code': 'ar-SA'},
}

# Language detection patterns
LANGUAGE_PATTERNS = {
    'es': ['hola', 'buenos', 'gracias', 'por favor', 'disculpe', 'reserva', 'mesa'],
    'fr': ['bonjour', 'merci', 'excusez', 'réservation', 'table', 'restaurant'],
    'de': ['hallo', 'danke', 'entschuldigung', 'reservierung', 'tisch', 'restaurant'],
    'it': ['ciao', 'grazie', 'scusi', 'prenotazione', 'tavolo', 'ristorante'],
    'pt': ['olá', 'obrigado', 'desculpe', 'reserva', 'mesa', 'restaurante'],
    'ru': ['привет', 'спасибо', 'извините', 'бронирование', 'столик'],
    'ja': ['こんにちは', 'ありがとう', 'すみません', '予約', 'テーブル'],
    'ko': ['안녕하세요', '감사합니다', '죄송합니다', '예약', '테이블'],
    'zh': ['你好', '谢谢', '对不起', '预订', '桌子'],
    'hi': ['नमस्ते', 'धन्यवाद', 'माफ करें', 'बुकिंग', 'टेबल'],
    'ar': ['مرحبا', 'شكرا', 'عذرا', 'حجز', 'طاولة']
}

# Enhanced restaurant information for AI context
RESTAURANT_INFO = {
    "name": "Bella Vista Italian Restaurant",
    "address": "123 Main Street, Downtown, CA 90210",
    "phone": "(555) 123-4567",
    "website": "www.bellavista.com",
    
    # Detailed menu information with allergens and preparations
    "menu": {
        "appetizers": {
            "bruschetta": {
                "name": "Classic Bruschetta",
                "price": "$12",
                "description": "Grilled bread topped with fresh tomatoes, basil, garlic, and extra virgin olive oil",
                "allergens": ["gluten"],
                "vegetarian": True,
                "preparation_time": "5-8 minutes",
                "ingredients": ["bread", "tomatoes", "basil", "garlic", "olive oil", "balsamic vinegar"]
            },
            "calamari": {
                "name": "Fried Calamari",
                "price": "$16",
                "description": "Fresh squid rings lightly breaded and fried, served with marinara sauce",
                "allergens": ["seafood", "gluten"],
                "vegetarian": False,
                "preparation_time": "8-10 minutes",
                "ingredients": ["squid", "flour", "eggs", "breadcrumbs", "marinara sauce"]
            }
        },
        "pasta": {
            "spaghetti_carbonara": {
                "name": "Spaghetti Carbonara",
                "price": "$18",
                "description": "Traditional Roman pasta with eggs, pecorino cheese, pancetta, and black pepper",
                "allergens": ["gluten", "dairy", "eggs"],
                "vegetarian": False,
                "preparation_time": "12-15 minutes",
                "ingredients": ["spaghetti", "eggs", "pecorino cheese", "pancetta", "black pepper"],
                "modifications": ["can substitute pancetta with vegetables for vegetarian version"]
            },
            "penne_arrabbiata": {
                "name": "Penne Arrabbiata",
                "price": "$16",
                "description": "Penne pasta in spicy tomato sauce with garlic, red chili, and fresh herbs",
                "allergens": ["gluten"],
                "vegetarian": True,
                "spicy": True,
                "preparation_time": "10-12 minutes",
                "ingredients": ["penne pasta", "tomatoes", "garlic", "red chili", "herbs", "olive oil"]
            }
        },
        "main_courses": {
            "osso_buco": {
                "name": "Osso Buco alla Milanese",
                "price": "$32",
                "description": "Braised veal shanks with vegetables, white wine, and saffron risotto",
                "allergens": ["dairy"],
                "vegetarian": False,
                "preparation_time": "25-30 minutes",
                "ingredients": ["veal shanks", "carrots", "celery", "onions", "white wine", "arborio rice", "saffron"],
                "chef_special": True
            },
            "branzino": {
                "name": "Mediterranean Branzino",
                "price": "$28",
                "description": "Whole grilled sea bass with lemon, herbs, and seasonal vegetables",
                "allergens": ["fish"],
                "vegetarian": False,
                "preparation_time": "20-25 minutes",
                "ingredients": ["sea bass", "lemon", "herbs", "seasonal vegetables", "olive oil"],
                "gluten_free": True
            }
        },
        "desserts": {
            "tiramisu": {
                "name": "Classic Tiramisu",
                "price": "$9",
                "description": "Traditional Italian dessert with coffee-soaked ladyfingers and mascarpone",
                "allergens": ["dairy", "eggs", "gluten"],
                "vegetarian": True,
                "preparation_time": "made fresh daily",
                "ingredients": ["ladyfingers", "espresso", "mascarpone", "eggs", "cocoa powder"]
            }
        }
    },
    
    # Local area information
    "local_info": {
        "parking": {
            "street_parking": "Available on Main Street (2-hour limit until 6 PM)",
            "valet": "Complimentary valet service available evenings after 5 PM",
            "nearby_lots": ["City Parking Garage (2 blocks east)", "Plaza Parking Structure (3 blocks north)"],
            "cost": "Street parking $2/hour, lots $5-8/hour"
        },
        "public_transport": {
            "metro": "Red Line Metro station 3 blocks away (Downtown/Civic Center)",
            "bus": "Bus lines 4, 16, 20 stop directly in front",
            "rideshare": "Designated pickup zone on side street (1st Avenue)"
        },
        "nearby_attractions": [
            "Downtown Art Museum (2 blocks)",
            "Historic Theater District (4 blocks)",
            "Waterfront Park (6 blocks)",
            "Shopping Plaza (3 blocks)"
        ],
        "area_description": "Located in the heart of downtown's dining district, walking distance to major hotels and attractions"
    },
    
    # Seasonal and special information
    "seasonal_info": {
        "current_specials": [
            "Winter Truffle Menu (available through March)",
            "Happy Hour 4-6 PM weekdays (50% off appetizers)",
            "Sunday Brunch 10 AM - 3 PM"
        ],
        "holiday_hours": {
            "christmas": "Closed December 25th",
            "new_year": "Special NYE menu December 31st",
            "thanksgiving": "Closed November 4th Thursday"
        },
        "events": {
            "wine_tastings": "First Friday of each month at 7 PM",
            "cooking_classes": "Saturday mornings 10 AM (advance booking required)",
            "live_music": "Thursday and Friday evenings 7-10 PM"
        }
    },
    "hours": {
        "monday": "11:00 AM - 10:00 PM",
        "tuesday": "11:00 AM - 10:00 PM", 
        "wednesday": "11:00 AM - 10:00 PM",
        "thursday": "11:00 AM - 10:00 PM",
        "friday": "11:00 AM - 11:00 PM",
        "saturday": "11:00 AM - 11:00 PM",
        "sunday": "12:00 PM - 9:00 PM"
    },
    "menu": """
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
    """,
    "features": """
    - Private dining room available for groups of 8-20 people
    - Outdoor patio seating (weather permitting)
    - Full bar with extensive wine list
    - Live music on Friday and Saturday evenings
    - Catering services available for events
    - Happy hour Monday-Friday 4-6 PM
    - Kids menu available
    - Vegetarian and gluten-free options
    """
}

# Mock reservation system (fallback)
reservations = []
call_history = {}
call_languages = {}  # Store detected language for each call
reservation_state = {}  # Track reservation progress per call

# Security and spam protection
call_rate_limit = defaultdict(list)  # Track calls per phone number
blocked_numbers = set()  # Blocked phone numbers
moderation_flags = defaultdict(int)  # Track inappropriate content per number

# Content moderation keywords
INAPPROPRIATE_KEYWORDS = {
    'profanity': ['fuck', 'shit', 'damn', 'bitch', 'asshole', 'bastard'],
    'spam_indicators': ['test', 'testing', 'spam', 'fake', 'bot', 'automated'],
    'malicious': ['hack', 'attack', 'virus', 'scam', 'fraud'],
    'inappropriate_names': ['hitler', 'satan', 'devil', 'nazi']
}

# Rate limiting settings
MAX_CALLS_PER_HOUR = 5
MAX_MODERATION_FLAGS = 3
RESERVATION_COOLDOWN = 300  # 5 minutes between reservations from same number
last_analysis = {}

def is_rate_limited(phone_number: str) -> bool:
    """Check if phone number is rate limited"""
    if phone_number in blocked_numbers:
        return True
    
    current_time = time.time()
    # Clean old calls (older than 1 hour)
    call_rate_limit[phone_number] = [
        call_time for call_time in call_rate_limit[phone_number] 
        if current_time - call_time < 3600
    ]
    
    # Check if exceeded rate limit
    if len(call_rate_limit[phone_number]) >= MAX_CALLS_PER_HOUR:
        logger.warning(f"Rate limit exceeded for {phone_number}")
        return True
    
    # Add current call
    call_rate_limit[phone_number].append(current_time)
    return False

def moderate_content(text: str, phone_number: str) -> tuple[bool, str]:
    """
    Moderate content for inappropriate language and spam
    Returns (is_safe, reason_if_blocked)
    """
    text_lower = text.lower()
    
    # Check for inappropriate keywords
    for category, keywords in INAPPROPRIATE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                moderation_flags[phone_number] += 1
                logger.warning(f"Inappropriate content detected from {phone_number}: {category} - {keyword}")
                
                # Block after repeated violations
                if moderation_flags[phone_number] >= MAX_MODERATION_FLAGS:
                    blocked_numbers.add(phone_number)
                    logger.error(f"Phone number {phone_number} blocked for repeated violations")
                    return False, "account_blocked"
                
                return False, category
    
    # Check for repeated identical messages (spam detection)
    if phone_number in call_history:
        recent_messages = [
            msg['content'] for msg in call_history[phone_number][-5:] 
            if msg['role'] == 'user'
        ]
        if len(recent_messages) >= 3 and len(set(recent_messages)) <= 1:
            moderation_flags[phone_number] += 1
            logger.warning(f"Spam detected from {phone_number}: repeated messages")
            return False, "spam_detected"
    
    return True, ""

def validate_reservation_data(data: dict, phone_number: str) -> tuple[bool, str]:
    """
    Validate reservation data for suspicious patterns
    Returns (is_valid, reason_if_invalid)
    """
    # Check for inappropriate names
    if 'name' in data:
        name_lower = data['name'].lower()
        for keyword in INAPPROPRIATE_KEYWORDS['inappropriate_names']:
            if keyword in name_lower:
                logger.warning(f"Inappropriate name detected: {data['name']}")
                return False, "inappropriate_name"
    
    # Check reservation cooldown
    current_time = time.time()
    if phone_number in reservation_state:
        last_reservation = reservation_state[phone_number].get('last_reservation_time', 0)
        if current_time - last_reservation < RESERVATION_COOLDOWN:
            logger.warning(f"Reservation cooldown active for {phone_number}")
            return False, "too_frequent"
    
    return True, ""

def log_call_start(call_sid: str, from_number: str, to_number: str):
    """Log call start to database"""
    if not DATABASE_AVAILABLE:
        return
    
    db = get_db()
    if not db:
        return
    
    try:
        # Check if call already exists
        existing_call = db.query(Call).filter(Call.call_sid == call_sid).first()
        if not existing_call:
            call = Call(
                call_sid=call_sid,
                from_number=from_number,
                to_number=to_number,
                status="in-progress"
            )
            db.add(call)
            db.commit()
            logger.info(f"Call {call_sid} logged to database")
    except Exception as e:
        logger.error(f"Failed to log call start: {e}")
        db.rollback()
    finally:
        db.close()

def log_transcript(call_sid: str, speaker: str, message: str, confidence: float = None):
    """Log transcript to database"""
    if not DATABASE_AVAILABLE:
        return
    
    db = get_db()
    if not db:
        return
    
    try:
        # Find the call
        call = db.query(Call).filter(Call.call_sid == call_sid).first()
        if call:
            transcript = Transcript(
                call_id=call.id,
                speaker=speaker,
                message=message,
                confidence=confidence
            )
            db.add(transcript)
            db.commit()
            logger.info(f"Transcript logged for call {call_sid}")
    except Exception as e:
        logger.error(f"Failed to log transcript: {e}")
        db.rollback()
    finally:
        db.close()

def log_reservation(call_sid: str, reservation_data: dict):
    """Log reservation to database"""
    if not DATABASE_AVAILABLE:
        return
    
    db = get_db()
    if not db:
        return
    
    try:
        # Find the call
        call = db.query(Call).filter(Call.call_sid == call_sid).first()
        if call:
            reservation = Reservation(
                call_id=call.id,
                customer_name=reservation_data.get('name'),
                customer_phone=reservation_data.get('phone'),
                party_size=reservation_data.get('party_size'),
                reservation_time=reservation_data.get('time'),
                status="confirmed",
                sms_consent=reservation_data.get('sms_consent', False)
            )
            db.add(reservation)
            db.commit()
            logger.info(f"Reservation logged for call {call_sid}")
    except Exception as e:
        logger.error(f"Failed to log reservation: {e}")
        db.rollback()
    finally:
        db.close()

def log_call_end(call_sid: str):
    """Log call end to database"""
    if not DATABASE_AVAILABLE:
        return
    
    db = get_db()
    if not db:
        return
    
    try:
        call = db.query(Call).filter(Call.call_sid == call_sid).first()
        if call:
            call.status = "completed"
            call.end_time = func.now()
            db.commit()
            logger.info(f"Call {call_sid} marked as completed")
    except Exception as e:
        logger.error(f"Failed to log call end: {e}")
        db.rollback()
    finally:
        db.close()

def transcribe_audio(audio_url: str) -> str:
    """Transcribe audio using OpenAI Whisper"""
    try:
        if not OPENAI_API_KEY:
            return "I'm sorry, I'm experiencing technical difficulties. Please call back later."
        
        # For now, return a mock transcription
        # In production, you would use: openai.Audio.transcribe("whisper-1", audio_file)
        return "I would like to make a reservation"
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        return "I'm sorry, I couldn't understand that. Could you please repeat?"

def generate_ai_response(user_message: str, call_sid: str) -> str:
    """Generate multilingual AI response using OpenAI GPT with language detection"""
    try:
        if not OPENAI_API_KEY:
            return "I'm sorry, I'm experiencing technical difficulties. Please call back later."
        
        # Detect language from user input
        detected_language = detect_language(user_message)
        logger.info(f"Detected language: {detected_language} for message: {user_message}")
        
        # Store language preference for this call
        if call_sid not in call_languages:
            call_languages[call_sid] = detected_language
        
        # Get conversation history
        history = call_history.get(call_sid, [])
        
        # Add user message to history
        history.append({"role": "user", "content": user_message})
        
        # Keep only last 10 messages to avoid token limits
        if len(history) > 10:
            history = history[-10:]
        
        # Create language-specific system prompt
        system_prompt = create_multilingual_system_prompt(detected_language)

Restaurant Information:
- Name: {RESTAURANT_INFO['name']}
- Address: {RESTAURANT_INFO['address']}
- Phone: {RESTAURANT_INFO['phone']}
- Website: {RESTAURANT_INFO['website']}

Hours:
{chr(10).join([f"- {day.title()}: {hours}" for day, hours in RESTAURANT_INFO['hours'].items()])}

Menu:
{RESTAURANT_INFO['menu']}

Special Features:
{RESTAURANT_INFO['features']}

Your capabilities:
1. Make reservations (collect details step by step: name & phone first, then party size, then date & time)
2. Answer questions about hours, menu, location, special features
3. Provide excellent service - be friendly and professional
4. Handle reservation changes and cancellations
5. Offer alternatives if requested time isn't available
6. Ask for SMS consent before sending confirmations
7. Escalate to human if customer requests or if you're unsure after 2 attempts

IMPORTANT CONVERSATION RULES:
- Stay focused on the current task. Do NOT ask "Is there anything else I can help you with" unless the customer has completed their request.
- For reservations, collect information step by step:
  * First: Ask for name and phone number
  * Second: Ask for party size
  * Third: Ask for date and time
  * Fourth: Ask for SMS consent for confirmation
- Be formal and professional in tone
- Only offer additional help when the current request is fully completed.
- Be conversational and natural - don't sound robotic or repetitive.

RESERVATION FLOW EXAMPLES:
- When someone says "I'd like to make a reservation": "I'd be happy to help you make a reservation. To get started, could you please provide your name and phone number?"
- After getting name/phone: "Thank you. How many people will be in your party?"
- After getting party size: "Perfect. What date and time would you prefer for your reservation?"
- After getting date/time: "Excellent! Would you like me to send you a text message confirmation of your reservation?"

SMS CONSENT:
- Always ask for SMS consent after collecting all reservation details
- If customer says yes: "Perfect! I'll send you a confirmation text. Your reservation is confirmed for [date] at [time] for [party_size] people. Thank you for choosing [restaurant_name]!"
- If customer says no: "No problem! Your reservation is confirmed for [date] at [time] for [party_size] people. Thank you for choosing [restaurant_name]!"

Current conversation context: {len(history)} previous exchanges.

Respond naturally and conversationally. Keep responses concise but helpful."""

        # Prepare messages for OpenAI
        messages = [{"role": "system", "content": system_prompt}] + history
        
        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=150,
            temperature=0.7
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Add AI response to history
        history.append({"role": "assistant", "content": ai_response})
        call_history[call_sid] = history
        
        return ai_response
        
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return "I'm sorry, I'm experiencing technical difficulties. Please call back later."

def analyze_interaction(user_message: str, ai_message: str) -> dict:
    """Lightweight analyzer using OpenAI to extract intent, reservation completion, and SMS consent.

    Returns dict like:
    {
      "reservation_complete": bool,
      "sms_consent": "yes"|"no"|"unknown",
      "details": {"name": str|None, "phone": str|None, "party_size": int|None, "date": str|None, "time": str|None}
    }
    """
    try:
        if not OPENAI_API_KEY:
            return {"reservation_complete": False, "sms_consent": "unknown", "details": {}}

        system = (
            "You extract structured data from a restaurant phone conversation. "
            "Return strict JSON only."
        )
        instruction = (
            "Given the last user message and the assistant reply, decide if a reservation is completed, "
            "and whether the caller consented to SMS. "
            "Output JSON with keys: reservation_complete (boolean), sms_consent ('yes'|'no'|'unknown'), "
            "and details {name, phone, party_size, date, time}. If unknown, use null."
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": instruction},
            {
                "role": "user",
                "content": json.dumps(
                    {"user_message": user_message, "assistant_message": ai_message}
                ),
            },
        ]
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0,
            max_tokens=200,
        )
        raw = resp.choices[0].message.content.strip()
        # Ensure pure JSON
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start : end + 1]
        parsed = json.loads(raw)
        # Basic shape guard
        if "reservation_complete" not in parsed or "sms_consent" not in parsed:
            raise ValueError("missing keys")
        return parsed
    except Exception as exc:
        logger.warning(f"analyze_interaction fallback: {exc}")
        return {"reservation_complete": False, "sms_consent": "unknown", "details": {}}
def text_to_speech(text: str) -> str:
    """Convert text to speech using ElevenLabs"""
    try:
        if not ELEVENLABS_API_KEY:
            # Fallback to Twilio TTS
            return text
        
        # Use ElevenLabs for high-quality TTS
        audio = generate(
            text=text,
            voice="Rachel",  # Natural female voice
            model="eleven_monolingual_v1"
        )
        
        # For now, return the text (Twilio will handle TTS)
        # In production, you would save the audio and return the URL
        return text
        
    except Exception as e:
        logger.error(f"Error in text-to-speech: {e}")
        return text

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {RESTAURANT_INFO['name']} AI Agent",
        "status": "operational",
        "version": "1.0.0"
    }

@app.get("/health")
def health():
    """Health check endpoint - Railway uses this to verify the app is running"""
    import datetime
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "message": "All systems operational",
        "uptime": "ok"
    }

@app.post("/voice/")
async def handle_call(request: Request):
    """Handle incoming call"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    from_number = form_data.get("From", "unknown")
    to_number = form_data.get("To", "unknown")

    logger.info(f"New call received: {call_sid} from {from_number}")

    # Log call start to database
    log_call_start(call_sid, from_number, to_number)

    # Security check: Rate limiting
    if is_rate_limited(from_number):
        logger.warning(f"Call blocked due to rate limiting: {from_number}")
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>I'm sorry, but you have exceeded the maximum number of calls allowed. Please try again later.</Say>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    # Initialize call history
    if call_sid not in call_history:
        call_history[call_sid] = []
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Thank you for calling {RESTAURANT_INFO['name']}! I'm your AI assistant. How can I help you today?</Say>
    <Gather input="speech" action="/voice/process" method="POST" speechTimeout="auto" speechModel="phone_call">
        <Say>Please tell me what you'd like to do. You can say things like "I'd like to make a reservation" or "What are your hours?"</Say>
    </Gather>
    <Say>I didn't hear anything. Please call back and I'll be happy to help you!</Say>
    <Hangup/>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")

@app.post("/voice/process")
async def process_speech(request: Request):
    """Process user speech and generate AI response"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    from_number = form_data.get("From", "unknown")
    speech_result = form_data.get("SpeechResult", "")
    confidence = form_data.get("Confidence", "0")
    
    logger.info(f"Processing speech for call {call_sid}: '{speech_result}' (confidence: {confidence})")

    # Log user transcript
    log_transcript(call_sid, "customer", speech_result, float(confidence) if confidence else None)

    # Content moderation check
    is_safe, block_reason = moderate_content(speech_result, from_number)
    if not is_safe:
        logger.warning(f"Content blocked for {from_number}: {block_reason}")
        
        if block_reason == "account_blocked":
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>I'm sorry, but this number has been blocked due to repeated policy violations. Goodbye.</Say>
    <Hangup/>
</Response>"""
        else:
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>I'm sorry, but I can't process that request. Please keep our conversation professional and appropriate.</Say>
    <Gather input="speech" action="/voice/process" method="POST" speechTimeout="auto" speechModel="phone_call">
        <Say>How else can I help you today?</Say>
    </Gather>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")
    
    # If no speech detected or low confidence, ask for clarification
    if not speech_result or float(confidence) < 0.5:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>I'm sorry, I didn't catch that. Could you please repeat what you said?</Say>
    <Gather input="speech" action="/voice/process" method="POST" speechTimeout="auto" speechModel="phone_call">
        <Say>Please tell me what you'd like to do.</Say>
    </Gather>
    <Say>I'm still having trouble understanding. Please call back and I'll be happy to help!</Say>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")
    
    # Generate AI response
    ai_response = generate_ai_response(speech_result, call_sid)

    # Log AI response
    log_transcript(call_sid, "ai", ai_response)

    # Analyze exchange for reservation completion and consent
    analysis = analyze_interaction(speech_result, ai_response)
    last_analysis[call_sid] = analysis
    
    # Convert to speech (for now, using Twilio TTS)
    speech_text = text_to_speech(ai_response)
    
    # Check if this is a reservation completion
    if analysis.get("reservation_complete", False):
        # Validate reservation data
        reservation_data = analysis.get("details", {})
        is_valid, validation_error = validate_reservation_data(reservation_data, from_number)
        
        if not is_valid:
            logger.warning(f"Reservation validation failed for {from_number}: {validation_error}")
            
            if validation_error == "inappropriate_name":
                error_msg = "I'm sorry, but I cannot process a reservation with that name. Please provide a different name."
            elif validation_error == "too_frequent":
                error_msg = "I notice you just made a reservation recently. Please wait a few minutes before making another reservation."
            else:
                error_msg = "I'm sorry, but I cannot process this reservation at the moment. Please try again later."
            
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>{error_msg}</Say>
    <Gather input="speech" action="/voice/process" method="POST" speechTimeout="auto" speechModel="phone_call">
        <Say>How else can I help you today?</Say>
    </Gather>
    <Hangup/>
</Response>"""
        else:
            # Mark reservation time for cooldown
            if from_number not in reservation_state:
                reservation_state[from_number] = {}
            reservation_state[from_number]['last_reservation_time'] = time.time()
            
            # Log reservation to database
            log_reservation(call_sid, reservation_data)
            
            # End call after successful reservation confirmation
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>{speech_text}</Say>
    <Say>Thank you for choosing {RESTAURANT_INFO['name']}. Have a great day!</Say>
    <Hangup/>
</Response>"""
    else:
        # Continue conversation
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>{speech_text}</Say>
    <Gather input="speech" action="/voice/process" method="POST" speechTimeout="auto" speechModel="phone_call">
        <Say>Is there anything else I can help you with?</Say>
    </Gather>
    <Say>Thank you for calling {RESTAURANT_INFO['name']}. Have a great day!</Say>
    <Hangup/>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")

@app.get("/analysis/{call_sid}")
def get_last_analysis(call_sid: str):
    """Return the most recent analyzer output for a call (for validation)."""
    return last_analysis.get(call_sid, {})

@app.get("/test")
def test():
    """Test endpoint"""
    return {
        "message": "API is working!",
        "restaurant": RESTAURANT_INFO['name'],
        "status": "operational"
    }

@app.get("/sms/status")
def sms_status():
    """Check whether SMS subsystem is ready (no send)."""
    client = get_twilio_client()
    return {
        "twilio_import": _twilio_import_ok,
        "twilio_env_ready": bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER),
        "twilio_client_ready": bool(client is not None),
        "from_number": TWILIO_PHONE_NUMBER if client else None
    }

class SMSRequest(BaseModel):
    to: str
    message: Optional[str] = None

@app.post("/sms/send")
def sms_send(payload: SMSRequest):
    """Send an SMS if Twilio is properly configured; otherwise return 503.

    This is intentionally minimal and safe: no send unless env/imports are ready.
    """
    client = get_twilio_client()
    if client is None:
        return JSONResponse(
            status_code=503,
            content={
                "error": "SMS subsystem not ready",
                "twilio_import": _twilio_import_ok,
                "twilio_env_ready": bool(
                    TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER
                ),
            },
        )

    text = payload.message or f"Hello from {RESTAURANT_INFO['name']}!"
    try:
        msg = client.messages.create(
            from_=TWILIO_PHONE_NUMBER,
            to=payload.to,
            body=text,
        )
        return {"status": "queued", "sid": msg.sid}
    except Exception as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})

@app.get("/test-ai")
def test_ai():
    """Test AI functionality"""
    try:
        if not OPENAI_API_KEY:
            return {"error": "OpenAI API key not found"}
        
        # Test AI response
        test_response = generate_ai_response("What are your hours?", "test-call")
        
        return {
            "test_response": test_response,
            "status": "AI working"
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/security/status")
def security_status():
    """Get security monitoring dashboard"""
    return {
        "blocked_numbers": list(blocked_numbers),
        "total_blocked": len(blocked_numbers),
        "rate_limited_numbers": len([
            phone for phone, calls in call_rate_limit.items() 
            if len(calls) >= MAX_CALLS_PER_HOUR
        ]),
        "moderation_flags": dict(moderation_flags),
        "settings": {
            "max_calls_per_hour": MAX_CALLS_PER_HOUR,
            "max_moderation_flags": MAX_MODERATION_FLAGS,
            "reservation_cooldown_seconds": RESERVATION_COOLDOWN
        }
    }

@app.post("/security/unblock")
async def unblock_number(request: Request):
    """Unblock a phone number (admin function)"""
    data = await request.json()
    phone_number = data.get("phone_number")
    
    if not phone_number:
        return {"error": "phone_number required"}
    
    if phone_number in blocked_numbers:
        blocked_numbers.remove(phone_number)
        moderation_flags[phone_number] = 0
        logger.info(f"Unblocked phone number: {phone_number}")
        return {"message": f"Phone number {phone_number} has been unblocked"}
    else:
        return {"message": f"Phone number {phone_number} was not blocked"}

@app.get("/analytics/dashboard")
def analytics_dashboard():
    """Get analytics dashboard with call and reservation statistics"""
    if not DATABASE_AVAILABLE:
        return {
            "database_status": "not_available",
            "in_memory_stats": {
                "call_history_count": len(call_history),
                "reservations_count": len(reservations)
            }
        }
    
    db = get_db()
    if not db:
        return {"error": "Database connection failed"}
    
    try:
        # Call statistics
        total_calls = db.query(Call).count()
        completed_calls = db.query(Call).filter(Call.status == "completed").count()
        in_progress_calls = db.query(Call).filter(Call.status == "in-progress").count()
        
        # Reservation statistics
        total_reservations = db.query(Reservation).count()
        confirmed_reservations = db.query(Reservation).filter(Reservation.status == "confirmed").count()
        
        # SMS consent statistics
        sms_consent_given = db.query(Reservation).filter(Reservation.sms_consent == True).count()
        
        return {
            "database_status": "available",
            "call_stats": {
                "total_calls": total_calls,
                "completed_calls": completed_calls,
                "in_progress_calls": in_progress_calls,
                "completion_rate": (completed_calls / total_calls * 100) if total_calls > 0 else 0
            },
            "reservation_stats": {
                "total_reservations": total_reservations,
                "confirmed_reservations": confirmed_reservations,
                "sms_consent_rate": (sms_consent_given / total_reservations * 100) if total_reservations > 0 else 0
            },
            "conversion_rate": (total_reservations / total_calls * 100) if total_calls > 0 else 0
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()

@app.get("/analytics/calls")
def get_calls(limit: int = 50):
    """Get recent calls with transcripts"""
    if not DATABASE_AVAILABLE:
        return {"error": "Database not available"}
    
    db = get_db()
    if not db:
        return {"error": "Database connection failed"}
    
    try:
        calls = db.query(Call).order_by(Call.start_time.desc()).limit(limit).all()
        result = []
        
        for call in calls:
            call_data = {
                "call_sid": call.call_sid,
                "from_number": call.from_number,
                "start_time": call.start_time.isoformat() if call.start_time else None,
                "end_time": call.end_time.isoformat() if call.end_time else None,
                "status": call.status,
                "transcript_count": len(call.transcripts),
                "reservation_count": len(call.reservations)
            }
            result.append(call_data)
        
        return {"calls": result}
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()

@app.get("/analytics/call/{call_sid}")
def get_call_details(call_sid: str):
    """Get detailed call information including full transcript"""
    if not DATABASE_AVAILABLE:
        return {"error": "Database not available"}
    
    db = get_db()
    if not db:
        return {"error": "Database connection failed"}
    
    try:
        call = db.query(Call).filter(Call.call_sid == call_sid).first()
        if not call:
            return {"error": "Call not found"}
        
        # Get transcripts
        transcripts = [
            {
                "timestamp": t.timestamp.isoformat(),
                "speaker": t.speaker,
                "message": t.message,
                "confidence": t.confidence
            }
            for t in call.transcripts
        ]
        
        # Get reservations
        reservations = [
            {
                "customer_name": r.customer_name,
                "customer_phone": r.customer_phone,
                "party_size": r.party_size,
                "reservation_time": r.reservation_time,
                "status": r.status,
                "sms_consent": r.sms_consent,
                "sms_sent": r.sms_sent,
                "created_at": r.created_at.isoformat()
            }
            for r in call.reservations
        ]
        
        return {
            "call": {
                "call_sid": call.call_sid,
                "from_number": call.from_number,
                "to_number": call.to_number,
                "start_time": call.start_time.isoformat() if call.start_time else None,
                "end_time": call.end_time.isoformat() if call.end_time else None,
                "status": call.status
            },
            "transcripts": transcripts,
            "reservations": reservations
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()

@app.get("/debug")
def debug():
    """Debug endpoint to check environment"""
    db_status = "not_configured"
    if DATABASE_URL:
        db_status = "available" if DATABASE_AVAILABLE else "failed"
    
    return {
        "openai_key_set": bool(OPENAI_API_KEY),
        "elevenlabs_key_set": bool(ELEVENLABS_API_KEY),
        "twilio_ready": bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER),
        "database_status": db_status,
        "database_url_set": bool(DATABASE_URL),
        "restaurant_name": RESTAURANT_INFO['name'],
        "call_history_count": len(call_history),
        "reservations_count": len(reservations),
        "security_stats": {
            "blocked_numbers": len(blocked_numbers),
            "moderation_flags": len(moderation_flags)
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 