# AI Infrastructure Lab

Hands-on engineering lab for **self-hosted LLM inference**: deploy open-weight models with vLLM, measure real GPU performance, and build toward Kubernetes-based serving with observability.

This repository is a portfolio project. Each day produces runnable experiments, raw results, and written interpretation — not just notes.

## What this demonstrates

- Deploying and serving open-weight LLMs with [vLLM](https://github.com/vllm-project/vllm)
- Concurrency, throughput, latency, TTFT/TPOT, and KV-cache behavior
- Reproducible benchmarking with preserved raw outputs
- Clear separation between synthetic load tests and production claims
- (Upcoming) Kubernetes manifests, Prometheus/Grafana, and serving architecture

## Lab roadmap

| Day | Topic | Status |
| --- | --- | --- |
| 1 | GPU inference with vLLM and performance benchmarking | Completed |
| 2 | Kubernetes fundamentals and inference deployment manifests | Planned |
| 3 | Prometheus and Grafana monitoring | Planned |
| 4 | Reliability, scaling, and serving architecture | Planned |
| 5 | Integration and final architecture review | Planned |

## Day 1 highlight — GPU inference and benchmarking

Deployed `Qwen/Qwen3-8B` with vLLM on an **NVIDIA RTX A5000 (24 GB)**, then measured inference throughput, latency, and KV-cache usage under concurrent load.

**Official vLLM serving benchmark (saved run):**

| Metric | Value |
| --- | ---: |
| Successful / failed requests | 30 / 0 |
| Max concurrency | 10 |
| Input / output tokens per request | 256 / 128 |
| Output throughput | **367.82 tok/s** |
| Mean TTFT | 121.69 ms |
| Mean TPOT | 26.40 ms |

Full commands, custom concurrency experiments, KV-cache observations, and limitations: **[Day 1 lab report](day1-vllm/README.md)**.

## Repository layout

```text
ai-infrastructure-lab/
├── README.md                 # Portfolio overview
├── day1-vllm/
│   ├── README.md             # Lab report and interpretation
│   ├── benchmarks/           # Custom concurrency benchmark scripts
│   └── results/              # Raw .txt / .json measurement outputs
└── (day2+ folders as the lab progresses)
```

## Principles

- Keep raw measurements next to conclusions so results can be audited.
- Distinguish synthetic benchmarks from sustained production workloads.
- Record hardware and software configuration for reproducibility.
- Never commit credentials, private keys, model weights, or virtual environments.

## Reproducing experiments

Day 1 requires a GPU host that can run Qwen3-8B with vLLM (tested on a rented RTX A5000 via RunPod). Later Kubernetes exercises can often be done locally without a GPU.

See [day1-vllm/README.md](day1-vllm/README.md) for serving commands and how to run the benchmarks.

> This repository documents learning experiments. It does not claim production-grade reliability or capacity.

## License

MIT — see [LICENSE](LICENSE).
