import os
import json
import time
import statistics
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

URL = "http://127.0.0.1:8000/v1/chat/completions"
MODEL = "Qwen/Qwen3-8B"
API_KEY = os.environ.get("VLLM_API_KEY")

TOTAL_REQUESTS = 20
MAX_TOKENS = 128

if not API_KEY:
    raise RuntimeError("VLLM_API_KEY missing")


def send_request(i):
    prompt = (
        f"Scenario {i}: Explain how a backend system handles "
        f"{100+i*17} simultaneous users. Discuss database "
        "connections, caching, and load balancing."
    )

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "stream": False,
    }

    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    start = time.perf_counter()

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.load(resp)

        return {
            "latency": time.perf_counter() - start,
            "tokens": data["usage"]["completion_tokens"],
            "ok": True,
        }
    except Exception as exc:
        print(f"Request {i} failed: {exc}")
        return {"ok": False}


def benchmark(concurrency):
    print(f"\nConcurrency: {concurrency}")

    start = time.perf_counter()
    results = []

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(send_request, i)
            for i in range(TOTAL_REQUESTS)
        ]
        for future in as_completed(futures):
            results.append(future.result())

    elapsed = time.perf_counter() - start
    successful = [r for r in results if r["ok"]]
    tokens = sum(r["tokens"] for r in successful)

    if not successful:
        print("All requests failed")
        return
    latencies = sorted(r["latency"] for r in successful)
    p95_index = max(0, int(0.95 * len(latencies) + 0.999999) - 1)

    print(f"Completed:       {len(successful)}/{TOTAL_REQUESTS}")
    print(f"Wall time:       {elapsed:.2f}s")
    print(f"Throughput:      {tokens/elapsed:.2f} tok/s")
    print(f"Mean latency:    {statistics.mean(latencies):.2f}s")
    print(f"P95 latency:     {latencies[p95_index]:.2f}s")
    print(f"Max latency:     {max(latencies):.2f}s")
    print(f"Output tokens:   {tokens}")


if __name__ == "__main__":
    for concurrency in [1, 5, 10, 20]:
        benchmark(concurrency)
