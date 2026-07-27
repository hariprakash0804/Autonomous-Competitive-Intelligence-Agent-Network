import os
import re
import smtplib
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import httpx

# Static reports storage directory
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "reports"


def _convert_markdown_to_slack_mrkdwn(text: str) -> str:
    """Converts raw Markdown syntax to clean Slack mrkdwn format."""
    if not text:
        return ""
    cleaned = text.strip()
    cleaned = re.sub(r"^#{1,6}\s*", "*", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-*_]{3,}\s*$", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"*\1*", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def render_html_report(report_id: str, competitor_name: str, markdown_content: str) -> str:
    """Renders a Markdown report into a standalone HTML document."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    html_body = markdown_content.replace("# ", "<h1>").replace("\n# ", "</h1>\n<h1>")
    html_body = html_body.replace("## ", "<h2>").replace("\n## ", "</h2>\n<h2>")
    html_body = html_body.replace("### ", "<h3>").replace("\n### ", "</h3>\n<h3>")
    html_body = html_body.replace("\n\n", "</p><p>").replace("\n- ", "</li><li>")
    html_body = html_body.replace("<li>", "<ul><li>", 1) + "</ul>" if "<li>" in html_body else html_body

    html_full = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Competitive Intelligence Executive Report - {competitor_name}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #090d16; color: #e2e8f0; margin: 0; padding: 40px 20px; line-height: 1.6; }}
    .container {{ max-width: 860px; margin: 0 auto; background: #0f172a; border: 1px solid #1e293b; border-radius: 16px; padding: 40px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5); }}
    h1 {{ color: #ffffff; border-bottom: 2px solid #6366f1; padding-bottom: 12px; font-size: 24px; }}
    h2 {{ color: #818cf8; margin-top: 28px; font-size: 18px; }}
    h3 {{ color: #cbd5e1; font-size: 15px; }}
    p {{ color: #94a3b8; font-size: 14px; }}
    ul {{ color: #cbd5e1; padding-left: 20px; font-size: 14px; }}
    li {{ margin-bottom: 6px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 13px; }}
    th, td {{ border: 1px solid #334155; padding: 10px 14px; text-align: left; }}
    th {{ background: #1e293b; color: #f8fafc; }}
    blockquote {{ background: #1e1b4b; border-left: 4px solid #6366f1; padding: 12px 16px; margin: 16px 0; color: #a5b4fc; border-radius: 4px; }}
    .footer {{ margin-top: 40px; pt: 20px; border-top: 1px solid #1e293b; font-size: 12px; color: #64748b; text-align: center; }}
  </style>
</head>
<body>
  <div class="container">
    {html_body}
    <div class="footer">
      Generated automatically by Autonomous Competitive Intelligence Agent Network • {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    </div>
  </div>
</body>
</html>"""

    file_path = REPORTS_DIR / f"{report_id}.html"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_full)

    return f"/static/reports/{report_id}.html"


