# Lead Qualification & Outreach Agent (LQOA)

A production-ready Python/Streamlit multi-agent pipeline that enriches, scores, classifies, and routes inbound leads — with mandatory human approval gates, role-based authentication, real-time monitoring, and comprehensive audit trails.

---

## Architecture

```mermaid
flowchart TD
    A[Inbound Lead] -->|REST API| B[FastAPI Backend]
    A -->|UI Form| C[Enhanced Streamlit UI]
    B -->|authenticate| D[Auth System]
    C -->|authenticate| D
    D -->|RBAC| E[Database Layer]
    B -->|store/retrieve| E
    C -->|store/retrieve| E
    B -->|validate & enqueue| F[Orchestrator]
    C -->|validate & enqueue| F
    F -->|sanitize free-text\ndetect injection| G[Enrichment Agent]
    G -->|cache results| H[Redis Cache]
    G -->|EnrichmentResult| I[Scoring Agent]
    I -->|rule-based score\nLLM for reason text only| J[Classification Agent]
    J -->|HOT / NURTURE / DISQUALIFY| K{Routing Agent}
    K -->|DISQUALIFY| L[archive_lead tool]
    K -->|NURTURE| M[sequence_enroll tool]
    K -->|HOT| N[Drafting Agent]
    N -->|DraftEmail\nLLM grounded in enrichment facts only| O[Pending Approval Queue]
    O -->|Enhanced UI| P{Human Gate}
    P -->|role-based permissions| D
    P -->|Approve / Approve-as-Edited| Q[register_approval\ncontent hash stored]
    Q --> R[email_send tool\nhash-verified]
    P -->|Reject| S[rejected queue]
    L --> T[(Audit System\nStructured Logging)]
    M --> T
    R --> T
    Q --> T
    T --> U[Real-time Monitoring]
    T --> V[Governance Dashboard]
    
    subgraph "Infrastructure"
        E[(PostgreSQL/SQLite)]
        H[(Redis Cache)]
        T[(Audit Logs)]
    end
```

### Enhanced Components

| Component | Module | Features |
|-----------|--------|----------|
| **Authentication** | `auth/` | JWT tokens, RBAC, session management |
| **REST API** | `api/main.py` | FastAPI endpoints, OpenAPI docs, CORS |
| **Database** | `database/` | SQLAlchemy models, repositories, migrations |
| **Caching** | `cache/` | Redis integration, performance optimization |
| **Monitoring** | `monitoring/` | Error handling, structured logging, alerts |
| **Enhanced UI** | `gate/enhanced_streamlit_app.py` | Real-time updates, role-based views |

### Pipeline Stages

| Stage | Module | LLM? | Notes |
|-------|--------|------|-------|
| Intake / sanitize | `orchestrator.py` | ✗ | Strips free-text of instruction power; detects injection |
| Enrich | `agents/enrichment.py` | ✗ | Firmographic lookup via mock dataset |
| Score | `agents/scoring.py` | Optional | Deterministic math; LLM only phrases the reason string |
| Classify | `agents/classification.py` | ✗ | Threshold comparison against `icp_config.json` |
| Route | `agents/routing.py` | ✗ | Dispatches to archive / sequence / drafting |
| Draft | `agents/drafting.py` | ✓ | Grounded strictly in enrichment facts |
| Human Gate | `gate/enhanced_streamlit_app.py` | ✗ | Edit + approve/reject; writes approval record |
| Send | `tools/email_send.py` | ✗ | Hard-verifies approval hash before sending |

---

## Non-negotiable constraints

1. **Only the post-approval path in `email_send()` may send** — no agent calls it directly.
2. **Lead-submitted free text is never treated as an instruction**, regardless of phrasing (injection detection + sanitization wrapper).
3. **Scoring is deterministic and identity-blind** — name, email local-part, and demographics are in `excluded_fields` and never touch the scoring feature vector.
4. **Every outbound action traces back to a specific approval record** in the governance log.
5. **LLM is used for two things only**: rationale phrasing (grounded in precomputed score) and email drafting (grounded strictly in enrichment facts).

