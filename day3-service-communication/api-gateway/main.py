import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="AI API Gateway")

INFERENCE_URL = os.getenv(
    "INFERENCE_URL",
    "http://mock-inference:8000"
)

class ChatRequest(BaseModel):
    message: str

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{INFERENCE_URL}/generate",
                json={"prompt": request.message}
            )
            response.raise_for_status()

        return {
            "gateway_pod": os.getenv("HOSTNAME", "unknown"),
            "inference": response.json()
        }
    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="Inference service unavailable"
        )
