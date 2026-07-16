"""
Streamlit Human Gate — LQOA
Tabs:
  1. New Lead       — intake form + immediate pipeline run
  2. Approval Queue — HOT leads pending approval; edit + approve/reject
  3. Nurture Queue  — read-only, sequence-enrolled leads
  4. Disqualified   — read-only, archived leads with reasons
  5. Governance     — audit log viewer + violation check
"""
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from datetime import datetime, timezone

from orchestrator import LeadState, run_pipeline
from tools.email_send import register_approval, email_send, get_sent_emails, get_approval
from tools.sequence_enroll import get_enrolled
from tools.archive_lead import get_archived
from governance.logger import query_log, sends_without_approval

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LQOA — Lead Qualification & Outreach Agent",
    page_icon="🎯",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
# Palette:
#   Primary navy   #0A1628   (headers, sidebar bg)
#   Mid navy       #112240   (sidebar gradient end)
#   Gold accent    #C9A84C   (borders, highlights, active elements)
#   Light gold     #F0D080   (hover tints)
#   Surface white  #FFFFFF
#   Page bg        #F5F6FA
#   Muted text     #5A6A85
#   Border         #DDE3EE
st.markdown("""
<style>
/* ── Google Font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── Page background ── */
.stApp {
    background-color: #F5F6FA;
}

/* ══════════════════════════════════════
   SIDEBAR
══════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0A1628 0%, #112240 100%);
    border-right: 1px solid #1E3A5F;
}
[data-testid="stSidebar"] * {
    color: #C8D6E8 !important;
}
[data-testid="stSidebar"] hr {
    border-color: #1E3A5F !important;
    margin: 12px 0 !important;
}
.sidebar-brand {
    font-size: 1.45rem;
    font-weight: 800;
    color: #FFFFFF !important;
    letter-spacing: -0.5px;
}
.sidebar-tagline {
    font-size: 0.75rem;
    color: #C9A84C !important;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 600;
    margin-top: 2px;
}
.sidebar-section-label {
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #4A6A90 !important;
    margin-bottom: 6px;
    margin-top: 4px;
}

/* Pipeline step list */
.pipeline-step {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 5px 0;
    font-size: 0.82rem;
    color: #A8BDD4 !important;
}
.step-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #C9A84C;
    flex-shrink: 0;
}

/* Live stats rows */
.stat-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 0;
    border-bottom: 1px solid #1A3050;
    font-size: 0.8rem;
}
.stat-label { color: #8AAAC8 !important; }

/* ══════════════════════════════════════
   TAB STRIP
══════════════════════════════════════ */
button[data-baseweb="tab"] {
    font-weight: 600;
    font-size: 0.88rem;
    color: #5A6A85 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #0A1628 !important;
    border-bottom: 3px solid #C9A84C !important;
}

/* ══════════════════════════════════════
   SECTION HEADERS
══════════════════════════════════════ */
.section-header {
    font-size: 1.4rem;
    font-weight: 800;
    color: #0A1628;
    margin-bottom: 2px;
    letter-spacing: -0.3px;
}
.section-sub {
    font-size: 0.84rem;
    color: #5A6A85;
    margin-bottom: 20px;
}

/* ══════════════════════════════════════
   KPI CARDS
══════════════════════════════════════ */
.kpi-card {
    background: #FFFFFF;
    border-radius: 10px;
    padding: 18px 22px;
    box-shadow: 0 1px 4px rgba(10,22,40,0.08), 0 0 0 1px #DDE3EE;
    border-top: 3px solid #C9A84C;
    margin-bottom: 8px;
}
.kpi-card.hot   { border-top-color: #C0392B; }
.kpi-card.warm  { border-top-color: #D4870A; }
.kpi-card.cool  { border-top-color: #1A7F5A; }
.kpi-card.info  { border-top-color: #C9A84C; }
.kpi-card.muted { border-top-color: #8A9BB5; }
.kpi-label {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #8A9BB5;
    margin-bottom: 6px;
}
.kpi-value {
    font-size: 2.1rem;
    font-weight: 800;
    color: #0A1628;
    line-height: 1;
}
.kpi-sub {
    font-size: 0.76rem;
    color: #A0AEBE;
    margin-top: 4px;
}

/* ══════════════════════════════════════
   CONTENT CARDS (lead cards, form card)
══════════════════════════════════════ */
.lead-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 24px 28px;
    box-shadow: 0 2px 8px rgba(10,22,40,0.07), 0 0 0 1px #DDE3EE;
    margin-bottom: 20px;
    border-top: 3px solid #C9A84C;
}
.lead-card-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 18px;
    padding-bottom: 14px;
    border-bottom: 1px solid #EEF1F7;
}

/* ══════════════════════════════════════
   BADGES
══════════════════════════════════════ */
.badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.badge-hot  { background: #FDECEA; color: #C0392B; border: 1px solid #F5C6C2; }
.badge-nurture { background: #E8F8F2; color: #1A7F5A; border: 1px solid #B7E4D0; }
.badge-disq { background: #F0F2F7; color: #5A6A85; border: 1px solid #D0D6E4; }

/* ══════════════════════════════════════
   SCORE BAR
══════════════════════════════════════ */
.score-bar-wrap { margin: 6px 0 14px 0; }
.score-bar-bg {
    background: #EEF1F7;
    border-radius: 999px;
    height: 7px;
    overflow: hidden;
}
.score-bar-fill {
    height: 7px;
    border-radius: 999px;
    background: linear-gradient(90deg, #C9A84C, #F0D080);
}
.score-bar-fill.high { background: linear-gradient(90deg, #C0392B, #E85D52); }
.score-bar-fill.mid  { background: linear-gradient(90deg, #D4870A, #F0A830); }
.score-bar-fill.low  { background: linear-gradient(90deg, #1A7F5A, #2ECC8A); }

/* ══════════════════════════════════════
   FACTOR ROWS
══════════════════════════════════════ */
.factor-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 10px;
    border-radius: 6px;
    margin-bottom: 4px;
    background: #F5F6FA;
    font-size: 0.81rem;
    border: 1px solid #EEF1F7;
}
.factor-pos { color: #1A7F5A; font-weight: 700; }
.factor-neg { color: #C0392B; font-weight: 700; }
.factor-neu { color: #A0AEBE; font-weight: 600; }

/* ══════════════════════════════════════
   QUEUE ROWS (Nurture / Disqualified)
══════════════════════════════════════ */
.queue-row {
    background: #FFFFFF;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 8px;
    border: 1px solid #DDE3EE;
    border-left: 4px solid #C9A84C;
    box-shadow: 0 1px 3px rgba(10,22,40,0.05);
    display: flex;
    align-items: flex-start;
    gap: 12px;
}
.queue-row.disq { border-left-color: #8A9BB5; }
.queue-icon { font-size: 1.2rem; flex-shrink: 0; padding-top: 2px; }
.queue-meta { font-size: 0.77rem; color: #8A9BB5; margin-top: 3px; }

/* ══════════════════════════════════════
   SENT EMAIL ROW
══════════════════════════════════════ */
.sent-row {
    background: #F0FAF5;
    border: 1px solid #B7E4D0;
    border-left: 4px solid #1A7F5A;
    border-radius: 8px;
    padding: 11px 16px;
    margin-bottom: 6px;
    font-size: 0.84rem;
    color: #0D5C3A;
}

/* ══════════════════════════════════════
   BUTTONS
══════════════════════════════════════ */
div[data-testid="stButton"] > button {
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.84rem;
    letter-spacing: 0.02em;
    transition: all 0.15s ease;
    border: 1.5px solid transparent;
}
div[data-testid="stButton"] > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(10,22,40,0.12);
}

/* Primary form submit — gold */
div[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #C9A84C 0%, #D4AF60 100%) !important;
    color: #0A1628 !important;
    border: none !important;
    font-weight: 700 !important;
    border-radius: 6px !important;
    letter-spacing: 0.03em;
}
div[data-testid="stFormSubmitButton"] > button:hover {
    background: linear-gradient(135deg, #B8973B 0%, #C9A84C 100%) !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(201,168,76,0.35) !important;
}

/* ══════════════════════════════════════
   FORM INPUTS
══════════════════════════════════════ */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    border-radius: 6px;
    border: 1.5px solid #DDE3EE;
    background: #FAFBFD;
    font-family: 'Inter', sans-serif;
    font-size: 0.88rem;
    color: #0A1628;
    transition: border-color 0.15s, box-shadow 0.15s;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #C9A84C !important;
    box-shadow: 0 0 0 3px rgba(201,168,76,0.15) !important;
    background: #FFFFFF !important;
}
label[data-testid="stWidgetLabel"] p {
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    color: #3A4D66 !important;
    letter-spacing: 0.02em;
}

/* ══════════════════════════════════════
   SELECTBOX
══════════════════════════════════════ */
.stSelectbox > div > div {
    border-radius: 6px !important;
    border: 1.5px solid #DDE3EE !important;
    background: #FAFBFD !important;
}

/* ══════════════════════════════════════
   ALERTS / BANNERS
══════════════════════════════════════ */
div[data-testid="stAlert"] {
    border-radius: 8px !important;
    font-size: 0.86rem !important;
}

/* ══════════════════════════════════════
   DATAFRAME / TABLE
══════════════════════════════════════ */
.stDataFrame {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #DDE3EE !important;
}

/* ══════════════════════════════════════
   EXPANDER
══════════════════════════════════════ */
details[data-testid="stExpander"] {
    border: 1px solid #DDE3EE !important;
    border-radius: 8px !important;
    background: #FFFFFF !important;
}
details[data-testid="stExpander"] summary {
    font-size: 0.84rem !important;
    font-weight: 600 !important;
    color: #0A1628 !important;
    padding: 10px 14px !important;
}

/* ══════════════════════════════════════
   DIVIDERS
══════════════════════════════════════ */
hr { border-color: #DDE3EE !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "approval_queue" not in st.session_state:
    st.session_state["approval_queue"] = {}

if "rejected" not in st.session_state:
    st.session_state["rejected"] = []

if "pipeline_results" not in st.session_state:
    st.session_state["pipeline_results"] = []

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-brand">🎯 LQOA</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sidebar-tagline">Lead Qualification &amp; Outreach</div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Pipeline flow
    st.markdown('<div class="sidebar-section-label">Pipeline</div>', unsafe_allow_html=True)
    pipeline_steps = ["Enrich", "Score", "Classify", "Route", "Draft", "Human Gate", "Send"]
    for step in pipeline_steps:
        st.markdown(
            f'<div class="pipeline-step"><span class="step-dot"></span>{step}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Live stats
    queue_count   = len(st.session_state["approval_queue"])
    sent_count    = len(get_sent_emails())
    nurture_count = len(get_enrolled())
    archive_count = len(get_archived())
    total_leads   = len(st.session_state["pipeline_results"])

    st.markdown('<div class="sidebar-section-label">Live Stats</div>', unsafe_allow_html=True)
    stats = [
        ("Total Processed",  total_leads,   "#C9A84C"),
        ("Pending Approval", queue_count,   "#E85D52"),
        ("Emails Sent",      sent_count,    "#2ECC8A"),
        ("In Nurture",       nurture_count, "#F0A830"),
        ("Disqualified",     archive_count, "#8A9BB5"),
    ]
    for label, val, color in stats:
        st.markdown(
            f'<div class="stat-row">'
            f'<span class="stat-label">{label}</span>'
            f'<span style="font-size:0.92rem;font-weight:700;color:{color};">{val}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown(
        '<div style="font-size:0.7rem;color:#3A5070;text-align:center;padding:4px 0;">'
        'v1.0 &nbsp;·&nbsp; Built with Streamlit</div>',
        unsafe_allow_html=True,
    )

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_new, tab_queue, tab_nurture, tab_archive, tab_gov = st.tabs(
    ["➕  New Lead", "🔥  Approval Queue", "🌱  Nurture", "🗂️  Disqualified", "🔍  Governance"]
)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — NEW LEAD
# ═══════════════════════════════════════════════════════════════════════════════
with tab_new:
    st.markdown('<div class="section-header">Submit a New Lead</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">Fill in the lead details below. '
        'The pipeline runs immediately — HOT leads are queued for human approval.</div>',
        unsafe_allow_html=True,
    )

    # KPI row
    total_processed = len(st.session_state["pipeline_results"])
    hot_count   = sum(1 for r in st.session_state["pipeline_results"]
                      if r.classification and r.classification.label == "HOT")
    nur_count   = sum(1 for r in st.session_state["pipeline_results"]
                      if r.classification and r.classification.label == "NURTURE")
    disq_count  = sum(1 for r in st.session_state["pipeline_results"]
                      if r.classification and r.classification.label == "DISQUALIFY")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            '<div class="kpi-card info">'
            '<div class="kpi-label">Total Submitted</div>'
            f'<div class="kpi-value">{total_processed}</div>'
            '<div class="kpi-sub">This session</div>'
            '</div>', unsafe_allow_html=True)
    with k2:
        st.markdown(
            '<div class="kpi-card hot">'
            '<div class="kpi-label">🔥 HOT</div>'
            f'<div class="kpi-value">{hot_count}</div>'
            '<div class="kpi-sub">Queued for approval</div>'
            '</div>', unsafe_allow_html=True)
    with k3:
        st.markdown(
            '<div class="kpi-card warm">'
            '<div class="kpi-label">🌱 Nurture</div>'
            f'<div class="kpi-value">{nur_count}</div>'
            '<div class="kpi-sub">In sequences</div>'
            '</div>', unsafe_allow_html=True)
    with k4:
        st.markdown(
            '<div class="kpi-card cool">'
            '<div class="kpi-label">🗂️ Disqualified</div>'
            f'<div class="kpi-value">{disq_count}</div>'
            '<div class="kpi-sub">Archived</div>'
            '</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Form card
    st.markdown('<div class="lead-card">', unsafe_allow_html=True)
    with st.form("lead_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            first_name = st.text_input("First Name", placeholder="Alex")
            last_name  = st.text_input("Last Name", placeholder="Rivera")
        with col2:
            email      = st.text_input("Work Email", placeholder="alex@acmecorp.com")
            company    = st.text_input("Company", placeholder="Acme Corp")
        with col3:
            role_title = st.text_input("Role / Title", placeholder="VP Sales")
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

        free_text = st.text_area(
            "Message / Notes (optional)",
            placeholder="Any context the lead provided…",
            height=90,
        )
        submitted = st.form_submit_button("▶  Run Pipeline", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if submitted:
        if not email or not company or not role_title:
            st.error("⚠️  Email, Company, and Role are required.")
        else:
            lead = LeadState(
                first_name=first_name,
                last_name=last_name,
                email=email,
                company=company,
                role_title=role_title,
                free_text=free_text,
            )
            with st.spinner("Running pipeline…"):
                result = run_pipeline(lead)
            st.session_state["pipeline_results"].append(result)

            label     = result.classification.label if result.classification else "N/A"
            score_val = result.score_result.score if result.score_result else 0
            pct       = min(score_val, 100)

            colour_map = {"HOT": ("#EF4444", "🔥", "hot"), "NURTURE": ("#10B981", "🌱", "warm"), "DISQUALIFY": ("#94A3B8", "🗂️", "cool")}
            hex_c, emoji, bar_cls = colour_map.get(label, ("#6366F1", "❓", "info"))

            # Result card
            st.markdown(
                f'<div class="lead-card" style="border-left:4px solid {hex_c};margin-top:16px;">'
                f'<div style="font-size:1.1rem;font-weight:700;color:{hex_c};">'
                f'{emoji} {label}</div>'
                f'<div style="margin:8px 0 4px 0;font-size:0.82rem;color:#64748B;">Score</div>'
                f'<div style="font-size:1.6rem;font-weight:700;color:#0F172A;">{score_val}<span style="font-size:1rem;color:#94A3B8;">/100</span></div>'
                f'<div class="score-bar-wrap">'
                f'<div class="score-bar-bg"><div class="score-bar-fill {bar_cls}" style="width:{pct}%;"></div></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if result.classification:
                st.markdown(
                    f'<div style="font-size:0.85rem;color:#334155;margin-top:4px;">'
                    f'<b>Reason:</b> {result.classification.reason}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown('</div>', unsafe_allow_html=True)

            if result.injection_detected:
                st.warning(
                    "⚠️ Injection attempt detected in free-text field. "
                    "Scoring proceeded from verified signals only."
                )

            if label == "HOT" and result.draft:
                st.session_state["approval_queue"][result.lead_id] = result
                st.success("✅ Draft queued for human approval — check the **Approval Queue** tab.")
                with st.expander("Preview draft email"):
                    st.markdown(f"**Subject:** {result.draft.subject}")
                    st.text_area("Body", result.draft.body, height=200, disabled=True)

            elif label == "NURTURE":
                st.info("Lead enrolled in nurture sequence.")
            elif label == "DISQUALIFY":
                st.info("Lead archived with reason.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — APPROVAL QUEUE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_queue:
    st.markdown('<div class="section-header">🔥 Approval Queue — HOT Leads</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">Review AI-drafted outreach emails. Edit if needed, then approve or reject.</div>',
        unsafe_allow_html=True,
    )

    queue = st.session_state["approval_queue"]
    pending = {lid: ls for lid, ls in queue.items() if not get_approval(lid)}

    if not pending:
        st.markdown(
            '<div style="background:#F8FAFC;border:1px dashed #CBD5E1;border-radius:12px;'
            'padding:40px;text-align:center;color:#94A3B8;font-size:0.95rem;">'
            '✅ &nbsp; No HOT leads pending approval right now.</div>',
            unsafe_allow_html=True,
        )
    else:
        for lead_id, lead_state in list(pending.items()):
            score_val = lead_state.score_result.score if lead_state.score_result else 0
            pct       = min(score_val, 100)
            bar_cls   = "high" if pct >= 80 else ("mid" if pct >= 50 else "low")

            st.markdown('<div class="lead-card">', unsafe_allow_html=True)

            # Card header
            st.markdown(
                f'<div class="lead-card-header">'
                f'<span style="font-size:1.4rem;">🔥</span>'
                f'<div>'
                f'<div style="font-weight:700;font-size:1rem;color:#0F172A;">'
                f'{lead_state.first_name or ""} {lead_state.last_name or ""} '
                f'<span style="color:#64748B;font-weight:400;">·</span> '
                f'{lead_state.company}</div>'
                f'<div style="font-size:0.8rem;color:#64748B;">{lead_state.role_title} &nbsp;·&nbsp; '
                f'<code style="font-size:0.75rem;">{lead_id}</code></div>'
                f'</div>'
                f'<span class="badge badge-hot" style="margin-left:auto;">HOT</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            col_score, col_draft = st.columns([1, 2])

            with col_score:
                st.markdown(
                    f'<div style="font-weight:600;font-size:0.88rem;color:#0F172A;margin-bottom:6px;">Score</div>'
                    f'<div style="font-size:2rem;font-weight:700;color:#0F172A;">{score_val}'
                    f'<span style="font-size:1rem;color:#94A3B8;">/100</span></div>'
                    f'<div class="score-bar-wrap">'
                    f'<div class="score-bar-bg">'
                    f'<div class="score-bar-fill {bar_cls}" style="width:{pct}%;"></div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

                if lead_state.score_result:
                    st.markdown('<div style="margin-top:10px;font-size:0.8rem;font-weight:600;color:#64748B;margin-bottom:4px;">Factor Breakdown</div>', unsafe_allow_html=True)
                    for factor, val in lead_state.score_result.factors.items():
                        cls  = "factor-pos" if val > 0 else ("factor-neg" if val < 0 else "factor-neu")
                        sign = "+" if val > 0 else ""
                        st.markdown(
                            f'<div class="factor-row">'
                            f'<span style="color:#334155;">{factor}</span>'
                            f'<span class="{cls}">{sign}{val}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                if lead_state.classification:
                    st.markdown(
                        f'<div style="margin-top:10px;font-size:0.8rem;color:#475569;">'
                        f'<b>Reason:</b> {lead_state.classification.reason}</div>',
                        unsafe_allow_html=True,
                    )

            with col_draft:
                st.markdown('<div style="font-weight:600;font-size:0.88rem;color:#0F172A;margin-bottom:8px;">Draft Email</div>', unsafe_allow_html=True)
                edited_subject = st.text_input(
                    "Subject", value=lead_state.draft.subject, key=f"subj_{lead_id}"
                )
                edited_body = st.text_area(
                    "Body", value=lead_state.draft.body, height=220, key=f"body_{lead_id}"
                )
                approver = st.text_input(
                    "Your name (approver)", key=f"approver_{lead_id}", placeholder="Jane Smith"
                )

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                if st.button("✅  Approve", key=f"approve_{lead_id}", use_container_width=True):
                    if not approver:
                        st.error("Enter your name before approving.")
                    else:
                        ts = datetime.now(timezone.utc).isoformat()
                        register_approval(lead_id=lead_id, subject=edited_subject, body=edited_body, approver=approver, timestamp=ts)
                        email_send(lead_id=lead_id, subject=edited_subject, body=edited_body, sender=approver)
                        del queue[lead_id]
                        st.success(f"✅ Email sent for lead {lead_id}!")
                        st.rerun()
            with col_b:
                if st.button("✏️  Approve as Edited", key=f"approveedit_{lead_id}", use_container_width=True):
                    if not approver:
                        st.error("Enter your name before approving.")
                    elif edited_subject == lead_state.draft.subject and edited_body == lead_state.draft.body:
                        st.warning("No edits detected — use Approve instead.")
                    else:
                        ts = datetime.now(timezone.utc).isoformat()
                        register_approval(lead_id=lead_id, subject=edited_subject, body=edited_body, approver=approver, timestamp=ts)
                        email_send(lead_id=lead_id, subject=edited_subject, body=edited_body, sender=approver)
                        del queue[lead_id]
                        st.success(f"✅ Edited email sent for lead {lead_id}!")
                        st.rerun()
            with col_c:
                if st.button("❌  Reject", key=f"reject_{lead_id}", use_container_width=True):
                    st.session_state["rejected"].append({"lead_id": lead_id, "reason": "Rejected by approver"})
                    del queue[lead_id]
                    st.info(f"Lead {lead_id} rejected.")
                    st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Sent emails section
    sent = get_sent_emails()
    if sent:
        st.markdown("---")
        st.markdown('<div style="font-weight:700;font-size:1rem;color:#0F172A;margin-bottom:10px;">📬 Recently Sent</div>', unsafe_allow_html=True)
        for s in sent:
            st.markdown(
                f'<div class="sent-row">✅ &nbsp;<b>{s["subject"]}</b>'
                f'<span style="float:right;color:#4B5563;font-size:0.78rem;">'
                f'lead: <code>{s["lead_id"]}</code> &nbsp;·&nbsp; by {s["approved_by"]}</span></div>',
                unsafe_allow_html=True,
            )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — NURTURE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_nurture:
    st.markdown('<div class="section-header">🌱 Nurture Queue</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">Leads enrolled in automated nurture sequences. Read-only view.</div>',
        unsafe_allow_html=True,
    )

    enrolled = get_enrolled()
    if not enrolled:
        st.markdown(
            '<div style="background:#F0FDF4;border:1px dashed #86EFAC;border-radius:12px;'
            'padding:40px;text-align:center;color:#6B7280;font-size:0.95rem;">'
            '🌱 &nbsp; No leads in nurture sequences yet.</div>',
            unsafe_allow_html=True,
        )
    else:
        # KPI
        st.markdown(
            f'<div class="kpi-card warm" style="max-width:220px;margin-bottom:20px;">'
            f'<div class="kpi-label">In Nurture</div>'
            f'<div class="kpi-value">{len(enrolled)}</div>'
            f'<div class="kpi-sub">Total enrolled</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        for e in enrolled:
            st.markdown(
                f'<div class="queue-row">'
                f'<div class="queue-icon">🌱</div>'
                f'<div>'
                f'<div style="font-weight:600;font-size:0.9rem;color:#065F46;">'
                f'<code>{e["lead_id"]}</code></div>'
                f'<div style="font-size:0.85rem;color:#374151;margin-top:2px;">'
                f'Sequence: <b>{e["sequence_name"]}</b></div>'
                f'<div class="queue-meta">Reason: {e["reason"]}</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — DISQUALIFIED
# ═══════════════════════════════════════════════════════════════════════════════
with tab_archive:
    st.markdown('<div class="section-header">🗂️ Disqualified Archive</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">Leads that did not meet qualification criteria. Read-only view.</div>',
        unsafe_allow_html=True,
    )

    archived = get_archived()
    if not archived:
        st.markdown(
            '<div style="background:#F8FAFC;border:1px dashed #CBD5E1;border-radius:12px;'
            'padding:40px;text-align:center;color:#94A3B8;font-size:0.95rem;">'
            '🗂️ &nbsp; No disqualified leads yet.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="kpi-card" style="max-width:220px;margin-bottom:20px;border-left-color:#94A3B8;">'
            f'<div class="kpi-label">Disqualified</div>'
            f'<div class="kpi-value">{len(archived)}</div>'
            f'<div class="kpi-sub">Total archived</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        for a in archived:
            st.markdown(
                f'<div class="queue-row">'
                f'<div class="queue-icon">🗂️</div>'
                f'<div>'
                f'<div style="font-weight:600;font-size:0.9rem;color:#475569;">'
                f'<code>{a["lead_id"]}</code></div>'
                f'<div class="queue-meta" style="margin-top:3px;">Reason: {a["reason"]}</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — GOVERNANCE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_gov:
    st.markdown('<div class="section-header">🔍 Governance & Audit</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">Compliance overview, injection detections, and full audit trail.</div>',
        unsafe_allow_html=True,
    )

    violations = sends_without_approval()
    injections  = [e for e in query_log() if e.get("injection_detected")]

    # Top stat row
    g1, g2, g3 = st.columns(3)
    with g1:
        v_color = "#EF4444" if violations else "#10B981"
        v_label = f"{len(violations)} Violation(s)" if violations else "All Clear"
        st.markdown(
            f'<div class="kpi-card" style="border-left-color:{v_color};">'
            f'<div class="kpi-label">Unapproved Sends</div>'
            f'<div class="kpi-value" style="color:{v_color};">{len(violations)}</div>'
            f'<div class="kpi-sub">{v_label}</div>'
            f'</div>', unsafe_allow_html=True)
    with g2:
        i_color = "#F59E0B" if injections else "#10B981"
        st.markdown(
            f'<div class="kpi-card" style="border-left-color:{i_color};">'
            f'<div class="kpi-label">Injection Attempts</div>'
            f'<div class="kpi-value" style="color:{i_color};">{len(injections)}</div>'
            f'<div class="kpi-sub">{"Detected" if injections else "None detected"}</div>'
            f'</div>', unsafe_allow_html=True)
    with g3:
        total_entries = len(query_log())
        st.markdown(
            f'<div class="kpi-card info">'
            f'<div class="kpi-label">Audit Log Entries</div>'
            f'<div class="kpi-value">{total_entries}</div>'
            f'<div class="kpi-sub">Total events</div>'
            f'</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Violations + Injections side by side
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div style="font-weight:700;font-size:0.95rem;color:#0F172A;margin-bottom:8px;">Sends Without Approval</div>', unsafe_allow_html=True)
        if not violations:
            st.success("✅ Zero unapproved sends — all outbound actions are authorised.")
        else:
            st.error(f"🚨 {len(violations)} violation(s) detected!")
            for v in violations:
                st.json(v)

    with col2:
        st.markdown('<div style="font-weight:700;font-size:0.95rem;color:#0F172A;margin-bottom:8px;">Injection Detections</div>', unsafe_allow_html=True)
        if not injections:
            st.info("No injection attempts logged.")
        else:
            st.warning(f"⚠️ {len(injections)} injection attempt(s) detected.")
            for inj in injections:
                st.json(inj)

    st.markdown("---")
    st.markdown('<div style="font-weight:700;font-size:1rem;color:#0F172A;margin-bottom:12px;">Full Audit Log</div>', unsafe_allow_html=True)

    # Filters
    cf1, cf2, cf3 = st.columns(3)
    with cf1:
        filter_lead = st.text_input("Filter by Lead ID", placeholder="Leave blank for all")
    with cf2:
        filter_stage = st.text_input("Filter by Stage", placeholder="Leave blank for all")
    with cf3:
        filter_classification = st.selectbox(
            "Filter by Classification",
            options=["All", "HOT", "NURTURE", "DISQUALIFY"],
        )

    classification_filter = None if filter_classification == "All" else filter_classification
    log_entries = query_log(
        lead_id=filter_lead or None,
        stage=filter_stage or None,
        classification=classification_filter,
    )
    st.caption(f"{len(log_entries)} entries")

    if log_entries:
        table_data = []
        for entry in reversed(log_entries):
            table_data.append({
                "Timestamp":      entry.get("timestamp", "N/A")[:19].replace("T", " "),
                "Lead ID":        entry.get("lead_id", "N/A"),
                "Stage":          entry.get("stage", "N/A"),
                "Email":          entry.get("email", "N/A"),
                "Classification": entry.get("classification", "N/A"),
                "Injection":      "⚠️" if entry.get("injection_detected") else "",
                "Gate Decision":  entry.get("gate_decision", "N/A"),
                "Authorized By":  entry.get("authorized_by", "N/A"),
            })
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True)

        st.markdown("---")
        st.markdown('<div style="font-weight:700;font-size:0.95rem;color:#0F172A;margin-bottom:8px;">Detailed Entry View</div>', unsafe_allow_html=True)
        st.caption("Expand individual entries for full JSON details")
        for entry in reversed(log_entries):
            email_d = f" · {entry.get('email', '')}" if entry.get("email") else ""
            cls_d   = f" · {entry.get('classification', '')}" if entry.get("classification") else ""
            with st.expander(
                f"{entry['timestamp'][:19].replace('T',' ')}  |  {entry['stage']}  |  {entry['lead_id']}{email_d}{cls_d}"
            ):
                st.json(entry)
    else:
        st.markdown(
            '<div style="background:#F8FAFC;border:1px dashed #CBD5E1;border-radius:10px;'
            'padding:24px;text-align:center;color:#94A3B8;">No log entries match the current filters.</div>',
            unsafe_allow_html=True,
        )