---

## Fairness defence

`agents/scoring.py` derives its feature vector exclusively from:

- Company size (employee count)
- Industry
- Role / job function title
- Buying signals (firmographic signals)
- Email domain (business vs personal)

Fields in `icp_config.json → excluded_fields` — including `first_name`, `last_name`, `email_local_part`, `gender`, `age`, `nationality`, `ethnicity` — are never passed to the scoring function. `ScoreResult.excluded_fields_used` is always an empty list, asserted by `test_fairness.py`.

---

## Injection defence

`orchestrator.py` runs `detect_injection()` over all lead-submitted free text before the pipeline starts:

- Pattern matches cover `ignore previous instructions`, `mark me as HOT`, `bypass the gate`, `you are now a different AI`, etc.
- `injection_detected=True` is logged in the governance JSONL.
- The free text is wrapped in `[LEAD_DATA_START]…[LEAD_DATA_END]` before being placed in any LLM prompt context block.
- **Scoring always proceeds from real enrichment signals** regardless of what the free text says — injection cannot change the classification.

---

## Setup

```bash
# 1. Clone / enter the project
cd Lead_Qualification\&Outreach_Agent

# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize the database
python -c "from database.init_db import init_database; init_database()"

# 5. Configure environment variables in a .env file (copy the block below)
cp .env.example .env   # then fill in the values you need
```

### Environment variables

Create a `.env` file in the project root. Most variables are optional — the
pipeline runs with sensible defaults.

```dotenv
# ── Database Configuration ──────────────────────────────────────────────────
DATABASE_URL=sqlite:///./lqoa.db  # or postgresql://user:password@host:port/db
DB_ECHO=false                     # Set true for SQL query logging

# ── Authentication & Security ────────────────────────────────────────────────
JWT_SECRET_KEY=your-secret-key-here-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=720

# ── API Server Settings ─────────────────────────────────────────────────────
API_HOST=127.0.0.1
API_PORT=8000
DEBUG=true                        # Set false in production

# ── LLM (scoring rationale + email drafting) ─────────────────────────────────
# Without this the pipeline runs in deterministic-only mode.
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_TEMPERATURE=0.2

# ── Redis Cache (optional) ────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=                   # if required
REDIS_TTL=3600                   # cache expiration in seconds

# ── Firmographic enrichment ───────────────────────────────────────────────────
# Controls which provider is used for company data lookup.
# Accepted values: clearbit | pdl | mock  (default: mock)
ENRICHMENT_PROVIDER=clearbit

# Clearbit Company Enrichment API
# Sign up: https://dashboard.clearbit.com/
# Free tier: 50 lookups/month — sufficient for low-volume testing.
CLEARBIT_API_KEY=sk-...

# People Data Labs Company Enrichment API
# Sign up: https://www.peopledatalabs.com/
# Free tier: 100 credits/month.
PDL_API_KEY=...

# ── Logging & Monitoring ─────────────────────────────────────────────────────
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR
STRUCTURED_LOGGING=true
LOG_FILE_PATH=logs/
```

### Default User Accounts

The system creates default user accounts on first run:

| Username | Password | Role | Permissions |
|----------|----------|------|-------------|
| `admin` | `admin123` | Admin | Full system access, user management |
| `reviewer` | `review123` | Reviewer | Lead review, approval queue access |
| `viewer` | `view123` | Viewer | Read-only access to leads |

**⚠️ Change these passwords in production environments!**

#### Enrichment provider behaviour

| `ENRICHMENT_PROVIDER` | Resolution chain | Required keys |
|---|---|---|
| `clearbit` *(recommended)* | Clearbit → PDL → mock → not-found | `CLEARBIT_API_KEY` |
| `pdl` | PDL → mock → not-found | `PDL_API_KEY` |
| `mock` *(default)* | 6-company local dataset only | none |

