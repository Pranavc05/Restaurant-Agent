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
    return JSONResponse(content={
        "message": "Call received successfully",
        "status": "success",
        "twiml": "<Response><Say>Hello from Restaurant Agent!</Say></Response>"
    })

@app.get("/test")
def test():
    return {"message": "Test endpoint working", "timestamp": "now"}

@app.get("/debug")
def debug():
    return {
        "port": os.environ.get("PORT"),
        "railway_environment": os.environ.get("RAILWAY_ENVIRONMENT"),
        "railway_service_name": os.environ.get("RAILWAY_SERVICE_NAME"),
        "all_env_vars": {k: v for k, v in os.environ.items() if not k.startswith("RAILWAY_")}
    } 