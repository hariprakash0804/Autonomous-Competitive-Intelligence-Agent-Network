# Implementation Plan - Phase 5: Automation, Delivery, Deploy

Implement the final phase of the **Autonomous Competitive Intelligence Agent Network**. Includes HTML report rendering engine, UI `ReportsPanel`, n8n weekly cron workflow export (`n8n_workflow.json`), Slack webhook notification integration, Docker Compose production deployment stack, final verification suite, and `README.md` architecture pass.

---

## User Review Required

> [!IMPORTANT]
> - **HTML Report Rendering**: Converts Markdown executive reports into styled HTML documents with embedded CSS and stores them at `backend/static/reports/{id}.html`.
> - **Slack Webhook & n8n Integration**: Adds `SLACK_WEBHOOK_URL` support to post executive summaries and report links directly to a Slack channel when an agent run finishes. Provides exportable `n8n_workflow.json` for weekly automated crons.
> - **Single Docker Stack Deployment**: Production `docker-compose.yml` and `Dockerfile` packaging FastAPI, PostgreSQL, local FAISS vector index, and static HTML reports in a unified Docker stack.

---

## Proposed Changes

### Backend Report Generation & Webhook Delivery

#### [NEW] [reports_service.py](file:///c:/Users/Hariprakash%20A/Desktop/Autonomous-Competitive-Intelligence-Agent-Network/backend/app/services/reports_service.py)
- `render_html_report(report_id, competitor_name, markdown_content)`: Converts markdown to clean styled HTML. Saves HTML file under `backend/static/reports/`.
- `send_slack_notification(webhook_url, competitor_name, report_summary, html_url)`: Posts rich Slack message payload via `httpx`.

#### [MODIFY] [reports.py](file:///c:/Users/Hariprakash%20A/Desktop/Autonomous-Competitive-Intelligence-Agent-Network/backend/app/routers/reports.py)
- Un-stub endpoints:
  - `GET /reports/`: Lists reports for user's competitors.
  - `GET /reports/{id}/html`: Returns rendered HTML report file.
  - `POST /reports/deliver-slack/{id}`: Triggers Slack webhook post for a report.

#### [NEW] [n8n_workflow.json](file:///c:/Users/Hariprakash%20A/Desktop/Autonomous-Competitive-Intelligence-Agent-Network/n8n_workflow.json)
- Exportable n8n workflow definition featuring weekly cron trigger -> API pipeline invocation -> Slack notification node.

---

### Frontend UI Reports Panel

#### [NEW] [ReportsPanel.jsx](file:///c:/Users/Hariprakash%20A/Desktop/Autonomous-Competitive-Intelligence-Agent-Network/frontend/src/components/ReportsPanel.jsx)
- Displays list of generated intelligence reports with "View HTML Report", "Send to Slack", and "Copy Link" buttons.

#### [MODIFY] [DashboardPage.jsx](file:///c:/Users/Hariprakash%20A/Desktop/Autonomous-Competitive-Intelligence-Agent-Network/frontend/src/pages/DashboardPage.jsx)
- Adds `ReportsPanel` tab/section into the dashboard interface.

---

### Containerization & Final Documentation

#### [NEW] [Dockerfile](file:///c:/Users/Hariprakash%20A/Desktop/Autonomous-Competitive-Intelligence-Agent-Network/backend/Dockerfile)
- Multi-stage build packaging Python 3.10 backend, dependencies, and static file directories.

#### [MODIFY] [docker-compose.yml](file:///c:/Users/Hariprakash%20A/Desktop/Autonomous-Competitive-Intelligence-Agent-Network/docker-compose.yml)
- Configures `postgres` DB service and `backend` API service with persistent volume mounts for Postgres data, FAISS vector index, and static HTML reports.

#### [MODIFY] [README.md](file:///c:/Users/Hariprakash%20A/Desktop/Autonomous-Competitive-Intelligence-Agent-Network/README.md)
- Complete ASCII architecture diagram, setup instructions, OpenRouter setup guide, n8n workflow import steps, and deployment guide.

#### [NEW] [run_phase5_delivery.py](file:///c:/Users/Hariprakash%20A/Desktop/Autonomous-Competitive-Intelligence-Agent-Network/backend/scripts/run_phase5_delivery.py)
- Final end-to-end verification script testing HTML report generation, Slack webhook delivery payload, and database audit.

---

## Verification Plan

### Automated & CLI Verification
1. Run `python -m backend.scripts.run_phase5_delivery` to verify HTML report creation, Slack webhook payload, and database audit.
2. Build frontend production bundle with `npm run build`.

### Interactive Verification
1. Open generated HTML report URL in browser to verify styling.
2. Verify Slack webhook message payload receipt.
