"""
Database repositories for data access layer
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from typing import List, Optional, Dict, Any
from datetime import datetime
import hashlib

from .models import User, Lead, ApprovalRecord, GovernanceLog, CacheEntry
from auth.security import verify_password, hash_password

class UserRepository:
    """Repository for User operations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return self.session.query(User).filter(User.id == user_id).first()
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self.session.query(User).filter(User.username == username).first()
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.session.query(User).filter(User.email == email).first()
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password"""
        user = self.get_by_username(username)
        if user and verify_password(password, user.hashed_password):
            # Update last login
            user.last_login = datetime.utcnow()
            self.session.commit()
            return user
        return None
    
    def create_user(self, username: str, password: str, email: str = None, role: str = "viewer") -> User:
        """Create a new user"""
        hashed_password = hash_password(password)
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            role=role
        )
        self.session.add(user)
        self.session.commit()
        return user
    
    def update_password(self, user_id: str, new_password: str) -> bool:
        """Update user password"""
        user = self.get_by_id(user_id)
        if user:
            user.hashed_password = hash_password(new_password)
            self.session.commit()
            return True
        return False
    
    def get_all_users(self) -> List[User]:
        """Get all users"""
        return self.session.query(User).order_by(User.username).all()
    
    def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user"""
        user = self.get_by_id(user_id)
        if user:
            user.is_active = False
            self.session.commit()
            return True
        return False

class LeadRepository:
    """Repository for Lead operations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, lead_id: str) -> Optional[Lead]:
        """Get lead by ID"""
        return self.session.query(Lead).filter(Lead.id == lead_id).first()
    
    def get_by_email(self, email: str) -> Optional[Lead]:
        """Get lead by email"""
        return self.session.query(Lead).filter(Lead.email == email).first()
    
    def create_from_state(self, lead_state) -> Lead:
        """Create lead from LeadState object"""
        lead = Lead(
            id=lead_state.id,
            first_name=lead_state.first_name,
            last_name=lead_state.last_name,
            email=lead_state.email,
            company=lead_state.company,
            job_title=lead_state.job_title,
            phone=getattr(lead_state, 'phone', ''),
            website=getattr(lead_state, 'website', ''),
            message=getattr(lead_state, 'message', ''),
            status=getattr(lead_state, 'status', 'processing'),
            classification=getattr(lead_state, 'classification', None),
            score=getattr(lead_state, 'score', None),
            score_rationale=getattr(lead_state, 'score_rationale', None),
            enrichment_data=getattr(lead_state, 'enrichment_data', None),
            enrichment_provider=getattr(lead_state, 'enrichment_provider', None),
            draft_email=getattr(lead_state, 'draft_email', None),
            submitted_by=getattr(lead_state, 'submitted_by', None),
            injection_detected=getattr(lead_state, 'injection_detected', False),
            sanitized_message=getattr(lead_state, 'sanitized_message', None),
            processed_at=datetime.utcnow()
        )
        self.session.add(lead)
        return lead
    
    def get_filtered(self, status: str = None, classification: str = None, 
                    submitted_by: str = None, limit: int = 100) -> List[Lead]:
        """Get leads with optional filtering"""
        query = self.session.query(Lead)
        
        if status:
            query = query.filter(Lead.status == status)
        if classification:
            query = query.filter(Lead.classification == classification)
        if submitted_by:
            query = query.filter(Lead.submitted_by == submitted_by)
        
        return query.order_by(desc(Lead.created_at)).limit(limit).all()
    
    def get_pending_approval(self) -> List[Lead]:
        """Get leads pending approval"""
        return self.session.query(Lead).filter(
            and_(
                Lead.status == "pending_approval",
                Lead.classification == "HOT"
            )
        ).order_by(desc(Lead.created_at)).all()
    
    def update_status(self, lead_id: str, status: str) -> bool:
        """Update lead status"""
        lead = self.get_by_id(lead_id)
        if lead:
            lead.status = status
            lead.updated_at = datetime.utcnow()
            self.session.commit()
            return True
        return False
    
    def get_analytics_summary(self) -> Dict[str, Any]:
        """Get analytics summary data"""
        total_leads = self.session.query(Lead).count()
        
        # Classification counts
        hot_count = self.session.query(Lead).filter(Lead.classification == "HOT").count()
        nurture_count = self.session.query(Lead).filter(Lead.classification == "NURTURE").count()
        disqualify_count = self.session.query(Lead).filter(Lead.classification == "DISQUALIFY").count()
        
        # Status counts
        pending_count = self.session.query(Lead).filter(Lead.status == "pending_approval").count()
        approved_count = self.session.query(Lead).filter(Lead.status == "approved").count()
        rejected_count = self.session.query(Lead).filter(Lead.status == "rejected").count()
        
        return {
            "total_leads": total_leads,
            "classifications": {
                "HOT": hot_count,
                "NURTURE": nurture_count,
                "DISQUALIFY": disqualify_count
            },
            "statuses": {
                "pending_approval": pending_count,
                "approved": approved_count,
                "rejected": rejected_count
            }
        }

class ApprovalRepository:
    """Repository for ApprovalRecord operations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, approval_id: str) -> Optional[ApprovalRecord]:
        """Get approval record by ID"""
        return self.session.query(ApprovalRecord).filter(ApprovalRecord.id == approval_id).first()
    
    def create_approval(self, lead_id: str, approver_id: str, action: str, 
                       original_content: str = None, approved_content: str = None,
                       notes: str = None) -> ApprovalRecord:
        """Create approval record"""
        # Generate content hash for verification
        content_hash = None
        if approved_content:
            content_hash = hashlib.sha256(approved_content.encode()).hexdigest()
        
        approval = ApprovalRecord(
            lead_id=lead_id,
            approver_id=approver_id,
            action=action,
            original_content=original_content,
            approved_content=approved_content,
            content_hash=content_hash,
            notes=notes
        )
        self.session.add(approval)
        self.session.commit()
        return approval
    
    def get_by_lead_id(self, lead_id: str) -> List[ApprovalRecord]:
        """Get approval records for a lead"""
        return self.session.query(ApprovalRecord).filter(
            ApprovalRecord.lead_id == lead_id
        ).order_by(desc(ApprovalRecord.created_at)).all()
    
    def verify_approval_hash(self, approval_id: str, content: str) -> bool:
        """Verify that content matches the approval hash"""
        approval = self.get_by_id(approval_id)
        if not approval or not approval.content_hash:
            return False
        
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return content_hash == approval.content_hash

