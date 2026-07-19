"""
Deterministic rules layer between SQL fetch and LLM narration.

The middle step of CLAUDE.md's tab pipeline:

    CREATE VIEW per tab  ->  RULES LAYER (this module)  ->  LLM narration

Business logic about WHAT deserves attention lives here — in auditable,
threshold-driven Python — not in an LLM prompt. apply_rules() takes the
db_reader.fetch_all_tab_data() payload and returns:

- highlights: per-tab lists of {rule, severity, message} findings, each
  computed from the fetched rows with the thresholds in RULES_CONFIG. The
  narrator is instructed to weave these in, so what gets emphasized is a
  deterministic decision, reproducible for any given data.
- narration_overrides: pre-filtered row sets for narration (date windows /
  top-N), e.g. discussion sessions capped to a recency window. Chart/UI
  payloads are NOT touched — the overrides apply to narration input only.

Everything here is pure computation on already-fetched data: no DB access,
no LLM, no side effects.
"""
import datetime
from typing import Any, Dict, List, Optional, Tuple

# All thresholds in one place — tune per business sign-off, not per prompt.
RULES_CONFIG = {
    # Relationship hygiene
    "stale_contact_days": 60,            # no touchpoint in N days -> warning
    "expired_document_warn_at": 1,       # >= N expired documents -> warning
    "open_escalation_warn_at": 1,        # >= N open escalations -> warning
    "low_feedback_warn_below": 3.0,      # avg rating below N (of 5) -> warning
    # Asset risk
    "npa_share_warn_pct": 5.0,           # non-Standard share of asset value
    "limit_utilization_warn_pct": 80.0,  # utilized / sanctioned limits
    "covenant_breach_warn_at": 1,
    # Liability risk
    "concentration_risk_warn_pct": 40.0,
    "near_term_maturity_warn_pct": 50.0,  # share of value maturing < 1Y
    # Product depth
    "product_utilization_warn_pct": 80.0,
    "cross_sell_info_at": 1,             # >= N open opportunities -> info
    # Narration windows
    "growth_trend_months": 12,           # months of history the narrator sees
    "discussion_window_days": 180,       # discussions older than this dropped
    "discussion_max_sessions": 10,       # cap after the window filter
}


def _highlight(rule: str, severity: str, message: str) -> Dict[str, str]:
    return {"rule": rule, "severity": severity, "message": message}


def _parse_date(value: Any) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _days_since(value: Any, today: datetime.date) -> Optional[int]:
    parsed = _parse_date(value)
    return (today - parsed).days if parsed else None


def _pct(part: float, whole: float) -> Optional[float]:
    if not whole:
        return None
    return round(100.0 * part / whole, 1)


# --------------------------------------------------------------------------- #
# Per-tab rules
# --------------------------------------------------------------------------- #

def cms_rules(cms: Optional[Dict], today: datetime.date) -> List[Dict]:
    if not cms:
        return []
    out = []
    expired = cms.get("expired_document_count") or 0
    if expired >= RULES_CONFIG["expired_document_warn_at"]:
        out.append(_highlight(
            "CMS_EXPIRED_DOCUMENTS", "warning",
            f"{int(expired)} of {int(cms.get('document_count') or 0)} documents "
            "in the repository have expired and need renewal."))
    touch_days = [d for d in (
        _days_since(cms.get("last_communication_date"), today),
        _days_since(cms.get("last_call_date"), today),
        _days_since(cms.get("last_meeting_date"), today),
    ) if d is not None]
    if touch_days and min(touch_days) > RULES_CONFIG["stale_contact_days"]:
        out.append(_highlight(
            "CMS_STALE_CONTACT", "warning",
            f"No touchpoint (communication, call, or meeting) in the last "
            f"{min(touch_days)} days — beyond the {RULES_CONFIG['stale_contact_days']}-day standard."))
    if (cms.get("client_status") or "").lower() == "dormant":
        out.append(_highlight(
            "CMS_DORMANT_CLIENT", "warning", "Client status is Dormant."))
    return out


