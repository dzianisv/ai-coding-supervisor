#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 Starting MCP Server Smoke Test...${NC}"

# Check if kind is installed
if ! command -v kind &> /dev/null; then
    echo -e "${RED}❌ kind is not installed. Please install it first: https://kind.sigs.k8s.io/docs/user/quick-start/#installation${NC}"
    exit 1
fi

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl is not installed. Please install it first: https://kubernetes.io/docs/tasks/tools/${NC}"
    exit 1
fi

# Check if helm is installed
if ! command -v helm &> /dev/null; then
    echo -e "${RED}❌ helm is not installed. Please install it first: https://helm.sh/docs/intro/install/${NC}"
    exit 1
fi

# Clean up any existing kind cluster
echo -e "${YELLOW}♻️  Cleaning up any existing kind cluster...${NC}"
kind delete cluster --name mcp-test 2>/dev/null || true

# Create a new kind cluster
echo -e "${YELLOW}🔄 Creating a new kind cluster...${NC}"
cat <<EOF | kind create cluster --name mcp-test --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
EOF

# Install NGINX Ingress
echo -e "${YELLOW}📦 Installing NGINX Ingress...${NC}"
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=180s

# Install cert-manager
echo -e "${YELLOW}📦 Installing cert-manager...${NC}"
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.2/cert-manager.yaml
kubectl wait --namespace cert-manager \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=webhook \
  --timeout=180s

# Build and load the Docker image
echo -e "${YELLOW}🐳 Building and loading Docker image...${NC}"
docker build -t mcp-server:test .
kind load docker-image mcp-server:test --name mcp-test

# Install the Helm chart
echo -e "${YELLOW}📊 Installing Helm chart...${NC}"
kubectl create namespace mcp-test 2>/dev/null || true
helm upgrade --install mcp-test ./deploy/k8s/chart \
  --namespace mcp-test \
  --set replicaCount=1 \
  --set image.repository=mcp-server \
  --set image.tag=test \
  --set image.pullPolicy=IfNotPresent \
  --set service.type=ClusterIP \
  --set ingress.enabled=true \
  --set ingress.className=nginx \
  --set ingress.hosts[0].host=mcp.local \
  --set ingress.hosts[0].paths[0].path=/ \
  --set ingress.hosts[0].paths[0].pathType=Prefix \
  --set resources.limits.cpu=100m \
  --set resources.limits.memory=128Mi \
  --set resources.requests.cpu=50m \
  --set resources.requests.memory=64Mi

# Wait for the deployment to be ready
echo -e "${YELLOW}⏳ Waiting for MCP Server to be ready...${NC}"
if ! kubectl wait --namespace mcp-test \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/name=mcp-server \
  --timeout=180s; then
  echo -e "${RED}❌ MCP Server pod failed to become ready${NC}"
  echo -e "${YELLOW}📝 Pod status:${NC}"
  kubectl get pods -n mcp-test
  echo -e "${YELLOW}📝 Pod logs:${NC}"
  kubectl logs -n mcp-test -l app.kubernetes.io/name=mcp-server
  exit 1
fi

# Test the health endpoint
echo -e "${YELLOW}🩺 Testing health endpoint...${NC}"
if ! kubectl run -i --rm --restart=Never --image=curlimages/curl curl-test \
  --namespace mcp-test -- /bin/sh -c '\
  for i in $(seq 1 10); do
    if curl -s http://mcp-test-mcp-server.mcp-test.svc.cluster.local:3333/healthz | grep -q "healthy"; then
      echo "✅ Health check passed";
      exit 0;
    fi;
    echo "⏳ Waiting for service to be ready...";
    sleep 5;
  done;
  echo "❌ Health check failed";
  exit 1;'; then
  echo -e "${RED}❌ Health check failed${NC}"
  exit 1
fi

# Test the API endpoint
echo -e "${YELLOW}🌐 Testing API endpoint...${NC}"
if ! kubectl run -i --rm --restart=Never --image=curlimages/curl curl-test \
  --namespace mcp-test -- /bin/sh -c '\
  if curl -s http://mcp-test-mcp-server.mcp-test.svc.cluster.local:3333/ | grep -q "MCP Server"; then
    echo "✅ API endpoint is working";
    exit 0;
  else
    echo "❌ API endpoint check failed";
    exit 1;
  fi'; then
  echo -e "${RED}❌ API test failed${NC}"
  exit 1
fi

echo -e "${GREEN}🎉 All tests passed! MCP Server is running correctly in Kubernetes.${NC}"

# Clean up
echo -e "${YELLOW}🧹 Cleaning up...${NC}"
kind delete cluster --name mcp-test

echo -e "${GREEN}✅ Smoke test completed successfully!${NC}"
