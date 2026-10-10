# Kubernetes Architecture — Conceptual Guide

Traffic flows through the networking path. Controllers manage workloads separately. Pods run **on** nodes — not inside a Deployment.

## Component responsibilities

| Component | Responsibility | Example |
| --- | --- | --- |
| Ingress / Gateway | Routes external HTTP requests | `/api/chat` → FastAPI |
| Service | Stable network endpoint for Pods | `inference-api:80` |
| Deployment | Declares how the application should run | `replicas: 2` |
| ReplicaSet | Maintains the requested number of Pods | Replaces deleted Pods |
| Pod | Smallest deployable Kubernetes unit | A running Nginx container |
| Container | Runs the application process | Nginx, FastAPI, vLLM |
| Node | Machine that runs Pods | EC2, VM, or local node |
| Cluster | Group of nodes managed by Kubernetes | Your Docker Desktop / kind cluster |

## Two different flows

The most important distinction: **networking** and **orchestration** are separate.

### A. Request flow (networking)

```text
Client
  ↓
Ingress / Gateway
  ↓
Service
  ↓
Pod
  ↓
Container
```

This is how an HTTP request reaches your application.

### B. Deployment flow (orchestration)

```text
Deployment
  ↓
ReplicaSet
  ↓
Pod
  ↓
Container
```

This is how Kubernetes creates, scales, updates, and replaces application instances.

A request does **not** pass through a Deployment or ReplicaSet. Those are management resources, not networking proxies.

## Applied to AI infrastructure

Imagine deploying a FastAPI gateway and a vLLM inference server:

```text
                         Internet
                            |
                            v
                      Load Balancer
                            |
                            v
                     Ingress / Gateway
                            |
                            v
                   FastAPI Service
                            |
                +-----------+-----------+
                |                       |
                v                       v
          FastAPI Pod 1            FastAPI Pod 2
                |                       |
                +-----------+-----------+
                            |
                            v
                      vLLM Service
                            |
                            v
                       vLLM Pod
                            |
                            v
                       GPU Node
```

In this architecture:

- The FastAPI Deployment might run 2–5 replicas.
- The FastAPI Service distributes connections among healthy FastAPI Pods.
- FastAPI Pods call the internal vLLM Service using Kubernetes DNS.
- The vLLM Pod runs on a GPU-enabled node.
- The vLLM Service stays private inside the cluster.

Example client call from FastAPI to vLLM:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://vllm-service.ai-infra.svc.cluster.local:8000/v1",
    api_key="empty",
)
```

Pod-to-Service traffic inside the cluster does not need `kubectl port-forward`.

## Where is the control plane?

The control plane includes the API server, scheduler, controllers, and etcd. These manage the cluster but are not normally on the HTTP path to your application.

When you run:

```bash
kubectl scale deployment inference-api --replicas=3 -n ai-infra
```

the control plane accepts the change, and Kubernetes works toward three Pods.

On Docker Desktop / a single-node kind cluster, the control plane and application Pods share one local node. In production they often run on separate machines.

## Three relationships to remember

| Path | Relationship |
| --- | --- |
| Networking | Ingress → Service → Pod |
| Application management | Deployment → ReplicaSet → Pod |
| Infrastructure | Cluster → Node → Pod → Container |

Once these three relationships are clear, the rest of Kubernetes architecture is much easier to place.
