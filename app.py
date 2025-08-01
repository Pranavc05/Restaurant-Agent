from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/voice/")
def voice():
    return {"message": "Call received"} 