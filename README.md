# Referral Router MVP

Automate the hand-off of referral documents (PDF or HL7 v2) between siloed healthcare systems by converting them into validated FHIR ServiceRequest resources and posting them to a FHIR store.

## Quick Start

```bash
# 1. Clone repo
git clone <your-repo-url>
cd referral-router

# 2. Install dev deps
pipx install poetry
poetry install --with dev
poetry env use python3.11

# 3. Start stack
docker-compose up -d

# 4. Load Synthea patients (once)
./scripts/load_synthea.sh 100

# 5. Process a referral
python router.py data/sample_referral.pdf
```

## Architecture

```
PDF/HL7
   │
   ▼                                 ┌──────────────┐
[PDF Extract] ──▶  Draft JSON  ──▶  │ Generator    │
   │                                   └──────────────┘
   │                                        │
   ▼                                 ┌──────────────┐
[empi_mock] (optional)──────────────▶│ Validator    │─┐
                                     └──────────────┘ │
                                                     │fail
                                                     ▼
                                           ┌──────────────┐
                                           │ Fixer (LLM)  │───loop max 3
                                           └──────────────┘
                                                     │pass
                                                     ▼
                                     ┌──────────────┐
                                     │ Poster       │─▶ local FHIR
                                     └──────────────┘
```

## Components

- **LLM (GPT-4o)** – handles generation & fixing
- **Agent Runtime (LangGraph)** – stateful graph with five nodes
- **Tool Registry (YAML)** – declares callable systems
- **PDF Extract Service** – FastAPI wrapper around pdfplumber + LlamaParse
- **HAPI-FHIR Server** – local container, canonical endpoint
- **SQLite Audit DB** – stores every request/response pair
- **CLI Entrypoint** – `python router.py referral.pdf`

## Development

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Poetry (for dependency management)

### Environment Setup

1. Copy `.env.example` to `.env` and add your OpenAI API key:
```bash
cp .env.example .env
# Edit .env and add OPENAI_API_KEY=your_key_here
```

2. Install dependencies:
```bash
poetry install --with dev
```

3. Start services:
```bash
docker-compose up -d
```

### Testing

```bash
# Run unit tests
poetry run pytest

# Run end-to-end tests
poetry run pytest tests/e2e/

# Run linting
poetry run flake8
poetry run black --check .
```

## Project Structure

```
referral-router/
├── agent_app/           # LangGraph agent application
├── pdf_service/         # FastAPI PDF extraction service
├── scripts/             # Utility scripts (Synthea loader)
├── data/                # Sample data and audit logs
├── tests/               # Test suite
├── docker-compose.yml   # Service orchestration
├── pyproject.toml       # Python dependencies
├── tools.yml           # Tool registry
└── router.py           # CLI entrypoint
```

## API Endpoints

- **HAPI FHIR**: http://localhost:8080/fhir
- **PDF Service**: http://localhost:7000/extract
- **EMPI Mock**: http://localhost:7001/patient

## License

MIT 