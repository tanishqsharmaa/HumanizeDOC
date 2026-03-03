# HumanizeDOC

## What it does

HumanizeDOC accepts an AI-written `.docx` file from a student, runs it through a multi-stage rewriting pipeline powered by Groq's LLaMA 3.1 70B model (with Google Gemini 1.5 Flash as fallback), and returns the same document fully rewritten to pass Turnitin's AI-detection system — with all original formatting, headings, tables, and references completely preserved.

---

## Architecture Overview

```
                          ┌─────────────────────────────────────┐
                          │         Azure Static Web Apps        │
                          │         (Next.js 14 frontend)        │
                          └──────────────────┬──────────────────┘
                                             │ HTTPS
                          ┌──────────────────▼──────────────────┐
                          │         Azure Container Apps         │
                          │         (FastAPI backend)            │
                          │                                      │
                          │  ┌──────────────────────────────┐   │
                          │  │       Processing Pipeline     │   │
                          │  │  Parse → Classify → Chunk →  │   │
                          │  │  Humanize → Reconstruct       │   │
                          │  └──────────────────────────────┘   │
                          └────────────┬─────────────┬──────────┘
                                       │             │
               ┌───────────────────────┘             └──────────────────────┐
               │                                                             │
  ┌────────────▼────────────┐                              ┌────────────────▼──────────────┐
  │   Azure Blob Storage     │                              │  Groq API (LLaMA 3.1 70B)     │
  │   (uploads container,    │                              │  ── OR ──                     │
  │    SAS URLs expire 60m,  │                              │  Google Gemini 1.5 Flash API   │
  │    blobs deleted 1 day)  │                              │                               │
  └─────────────────────────┘                              └───────────────────────────────┘
```

---

## Prerequisites

