"""
FastAPI application for Lead Qualification & Outreach Agent (LQOA)
Provides REST API endpoints for the pipeline with authentication and RBAC.
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import sys
import asyncio
from datetime import datetime
import uuid

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager

from database.connection import get_database_session
from database.models import User, Lead, ApprovalRecord
from database.repositories import UserRepository, LeadRepository, ApprovalRepository
from database.init_db import init_database
from auth.security import verify_token, hash_password, create_access_token
from orchestrator import run_pipeline, LeadState
from monitoring.error_handler import handle_error
from governance.logger import log_event

# ── Startup / shutdown lifecycle ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run DB init on startup so no pre-deploy command is needed."""
    try:
        init_database()
        print("✓ Database initialized on startup")
    except Exception as e:
        print(f"⚠ Database init warning (may already exist): {e}")
    yield  # app runs here
    # shutdown logic can go here if needed

# Initialize FastAPI app
app = FastAPI(
    title="Lead Qualification & Outreach Agent API",
    description="Production-ready lead processing pipeline with human approval gates",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Pydantic models
class LeadInput(BaseModel):
    first_name: str
    last_name: str
    email: str
    company: str
    job_title: str
    message: Optional[str] = ""
    phone: Optional[str] = ""
    website: Optional[str] = ""

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    username: str
    role: str

class LeadResponse(BaseModel):
    id: str
    status: str
    classification: Optional[str]
    score: Optional[float]
    created_at: datetime

class ApprovalRequest(BaseModel):
    lead_id: str
    action: str  # "approve", "reject", "approve_edited"
    edited_content: Optional[str] = None

# Dependencies
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token and return current user"""
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    with get_database_session() as session:
        user_repo = UserRepository(session)
        user = user_repo.get_by_id(payload.get("sub"))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
    return user

def require_role(required_roles: List[str]):
    """Decorator to require specific roles"""
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {required_roles}",
            )
        return current_user
    return role_checker

# Routes
@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "LQOA API", "timestamp": datetime.utcnow()}

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user and return JWT token"""
    try:
        with get_database_session() as session:
            user_repo = UserRepository(session)
            user = user_repo.authenticate(request.username, request.password)
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password",
                )
            
            # Create access token
            access_token = create_access_token(data={"sub": user.id})
            
            return LoginResponse(
                access_token=access_token,
                token_type="bearer",
                user_id=user.id,
                username=user.username,
                role=user.role
            )
    except Exception as e:
        handle_error(e, {"endpoint": "/api/auth/login", "username": request.username})
        raise HTTPException(status_code=500, detail="Authentication failed")

