# Day 3 — Service-to-Service Communication

## Objective

Deploy two applications on Kubernetes — a mock inference server and an API gateway — and prove they communicate through ClusterIP Service DNS inside the cluster, without exposing inference publicly for app-to-app traffic.

## Environment

Two local cluster options work for this lab:

| | Docker Desktop Kubernetes | Standalone `kind` |
| --- | --- | --- |
| What it is | Cluster managed by Docker Desktop | CLI tool that creates clusters as Docker containers |
| How you manage it | Docker Desktop UI / settings | `kind create/delete/get clusters` |
| Local image load | Desktop node may not see `docker build` images the way you expect | `kind load docker-image ... --name <cluster>` |
| Image source for this lab | Usually Docker Hub (registry pull) | Local image via `kind load` + `imagePullPolicy: Never` |
| Best for | Convenient Deployments / Services / DNS | Explicit control, multi-cluster experiments, CI |

Docker Desktop may use kind-style node images under the hood, but that does **not** mean the standalone `kind` CLI is installed or that `kind get clusters` will list the Desktop cluster.

Pick **one** path below and stay on that cluster for the rest of Day 3.

## Repository layout

```text
day3-service-communication/
├── README.md
├── mock-inference/
│   ├── main.py              # FastAPI /health and /generate
│   ├── requirements.txt
│   └── Dockerfile
├── api-gateway/
│   ├── main.py              # FastAPI /health and /chat → calls mock-inference
│   ├── requirements.txt
│   └── Dockerfile
└── k8s/
    ├── mock-deployment.yaml
    ├── mock-service.yaml
    ├── gateway-deployment.yaml
    └── gateway-service.yaml
```

## Roles of each piece

| Artifact | Role |
| --- | --- |
| `Dockerfile` | Builds the application image |
| Deployment | Runs and manages Pods (replicas, probes, resources) |
| Service | Stable in-cluster network endpoint for those Pods |

In-cluster DNS names:

```text
http://mock-inference.ai-infra.svc.cluster.local:8000
http://ai-api-gateway.ai-infra.svc.cluster.local:8000
```

Short names also work inside the same namespace (`http://mock-inference:8000`).

## With vs without the API gateway

```text
Without gateway (direct to inference):

  Client  --port-forward-->  mock-inference Service  -->  mock Pods
  POST /generate


With gateway (two-service architecture):

  Client  --port-forward-->  ai-api-gateway Service  -->  gateway Pods
                                      |
                                      |  INFERENCE_URL=http://mock-inference:8000
                                      v
                               mock-inference Service  -->  mock Pods
  POST /chat  ---------------------->  POST /generate
```

| | Without gateway | With gateway |
| --- | --- | --- |
| What the client calls | `mock-inference` directly (`/generate`) | `ai-api-gateway` (`/chat`) |
| Who knows about inference | Every client | Only the gateway |
| Response shape | Raw inference JSON | Gateway wrapper (`gateway_pod` + `inference`) |
| Scaling / ownership | Clients coupled to inference API | Inference can change behind the gateway |
| Typical production pattern | Rare for public entry | Common: public/edge API → private inference |

Without a gateway, a client must speak the inference API and reach that Service (or be given a port-forward to it). With a gateway, clients hit a front-door API; gateway Pods call `http://mock-inference:8000` over cluster DNS. Inference can stay private inside the cluster while only the gateway is exposed later (Ingress / LoadBalancer).

---

## Path A — Standalone `kind` + local image

No Docker Hub required. Build locally, load the image into the kind node, tell Kubernetes never to pull from a registry.

### A1. Install / verify `kind` and tools

```powershell
kind version
kubectl version --client
docker version
```

