# ColdChain AI — Complete DevOps Pipeline Guide
## All 7 Phases with Commands and Screenshots Checklist

---

## ML PREDICTION BUG — WHAT WAS WRONG & HOW IT WAS FIXED

### Root Cause
`test_predictions.py` was passing a raw NumPy array to sklearn models:
```python
# BROKEN — causes wrong predictions + UserWarning
feat = np.array([[food_enc, veh_enc, tod_enc, travel, ...]])
```

The models were **trained** on a `pd.DataFrame` with named columns. Passing
a raw array means sklearn cannot verify column order, which can silently
produce incorrect predictions and always throws:
```
UserWarning: X does not have valid feature names, but RandomForestClassifier
was fitted with feature names
```

### Fix Applied (3 changes)
1. **`test_predictions.py`** — Changed `np.array` → `pd.DataFrame(cols=FEATURE_COLS)`
2. **`api/app.py`** — Added input validation against `le_xxx.classes_` before `.transform()`
3. **`api/app.py`** — Added `/health` endpoint required by Kubernetes probes
4. **`frontend/js/app.js`** — Fixed health check URL from `/` to `/health`; added
   `window.COLDCHAIN_API_URL` so AKS LoadBalancer IP works in production

---

## PREREQUISITES — Install These First

```bash
# 1. Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
az --version

# 2. Terraform
wget https://releases.hashicorp.com/terraform/1.7.0/terraform_1.7.0_linux_amd64.zip
unzip terraform_1.7.0_linux_amd64.zip && sudo mv terraform /usr/local/bin/
terraform --version

# 3. kubectl
az aks install-cli
kubectl version --client

# 4. Docker
sudo apt-get install docker.io -y
sudo usermod -aG docker $USER
newgrp docker
docker --version

# 5. Ansible
pip install ansible
ansible --version

# 6. Python 3.11+
python3 --version
pip install -r coldchain_ai/requirements.txt
```

---

## PHASE 1 — Source Code and Version Control

### Step 1.1 — Initialize Git Repository
```bash
cd coldchain_devops
git init
git add .
git commit -m "Initial commit: ColdChain AI with ML prediction fix"
```

### Step 1.2 — Create GitHub Repository
1. Go to https://github.com/new
2. Name it `coldchain-ai`
3. Keep it **Private**
4. Do NOT initialize with README (you already have one)

### Step 1.3 — Push to GitHub
```bash
git remote add origin https://github.com/YOUR_USERNAME/coldchain-ai.git
git branch -M main
git push -u origin main
```

### Step 1.4 — Create a Feature Branch (best practice)
```bash
git checkout -b feature/ml-fix
# Make changes, then:
git add .
git commit -m "fix: use pd.DataFrame for sklearn predictions"
git push origin feature/ml-fix
# Create Pull Request on GitHub, then merge to main
```

**Screenshot checklist:** GitHub repo page showing commits, branches

---

## PHASE 2 — Containerization (Docker)

### Step 2.1 — Build Docker Image Locally
```bash
cd coldchain_devops
docker build -t coldchain-ai:latest .
```

### Step 2.2 — Run and Test Locally
```bash
docker run -d -p 5000:5000 --name coldchain-test coldchain-ai:latest

# Test health endpoint
curl http://localhost:5000/health
# Expected: {"status":"ok"}

# Test ML prediction
curl -X POST http://localhost:5000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "food_type": "Milk",
    "vehicle_type": "Normal Truck",
    "time_of_day": "afternoon",
    "travel_hours": 8,
    "ambient_temp_c": 38,
    "humidity_pct": 72,
    "quantity": 200,
    "cost_per_unit": 50
  }'
# Expected: JSON with ml_predictions and prediction_summary

# Stop container
docker stop coldchain-test && docker rm coldchain-test
```

### Step 2.3 — Azure Login and Create ACR
```bash
az login

# Create ACR (skip if using Terraform in Phase 3)
az acr create \
  --resource-group coldchain-rg \
  --name coldchainacr \
  --sku Basic \
  --admin-enabled true
```

### Step 2.4 — Push to ACR
```bash
az acr login --name coldchainacr

# Tag with ACR address
docker tag coldchain-ai:latest coldchainacr.azurecr.io/coldchain-ai:latest
docker tag coldchain-ai:latest coldchainacr.azurecr.io/coldchain-ai:v1.0

# Push
docker push coldchainacr.azurecr.io/coldchain-ai:latest
docker push coldchainacr.azurecr.io/coldchain-ai:v1.0

# Verify it's in ACR
az acr repository list --name coldchainacr --output table
az acr repository show-tags --name coldchainacr --repository coldchain-ai --output table
```

