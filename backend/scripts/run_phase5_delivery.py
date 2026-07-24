import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone

# Fix Windows console UTF-8 output encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path and load .env
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env", override=True)

import app.config as config_module
config_module.settings = config_module.Settings()

from sqlalchemy import select
from app.database import SessionLocal
from app.models.competitor import Competitor
from app.models.agent_run import AgentRun
from app.models.report import Report
from app.services.agent.graph import agent_pipeline_graph
from app.services.agent.state import AgentState
from app.services.reports_service import render_html_report, send_slack_notification, REPORTS_DIR


def test_n8n_cron_pipeline_run():
    db = SessionLocal()
    try:
        competitor = db.scalars(select(Competitor).where(Competitor.name == "GitHub")).first()
        if not competitor:
            print("Seeded competitor 'GitHub' not found. Run seed_data.py first.")
            return

        print("=========================================================================")
        print("1. END-TO-END N8N CRON PIPELINE EXECUTION & SLACK DELIVERY")
        print("=========================================================================\n")

        # 1. Create AgentRun row
        agent_run = AgentRun(
            competitor_id=competitor.id,
            status="RUNNING",
            started_at=datetime.now(timezone.utc),
            reflection_triggered=False,
        )
        db.add(agent_run)
        db.commit()
        db.refresh(agent_run)

        # 2. Invoke Agent Pipeline Graph
        urls = ["https://github.com/pricing", "https://github.blog/"]
        initial_state: AgentState = {
            "competitor_id": str(competitor.id),
            "competitor_name": competitor.name,
            "urls": urls,
            "raw_pages": [],
            "prev_snapshot": None,
            "diffs": [],
            "sentiment_results": [],
            "report_draft": "",
            "model_used": None,
            "retry_count": 0,
            "reflection_triggered": False,
            "is_incomplete": False,
            "status": "RUNNING",
        }

        print(f"[n8n Cron Trigger] Invoking pipeline for competitor '{competitor.name}' (Run ID: {agent_run.id})...")
        final_state = agent_pipeline_graph.invoke(initial_state)

        # 3. Update AgentRun row
        agent_run.status = "COMPLETED"
        agent_run.completed_at = datetime.now(timezone.utc)
        agent_run.reflection_triggered = final_state.get("reflection_triggered", False)
        
        # 4. Save Report row (matching SQLAlchemy Report schema)
        report_text = final_state.get("report_draft", "No draft generated.")
        
        # Render Standalone HTML Report File first
        temp_id = str(uuid.uuid4())
        html_relative_path = render_html_report(
            report_id=temp_id,
            competitor_name=competitor.name,
            markdown_content=report_text,
        )

        report_obj = Report(
            id=uuid.UUID(temp_id),
            user_id=competitor.user_id,
            competitor_id=competitor.id,
            summary=report_text[:400],
            html_url=html_relative_path,
            delivered_channels=["slack"],
            generated_at=datetime.now(timezone.utc),
        )
        db.add(report_obj)
        db.commit()
        db.refresh(report_obj)

        full_html_file = REPORTS_DIR / f"{report_obj.id}.html"

        print(f"\n[HTML Report Rendered]")
        print(f"  • Report Database ID : {report_obj.id}")
        print(f"  • HTML File Exists   : {full_html_file.exists()}")
        print(f"  • Relative HTML Path : {report_obj.html_url}")
        print(f"  • File Size          : {full_html_file.stat().st_size} bytes")

        # 5. Deliver Slack Webhook Notification
        slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL") or "https://hooks.slack.com/services/mock/test/webhook"
        slack_result = send_slack_notification(
            webhook_url=slack_webhook_url,
            competitor_name=competitor.name,
            report_summary=report_text[:350],
            html_report_url=f"http://localhost:8000{report_obj.html_url}",
        )

        print(f"\n[Slack Webhook Delivery Result]")
        print(f"  • Configured Webhook : {slack_webhook_url[:40]}...")
        print(f"  • Delivery Status    : {slack_result.get('status')}")
        print(f"  • Response Details   : {slack_result}")

        print("\n=========================================================================")
        print("2. DOCKER-COMPOSE PERSISTENT VOLUMES AUDIT")
        print("=========================================================================\n")
        compose_file = Path(__file__).resolve().parent.parent.parent / "docker-compose.yml"
        with open(compose_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            in_volumes = False
            for line in lines:
                if "volumes:" in line:
                    in_volumes = True
                if in_volumes:
                    print(line, end="")

        print("\n=========================================================================")
        print("PHASE 5 VERIFICATION COMPLETE")
        print("=========================================================================")

    finally:
        db.close()


if __name__ == "__main__":
    test_n8n_cron_pipeline_run()