If `kind` is not recognized, install it and open a **new** PowerShell so PATH updates apply:
[kind quick start](https://kind.sigs.k8s.io/docs/user/quick-start/#installation).

### A2. Create a cluster

```powershell
kind create cluster --name ai-infra-lab
kubectl config current-context
kubectl get nodes
```

Expected context: `kind-ai-infra-lab`.

### A3. Build the image on the host

```powershell
cd C:\Users\darrick\Desktop\Projects\ai-infrastructure-lab\day3-service-communication\mock-inference
docker build -t mock-inference:v1 .
docker images mock-inference
```

### A4. Load the image into the kind node

`docker build` puts the image on your machine. The kind node is a separate container — load the image into it:

```powershell
kind load docker-image mock-inference:v1 --name ai-infra-lab
docker exec ai-infra-lab-control-plane crictl images | Select-String mock-inference
```

You should see `docker.io/library/mock-inference` (or similar) listed on the node.

### A5. Point the Deployment at the local image

In `k8s/mock-deployment.yaml`, set:

```yaml
image: mock-inference:v1
imagePullPolicy: Never
```

`Never` is required so kubelet does not try to pull `mock-inference:v1` from Docker Hub.

### A6. Create namespace and apply manifests

```powershell
cd C:\Users\darrick\Desktop\Projects\ai-infrastructure-lab\day3-service-communication
kubectl create namespace ai-infra
kubectl apply -f k8s/mock-deployment.yaml
kubectl apply -f k8s/mock-service.yaml
kubectl rollout status deployment/mock-inference -n ai-infra --timeout=120s
kubectl get pods -n ai-infra
kubectl get svc -n ai-infra
```

Expect two Pods `1/1 Running` and a ClusterIP Service on port `8000`.

### A7. Deploy the API gateway (kind + local image)

After mock-inference is Running:

```powershell
cd C:\Users\darrick\Desktop\Projects\ai-infrastructure-lab\day3-service-communication
docker build -t ai-api-gateway:v1 ./api-gateway
kind load docker-image ai-api-gateway:v1 --name ai-infra-lab
kubectl apply -f k8s/gateway-deployment.yaml
kubectl apply -f k8s/gateway-service.yaml
kubectl rollout status deployment/ai-api-gateway -n ai-infra --timeout=120s
kubectl get pods -n ai-infra
kubectl get svc -n ai-infra
```

Expect four Pods (2 gateway + 2 mock) and two Services.

The gateway Deployment sets:

```yaml
env:
  - name: INFERENCE_URL
    value: "http://mock-inference:8000"
```

That is Kubernetes DNS for the mock Service in the same namespace.

### A8. Verify

Continue at [Verify the deployment](#verify-the-deployment).

### A9. Useful kind cleanup / reset commands

```powershell
kind get clusters
kubectl config use-context kind-ai-infra-lab
kind delete cluster --name ai-infra-lab
```

---

## Path B — Docker Hub registry (Docker Desktop or any cluster)

Production-style flow: build → tag → push → Kubernetes pulls the image.

### B1. Confirm cluster context

```powershell
kubectl config current-context
kubectl get nodes
```

For Docker Desktop this is often `docker-desktop`.

### B2. Build and tag

```powershell
cd C:\Users\darrick\Desktop\Projects\ai-infrastructure-lab\day3-service-communication\mock-inference
docker build -t mock-inference:v1 .
docker tag mock-inference:v1 YOUR_DOCKERHUB_USERNAME/mock-inference:v1
docker images mock-inference
```

### B3. Push (public repo for this lab)

```powershell
docker login
docker push YOUR_DOCKERHUB_USERNAME/mock-inference:v1
```

### B4. Point the Deployment at the registry image

In `k8s/mock-deployment.yaml`, set:

```yaml
image: YOUR_DOCKERHUB_USERNAME/mock-inference:v1
imagePullPolicy: IfNotPresent
```

Do not leave the literal string `YOUR_DOCKERHUB_USERNAME` — that produces `InvalidImageName`.

### B5. Create namespace and apply manifests

```powershell
cd C:\Users\darrick\Desktop\Projects\ai-infrastructure-lab\day3-service-communication
kubectl create namespace ai-infra
kubectl apply -f k8s/mock-deployment.yaml
kubectl apply -f k8s/mock-service.yaml
kubectl rollout status deployment/mock-inference -n ai-infra --timeout=120s
kubectl get pods -n ai-infra
kubectl get svc -n ai-infra
```

### B6. Deploy the API gateway (registry)

```powershell
cd C:\Users\darrick\Desktop\Projects\ai-infrastructure-lab\day3-service-communication
docker build -t ai-api-gateway:v1 ./api-gateway
docker tag ai-api-gateway:v1 YOUR_DOCKERHUB_USERNAME/ai-api-gateway:v1
docker push YOUR_DOCKERHUB_USERNAME/ai-api-gateway:v1
```

Update `k8s/gateway-deployment.yaml` `image:` to `YOUR_DOCKERHUB_USERNAME/ai-api-gateway:v1`, then:

```powershell
kubectl apply -f k8s/gateway-deployment.yaml
kubectl apply -f k8s/gateway-service.yaml
kubectl rollout status deployment/ai-api-gateway -n ai-infra --timeout=120s
kubectl get pods -n ai-infra
kubectl get svc -n ai-infra
```

---

## Verify the deployment

Use these after Path A or Path B once Pods are Ready.

### In-cluster DNS — mock inference

```powershell
kubectl run dns-test -n ai-infra --image=curlimages/curl:8.12.1 --restart=Never --rm -i -- curl -s http://mock-inference.ai-infra.svc.cluster.local:8000/health
```

Expected:

```json
{"status":"healthy"}
```

### In-cluster DNS — gateway → inference

```powershell
kubectl run gateway-dns-test -n ai-infra --image=curlimages/curl:8.12.1 --restart=Never --rm -i -- curl -s -X POST http://ai-api-gateway.ai-infra.svc.cluster.local:8000/chat -H "Content-Type: application/json" -d "{\"message\":\"hello\"}"
```

Expected shape (values vary by Pod):

```json
{
  "gateway_pod": "ai-api-gateway-...",
  "inference": {
    "model": "mock-llm",
    "response": "Mock LLM response to: hello",
    "pod_name": "mock-inference-..."
  }
}
```

That is the Day 3 result: client → gateway Service → gateway Pod → mock Service → mock Pod.

### Optional: reach Services from the host

Direct to inference (without gateway):

```powershell
kubectl port-forward svc/mock-inference 8000:8000 -n ai-infra
```

```powershell
curl.exe http://localhost:8000/health
curl.exe -X POST http://localhost:8000/generate -H "Content-Type: application/json" -d "{\"prompt\":\"hello\"}"
```

Through the gateway — Terminal 1 (keep running):

```powershell
kubectl port-forward svc/ai-api-gateway 8080:8000 -n ai-infra
```

Terminal 2 — either `curl.exe` or PowerShell:

```powershell
curl.exe http://localhost:8080/health
curl.exe -X POST http://localhost:8080/chat -H "Content-Type: application/json" -d "{\"message\":\"hello\"}"
```

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8080/chat" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"Explain Kubernetes"}' |
  ConvertTo-Json -Depth 5
```

Expected `/chat` shape (Pod names differ):

```json
{
  "gateway_pod": "ai-api-gateway-xxxxx",
  "inference": {
    "model": "mock-llm",
    "response": "Mock LLM response to: Explain Kubernetes",
    "pod_name": "mock-inference-xxxxx"
  }
}
```

Also useful after deploy:

```powershell
kubectl get deployments,pods,services -n ai-infra
```

Port-forward is for laptop access. In-cluster clients should use Service DNS.

### Debug if rollout stalls

```powershell
kubectl get pods -n ai-infra
kubectl describe pod -n ai-infra -l app=mock-inference
kubectl describe pod -n ai-infra -l app=ai-api-gateway
kubectl logs -n ai-infra -l app=mock-inference --tail=50
kubectl logs -n ai-infra -l app=ai-api-gateway --tail=50
```

---

## Experiment — Scaling and load distribution

Requires gateway port-forward on `localhost:8080`:

```powershell
kubectl port-forward svc/ai-api-gateway 8080:8000 -n ai-infra
```

### 1. Send 10 requests

In a second PowerShell terminal:

```powershell
1..10 | ForEach-Object {
    $result = Invoke-RestMethod `
        -Uri "http://localhost:8080/chat" `
        -Method Post `
        -ContentType "application/json" `
        -Body '{"message":"Hello Kubernetes"}'

    Write-Host "Gateway: $($result.gateway_pod) | Inference: $($result.inference.pod_name)"
}
```

Observe which gateway and inference Pods respond.

**Caveat:** `kubectl port-forward svc/ai-api-gateway` typically sticks to **one** backend Pod for that session. You may see the same `gateway_pod` repeatedly — that is not a reliable load-balancing test across gateway replicas.

Gateway → `mock-inference` uses normal Service networking, so inference `pod_name` values may still vary across requests.

### 2. Scale inference from 2 to 4

```powershell
kubectl scale deployment mock-inference --replicas=4 -n ai-infra
kubectl rollout status deployment/mock-inference -n ai-infra
kubectl get pods -n ai-infra
```

Expect four inference Pods (plus two gateway Pods).

### 3. Send 10 requests again

Repeat the PowerShell loop from step 1. Check whether inference Pod names change. Services distribute among eligible endpoints, but a small sample is not always even.

### 4. Test self-healing

```powershell
kubectl get pods -n ai-infra -l app=mock-inference
kubectl delete pod YOUR_INFERENCE_POD_NAME -n ai-infra
kubectl get pods -n ai-infra -w
```

Kubernetes should create a replacement to keep four replicas. Press `Ctrl+C` to stop watching.

Deleting a Pod demonstrates recovery; it does **not** guarantee zero failed in-flight requests.

### 5. Restore replica count

```powershell
kubectl scale deployment mock-inference --replicas=2 -n ai-infra
```

Keep `replicas: 2` in `k8s/mock-deployment.yaml` so a later `kubectl apply` does not surprise you with a different count.

### What this tests

| Kubernetes feature | What you exercise |
| --- | --- |
| Service | Routing to eligible Pods |
| Deployment | Desired replica count |
| ReplicaSet | Creating replacement Pods |
| Readiness probe | Keeping unready Pods out of endpoints |
| Self-healing | Recovering after a deleted Pod |

### Observed results (this lab)

| Experiment | Result | Meaning |
| --- | --- | --- |
| Scale 2 → 4 | Four inference Pods became Ready | Deployment maintained desired replicas |
| Send 10 requests | Requests reached different inference Pods | Service distributed connections |
| Delete a Pod | A replacement Pod appeared | ReplicaSet restored the desired count |
| Wait for readiness | Replacement went `0/1` → `1/1` | Readiness check passed |
| Scale 4 → 2 | Two inference Pods remained | Excess replicas removed |

Gateway Pod name stayed the same across the port-forward session (`ai-api-gateway-84849cd56b-f6htt`) — expected for port-forward, not Service load balancing.

---

## Experiment — Downstream inference unavailable

Demonstrates a **healthy gateway** when **all** inference Pods are gone (not just one deleted Pod).

Keep gateway port-forward on `localhost:8080`.

### 1. Scale inference to zero

```powershell
kubectl scale deployment mock-inference --replicas=0 -n ai-infra
kubectl get pods -n ai-infra
kubectl get endpointslice -n ai-infra -l kubernetes.io/service-name=mock-inference
```

The `mock-inference` Service still exists, but ready endpoints should be empty / unset.

### 2. Call the gateway

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8080/chat" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"Hello"}'
```

Expected body (HTTP 502 from FastAPI):

```json
{"detail":"Inference service unavailable"}
```

`Invoke-RestMethod` throws a PowerShell error for non-2xx responses — that means the HTTP call failed as designed, not that the gateway process crashed.

What happened:

1. Inference scaled to zero replicas.
2. Service had no ready endpoints.
3. Gateway called `http://mock-inference:8000/generate`.
4. The HTTP call failed; the gateway handler returned 502.

### 3. Recover

```powershell
kubectl scale deployment mock-inference --replicas=2 -n ai-infra
kubectl rollout status deployment/mock-inference -n ai-infra
```

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8080/chat" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"Hello"}' |
  ConvertTo-Json -Depth 5
```

`/chat` should succeed again once Pods are Ready.

### Observed result (this lab)

With inference at zero: `{"detail":"Inference service unavailable"}`.  
After scaling back to 2: successful `/chat` with `gateway_pod` + `inference` payload.

### Liveness vs readiness vs dependency health

The gateway `/health` currently always returns `{"status":"healthy"}`, even when inference is down. That is process health, not “can serve AI chat.”

| Check | Question |
| --- | --- |
| Liveness | Is this process alive? (restart if not) |
| Readiness | Should this Pod receive traffic? |
| Dependency health | Are downstream services (vLLM, Redis, DB) available? |

Do **not** restart a healthy gateway solely because a temporary inference outage — surface 502/503 to clients (and optional dependency status) instead.

---

## Application APIs

### mock-inference

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Readiness / liveness probe target |
| `POST` | `/generate` | Mock completion; body `{"prompt":"..."}`; includes `pod_name` |

### ai-api-gateway

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Readiness / liveness probe target |
| `POST` | `/chat` | Client entrypoint; body `{"message":"..."}`; calls mock `/generate` via `INFERENCE_URL` |

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `InvalidImageName` | Placeholder still in `image:` | Use a real `username/repo:tag` or `mock-inference:v1` |
| `ImagePullBackOff` (Path B) | Private repo or wrong name/tag | Make Hub repo public; fix tag; push again |
| `ErrImageNeverPull` / image missing (Path A) | Image not loaded into kind node | Re-run `kind load docker-image mock-inference:v1 --name ai-infra-lab` and keep `imagePullPolicy: Never` |
| `kind: command not found` | Standalone kind CLI not on PATH | Install kind, or use Path B on Docker Desktop |
| Rollout waits forever | Pods not Ready | `kubectl describe pod` — check Events and probes |
| `curl http://localhost:8000` fails with no port-forward | ClusterIP is not on the host | Use DNS test or `kubectl port-forward` |
| Wrong cluster | `kubectl` context points elsewhere | `kubectl config get-contexts` then `kubectl config use-context ...` |

## Key takeaways

- Dockerfile builds the image; Deployment runs it; Service publishes it inside the cluster.
- ClusterIP + DNS is how Pods talk to each other without exposing every app publicly.
- The gateway is the client-facing API; inference stays an internal dependency at `http://mock-inference:8000`.
- Scaling a Deployment changes how many Pods a Service can select; `kubectl port-forward` is a poor test of gateway-side load balancing.
- Self-healing restores replica count after Pod deletion; in-flight requests can still fail.
- Scale-to-zero leaves the Service in place with no endpoints; the gateway can stay up and return 502.
- Gateway liveness ≠ dependency health — do not kill the gateway just because inference is temporarily down.
- Standalone `kind`: load local images with `kind load` (and prefer `imagePullPolicy: Never` for bare local tags).
- Registry path: push once, then any cluster can pull with `IfNotPresent` / `Always`.
- Docker Desktop Kubernetes and standalone `kind` are different management paths — do not mix `kind load` with the Desktop context unless you know that node is your kind cluster.

## Day 3 learning checklist

- [x] Docker image build and kind image loading
- [x] Deployment and Service manifests
- [x] Kubernetes internal DNS
- [x] Gateway → inference communication
- [x] Horizontal scaling and traffic distribution
- [x] Pod deletion and self-healing
- [x] Downstream service failure and recovery (scale to zero → 502 → restore)

## Status

- [x] FastAPI mock inference app and Dockerfile
- [x] mock-inference Deployment and Service
- [x] Healthy mock-inference Pods + ClusterIP Service
- [x] FastAPI API gateway app and Dockerfile
- [x] ai-api-gateway Deployment and Service (calls mock over DNS)
- [x] Scaling / load-distribution / self-healing experiment
- [x] Downstream failure (replicas=0) → 502 → recovery
- [ ] Confirm in-cluster `/chat` DNS test from a curl Pod (optional if port-forward path already verified)

## Next steps

Document Day 3 as complete in the portfolio root README, then Day 4: resource requests/limits, scheduling, and multi-node architecture. Optionally expose only the gateway (Ingress / LoadBalancer) and swap mock inference for a real vLLM Service behind the same `INFERENCE_URL`.
