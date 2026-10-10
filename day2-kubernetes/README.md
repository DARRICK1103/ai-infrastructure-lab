# Day 2 — Kubernetes Fundamentals

## Objective

Learn how Kubernetes manages containerized applications through Deployments, ReplicaSets, Pods, Services, and declarative YAML configurations.

## Environment

- Docker Desktop with WSL2
- Kubernetes v1.36.4
- Single-node kind cluster
- Namespace: `ai-infra`
- Application: Nginx (representing an inference API)

## Experiments

### 1. Deploy an application

Created an Nginx Deployment and verified the Pod reached the `Running` state.

### 2. Test self-healing

Manually deleted a running Pod. Kubernetes automatically created a replacement to maintain the desired replica count.

### 3. Horizontal scaling

Scaled the Deployment from 1 to 3 replicas using `kubectl scale`.

### 4. Service networking

Created a ClusterIP Service and verified that it selected three Pod endpoints. Used `kubectl port-forward` to access Nginx at `http://localhost:8080`.

### 5. Declarative infrastructure

Created `deployment.yaml` and `service.yaml`, applied them with `kubectl apply`, and scaled from 3 to 2 replicas by modifying the YAML configuration.

### 6. Rolling updates

Observed Kubernetes create a new ReplicaSet after changing the Pod template to include CPU and memory resource settings. The previous ReplicaSet was retained with zero replicas.

## Troubleshooting

The initial Kubernetes v1.37.0 cluster failed because the generated kubeadm configuration used the unsupported `kubeadm.k8s.io/v1beta3` API. Using Kubernetes v1.36.4 resolved the initialization failure.

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for a conceptual map of how traffic, controllers, and infrastructure relate.

Remember these three relationships:

- **Networking:** Ingress → Service → Pod
- **Application management:** Deployment → ReplicaSet → Pod
- **Infrastructure:** Cluster → Node → Pod → Container

A request does not pass through a Deployment or ReplicaSet — those manage Pods; they do not proxy HTTP.

## Key Takeaways

- Deployments define desired application state.
- ReplicaSets maintain the requested number of Pods.
- Kubernetes automatically replaces deleted Pods.
- Services provide stable networking for changing Pod endpoints.
- YAML manifests make deployments reproducible and version-controlled.
- Pod-template changes trigger a Deployment rollout.
- Multiple replicas on a single node do not provide node-level high availability.

## Next Steps

Deploy two separate applications — a FastAPI gateway and vLLM (or a CPU mock inference server) — each with its own Service. That demonstrates real service-to-service communication inside the cluster, rather than only accessing Nginx from the browser via port-forward.

Then explore readiness probes, liveness probes, rolling updates, and GPU scheduling.
