from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session
import logging
import json
from typing import Dict, Any

from app.config import settings

# Import database components conditionally
try:
    from app.database import get_db, engine
    from app.models import Base
    from app.routes import voice, analytics, reservations
    
    # Create database tables (only if database is available)
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.warning(f"Could not create database tables: {e}")
        
    # Include routers
    app.include_router(voice.router, prefix="/voice", tags=["voice"])
    app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
    app.include_router(reservations.router, prefix="/reservations", tags=["reservations"])
    
except Exception as e:
    logger.error(f"Could not initialize database components: {e}")
    # Create a minimal app without database features
    pass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AI Restaurant Agent",
    description="AI-powered phone agent for restaurant reservations and customer service",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI Restaurant Agent API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/config")
async def get_config():
    """Get current configuration (without sensitive data)"""
    return {
        "restaurant_name": settings.restaurant_name,
        "restaurant_hours": settings.restaurant_hours,
        "max_retry_attempts": settings.max_retry_attempts
    }


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, call_id: str):
        await websocket.accept()
        self.active_connections[call_id] = websocket

    def disconnect(self, call_id: str):
        if call_id in self.active_connections:
            del self.active_connections[call_id]

    async def send_message(self, call_id: str, message: str):
        if call_id in self.active_connections:
            await self.active_connections[call_id].send_text(message)

    async def send_audio(self, call_id: str, audio_data: bytes):
        if call_id in self.active_connections:
            await self.active_connections[call_id].send_bytes(audio_data)


manager = ConnectionManager()


@app.websocket("/media-stream/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    """WebSocket endpoint for real-time audio streaming"""
    await manager.connect(websocket, call_id)
    
    try:
        while True:
            # Receive audio data from Twilio
            audio_data = await websocket.receive_bytes()
            
            # Process the audio data
            # This will be handled by the voice processing service
            await manager.send_message(call_id, "Audio received")
            
    except WebSocketDisconnect:
        manager.disconnect(call_id)
        logger.info(f"WebSocket disconnected for call {call_id}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 