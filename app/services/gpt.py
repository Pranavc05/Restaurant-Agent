import openai
from app.config import settings
import logging
from typing import Dict, Any, List
import json

logger = logging.getLogger(__name__)

# Configure OpenAI client
openai.api_key = settings.openai_api_key


class GPTService:
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.openai_api_key)
        self.conversation_history = {}
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the AI agent"""
        return f"""You are an AI phone agent for {settings.restaurant_name}. Your role is to:

1. **Handle Reservations**: Book tables, check availability, modify existing reservations
2. **Answer Questions**: Provide information about hours, menu, location, etc.
3. **Provide Excellent Service**: Be friendly, professional, and helpful
4. **Collect Information**: Get customer name, phone number, party size, date, time
5. **Handle Edge Cases**: Offer alternatives when requested times aren't available

**Restaurant Information:**
- Name: {settings.restaurant_name}
- Hours: {settings.restaurant_hours}

**Reservation Process:**
1. Greet customer warmly
2. Ask for party size, date, and time
3. Check availability (use mock data for now)
4. Confirm details and get customer name and phone
5. Ask for SMS consent
6. Provide confirmation

**Response Format:**
Always respond in a conversational, friendly tone. Keep responses concise but warm.
If you need to ask for clarification, be specific about what you need.

**Important Rules:**
- Always ask for recording consent at the start
- Be patient and clear
- Offer alternatives if requested time isn't available
- Ask for SMS consent before sending confirmations
- Escalate to human if customer requests or if you're unsure after 2 attempts"""

    async def process_message(self, message: str, call_id: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process a customer message and generate an appropriate response
        """
        try:
            # Get conversation history for this call
            if call_id not in self.conversation_history:
                self.conversation_history[call_id] = []
            
            # Add user message to history
            self.conversation_history[call_id].append({
                "role": "user",
                "content": message
            })
            
            # Prepare messages for GPT
            messages = [
                {"role": "system", "content": self._get_system_prompt()}
            ]
            
            # Add conversation history (last 10 messages to avoid token limits)
            messages.extend(self.conversation_history[call_id][-10:])
            
            # Add context if provided
            if context:
                context_message = f"Context: {json.dumps(context)}"
                messages.append({"role": "system", "content": context_message})
            
            # Get response from GPT
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=300,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # Add AI response to history
            self.conversation_history[call_id].append({
                "role": "assistant",
                "content": ai_response
            })
            
            # Analyze intent and extract information
            intent_analysis = await self._analyze_intent(message, ai_response)
            
            return {
                "response": ai_response,
                "intent": intent_analysis["intent"],
                "extracted_info": intent_analysis["extracted_info"],
                "confidence": intent_analysis["confidence"],
                "should_escalate": intent_analysis["should_escalate"]
            }
            
        except Exception as e:
            logger.error(f"Error processing message with GPT: {e}")
            return {
                "response": "I'm sorry, I'm having trouble understanding. Let me connect you with a human representative.",
                "intent": "escalation",
                "extracted_info": {},
                "confidence": 0.0,
                "should_escalate": True
            }
    
    async def _analyze_intent(self, user_message: str, ai_response: str) -> Dict[str, Any]:
        """
        Analyze the intent of the user message and extract relevant information
        """
        try:
            analysis_prompt = f"""
            Analyze this customer message and extract intent and information:
            
            Customer: "{user_message}"
            AI Response: "{ai_response}"
            
            Return a JSON object with:
            - intent: "reservation", "question", "modification", "cancellation", "escalation"
            - extracted_info: {{"party_size": null, "date": null, "time": null, "name": null, "phone": null}}
            - confidence: 0.0-1.0
            - should_escalate: true/false (escalate if unclear intent or customer requests human)
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an intent analyzer. Return only valid JSON."},
                    {"role": "user", "content": analysis_prompt}
                ],
                max_tokens=200,
                temperature=0.1
            )
            
            analysis_text = response.choices[0].message.content.strip()
            analysis = json.loads(analysis_text)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing intent: {e}")
            return {
                "intent": "unknown",
                "extracted_info": {},
                "confidence": 0.0,
                "should_escalate": False
            }
    
    def clear_conversation_history(self, call_id: str):
        """Clear conversation history for a specific call"""
        if call_id in self.conversation_history:
            del self.conversation_history[call_id] 