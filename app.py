"""
Main Streamlit Application for Wholesale Banking Chatbot
"""
import streamlit as st
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))
sys.path.append(str(Path(__file__).parent))

from src.chatbot import WholesaleBankingChatbot
from src.utils import validate_client_code, format_client_code
from src.multi_agent_generator import MultiAgentSummaryGenerator
from src.chart_generator import ChartGenerator

# Static wholesale banking summary text
STATIC_WHOLESALE_INTRO = (
    "ABC Bank Wholesale Banking delivers comprehensive financial solutions to "
    "large-scale clients including corporations, financial institutions, government "
    "agencies, and real estate developers, providing specialized services for complex "
    "business requirements and high-value transactions."
)

FEATURES = [
    {"icon": "👤", "title": "Client Relationship Management",
     "desc": "Access detailed RM interactions, contact information, and relationship history."},
    {"icon": "💼", "title": "Asset Analysis",
     "desc": "Comprehensive asset portfolio breakdown, quality metrics, and performance trends."},
    {"icon": "📈", "title": "Liability Assessment",
     "desc": "Complete liability structure analysis, maturity profiles, and risk evaluation."},
    {"icon": "🏢", "title": "Product Holdings",
     "desc": "Detailed product portfolio review, utilization rates, and cross-selling opportunities."},
    {"icon": "💬", "title": "RM Discussions",
     "desc": "Historical conversation records, meeting notes, and action items."},
    {"icon": "✨", "title": "Financial Insights",
     "desc": "Real-time analysis and recommendations based on client data."},
    {"icon": "🛎️", "title": "Service Support",
     "desc": "Answers to queries about ABC Bank's wholesale banking products and services."},
]

