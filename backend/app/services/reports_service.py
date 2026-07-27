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


def _convert_markdown_to_html(md_text: str) -> str:
    """Converts raw Markdown text (including tables, headers, bold text, lists) to HTML."""
    if not md_text:
        return "<p>No report summary available.</p>"

    lines = md_text.split("\n")
    html_parts = []
    in_table = False
    table_rows = []
    in_list = False

    def flush_list():
        nonlocal in_list
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    def flush_table():
        nonlocal in_table, table_rows
        if table_rows:
            header = table_rows[0]
            body = [r for r in table_rows[1:] if not all(c.strip().startswith("-") for c in r)]
            table_html = ["<table><thead><tr>"]
            for h in header:
                clean_h = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", h.strip())
                table_html.append(f"<th>{clean_h}</th>")
            table_html.append("</tr></thead><tbody>")
            for row in body:
                table_html.append("<tr>")
                for cell in row:
                    clean_c = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", cell.strip())
                    table_html.append(f"<td>{clean_c}</td>")
                table_html.append("</tr>")
            table_html.append("</tbody></table>")
            html_parts.append("".join(table_html))
            table_rows = []
        in_table = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            flush_list()
            in_table = True
            cells = [c for c in stripped.split("|")[1:-1]]
            table_rows.append(cells)
            continue
        else:
            if in_table:
                flush_table()

        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            item_text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", stripped[2:])
            html_parts.append(f"<li>{item_text}</li>")
            continue
        else:
            flush_list()

        if stripped.startswith("### "):
            text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", stripped[4:])
            html_parts.append(f"<h3>{text}</h3>")
        elif stripped.startswith("## "):
            text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", stripped[3:])
            html_parts.append(f"<h2>{text}</h2>")
        elif stripped.startswith("# "):
            text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", stripped[2:])
            html_parts.append(f"<h1>{text}</h1>")
        elif stripped.startswith("> "):
            text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", stripped[2:])
            html_parts.append(f"<blockquote>{text}</blockquote>")
        elif stripped == "---":
            html_parts.append("<hr style='border: 0; border-top: 1px solid #1e293b; margin: 24px 0;'>")
        elif stripped:
            text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", stripped)
            html_parts.append(f"<p>{text}</p>")

    if in_table:
        flush_table()
    flush_list()

    return "\n".join(html_parts)


