from twilio.rest import Client
from app.config import settings
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SMSService:
    def __init__(self):
        self.client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self.from_number = settings.twilio_phone_number
    
    async def send_reservation_confirmation(self, to_number: str, reservation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send reservation confirmation SMS
        """
        try:
            # Format the message
            message_body = self._format_reservation_confirmation(reservation_data)
            
            # Send SMS
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=to_number
            )
            
            return {
                "success": True,
                "message_sid": message.sid,
                "status": message.status
            }
            
        except Exception as e:
            logger.error(f"Error sending SMS confirmation: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _format_reservation_confirmation(self, reservation_data: Dict[str, Any]) -> str:
        """
        Format reservation confirmation message
        """
        restaurant_name = settings.restaurant_name
        
        message = f"""Thank you for your reservation at {restaurant_name}!

📅 Date: {reservation_data.get('date', 'N/A')}
🕐 Time: {reservation_data.get('time', 'N/A')}
👥 Party Size: {reservation_data.get('party_size', 'N/A')}
📞 Confirmation: {reservation_data.get('confirmation_number', 'N/A')}

We look forward to serving you! Please call us if you need to make any changes.

{restaurant_name}
{settings.twilio_phone_number}"""
        
        return message
    
    async def send_waitlist_confirmation(self, to_number: str, waitlist_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send waitlist confirmation SMS
        """
        try:
            # Format the message
            message_body = self._format_waitlist_confirmation(waitlist_data)
            
            # Send SMS
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=to_number
            )
            
            return {
                "success": True,
                "message_sid": message.sid,
                "status": message.status
            }
            
        except Exception as e:
            logger.error(f"Error sending waitlist SMS: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _format_waitlist_confirmation(self, waitlist_data: Dict[str, Any]) -> str:
        """
        Format waitlist confirmation message
        """
        restaurant_name = settings.restaurant_name
        
        message = f"""You've been added to the waitlist at {restaurant_name}!

📅 Date: {waitlist_data.get('date', 'N/A')}
🕐 Requested Time: {waitlist_data.get('time', 'N/A')}
👥 Party Size: {waitlist_data.get('party_size', 'N/A')}
⏱️ Estimated Wait: {waitlist_data.get('estimated_wait_time', 'N/A')} minutes

We'll call you when a table becomes available!

{restaurant_name}
{settings.twilio_phone_number}"""
        
        return message
    
    async def send_reminder(self, to_number: str, reservation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send reservation reminder SMS
        """
        try:
            # Format the message
            message_body = self._format_reminder(reservation_data)
            
            # Send SMS
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=to_number
            )
            
            return {
                "success": True,
                "message_sid": message.sid,
                "status": message.status
            }
            
        except Exception as e:
            logger.error(f"Error sending reminder SMS: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _format_reminder(self, reservation_data: Dict[str, Any]) -> str:
        """
        Format reminder message
        """
        restaurant_name = settings.restaurant_name
        
        message = f"""Reminder: Your reservation at {restaurant_name} is today!

📅 Date: {reservation_data.get('date', 'N/A')}
🕐 Time: {reservation_data.get('time', 'N/A')}
👥 Party Size: {reservation_data.get('party_size', 'N/A')}

We look forward to seeing you!

{restaurant_name}
{settings.twilio_phone_number}"""
        
        return message
    
    async def send_cancellation_confirmation(self, to_number: str, reservation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send cancellation confirmation SMS
        """
        try:
            # Format the message
            message_body = self._format_cancellation_confirmation(reservation_data)
            
            # Send SMS
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=to_number
            )
            
            return {
                "success": True,
                "message_sid": message.sid,
                "status": message.status
            }
            
        except Exception as e:
            logger.error(f"Error sending cancellation SMS: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _format_cancellation_confirmation(self, reservation_data: Dict[str, Any]) -> str:
        """
        Format cancellation confirmation message
        """
        restaurant_name = settings.restaurant_name
        
        message = f"""Your reservation at {restaurant_name} has been cancelled.

📅 Date: {reservation_data.get('date', 'N/A')}
🕐 Time: {reservation_data.get('time', 'N/A')}
👥 Party Size: {reservation_data.get('party_size', 'N/A')}

We hope to see you again soon!

{restaurant_name}
{settings.twilio_phone_number}"""
        
        return message 