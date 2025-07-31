from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


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
    recording_url = Column(String, nullable=True)
    recording_consent = Column(Boolean, default=False)
    status = Column(String, default="in-progress")  # in-progress, completed, failed
    
    # Relationships
    transcripts = relationship("Transcript", back_populates="call")
    reservations = relationship("Reservation", back_populates="call")
    consent_logs = relationship("ConsentLog", back_populates="call")


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
    reservation_time = Column(String)  # "7:00 PM"
    status = Column(String, default="confirmed")  # confirmed, cancelled, completed
    sms_consent = Column(Boolean, default=False)
    sms_sent = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    call = relationship("Call", back_populates="reservations")


class ConsentLog(Base):
    __tablename__ = "consent_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"))
    consent_type = Column(String)  # "recording", "sms"
    method = Column(String)  # "voice", "dtmf"
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    granted = Column(Boolean, default=False)
    
    # Relationships
    call = relationship("Call", back_populates="consent_logs")


class CallAnalytics(Base):
    __tablename__ = "call_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"))
    call_type = Column(String)  # "reservation", "general_question", "escalation"
    intent_detected = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=True)
    retry_count = Column(Integer, default=0)
    fallback_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 