def rm_details_rules(rm: Optional[Dict], today: datetime.date) -> List[Dict]:
    if not rm:
        return []
    out = []
    escalations = rm.get("open_escalation_count") or 0
    if escalations >= RULES_CONFIG["open_escalation_warn_at"]:
        out.append(_highlight(
            "RM_OPEN_ESCALATIONS", "warning",
            f"{int(escalations)} escalation(s) are currently open."))
    days = _days_since(rm.get("last_interaction_date"), today)
    if days is not None and days > RULES_CONFIG["stale_contact_days"]:
        out.append(_highlight(
            "RM_STALE_INTERACTION", "warning",
            f"Last RM interaction was {days} days ago — beyond the "
            f"{RULES_CONFIG['stale_contact_days']}-day standard."))
    rating = rm.get("average_feedback_rating")
    if rating is not None and rating < RULES_CONFIG["low_feedback_warn_below"]:
        out.append(_highlight(
            "RM_LOW_FEEDBACK", "warning",
            f"Average client feedback rating is {rating:.1f}/5, below the "
            f"{RULES_CONFIG['low_feedback_warn_below']:.1f} threshold."))
    return out


def asset_rules(asset: Optional[Dict], charts: Optional[Dict],
                ) -> Tuple[List[Dict], List[Dict]]:
    """Returns (highlights, growth_trend rows trimmed for narration)."""
    out = []
    trend = list((charts or {}).get("growth_trend") or [])
    trimmed_trend = trend[-RULES_CONFIG["growth_trend_months"]:]
    if not asset:
        return out, trimmed_trend

    total = asset.get("total_asset_value") or 0
    non_standard = sum(asset.get(k) or 0 for k in
                       ("sub_standard_value", "doubtful_value", "loss_value"))
    npa_share = _pct(non_standard, total)
    if npa_share is not None and npa_share >= RULES_CONFIG["npa_share_warn_pct"]:
        out.append(_highlight(
            "ASSET_NPA_SHARE", "warning",
            f"{npa_share}% of asset value (₹{non_standard:.2f} CR of ₹{total:.2f} CR) "
            f"is classified below Standard — above the {RULES_CONFIG['npa_share_warn_pct']}% threshold."))

    utilization = _pct(asset.get("total_utilized_limit") or 0,
                       asset.get("total_sanctioned_limit") or 0)
    if utilization is not None and utilization >= RULES_CONFIG["limit_utilization_warn_pct"]:
        out.append(_highlight(
            "ASSET_LIMIT_UTILIZATION", "warning",
            f"Sanctioned limits are {utilization}% utilized — above the "
            f"{RULES_CONFIG['limit_utilization_warn_pct']}% threshold."))

    breaches = asset.get("covenant_breach_count") or 0
    if breaches >= RULES_CONFIG["covenant_breach_warn_at"]:
        out.append(_highlight(
            "ASSET_COVENANT_BREACH", "warning",
            f"{int(breaches)} covenant(s) are in breach."))

    if len(trimmed_trend) >= 2:
        first = trimmed_trend[0].get("total_asset_value") or 0
        last = trimmed_trend[-1].get("total_asset_value") or 0
        growth = _pct(last - first, first)
        if growth is not None:
            direction = "grew" if growth >= 0 else "declined"
            out.append(_highlight(
                "ASSET_TREND", "info",
                f"Total assets {direction} {abs(growth)}% over the last "
                f"{len(trimmed_trend)} months (₹{first:.2f} CR → ₹{last:.2f} CR)."))
    return out, trimmed_trend


def liability_rules(liab: Optional[Dict], charts: Optional[Dict]) -> List[Dict]:
    if not liab:
        return []
    out = []
    concentration = liab.get("average_concentration_risk_percentage")
    if concentration is not None and concentration >= RULES_CONFIG["concentration_risk_warn_pct"]:
        out.append(_highlight(
            "LIABILITY_CONCENTRATION", "warning",
            f"Average concentration risk is {concentration:.1f}% — above the "
            f"{RULES_CONFIG['concentration_risk_warn_pct']}% threshold."))
    maturity_rows = (charts or {}).get("maturity_profile") or []
    total = sum(r.get("bucket_total") or 0 for r in maturity_rows)
    near = sum(r.get("bucket_total") or 0 for r in maturity_rows
               if r.get("maturity_bucket") == "<1Y")
    near_share = _pct(near, total)
    if near_share is not None and near_share >= RULES_CONFIG["near_term_maturity_warn_pct"]:
        out.append(_highlight(
            "LIABILITY_NEAR_TERM_MATURITY", "info",
            f"{near_share}% of maturing liability value (₹{near:.2f} CR) falls "
            "due within 1 year — renewal conversations are time-sensitive."))
    return out


