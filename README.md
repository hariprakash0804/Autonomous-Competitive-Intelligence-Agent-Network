# Autonomous Competitive Intelligence Agent Network

An autonomous, multi-agent full-stack platform for competitive intelligence gathering, web scraping, VADER sentiment & topic analysis, pricing diff extraction, FAISS vector RAG, LangGraph agent workflow orchestration, FastMCP tool server integration, and automated multi-channel report delivery (Slack & Email).

---

## 🏛️ System Architecture

```text
+-----------------------------------------------------------------------------------+
|                                  USER INTERFACE                                   |
|             React 19 + Vite + Tailwind CSS + Recharts + Lucide Dashboard          |
+----------------------------------------+------------------------------------------+
                                         | REST API (JWT Auth) / Chat / Reports
                                         v
+-----------------------------------------------------------------------------------+
|                              FASTAPI BACKEND SERVICE                              |
|                                                                                   |
|  +---------------------+   +---------------------+   +--------------------------+ |
|  | Playwright Scraper  |   | Diff Pricing Engine |   | VADER Sentiment Analyzer | |
|  | Dynamic / JS Shell  |   | Regex + Currency    |   | NLTK + Topic Extraction  | |
|  +----------+----------+   +----------+----------+   +------------+-------------+ |
|             |                         |                           |               |
|             +-------------------------+---------------------------+               |
|                                       v                                           |
|                   +---------------------------------------+                       |
|                   |  4-Node LangGraph Agent Pipeline      |                       |
|                   |                                       |                       |
|                   | Researcher -> [Reflection Loop]       |                       |
|                   | Change-Detector -> Sentiment-Analyst  |                       |
|                   | -> Report-Writer (OpenRouter LLM)     |                       |
|                   +-------------------+-------------------+                       |
|                                       |                                           |
|  +------------------------------------+----------------------------------------+  |
|  | FastMCP Protocol Server (mcp_server.py)                                     |  |
|  | Tools: scrape | diff_pricing_tool | sentiment_score_tool                    |  |
|  +-----------------------------------------------------------------------------+  |
+---------------------------------------|-------------------------------------------+
                                        |
      +---------------------------------+---------------------------------+
      |                                 |                                 |
      v                                 v                                 v
+-----------+                   +---------------+                 +---------------+
| PostgreSQL|                   |  FAISS Index  |                 | Standalone    |
|  Database |                   | Vector Store  |                 | HTML / PDF &  |
| (Alembic) |                   | (Auto-Rehydrate)|               | Slack / Email |
+-----------+                   +---------------+                 +---------------+
```

---

## 🔑 Key Features

- 🤖 **Autonomous LangGraph Agent Pipeline**: 4-node sequential multi-agent network (`Researcher` with reflection loop for missing content, `Change-Detector` for pricing diffs, `Sentiment-Analyst` for NLP & VADER sentiment, `Report-Writer` for OpenRouter LLM report synthesis).
- 🔌 **FastMCP Tool Server (`mcp_server.py`)**: Model Context Protocol (MCP) server providing standard stdio tool bindings (`scrape`, `diff_pricing_tool`, `sentiment_score_tool`) for external AI agents and orchestration.
- 💬 **RAG AI Chat Assistant**: Interactive context-bounded chat endpoint (`/chat/`) leveraging FAISS vector search, chat history memory, image attachments, and document/PDF text analysis.
- 📊 **FAISS Vector Store with Startup Auto-Rehydration**: Vector database holding section-aware document chunks. Automatically rehydrates index from PostgreSQL snapshots upon startup. Public monitoring endpoint at `/faiss-status`.
- 🔍 **Resilient Web Scraping & Pricing Diff Engine**: Playwright browser integration handling JavaScript-heavy competitor sites, fallback HTTP fetching, currency symbol preservation, and tier extraction.
- 📈 **Modern Analytics Dashboard**: Dark-themed React 19 dashboard featuring Recharts price history timelines, sentiment score radar/bar charts, multi-competitor comparative matrix, real-time agent run status modal, and report center.
- 📑 **Multi-Channel Report Delivery**: Standalone rendered HTML reports, PDF downloads, automated Slack Webhook integration, and SMTP Email delivery.
- 🛡️ **LangSmith Telemetry & Tracing**: Native LangSmith integration for monitoring agent execution traces and latency with automatic tracer flushing.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy ORM, Alembic, LangGraph, Playwright, NLTK VADER, FAISS Vector Store, FastMCP.
- **LLM Orchestration**: OpenRouter API (`google/gemma-4-31b-it:free`, `nvidia/nemotron-3-nano-30b-a3b:free`) with proactive 3-second rate-limit guard and automatic 429/404 model fallback handling.
- **Frontend**: React 19, Vite, Tailwind CSS, Recharts, Lucide React, Axios, React Router.
- **Database**: PostgreSQL with SQLAlchemy ORM and Alembic migrations.
- **Vector Store**: Local FAISS index file store (`faiss_index.bin`) with PostgreSQL metadata sync.
- **Telemetry**: LangSmith tracing (`LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_ENDPOINT`).
- **Automation & Delivery**: n8n weekly cron workflow (`n8n_workflow.json`), Slack Webhooks, SMTP Email.
- **Containerization**: Docker Compose (`docker-compose.yml`) with persistent volumes for database (`pgdata`), FAISS store (`faissdata`), and static reports (`reportsdata`).

