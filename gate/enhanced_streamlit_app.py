"""
Enhanced Streamlit Application for LQOA with Authentication & Role-Based Access
Features: JWT authentication, real-time updates, role-based UI components, admin panel
"""

import sys
import os
import pandas as pd
import streamlit as st
import requests
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import core modules
from orchestrator import LeadState, run_pipeline
from database.connection import get_database_session
from database.repositories import UserRepository, LeadRepository, ApprovalRepository, GovernanceRepository
from database.models import User, Lead
from auth.security import verify_token, create_access_token, verify_password, hash_password
from governance.logger import query_log
from monitoring.error_handler import handle_error, log_info

# ── Page Configuration ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="LQOA - Lead Qualification & Outreach Agent",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Authentication Functions ────────────────────────────────────────────────
def initialize_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'token' not in st.session_state:
        st.session_state.token = None

def login_user(username: str, password: str) -> bool:
    """Authenticate user and set session state"""
    try:
        with get_database_session() as session:
            user_repo = UserRepository(session)
            user = user_repo.authenticate(username, password)
            
            if user and user.is_active:
                # Create JWT token
                token = create_access_token(data={"sub": user.id})
                
                # Set session state
                st.session_state.authenticated = True
                st.session_state.user = {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role
                }
                st.session_state.token = token
                
                log_info(f"User {username} logged in successfully", {"user_id": user.id, "role": user.role})
                return True
    except Exception as e:
        handle_error(e, {"action": "login", "username": username})
    
    return False

def logout_user():
    """Clear session state and logout user"""
    if st.session_state.user:
        log_info(f"User {st.session_state.user['username']} logged out", {"user_id": st.session_state.user['id']})
    
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.token = None

def check_permission(required_roles: List[str]) -> bool:
    """Check if current user has required role"""
    if not st.session_state.authenticated or not st.session_state.user:
        return False
    return st.session_state.user["role"] in required_roles

def require_auth(required_roles: List[str] = None):
    """Decorator to require authentication and optionally specific roles"""
    if not st.session_state.authenticated:
        st.error("🔒 Authentication required. Please login to continue.")
        st.stop()
    
    if required_roles and not check_permission(required_roles):
        st.error(f"🚫 Access denied. Required roles: {', '.join(required_roles)}")
        st.stop()

# ── UI Components ───────────────────────────────────────────────────────────
def render_login_form():
    """Render login form"""
    st.markdown("## 🔐 Login to LQOA")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            if username and password:
                if login_user(username, password):
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password")
            else:
                st.error("Please enter both username and password")

def render_sidebar():
    """Render sidebar with user info and navigation"""
    if st.session_state.authenticated:
        user = st.session_state.user
        
        st.sidebar.markdown(f"""
        ### 👤 Welcome, {user['username']}
        **Role:** {user['role'].title()}  
        **Email:** {user.get('email', 'N/A')}
        """)
        
        if st.sidebar.button("🚪 Logout"):
            logout_user()
            st.rerun()
        
        st.sidebar.markdown("---")
        
        # Role-based navigation info
        st.sidebar.markdown("### 🎯 Available Features")
        
        if user['role'] == 'admin':
            st.sidebar.markdown("""
            - 📥 Submit & Process Leads
            - 🔥 Approval Queue Management
            - 📊 Analytics & Insights
            - 🔍 Governance & Audit Logs
            - ⚙️ User Management
            - 🌱 All Lead Queues
            """)
        elif user['role'] == 'reviewer':
            st.sidebar.markdown("""
            - 📥 Submit & Process Leads
            - 🔥 Approval Queue Management
            - 🔍 Governance & Audit Logs
            - 🌱 All Lead Queues
            """)
        else:  # viewer
            st.sidebar.markdown("""
            - 📥 Submit & Process Leads
            - 🌱 View Lead Queues (Read-only)
            """)