def _clean_latin1(text: str) -> str:
    """Replaces Unicode characters outside Latin-1 (bullet, em-dash, smart quotes) with ASCII equivalents for FPDF."""
    if not text:
        return ""
    replacements = {
        "\u2022": "-",
        "\u2013": "-",
        "\u2014": "--",
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u2026": "...",
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    return text.encode("latin-1", "replace").decode("latin-1")


def render_pdf_report(report_id: str, competitor_name: str, markdown_content: str) -> str:
    """
    Renders a Markdown report into a downloadable PDF document using fpdf2.
    Supports headings (H1-H3), bullet lists, and body paragraphs.
    """
    from fpdf import FPDF

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title Header
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(99, 102, 241)  # Indigo
    pdf.cell(0, 12, _clean_latin1(f"Competitive Intelligence Report"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(100, 116, 139)  # Slate
    pdf.cell(0, 8, _clean_latin1(competitor_name), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Divider line
    pdf.set_draw_color(99, 102, 241)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Parse markdown content into lines and render
    pdf.set_text_color(30, 41, 59)  # Dark slate for body text
    lines = markdown_content.split("\n")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            pdf.ln(3)
            continue

        # Strip bold markdown markers and sanitize unicode for PDF rendering
        display_text = _clean_latin1(stripped.replace("**", "").replace("__", ""))

        if stripped.startswith("### "):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(71, 85, 105)
            pdf.multi_cell(0, 6, display_text[4:])
        elif stripped.startswith("## "):
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(99, 102, 241)
            pdf.multi_cell(0, 7, display_text[3:])
            pdf.ln(1)
        elif stripped.startswith("# "):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 15)
            pdf.set_text_color(15, 23, 42)
            pdf.multi_cell(0, 9, display_text[2:])
        elif stripped.startswith("- ") or stripped.startswith("* "):
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(51, 65, 85)
            bullet_text = display_text[2:]
            pdf.cell(6)
            pdf.multi_cell(0, 5.5, f"-  {bullet_text}")
        elif stripped.startswith("> "):
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(129, 140, 248)
            pdf.cell(8)
            pdf.multi_cell(0, 5.5, display_text[2:])
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(51, 65, 85)
            pdf.multi_cell(0, 5.5, display_text)

    # Footer
    pdf.ln(12)
    pdf.set_draw_color(99, 102, 241)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(
        0, 5,
        _clean_latin1(f"Generated by Autonomous Competitive Intelligence Agent Network  |  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"),
        align="C",
    )

    file_path = REPORTS_DIR / f"{report_id}.pdf"
    pdf.output(str(file_path))
    return f"/static/reports/{report_id}.pdf"


def send_slack_notification(webhook_url: str, competitor_name: str, report_summary: str, html_report_url: str) -> Dict[str, Any]:
    """Sends a rich Slack block notification with clean Slack mrkdwn formatting."""
    if not webhook_url or not webhook_url.strip():
        return {"status": "skipped", "reason": "No webhook URL configured"}

    formatted_summary = _convert_markdown_to_slack_mrkdwn(report_summary[:600])

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🚨 Competitive Intelligence Alert: {competitor_name}", "emoji": True},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Automated Weekly Agent Pipeline Executive Summary*\n\n{formatted_summary}"},
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "📄 View Full Executive Report"},
                        "url": html_report_url,
                        "style": "primary",
                    }
                ],
            },
        ]
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.post(webhook_url, json=payload)
            return {
                "status": "sent" if res.status_code == 200 else "failed",
                "status_code": res.status_code,
                "response": res.text,
            }
    except Exception as exc:
        return {"status": "failed", "reason": str(exc)}


def send_email_notification(
    recipient_email: str,
    competitor_name: str,
    markdown_report: str,
    html_report_url: str,
    smtp_host: Optional[str] = None,
    smtp_port: Optional[int] = None,
    smtp_user: Optional[str] = None,
    smtp_password: Optional[str] = None,
) -> Dict[str, Any]:
    """
    100% Free Email Facility (Gmail SMTP / Any Free SMTP Server).
    Sends the rendered HTML report directly to the recipient's inbox.
    Default SMTP Provider: Gmail SMTP (smtp.gmail.com:587).
    """
    host = smtp_host or os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
    user = smtp_user or os.getenv("SMTP_USER", "")
    password = smtp_password or os.getenv("SMTP_PASSWORD", "")

    if not user or not password:
        return {
            "status": "skipped",
            "reason": "SMTP_USER or SMTP_PASSWORD environment variables not set. Configure a free Gmail App Password in .env.",
        }

    subject = f"📊 Executive Intelligence Report: {competitor_name}"

    # Build HTML email body
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 20px;">
        <h2 style="color: #818cf8;">🚨 Competitive Intelligence Executive Summary: {competitor_name}</h2>
        <div style="background-color: #1e293b; padding: 20px; border-radius: 8px; margin: 15px 0;">
          <p>{markdown_report[:500]}...</p>
        </div>
        <p><a href="{html_report_url}" style="background-color: #6366f1; color: white; padding: 10px 18px; text-decoration: none; border-radius: 6px; font-weight: bold;">View Full Interactive HTML Report</a></p>
        <p style="color: #64748b; font-size: 12px; margin-top: 30px;">Sent automatically by Autonomous Competitive Intelligence Agent Network.</p>
      </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = recipient_email
    msg.attach(MIMEText(markdown_report, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, recipient_email, msg.as_string())
        return {"status": "sent", "recipient": recipient_email}
    except Exception as exc:
        return {"status": "failed", "reason": str(exc)}