---

## 🌐 API Endpoints Overview

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/auth/register` | `POST` | Register a new user account |
| `/auth/login` | `POST` | Authenticate user & receive JWT bearer token |
| `/auth/me` | `GET` | Retrieve current authenticated user profile |
| `/competitors/` | `GET` / `POST` | List or create tracked competitors |
| `/competitors/{id}` | `GET` / `PUT` / `DELETE` | Retrieve, update, or delete competitor |
| `/snapshots/` | `GET` | Retrieve scraped website snapshots |
| `/snapshots/scrape/{id}` | `POST` | Manually trigger scraper for a competitor |
| `/pipeline/run/{id}` | `POST` | Trigger 4-node LangGraph pipeline run |
| `/pipeline/runs` | `GET` | List history of agent execution runs |
| `/reports/` | `GET` | List generated intelligence reports |
| `/reports/{id}` | `GET` | Fetch specific report details |
| `/reports/deliver-slack/{id}` | `POST` | Dispatch report summary to Slack Webhook |
| `/reports/send-email/{id}` | `POST` | Send report via SMTP Email |
| `/chat/` | `POST` | Perform RAG vector search & AI chat query |
| `/health` | `GET` | Backend health check |
| `/faiss-status` | `GET` | Live vector store indexing status |

---

## 🚀 Quickstart & Local Setup

### 1. Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL database instance

### 2. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create & activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
# source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Download NLTK VADER lexicon
python -c "import nltk; nltk.download('vader_lexicon')"

# Install Playwright Chromium browser binary
playwright install chromium

# Create environment file (.env)
cp .env.example .env
# Edit .env to set your DATABASE_URL, OPENROUTER_API_KEY, JWT_SECRET, etc.

# Run database migrations & seed initial data
alembic upgrade head
python scripts/seed_data.py

# Start FastAPI development server
uvicorn app.main:app --reload --port 8000
```

### 3. FastMCP Tool Server (Optional)
To expose the backend tools via Model Context Protocol (MCP) stdio transport:
```bash
python -m app.mcp_server
```

### 4. Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install node dependencies
npm install

# Start Vite development server
npm run dev
```

Open `http://localhost:5173` in your browser. Default login: `user@example.com` / `password123`.

---

## 📦 Docker Compose Deployment

Deploy the full stack (PostgreSQL + FastAPI Backend + Vector Store + Reports):

```bash
docker-compose up -d --build
```

### Persistent Volumes (`docker-compose.yml`)
- `pgdata`: PostgreSQL data directory
- `faissdata`: FAISS vector index binary and metadata
- `reportsdata`: Rendered HTML & PDF report files

---

## 🔄 n8n Weekly Automation Workflow

Import `n8n_workflow.json` into your n8n instance for automated competitive monitoring:
1. **Cron Trigger**: Weekly (`0 9 * * 1` - Mondays at 9:00 AM).
2. **Fetch Competitors**: `GET /competitors/`.
3. **Execute Pipeline**: `POST /pipeline/run/{competitor_id}` for each target.
4. **Slack Notification**: `POST /reports/deliver-slack/{report_id}` to publish updates.

---

## 📄 License & Attribution

Built for the **Autonomous Competitive Intelligence Agent Network**.
