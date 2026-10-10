import json
import os

import time
import statistics
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

URL = "http://127.0.0.1:8000/v1/chat/completions"
MODEL = "Qwen/Qwen3-8B"
API_KEY = os.environ.get("VLLM_API_KEY")

if not API_KEY:
    raise RuntimeError("VLLM_API_KEY is not set")

PROMPT = (
    "Explain the difference between CPU and GPU, "
    "including how each handles parallel computing."
)

def send_request(request_id):
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 200,
        "temperature": 0,
        "stream": False
    }

    request = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    start = time.perf_counter()

    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.load(response)

    latency = time.perf_counter() - start

    return {
        "id": request_id,
        "latency": latency,
        "tokens": result["usage"]["completion_tokens"]
    }


def benchmark(concurrency):
    print(f"\nTesting {concurrency} concurrent requests")

    start = time.perf_counter()
    results = []

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(send_request, i)
            for i in range(concurrency)
        ]

        for future in as_completed(futures):
            results.append(future.result())

    elapsed = time.perf_counter() - start
    total_tokens = sum(r["tokens"] for r in results)

    print(f"Wall time:          {elapsed:.2f}s")
    print(f"Total tokens:       {total_tokens}")
    print(f"Throughput:         {total_tokens / elapsed:.2f} tok/s")
    print(f"Average latency:    {statistics.mean(r['latency'] for r in results):.2f}s")
    print(f"Maximum latency:    {max(r['latency'] for r in results):.2f}s")
    print(f"Completed requests: {len(results)}")


if __name__ == "__main__":
    print("Warming up...")
    send_request(-1)

    for concurrency in [1, 5, 10]:
        benchmark(concurrency)