- If a live provider is configured but the domain is not found, the chain
  continues to the next provider automatically.
- If a live provider returns a network or auth error it is skipped silently and
  the chain continues — the pipeline never hard-fails due to an enrichment outage.
- The `provider` field on `EnrichmentResult` records which source ultimately
  supplied the data and is written to the governance audit log.
- You can override `ENRICHMENT_PROVIDER` per-run without editing the config file:
  `ENRICHMENT_PROVIDER=pdl python -c "from orchestrator import run_pipeline; ..."`

---

## Running the Application

### Option 1: Enhanced UI with Authentication (Recommended)

```bash
# Terminal 1: Start the API server
python api/server.py

# Terminal 2: Start the enhanced Streamlit UI  
streamlit run gate/enhanced_streamlit_app.py
```

Open http://localhost:8501 and login with:
- **Admin**: `admin` / `admin123` 
- **Reviewer**: `reviewer` / `review123`

### Option 2: Basic UI (No Authentication)

```bash
streamlit run gate/streamlit_app.py
```

Open http://localhost:8501 in your browser (no login required).

### Available Interfaces

| Interface | URL | Features |
|-----------|-----|----------|
| **Enhanced UI** | http://localhost:8501 | Authentication, real-time updates, role-based access |
| **REST API** | http://localhost:8000/api/docs | OpenAPI documentation, programmatic access |
| **Basic UI** | http://localhost:8501 | Simple interface, no authentication |

### Enhanced UI Tabs

Role-based access to different features:

| Tab | Admin | Reviewer | Viewer | Description |
|-----|-------|----------|--------|-------------|
| 📥 New Lead | ✓ | ✓ | ✓ | Submit leads and run pipeline |
| 🔥 Approval Queue | ✓ | ✓ | ✗ | Review/approve HOT leads |
| 🌱 Nurture | ✓ | ✓ | ✓ | View sequence-enrolled leads |
| 🗂️ Disqualified | ✓ | ✓ | ✓ | View archived leads |
| 📊 Analytics | ✓ | ✗ | ✗ | Performance metrics and insights |
| 🔍 Governance | ✓ | ✓ | ✗ | Audit logs and compliance |
| ⚙️ Admin | ✓ | ✗ | ✗ | User management, system config |

---

## Testing & Quality Assurance

### Unit & Integration Tests

```bash
# Run all tests
python tests/run_all_tests.py

# Run specific test suites
pytest tests/test_api_integration.py -v
pytest tests/test_database_integration.py -v
pytest tests/test_pipeline_integration.py -v
pytest tests/test_performance.py -v

# Or run all at once via pytest
pytest tests/ -v
```

### Performance Testing

The performance test suite includes:
- Lead processing throughput benchmarks
- Database query performance tests
- API endpoint latency measurements
- Memory usage profiling

---

## Run the eval suite

```bash
# Run all 5 tests with summary table
python eval/run_all.py

# Or run individual files
pytest eval/test_hot_lead.py -v
pytest eval/test_disqualify.py -v
pytest eval/test_approval_gate.py -v
pytest eval/test_fairness.py -v
pytest eval/test_injection.py -v

# Or run all at once via pytest
pytest eval/ -v
```

All 5 test files must pass before the project is considered complete.

---

## File structure

