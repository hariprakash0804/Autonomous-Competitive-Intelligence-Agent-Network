"""
MCP Tool Server exposing scrape(url), diff_pricing(old, new), and sentiment_score(text)
via stdio transport using FastMCP.
"""

from mcp.server.fastmcp import FastMCP
from app.services.scraper import scrape_url
from app.services.diff_pricing import diff_pricing
from app.services.sentiment import sentiment_score

mcp = FastMCP("CompetitiveIntelTools")


@mcp.tool()
def scrape(url: str) -> dict:
    """
    Fetches clean visible text from a URL.
    Returns content hash and flags is_stale=True if HTTP fails or content is a JS shell.
    """
    return scrape_url(url)


@mcp.tool()
def diff_pricing_tool(old_text: str, new_text: str) -> list:
    """
    Compares old pricing snapshot text against new pricing snapshot text.
    Extracts price numbers, currency symbols, and plan tier changes.
    """
    return diff_pricing(old_text, new_text)


@mcp.tool()
def sentiment_score_tool(text: str) -> dict:
    """
    Computes compound sentiment score (-1.0 to 1.0) using VADER and extracts key topics.
    """
    return sentiment_score(text)


if __name__ == "__main__":
    mcp.run(transport="stdio")
