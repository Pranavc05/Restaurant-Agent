# AI Restaurant Agent Backend

An AI-powered phone agent that handles restaurant reservations, answers customer questions, and provides excellent customer service.

## Features

- **Voice Call Handling**: Receives calls via Twilio and processes them in real-time
- **Natural Language Understanding**: Uses OpenAI GPT-4o to understand customer intent
- **High-Quality TTS**: Uses ElevenLabs for natural-sounding voice responses
- **Reservation Management**: Integrates with OpenTable API (mock data for MVP)
- **SMS Confirmations**: Sends booking confirmations via Twilio SMS
- **Call Analytics**: Tracks call metrics and reservation conversion rates
- **Human Fallback**: Escalates to human staff when needed
- **Consent Management**: Handles recording consent and SMS opt-ins

## Architecture

```
Customer Call → Twilio → FastAPI → Whisper (ASR) → GPT-4o (NLU) → ElevenLabs (TTS) → Twilio → Customer
                                    ↓
                              OpenTable API → SMS Confirmation → Database Logging
```

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment variables** (create `.env` file):
   ```env
   # Twilio
   TWILIO_ACCOUNT_SID=your_account_sid
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_PHONE_NUMBER=your_twilio_number
   
   # OpenAI
   OPENAI_API_KEY=your_openai_key
   
   # ElevenLabs
   ELEVENLABS_API_KEY=your_elevenlabs_key
   
   # Database
   DATABASE_URL=postgresql://user:password@localhost/restaurant_agent
   
   # Redis (for session management)
   REDIS_URL=redis://localhost:6379
   ```

3. **Database setup**:
   ```bash
   alembic upgrade head
   ```

4. **Run the application**:
   ```bash
   uvicorn app.main:app --reload
   ```

## API Endpoints

- `POST /voice` - Twilio webhook for incoming calls
- `WebSocket /media-stream` - Real-time audio streaming
- `GET /analytics` - Call and reservation analytics
- `GET /reservations` - View all reservations
- `POST /reservations` - Create new reservation

## Deployment

This application is configured for Railway deployment. Simply connect your GitHub repository to Railway and it will automatically deploy.

## Development

- **Local testing**: Use ngrok to expose local server to Twilio
- **Database migrations**: Use Alembic for schema changes
- **Testing**: Run `pytest` for unit tests

## Security & Compliance

- All API communications use HTTPS
- Call recording consent is collected at the start of each call
- SMS consent is logged for TCPA compliance
- Personal data is encrypted in transit and at rest 