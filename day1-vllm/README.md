# Day 1 — GPU inference with vLLM

## Objective

Deploy an open-weight language model on a rented GPU, expose an OpenAI-compatible API, measure latency and throughput under concurrency, and inspect vLLM KV-cache metrics.

## Environment

| Component | Configuration |
| --- | --- |
| GPU | NVIDIA RTX A5000, 24 GB VRAM |
| Platform | RunPod |
| Model | `Qwen/Qwen3-8B` |
| Inference server | vLLM 0.31.0 |
| API | OpenAI-compatible `/v1/completions` and chat completions |
| Serving settings | `--dtype auto --enforce-eager --gpu-memory-utilization 0.95 --max-model-len 8128` |

### Serving the model

Set an API key in the environment (do not commit secrets):

```bash
export VLLM_API_KEY="your-key-here"
```

```bash
vllm serve Qwen/Qwen3-8B \
  --host 0.0.0.0 --port 8000 \
  --dtype auto --enforce-eager \
  --gpu-memory-utilization 0.95 \
  --max-model-len 8128 \
  --api-key "${VLLM_API_KEY}"
```

### Running the custom benchmarks

Scripts use only the Python standard library. From a shell with `VLLM_API_KEY` set and vLLM listening on `127.0.0.1:8000`:

```bash
cd day1-vllm/benchmarks
python benchmark.py      # short concurrency sweep
python benchmark_v2.py   # fixed 20-request workload
python benchmark_v3.py   # fixed 60-request workload
python benchmark_v4.py   # longer-prompt comparison
```

## Experiment 1 — Custom concurrency benchmarks

The first test sent as many requests as the configured concurrency level, each requesting 200 output tokens:

| Concurrency | Wall time | Output throughput |
| ---: | ---: | ---: |
| 1 | 4.94 s | 40.52 tok/s |
| 5 | 5.15 s | 194.09 tok/s |
| 10 | 5.22 s | 382.93 tok/s |

These are short bursts, not sustained-load capacity estimates.

### Fixed 20-request workload (128 output tokens/request)

| Concurrency | Wall time | Output throughput | Mean request latency |
| ---: | ---: | ---: | ---: |
| 1 | 63.34 s | 40.42 tok/s | 3.17 s |
| 5 | 13.22 s | 193.65 tok/s | 3.30 s |
| 10 | 6.74 s | 379.81 tok/s | 3.36 s |
| 20 | 3.47 s | 738.12 tok/s | 3.45 s |

### Fixed 60-request workload (128 output tokens/request)

| Concurrency | Wall time | Output throughput | Mean request latency | P95 request latency |
| ---: | ---: | ---: | ---: | ---: |
| 20 | 12.52 s | 613.30 tok/s | 4.15 s | 5.59 s |
| 40 | 7.13 s | 1077.78 tok/s | 3.59 s | 3.68 s |
| 60 | 3.73 s | 2061.08 tok/s | 3.66 s | 3.68 s |

**Interpretation:** vLLM can batch concurrent decode work, increasing aggregate throughput. The 60-request test was a short synthetic burst and should not be interpreted as sustainable 2,061 tok/s throughput or a verified 60-user production capacity. Prompt repetition and prefix caching may influence results.

## Experiment 2 — KV-cache monitoring

Queried vLLM's Prometheus metrics endpoint:

```bash
curl -s http://127.0.0.1:8000/metrics | grep -E '^vllm:.*(kv_cache|num_requests_running|num_requests_waiting)'
```

Observed snapshots:

| State | Running requests | Waiting requests | KV-cache usage |
| --- | ---: | ---: | ---: |
| Before load | 0 | 0 | 0% |
| During 20 concurrent requests | 20 | 0 | ~40.94% |
| After load | 0 | 0 | 0% |

