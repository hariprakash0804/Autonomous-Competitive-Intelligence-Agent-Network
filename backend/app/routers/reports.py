import os
import uuid
from pathlib import Path
from typing import Annotated, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.report import Report
from app.models.competitor import Competitor
from app.config import settings
from app.services.reports_service import (
    render_html_report,
    send_slack_notification,
    send_email_notification,
    REPORTS_DIR,
)

router = APIRouter(prefix="/reports", tags=["reports"])


class SlackDeliverRequest(BaseModel):
    webhook_url: Optional[str] = None


class EmailDeliverRequest(BaseModel):
    recipient_email: Optional[str] = None


@router.get("/")
def list_reports(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Lists all generated competitive intelligence reports for current user's competitors."""
    user_competitors = db.scalars(
        select(Competitor.id).where(Competitor.user_id == current_user.id)
    ).all()

    if not user_competitors:
        return []

    reports = db.scalars(
        select(Report)
        .where(Report.competitor_id.in_(user_competitors))
        .order_by(Report.generated_at.desc())
    ).all()

    results = []
    for r in reports:
        comp = db.get(Competitor, r.competitor_id)
        results.append({
            "id": str(r.id),
            "competitor_id": str(r.competitor_id),
            "competitor_name": comp.name if comp else "Unknown",
            "model_used": r.model_used or "unknown",
            "generated_at": r.generated_at.isoformat(),
            "formatted_date": r.generated_at.strftime("%b %d, %Y %H:%M UTC"),
            "content_snippet": (r.summary or "")[:200] + "...",
            "html_url": f"/reports/{r.id}/html",
        })

    return results


@router.get("/{report_id}/html")
def get_report_html(
    report_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    """Serves the standalone rendered HTML report file."""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    comp = db.get(Competitor, report.competitor_id)
    comp_name = comp.name if comp else "Competitor"

    file_path = REPORTS_DIR / f"{report.id}.html"
    if not file_path.exists():
        render_html_report(str(report.id), comp_name, report.summary or "")

    return FileResponse(file_path, media_type="text/html")


@router.post("/deliver-slack/{report_id}")
def deliver_slack_notification(
    report_id: uuid.UUID,
    payload: SlackDeliverRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Triggers Slack webhook delivery for a report."""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    comp = db.get(Competitor, report.competitor_id)
    if not comp or comp.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    webhook_url = payload.webhook_url or os.getenv("SLACK_WEBHOOK_URL") or "https://hooks.slack.com/services/mock/test/webhook"
    backend_url = (settings.BACKEND_URL or os.getenv("BACKEND_URL", "http://localhost:8000")).rstrip("/")
    html_url = f"{backend_url}/reports/{report.id}/html"

    res = send_slack_notification(
        webhook_url=webhook_url,
        competitor_name=comp.name,
        report_summary=report.summary or "",
        html_report_url=html_url,
    )

    return {"status": "success", "slack_result": res}


@router.post("/deliver-email/{report_id}")
def deliver_email_notification(
    report_id: uuid.UUID,
    payload: EmailDeliverRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Triggers 100% Free Email delivery (Gmail SMTP / Free SMTP) for a report."""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    comp = db.get(Competitor, report.competitor_id)
    if not comp or comp.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    target_email = payload.recipient_email or current_user.email
    backend_url = (settings.BACKEND_URL or os.getenv("BACKEND_URL", "http://localhost:8000")).rstrip("/")
    html_url = f"{backend_url}/reports/{report.id}/html"

    res = send_email_notification(
        recipient_email=target_email,
        competitor_name=comp.name,
        markdown_report=report.summary or "",
        html_report_url=html_url,
    )

    return {"status": "success", "email_result": res}
