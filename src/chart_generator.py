"""
Plotly chart generation for Asset Base and Liability Base summaries
"""
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import List, Dict


class ChartGenerator:
    """Generate Plotly charts for financial summaries"""
    
    # Color palette for charts
    COLORS = ['#003087', '#E31837', '#00A8E8', '#FFB81C', '#6B7280', '#10B981', '#F59E0B', '#8B5CF6']
    
    @staticmethod
    def generate_asset_charts(client_code: str) -> List[go.Figure]:
        """
        Generate 2-3 charts for Asset Base summary
        
        Returns:
            List of Plotly figure objects
        """
        charts = []
        
        # Chart 1: Asset Category Breakdown (Bar Chart)
        categories = ['Corporate Loans', 'Trade Finance', 'Investments', 'Securities', 'Cash & Equivalents']
        values_cr = [245.5, 128.3, 95.7, 67.2, 42.8]  # Values in Crores
        
        fig1 = go.Figure(data=[
            go.Bar(
                x=categories,
                y=values_cr,
                marker_color=ChartGenerator.COLORS[:len(categories)],
                text=[f'{val:.2f} CR' for val in values_cr],
                textposition='auto',
            )
        ])
        fig1.update_layout(
            title='Asset Category Breakdown (₹ Crores)',
            xaxis_title='Asset Categories',
            yaxis_title='Amount (₹ Crores)',
            template='plotly_white',
            height=400,
            showlegend=False
        )
        charts.append(fig1)
        
        # Chart 2: Asset Quality Distribution (Pie Chart)
        quality_labels = ['Standard', 'Sub-Standard', 'Doubtful', 'Loss']
        quality_values = [78.5, 12.3, 6.8, 2.4]  # Percentages
        
        fig2 = go.Figure(data=[
            go.Pie(
                labels=quality_labels,
                values=quality_values,
                marker_colors=ChartGenerator.COLORS[:4],
                textinfo='label+percent',
                hole=0.4
            )
        ])
        fig2.update_layout(
            title='Asset Quality Distribution (%)',
            template='plotly_white',
            height=400,
            showlegend=True
        )
        charts.append(fig2)
        
        # Chart 3: Asset Trend Over Time (Line Chart)
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
        total_assets_cr = [520.5, 535.2, 548.7, 562.3, 575.8, 579.5]
        
        fig3 = go.Figure(data=[
            go.Scatter(
                x=months,
                y=total_assets_cr,
                mode='lines+markers',
                name='Total Assets',
                line=dict(color=ChartGenerator.COLORS[0], width=3),
                marker=dict(size=10, color=ChartGenerator.COLORS[1])
            )
        ])
        fig3.update_layout(
            title='Asset Growth Trend (₹ Crores)',
            xaxis_title='Month',
            yaxis_title='Total Assets (₹ Crores)',
            template='plotly_white',
            height=400,
            showlegend=False
        )
        charts.append(fig3)
        
        return charts
    
    @staticmethod
    def generate_liability_charts(client_code: str) -> List[go.Figure]:
        """
        Generate 2-3 charts for Liability Base summary
        
        Returns:
            List of Plotly figure objects
        """
        charts = []
        
        # Chart 1: Liability Category Breakdown (Horizontal Bar Chart)
        categories = ['Term Deposits', 'Current Accounts', 'Borrowings', 'Bonds', 'Other Liabilities']
        values_cr = [185.6, 142.3, 98.7, 75.4, 38.2]  # Values in Crores
        
        fig1 = go.Figure(data=[
            go.Bar(
                y=categories,
                x=values_cr,
                orientation='h',
                marker_color=ChartGenerator.COLORS[:len(categories)],
                text=[f'{val:.2f} CR' for val in values_cr],
                textposition='auto',
            )
        ])
        fig1.update_layout(
            title='Liability Category Breakdown (₹ Crores)',
            xaxis_title='Amount (₹ Crores)',
            yaxis_title='Liability Categories',
            template='plotly_white',
            height=400,
            showlegend=False
        )
        charts.append(fig1)
        
        # Chart 2: Maturity Profile (Stacked Bar Chart)
        maturity_periods = ['< 1 Year', '1-3 Years', '3-5 Years', '> 5 Years']
        deposits = [85.2, 65.3, 25.1, 10.0]
        borrowings = [45.6, 30.2, 15.5, 7.4]
        bonds = [20.3, 35.1, 15.2, 4.8]
        
        fig2 = go.Figure(data=[
            go.Bar(name='Deposits', x=maturity_periods, y=deposits, marker_color=ChartGenerator.COLORS[0]),
            go.Bar(name='Borrowings', x=maturity_periods, y=borrowings, marker_color=ChartGenerator.COLORS[1]),
            go.Bar(name='Bonds', x=maturity_periods, y=bonds, marker_color=ChartGenerator.COLORS[2])
        ])
        fig2.update_layout(
            title='Liability Maturity Profile (₹ Crores)',
            xaxis_title='Maturity Period',
            yaxis_title='Amount (₹ Crores)',
            barmode='stack',
            template='plotly_white',
            height=400,
            showlegend=True
        )
        charts.append(fig2)
        
        # Chart 3: Interest Rate Exposure (Bar Chart)
        rate_buckets = ['Fixed < 5%', 'Fixed 5-7%', 'Fixed > 7%', 'Floating']
        exposure_cr = [125.4, 180.6, 95.2, 139.0]
        
        fig3 = go.Figure(data=[
            go.Bar(
                x=rate_buckets,
                y=exposure_cr,
                marker_color=ChartGenerator.COLORS[:4],
                text=[f'{val:.2f} CR' for val in exposure_cr],
                textposition='auto',
            )
        ])
        fig3.update_layout(
            title='Interest Rate Exposure (₹ Crores)',
            xaxis_title='Interest Rate Buckets',
            yaxis_title='Amount (₹ Crores)',
            template='plotly_white',
            height=400,
            showlegend=False
        )
        charts.append(fig3)
        
        return charts
