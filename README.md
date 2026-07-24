# Autonomous Competitive Intelligence Agent Network

An autonomous, multi-agent full-stack platform for competitive intelligence gathering, web scraping, VADER sentiment & topic analysis, pricing diff extraction, FAISS vector RAG, LangGraph multi-agent workflow orchestration, and automated Slack HTML report delivery.

---

## 🏛️ System Architecture

```text
+-----------------------------------------------------------------------------------+
|                                  USER INTERFACE                                   |
|                React + Vite + Tailwind CSS + Recharts Dashboard                   |
+----------------------------------------+------------------------------------------+
                                         | REST API (JWT Auth)
                                         v
+-----------------------------------------------------------------------------------+
|                              FASTAPI BACKEND SERVICE                              |
|                                                                                   |
|  +---------------------+   +---------------------+   +--------------------------+ |
|  | Scraper Service     |   | Diff Pricing Engine |   | VADER Sentiment Analyzer | |
|  | Playwright / HTTP   |   | Regex + Binding Fix |   | NLTK + Topic Extraction  | |
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
+---------------------------------------|-------------------------------------------+
                                        |
      +---------------------------------+---------------------------------+
      |                                 |                                 |
      v                                 v                                 v
+-----------+                   +---------------+                 +---------------+
| PostgreSQL|                   |  FAISS Index  |                 | Static HTML & |
|  Database |                   | Vector Store  |                 | Slack Webhook |
+-----------+                   +---------------+                 +---------------+
```

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10, FastAPI, SQLAlchemy, Alembic, LangGraph, Playwright, VADER Sentiment, FAISS vector store.
- **LLM Provider**: OpenRouter API (`https://openrouter.ai/api/v1`) using OpenAI SDK with active free models (`google/gemma-4-31b-it:free`, `nvidia/nemotron-3-nano-30b-a3b:free`), 3s proactive rate-limit guard (20 req/min), and automatic 429 / 404 fallback handling.
- **Frontend**: React 19, Vite, Tailwind CSS, Recharts (Price Timeline & Sentiment Score charts), Lucide React.
- **Database**: PostgreSQL with SQLAlchemy ORM.
- **Vector Store**: Local FAISS file-based vector index.
- **Automation & Delivery**: Rendered standalone HTML reports, n8n weekly cron trigger workflow (`n8n_workflow.json`), and Slack Webhook notifications.
- **Containerization**: Docker Compose (`docker-compose.yml`) with persistent volume storage for PostgreSQL data (`pgdata`), FAISS vector store (`faissdata`), and rendered HTML reports (`reportsdata`).

---

## 🚀 Quickstart & Local Setup

### 1. Backend Setup
```bash
# Navigate to backend
cd backend

# Create virtual environment & install dependencies
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Download NLTK VADER lexicon
python -c "import nltk; nltk.download('vader_lexicon')"

# Install Playwright browser binaries
playwright install chromium

# Set environment variables (.env)
cp .env.example .env

# Run database migrations and seed baseline competitors
alembic upgrade head
python scripts/seed_data.py

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup
```bash
# Navigate to frontend
cd frontend

# Install node packages
npm install

# Start Vite dev server
npm run dev
```

Visit `http://localhost:5173` in your browser. Default login: `user@example.com` / `password123`.

---

## 📦 Docker Compose Deployment

To deploy the unified backend stack (PostgreSQL + FastAPI + FAISS + HTML Reports):

```bash
docker-compose up -d --build
```

### Persistent Volume Storage (`docker-compose.yml`)
```yaml
volumes:
  pgdata:
    driver: local      # Persists PostgreSQL database data
  faissdata:
    driver: local      # Persists FAISS vector embeddings index
  reportsdata:
    driver: local      # Persists rendered HTML reports
```

---

## 🔄 n8n Weekly Automation Workflow

Import `n8n_workflow.json` into your n8n instance:
1. **Trigger**: Weekly Cron (`0 9 * * 1` - Mondays at 9:00 AM).
2. **Action 1**: Fetch active competitor list (`GET /competitors/`).
3. **Action 2**: Trigger background agent pipeline (`POST /pipeline/run/{competitor_id}`).
4. **Action 3**: Post summary & HTML report link to Slack Webhook (`POST /reports/deliver-slack/{report_id}`).

---

## 📄 License & Attribution

Built for the **Autonomous Competitive Intelligence Agent Network** project.
