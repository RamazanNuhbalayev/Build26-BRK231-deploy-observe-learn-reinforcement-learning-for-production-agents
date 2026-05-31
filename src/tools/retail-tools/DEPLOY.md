# Deploying Retail Tools (Azure Function App)

The retail tools are a FastAPI app deployed as an Azure Function App. They provide 6 HTTP endpoints that the agents call during conversations:

| Tool | Endpoint | Description |
|------|----------|-------------|
| `get_order_details` | `POST /tool/get_order_details` | Look up order info |
| `get_fulfillment_status` | `POST /tool/get_fulfillment_status` | Check shipping/delivery status |
| `check_resolution_policy` | `POST /tool/check_resolution_policy` | Check if item is returnable |
| `check_inventory` | `POST /tool/check_inventory` | Inventory lookup |
| `calculate_resolution` | `POST /tool/calculate_resolution` | Compute refund/exchange options |
| `submit_resolution` | `POST /tool/submit_resolution` | Execute the resolution |

## Prerequisites

- Azure CLI (`az`) installed and authenticated
- Azure Functions Core Tools v4 (`func`)

```bash
# Install Azure Functions Core Tools (if not present)
npm install -g azure-functions-core-tools@4

# Or on macOS:
brew tap azure/functions && brew install azure-functions-core-tools@4
```

## Option 1: Deploy via Azure CLI (Recommended)

### 1. Create the Function App (first time only)

```bash
# Variables — adjust as needed
RG="rg-omi-build26-azd-env"
LOCATION="northcentralus"
STORAGE_NAME="retailtoolsomkarm"    # must be globally unique, lowercase, no hyphens
APP_NAME="retail-tools-omkarm"       # your Function App name (becomes the URL)

# Create storage account (required by Azure Functions)
az storage account create \
  --name $STORAGE_NAME \
  --resource-group $RG \
  --location $LOCATION \
  --sku Standard_LRS

# Create the Function App (Python 3.12, Consumption plan)
az functionapp create \
  --name $APP_NAME \
  --resource-group $RG \
  --storage-account $STORAGE_NAME \
  --consumption-plan-location $LOCATION \
  --runtime python \
  --runtime-version 3.12 \
  --functions-version 4 \
  --os-type Linux
```

### 2. Configure startup command

```bash
az functionapp config set \
  --name $APP_NAME \
  --resource-group $RG \
  --startup-file "gunicorn function_app:fastapi_app --bind 0.0.0.0:8000 --worker-class uvicorn.workers.UvicornWorker"
```

### 3. Deploy the code

```bash
cd tools/retail-tools

# Deploy using Azure Functions Core Tools
func azure functionapp publish $APP_NAME --python
```

### 4. Verify

```bash
# Health check
curl https://$APP_NAME.azurewebsites.net/

# Expected: {"status":"ok","tools":["get_order_details","get_fulfillment_status",...],"today":"2026-07-15"}

# Test a tool
curl -X POST https://$APP_NAME.azurewebsites.net/tool/get_order_details \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"order_id": "ORD-001"}}'
```

## Option 2: Deploy via VS Code

1. Open `tools/retail-tools/` in VS Code
2. Install the **Azure Functions** extension
3. Click the Azure icon → Functions → Deploy to Function App
4. Select your subscription and choose "Create new Function App in Azure (Advanced)"
5. Settings:
   - Name: `retail-tools-omkarm`
   - Runtime: Python 3.12
   - Plan: Consumption
   - OS: Linux
   - Region: North Central US

## Option 3: Run Locally (for development)

```bash
cd tools/retail-tools
pip install -r requirements.txt

# Run with uvicorn directly
uvicorn function_app:fastapi_app --port 8000 --reload

# Or with gunicorn (production-like)
gunicorn function_app:fastapi_app --bind 0.0.0.0:8000 --worker-class uvicorn.workers.UvicornWorker
```

Then test at `http://localhost:8000/`.

## Updating the Agent TOOL_URL

After deploying, each agent's `main.py` uses the `TOOL_URL` environment variable (defaults to `https://retail-tools-omkarm.azurewebsites.net`).

If you deploy to a different app name, update:

```bash
# Option A: Set env var on the hosted agents
azd env set TOOL_URL "https://YOUR-APP-NAME.azurewebsites.net"
azd deploy

# Option B: Update the default in main.py
TOOL_URL = os.environ.get("TOOL_URL", "https://YOUR-APP-NAME.azurewebsites.net")
```

## Current Deployment

| Setting | Value |
|---------|-------|
| App Name | `retail-tools-omkarm` |
| URL | `https://retail-tools-omkarm.azurewebsites.net` |
| Demo Console | `https://retail-tools-omkarm.azurewebsites.net/demo` |
| Resource Group | `rg-omi-build26-azd-env` |
| Region | North Central US |
| Runtime | Python 3.12, Linux Consumption |
| Storage Account | `retailtoolsomkarm` |

## Demo Console

The function app includes an interactive demo page at `/demo`:

- **Database tab** — browse all customers, products, orders, and inventory
- **Tool Invoker tab** — call any of the 6 tools with a form UI and see live JSON responses

Access it at: `https://retail-tools-omkarm.azurewebsites.net/demo`

Or run locally: `http://localhost:8000/demo`

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Health check (returns tool list) |
| `GET /db` | Full in-memory database as JSON |
| `GET /demo` | Interactive demo console |
| `POST /tool/{name}` | Invoke a tool |

## Architecture

```
┌─────────────────┐         ┌──────────────────────────────┐
│  Hosted Agent   │  HTTP   │  Azure Function App          │
│  (AI Foundry)   │────────▶│  retail-tools-omkarm         │
│                 │         │  POST /tool/{tool_name}      │
└─────────────────┘         │  ┌──────────────────────┐    │
                            │  │  FastAPI + In-Memory  │    │
                            │  │  Database (mock)      │    │
                            │  └──────────────────────┘    │
                            └──────────────────────────────┘
```

The tools use an in-memory mock database (no external DB required). The data resets on each cold start.