class GovernanceRepository:
    """Repository for GovernanceLog operations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def log_event(self, event_type: str, event_data: Dict[str, Any] = None,
                  lead_id: str = None, user_id: str = None,
                  ip_address: str = None, user_agent: str = None) -> GovernanceLog:
        """Log a governance event"""
        log_entry = GovernanceLog(
            event_type=event_type,
            lead_id=lead_id,
            user_id=user_id,
            event_data=event_data,
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.session.add(log_entry)
        self.session.commit()
        return log_entry
    
    def get_events(self, event_type: str = None, lead_id: str = None,
                   user_id: str = None, limit: int = 100) -> List[GovernanceLog]:
        """Get governance events with optional filtering"""
        query = self.session.query(GovernanceLog)
        
        if event_type:
            query = query.filter(GovernanceLog.event_type == event_type)
        if lead_id:
            query = query.filter(GovernanceLog.lead_id == lead_id)
        if user_id:
            query = query.filter(GovernanceLog.user_id == user_id)
        
        return query.order_by(desc(GovernanceLog.timestamp)).limit(limit).all()

class CacheRepository:
    """Repository for cache operations (Redis fallback)"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        entry = self.session.query(CacheEntry).filter(CacheEntry.id == key).first()
        
        if not entry:
            return None
        
        # Check expiration
        if entry.expires_at and entry.expires_at < datetime.utcnow():
            self.session.delete(entry)
            self.session.commit()
            return None
        
        return entry.data
    
    def set(self, key: str, value: Any, expires_at: datetime = None) -> bool:
        """Set cached value"""
        # Remove existing entry
        existing = self.session.query(CacheEntry).filter(CacheEntry.id == key).first()
        if existing:
            self.session.delete(existing)
        
        # Create new entry
        entry = CacheEntry(
            id=key,
            data=value,
            expires_at=expires_at
        )
        self.session.add(entry)
        self.session.commit()
        return True
    
    def delete(self, key: str) -> bool:
        """Delete cached value"""
        entry = self.session.query(CacheEntry).filter(CacheEntry.id == key).first()
        if entry:
            self.session.delete(entry)
            self.session.commit()
            return True
        return False