def product_rules(product: Optional[Dict]) -> List[Dict]:
    if not product:
        return []
    out = []
    utilization = product.get("avg_utilization_percentage")
    if utilization is not None and utilization >= RULES_CONFIG["product_utilization_warn_pct"]:
        out.append(_highlight(
            "PRODUCT_HIGH_UTILIZATION", "info",
            f"Average product utilization is {utilization:.1f}% — above "
            f"{RULES_CONFIG['product_utilization_warn_pct']}%, an enhancement conversation may be due."))
    cross_sell = product.get("open_cross_sell_opportunity_count") or 0
    if cross_sell >= RULES_CONFIG["cross_sell_info_at"]:
        potential = product.get("open_cross_sell_potential_value") or 0
        out.append(_highlight(
            "PRODUCT_CROSS_SELL", "info",
            f"{int(cross_sell)} open cross-sell opportunit(ies) worth "
            f"₹{potential:.2f} CR in potential value."))
    return out


def discussion_rules(sessions: Optional[List[Dict]], today: datetime.date,
                     ) -> Tuple[List[Dict], List[Dict]]:
    """Returns (highlights, sessions filtered to the narration window)."""
    sessions = sessions or []
    window = RULES_CONFIG["discussion_window_days"]
    cap = RULES_CONFIG["discussion_max_sessions"]
    recent = [s for s in sessions
              if (_days_since(s.get("discussion_date"), today) or 0) <= window]

    out = []
    if recent:
        kept = recent[:cap]
        dropped = len(sessions) - len(kept)
        if dropped > 0:
            out.append(_highlight(
                "DISCUSSION_WINDOW", "info",
                f"Showing the {len(kept)} discussion(s) from the last {window} days; "
                f"{dropped} older session(s) omitted."))
    elif sessions:
        # Nothing inside the window: an empty tab helps nobody, so fall back
        # to the newest few and say plainly that they're old.
        kept = sessions[:cap]
        out.append(_highlight(
            "DISCUSSION_STALE", "warning",
            f"No discussions in the last {window} days — the most recent "
            f"session was on {kept[0].get('discussion_date')}. Showing the "
            f"latest {len(kept)} older session(s)."))
    else:
        kept = []
    open_actions = sum(s.get("open_followup_action_count") or 0 for s in kept)
    if open_actions > 0:
        out.append(_highlight(
            "DISCUSSION_OPEN_FOLLOWUPS", "warning",
            f"{int(open_actions)} follow-up action(s) from recent discussions are still open."))
    return out, kept


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def apply_rules(tab_data: Dict[str, Any],
                today: Optional[datetime.date] = None) -> Dict[str, Any]:
    """
    Run every tab's rules over one fetched payload.

    Returns:
        {
          "highlights": {cms|rm_details|asset|liability|product|discussion: [...]},
          "narration_overrides": {
              "rm_discussion_sessions": [...],   # windowed + capped
              "asset_growth_trend": [...],       # last N months
          },
        }
    """
    today = today or datetime.date.today()

    asset_highlights, trimmed_trend = asset_rules(
        tab_data.get("asset_base_summary"), tab_data.get("asset_charts"))
    discussion_highlights, kept_sessions = discussion_rules(
        tab_data.get("rm_discussion_sessions"), today)

    return {
        "highlights": {
            "cms": cms_rules(tab_data.get("cms_summary"), today),
            "rm_details": rm_details_rules(tab_data.get("rm_details_summary"), today),
            "asset": asset_highlights,
            "liability": liability_rules(
                tab_data.get("liability_base_summary"), tab_data.get("liability_charts")),
            "product": product_rules(tab_data.get("product_holdings_summary")),
            "discussion": discussion_highlights,
        },
        "narration_overrides": {
            "rm_discussion_sessions": kept_sessions,
            "asset_growth_trend": trimmed_trend,
        },
    }
