"""
Multi-Agent LangGraph system for narrating client summaries from database data.

Implements the tab-rendering pipeline from CLAUDE.md:

    SQL fetch (src/db_reader.py)  ->  LLM narration (this module)

The LLM here is a narrator, not a data source: every agent receives only
already-fetched rows from the tab's database view as JSON context, runs at
low temperature, and is instructed to never state a fact that isn't in the
payload. Unknown client codes raise in db_reader before any LLM call.

The six tab agents are independent, so the graph fans them out in parallel
from START (each node returns a partial state update — required by LangGraph
for concurrent branches, and the parallelization lever that replaces the old
sequential 5-call chain).
"""
import json
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage

import datetime

from config.langchain_config import get_llm
from src import db_reader
from src import summary_cache
from src.rules_layer import apply_rules

# Narration must be deterministic prose over fixed numbers, not creative
# writing — CLAUDE.md prescribes 0.1-0.2 for this path.
NARRATION_TEMPERATURE = 0.1

NARRATOR_SYSTEM_PROMPT = """You are a banking data narrator for ABC Bank Wholesale Banking Department.
You turn structured rows retrieved from the bank's database into short, professional prose summaries for relationship managers.

STRICT GROUNDING RULES:
- Use ONLY the facts and figures present in the provided JSON. Every number, name, date, and product you mention must appear in the data.
- NEVER invent, estimate, extrapolate, or fill in missing values.
- If a field is null or missing, simply omit it from the narrative.
- If the data contains no records (empty list, all-zero totals), state that plainly in one sentence instead of describing activity that isn't there.
- Monetary values are stored in INR Crores: format them as ₹**XX.XX CR**.
- Format every number, percentage, and date as bold markdown (**...**).
- Write 1-3 short paragraphs of flowing prose; use a list only when the data itself is a list of events.
- If the payload contains a "highlights" list, each entry was computed by a
  deterministic business rule from this same data: weave every highlight's
  message into the narrative (rephrased naturally, numbers unchanged), and
  never contradict one."""


class SummaryState(TypedDict):
    """State for the multi-agent summary narration"""
    client_code: str
    tab_data: dict          # db_reader.fetch_all_tab_data() payload
    rules: dict             # rules_layer.apply_rules() output
    cms_summary: str
    rm_summary: str
    asset_summary: str
    liability_summary: str
    product_holding_summary: str
    rm_discussion_summary: str


