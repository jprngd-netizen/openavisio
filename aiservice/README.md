# OpenAvisio AI Service

Python FastAPI microservice for medical document extraction. Supports Ollama (local), vLLM (high-throughput), and Mistral (cloud) backends.

> **Part of this fork.** This service is one component of the OpenAvisio Brazilian clinical fork — a self-hosted record built on top of an AGPL-3.0 open-source upstream (see the root [`README.md`](../README.md) and ADR 032). It is not a standalone project: it talks to the backend over the endpoints listed below. Operational context, profiles, and deployment live in the repository docs.

> **Configuration:** see [ADR 005 — AI model configuration](../docs/adr/005-ai-model-configuration.md) for profiles and backend selection, and the root [`README.md`](../README.md) (Deploy → IA local) for how the service is wired into a deployment.

## How It Works

1. Receives uploaded document (PDF or image) via `/extract`
2. PDFs: extracts text with pypdfium2. If text is substantial → text model. If scanned → vision model on page images.
3. Images: sends directly to vision model.
4. Returns structured JSON summary (diagnoses, medications, observations, etc.)

## Determinism

All chat/inference calls run with **`temperature=0`** (greedy decoding), set centrally in `backend.py` for every backend. Without it, Ollama samples at its 0.8 default and vLLM/Mistral at 1.0 — uploading the same document then yields different extraction results on every run, which makes the pipeline untrustworthy and undebuggable. Do not add sampling parameters per call site; if a use case ever genuinely needs creative sampling, make it an explicit, documented exception. Note: `temperature=0` is not bit-perfect determinism (GPU kernels, vLLM batching), but same-input runs are practically stable.

## Hardware Requirements

- **Minimum:** NVIDIA GPU with 8 GB VRAM (e.g., RTX 3060)
- **Recommended:** NVIDIA RTX 3090 / RTX 4090 (24 GB VRAM)
- CPU-only works for testing but is very slow

## Model Options

| Model | VRAM | Type | Use Case |
|-------|------|------|----------|
| `alibayram/medgemma:27b` | ~17 GB | Text | **Default** — medical extraction & chat (24GB+) |
| `alibayram/medgemma:4b` | ~3 GB | Vision | Medical multimodal (8-16GB GPUs) |
| `glm-ocr` | ~2 GB | Vision | **Default** — #1 OmniDocBench OCR, German + handwriting, fits beside the extraction model |
| `qwen3.5:9b` | ~7 GB | Vision | General multimodal alternative (supersedes qwen3-vl; qwen3.6 exists but starts at 27b) |
| `qwen3:14b` | ~9 GB | Text | **Default** — classification |
| `nomic-embed-text` | ~0.3 GB | Embedding | **Required** for RAG chat pipeline |

See [`docs/research-gpu-upgrade.md`](../docs/research-gpu-upgrade.md) and [`docs/research-extraction-model.md`](../docs/research-extraction-model.md) for GPU hardware profiles and per-tier model choices.

## Setup

### 1. Install Ollama

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Or via Docker (handled by Aspire AppHost)
docker run -d --gpus all -v ollama:/root/.ollama -p 11434:11434 ollama/ollama
```

### 2. Pull models

```bash
ollama pull alibayram/medgemma:27b
ollama pull glm-ocr
ollama pull qwen3:14b
ollama pull nomic-embed-text
```

### 3. Run locally (without Aspire)

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SERVICES__OLLAMA__HTTP__0` | Ollama URL (Aspire convention) | — |
| `OLLAMA_URL` | Ollama URL(s), comma-separated for round-robin | `http://localhost:11434` |
| `OLLAMA_MODEL` | Default model for extraction | `alibayram/medgemma:27b` |
| `OLLAMA_<STAGE>_MODEL` | Per-stage model (`EXTRACT`/`CLASSIFY`/`CHAT`/`VISION`) | — |
| `OLLAMA_<STAGE>_NUM_CTX` | Per-stage Ollama context window (tokens). The aiservice sets a per-stage default (extract 32768, chat 16384, vision/classify 8192) because Ollama's own default is 4096 and truncates multi-page documents — and neither a server-wide `OLLAMA_CONTEXT_LENGTH` nor an OpenWebUI per-model setting reaches these API calls. Override up (longer docs) or down (save VRAM) per stage. Bigger = more KV-cache VRAM | *(stage default above)* |
| `AI_BACKEND` | Backend: `ollama`, `vllm`, or `mistral` | `ollama` |
| `AI_PROFILE` | Profile for model defaults: `homelab`, `team`, `org`, `cloud` | *(none)* |
| `MISTRAL_API_KEY` | Mistral API key (when `AI_BACKEND=mistral`) | — |
| `AI_ALLOW_CLOUD_EGRESS` | Required opt-in for cloud backends. `AI_BACKEND=mistral` refuses to start unless this is `true`, because it egresses all patient data (OCR text, extracted entities, RAG context) to the Mistral cloud — data-protection implications (under Brazilian law, LGPD/ANPD; also GDPR if you serve EU patients); ensure a data-processing agreement and patient consent. Prefer `ollama`/`vllm` to keep data on-premise | `false` |

## API Endpoints

- `GET /health` — health check
- `POST /extract` — upload file, get structured extraction
- `POST /ocr` — Tesseract/OCRmyPDF text extraction
- `POST /ocr/vision` — vision model OCR fallback
- `POST /classify` — document classification
- `POST /extract-entities` — entity extraction from text
- `POST /embed` — generate embeddings
- `POST /chat` — RAG chat
- `POST /chat/stream` — RAG chat with SSE streaming
- `GET /models` — list available models
- `GET /backend` — backend info
- `GET /connection/test` — test connectivity