@app.post("/api/leads", response_model=LeadResponse)
async def submit_lead(
    lead_data: LeadInput,
    current_user: User = Depends(get_current_user)
):
    """Submit a new lead and run it through the pipeline"""
    try:
        # Create lead state
        lead_state = LeadState(
            id=str(uuid.uuid4()),
            first_name=lead_data.first_name,
            last_name=lead_data.last_name,
            email=lead_data.email,
            company=lead_data.company,
            job_title=lead_data.job_title,
            message=lead_data.message or "",
            phone=lead_data.phone or "",
            website=lead_data.website or "",
            submitted_by=current_user.id
        )
        
        # Run pipeline
        result = run_pipeline(lead_state)
        
        # Store in database
        with get_database_session() as session:
            lead_repo = LeadRepository(session)
            lead = lead_repo.create_from_state(result)
            session.commit()
        
        # Log governance event
        log_event(
            lead_id=lead.id,
            stage="lead_submitted",
            extra={
                "user_id": current_user.id,
                "classification": result.classification,
                "score": result.score,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        return LeadResponse(
            id=lead.id,
            status=lead.status,
            classification=result.classification,
            score=result.score,
            created_at=lead.created_at
        )
        
    except Exception as e:
        handle_error(e, {"endpoint": "/api/leads", "lead_data": lead_data.dict()})
        raise HTTPException(status_code=500, detail="Failed to process lead")

@app.get("/api/leads", response_model=List[LeadResponse])
async def get_leads(
    status: Optional[str] = None,
    classification: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
):
    """Get leads with optional filtering"""
    try:
        with get_database_session() as session:
            lead_repo = LeadRepository(session)
            leads = lead_repo.get_filtered(
                status=status,
                classification=classification,
                limit=limit
            )
            
        return [
            LeadResponse(
                id=lead.id,
                status=lead.status,
                classification=lead.classification,
                score=lead.score,
                created_at=lead.created_at
            )
            for lead in leads
        ]
        
    except Exception as e:
        handle_error(e, {"endpoint": "/api/leads"})
        raise HTTPException(status_code=500, detail="Failed to retrieve leads")

@app.get("/api/leads/pending-approval", response_model=List[Dict[str, Any]])
async def get_pending_approvals(
    current_user: User = Depends(require_role(["admin", "reviewer"]))
):
    """Get leads pending approval (HOT leads)"""
    try:
        with get_database_session() as session:
            lead_repo = LeadRepository(session)
            pending_leads = lead_repo.get_filtered(
                status="pending_approval",
                classification="HOT"
            )
            
        return [
            {
                "id": lead.id,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "email": lead.email,
                "company": lead.company,
                "job_title": lead.job_title,
                "score": lead.score,
                "draft_email": lead.draft_email,
                "created_at": lead.created_at,
                "enrichment_data": lead.enrichment_data
            }
            for lead in pending_leads
        ]
        
    except Exception as e:
        handle_error(e, {"endpoint": "/api/leads/pending-approval"})
        raise HTTPException(status_code=500, detail="Failed to retrieve pending approvals")

@app.post("/api/leads/approve")
async def approve_lead(
    request: ApprovalRequest,
    current_user: User = Depends(require_role(["admin", "reviewer"]))
):
    """Approve, reject, or approve with edits a lead"""
    try:
        with get_database_session() as session:
            lead_repo = LeadRepository(session)
            approval_repo = ApprovalRepository(session)
            
            lead = lead_repo.get_by_id(request.lead_id)
            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")
            
            if lead.status != "pending_approval":
                raise HTTPException(status_code=400, detail="Lead is not pending approval")
            
            # Create approval record
            approval_record = approval_repo.create_approval(
                lead_id=request.lead_id,
                approver_id=current_user.id,
                action=request.action,
                original_content=lead.draft_email,
                approved_content=request.edited_content or lead.draft_email
            )
            
            # Update lead status
            if request.action == "reject":
                lead.status = "rejected"
            else:
                lead.status = "approved"
                if request.edited_content:
                    lead.draft_email = request.edited_content
            
            session.commit()
            
            # Log governance event
            log_event(
                lead_id=request.lead_id,
                stage="lead_approval",
                extra={
                    "approver_id": current_user.id,
                    "action": request.action,
                    "approval_id": approval_record.id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
        return {"message": f"Lead {request.action}d successfully", "approval_id": approval_record.id}
        
    except HTTPException:
        raise
    except Exception as e:
        handle_error(e, {"endpoint": "/api/leads/approve", "request": request.dict()})
        raise HTTPException(status_code=500, detail="Failed to process approval")

@app.get("/api/analytics/summary")
async def get_analytics_summary(
    current_user: User = Depends(require_role(["admin"]))
):
    """Get analytics summary - admin only"""
    try:
        with get_database_session() as session:
            lead_repo = LeadRepository(session)
            
            # Get counts by classification
            hot_count = len(lead_repo.get_filtered(classification="HOT"))
            nurture_count = len(lead_repo.get_filtered(classification="NURTURE"))
            disqualified_count = len(lead_repo.get_filtered(classification="DISQUALIFY"))
            
            # Get counts by status
            pending_count = len(lead_repo.get_filtered(status="pending_approval"))
            approved_count = len(lead_repo.get_filtered(status="approved"))
            rejected_count = len(lead_repo.get_filtered(status="rejected"))
            
        return {
            "classifications": {
                "HOT": hot_count,
                "NURTURE": nurture_count,
                "DISQUALIFY": disqualified_count
            },
            "statuses": {
                "pending_approval": pending_count,
                "approved": approved_count,
                "rejected": rejected_count
            },
            "total_leads": hot_count + nurture_count + disqualified_count
        }
        
    except Exception as e:
        handle_error(e, {"endpoint": "/api/analytics/summary"})
        raise HTTPException(status_code=500, detail="Failed to retrieve analytics")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)