**Screenshot checklist:** Docker build output, ACR repository list in Azure Portal

---

## PHASE 3 — Infrastructure Provisioning (Terraform)

### Step 3.1 — Set Up Azure Service Principal
```bash
# Create Service Principal for Terraform and GitHub Actions
az ad sp create-for-rbac \
  --name "coldchain-sp" \
  --role Contributor \
  --scopes /subscriptions/$(az account show --query id -o tsv) \
  --sdk-auth

# SAVE the output JSON — you'll need it for GitHub Secrets
# It looks like:
# {
#   "clientId": "...",
#   "clientSecret": "...",
#   "subscriptionId": "...",
#   "tenantId": "..."
# }
```

### Step 3.2 — Configure Terraform Variables
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your ACR name (must be globally unique)
nano terraform.tfvars
```

### Step 3.3 — Set Environment Variables for Terraform
```bash
export ARM_CLIENT_ID="your-client-id"
export ARM_CLIENT_SECRET="your-client-secret"
export ARM_SUBSCRIPTION_ID="your-subscription-id"
export ARM_TENANT_ID="your-tenant-id"
```

### Step 3.4 — Run Terraform
```bash
cd terraform

# Initialize — downloads Azure provider
terraform init

# Preview what will be created
terraform plan

# Create infrastructure (takes ~5-10 minutes for AKS)
terraform apply
# Type 'yes' when prompted

# Save outputs
terraform output acr_login_server
terraform output aks_cluster_name
```

### Step 3.5 — Verify in Azure Portal
```bash
az group list --output table
az acr list --output table
az aks list --output table
```

**Screenshot checklist:**
- `terraform apply` success output
- Azure Portal showing Resource Group with ACR + AKS

---

## PHASE 4 — Configuration Management (Ansible)

### Step 4.1 — Get AKS Credentials
```bash
az aks get-credentials \
  --resource-group coldchain-rg \
  --name coldchain-aks

# Verify connection
kubectl get nodes
# Expected: 2 nodes in Ready state
```

### Step 4.2 — Run Ansible Playbook
```bash
cd coldchain_devops

ansible-playbook ansible/playbook.yml \
  -e "resource_group=coldchain-rg" \
  -e "aks_cluster=coldchain-aks" \
  -e "acr_name=coldchainacr" \
  -e "image_tag=latest"
```

### Step 4.3 — Manual kubectl apply (alternative to Ansible)
```bash
# Replace image placeholder manually
sed 's|IMAGE_PLACEHOLDER|coldchainacr.azurecr.io/coldchain-ai:latest|g' \
  k8s/deployment.yaml | kubectl apply -f -

kubectl apply -f k8s/service.yaml
```

**Screenshot checklist:** Ansible playbook run output showing all tasks OK/Changed

---

## PHASE 5 — CI/CD Pipeline Setup (GitHub Actions)

### Step 5.1 — Add GitHub Secrets
1. Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** for each:

| Secret Name | Value |
|---|---|
| `AZURE_CLIENT_ID` | clientId from Service Principal JSON |
| `AZURE_CLIENT_SECRET` | clientSecret from Service Principal JSON |
| `AZURE_SUBSCRIPTION_ID` | subscriptionId from Service Principal JSON |
| `AZURE_TENANT_ID` | tenantId from Service Principal JSON |
| `ACR_NAME` | `coldchainacr` |
| `AKS_CLUSTER_NAME` | `coldchain-aks` |
| `RESOURCE_GROUP` | `coldchain-rg` |

### Step 5.2 — Trigger the Pipeline
```bash
# Push any change to main to trigger the pipeline
git add .
git commit -m "ci: trigger pipeline test"
git push origin main
```

### Step 5.3 — Monitor Pipeline
1. Go to GitHub repo → **Actions** tab
2. Click the running workflow
3. Watch Jobs: `test` → `build-and-push` → `deploy`

**Screenshot checklist:** GitHub Actions showing all 3 jobs green ✅

---

## PHASE 6 — Deployment and Validation

### Step 6.1 — Verify Pods Running
```bash
kubectl get pods
# Expected output:
# NAME                            READY   STATUS    RESTARTS   AGE
# coldchain-ai-7d6f9b8c4-abcde   1/1     Running   0          2m
# coldchain-ai-7d6f9b8c4-fghij   1/1     Running   0          2m
```

### Step 6.2 — Verify Service and Get Public IP
```bash
kubectl get svc
# Expected output:
# NAME                     TYPE           CLUSTER-IP     EXTERNAL-IP      PORT(S)        AGE
# coldchain-ai-service     LoadBalancer   10.0.xxx.xxx   20.xx.xx.xx      80:30xxx/TCP   3m

