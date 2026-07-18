#!/usr/bin/env python3
"""
LQOA Deployment Validation Script
Checks all components are in place for successful deployment
"""

import os
import sys
import importlib.util
from pathlib import Path

def check_file_exists(path: str, description: str) -> bool:
    """Check if a file exists"""
    if os.path.exists(path):
        print(f"✅ {description}: {path}")
        return True
    else:
        print(f"❌ {description}: {path} - NOT FOUND")
        return False

def check_directory_exists(path: str, description: str) -> bool:
    """Check if a directory exists"""
    if os.path.isdir(path):
        print(f"✅ {description}: {path}")
        return True
    else:
        print(f"❌ {description}: {path} - NOT FOUND")
        return False

def check_import(module_name: str, description: str) -> bool:
    """Check if a module can be imported"""
    try:
        __import__(module_name)
        print(f"✅ {description}: {module_name}")
        return True
    except ImportError as e:
        print(f"❌ {description}: {module_name} - IMPORT ERROR: {e}")
        return False

def main():
    """Run all validation checks"""
    print("🔍 LQOA Deployment Validation")
    print("=" * 50)
    
    checks_passed = 0
    total_checks = 0
    
    # Core deployment files
    files_to_check = [
        ("render.yaml", "Render configuration"),
        ("requirements.txt", "Python dependencies"),
        ("alembic.ini", "Database migrations config"),
        (".env.example", "Environment variables template"),
        ("RENDER_DEPLOYMENT.md", "Deployment guide"),
    ]
    
    print("\n📁 Core Deployment Files:")
    for file_path, description in files_to_check:
        total_checks += 1
        if check_file_exists(file_path, description):
            checks_passed += 1
    
    # API and application files
    api_files = [
        ("api/main.py", "FastAPI application"),
        ("gate/enhanced_streamlit_app.py", "Enhanced Streamlit UI"),
        ("orchestrator.py", "Pipeline orchestrator"),
        ("llm_client.py", "LLM client"),
    ]
    
    print("\n🚀 Application Files:")
    for file_path, description in api_files:
        total_checks += 1
        if check_file_exists(file_path, description):
            checks_passed += 1
    
    # Database components
    db_files = [
        ("database/models.py", "Database models"),
        ("database/connection.py", "Database connection"),
        ("database/repositories.py", "Data repositories"),
        ("database/init_db.py", "Database initialization"),
        ("database/migrations/env.py", "Alembic environment"),
    ]
    
    print("\n🗄️ Database Components:")
    for file_path, description in db_files:
        total_checks += 1
        if check_file_exists(file_path, description):
            checks_passed += 1
    
    # Authentication and security
    auth_files = [
        ("auth/security.py", "Authentication & security"),
        ("monitoring/error_handler.py", "Error handling & monitoring"),
    ]
    
    print("\n🔐 Security Components:")
    for file_path, description in auth_files:
        total_checks += 1
        if check_file_exists(file_path, description):
            checks_passed += 1
    
    # Agent modules
    agent_files = [
        ("agents/enrichment.py", "Enrichment agent"),
        ("agents/scoring.py", "Scoring agent"),
        ("agents/classification.py", "Classification agent"),
        ("agents/routing.py", "Routing agent"),
        ("agents/drafting.py", "Drafting agent"),
    ]
    
    print("\n🤖 Agent Modules:")
    for file_path, description in agent_files:
        total_checks += 1
        if check_file_exists(file_path, description):
            checks_passed += 1
    
    # Tool modules
    tool_files = [
        ("tools/enrichment_lookup.py", "Enrichment lookup tool"),
        ("tools/email_send.py", "Email sending tool"),
        ("tools/sequence_enroll.py", "Sequence enrollment tool"),
        ("tools/archive_lead.py", "Lead archiving tool"),
        ("tools/crm_write.py", "CRM writing tool"),
    ]
    
    print("\n🛠️ Tool Modules:")
    for file_path, description in tool_files:
        total_checks += 1
        if check_file_exists(file_path, description):
            checks_passed += 1
    
    # Configuration files
    config_files = [
        ("config/icp_config.json", "ICP configuration"),
    ]
    
    print("\n⚙️ Configuration Files:")
    for file_path, description in config_files:
        total_checks += 1
        if check_file_exists(file_path, description):
            checks_passed += 1
    
    # Governance and logging
    governance_files = [
        ("governance/logger.py", "Governance logger"),
    ]
    
    print("\n📋 Governance Components:")
    for file_path, description in governance_files:
        total_checks += 1
        if check_file_exists(file_path, description):
            checks_passed += 1
    
    # Directories
    directories = [
        ("database/migrations/versions", "Migration versions directory"),
        ("logs", "Logs directory (auto-created)"),
    ]
    
    print("\n📂 Required Directories:")
    for dir_path, description in directories:
        total_checks += 1
        if check_directory_exists(dir_path, description) or dir_path == "logs":
            checks_passed += 1
    
    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Validation Summary: {checks_passed}/{total_checks} checks passed")
    
    if checks_passed == total_checks:
        print("🎉 ✅ ALL CHECKS PASSED - Ready for deployment!")
        print("\n🚀 Next steps:")
        print("1. Push code to GitHub repository")
        print("2. Create Render services as per RENDER_DEPLOYMENT.md")
        print("3. Configure environment variables")
        print("4. Deploy and test!")
        return True
    else:
        print("❌ Some checks failed - please review missing components")
        missing = total_checks - checks_passed
        print(f"⚠️ {missing} component(s) missing or have issues")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)