class MultiAgentSummaryGenerator:
    """LangGraph fan-out of six narration agents, one per dashboard tab."""

    def __init__(self):
        self.llm = get_llm(temperature=NARRATION_TEMPERATURE)

        workflow = StateGraph(SummaryState)
        workflow.add_node("cms_agent", self.narrate_cms_summary)
        workflow.add_node("rm_agent", self.narrate_rm_summary)
        workflow.add_node("asset_agent", self.narrate_asset_summary)
        workflow.add_node("liability_agent", self.narrate_liability_summary)
        workflow.add_node("product_agent", self.narrate_product_holding_summary)
        workflow.add_node("discussion_agent", self.narrate_rm_discussion_summary)

        for node in ("cms_agent", "rm_agent", "asset_agent", "liability_agent",
                     "product_agent", "discussion_agent"):
            workflow.add_edge(START, node)
            workflow.add_edge(node, END)

        self._graph = workflow.compile()

    # ------------------------------------------------------------------ #
    # Shared narration call
    # ------------------------------------------------------------------ #

    def _narrate(self, tab: str, coverage: str, payload: dict) -> str:
        """One grounded narration call: tab context + JSON rows -> prose."""
        messages = [
            SystemMessage(content=NARRATOR_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Tab: {tab}\n"
                f"Write the summary covering {coverage}.\n\n"
                "Database rows retrieved for this client (JSON):\n"
                f"{json.dumps(payload, indent=2, default=str, ensure_ascii=False)}"
            )),
        ]
        return self.llm.invoke(messages).content

    # ------------------------------------------------------------------ #
    # Tab agents — each returns a partial state update (parallel-safe)
    # ------------------------------------------------------------------ #

    def narrate_cms_summary(self, state: SummaryState) -> dict:
        """CMS tab: VW_CMS_SUMMARY — customer profile, contacts, touchpoints."""
        payload = {
            "cms_profile": state["tab_data"]["cms_summary"],
            "highlights": state["rules"]["highlights"]["cms"],
        }
        return {"cms_summary": self._narrate(
            tab="Customer Management (CMS)",
            coverage=(
                "who the client is (name, segment, group/parent company, "
                "relationship-since date, annual turnover), their credit "
                "rating with agency and date, the primary contact person and "
                "registered address, current balances and active account "
                "count, the most recent communication/call/meeting dates, and "
                "document repository counts including any expired documents"
            ),
            payload=payload,
        )}

    def narrate_rm_summary(self, state: SummaryState) -> dict:
        """RM Details tab: VW_RM_DETAILS_SUMMARY + client master row."""
        payload = {
            "client": state["tab_data"]["client"],
            "rm_details": state["tab_data"]["rm_details_summary"],
            "highlights": state["rules"]["highlights"]["rm_details"],
        }
        return {"rm_summary": self._narrate(
            tab="Relationship Manager Details & CRM Interactions",
            coverage=(
                "who manages the client (RM name, designation, contact, branch), "
                "how actively the relationship is covered (interaction, call and "
                "meeting counts, last-interaction dates), and any escalations or "
                "feedback figures present"
            ),
            payload=payload,
        )}

    def narrate_asset_summary(self, state: SummaryState) -> dict:
        """Asset Base tab: VW_ASSET_BASE_SUMMARY + the three asset chart views."""
        payload = {
            "asset_summary": state["tab_data"]["asset_base_summary"],
            # growth_trend windowed by the rules layer for narration; the
            # chart itself still renders the untouched fetch.
            "asset_charts": {
                **state["tab_data"]["asset_charts"],
                "growth_trend": state["rules"]["narration_overrides"]["asset_growth_trend"],
            },
            "highlights": state["rules"]["highlights"]["asset"],
        }
        return {"asset_summary": self._narrate(
            tab="Asset Base",
            coverage=(
                "total asset value and account count, the category breakdown, "
                "asset quality (Standard/Sub-Standard/Doubtful/Loss split), "
                "sanctioned vs utilized limits, collateral cover, covenant "
                "breaches, and the growth trend across the monthly history"
            ),
            payload=payload,
        )}

    def narrate_liability_summary(self, state: SummaryState) -> dict:
        """Liability Base tab: VW_LIABILITY_BASE_SUMMARY + liability chart views."""
        payload = {
            "liability_summary": state["tab_data"]["liability_base_summary"],
            "liability_charts": state["tab_data"]["liability_charts"],
            "highlights": state["rules"]["highlights"]["liability"],
        }
        return {"liability_summary": self._narrate(
            tab="Liability Base",
            coverage=(
                "total liability value and account count, the category "
                "breakdown, average interest rate and concentration risk, the "
                "maturity profile buckets, and the interest-rate exposure split"
            ),
            payload=payload,
        )}

    def narrate_product_holding_summary(self, state: SummaryState) -> dict:
        """Product Holdings tab: VW_PRODUCT_HOLDINGS_SUMMARY."""
        payload = {
            "client": state["tab_data"]["client"],
            "product_holdings": state["tab_data"]["product_holdings_summary"],
            "highlights": state["rules"]["highlights"]["product"],
        }
        return {"product_holding_summary": self._narrate(
            tab="Overall Banking & Product Holdings",
            coverage=(
                "how many products the client holds and their total value, "
                "utilization figures, fee income, relationship depth, and any "
                "cross-sell opportunity counts present"
            ),
            payload=payload,
        )}

    def narrate_rm_discussion_summary(self, state: SummaryState) -> dict:
        """RM Discussion tab: VW_RM_DISCUSSION_SUMMARY sessions, newest first."""
        payload = {
            # Windowed + capped by the rules layer (narration input only).
            "discussion_sessions": state["rules"]["narration_overrides"]["rm_discussion_sessions"],
            "highlights": state["rules"]["highlights"]["discussion"],
        }
        return {"rm_discussion_summary": self._narrate(
            tab="RM-Client Discussions",
            coverage=(
                "the recent discussion sessions in order (date, mode, topics/"
                "needs/solutions counts), what was concluded (outcome "
                "summaries), accepted solutions, open follow-up actions, and "
                "upcoming next steps / review dates"
            ),
            payload=payload,
        )}

    # ------------------------------------------------------------------ #
    # Entry point
    # ------------------------------------------------------------------ #

    def generate_all_summaries(self, client_code: str,
                               use_cache: bool = True) -> dict:
        """
        Fetch the client's data (parallel SQL, src/db_reader.py) and narrate
        all 6 tab summaries (parallel LLM calls via the LangGraph fan-out).

        Results are cached in-process per client (src/summary_cache.py,
        TTL-bounded) so repeat lookups skip the fetch+narration cost.

        Args:
            client_code: APR_CLIENT_CODE to summarize
            use_cache: pass False to force a fresh fetch+narration (the
                UI's Refresh action also invalidates the stored entry)

        Returns:
            dict: the 6 summaries (same keys the UI already renders) plus
            "tab_data" — the raw fetched payload, so downstream consumers
            (charts, rules) don't have to refetch.

        Raises:
            ValueError: if the code doesn't exist in CLIENT_MASTER — the
            caller shows not-found; nothing ever reaches the LLM.
        """
        if use_cache:
            cached = summary_cache.get(client_code)
            if cached is not None:
                return cached

        tab_data = db_reader.fetch_all_tab_data(client_code)
        rules = apply_rules(tab_data)

        initial_state: SummaryState = {
            "client_code": client_code,
            "tab_data": tab_data,
            "rules": rules,
            "cms_summary": "",
            "rm_summary": "",
            "asset_summary": "",
            "liability_summary": "",
            "product_holding_summary": "",
            "rm_discussion_summary": "",
        }

        final_state = self._graph.invoke(initial_state)

        result = {
            "cms_summary": final_state["cms_summary"],
            "rm_summary": final_state["rm_summary"],
            "asset_summary": final_state["asset_summary"],
            "liability_summary": final_state["liability_summary"],
            "product_holding_summary": final_state["product_holding_summary"],
            "rm_discussion_summary": final_state["rm_discussion_summary"],
            "tab_data": tab_data,
            "rules": rules,
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        summary_cache.put(client_code, result)
        return result
