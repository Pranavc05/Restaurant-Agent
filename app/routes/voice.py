from fastapi import APIRouter, Request, Response, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from twilio.twiml import VoiceResponse
from twilio.twiml.voice_response import Connect, Stream
import logging
import json
from datetime import datetime
from typing import Dict, Any

from app.database import get_db
from app.models import Call, Transcript, ConsentLog, CallAnalytics
from app.services.whisper import WhisperService
from app.services.gpt import GPTService
from app.services.elevenlabs import ElevenLabsService
from app.services.opentable import OpenTableService
from app.services.sms import SMSService
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
whisper_service = WhisperService()
gpt_service = GPTService()
elevenlabs_service = ElevenLabsService()
opentable_service = OpenTableService()
sms_service = SMSService()


@router.post("/")
async def handle_incoming_call(request: Request, db: Session = Depends(get_db)):
    """
    Handle incoming calls from Twilio
    """
    try:
        # Parse form data from Twilio
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From")
        to_number = form_data.get("To")
        
        logger.info(f"Received incoming call: {call_sid} from {from_number}")
        
        # Create call record in database
        call = Call(
            call_sid=call_sid,
            from_number=from_number,
            to_number=to_number,
            status="in-progress"
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        
        # Create TwiML response
        response = VoiceResponse()
        
        # Add recording consent
        gather = response.gather(
            input='speech',
            action='/voice/consent',
            method='POST',
            speech_timeout='auto',
            language='en-US'
        )
        gather.say(settings.call_recording_consent_text)
        
        # If no input, redirect to consent
        response.redirect('/voice/consent')
        
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error handling incoming call: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error. Please try again later.")
        return Response(content=str(response), media_type="application/xml")


@router.post("/consent")
async def handle_consent(request: Request, db: Session = Depends(get_db)):
    """
    Handle recording consent and start the conversation
    """
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        speech_result = form_data.get("SpeechResult", "").lower()
        
        # Get call record
        call = db.query(Call).filter(Call.call_sid == call_sid).first()
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        # Log consent
        consent_granted = "yes" in speech_result or "sure" in speech_result or "okay" in speech_result
        consent_log = ConsentLog(
            call_id=call.id,
            consent_type="recording",
            method="voice",
            granted=consent_granted
        )
        db.add(consent_log)
        call.recording_consent = consent_granted
        db.commit()
        
        # Create TwiML response
        response = VoiceResponse()
        
        # Start media stream for real-time processing
        connect = Connect()
        connect.stream(url=f'wss://your-domain.com/media-stream/{call_sid}')
        response.append(connect)
        
        # Play greeting
        response.say(f"Hello! Welcome to {settings.restaurant_name}. How can I help you today?")
        
        # Start gathering speech
        gather = response.gather(
            input='speech',
            action='/voice/process',
            method='POST',
            speech_timeout='auto',
            language='en-US'
        )
        
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error handling consent: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error. Please try again later.")
        return Response(content=str(response), media_type="application/xml")


@router.post("/process")
async def process_speech(request: Request, db: Session = Depends(get_db)):
    """
    Process customer speech and generate AI response
    """
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        speech_result = form_data.get("SpeechResult", "")
        confidence = float(form_data.get("Confidence", 0))
        
        # Get call record
        call = db.query(Call).filter(Call.call_sid == call_sid).first()
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        # Log customer transcript
        customer_transcript = Transcript(
            call_id=call.id,
            speaker="customer",
            message=speech_result,
            confidence=confidence
        )
        db.add(customer_transcript)
        
        # Process with GPT
        gpt_response = await gpt_service.process_message(speech_result, call_sid)
        
        # Log AI transcript
        ai_transcript = Transcript(
            call_id=call.id,
            speaker="ai",
            message=gpt_response["response"],
            confidence=gpt_response["confidence"]
        )
        db.add(ai_transcript)
        
        # Log analytics
        analytics = CallAnalytics(
            call_id=call.id,
            call_type=gpt_response["intent"],
            intent_detected=gpt_response["intent"],
            confidence_score=gpt_response["confidence"]
        )
        db.add(analytics)
        
        db.commit()
        
        # Check if escalation is needed
        if gpt_response["should_escalate"]:
            return await escalate_to_human(call_sid, db)
        
        # Generate speech response
        audio_data = await elevenlabs_service.text_to_speech(gpt_response["response"])
        
        # Create TwiML response
        response = VoiceResponse()
        
        # Play AI response
        response.say(gpt_response["response"])
        
        # Continue gathering speech
        gather = response.gather(
            input='speech',
            action='/voice/process',
            method='POST',
            speech_timeout='auto',
            language='en-US'
        )
        
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error processing speech: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, I didn't catch that. Could you please repeat?")
        return Response(content=str(response), media_type="application/xml")


@router.post("/escalate")
async def escalate_to_human(call_sid: str, db: Session = Depends(get_db)):
    """
    Escalate call to human representative
    """
    try:
        # Get call record
        call = db.query(Call).filter(Call.call_sid == call_sid).first()
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        # Update call status
        call.escalated = True
        call.status = "escalated"
        db.commit()
        
        # Create TwiML response
        response = VoiceResponse()
        
        if settings.human_fallback_number:
            response.say("I'm connecting you with a human representative. Please hold.")
            response.dial(settings.human_fallback_number)
        else:
            response.say("I'm sorry, but I need to transfer you to a human representative. Please call back during business hours.")
        
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error escalating call: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error. Please try again later.")
        return Response(content=str(response), media_type="application/xml")


@router.post("/status")
async def handle_call_status(request: Request, db: Session = Depends(get_db)):
    """
    Handle call status updates from Twilio
    """
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        call_status = form_data.get("CallStatus")
        call_duration = form_data.get("CallDuration")
        
        # Get call record
        call = db.query(Call).filter(Call.call_sid == call_sid).first()
        if not call:
            logger.warning(f"Call not found for status update: {call_sid}")
            return Response(content="OK", media_type="text/plain")
        
        # Update call status
        call.status = call_status
        if call_duration:
            call.duration = float(call_duration)
        call.end_time = datetime.now()
        
        db.commit()
        
        # Clear conversation history
        gpt_service.clear_conversation_history(call_sid)
        
        logger.info(f"Call {call_sid} ended with status: {call_status}")
        
        return Response(content="OK", media_type="text/plain")
        
    except Exception as e:
        logger.error(f"Error handling call status: {e}")
        return Response(content="OK", media_type="text/plain") 