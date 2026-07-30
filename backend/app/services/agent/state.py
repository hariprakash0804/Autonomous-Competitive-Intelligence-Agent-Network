from typing import TypedDict, List, Dict, Any, Optional


class AgentState(TypedDict):
    competitor_id: str
    competitor_name: str
    urls: List[str]
    raw_pages: List[Dict[str, Any]]
    prev_snapshot: Optional[Dict[str, Any]]
    diffs: List[Dict[str, Any]]
    sentiment_results: List[Dict[str, Any]]
    report_draft: str
    model_used: Optional[str]
    retry_count: int
    reflection_triggered: bool
    is_incomplete: bool
    agent_run_id: Optional[str]
    status: str
