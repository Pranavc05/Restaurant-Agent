from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Restaurant Agent")

@app.get("/")
def root():
    return {"message": "Restaurant Agent API is running!"}

@app.get("/health")
def health():
    return {"status": "healthy", "message": "All systems operational"}

@app.post("/voice/")
def handle_call(request: Request):
    return JSONResponse(content={
        "message": "Call received successfully",
        "status": "success"
    })

@app.get("/test")
def test():
    return {"message": "Test endpoint working"} 