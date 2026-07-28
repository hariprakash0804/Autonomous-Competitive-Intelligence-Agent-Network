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
from app.dependencies.auth import get_current_user, get_current_user_or_api_key
from app.models.user import User
from app.models.report import Report
from app.models.competitor import Competitor
from app.config import settings
from app.services.reports_service import (
    render_html_report,
    render_pdf_report,
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
    current_user: Annotated[User, Depends(get_current_user_or_api_key)],
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
            "pdf_url": f"/reports/{r.id}/pdf",
        })

@router.get("/competitor/{competitor_id}")
def get_reports_by_competitor(
    competitor_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_api_key)],
):
    """Lists all generated reports for a specific competitor target."""
    comp = db.get(Competitor, competitor_id)
    if not comp or comp.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

    reports = db.scalars(
        select(Report)
        .where(Report.competitor_id == competitor_id)
        .order_by(Report.generated_at.desc())
    ).all()

    return [
        {
            "id": str(r.id),
            "competitor_id": str(r.competitor_id),
            "competitor_name": comp.name,
            "model_used": r.model_used or "unknown",
            "summary": r.summary or "",
            "generated_at": r.generated_at.isoformat(),
            "formatted_date": r.generated_at.strftime("%b %d, %Y %H:%M UTC"),
            "content_snippet": (r.summary or "")[:200] + "...",
            "html_url": f"/reports/{r.id}/html",
            "pdf_url": f"/reports/{r.id}/pdf",
        }
        for r in reports
    ]


@router.get("/{report_id}/html")
def get_report_html(
    report_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    """Serves the standalone rendered HTML report file with clean Markdown formatting."""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    comp = db.get(Competitor, report.competitor_id)
    comp_name = comp.name if comp else "Competitor"

    file_path = REPORTS_DIR / f"{report.id}.html"
    render_html_report(str(report.id), comp_name, report.summary or "")

    return FileResponse(file_path, media_type="text/html")


@router.get("/{report_id}/pdf")
def get_report_pdf(
    report_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    """Serves or generates the downloadable PDF report file."""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    comp = db.get(Competitor, report.competitor_id)
    comp_name = comp.name if comp else "Competitor"

    file_path = REPORTS_DIR / f"{report.id}.pdf"
    render_pdf_report(str(report.id), comp_name, report.summary or "")

    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=f"competitive_intel_{comp_name.replace(' ', '_')}_{report.id}.pdf",
    )


def get_public_backend_url() -> str:
    """
    Resolves the public backend URL for external links (Slack, Email, webhooks).
    Prioritizes public URL environment variables (WEBHOOK_URL, RENDER_EXTERNAL_URL, PUBLIC_URL, BACKEND_URL)
    over local fallback.
    """
    for env_var in ["WEBHOOK_URL", "RENDER_EXTERNAL_URL", "PUBLIC_URL", "BACKEND_URL"]:
        val = os.getenv(env_var)
        if val and val.strip():
            cleaned = val.strip().rstrip("/")
            if cleaned.startswith("http://") or cleaned.startswith("https://"):
                if "localhost" not in cleaned and "127.0.0.1" not in cleaned:
                    return cleaned

    if settings.BACKEND_URL and "localhost" not in settings.BACKEND_URL and "127.0.0.1" not in settings.BACKEND_URL:
        return settings.BACKEND_URL.strip().rstrip("/")

    return (os.getenv("BACKEND_URL") or settings.BACKEND_URL or "http://localhost:8000").strip().rstrip("/")


@router.post("/deliver-slack/{report_id}")
def deliver_slack_notification(
    report_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_api_key)],
    payload: Optional[SlackDeliverRequest] = None,
):
    """Triggers Slack webhook delivery for a report."""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    comp = db.get(Competitor, report.competitor_id)
    if not comp or comp.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    target_webhook = payload.webhook_url.strip() if payload and payload.webhook_url and payload.webhook_url.strip() else None
    user_webhook = (current_user.slack_webhook_url or "").strip() if getattr(current_user, "slack_webhook_url", None) else None
    env_webhook = (
        os.getenv("SLACK_WEBHOOK_URL")
        or os.getenv("WEBHOOK_URL")
        or getattr(settings, "SLACK_WEBHOOK_URL", None)
        or getattr(settings, "WEBHOOK_URL", None)
        or ""
    ).strip() or None

    webhook_url = target_webhook or user_webhook or env_webhook
    if not webhook_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slack webhook URL is missing. Set WEBHOOK_URL / SLACK_WEBHOOK_URL in environment, save it in your Profile settings, or provide 'webhook_url' in request payload.",
        )
    backend_url = get_public_backend_url()
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
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_api_key)],
    payload: Optional[EmailDeliverRequest] = None,
):
    """Triggers 100% Free Email delivery (Gmail SMTP / Free SMTP) for a report."""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    comp = db.get(Competitor, report.competitor_id)
    if not comp or comp.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    target_email = (payload.recipient_email if payload and payload.recipient_email else None) or current_user.email
    backend_url = get_public_backend_url()
    html_url = f"{backend_url}/reports/{report.id}/html"

    res = send_email_notification(
        recipient_email=target_email,
        competitor_name=comp.name,
        markdown_report=report.summary or "",
        html_report_url=html_url,
    )

    return {"status": "success", "email_result": res}
