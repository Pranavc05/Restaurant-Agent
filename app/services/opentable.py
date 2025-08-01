import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)


class OpenTableService:
    def __init__(self):
        # Mock restaurant data
        self.restaurant_name = "Bella Vista Italian Restaurant"
        self.business_hours = {
            "monday": {"open": "11:00", "close": "22:00"},
            "tuesday": {"open": "11:00", "close": "22:00"},
            "wednesday": {"open": "11:00", "close": "22:00"},
            "thursday": {"open": "11:00", "close": "22:00"},
            "friday": {"open": "11:00", "close": "23:00"},
            "saturday": {"open": "10:00", "close": "23:00"},
            "sunday": {"open": "10:00", "close": "22:00"}
        }
        
        # Mock existing reservations
        self.existing_reservations = []
        
        # Mock table availability
        self.total_tables = 20
        self.tables_per_time_slot = 15  # Assume 75% capacity for popular times
    
    def check_availability(self, date: str, time: str, party_size: int) -> Dict[str, any]:
        """
        Check availability for a specific date and time
        Returns mock availability data
        """
        try:
            # Parse date and time
            reservation_datetime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            
            # Check if restaurant is open
            day_of_week = reservation_datetime.strftime("%A").lower()
            if day_of_week not in self.business_hours:
                return {"available": False, "reason": "Restaurant closed on this day"}
            
            # Check business hours
            reservation_time = reservation_datetime.strftime("%H:%M")
            open_time = self.business_hours[day_of_week]["open"]
            close_time = self.business_hours[day_of_week]["close"]
            
            if reservation_time < open_time or reservation_time > close_time:
                return {"available": False, "reason": f"Restaurant hours: {open_time} - {close_time}"}
            
            # Mock availability check
            # For demo purposes, make some times unavailable
            hour = reservation_datetime.hour
            
            # Peak hours (6-8 PM) are more likely to be full
            if 18 <= hour <= 20:
                availability_chance = 0.3  # 30% chance of availability
            else:
                availability_chance = 0.8  # 80% chance of availability
            
            is_available = random.random() < availability_chance
            
            if is_available:
                return {
                    "available": True,
                    "tables_available": random.randint(1, 5),
                    "estimated_wait_time": 0
                }
            else:
                return {
                    "available": False,
                    "reason": "No tables available at this time",
                    "alternative_times": self._get_alternative_times(date, time)
                }
                
        except Exception as e:
            logger.error(f"Error checking availability: {e}")
            return {"available": False, "reason": "Error checking availability"}
    
    def _get_alternative_times(self, date: str, requested_time: str) -> List[str]:
        """
        Get alternative times when requested time is not available
        """
        try:
            base_datetime = datetime.strptime(f"{date} {requested_time}", "%Y-%m-%d %H:%M")
            alternatives = []
            
            # Generate 3 alternative times
            for i in range(1, 4):
                # Try 30 minutes before and after
                alternative_before = base_datetime - timedelta(minutes=30 * i)
                alternative_after = base_datetime + timedelta(minutes=30 * i)
                
                # Check if alternative times are within business hours
                day_of_week = alternative_before.strftime("%A").lower()
                if day_of_week in self.business_hours:
                    time_str = alternative_before.strftime("%H:%M")
                    open_time = self.business_hours[day_of_week]["open"]
                    close_time = self.business_hours[day_of_week]["close"]
                    
                    if open_time <= time_str <= close_time:
                        alternatives.append(alternative_before.strftime("%H:%M"))
                
                day_of_week = alternative_after.strftime("%A").lower()
                if day_of_week in self.business_hours:
                    time_str = alternative_after.strftime("%H:%M")
                    open_time = self.business_hours[day_of_week]["open"]
                    close_time = self.business_hours[day_of_week]["close"]
                    
                    if open_time <= time_str <= close_time:
                        alternatives.append(alternative_after.strftime("%H:%M"))
            
            return alternatives[:3]  # Return max 3 alternatives
            
        except Exception as e:
            logger.error(f"Error getting alternative times: {e}")
            return []
    
    def create_reservation(self, customer_name: str, customer_phone: str, 
                          party_size: int, date: str, time: str) -> Dict[str, any]:
        """
        Create a new reservation
        """
        try:
            reservation_id = f"OT{random.randint(10000, 99999)}"
            
            reservation = {
                "id": reservation_id,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "party_size": party_size,
                "date": date,
                "time": time,
                "status": "confirmed",
                "created_at": datetime.now().isoformat()
            }
            
            # Add to mock database
            self.existing_reservations.append(reservation)
            
            return {
                "success": True,
                "reservation_id": reservation_id,
                "confirmation_number": reservation_id,
                "reservation": reservation
            }
            
        except Exception as e:
            logger.error(f"Error creating reservation: {e}")
            return {"success": False, "error": str(e)}
    
    def modify_reservation(self, reservation_id: str, **kwargs) -> Dict[str, any]:
        """
        Modify an existing reservation
        """
        try:
            # Find reservation
            reservation = next((r for r in self.existing_reservations if r["id"] == reservation_id), None)
            
            if not reservation:
                return {"success": False, "error": "Reservation not found"}
            
            # Update fields
            for key, value in kwargs.items():
                if key in reservation:
                    reservation[key] = value
            
            return {
                "success": True,
                "reservation": reservation
            }
            
        except Exception as e:
            logger.error(f"Error modifying reservation: {e}")
            return {"success": False, "error": str(e)}
    
    def cancel_reservation(self, reservation_id: str) -> Dict[str, any]:
        """
        Cancel a reservation
        """
        try:
            # Find reservation
            reservation = next((r for r in self.existing_reservations if r["id"] == reservation_id), None)
            
            if not reservation:
                return {"success": False, "error": "Reservation not found"}
            
            # Update status
            reservation["status"] = "cancelled"
            
            return {
                "success": True,
                "reservation": reservation
            }
            
        except Exception as e:
            logger.error(f"Error cancelling reservation: {e}")
            return {"success": False, "error": str(e)}
    
    def get_business_hours(self) -> Dict[str, str]:
        """
        Get restaurant business hours
        """
        return self.business_hours
    
    def add_to_waitlist(self, customer_name: str, customer_phone: str, 
                       party_size: int, date: str, time: str) -> Dict[str, any]:
        """
        Add customer to waitlist
        """
        try:
            waitlist_id = f"WL{random.randint(10000, 99999)}"
            
            waitlist_entry = {
                "id": waitlist_id,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "party_size": party_size,
                "date": date,
                "time": time,
                "status": "waiting",
                "created_at": datetime.now().isoformat()
            }
            
            return {
                "success": True,
                "waitlist_id": waitlist_id,
                "estimated_wait_time": random.randint(15, 45),  # 15-45 minutes
                "waitlist_entry": waitlist_entry
            }
            
        except Exception as e:
            logger.error(f"Error adding to waitlist: {e}")
            return {"success": False, "error": str(e)} 