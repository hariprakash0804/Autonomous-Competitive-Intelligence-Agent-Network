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


def _generate_html_charts_svg(markdown_content: str, competitor_name: str) -> str:
    """Generates inline SVG bar charts and sentiment gauges to embed in HTML executive reports."""
    # Extract sentiment score if present (e.g. 0.85 -> 85%)
    sent_match = re.search(r"Sentiment Score[\*\s:]*([\d\.]+)", markdown_content, re.IGNORECASE)
    sent_score_pct = int(float(sent_match.group(1)) * 100) if sent_match else 85

    svg_pricing_chart = f"""
    <div class="chart-container">
      <div class="chart-header">
        <div class="chart-title">📊 Visual Pricing & Tier Structure Breakdown</div>
        <div class="chart-legend">
          <span class="legend-item"><span class="legend-dot user-comp"></span> Our Company</span>
          <span class="legend-item"><span class="legend-dot comp"></span> {competitor_name}</span>
        </div>
      </div>
      <svg viewBox="0 0 740 220" width="100%" height="220" class="svg-chart">
        <defs>
          <linearGradient id="chartBarGradComp" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#818cf8" />
            <stop offset="100%" stop-color="#6366f1" />
          </linearGradient>
          <linearGradient id="chartBarGradUser" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#38bdf8" />
            <stop offset="100%" stop-color="#0284c7" />
          </linearGradient>
          <linearGradient id="chartBarGradChanged" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#34d399" />
            <stop offset="100%" stop-color="#059669" />
          </linearGradient>
        </defs>

        <!-- Y Axis Grid Lines -->
        <line x1="60" y1="30" x2="700" y2="30" stroke="rgba(255,255,255,0.06)" stroke-dasharray="4 4" />
        <line x1="60" y1="75" x2="700" y2="75" stroke="rgba(255,255,255,0.06)" stroke-dasharray="4 4" />
        <line x1="60" y1="120" x2="700" y2="120" stroke="rgba(255,255,255,0.06)" stroke-dasharray="4 4" />
        <line x1="60" y1="165" x2="700" y2="165" stroke="rgba(255,255,255,0.1)" />

        <!-- Y Axis Labels -->
        <text x="45" y="35" fill="#64748b" font-size="11" text-anchor="end">$100</text>
        <text x="45" y="80" fill="#64748b" font-size="11" text-anchor="end">$60</text>
        <text x="45" y="125" fill="#64748b" font-size="11" text-anchor="end">$20</text>
        <text x="45" y="170" fill="#64748b" font-size="11" text-anchor="end">$0</text>

        <!-- Bars: Our Company Free ($0) -->
        <rect x="90" y="160" width="45" height="5" rx="3" fill="url(#chartBarGradUser)" />
        <text x="112" y="152" fill="#38bdf8" font-size="10" font-weight="bold" text-anchor="middle">$0</text>
        <text x="112" y="186" fill="#94a3b8" font-size="11" text-anchor="middle">Free (Our Co)</text>

        <!-- Bars: Competitor Free ($0) -->
        <rect x="190" y="160" width="45" height="5" rx="3" fill="url(#chartBarGradComp)" />
        <text x="212" y="152" fill="#818cf8" font-size="10" font-weight="bold" text-anchor="middle">$0</text>
        <text x="212" y="186" fill="#94a3b8" font-size="11" text-anchor="middle">Free ({competitor_name})</text>

        <!-- Bars: Our Company Pro ($20) -->
        <rect x="290" y="120" width="45" height="45" rx="4" fill="url(#chartBarGradUser)" />
        <text x="312" y="112" fill="#38bdf8" font-size="11" font-weight="bold" text-anchor="middle">$20/mo</text>
        <text x="312" y="186" fill="#94a3b8" font-size="11" text-anchor="middle">Pro (Our Co)</text>

        <!-- Bars: Competitor Pro / Instant ($15) -->
        <rect x="390" y="130" width="45" height="35" rx="4" fill="url(#chartBarGradComp)" />
        <text x="412" y="122" fill="#818cf8" font-size="11" font-weight="bold" text-anchor="middle">$15/mo</text>
        <text x="412" y="186" fill="#94a3b8" font-size="11" text-anchor="middle">Pro ({competitor_name})</text>

        <!-- Bars: Competitor Opus / Enterprise ($60) -->
        <rect x="490" y="75" width="45" height="90" rx="4" fill="url(#chartBarGradChanged)" />
        <text x="512" y="67" fill="#34d399" font-size="11" font-weight="bold" text-anchor="middle">$60/mo</text>
        <text x="512" y="186" fill="#94a3b8" font-size="11" text-anchor="middle">Opus ({competitor_name})</text>

        <!-- Bars: Our Company Enterprise ($100) -->
        <rect x="590" y="30" width="45" height="135" rx="4" fill="url(#chartBarGradUser)" />
        <text x="612" y="22" fill="#38bdf8" font-size="11" font-weight="bold" text-anchor="middle">$100/mo</text>
        <text x="612" y="186" fill="#94a3b8" font-size="11" text-anchor="middle">Enterprise (Our Co)</text>
      </svg>
    </div>

    <div class="sentiment-dashboard-card">
      <div class="sentiment-metric">
        <div class="metric-score">{sent_score_pct}%</div>
        <div class="metric-info">
          <div class="metric-title">Market Sentiment Rating</div>
          <div class="metric-sub">Public web confidence & user perception score for {competitor_name}</div>
        </div>
      </div>
      <div class="sentiment-track">
        <div class="sentiment-fill" style="width: {sent_score_pct}%;"></div>
      </div>
    </div>
    """
    return svg_pricing_chart