The reported cache configuration included `kv_cache_size_tokens=48480`, `block_size=16`, and `num_gpu_blocks=3030`. The reported `kv_cache_max_concurrency≈5.96` corresponds to full-length sequences at the configured 8,128-token limit; it is **not** a hard limit on the number of short concurrent requests.

## Experiment 3 — Longer input prompt

With 20 requests at concurrency 20 and 128 output tokens per request:

| Workload | Wall time | Output throughput | Mean request latency |
| --- | ---: | ---: | ---: |
| Shorter prompt | 3.47 s | 738.12 tok/s | 3.45 s |
| Longer prompt | 6.05 s | 422.93 tok/s | 5.97 s |

Longer prompts require additional prefill work. The difference also may be affected by prompt reuse and caching; this experiment alone does not isolate prefill cost.

## Experiment 4 — Official vLLM serving benchmark

```bash
vllm bench serve \
  --backend vllm \
  --base-url http://127.0.0.1:8000 \
  --endpoint /v1/completions \
  --model Qwen/Qwen3-8B \
  --dataset-name random \
  --random-input-len 256 \
  --random-output-len 128 \
  --num-prompts 30 \
  --max-concurrency 10 \
  --request-rate inf \
  --temperature 0 \
  --header "Authorization=Bearer ${VLLM_API_KEY}" \
  --save-result \
  --result-dir ./results
```

**Saved run:**

| Metric | Result |
| --- | ---: |
| Successful / failed requests | 30 / 0 |
| Benchmark duration | 10.44 s |
| Total input / output tokens | 7,680 / 3,840 |
| Request throughput | 2.87 requests/s |
| Output throughput | 367.82 tok/s |
| Total token throughput | 1,103.45 tok/s |
| Mean / P99 TTFT | 121.69 / 158.71 ms |
| Mean / P99 TPOT | 26.40 / 26.64 ms |
| Mean / P99 inter-token latency | 26.40 / 28.77 ms |

An earlier run with the same benchmark arguments measured 330.26 output tok/s and 416.25 ms mean TTFT. The later run was faster, but the experiment does not establish why; warm-up and cache effects are possible explanations.

**Metric definitions:**

- **TTFT (time to first token):** delay until the first output token arrives.
- **TPOT (time per output token):** average interval for generating subsequent tokens.
- **Throughput:** aggregate work completed per second, not the speed experienced by one user.
- **KV cache:** GPU-resident attention key/value state used to avoid recomputing previous tokens during generation.

## Limitations and next experiments

1. Small, synthetic workloads; no sustained multi-minute load test.
2. Short prompts and output lengths do not represent all real-world use cases.
3. Repeated inputs, prefix caching, warm-up, and GPU state can affect results.
4. Snapshot-based KV-cache metrics may miss transient waiting or pressure.
5. Results apply to this model, GPU, configuration, and software environment; they are not universal vLLM performance claims.

Future work: vary prompt lengths independently, collect TTFT/TPOT under sustained arrival rates, compare cache settings, and add Prometheus/Grafana dashboards.

## Files in this directory

| Path | Purpose |
| --- | --- |
| `benchmarks/benchmark.py` | Short concurrency sweep (1 / 5 / 10), 200 output tokens |
| `benchmarks/benchmark_v2.py` | Fixed 20-request workload across concurrency levels |
| `benchmarks/benchmark_v3.py` | Fixed 60-request workload across concurrency levels |
| `benchmarks/benchmark_v4.py` | Longer-prompt comparison at concurrency 20 |
| `results/benchmark_results.txt` | Raw output from `benchmark.py` |
| `results/benchmark_v2_results.txt` | Raw output from `benchmark_v2.py` |
| `results/benchmark_v3_results.txt` | Raw output from `benchmark_v3.py` |
| `results/benchmark_v4_results.txt` | Raw output from `benchmark_v4.py` |
| `results/vllm-infqps-concurrency10-Qwen3-8B-*.json` | Official `vllm bench serve` saved result |

Raw outputs are kept so numbers in this report can be audited against the original runs.