def render_lead_form():
    """Render new lead submission form"""
    st.markdown("## 📥 Submit New Lead")
    
    with st.form("lead_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            first_name = st.text_input("First Name *", placeholder="John")
            last_name = st.text_input("Last Name *", placeholder="Doe")
            email = st.text_input("Email *", placeholder="john.doe@company.com")
            phone = st.text_input("Phone", placeholder="+1 (555) 123-4567")
        
        with col2:
            company = st.text_input("Company *", placeholder="Acme Corp")
            job_title = st.text_input("Job Title *", placeholder="VP of Engineering")
            website = st.text_input("Website", placeholder="https://company.com")
        
        message = st.text_area("Message", 
                              placeholder="I'm interested in learning more about your solution...",
                              height=100)
        
        submitted = st.form_submit_button("🚀 Process Lead", use_container_width=True)
        
        if submitted:
            # Validate required fields
            if not all([first_name, last_name, email, company, job_title]):
                st.error("❌ Please fill in all required fields (marked with *)")
                return
            
            # Create lead state
            lead_state = LeadState(
                id=str(uuid.uuid4()),
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                email=email.strip().lower(),
                company=company.strip(),
                job_title=job_title.strip(),
                phone=phone.strip(),
                website=website.strip(),
                message=message.strip(),
                submitted_by=st.session_state.user["id"]
            )
            
            # Process lead
            with st.spinner("🔄 Processing lead through pipeline..."):
                try:
                    result = run_pipeline(lead_state)
                    
                    # Store in database
                    with get_database_session() as session:
                        lead_repo = LeadRepository(session)
                        lead = lead_repo.create_from_state(result)
                        session.commit()
                    
                    # Show results
                    st.success("✅ Lead processed successfully!")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Classification", result.classification)
                    with col2:
                        st.metric("Score", f"{result.score:.2f}" if result.score else "N/A")
                    with col3:
                        status_color = {"HOT": "🔥", "NURTURE": "🌱", "DISQUALIFY": "❌"}
                        st.metric("Status", f"{status_color.get(result.classification, '❓')} {result.classification}")
                    
                    if result.classification == "HOT":
                        st.info("🔥 This lead is classified as HOT and needs approval in the Approval Queue!")
                    elif result.classification == "NURTURE":
                        st.info("🌱 This lead has been enrolled in the nurture sequence.")
                    else:
                        st.info("❌ This lead has been disqualified and archived.")
                
                except Exception as e:
                    st.error(f"❌ Error processing lead: {str(e)}")
                    handle_error(e, {"lead_data": lead_state.__dict__})

def render_approval_queue():
    """Render approval queue for HOT leads"""
    require_auth(["admin", "reviewer"])
    
    st.markdown("## 🔥 Approval Queue")
    
    # Get pending leads
    with get_database_session() as session:
        lead_repo = LeadRepository(session)
        pending_leads = lead_repo.get_pending_approval()
    
    if not pending_leads:
        st.info("✅ No leads pending approval")
        return
    
    st.markdown(f"**{len(pending_leads)} leads pending approval**")
    
    for lead in pending_leads:
        with st.expander(f"🔥 {lead.first_name} {lead.last_name} - {lead.company}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"""
                **Email:** {lead.email}  
                **Job Title:** {lead.job_title}  
                **Score:** {lead.score:.2f}  
                **Submitted:** {lead.created_at.strftime('%Y-%m-%d %H:%M')}
                """)
                
                if lead.message:
                    st.markdown(f"**Message:** {lead.message}")
            
            with col2:
                st.markdown("### 📧 Draft Email")
                
                # Editable draft email
                draft_key = f"draft_{lead.id}"
                if draft_key not in st.session_state:
                    st.session_state[draft_key] = lead.draft_email or "No draft available"
                
                edited_draft = st.text_area(
                    "Edit draft email:",
                    value=st.session_state[draft_key],
                    height=200,
                    key=f"edit_{lead.id}"
                )
                st.session_state[draft_key] = edited_draft
                
                # Approval buttons
                col_approve, col_reject = st.columns(2)
                
                with col_approve:
                    if st.button("✅ Approve", key=f"approve_{lead.id}"):
                        approve_lead(lead.id, "approve", edited_draft)
                        st.rerun()
                
                with col_reject:
                    if st.button("❌ Reject", key=f"reject_{lead.id}"):
                        approve_lead(lead.id, "reject", None)
                        st.rerun()

def approve_lead(lead_id: str, action: str, content: str = None):
    """Approve or reject a lead"""
    try:
        with get_database_session() as session:
            lead_repo = LeadRepository(session)
            approval_repo = ApprovalRepository(session)
            
            # Create approval record
            approval = approval_repo.create_approval(
                lead_id=lead_id,
                approver_id=st.session_state.user["id"],
                action=action,
                original_content=None,
                approved_content=content
            )
            
            # Update lead status
            new_status = "approved" if action == "approve" else "rejected"
            lead_repo.update_status(lead_id, new_status)
            
            st.success(f"✅ Lead {action}d successfully!")
            
    except Exception as e:
        st.error(f"❌ Error processing approval: {str(e)}")
        handle_error(e, {"lead_id": lead_id, "action": action})

def render_analytics():
    """Render analytics dashboard - admin only"""
    require_auth(["admin"])
    
    st.markdown("## 📊 Analytics Dashboard")
    
    try:
        with get_database_session() as session:
            lead_repo = LeadRepository(session)
            analytics = lead_repo.get_analytics_summary()
        
        # Metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Leads", analytics["total_leads"])
        with col2:
            st.metric("HOT Leads", analytics["classifications"]["HOT"])
        with col3:
            st.metric("NURTURE Leads", analytics["classifications"]["NURTURE"])
        with col4:
            st.metric("Disqualified", analytics["classifications"]["DISQUALIFY"])
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Classification Distribution")
            classification_data = pd.DataFrame([
                {"Classification": k, "Count": v} 
                for k, v in analytics["classifications"].items()
            ])
            if not classification_data.empty:
                st.bar_chart(classification_data.set_index("Classification"))
        
        with col2:
            st.markdown("### Status Distribution")
            status_data = pd.DataFrame([
                {"Status": k.replace("_", " ").title(), "Count": v} 
                for k, v in analytics["statuses"].items()
            ])
            if not status_data.empty:
                st.bar_chart(status_data.set_index("Status"))
        
    except Exception as e:
        st.error(f"❌ Error loading analytics: {str(e)}")
        handle_error(e, {"component": "analytics"})

def render_governance():
    """Render governance and audit logs"""
    require_auth(["admin", "reviewer"])
    
    st.markdown("## 🔍 Governance & Audit Logs")
    
    try:
        # Get recent governance events
        governance_events = query_log(limit=50)
        
        if governance_events:
            st.markdown(f"**{len(governance_events)} recent events**")
            
            # Convert to DataFrame for display
            events_data = []
            for event in governance_events:
                events_data.append({
                    "Timestamp": event.get("timestamp", "N/A"),
                    "Event": event.get("event", "N/A"),
                    "User": event.get("user_id", "N/A"),
                    "Lead ID": event.get("lead_id", "N/A"),
                    "Details": str(event.get("details", ""))[:100] + "..." if len(str(event.get("details", ""))) > 100 else str(event.get("details", ""))
                })
            
            df = pd.DataFrame(events_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No governance events found")
    
    except Exception as e:
        st.error(f"❌ Error loading governance data: {str(e)}")
        handle_error(e, {"component": "governance"})

def render_admin_panel():
    """Render admin panel - admin only"""
    require_auth(["admin"])
    
    st.markdown("## ⚙️ Administration")
    
    tab1, tab2 = st.tabs(["👥 Users", "🔧 System"])
    
    with tab1:
        st.markdown("### User Management")
        
        try:
            with get_database_session() as session:
                user_repo = UserRepository(session)
                users = user_repo.get_all_users()
            
            # Display users
            users_data = []
            for user in users:
                users_data.append({
                    "Username": user.username,
                    "Email": user.email or "N/A",
                    "Role": user.role,
                    "Status": "Active" if user.is_active else "Inactive",
                    "Created": user.created_at.strftime('%Y-%m-%d') if user.created_at else "N/A",
                    "Last Login": user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else "Never"
                })
            
            df = pd.DataFrame(users_data)
            st.dataframe(df, use_container_width=True)
            
            # Create new user
            st.markdown("### Create New User")
            with st.form("create_user_form"):
                col1, col2 = st.columns(2)
                with col1:
                    new_username = st.text_input("Username")
                    new_email = st.text_input("Email")
                with col2:
                    new_password = st.text_input("Password", type="password")
                    new_role = st.selectbox("Role", ["viewer", "reviewer", "admin"])
                
                if st.form_submit_button("Create User"):
                    if new_username and new_password:
                        try:
                            with get_database_session() as session:
                                user_repo = UserRepository(session)
                                user_repo.create_user(new_username, new_password, new_email, new_role)
                            st.success("✅ User created successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error creating user: {str(e)}")
                    else:
                        st.error("Username and password are required")
        
        except Exception as e:
            st.error(f"❌ Error loading users: {str(e)}")
            handle_error(e, {"component": "admin_users"})
    
    with tab2:
        st.markdown("### System Information")
        
        # System health
        from monitoring.error_handler import get_system_health
        health = get_system_health()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Database", "✅ Healthy" if health["database"] else "❌ Error")
        with col2:
            st.metric("Redis", "✅ Healthy" if health["redis"] else "❌ Error")
        
        # Environment info
        st.markdown("### Environment Variables")
        env_vars = {
            "Environment": os.getenv("ENVIRONMENT", "development"),
            "Debug Mode": os.getenv("DEBUG", "false"),
            "Database URL": "***" + (os.getenv("DATABASE_URL", "")[-20:] if os.getenv("DATABASE_URL") else "Not set"),
            "Enrichment Provider": os.getenv("ENRICHMENT_PROVIDER", "mock"),
            "OpenAI Configured": "Yes" if os.getenv("OPENAI_API_KEY") else "No"
        }
        
        for key, value in env_vars.items():
            st.text(f"{key}: {value}")

# ── Main Application ────────────────────────────────────────────────────────
def main():
    """Main application logic"""
    initialize_session_state()
    
    # Show login form if not authenticated
    if not st.session_state.authenticated:
        render_login_form()
        return
    
    # Render sidebar
    render_sidebar()
    
    # Main content tabs
    user_role = st.session_state.user["role"]
    
    # Define tabs based on role
    if user_role == "admin":
        tabs = ["📥 New Lead", "🔥 Approval Queue", "🌱 Nurture", "🗂️ Disqualified", 
               "📊 Analytics", "🔍 Governance", "⚙️ Admin"]
    elif user_role == "reviewer":
        tabs = ["📥 New Lead", "🔥 Approval Queue", "🌱 Nurture", "🗂️ Disqualified", 
               "🔍 Governance"]
    else:  # viewer
        tabs = ["📥 New Lead", "🌱 Nurture", "🗂️ Disqualified"]
    
    selected_tab = st.tabs(tabs)
    
    with selected_tab[0]:  # New Lead
        render_lead_form()
    
    if len(selected_tab) > 1:
        with selected_tab[1]:  # Approval Queue or Nurture (depending on role)
            if user_role in ["admin", "reviewer"]:
                render_approval_queue()
            else:
                st.info("🌱 Nurture queue - view only access")
    
    if len(selected_tab) > 2:
        with selected_tab[2]:  # Nurture or Disqualified
            st.info("🌱 Nurture queue - feature in development")
    
    if len(selected_tab) > 3:
        with selected_tab[3]:  # Disqualified
            st.info("🗂️ Disqualified leads - feature in development")
    
    if user_role == "admin":
        if len(selected_tab) > 4:
            with selected_tab[4]:  # Analytics
                render_analytics()
        
        if len(selected_tab) > 5:
            with selected_tab[5]:  # Governance
                render_governance()
        
        if len(selected_tab) > 6:
            with selected_tab[6]:  # Admin
                render_admin_panel()
    
    elif user_role == "reviewer" and len(selected_tab) > 4:
        with selected_tab[4]:  # Governance
            render_governance()

if __name__ == "__main__":
    main()