def render_html_report(report_id: str, competitor_name: str, markdown_content: str) -> str:
    """Renders a Markdown report into a standalone styled HTML document."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    html_body = _convert_markdown_to_html(markdown_content)

    html_full = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Competitive Intelligence Executive Report - {competitor_name}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #090d16; color: #e2e8f0; margin: 0; padding: 40px 20px; line-height: 1.6; }}
    .container {{ max-width: 860px; margin: 0 auto; background: #0f172a; border: 1px solid #1e293b; border-radius: 16px; padding: 40px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5); }}
    h1 {{ color: #ffffff; border-bottom: 2px solid #6366f1; padding-bottom: 12px; font-size: 24px; margin-top: 0; }}
    h2 {{ color: #818cf8; margin-top: 28px; font-size: 18px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
    h3 {{ color: #cbd5e1; font-size: 15px; margin-top: 20px; }}
    p {{ color: #94a3b8; font-size: 14px; margin: 10px 0; }}
    ul {{ color: #cbd5e1; padding-left: 20px; font-size: 14px; }}
    li {{ margin-bottom: 8px; color: #cbd5e1; }}
    strong {{ color: #f8fafc; font-weight: 600; }}
    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 13px; background: #0b1329; border-radius: 8px; overflow: hidden; border: 1px solid #334155; }}
    th, td {{ border: 1px solid #334155; padding: 10px 14px; text-align: left; }}
    th {{ background: #1e293b; color: #818cf8; font-weight: 700; }}
    tr:nth-child(even) {{ background: #0f172a; }}
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
    """Replaces Unicode characters, non-breaking hyphens, dashes, and HTML breaks with clean ASCII equivalents for FPDF."""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n  - ", text, flags=re.IGNORECASE)
    replacements = {
        "\u00a0": " ",
        "\u202f": " ",
        "\u2007": " ",
        "\u200b": "",
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "--",
        "\u2015": "--",
        "\u2212": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u2026": "...",
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    return text.encode("latin-1", "ignore").decode("latin-1")


def render_pdf_report(report_id: str, competitor_name: str, markdown_content: str) -> str:
    """
    Renders a Markdown report into a downloadable PDF document using fpdf2.
    Supports headings, bullet lists, native multi-column PDF tables, and clean typography.
    """
    from fpdf import FPDF

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = REPORTS_DIR / f"{report_id}.pdf"

    try:
        pdf = FPDF()
        pdf.set_margins(15, 15, 15)
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Title Header
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(99, 102, 241)  # Indigo
        pdf.cell(0, 10, _clean_latin1("Competitive Intelligence Executive Report"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(100, 116, 139)  # Slate
        pdf.cell(0, 6, _clean_latin1(f"Target: {competitor_name}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        # Divider line
        pdf.set_draw_color(99, 102, 241)
        pdf.set_line_width(0.5)
        cur_y = pdf.get_y()
        pdf.line(15, cur_y, 195, cur_y)
        pdf.ln(4)

        lines = markdown_content.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if not stripped or stripped == "---":
                pdf.ln(2)
                i += 1
                continue

            # Process Markdown Table block
            if stripped.startswith("|") and stripped.endswith("|"):
                table_lines = []
                while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                    table_lines.append(lines[i].strip())
                    i += 1

                if table_lines:
                    rows = []
                    for tl in table_lines:
                        cells = [c.strip() for c in tl.split("|")[1:-1]]
                        if not all(c.startswith("-") for c in cells):
                            rows.append(cells)

                    if rows:
                        if pdf.get_y() > 220:
                            pdf.add_page()
                        pdf.ln(2)
                        pdf.set_font("Helvetica", "", 8.5)
                        pdf.set_text_color(30, 41, 59)

                        num_cols = max(len(r) for r in rows)
                        if num_cols == 3:
                            col_w = (35, 72, 73)
                        elif num_cols == 2:
                            col_w = (50, 130)
                        else:
                            col_w = tuple([int(180 / max(1, num_cols))] * num_cols)

                        try:
                            with pdf.table(col_widths=col_w, text_align="LEFT", line_height=4.5) as table:
                                for r_idx, row_cells in enumerate(rows):
                                    row = table.row()
                                    for c_idx, cell_text in enumerate(row_cells):
                                        clean_cell = _clean_latin1(cell_text.replace("**", ""))
                                        row.cell(clean_cell)
                        except Exception as t_err:
                            print(f"[PDF Table Fallback] {t_err}")
                            for row_cells in rows:
                                pdf.multi_cell(pdf.epw, 5, _clean_latin1(" | ".join(row_cells).replace("**", "")))
                        pdf.ln(3)
                continue

            if pdf.get_y() > 250:
                pdf.add_page()

            pdf.set_x(15)
            display_text = _clean_latin1(stripped.replace("**", "").replace("__", ""))
            epw = pdf.epw

            if stripped.startswith("### "):
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_text_color(71, 85, 105)
                pdf.multi_cell(epw, 6, display_text[4:])
            elif stripped.startswith("## "):
                pdf.ln(3)
                pdf.set_font("Helvetica", "B", 12)
                pdf.set_text_color(99, 102, 241)
                pdf.multi_cell(epw, 6, display_text[3:])
            elif stripped.startswith("# "):
                pdf.ln(3)
                pdf.set_font("Helvetica", "B", 14)
                pdf.set_text_color(15, 23, 42)
                pdf.multi_cell(epw, 8, display_text[2:])
            elif stripped.startswith("- ") or stripped.startswith("* "):
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(51, 65, 85)
                bullet_text = display_text[2:]
                pdf.multi_cell(epw, 5, f"  -  {bullet_text}")
            elif stripped.startswith("> "):
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(99, 102, 241)
                pdf.multi_cell(epw, 5, f"  >  {display_text[2:]}")
            else:
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(51, 65, 85)
                pdf.multi_cell(epw, 5, display_text)

            i += 1

        # Footer
        pdf.ln(6)
        cur_y = pdf.get_y()
        if cur_y < 260:
            pdf.set_draw_color(99, 102, 241)
            pdf.line(15, cur_y, 195, cur_y)
            pdf.ln(3)
        pdf.set_x(15)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(
            pdf.epw, 5,
            _clean_latin1(f"Generated by Autonomous Competitive Intelligence Agent Network  |  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"),
            align="C",
        )

        pdf.output(str(file_path))
    except Exception as exc:
        print(f"[PDF Generation Error] {exc}. Rendering fallback plain text PDF...")
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, _clean_latin1(markdown_content.replace("**", "")))
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
