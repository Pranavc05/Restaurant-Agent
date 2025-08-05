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

# Database imports
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models import Call, Transcript, Reservation, ConsentLog, CallAnalytics, Base

# SMS imports
from app.services.sms import SMSService

# Create database tables
Base.metadata.create_all(bind=engine)

# Mock reservation system (fallback)
reservations = []
call_history = {}
reservation_state = {}  # Track reservation progress per call

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def create_call_record(call_sid: str, from_number: str, to_number: str) -> Call:
    """Create a new call record in database"""
    try:
        db = get_db()
        if not db:
            return None
            
        call = Call(
            call_sid=call_sid,
            from_number=from_number,
            to_number=to_number,
            status="in-progress"
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        return call
    except Exception as e:
        logger.error(f"Error creating call record: {e}")
        return None

def save_transcript(call_id: int, speaker: str, message: str, confidence: float = None):
    """Save transcript to database"""
    try:
        db = get_db()
        if not db:
            return
            
        transcript = Transcript(
            call_id=call_id,
            speaker=speaker,
            message=message,
            confidence=confidence
        )
        db.add(transcript)
        db.commit()
    except Exception as e:
        logger.error(f"Error saving transcript: {e}")

def create_reservation(call_id: int, name: str, phone: str, party_size: int, date: str, time: str, sms_consent: bool = False) -> Reservation:
    """Create a new reservation in database"""
    try:
        db = get_db()
        if not db:
            return None
            
        reservation = Reservation(
            call_id=call_id,
            customer_name=name,
            customer_phone=phone,
            party_size=party_size,
            reservation_date=date,
            reservation_time=time,
            status="confirmed",
            sms_consent=sms_consent
        )
        db.add(reservation)
        db.commit()
        db.refresh(reservation)
        
        # Send SMS confirmation if consent was given
        if sms_consent:
            send_reservation_sms(reservation)
        
        return reservation
    except Exception as e:
        logger.error(f"Error creating reservation: {e}")
        return None

def send_reservation_sms(reservation: Reservation):
    """Send SMS confirmation for reservation"""
    try:
        sms_service = SMSService()
        
        # Format reservation data for SMS
        reservation_data = {
            "date": reservation.reservation_date.strftime("%B %d, %Y") if reservation.reservation_date else "N/A",
            "time": reservation.reservation_time,
            "party_size": reservation.party_size,
            "confirmation_number": f"R{reservation.id:06d}"
        }
        
        # Send SMS
        result = sms_service.send_reservation_confirmation(
            reservation.customer_phone, 
            reservation_data
        )
        
        if result["success"]:
            # Update reservation to mark SMS as sent
            db = get_db()
            if db:
                reservation.sms_sent = True
                db.commit()
            logger.info(f"SMS confirmation sent for reservation {reservation.id}")
        else:
            logger.error(f"Failed to send SMS confirmation: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error sending reservation SMS: {e}")

def extract_reservation_details(conversation_history: list) -> dict:
    """Extract reservation details from conversation history"""
    details = {
        "name": None,
        "phone": None,
        "party_size": None,
        "date": None,
        "time": None,
        "sms_consent": False
    }
    
    # Look for patterns in the conversation
    for msg in conversation_history:
        if msg["role"] == "user":
            text = msg["content"].lower()
            
            # Extract name and phone
            if "my name is" in text:
                details["name"] = text.split("my name is")[-1].strip().title()
            elif "name is" in text:
                details["name"] = text.split("name is")[-1].strip().title()
            
            # Extract phone number
            if any(char.isdigit() for char in text):
                # Simple phone extraction (you might want to improve this)
                import re
                phone_match = re.search(r'\d{3}[-.]?\d{3}[-.]?\d{4}', text)
                if phone_match:
                    details["phone"] = phone_match.group()
            
            # Extract party size
            if any(word in text for word in ["people", "person", "party"]):
                import re
                size_match = re.search(r'(\d+)\s*(?:people|person|party)', text)
                if size_match:
                    details["party_size"] = int(size_match.group(1))
            
            # Extract date and time
            if any(word in text for word in ["tomorrow", "today", "friday", "saturday", "sunday", "monday", "tuesday", "wednesday", "thursday"]):
                details["date"] = text
            
            if any(word in text for word in ["am", "pm", "o'clock"]):
                details["time"] = text
            
            # Check for SMS consent
            if any(word in text for word in ["yes", "sure", "okay", "ok", "text", "sms"]):
                if "reservation" in text or "confirmation" in text:
                    details["sms_consent"] = True
    
    return details

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
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        for msg in history[-4:]:  # Keep last 4 exchanges for context
            messages.append(msg)
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
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
        return f"I'm sorry, I'm experiencing technical difficulties: {str(e)}. Please call back later."

def text_to_speech(text: str) -> str:
    """Convert text to speech using ElevenLabs"""
    try:
        if not ELEVENLABS_API_KEY:
            # Fallback to Twilio's built-in TTS
            return text
        
        # Generate audio using ElevenLabs
        audio = elevenlabs.generate(
            text=text,
            voice="Rachel",  # Natural-sounding female voice in 20s
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
async def handle_call(request: Request):
    """Handle incoming call"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    from_number = form_data.get("From", "unknown")
    to_number = form_data.get("To", "unknown")
    
    logger.info(f"New call received: {call_sid} from {from_number}")
    
    # Create call record in database
    call_record = create_call_record(call_sid, from_number, to_number)
    
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
    
    # Get call record from database
    db = get_db()
    call_record = None
    if db:
        call_record = db.query(Call).filter(Call.call_sid == call_sid).first()
    
    # Save customer speech to database
    if call_record:
        save_transcript(call_record.id, "customer", speech_result, float(confidence))
    
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
    
    # Save AI response to database
    if call_record:
        save_transcript(call_record.id, "ai", ai_response)
    
    # Check if reservation is complete and create it
    if call_record and "reservation" in speech_result.lower():
        history = call_history.get(call_sid, [])
        reservation_details = extract_reservation_details(history)
        
        # If we have all the details, create the reservation
        if (reservation_details["name"] and reservation_details["phone"] and 
            reservation_details["party_size"] and reservation_details["date"] and 
            reservation_details["time"]):
            
            # Create reservation in database
            reservation = create_reservation(
                call_id=call_record.id,
                name=reservation_details["name"],
                phone=reservation_details["phone"],
                party_size=reservation_details["party_size"],
                date=reservation_details["date"],
                time=reservation_details["time"],
                sms_consent=reservation_details["sms_consent"]
            )
            
            if reservation:
                logger.info(f"Reservation created: {reservation.id}")
    
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
        return {"error": str(e), "openai_key": "found" if OPENAI_API_KEY else "missing", "full_error": repr(e)}

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

@app.get("/data/calls")
def get_calls():
    """Get all calls from database"""
    try:
        db = get_db()
        if not db:
            return {"error": "Database not available"}
        
        calls = db.query(Call).order_by(Call.start_time.desc()).limit(10).all()
        return {
            "calls": [
                {
                    "id": call.id,
                    "call_sid": call.call_sid,
                    "from_number": call.from_number,
                    "start_time": call.start_time,
                    "status": call.status
                }
                for call in calls
            ]
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/data/reservations")
def get_reservations():
    """Get all reservations from database"""
    try:
        db = get_db()
        if not db:
            return {"error": "Database not available"}
        
        reservations = db.query(Reservation).order_by(Reservation.created_at.desc()).limit(10).all()
        return {
            "reservations": [
                {
                    "id": reservation.id,
                    "customer_name": reservation.customer_name,
                    "customer_phone": reservation.customer_phone,
                    "party_size": reservation.party_size,
                    "reservation_date": reservation.reservation_date,
                    "reservation_time": reservation.reservation_time,
                    "status": reservation.status,
                    "sms_consent": reservation.sms_consent,
                    "sms_sent": reservation.sms_sent,
                    "created_at": reservation.created_at
                }
                for reservation in reservations
            ]
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/test-sms")
def test_sms():
    """Test SMS functionality"""
    try:
        sms_service = SMSService()
        
        # Test data
        test_reservation = {
            "date": "December 25, 2024",
            "time": "7:00 PM",
            "party_size": 4,
            "confirmation_number": "R000001"
        }
        
        # You'll need to replace this with a real phone number for testing
        test_phone = "+1234567890"  # Replace with your phone number
        
        result = sms_service.send_reservation_confirmation(test_phone, test_reservation)
        
        return {
            "status": "SMS test completed",
            "result": result,
            "note": "Replace test_phone with your actual number to receive SMS"
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 