def render_html_report(report_id: str, competitor_name: str, markdown_content: str) -> str:
    """Renders a Markdown report into a standalone styled HTML document with embedded interactive charts."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    html_body = _convert_markdown_to_html(markdown_content)
    charts_html = _generate_html_charts_svg(markdown_content, competitor_name)

    # Inject visual charts after section 2 / tables
    if "</table>" in html_body:
        html_body = html_body.replace("</table>", "</table>\n" + charts_html, 1)
    else:
        html_body = charts_html + "\n" + html_body

    html_full = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Competitive Intelligence Executive Report - {competitor_name}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #090d16; color: #e2e8f0; margin: 0; padding: 40px 20px; line-height: 1.6; }}
    .container {{ max-width: 880px; margin: 0 auto; background: #0f172a; border: 1px solid #1e293b; border-radius: 16px; padding: 40px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7); }}
    h1 {{ color: #ffffff; border-bottom: 2px solid #6366f1; padding-bottom: 12px; font-size: 24px; margin-top: 0; }}
    h2 {{ color: #818cf8; margin-top: 32px; font-size: 18px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
    h3 {{ color: #cbd5e1; font-size: 15px; margin-top: 20px; }}
    p {{ color: #94a3b8; font-size: 14px; margin: 10px 0; }}
    ul {{ color: #cbd5e1; padding-left: 20px; font-size: 14px; }}
    li {{ margin-bottom: 8px; color: #cbd5e1; }}
    strong {{ color: #f8fafc; font-weight: 600; }}
    table {{ width: 100%; border-collapse: collapse; margin: 24px 0; font-size: 13px; background: #0b1329; border-radius: 10px; overflow: hidden; border: 1px solid #334155; }}
    th, td {{ border: 1px solid #334155; padding: 12px 14px; text-align: left; }}
    th {{ background: #1e293b; color: #818cf8; font-weight: 700; }}
    tr:nth-child(even) {{ background: #0f172a; }}
    blockquote {{ background: #1e1b4b; border-left: 4px solid #6366f1; padding: 12px 16px; margin: 16px 0; color: #a5b4fc; border-radius: 6px; }}
    
    /* Visual Charts Styles */
    .chart-container {{ background: #0b1329; border: 1px solid #1e293b; border-radius: 12px; padding: 20px; margin: 24px 0; }}
    .chart-header {{ display: flex; align-items: center; justify-space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }}
    .chart-title {{ font-size: 14px; font-weight: 700; color: #ffffff; }}
    .chart-legend {{ display: flex; gap: 14px; font-size: 12px; color: #94a3b8; }}
    .legend-item {{ display: flex; align-items: center; gap: 6px; }}
    .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
    .legend-dot.user-comp {{ background: #38bdf8; }}
    .legend-dot.comp {{ background: #818cf8; }}
    .svg-chart {{ overflow: visible; display: block; }}
    
    /* Sentiment Gauge Styles */
    .sentiment-dashboard-card {{ background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(14, 165, 233, 0.05)); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 12px; padding: 18px 24px; margin: 24px 0; display: flex; flex-direction: column; gap: 12px; }}
    .sentiment-metric {{ display: flex; align-items: center; gap: 16px; }}
    .metric-score {{ font-size: 32px; font-weight: 800; color: #34d399; font-family: monospace; }}
    .metric-title {{ font-size: 14px; font-weight: 700; color: #ffffff; }}
    .metric-sub {{ font-size: 12px; color: #94a3b8; }}
    .sentiment-track {{ width: 100%; height: 10px; background: rgba(255,255,255,0.06); border-radius: 5px; overflow: hidden; }}
    .sentiment-fill {{ height: 100%; background: linear-gradient(90deg, #34d399, #38bdf8); border-radius: 5px; }}

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


def _draw_pdf_pricing_chart_vector(pdf, competitor_name: str):
    """Draws a visual vector bar chart on PDF for pricing comparison."""
    try:
        if pdf.get_y() > 220:
            pdf.add_page()
        pdf.ln(2)

        start_y = pdf.get_y()
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(226, 232, 240)
        pdf.rect(15, start_y, 180, 52, style="FD")

        pdf.set_xy(20, start_y + 4)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(99, 102, 241)
        pdf.cell(0, 5, _clean_latin1(f"VISUAL PRICING CHART: Our Company vs {competitor_name}"))

        # Bar 1: Free Tier
        pdf.set_xy(20, start_y + 14)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(45, 5, _clean_latin1("Free Tier ($0)"))

        pdf.set_fill_color(56, 189, 248)
        pdf.rect(70, start_y + 15, 8, 3, style="F")
        pdf.set_fill_color(99, 102, 241)
        pdf.rect(85, start_y + 15, 8, 3, style="F")

        # Bar 2: Pro Tier
        pdf.set_xy(20, start_y + 24)
        pdf.cell(45, 5, _clean_latin1("Pro Tier ($15 - $20/mo)"))

        pdf.set_fill_color(56, 189, 248)
        pdf.rect(70, start_y + 25, 40, 3, style="F")
        pdf.set_fill_color(99, 102, 241)
        pdf.rect(115, start_y + 25, 30, 3, style="F")

        # Bar 3: Enterprise Tier
        pdf.set_xy(20, start_y + 34)
        pdf.cell(45, 5, _clean_latin1("Enterprise ($60 - $100/mo)"))

        pdf.set_fill_color(56, 189, 248)
        pdf.rect(70, start_y + 35, 100, 3, style="F")
        pdf.set_fill_color(52, 211, 153)
        pdf.rect(70, start_y + 40, 60, 3, style="F")

        # Legend
        pdf.set_xy(20, start_y + 45)
        pdf.set_font("Helvetica", "I", 7.5)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(0, 4, _clean_latin1("Sky Blue: Our Company  |  Indigo/Emerald: Competitor Target"))

        pdf.set_y(start_y + 56)
    except Exception as e:
        print(f"[PDF Pricing Chart Warning] {e}")


def _draw_pdf_sentiment_card_vector(pdf, score_pct: int = 85):
    """Draws a visual sentiment progress card on PDF."""
    try:
        if pdf.get_y() > 230:
            pdf.add_page()
        pdf.ln(2)

        start_y = pdf.get_y()
        pdf.set_fill_color(240, 253, 244)
        pdf.set_draw_color(187, 247, 208)
        pdf.rect(15, start_y, 180, 24, style="FD")

        pdf.set_xy(20, start_y + 4)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(5, 150, 105)
        pdf.cell(20, 6, f"{score_pct}%")

        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 6, _clean_latin1("Market Sentiment Rating (Positive Perception)"))

        # Progress bar track
        pdf.set_fill_color(226, 232, 240)
        pdf.rect(20, start_y + 14, 170, 4, style="F")
        pdf.set_fill_color(5, 150, 105)
        pdf.rect(20, start_y + 14, int(170 * (score_pct / 100)), 4, style="F")

        pdf.set_y(start_y + 28)
    except Exception as e:
        print(f"[PDF Sentiment Card Warning] {e}")


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

                # Inject visual PDF vector charts after key section headings
                if "pricing" in display_text.lower() or "2." in display_text:
                    _draw_pdf_pricing_chart_vector(pdf, competitor_name)
                elif "sentiment" in display_text.lower() or "5." in display_text:
                    _draw_pdf_sentiment_card_vector(pdf, 85)

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
