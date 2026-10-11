from fastapi import FastAPI
from pydantic import BaseModel
import os

app = FastAPI(title="Mock Inference Server")


class GenerateRequest(BaseModel):
    prompt: str


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/generate")
def generate(request: GenerateRequest):
    return {
        "model": "mock-llm",
        "response": f"Mock LLM response to: {request.prompt}",
        "pod_name": os.getenv("HOSTNAME", "unknown"),
    }
