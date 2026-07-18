"""
SQLAlchemy database models for Lead Qualification & Outreach Agent (LQOA)
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    """User model for authentication and authorization"""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="viewer")  # admin, reviewer, viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    submitted_leads = relationship("Lead", back_populates="submitted_by_user", foreign_keys="Lead.submitted_by")
    approvals = relationship("ApprovalRecord", back_populates="approver")
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"

class Lead(Base):
    """Lead model for storing lead information and pipeline results"""
    __tablename__ = "leads"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Basic lead information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(200), nullable=False, index=True)
    company = Column(String(200), nullable=False)
    job_title = Column(String(200), nullable=False)
    phone = Column(String(50), nullable=True)
    website = Column(String(200), nullable=True)
    message = Column(Text, nullable=True)
    
    # Pipeline processing results
    status = Column(String(50), nullable=False, default="processing")  # processing, pending_approval, approved, rejected, archived
    classification = Column(String(20), nullable=True)  # HOT, NURTURE, DISQUALIFY
    score = Column(Float, nullable=True)
    score_rationale = Column(Text, nullable=True)
    
    # Enrichment data
    enrichment_data = Column(JSON, nullable=True)
    enrichment_provider = Column(String(50), nullable=True)
    
    # Email draft and approval
    draft_email = Column(Text, nullable=True)
    
    # Audit fields
    submitted_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Security and injection detection
    injection_detected = Column(Boolean, default=False)
    sanitized_message = Column(Text, nullable=True)
    
    # Relationships
    submitted_by_user = relationship("User", back_populates="submitted_leads", foreign_keys=[submitted_by])
    approval_records = relationship("ApprovalRecord", back_populates="lead")
    
    def __repr__(self):
        return f"<Lead(id={self.id}, email={self.email}, classification={self.classification})>"

class ApprovalRecord(Base):
    """Approval record model for human gate tracking"""
    __tablename__ = "approval_records"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    approver_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Approval action and content
    action = Column(String(20), nullable=False)  # approve, reject, approve_edited
    original_content = Column(Text, nullable=True)
    approved_content = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=True)  # SHA-256 hash for verification
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text, nullable=True)
    
    # Relationships
    lead = relationship("Lead", back_populates="approval_records")
    approver = relationship("User", back_populates="approvals")
    
    def __repr__(self):
        return f"<ApprovalRecord(id={self.id}, lead_id={self.lead_id}, action={self.action})>"

class GovernanceLog(Base):
    """Governance log for audit trail"""
    __tablename__ = "governance_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(50), nullable=False)
    lead_id = Column(String, nullable=True)
    user_id = Column(String, nullable=True)
    
    # Event data
    event_data = Column(JSON, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Additional context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    def __repr__(self):
        return f"<GovernanceLog(id={self.id}, event_type={self.event_type}, timestamp={self.timestamp})>"

class CacheEntry(Base):
    """Cache entry model for Redis fallback and persistence"""
    __tablename__ = "cache_entries"
    
    id = Column(String, primary_key=True)
    data = Column(JSON, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<CacheEntry(id={self.id}, expires_at={self.expires_at})>"