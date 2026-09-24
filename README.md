# JourneyGo Self-Hosted AI Recommendation Backend

A lightweight, production-ready **FastAPI** backend that exposes a REST API powered by a local, open-source LLM running via **Ollama**.

It serves as the AI intent parsing and truthful explanation layer for the **JourneyGo** iOS application.

---

## Architecture

```text
┌─────────────────────────────────┐
│     JourneyGo iOS Application   │
└────────────────┬────────────────┘
                 │
                 │ HTTPS / HTTP POST /v1/intent
                 ▼
┌─────────────────────────────────┐
│     FastAPI Backend Server      │
│  (Port 8000, Request Validation)│
└────────────────┬────────────────┘
                 │
                 │ format="json", temp=0.1
                 ▼
┌─────────────────────────────────┐
│         Ollama Server           │
│     (http://localhost:11434)    │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│   Local Open-Source LLM         │
│  (e.g. Llama 3.2:3b / Phi-3)    │
└─────────────────────────────────┘
```

* **No Hardcoded Keys**: The iOS app requires no third-party API keys or AI accounts.
* **Truthful Rationale**: The LLM is strictly used for intent extraction and contextual explanations using ONLY real place metadata retrieved from Geoapify. It never invents places or attributes.
* **Resilient**: If Ollama is offline or warming up, the backend gracefully falls back to deterministic rule extraction without breaking the iOS client.

---

## Quickstart Setup Guide (macOS)

### 1. Install Ollama

If you don't already have Ollama installed, install it via Homebrew or from the official site:

```bash
# Via Homebrew
brew install ollama

# Or download directly from:
# https://ollama.com/download/mac
```

### 2. Download the Recommended Model

We recommend `llama3.2:3b` or `qwen2.5:3b` for fast, low-memory inference on Apple Silicon Macs:

```bash
# Pull the lightweight, high-accuracy instruction model
ollama pull llama3.2:3b

# Alternatives:
# ollama pull qwen2.5:3b
# ollama pull phi3:mini
```

### 3. Start the Ollama Service

Make sure the Ollama daemon is running in the background:

```bash
ollama serve
```

Verify it's reachable:
```bash
curl http://localhost:11434/api/tags
```

---

### 4. Set Up the Python Environment & Dependencies

From the `backend/` directory:

```bash
cd backend

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

---

### 5. Start the FastAPI Backend Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server is now live at:
* API Base: `http://localhost:8000`
* Interactive OpenAPI Docs: `http://localhost:8000/docs`
* Health Check: `http://localhost:8000/v1/health`

---

## 6. Configure JourneyGo iOS App

### When Running in the iOS Simulator:
* The iOS Simulator shares the Mac's localhost network.
* `AIConfiguration.baseURL` automatically resolves to `http://127.0.0.1:8000`. No extra setup required!

### When Running on a Physical iPhone:
1. Find your Mac's local IP address:
   ```bash
   ipconfig getifaddr en0
   # Example: 192.168.1.15
   ```
2. In `JourneyGo/AI/AIConfiguration.swift`, set:
   ```swift
   static var customHost = "http://192.168.1.15:8000"
   ```
3. Ensure your Mac and iPhone are connected to the same Wi-Fi network.

---

## 7. Testing the System End-to-End

### Test via cURL:

#### Intent Parsing (`POST /v1/intent`):
```bash
curl -X POST http://localhost:8000/v1/intent \
  -H "Content-Type: application/json" \
  -d '{"text": "I had a stressful day. I want somewhere quiet where I can have coffee and relax."}'
```

**Expected JSON Response:**
```json
{
  "mood": "tired",
  "interests": ["coffee"],
  "activity": "relax",
  "budget": null,
  "max_distance_km": 5.0,
  "social_preference": "alone"
}
```

#### Truthful Place Explanation (`POST /v1/explain`):
```bash
curl -X POST http://localhost:8000/v1/explain \
  -H "Content-Type: application/json" \
  -d '{
    "intent": {
      "mood": "tired",
      "interests": ["coffee"],
      "activity": "relax"
    },
    "places": [
      {
        "place_id": "cafe-101",
        "name": "Artisan Tea & Coffee Lounge",
        "distance_km": 1.2,
        "category": "catering.cafe",
        "opening_status": "open",
        "rating": 4.8,
        "budget": "₹150 / person"
      }
    ]
  }'
```

---

## Production Security & Best Practices

1. **Keep Ollama Internal**: Never bind `11434` directly to a public interface.
2. **Reverse Proxy (Nginx / Caddy)**: Put FastAPI behind Nginx with SSL/TLS (`https://ai.yourdomain.com`).
3. **API Key Authentication**: Set `API_KEY=your_secret_token` in `.env` to enforce `X-API-Key` headers on all endpoints.
4. **Rate Limiting**: Enforced via standard reverse proxy rate limiters (e.g. `limit_req_zone` in Nginx).