- **Azure account** with an active subscription ([free tier available](https://azure.microsoft.com/free))
- **Azure CLI** installed and authenticated (`az login`) — [install guide](https://learn.microsoft.com/cli/azure/install-azure-cli)
- **Node.js 18+** — [nodejs.org](https://nodejs.org)
- **Python 3.11+** — [python.org](https://python.org)
- **Docker Desktop** — [docker.com](https://www.docker.com/products/docker-desktop)
- **Groq API key** (free) — sign up at [console.groq.com](https://console.groq.com)
- **Google AI Studio API key** (free) — get one at [aistudio.google.com](https://aistudio.google.com)

---

## Local Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/tanishqsharmaa/HumanizeDOC.git
cd HumanizeDOC
```

### 2. Backend setup

```bash
cd humanizedoc/backend
python -m venv venv

# Activate (macOS / Linux)
source venv/bin/activate

# Activate (Windows)
# venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Open .env and fill in all required values (see Environment Variables Reference below)

uvicorn main:app --reload --port 8000
```

The backend API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

### 3. Frontend setup

```bash
cd humanizedoc/frontend
npm install

# Create local environment file
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

npm run dev
```

### 4. Access the application

Open your browser at `http://localhost:3000`.

---

## Azure Deployment

Follow these steps in order. All commands assume you are in the repository root.

### Step 1 — Create a resource group

```bash
az group create --name humanizedoc-rg --location eastus
```

### Step 2 — Deploy Blob Storage

```bash
az deployment group create \
  --resource-group humanizedoc-rg \
  --template-file humanizedoc/infra/storage.bicep \
  --parameters storageAccountName=<unique-storage-name>
```

Retrieve the storage connection string and save it for later:

```bash
az storage account show-connection-string \
  --name <unique-storage-name> \
  --resource-group humanizedoc-rg \
  --query connectionString -o tsv
```

### Step 3 — Create Azure Container Registry

```bash
az acr create \
  --name humanizedocregistry \
  --resource-group humanizedoc-rg \
  --sku Basic \
  --admin-enabled true
```

### Step 4 — Build and push the Docker image

```bash
az acr build \
  --registry humanizedocregistry \
  --image humanizedoc-backend:latest \
  ./humanizedoc/backend
```

### Step 5 — Deploy the Container App

```bash
az deployment group create \
  --resource-group humanizedoc-rg \
  --template-file humanizedoc/infra/container-app.bicep \
  --parameters \
    containerAppName=humanizedoc-api \
    containerImage=humanizedocregistry.azurecr.io/humanizedoc-backend:latest \
    groqApiKey="<YOUR_GROQ_API_KEY>" \
    geminiApiKey="<YOUR_GEMINI_API_KEY>" \
    azureStorageConnectionString="<YOUR_STORAGE_CONNECTION_STRING>" \
    blobContainerName=humanizedoc-uploads
```

Note the `containerAppUrl` output value — you will need it in the next step.

### Step 6 — Deploy the Static Web App

```bash
az deployment group create \
  --resource-group humanizedoc-rg \
  --template-file humanizedoc/infra/static-web-app.bicep \
  --parameters \
    appName=humanizedoc-frontend \
    location=eastus2 \
    backendApiUrl="https://<container-app-fqdn>"
```

> **Note:** Azure Static Web Apps are only available in certain regions. Use `eastus2`, `westus2`, `centralus`, `eastasia`, or `westeurope`.

### Step 7 — Set GitHub secrets for CI/CD

In your GitHub repository go to **Settings → Secrets and variables → Actions** and add:

| Secret name | Description |
|---|---|
| `ACR_NAME` | ACR name without `.azurecr.io` (e.g. `humanizedocregistry`) |
| `AZURE_CLIENT_ID` | Service principal client ID |
| `AZURE_CLIENT_SECRET` | Service principal client secret |
| `AZURE_TENANT_ID` | Azure Active Directory tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `AZURE_RESOURCE_GROUP` | Resource group name (e.g. `humanizedoc-rg`) |
| `CONTAINER_APP_NAME` | Container App name (e.g. `humanizedoc-api`) |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | Deployment token from the Static Web App resource |

To create a service principal with the required permissions:

```bash
az ad sp create-for-rbac \
  --name humanizedoc-deploy \
  --role contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/humanizedoc-rg \
  --sdk-auth
```

The Static Web App deployment token can be found in the Azure portal under your Static Web App resource → **Overview → Manage deployment token**.

---

## Environment Variables Reference

| Variable | Required | Description | Example |
|---|---|---|---|
| `GROQ_API_KEY` | ✅ Yes | Groq API key for LLaMA 3.1 70B | `gsk_abc123...` |
| `GEMINI_API_KEY` | ✅ Yes | Google Gemini 1.5 Flash API key | `AIza...` |
| `HUMANIZER_BACKEND` | No | LLM provider to use (`groq` or `gemini`) | `groq` |
| `AZURE_STORAGE_CONNECTION_STRING` | ✅ Yes | Full Azure Blob Storage connection string | `DefaultEndpointsProtocol=https;...` |
| `AZURE_BLOB_CONTAINER_NAME` | No | Blob container for uploads | `humanizedoc-uploads` |
| `MAX_FILE_SIZE_MB` | No | Maximum upload size in megabytes | `15` |
| `MAX_WORDS_PER_REQUEST` | No | Maximum document length in words | `12000` |
| `CHUNK_SIZE_WORDS` | No | Target words per LLM chunk | `500` |
| `FILE_EXPIRY_MINUTES` | No | SAS URL validity window in minutes | `60` |
| `RATE_LIMIT_PER_IP_PER_DAY` | No | Max uploads per IP address per 24 h | `5` |

---

## Testing

```bash
cd humanizedoc/backend
source venv/bin/activate
pytest tests/ -v
```

| Test file | What it covers |
|---|---|
| `tests/test_parser.py` | DOCX paragraph extraction, metadata preservation, word counting |
| `tests/test_classifier.py` | Block classification (HUMANIZE vs PRESERVE) for headings, references, tables, etc. |
| `tests/test_chunker.py` | Chunk boundary logic — paragraphs never split mid-boundary, chunk sizes within target range |
| `tests/test_reconstructor.py` | DOCX reconstruction with humanized text while preserving original formatting |

---

## Cost Estimate

All costs based on low-traffic usage (≤ 100 documents/day). Groq and Gemini APIs are free tier for development usage.

| Azure Service | SKU | Estimated monthly cost |
|---|---|---|
| Container Apps | Consumption (scale to zero) | ~$0–$5 |
| Static Web Apps | Free | $0 |
| Blob Storage | Standard LRS, < 1 GB | ~$0.02 |
| Container Registry | Basic | ~$5 |
| **Total** | | **~$5–$10/month** |

> Costs scale with usage. The Container App scales to zero replicas when idle, so you only pay for active request processing time.

---

## Project Structure

```
HumanizeDOC/
├── .github/
│   └── workflows/
│       └── deploy.yml          # CI/CD: build → push → deploy on push to main
└── humanizedoc/
    ├── backend/
    │   ├── Dockerfile           # Production container image (non-root, health check)
    │   ├── main.py              # FastAPI app: upload, status, download, health routes
    │   ├── config.py            # Pydantic settings — all env vars validated at startup
    │   ├── models.py            # Pydantic data models (Job, JobStatus, responses)
    │   ├── requirements.txt     # Pinned Python dependencies
    │   ├── .env.example         # Template for local environment variables
    │   ├── backends/
    │   │   ├── base.py          # Abstract LLM backend interface
    │   │   ├── groq_backend.py  # Groq LLaMA 3.1 70B implementation
    │   │   └── gemini_backend.py# Google Gemini 1.5 Flash implementation
    │   ├── pipeline/
    │   │   ├── parser.py        # DOCX → list of Block objects with formatting metadata
    │   │   ├── classifier.py    # Labels each block HUMANIZE or PRESERVE
    │   │   ├── chunker.py       # Groups HUMANIZE blocks into 400–600 word chunks
    │   │   ├── humanizer.py     # Sends chunks to LLM, validates ±15% word count
    │   │   └── reconstructor.py # Rebuilds DOCX with humanized text + original formatting
    │   ├── storage/
    │   │   └── azure_blob.py    # Azure Blob Storage: upload, download, SAS URL generation
    │   └── tests/
    │       ├── test_parser.py
    │       ├── test_classifier.py
    │       ├── test_chunker.py
    │       └── test_reconstructor.py
    ├── frontend/
    │   ├── app/
    │   │   ├── page.tsx                     # Landing page with file upload UI
    │   │   ├── processing/[jobId]/page.tsx  # Live progress tracker
    │   │   └── download/[jobId]/page.tsx    # Download card with stats
    │   ├── components/
    │   │   ├── DropZone.tsx                 # Drag-and-drop .docx upload component
    │   │   ├── ProgressTracker.tsx          # Polling progress bar component
    │   │   └── DownloadCard.tsx             # Download button + word count stats
    │   └── package.json
    └── infra/
        ├── container-app.bicep  # Azure Container Apps: scale rules, env vars, ingress
        ├── static-web-app.bicep # Azure Static Web Apps: Next.js hosting, API URL setting
        └── storage.bicep        # Azure Blob Storage: account, container, lifecycle policy
```

---

## Known Limitations (MVP)

- **English language documents only** — the humanization prompt is tuned for English academic writing.
- **Maximum 12,000 words per document** — larger documents must be split manually.
- **No user accounts or document history** — jobs are stored in memory and lost on restart.
- **Rate limited to 5 documents per IP per day** — enforced in-memory (resets on restart).
- **PDF input not supported** — `.docx` format only; PDF support is planned for v2.
