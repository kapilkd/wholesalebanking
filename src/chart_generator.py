"""
Plotly chart generation for Asset Base and Liability Base summaries.

Charts are built directly from src/db_reader.py's chart-view payloads
(VW_ASSET_*/VW_LIABILITY_* rows, already fetched by
db_reader.fetch_all_tab_data() as part of the tab pipeline) -- no DB access
and no hardcoded data here.
"""
import plotly.graph_objects as go
from typing import Any, Dict, List

# LIABILITY_MATURITY_PROFILE.MATURITY_BUCKET / LIABILITY_INTEREST_RATE_HISTORY.RATE_BUCKET
# values (scripts/seed_data.py maturity_bucket()/rate_bucket()) -- fixed display
# order, short tenor / low rate first.
MATURITY_BUCKET_ORDER = ["<1Y", "1-3Y", "3-5Y", ">5Y"]
RATE_BUCKET_ORDER = ["Fixed <5%", "Fixed 5-7%", "Fixed >7%", "Floating"]
MONTH_LABELS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class ChartGenerator:
    """Build Plotly figures from db_reader chart payloads."""

    COLORS = ['#003087', '#E31837', '#00A8E8', '#FFB81C', '#6B7280', '#10B981', '#F59E0B', '#8B5CF6']

    @staticmethod
    def _empty_chart(title: str) -> go.Figure:
        fig = go.Figure()
        fig.add_annotation(text="No data available", showarrow=False,
                            font=dict(size=14, color="#5b6478"))
        fig.update_layout(title=title, template='plotly_white', height=400,
                           xaxis=dict(visible=False), yaxis=dict(visible=False))
        return fig

    @staticmethod
    def generate_asset_charts(asset_charts: Dict[str, List[Dict[str, Any]]]) -> List[go.Figure]:
        """
        Build the 3 Asset Base charts from
        db_reader.fetch_asset_charts_data()'s payload: category_breakdown,
        quality_distribution, growth_trend.
        """
        charts = []

        rows = asset_charts.get("category_breakdown") or []
        if rows:
            categories = [r["asset_category"] for r in rows]
            values_cr = [r["category_value"] for r in rows]
            fig1 = go.Figure(data=[go.Bar(
                x=categories, y=values_cr,
                marker_color=ChartGenerator.COLORS[:len(categories)],
                text=[f'{v:.2f} CR' for v in values_cr], textposition='auto',
            )])
            fig1.update_layout(title='Asset Category Breakdown (₹ Crores)',
                                xaxis_title='Asset Categories', yaxis_title='Amount (₹ Crores)',
                                template='plotly_white', height=400, showlegend=False)
        else:
            fig1 = ChartGenerator._empty_chart('Asset Category Breakdown (₹ Crores)')
        charts.append(fig1)

        rows = asset_charts.get("quality_distribution") or []
        if rows:
            labels = [r["asset_classification"] for r in rows]
            values = [r["percentage_of_total"] for r in rows]
            fig2 = go.Figure(data=[go.Pie(
                labels=labels, values=values,
                marker_colors=ChartGenerator.COLORS[:len(labels)],
                textinfo='label+percent', hole=0.4,
            )])
            fig2.update_layout(title='Asset Quality Distribution (%)',
                                template='plotly_white', height=400, showlegend=True)
        else:
            fig2 = ChartGenerator._empty_chart('Asset Quality Distribution (%)')
        charts.append(fig2)

        rows = asset_charts.get("growth_trend") or []
        if rows:
            x_labels = [f"{MONTH_LABELS[int(r['trend_month'])]} {int(r['trend_year'])}" for r in rows]
            values_cr = [r["total_asset_value"] for r in rows]
            fig3 = go.Figure(data=[go.Scatter(
                x=x_labels, y=values_cr, mode='lines+markers', name='Total Assets',
                line=dict(color=ChartGenerator.COLORS[0], width=3),
                marker=dict(size=10, color=ChartGenerator.COLORS[1]),
            )])
            fig3.update_layout(title='Asset Growth Trend (₹ Crores)',
                                xaxis_title='Month', yaxis_title='Total Assets (₹ Crores)',
                                template='plotly_white', height=400, showlegend=False)
        else:
            fig3 = ChartGenerator._empty_chart('Asset Growth Trend (₹ Crores)')
        charts.append(fig3)

        return charts

    @staticmethod
    def generate_liability_charts(liability_charts: Dict[str, List[Dict[str, Any]]]) -> List[go.Figure]:
        """
        Build the 3 Liability Base charts from
        db_reader.fetch_liability_charts_data()'s payload: category_breakdown,
        maturity_profile, rate_exposure.
        """
        charts = []

        rows = liability_charts.get("category_breakdown") or []
        if rows:
            categories = [r["liability_category"] for r in rows]
            values_cr = [r["category_value"] for r in rows]
            fig1 = go.Figure(data=[go.Bar(
                y=categories, x=values_cr, orientation='h',
                marker_color=ChartGenerator.COLORS[:len(categories)],
                text=[f'{v:.2f} CR' for v in values_cr], textposition='auto',
            )])
            fig1.update_layout(title='Liability Category Breakdown (₹ Crores)',
                                xaxis_title='Amount (₹ Crores)', yaxis_title='Liability Categories',
                                template='plotly_white', height=400, showlegend=False)
        else:
            fig1 = ChartGenerator._empty_chart('Liability Category Breakdown (₹ Crores)')
        charts.append(fig1)

        # Stacked bar: one series per liability category actually present for
        # this client, x-axis = maturity buckets in short -> long tenor order.
        rows = liability_charts.get("maturity_profile") or []
        if rows:
            categories = sorted({r["liability_category"] for r in rows})
            by_category = {cat: {} for cat in categories}
            for r in rows:
                by_category[r["liability_category"]][r["maturity_bucket"]] = r["bucket_total"]
            present_buckets = {r["maturity_bucket"] for r in rows}
            buckets = [b for b in MATURITY_BUCKET_ORDER if b in present_buckets]
            buckets += [b for b in sorted(present_buckets) if b not in MATURITY_BUCKET_ORDER]
            fig2 = go.Figure(data=[
                go.Bar(name=cat, x=buckets,
                       y=[by_category[cat].get(b, 0.0) for b in buckets],
                       marker_color=ChartGenerator.COLORS[i % len(ChartGenerator.COLORS)])
                for i, cat in enumerate(categories)
            ])
            fig2.update_layout(title='Liability Maturity Profile (₹ Crores)',
                                xaxis_title='Maturity Bucket', yaxis_title='Amount (₹ Crores)',
                                barmode='stack', template='plotly_white', height=400, showlegend=True)
        else:
            fig2 = ChartGenerator._empty_chart('Liability Maturity Profile (₹ Crores)')
        charts.append(fig2)

        rows = liability_charts.get("rate_exposure") or []
        if rows:
            by_bucket = {r["rate_bucket"]: r["bucket_value"] for r in rows}
            buckets = [b for b in RATE_BUCKET_ORDER if b in by_bucket]
            buckets += [b for b in sorted(by_bucket) if b not in RATE_BUCKET_ORDER]
            values_cr = [by_bucket[b] for b in buckets]
            fig3 = go.Figure(data=[go.Bar(
                x=buckets, y=values_cr,
                marker_color=ChartGenerator.COLORS[:len(buckets)],
                text=[f'{v:.2f} CR' for v in values_cr], textposition='auto',
            )])
            fig3.update_layout(title='Interest Rate Exposure (₹ Crores)',
                                xaxis_title='Interest Rate Buckets', yaxis_title='Amount (₹ Crores)',
                                template='plotly_white', height=400, showlegend=False)
        else:
            fig3 = ChartGenerator._empty_chart('Interest Rate Exposure (₹ Crores)')
        charts.append(fig3)

        return charts
