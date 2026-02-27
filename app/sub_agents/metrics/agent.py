
# app/sub_agents/metrics/agent.py

from google.adk.agents import LlmAgent
from app.tools.bigquery_tool import query_bigquery
from app.tools.financial_tool import (
    get_pnl_comparison,
    analyze_gross_margin,
    get_revenue_variance,
    get_budget_variance
)
from app.tools.visualization_tool import get_chart_data
from .prompts import METRICS_AGENT_PROMPT

# --- define call_metrics_agent
metrics_agent = LlmAgent(
    name="metrics_agent",
    instruction=METRICS_AGENT_PROMPT,
    tools=[
        query_bigquery, 
        get_pnl_comparison,
        analyze_gross_margin,
        get_revenue_variance,
        get_budget_variance,
        get_chart_data
    ],
    model="gemini-2.5-flash"
)
