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

# Ensure project root is on the path so imports work from any working directory
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

# ── Session state ─────────────────────────────────────────────────────────────
if "approval_queue" not in st.session_state:
    st.session_state["approval_queue"] = {}   # lead_id -> LeadState

if "rejected" not in st.session_state:
    st.session_state["rejected"] = []

if "pipeline_results" not in st.session_state:
    st.session_state["pipeline_results"] = []

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("🎯 LQOA")
st.sidebar.markdown("**Lead Qualification & Outreach Agent**")
st.sidebar.markdown("---")
st.sidebar.info(
    "Pipeline: Enrich → Score → Classify → Route → Draft → **Human Gate** → Send"
)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_new, tab_queue, tab_nurture, tab_archive, tab_gov = st.tabs(
    ["➕ New Lead", "🔥 Approval Queue", "🌱 Nurture", "🗂️ Disqualified", "🔍 Governance"]
)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — NEW LEAD (intake form)
# ═══════════════════════════════════════════════════════════════════════════════
with tab_new:
    st.header("Submit a New Lead")
    st.caption("Pipeline runs immediately on submit. HOT leads are queued for approval.")

    with st.form("lead_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input("First Name", placeholder="Alex")
            last_name = st.text_input("Last Name", placeholder="Rivera")
            email = st.text_input("Work Email", placeholder="alex@acmecorp.com")
        with col2:
            company = st.text_input("Company", placeholder="Acme Corp")
            role_title = st.text_input("Role / Title", placeholder="VP Sales")
        free_text = st.text_area(
            "Message / Notes (optional)",
            placeholder="Any context the lead provided…",
            height=100,
        )
        submitted = st.form_submit_button("▶ Run Pipeline", use_container_width=True)

    if submitted:
        if not email or not company or not role_title:
            st.error("Email, Company, and Role are required.")
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

            # Display result
            label = result.classification.label if result.classification else "N/A"
            score_val = result.score_result.score if result.score_result else 0

            colour = {"HOT": "🔥", "NURTURE": "🌱", "DISQUALIFY": "🗂️"}.get(label, "❓")
            st.success(f"{colour} **{label}** — Score: {score_val}/100")

            if result.injection_detected:
                st.warning(
                    "⚠️ Injection attempt detected in free-text field. "
                    "Scoring proceeded from verified signals only."
                )

            if result.classification:
                st.info(f"**Reason:** {result.classification.reason}")

            if label == "HOT" and result.draft:
                st.session_state["approval_queue"][result.lead_id] = result
                st.success("✅ Draft queued for human approval — check the **Approval Queue** tab.")
                with st.expander("Preview draft"):
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
    st.header("🔥 Approval Queue — HOT Leads")

    queue = st.session_state["approval_queue"]
    if not queue:
        st.info("No HOT leads pending approval.")
    else:
        for lead_id, lead_state in list(queue.items()):
            # Skip already processed
            if get_approval(lead_id):
                continue

            with st.expander(
                f"Lead {lead_id} | {lead_state.company} | {lead_state.role_title} "
                f"| Score: {lead_state.score_result.score}/100",
                expanded=True,
            ):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.markdown("**Score breakdown**")
                    if lead_state.score_result:
                        for factor, val in lead_state.score_result.factors.items():
                            colour = "🟢" if val > 0 else ("🔴" if val < 0 else "⚪")
                            st.markdown(f"{colour} `{factor}`: {val:+d}")
                        st.markdown(f"**Total: {lead_state.score_result.score}/100**")
                    st.markdown(f"**Reason:** {lead_state.classification.reason}")

                with col2:
                    st.markdown("**Draft email**")
                    edited_subject = st.text_input(
                        "Subject", value=lead_state.draft.subject, key=f"subj_{lead_id}"
                    )
                    edited_body = st.text_area(
                        "Body", value=lead_state.draft.body, height=250, key=f"body_{lead_id}"
                    )
                    approver = st.text_input(
                        "Your name (approver)", key=f"approver_{lead_id}", placeholder="Jane Smith"
                    )

                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if st.button("✅ Approve", key=f"approve_{lead_id}", use_container_width=True):
                        if not approver:
                            st.error("Enter your name before approving.")
                        else:
                            ts = datetime.now(timezone.utc).isoformat()
                            register_approval(
                                lead_id=lead_id,
                                subject=edited_subject,
                                body=edited_body,
                                approver=approver,
                                timestamp=ts,
                            )
                            email_send(
                                lead_id=lead_id,
                                subject=edited_subject,
                                body=edited_body,
                                sender=approver,
                            )
                            del queue[lead_id]
                            st.success(f"✅ Email sent for lead {lead_id}!")
                            st.rerun()

                with col_b:
                    if st.button("✏️ Approve as Edited", key=f"approveedit_{lead_id}", use_container_width=True):
                        if not approver:
                            st.error("Enter your name before approving.")
                        elif edited_subject == lead_state.draft.subject and edited_body == lead_state.draft.body:
                            st.warning("No edits detected — use Approve instead.")
                        else:
                            ts = datetime.now(timezone.utc).isoformat()
                            register_approval(
                                lead_id=lead_id,
                                subject=edited_subject,
                                body=edited_body,
                                approver=approver,
                                timestamp=ts,
                            )
                            email_send(
                                lead_id=lead_id,
                                subject=edited_subject,
                                body=edited_body,
                                sender=approver,
                            )
                            del queue[lead_id]
                            st.success(f"✅ Edited email sent for lead {lead_id}!")
                            st.rerun()

                with col_c:
                    if st.button("❌ Reject", key=f"reject_{lead_id}", use_container_width=True):
                        st.session_state["rejected"].append(
                            {"lead_id": lead_id, "reason": "Rejected by approver"}
                        )
                        del queue[lead_id]
                        st.info(f"Lead {lead_id} rejected.")
                        st.rerun()

    # Show recently sent
    sent = get_sent_emails()
    if sent:
        st.markdown("---")
        st.subheader("📬 Sent Emails")
        for s in sent:
            st.markdown(
                f"✅ `{s['lead_id']}` | **{s['subject']}** | Approved by: {s['approved_by']}"
            )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — NURTURE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_nurture:
    st.header("🌱 Nurture Queue (read-only)")
    enrolled = get_enrolled()
    if not enrolled:
        st.info("No leads in nurture sequences yet.")
    else:
        for e in enrolled:
            st.markdown(
                f"🌱 `{e['lead_id']}` → sequence: **{e['sequence_name']}**  \n"
                f"Reason: {e['reason']}"
            )
            st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — DISQUALIFIED
# ═══════════════════════════════════════════════════════════════════════════════
with tab_archive:
    st.header("🗂️ Disqualified Archive (read-only)")
    archived = get_archived()
    if not archived:
        st.info("No disqualified leads yet.")
    else:
        for a in archived:
            st.markdown(f"🗂️ `{a['lead_id']}` — **Reason:** {a['reason']}")
            st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — GOVERNANCE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_gov:
    st.header("🔍 Governance Audit")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Sends Without Approval")
        violations = sends_without_approval()
        if not violations:
            st.success("✅ Zero unapproved sends — all outbound actions are authorised.")
        else:
            st.error(f"🚨 {len(violations)} violation(s) detected!")
            for v in violations:
                st.json(v)

    with col2:
        st.subheader("Injection Detections")
        injections = [e for e in query_log() if e.get("injection_detected")]
        if not injections:
            st.info("No injection attempts logged.")
        else:
            st.warning(f"⚠️ {len(injections)} injection attempt(s) detected.")
            for inj in injections:
                st.json(inj)

    st.markdown("---")
    st.subheader("Full Audit Log")
    
    # Filters row
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filter_lead = st.text_input("Filter by lead_id (leave blank for all)")
    with col_f2:
        filter_stage = st.text_input("Filter by stage (leave blank for all)")
    with col_f3:
        filter_classification = st.selectbox(
            "Filter by classification", 
            options=["All", "HOT", "NURTURE", "DISQUALIFY"],
            index=0
        )

    # Apply filters
    classification_filter = None if filter_classification == "All" else filter_classification
    
    log_entries = query_log(
        lead_id=filter_lead or None,
        stage=filter_stage or None,
        classification=classification_filter,
    )
    
    st.caption(f"{len(log_entries)} entries")
    
    # Display entries in a table format for better readability
    if log_entries:
        # Create a summary table
        table_data = []
        for entry in reversed(log_entries):  # Show most recent first
            table_data.append({
                "Timestamp": entry.get('timestamp', 'N/A')[:19].replace('T', ' '),
                "Lead ID": entry.get('lead_id', 'N/A'),
                "Stage": entry.get('stage', 'N/A'),
                "Email": entry.get('email', 'N/A'),
                "Classification": entry.get('classification', 'N/A'),
                "Injection": "⚠️" if entry.get('injection_detected') else "",
                "Gate Decision": entry.get('gate_decision', 'N/A'),
                "Authorized By": entry.get('authorized_by', 'N/A'),
            })
        
        # Show table
        import pandas as pd
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True)
        
        st.markdown("---")
        st.subheader("Detailed Entry View")
        st.caption("Click to expand individual entries for full details")
        
        # Detailed expandable entries
        for entry in reversed(log_entries):
            email_display = f" | {entry.get('email', 'N/A')}" if entry.get('email') else ""
            classification_display = f" | {entry.get('classification', 'N/A')}" if entry.get('classification') else ""
            with st.expander(
                f"{entry['timestamp']} | {entry['stage']} | lead: {entry['lead_id']}{email_display}{classification_display}"
            ):
                st.json(entry)
    else:
        st.info("No log entries found matching the current filters.")
