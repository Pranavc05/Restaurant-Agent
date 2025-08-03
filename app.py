from fastapi import FastAPI, Request, Form
from fastapi.responses import Response, JSONResponse
import os
import json
import logging
from typing import Optional
import openai
from elevenlabs import generate, save
import elevenlabs

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Restaurant Agent")

# Load environment variables
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
RESTAURANT_NAME = os.environ.get("RESTAURANT_NAME", "Bella Vista Italian Restaurant")

# Configure OpenAI
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Configure ElevenLabs
if ELEVENLABS_API_KEY:
    os.environ["ELEVEN_API_KEY"] = ELEVENLABS_API_KEY

# Restaurant information for AI context
RESTAURANT_INFO = {
    "name": "Bella Vista Italian Restaurant",
    "address": "123 Main Street, Downtown, CA 90210",
    "phone": "(555) 123-4567",
    "website": "www.bellavista.com",
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

# Mock reservation system
reservations = []
call_history = {}

def transcribe_audio(audio_url: str) -> str:
    """Transcribe audio using OpenAI Whisper"""
    try:
        if not OPENAI_API_KEY:
            return "I'm sorry, I'm having trouble understanding. Could you please repeat that?"
        
        # For now, we'll simulate transcription since we need to handle Twilio's audio format
        # In production, you'd download the audio from Twilio and send to Whisper
        logger.info(f"Would transcribe audio from: {audio_url}")
        return "I'd like to make a reservation"  # Placeholder
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return "I'm sorry, I couldn't understand that. Could you please repeat?"

def generate_ai_response(user_message: str, call_sid: str) -> str:
    """Generate AI response using OpenAI GPT"""
    try:
        if not OPENAI_API_KEY:
            return "I'm sorry, I'm experiencing technical difficulties. Please call back later."
        
        # Get conversation history
        history = call_history.get(call_sid, [])
        
        system_prompt = f"""You are an AI assistant for {RESTAURANT_INFO['name']}. You are friendly, professional, and helpful.

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
1. Make reservations (collect: name, phone, party size, date, time)
2. Answer questions about hours, menu, location, special features
3. Provide excellent service - be friendly and professional
4. Handle reservation changes and cancellations
5. Offer alternatives if requested time isn't available
6. Ask for SMS consent before sending confirmations
7. Escalate to human if customer requests or if you're unsure after 2 attempts

Current conversation context: {len(history)} previous exchanges.

Respond naturally and conversationally. Keep responses concise but helpful."""
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        for msg in history[-4:]:  # Keep last 4 exchanges for context
            messages.append(msg)
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=messages,
            max_tokens=200,
            temperature=0.7
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Update conversation history
        history.extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": ai_response}
        ])
        call_history[call_sid] = history
        
        return ai_response
        
    except Exception as e:
        logger.error(f"AI response generation error: {e}")
        return "I'm sorry, I'm experiencing technical difficulties. Please call back later."

def text_to_speech(text: str) -> str:
    """Convert text to speech using ElevenLabs"""
    try:
        if not ELEVENLABS_API_KEY:
            # Fallback to Twilio's built-in TTS
            return text
        
        # Generate audio using ElevenLabs
        audio = elevenlabs.generate(
            text=text,
            voice="Josh",  # You can change this to any ElevenLabs voice
            model="eleven_monolingual_v1"
        )
        
        # Save to temporary file (in production, you'd stream this)
        filename = f"temp_audio_{hash(text)}.mp3"
        elevenlabs.save(audio, filename)
        
        # For now, return the text for Twilio TTS
        # In production, you'd return the audio file URL
        return text
        
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return text  # Fallback to Twilio TTS

@app.get("/")
def root():
    return {
        "message": "Restaurant Agent API is running!",
        "port": os.environ.get("PORT", "8000"),
        "environment": "production"
    }

@app.get("/health")
def health():
    return {"status": "healthy", "message": "All systems operational"}

@app.post("/voice/")
def handle_call(request: Request):
    """Handle incoming call"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    
    logger.info(f"New call received: {call_sid}")
    
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
    speech_result = form_data.get("SpeechResult", "")
    confidence = form_data.get("Confidence", "0")
    
    logger.info(f"Processing speech for call {call_sid}: '{speech_result}' (confidence: {confidence})")
    
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
    
    # Convert to speech (for now, using Twilio TTS)
    speech_text = text_to_speech(ai_response)
    
    # Check if this is a reservation completion
    if "reservation" in speech_result.lower() and any(word in ai_response.lower() for word in ["confirmed", "booked", "reserved"]):
        # End call after reservation confirmation
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

@app.get("/test")
def test():
    return {"message": "Test endpoint working", "timestamp": "now"}

@app.get("/test-ai")
def test_ai():
    """Test the AI agent functionality"""
    try:
        # Test OpenAI
        if not OPENAI_API_KEY:
            return {"error": "OpenAI API key not found", "openai_key": "missing"}
        
        # Test a simple AI response
        test_response = generate_ai_response("What are your hours?", "test_call")
        
        return {
            "status": "success",
            "openai_key": "found" if OPENAI_API_KEY else "missing",
            "elevenlabs_key": "found" if ELEVENLABS_API_KEY else "missing",
            "test_response": test_response,
            "restaurant_name": RESTAURANT_INFO['name']
        }
    except Exception as e:
        return {"error": str(e), "openai_key": "found" if OPENAI_API_KEY else "missing"}

@app.get("/debug")
def debug():
    return {
        "port": os.environ.get("PORT"),
        "railway_environment": os.environ.get("RAILWAY_ENVIRONMENT"),
        "railway_service_name": os.environ.get("RAILWAY_SERVICE_NAME"),
        "openai_key_set": bool(OPENAI_API_KEY),
        "elevenlabs_key_set": bool(ELEVENLABS_API_KEY),
        "all_env_vars": {k: v for k, v in os.environ.items() if not k.startswith("RAILWAY_")}
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 