```
.
├── agents/
│   ├── enrichment.py       # wraps enrichment_lookup tool
│   ├── scoring.py          # deterministic rule-based scoring
│   ├── classification.py   # threshold → HOT / NURTURE / DISQUALIFY
│   ├── routing.py          # dispatch to archive / sequence / drafting
│   └── drafting.py         # LLM email draft, grounded in enrichment facts
├── tools/
│   ├── enrichment_lookup.py  # mock firmographic dataset
│   ├── crm_write.py          # gated CRM write
│   ├── email_send.py         # hard-gated send (approval hash check)
│   ├── sequence_enroll.py    # nurture sequence enrollment
│   └── archive_lead.py       # disqualify archive
├── api/
│   ├── main.py             # FastAPI REST endpoints
│   └── server.py           # API server startup script
├── auth/
│   ├── security.py         # JWT authentication & password hashing
│   ├── session.py          # Streamlit session management
│   └── dependencies.py     # FastAPI auth dependencies
├── database/
│   ├── models.py           # SQLAlchemy models (User, Lead, Approval, etc.)
│   ├── repositories.py     # Data access layer
│   ├── connection.py       # Database connection & session management
│   ├── init_db.py          # Database initialization
│   └── migrations/         # Alembic database migrations
├── cache/
│   └── redis_manager.py    # Redis caching for performance
├── monitoring/
│   └── error_handler.py    # Error handling & structured logging
├── app_logging/
│   └── structured_logger.py # Advanced logging system
├── governance/
│   └── logger.py           # append-only JSONL + query helpers
├── gate/
│   ├── enhanced_streamlit_app.py  # Enhanced UI with auth & real-time
│   ├── streamlit_app.py           # Basic UI (legacy)
│   ├── ui_components.py           # Reusable UI components
│   └── admin_components.py        # Admin-only UI components
├── config/
│   ├── icp_config.json     # ICP weights, thresholds, excluded_fields
│   └── settings.py         # Pydantic settings management
├── deployment/
│   ├── k8s-manifests.yaml  # Kubernetes deployment
│   └── nginx.conf          # Reverse proxy configuration
├── tests/
│   ├── test_api_integration.py
│   ├── test_database_integration.py
│   ├── test_pipeline_integration.py
│   ├── test_performance.py
│   └── run_all_tests.py
├── eval/
│   ├── test_hot_lead.py
│   ├── test_disqualify.py
│   ├── test_approval_gate.py
│   ├── test_fairness.py
│   ├── test_injection.py
│   └── run_all.py
├── logs/                   # auto-created; append-only audit.jsonl
├── orchestrator.py         # pipeline state machine + LeadState dataclass
├── llm_client.py           # single llm_call() wrapper (OpenAI / offline fallback)
├── requirements.txt
├── docker-compose.yml      # Local development with Docker
├── docker-compose.prod.yml # Production Docker setup
├── Dockerfile              # Container definition
├── deploy.sh               # Automated deployment script
└── .env.example            # Environment configuration template
```

**Deploy to Render**

- Create a new **Web Service (Python)** on Render and point it at your repository and `main` branch.
- Use these values for the Render form fields:
  - Root directory: `.`
  - Build command: `pip install -r requirements.txt`
  - Start command: `streamlit run gate/enhanced_streamlit_app.py --server.port $PORT --server.address 0.0.0.0`
  - Health check path: `/`

- Required environment variables (set in Render dashboard, do NOT commit them):
  - `JWT_SECRET_KEY` — JWT signing key (required for authentication)
  - `DATABASE_URL` — PostgreSQL connection string (Render provides this)
  - `OPENAI_API_KEY` — OpenAI API key for drafting/rationale (optional: leave empty for offline mode)
  - `CLEARBIT_API_KEY` — optional, if using `ENRICHMENT_PROVIDER=clearbit`
  - `PDL_API_KEY` — optional, if using `ENRICHMENT_PROVIDER=pdl`

- I included a `render.yaml` at the repo root for a managed Python web service and a `.env.example` you can copy locally.

**Docker Deployment**

For containerized deployment:

```bash
# Development
docker-compose up

# Production
docker-compose -f docker-compose.prod.yml up -d
```

**Kubernetes Deployment**

```bash
kubectl apply -f deployment/k8s-manifests.yaml
```

Local test command:
```
streamlit run gate/enhanced_streamlit_app.py --server.port 8501
```

