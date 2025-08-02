from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os

app = FastAPI(title="Restaurant Agent")

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
def handle_call(request: Request):
    from fastapi.responses import Response
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Hello from Restaurant Agent! Thank you for calling Bella Vista Italian Restaurant. How can I help you today?</Say>
    <Gather input="speech" action="/voice/process" method="POST" speechTimeout="auto">
        <Say>Please tell me what you'd like to do. You can say things like "I'd like to make a reservation" or "What are your hours?"</Say>
    </Gather>
</Response>"""
    return Response(content=twiml, media_type="application/xml")

@app.get("/test")
def test():
    return {"message": "Test endpoint working", "timestamp": "now"}

@app.post("/voice/process")
def process_speech(request: Request):
    from fastapi.responses import Response
    # For now, just respond with a simple message
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Thank you for your input! This is a test response. The full AI agent will be implemented soon.</Say>
    <Hangup/>
</Response>"""
    return Response(content=twiml, media_type="application/xml")

@app.get("/debug")
def debug():
    return {
        "port": os.environ.get("PORT"),
        "railway_environment": os.environ.get("RAILWAY_ENVIRONMENT"),
        "railway_service_name": os.environ.get("RAILWAY_SERVICE_NAME"),
        "all_env_vars": {k: v for k, v in os.environ.items() if not k.startswith("RAILWAY_")}
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 