# Page configuration
st.set_page_config(
    page_title="ABC Bank | Wholesale Banking",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "chatbot" not in st.session_state:
    st.session_state.chatbot = None
if "client_code" not in st.session_state:
    st.session_state.client_code = None
if "code_type" not in st.session_state:
    st.session_state.code_type = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "client_summaries" not in st.session_state:
    st.session_state.client_summaries = None
if "summaries_generated" not in st.session_state:
    st.session_state.summaries_generated = False

# ----------------------------------------------------------------------------
# Design system — ABC Bank brand (navy + red) on a modern fintech shell
# ----------------------------------------------------------------------------
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        --navy: #003087;
        --navy-light: #0d4bb8;
        --navy-dark: #001f5c;
        --red: #E31837;
        --red-dark: #B01029;
        --blue-accent: #00A8E8;
        --gold-accent: #FFB81C;
        --surface: #ffffff;
        --bg: #f4f6fb;
        --border: #e6e9f2;
        --text-primary: #1a1f36;
        --text-secondary: #5b6478;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .stApp {
        background: var(--bg);
    }

    #MainMenu, footer {visibility: hidden;}

    /* ---------- Native Streamlit header / deploy button ---------- */
    /* Hide only the hamburger menu and deploy button. The sidebar's
       re-expand button (stExpandSidebarButton) lives inside the same
       stToolbar container, so stToolbar itself must stay visible --
       display:none on the whole toolbar/header made it impossible to
       bring a collapsed sidebar back (verified against the installed
       Streamlit build's testids: stMainMenu, stAppDeployButton,
       stExpandSidebarButton). */
    header[data-testid="stHeader"] {
        background: transparent;
        box-shadow: none;
    }
    [data-testid="stMainMenu"],
    [data-testid="stAppDeployButton"] {
        display: none;
    }
    [data-testid="stExpandSidebarButton"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
    }
    .block-container, [data-testid="stAppViewBlockContainer"] {
        padding-top: 0.8rem !important;
    }

    /* ---------- Hero banner (compact single-line header replacement) ---------- */
    .hero-banner {
        background: linear-gradient(120deg, var(--navy) 0%, var(--navy-light) 65%, var(--navy) 100%);
        border-radius: 12px;
        padding: 0.55rem 1.1rem;
        margin-bottom: 1.2rem;
        position: relative;
        overflow: hidden;
        box-shadow: 0 6px 16px -8px rgba(0, 48, 135, 0.45);
    }
    .hero-banner::after {
        content: "";
        position: absolute;
        top: 0; right: 0;
        width: 6px; height: 100%;
        background: linear-gradient(180deg, var(--red) 0%, var(--gold-accent) 100%);
    }
    .hero-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.8rem;
        flex-wrap: wrap;
    }
    .hero-title {
        font-size: 1.05rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: 0.2px;
        margin: 0;
        white-space: nowrap;
    }
    .hero-subtitle {
        font-size: 0.72rem;
        color: rgba(255,255,255,0.75);
        margin: 0.1rem 0 0 0;
        font-weight: 400;
        line-height: 1.3;
    }
    .hero-badge {
        display: inline-block;
        background: rgba(255,255,255,0.14);
        border: 1px solid rgba(255,255,255,0.25);
        color: #fff;
        padding: 0.2rem 0.7rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.3px;
        white-space: nowrap;
    }

    /* ---------- Section titles ---------- */
    .section-title {
        font-size: 1.35rem;
        font-weight: 700;
        color: var(--navy);
        display: flex;
        align-items: center;
        gap: 0.55rem;
        margin: 1.6rem 0 1rem 0;
    }
    .section-icon { font-size: 1.5rem; }

    /* ---------- Cards ---------- */
    .card {
        background: var(--surface);
        padding: 1.5rem;
        border-radius: 14px;
        box-shadow: 0 1px 3px rgba(16, 24, 64, 0.06), 0 1px 2px rgba(16,24,64,0.04);
        border: 1px solid var(--border);
        margin-bottom: 1.2rem;
    }
    .summary-text {
        font-size: 1.02rem;
        line-height: 1.85;
        color: var(--text-primary);
        padding: 1.4rem 1.6rem;
        background: var(--surface);
        border-radius: 14px;
        border-left: 4px solid var(--red);
        box-shadow: 0 1px 3px rgba(16, 24, 64, 0.06);
        margin-bottom: 1.2rem;
    }
    .summary-text strong { color: var(--navy); }

    /* ---------- Feature grid (empty state) ---------- */
    .feature-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 1.3rem 1.3rem 1.1rem 1.3rem;
        height: 100%;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        box-shadow: 0 1px 2px rgba(16,24,64,0.04);
    }
    .feature-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 22px -8px rgba(0, 48, 135, 0.25);
        border-color: var(--blue-accent);
    }
    .feature-icon {
        font-size: 1.6rem;
        background: linear-gradient(135deg, var(--navy) 0%, var(--blue-accent) 100%);
        width: 46px; height: 46px;
        border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        margin-bottom: 0.7rem;
    }
    .feature-title {
        font-weight: 700;
        color: var(--navy);
        font-size: 1.02rem;
        margin-bottom: 0.35rem;
    }
    .feature-desc {
        font-size: 0.9rem;
        color: var(--text-secondary);
        line-height: 1.55;
    }
    .cta-hint {
        text-align: center;
        color: var(--text-secondary);
        font-size: 0.95rem;
        padding: 0.9rem;
        border: 1px dashed var(--border);
        border-radius: 12px;
        margin-top: 1.4rem;
        background: rgba(0,48,135,0.03);
    }

    /* ---------- Status chips ---------- */
    .chip-row { display: flex; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 1rem; }
    .chip {
        display: inline-flex; align-items: center; gap: 0.4rem;
        padding: 0.4rem 0.9rem;
        border-radius: 999px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .chip-code { background: rgba(0,48,135,0.08); color: var(--navy); border: 1px solid rgba(0,48,135,0.18); }
    .chip-type { background: rgba(0,168,232,0.1); color: #0077a3; border: 1px solid rgba(0,168,232,0.25); }
    .chip-status { background: rgba(16,185,129,0.1); color: #0a8f63; border: 1px solid rgba(16,185,129,0.25); }
    .chip-dot { width: 7px; height: 7px; border-radius: 50%; background: #10B981; display: inline-block; }

    /* ---------- Tabs ---------- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: var(--surface);
        padding: 6px;
        border-radius: 12px;
        border: 1px solid var(--border);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 9px;
        padding: 0.55rem 1rem;
        font-weight: 600;
        color: var(--text-secondary);
    }
    .stTabs [aria-selected="true"] {
        background: var(--navy) !important;
        color: #ffffff !important;
    }
    .tab-section-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--navy);
        margin: 0.4rem 0 1rem 0;
        display: flex; align-items: center; gap: 0.5rem;
    }

    /* ---------- Buttons ---------- */
    .stButton > button {
        background: var(--red);
        color: white;
        border: none;
        border-radius: 9px;
        font-weight: 600;
        transition: background 0.15s ease;
    }
    .stButton > button:hover {
        background: var(--red-dark);
        color: white;
    }

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--navy-dark) 0%, var(--navy) 100%);
    }
    section[data-testid="stSidebar"] * {
        color: #eef1fa;
    }
    section[data-testid="stSidebar"] input {
        color: var(--text-primary) !important;
    }
    .sidebar-project-name {
        font-size: 0.95rem;
        font-weight: 800;
        letter-spacing: 1.5px;
        color: var(--gold-accent);
        text-transform: uppercase;
        margin: 0 0 0.5rem 0;
    }
    .sidebar-brand {
        display: flex; align-items: center; gap: 0.6rem;
        margin-bottom: 0.2rem;
    }
    .sidebar-brand-icon { font-size: 1.9rem; }
    .sidebar-brand-name { font-size: 1.15rem; font-weight: 800; color: #fff; margin: 0; }
    .sidebar-brand-sub { font-size: 0.8rem; color: rgba(255,255,255,0.65); margin-top: -0.2rem; }
    .sidebar-section-label {
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.6px;
        text-transform: uppercase;
        color: rgba(255,255,255,0.55);
        margin: 1.3rem 0 0.5rem 0;
    }
    .sidebar-status-card {
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.18);
        border-radius: 12px;
        padding: 0.9rem 1rem;
        margin: 0.8rem 0;
    }
    .sidebar-status-card .code { font-size: 1.05rem; font-weight: 700; color: #fff; }
    .sidebar-status-card .type { font-size: 0.78rem; color: rgba(255,255,255,0.65); margin-top: 0.2rem; }
    section[data-testid="stSidebar"] .stButton > button {
        background: rgba(255,255,255,0.12);
        border: 1px solid rgba(255,255,255,0.25);
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: var(--red);
        border-color: var(--red);
    }

    /* ---------- Chat ---------- */
    .stChatMessage {
        border-radius: 14px;
        border: 1px solid var(--border);
    }

    /* ---------- Footer ---------- */
    .app-footer {
        text-align: center;
        color: var(--text-secondary);
        font-size: 0.85rem;
        padding: 1.2rem 0 0.4rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Sidebar — brand + client lookup control panel
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
        <div class="sidebar-project-name">NEXORA</div>
        <div class="sidebar-brand">
            <span class="sidebar-brand-icon">🏦</span>
            <div>
                <p class="sidebar-brand-name">ABC Bank</p>
                <p class="sidebar-brand-sub">Wholesale Banking</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section-label">Client Lookup</div>', unsafe_allow_html=True)

    client_code_input = st.text_input(
        "Client / RM Code",
        value=st.session_state.client_code or "",
        key="client_code_input",
        placeholder="e.g. APR12345678",
        max_chars=14,
        label_visibility="collapsed"
    )
    st.caption("RM_CODE: 6-7 chars · APR_CLIENT_CODE: 8-14 chars")

    submit_col, clear_col = st.columns(2)
    with submit_col:
        submit_clicked = st.button("Submit", type="primary", use_container_width=True)
    with clear_col:
        clear_clicked = st.button("Clear", use_container_width=True)

    if submit_clicked:
        is_valid, code_type = validate_client_code(client_code_input)
        if is_valid and code_type == "RM_CODE":
            # Tab data is keyed by APR_CLIENT_CODE only; RM search resolves to
            # the RM's mapped clients (db_reader.resolve_lookup_code) and will
            # surface here as a client picker in an upcoming change.
            st.warning("⚠️ RM-code search is being upgraded to a client picker. "
                       "Until then, please enter an APR_CLIENT_CODE directly.")
        elif is_valid:
            formatted_code = format_client_code(client_code_input)

            if st.session_state.client_code != formatted_code or not st.session_state.summaries_generated:
                st.session_state.client_code = formatted_code
                st.session_state.code_type = code_type

                with st.spinner("Generating client summaries... This may take a minute."):
                    try:
                        generator = MultiAgentSummaryGenerator()
                        st.session_state.client_summaries = generator.generate_all_summaries(formatted_code)
                        st.session_state.summaries_generated = True
                    except ValueError as e:
                        # Raised by db_reader before any LLM call is made.
                        st.error(f"⚠️ {str(e)} — no matching client in the database.")
                        st.session_state.summaries_generated = False
                    except Exception as e:
                        st.error(f"Error generating summaries: {str(e)}. Please check your OpenAI API key and DB_* settings in the .env file.")
                        st.session_state.summaries_generated = False

            if st.session_state.chatbot is None:
                st.session_state.chatbot = WholesaleBankingChatbot(formatted_code)
            else:
                st.session_state.chatbot.update_client_code(formatted_code)

            st.session_state.messages = []
            st.rerun()
        else:
            st.error("⚠️ Enter a valid RM_CODE (6-7 chars) or APR_CLIENT_CODE (8-14 chars)")

    if clear_clicked:
        st.session_state.client_code = None
        st.session_state.code_type = None
        st.session_state.chatbot = None
        st.session_state.messages = []
        st.session_state.client_summaries = None
        st.session_state.summaries_generated = False
        st.rerun()

    if st.session_state.client_code:
        st.markdown(f"""
            <div class="sidebar-status-card">
                <div class="code">🔑 {st.session_state.client_code}</div>
                <div class="type">{st.session_state.code_type or ''} · {'Analysis ready' if st.session_state.summaries_generated else 'Pending'}</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section-label">Powered by</div>', unsafe_allow_html=True)
    st.caption("Wholesale Automation Team - Mumbai")

# ----------------------------------------------------------------------------
# Main area
# ----------------------------------------------------------------------------
st.markdown("""
    <div class="hero-banner">
        <div class="hero-row">
            <p class="hero-title">🏦 ABC Bank Wholesale Banking - NEXORA</p>
            <span class="hero-badge">● AI Assistant Online</span>
        </div>
        <p class="hero-subtitle">AI-powered insights for relationship managers &mdash; assets, liabilities, products, and client history in one place.</p>
    </div>
""", unsafe_allow_html=True)

if st.session_state.client_code and st.session_state.summaries_generated and st.session_state.client_summaries:
    # ---- Status chips ----
    st.markdown(f"""
        <div class="chip-row">
            <span class="chip chip-code">🔑 {st.session_state.client_code}</span>
            <span class="chip chip-type">{st.session_state.code_type or 'CLIENT'}</span>
            <span class="chip chip-status"><span class="chip-dot"></span> Analysis complete</span>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="section-title">
            <span class="section-icon">📊</span>
            <strong>Client Analysis Summaries</strong>
        </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👤 RM Details",
        "💼 Asset Base",
        "📈 Liability Base",
        "🏢 Product Holdings",
        "💬 RM Discussion"
    ])

    with tab1:
        st.markdown("""
            <div class="tab-section-title">
                <span>👤</span> Relationship Manager Details &amp; CRM Interactions
            </div>
        """, unsafe_allow_html=True)
        st.markdown(f'<div class="summary-text">{st.session_state.client_summaries["rm_summary"]}</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown("""
            <div class="tab-section-title"><span>💼</span> Asset Base Interactions</div>
        """, unsafe_allow_html=True)

        col_text, col_charts = st.columns([1, 1])
        with col_text:
            st.markdown(f'<div class="summary-text">{st.session_state.client_summaries["asset_summary"]}</div>', unsafe_allow_html=True)
        with col_charts:
            for chart in ChartGenerator.generate_asset_charts(st.session_state.client_code):
                st.plotly_chart(chart, use_container_width=True)

    with tab3:
        st.markdown("""
            <div class="tab-section-title"><span>📈</span> Liability Base Interactions</div>
        """, unsafe_allow_html=True)

        col_text, col_charts = st.columns([1, 1])
        with col_text:
            st.markdown(f'<div class="summary-text">{st.session_state.client_summaries["liability_summary"]}</div>', unsafe_allow_html=True)
        with col_charts:
            for chart in ChartGenerator.generate_liability_charts(st.session_state.client_code):
                st.plotly_chart(chart, use_container_width=True)

    with tab4:
        st.markdown("""
            <div class="tab-section-title"><span>🏢</span> Overall Banking &amp; Product Holdings</div>
        """, unsafe_allow_html=True)
        st.markdown(f'<div class="summary-text">{st.session_state.client_summaries["product_holding_summary"]}</div>', unsafe_allow_html=True)

    with tab5:
        st.markdown("""
            <div class="tab-section-title"><span>💬</span> RM-Client Discussions</div>
        """, unsafe_allow_html=True)
        st.markdown(f'<div class="summary-text">{st.session_state.client_summaries["rm_discussion_summary"]}</div>', unsafe_allow_html=True)

else:
    if not st.session_state.client_code:
        st.markdown("""
            <div class="section-title">
                <span class="section-icon">📚</span>
                <strong>Wholesale Banking Overview</strong>
            </div>
        """, unsafe_allow_html=True)
        st.markdown(f'<div class="summary-text">{STATIC_WHOLESALE_INTRO}</div>', unsafe_allow_html=True)

        st.markdown("""
            <div class="section-title" style="margin-top:0.5rem;">
                <span class="section-icon">🧭</span>
                <strong>What the assistant can help with</strong>
            </div>
        """, unsafe_allow_html=True)

        cols = st.columns(3)
        for i, feature in enumerate(FEATURES):
            with cols[i % 3]:
                st.markdown(f"""
                    <div class="feature-card">
                        <div class="feature-icon">{feature['icon']}</div>
                        <div class="feature-title">{feature['title']}</div>
                        <div class="feature-desc">{feature['desc']}</div>
                    </div>
                """, unsafe_allow_html=True)

        st.markdown("""
            <div class="cta-hint">👈 Enter an APR_CLIENT_CODE or RM_CODE in the sidebar to begin.</div>
        """, unsafe_allow_html=True)

# ---- Chat section ----
if st.session_state.client_code:
    st.markdown("""
        <div class="section-title">
            <span class="section-icon">🤖</span>
            <strong>Chat with Assistant</strong>
        </div>
    """, unsafe_allow_html=True)

    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("Ask me about wholesale banking..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        if st.session_state.chatbot is None:
            st.session_state.chatbot = WholesaleBankingChatbot(st.session_state.client_code)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = st.session_state.chatbot.get_response(prompt)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    error_msg = f"Sorry, I encountered an error: {str(e)}. Please check your OpenAI API key in the .env file."
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})

# Footer
st.markdown("""
    <div class="app-footer">Powered by Wholesale Automation Team - Mumbai</div>
""", unsafe_allow_html=True)
