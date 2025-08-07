from fastapi import FastAPI, Request, Form
from fastapi.responses import Response, JSONResponse
import os
import json
import logging
from typing import Optional
from pydantic import BaseModel
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

# Twilio (optional; used for SMS)
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

# Guarded Twilio import
try:
    from twilio.rest import Client as TwilioClient
    _twilio_import_ok = True
except Exception:
    TwilioClient = None
    _twilio_import_ok = False


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

# Mock reservation system (fallback)
reservations = []
call_history = {}
reservation_state = {}  # Track reservation progress per call

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
    """Generate AI response using OpenAI GPT"""
    try:
        if not OPENAI_API_KEY:
            return "I'm sorry, I'm experiencing technical difficulties. Please call back later."
        
        # Get conversation history
        history = call_history.get(call_sid, [])
        
        # Add user message to history
        history.append({"role": "user", "content": user_message})
        
        # Keep only last 10 messages to avoid token limits
        if len(history) > 10:
            history = history[-10:]
        
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
    return {
        "status": "healthy",
        "timestamp": "2024-12-25T00:00:00Z",
        "version": "1.0.0",
        "message": "All systems operational"
    }

@app.post("/voice/")
async def handle_call(request: Request):
    """Handle incoming call"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    from_number = form_data.get("From", "unknown")
    to_number = form_data.get("To", "unknown")
    
    logger.info(f"New call received: {call_sid} from {from_number}")
    
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

@app.get("/debug")
def debug():
    """Debug endpoint to check environment"""
    return {
        "openai_key_set": bool(OPENAI_API_KEY),
        "elevenlabs_key_set": bool(ELEVENLABS_API_KEY),
        "twilio_ready": bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER),
        "restaurant_name": RESTAURANT_INFO['name'],
        "call_history_count": len(call_history),
        "reservations_count": len(reservations)
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 