# Get just the IP
kubectl get svc coldchain-ai-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

### Step 6.3 — Test the Deployed API
```bash
# Replace with your actual LoadBalancer IP
export API_IP=$(kubectl get svc coldchain-ai-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Health check
curl http://$API_IP/health

# ML Prediction test
curl -X POST http://$API_IP/predict \
  -H "Content-Type: application/json" \
  -d '{"food_type":"Fish","vehicle_type":"Normal Truck","time_of_day":"afternoon","travel_hours":6,"ambient_temp_c":40,"humidity_pct":80,"quantity":100,"cost_per_unit":300}'
```

### Step 6.4 — Check Pod Logs
```bash
kubectl logs -l app=coldchain-ai --tail=50
kubectl describe pod -l app=coldchain-ai
```

### Step 6.5 — Update Frontend to Point to AKS
Open `coldchain_ai/frontend/index.html` and add before `</head>`:
```html
<script>
  // In production, point to AKS LoadBalancer IP
  window.COLDCHAIN_API_URL = 'http://YOUR_LOADBALANCER_IP';
</script>
```

**Screenshot checklist:**
- `kubectl get pods` showing 2/2 Running
- `kubectl get svc` showing External-IP
- Browser accessing the frontend with ML predictions working
- curl response from AKS LoadBalancer IP

---

## PHASE 7 — Documentation & Cleanup

### Step 7.1 — Check All Resources
```bash
az resource list --resource-group coldchain-rg --output table
```

### Step 7.2 — Destroy Resources (after evaluation)
```bash
cd terraform
terraform destroy
# Type 'yes' when prompted
# This deletes: AKS, ACR, Resource Group — ALL data is lost

# Verify deletion
az group list --output table
```

---

## QUICK TROUBLESHOOTING

### ML Prediction Returns Wrong Values
```bash
# Run the fixed test script
cd coldchain_ai
python test_predictions.py
# Should show predictions with no sklearn warnings
```

### Pod CrashLoopBackOff
```bash
kubectl describe pod <pod-name>
kubectl logs <pod-name> --previous
# Common cause: wrong ACR image URL or missing models/ directory in image
```

### ImagePullBackOff
```bash
# Check AKS has AcrPull role (Terraform does this automatically)
az role assignment list --scope $(az acr show --name coldchainacr --query id -o tsv)
```

### Terraform Apply Fails
```bash
# Ensure environment variables are set
echo $ARM_CLIENT_ID
echo $ARM_SUBSCRIPTION_ID
# Re-run: terraform init -reconfigure
```

### GitHub Actions Fails at Azure Login
- Verify all 4 Azure secrets are set correctly in GitHub
- Ensure Service Principal has Contributor role on subscription

---

## PROJECT FOLDER STRUCTURE

```
coldchain_devops/
├── coldchain_ai/
│   ├── api/
│   │   └── app.py              ← FIXED: validation + /health endpoint
│   ├── models/
│   │   ├── rf_classifier.pkl
│   │   ├── gb_regressor.pkl
│   │   ├── rf_risk.pkl
│   │   ├── le_*.pkl
│   │   ├── metadata.json
│   │   └── train_models.py
│   ├── data/
│   │   ├── shipment_dataset.csv
│   │   └── generate_dataset.py
│   ├── frontend/
│   │   ├── index.html
│   │   ├── shipment.html
│   │   ├── monitor.html
│   │   ├── analytics.html
│   │   ├── incidents.html
│   │   ├── css/style.css
│   │   └── js/
│   │       ├── app.js          ← FIXED: /health check, window.COLDCHAIN_API_URL
│   │       └── theme.js
│   ├── requirements.txt        ← Updated: added gunicorn
│   └── test_predictions.py     ← FIXED: np.array → pd.DataFrame
├── .github/
│   └── workflows/
│       └── cicd.yml            ← NEW: 3-job CI/CD pipeline
├── k8s/
│   ├── deployment.yaml         ← NEW: 2 replicas, liveness/readiness probes
│   └── service.yaml            ← NEW: LoadBalancer service
├── terraform/
│   ├── main.tf                 ← NEW: RG + ACR + AKS + role assignment
│   └── terraform.tfvars.example
├── ansible/
│   └── playbook.yml            ← NEW: automated kubectl apply
├── Dockerfile                  ← NEW: Gunicorn production build
├── .gitignore
└── DEVOPS_GUIDE.md             ← This file
```
