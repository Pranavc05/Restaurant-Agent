from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, List

from app.database import get_db
from app.models import Call, Reservation, CallAnalytics, Transcript

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def get_analytics_overview(db: Session = Depends(get_db)):
    """
    Get overview analytics for the dashboard
    """
    try:
        # Get date range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Total calls
        total_calls = db.query(Call).filter(
            Call.start_time >= start_date
        ).count()
        
        # Completed calls (not escalated)
        completed_calls = db.query(Call).filter(
            and_(
                Call.start_time >= start_date,
                Call.escalated == False
            )
        ).count()
        
        # Escalated calls
        escalated_calls = db.query(Call).filter(
            and_(
                Call.start_time >= start_date,
                Call.escalated == True
            )
        ).count()
        
        # Total reservations
        total_reservations = db.query(Reservation).filter(
            Reservation.created_at >= start_date
        ).count()
        
        # Call-to-reservation conversion rate
        conversion_rate = (total_reservations / total_calls * 100) if total_calls > 0 else 0
        
        # Average call duration
        avg_duration = db.query(func.avg(Call.duration)).filter(
            and_(
                Call.start_time >= start_date,
                Call.duration.isnot(None)
            )
        ).scalar() or 0
        
        # Call types breakdown
        call_types = db.query(
            CallAnalytics.call_type,
            func.count(CallAnalytics.id)
        ).filter(
            CallAnalytics.created_at >= start_date
        ).group_by(CallAnalytics.call_type).all()
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "overview": {
                "total_calls": total_calls,
                "completed_calls": completed_calls,
                "escalated_calls": escalated_calls,
                "total_reservations": total_reservations,
                "conversion_rate": round(conversion_rate, 2),
                "average_call_duration": round(avg_duration, 2)
            },
            "call_types": dict(call_types)
        }
        
    except Exception as e:
        logger.error(f"Error getting analytics overview: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving analytics")


@router.get("/calls")
async def get_call_analytics(
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db)
):
    """
    Get detailed call analytics
    """
    try:
        # Parse date range
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).isoformat()
        if not end_date:
            end_date = datetime.now().isoformat()
        
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Get calls in date range
        calls = db.query(Call).filter(
            and_(
                Call.start_time >= start_dt,
                Call.start_time <= end_dt
            )
        ).all()
        
        # Calculate metrics
        total_calls = len(calls)
        escalated_calls = len([c for c in calls if c.escalated])
        avg_duration = sum(c.duration or 0 for c in calls) / total_calls if total_calls > 0 else 0
        
        # Hourly breakdown
        hourly_calls = {}
        for call in calls:
            hour = call.start_time.hour
            hourly_calls[hour] = hourly_calls.get(hour, 0) + 1
        
        return {
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            },
            "metrics": {
                "total_calls": total_calls,
                "escalated_calls": escalated_calls,
                "escalation_rate": (escalated_calls / total_calls * 100) if total_calls > 0 else 0,
                "average_duration": round(avg_duration, 2)
            },
            "hourly_breakdown": hourly_calls
        }
        
    except Exception as e:
        logger.error(f"Error getting call analytics: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving call analytics")


@router.get("/reservations")
async def get_reservation_analytics(
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db)
):
    """
    Get reservation analytics
    """
    try:
        # Parse date range
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).isoformat()
        if not end_date:
            end_date = datetime.now().isoformat()
        
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Get reservations in date range
        reservations = db.query(Reservation).filter(
            and_(
                Reservation.created_at >= start_dt,
                Reservation.created_at <= end_dt
            )
        ).all()
        
        # Calculate metrics
        total_reservations = len(reservations)
        confirmed_reservations = len([r for r in reservations if r.status == "confirmed"])
        cancelled_reservations = len([r for r in reservations if r.status == "cancelled"])
        
        # Average party size
        avg_party_size = sum(r.party_size for r in reservations) / total_reservations if total_reservations > 0 else 0
        
        # Popular times
        time_slots = {}
        for reservation in reservations:
            time = reservation.reservation_time
            time_slots[time] = time_slots.get(time, 0) + 1
        
        popular_times = sorted(time_slots.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            },
            "metrics": {
                "total_reservations": total_reservations,
                "confirmed_reservations": confirmed_reservations,
                "cancelled_reservations": cancelled_reservations,
                "confirmation_rate": (confirmed_reservations / total_reservations * 100) if total_reservations > 0 else 0,
                "average_party_size": round(avg_party_size, 1)
            },
            "popular_times": dict(popular_times)
        }
        
    except Exception as e:
        logger.error(f"Error getting reservation analytics: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving reservation analytics")


