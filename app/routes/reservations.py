from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from datetime import datetime, timedelta
import logging
from typing import List, Optional

from app.database import get_db
from app.models import Reservation, Call
from app.services.opentable import OpenTableService
from app.services.sms import SMSService

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
opentable_service = OpenTableService()
sms_service = SMSService()


@router.get("/")
async def get_reservations(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Get all reservations with optional filtering
    """
    try:
        query = db.query(Reservation)
        
        # Apply date filters
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(Reservation.created_at >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(Reservation.created_at <= end_dt)
        
        # Apply status filter
        if status:
            query = query.filter(Reservation.status == status)
        
        # Apply pagination
        total_count = query.count()
        reservations = query.order_by(desc(Reservation.created_at)).offset(offset).limit(limit).all()
        
        return {
            "reservations": [
                {
                    "id": r.id,
                    "customer_name": r.customer_name,
                    "customer_phone": r.customer_phone,
                    "party_size": r.party_size,
                    "reservation_date": r.reservation_date.isoformat() if r.reservation_date else None,
                    "reservation_time": r.reservation_time,
                    "status": r.status,
                    "sms_consent": r.sms_consent,
                    "sms_sent": r.sms_sent,
                    "created_at": r.created_at.isoformat(),
                    "call_id": r.call_id
                }
                for r in reservations
            ],
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting reservations: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving reservations")


@router.get("/{reservation_id}")
async def get_reservation(reservation_id: int, db: Session = Depends(get_db)):
    """
    Get a specific reservation by ID
    """
    try:
        reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
        
        if not reservation:
            raise HTTPException(status_code=404, detail="Reservation not found")
        
        return {
            "id": reservation.id,
            "customer_name": reservation.customer_name,
            "customer_phone": reservation.customer_phone,
            "party_size": reservation.party_size,
            "reservation_date": reservation.reservation_date.isoformat() if reservation.reservation_date else None,
            "reservation_time": reservation.reservation_time,
            "status": reservation.status,
            "sms_consent": reservation.sms_consent,
            "sms_sent": reservation.sms_sent,
            "created_at": reservation.created_at.isoformat(),
            "call_id": reservation.call_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting reservation {reservation_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving reservation")


@router.put("/{reservation_id}")
async def update_reservation(
    reservation_id: int,
    customer_name: Optional[str] = None,
    customer_phone: Optional[str] = None,
    party_size: Optional[int] = None,
    reservation_date: Optional[str] = None,
    reservation_time: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Update a reservation
    """
    try:
        reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
        
        if not reservation:
            raise HTTPException(status_code=404, detail="Reservation not found")
        
        # Update fields if provided
        if customer_name is not None:
            reservation.customer_name = customer_name
        if customer_phone is not None:
            reservation.customer_phone = customer_phone
        if party_size is not None:
            reservation.party_size = party_size
        if reservation_date is not None:
            reservation.reservation_date = datetime.fromisoformat(reservation_date.replace('Z', '+00:00'))
        if reservation_time is not None:
            reservation.reservation_time = reservation_time
        if status is not None:
            reservation.status = status
        
        db.commit()
        db.refresh(reservation)
        
        return {
            "id": reservation.id,
            "customer_name": reservation.customer_name,
            "customer_phone": reservation.customer_phone,
            "party_size": reservation.party_size,
            "reservation_date": reservation.reservation_date.isoformat() if reservation.reservation_date else None,
            "reservation_time": reservation.reservation_time,
            "status": reservation.status,
            "sms_consent": reservation.sms_consent,
            "sms_sent": reservation.sms_sent,
            "created_at": reservation.created_at.isoformat(),
            "call_id": reservation.call_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating reservation {reservation_id}: {e}")
        raise HTTPException(status_code=500, detail="Error updating reservation")


@router.delete("/{reservation_id}")
async def cancel_reservation(reservation_id: int, db: Session = Depends(get_db)):
    """
    Cancel a reservation
    """
    try:
        reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
        
        if not reservation:
            raise HTTPException(status_code=404, detail="Reservation not found")
        
        # Update status to cancelled
        reservation.status = "cancelled"
        db.commit()
        
        # Send cancellation SMS if consent was given
        if reservation.sms_consent and reservation.customer_phone:
            try:
                reservation_data = {
                    "date": reservation.reservation_date.strftime("%Y-%m-%d") if reservation.reservation_date else "N/A",
                    "time": reservation.reservation_time,
                    "party_size": reservation.party_size
                }
                
                await sms_service.send_cancellation_confirmation(
                    reservation.customer_phone,
                    reservation_data
                )
            except Exception as e:
                logger.error(f"Error sending cancellation SMS: {e}")
        
        return {"message": "Reservation cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling reservation {reservation_id}: {e}")
        raise HTTPException(status_code=500, detail="Error cancelling reservation")


@router.get("/today/")
async def get_todays_reservations(db: Session = Depends(get_db)):
    """
    Get all reservations for today
    """
    try:
        today = datetime.now().date()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())
        
        reservations = db.query(Reservation).filter(
            and_(
                Reservation.reservation_date >= start_of_day,
                Reservation.reservation_date <= end_of_day
            )
        ).order_by(Reservation.reservation_time).all()
        
        return {
            "date": today.isoformat(),
            "reservations": [
                {
                    "id": r.id,
                    "customer_name": r.customer_name,
                    "customer_phone": r.customer_phone,
                    "party_size": r.party_size,
                    "reservation_time": r.reservation_time,
                    "status": r.status,
                    "created_at": r.created_at.isoformat()
                }
                for r in reservations
            ],
            "total": len(reservations)
        }
        
    except Exception as e:
        logger.error(f"Error getting today's reservations: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving today's reservations")


@router.get("/upcoming/")
async def get_upcoming_reservations(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """
    Get upcoming reservations for the next N days
    """
    try:
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=days)
        
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        
        reservations = db.query(Reservation).filter(
            and_(
                Reservation.reservation_date >= start_dt,
                Reservation.reservation_date <= end_dt,
                Reservation.status == "confirmed"
            )
        ).order_by(Reservation.reservation_date, Reservation.reservation_time).all()
        
        # Group by date
        reservations_by_date = {}
        for reservation in reservations:
            date_str = reservation.reservation_date.strftime("%Y-%m-%d")
            if date_str not in reservations_by_date:
                reservations_by_date[date_str] = []
            
            reservations_by_date[date_str].append({
                "id": reservation.id,
                "customer_name": reservation.customer_name,
                "customer_phone": reservation.customer_phone,
                "party_size": reservation.party_size,
                "reservation_time": reservation.reservation_time,
                "created_at": reservation.created_at.isoformat()
            })
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days
            },
            "reservations_by_date": reservations_by_date,
            "total_reservations": len(reservations)
        }
        
    except Exception as e:
        logger.error(f"Error getting upcoming reservations: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving upcoming reservations")


@router.post("/{reservation_id}/send-reminder")
async def send_reminder(reservation_id: int, db: Session = Depends(get_db)):
    """
    Send a reminder SMS for a reservation
    """
    try:
        reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
        
        if not reservation:
            raise HTTPException(status_code=404, detail="Reservation not found")
        
        if not reservation.sms_consent:
            raise HTTPException(status_code=400, detail="SMS consent not given for this reservation")
        
        if not reservation.customer_phone:
            raise HTTPException(status_code=400, detail="No phone number available for this reservation")
        
        # Send reminder SMS
        reservation_data = {
            "date": reservation.reservation_date.strftime("%Y-%m-%d") if reservation.reservation_date else "N/A",
            "time": reservation.reservation_time,
            "party_size": reservation.party_size
        }
        
        result = await sms_service.send_reminder(reservation.customer_phone, reservation_data)
        
        if result["success"]:
            return {"message": "Reminder sent successfully"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to send reminder: {result.get('error', 'Unknown error')}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending reminder for reservation {reservation_id}: {e}")
        raise HTTPException(status_code=500, detail="Error sending reminder") 