@router.get("/conversion")
async def get_conversion_analytics(
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db)
):
    """
    Get call-to-reservation conversion analytics
    """
    try:
        # Parse date range
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).isoformat()
        if not end_date:
            end_date = datetime.now().isoformat()
        
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Get calls and reservations in date range
        calls = db.query(Call).filter(
            and_(
                Call.start_time >= start_dt,
                Call.start_time <= end_dt
            )
        ).all()
        
        reservations = db.query(Reservation).filter(
            and_(
                Reservation.created_at >= start_dt,
                Reservation.created_at <= end_dt
            )
        ).all()
        
        # Calculate conversion metrics
        total_calls = len(calls)
        calls_with_reservations = len([c for c in calls if c.reservations])
        conversion_rate = (calls_with_reservations / total_calls * 100) if total_calls > 0 else 0
        
        # Conversion by call type
        call_type_conversions = {}
        for call in calls:
            analytics = db.query(CallAnalytics).filter(CallAnalytics.call_id == call.id).first()
            if analytics:
                call_type = analytics.call_type
                if call_type not in call_type_conversions:
                    call_type_conversions[call_type] = {"total": 0, "converted": 0}
                
                call_type_conversions[call_type]["total"] += 1
                if call.reservations:
                    call_type_conversions[call_type]["converted"] += 1
        
        # Calculate conversion rates by type
        for call_type, data in call_type_conversions.items():
            data["conversion_rate"] = (data["converted"] / data["total"] * 100) if data["total"] > 0 else 0
        
        return {
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            },
            "overall_conversion": {
                "total_calls": total_calls,
                "calls_with_reservations": calls_with_reservations,
                "conversion_rate": round(conversion_rate, 2)
            },
            "conversion_by_type": call_type_conversions
        }
        
    except Exception as e:
        logger.error(f"Error getting conversion analytics: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving conversion analytics")


@router.get("/realtime")
async def get_realtime_metrics(db: Session = Depends(get_db)):
    """
    Get real-time metrics for the current day
    """
    try:
        # Get today's date range
        today = datetime.now().date()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())
        
        # Today's calls
        today_calls = db.query(Call).filter(
            and_(
                Call.start_time >= start_of_day,
                Call.start_time <= end_of_day
            )
        ).all()
        
        # Today's reservations
        today_reservations = db.query(Reservation).filter(
            and_(
                Reservation.created_at >= start_of_day,
                Reservation.created_at <= end_of_day
            )
        ).all()
        
        # Active calls (in progress)
        active_calls = len([c for c in today_calls if c.status == "in-progress"])
        
        # Recent activity (last hour)
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_calls = len([c for c in today_calls if c.start_time >= one_hour_ago])
        recent_reservations = len([r for r in today_reservations if r.created_at >= one_hour_ago])
        
        return {
            "current_time": datetime.now().isoformat(),
            "today": {
                "total_calls": len(today_calls),
                "total_reservations": len(today_reservations),
                "active_calls": active_calls,
                "escalated_calls": len([c for c in today_calls if c.escalated])
            },
            "last_hour": {
                "calls": recent_calls,
                "reservations": recent_reservations
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting realtime metrics: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving realtime metrics") 