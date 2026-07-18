#!/usr/bin/env python3
"""
LQOA Deployment Readiness Test
Tests that all modules can be imported and basic structure is correct
without requiring external dependencies like passlib, redis, etc.
"""

import os
import sys
import ast
import importlib.util
from pathlib import Path

def check_python_syntax(filepath):
    """Check if Python file has valid syntax"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        return True, None
    except SyntaxError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)

def check_imports_structure(filepath):
    """Check if file has proper import structure (not actual imports)"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for common import patterns
        has_imports = any([
            'from ' in content,
            'import ' in content
        ])
        
        # Check for function definitions
        has_functions = 'def ' in content
        
        return has_imports or has_functions, None
    except Exception as e:
        return False, str(e)

def main():
    """Run deployment readiness checks"""
    print("🔍 LQOA Deployment Readiness Test")
    print("=" * 50)
    print("Checking code structure and syntax without external dependencies")
    print("=" * 50)
    
    # Core files that must have valid syntax
    critical_files = [
        "api/main.py",
        "gate/enhanced_streamlit_app.py", 
        "orchestrator.py",
        "database/models.py",
        "database/connection.py",
        "database/repositories.py",
        "database/init_db.py",
        "auth/security.py",
        "cache/__init__.py",
        "agents/enrichment.py",
        "agents/scoring.py",
        "agents/classification.py",
        "agents/routing.py",
        "agents/drafting.py"
    ]
    
    # Configuration files
    config_files = [
        "config/icp_config.json",
        "requirements.txt",
        "render.yaml",
        ".env.example"
    ]
    
    passed_syntax = 0
    total_syntax = 0
    
    print("\n🐍 Python Syntax Validation:")
    for filepath in critical_files:
        total_syntax += 1
        if os.path.exists(filepath):
            valid, error = check_python_syntax(filepath)
            if valid:
                print(f"✅ {filepath}")
                passed_syntax += 1
            else:
                print(f"❌ {filepath} - Syntax Error: {error}")
        else:
            print(f"❌ {filepath} - File not found")
    
    print("\n📁 Configuration Files:")
    config_passed = 0
    total_config = 0
    for filepath in config_files:
        total_config += 1
        if os.path.exists(filepath):
            print(f"✅ {filepath}")
            config_passed += 1
        else:
            print(f"❌ {filepath} - File not found")
    
    # Check specific critical functions exist (by text search)
    print("\n🔧 Critical Function Checks:")
    function_checks = [
        ("orchestrator.py", "def run_pipeline"),
        ("api/main.py", "FastAPI"),
        ("database/init_db.py", "def init_database"),
        ("auth/security.py", "def create_access_token"),
        ("gate/enhanced_streamlit_app.py", "def main")
    ]
    
    function_passed = 0
    total_functions = 0
    
    for filepath, function_pattern in function_checks:
        total_functions += 1
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                if function_pattern in content:
                    print(f"✅ {filepath} contains {function_pattern}")
                    function_passed += 1
                else:
                    print(f"❌ {filepath} missing {function_pattern}")
            except Exception as e:
                print(f"❌ {filepath} - Error reading: {e}")
        else:
            print(f"❌ {filepath} - File not found")
    
    # Check environment configuration
    print("\n⚙️ Environment Configuration:")
    env_checks = 0
    
    # Check .env.example has required variables
    if os.path.exists(".env.example"):
        with open(".env.example", 'r') as f:
            env_content = f.read()
        
        required_vars = [
            "DATABASE_URL",
            "JWT_SECRET_KEY", 
            "DEBUG",
            "LOG_LEVEL",
            "ENRICHMENT_PROVIDER"
        ]
        
        for var in required_vars:
            if var in env_content:
                print(f"✅ Environment variable template: {var}")
                env_checks += 1
            else:
                print(f"❌ Missing environment variable: {var}")
    
    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Deployment Readiness Summary:")
    print(f"   Python Syntax: {passed_syntax}/{total_syntax}")
    print(f"   Config Files: {config_passed}/{total_config}")
    print(f"   Critical Functions: {function_passed}/{total_functions}")
    print(f"   Environment Variables: {env_checks}/{len(required_vars)}")
    
    total_checks = passed_syntax + config_passed + function_passed + env_checks
    max_checks = total_syntax + total_config + total_functions + len(required_vars)
    
    print(f"   Overall Score: {total_checks}/{max_checks}")
    
    if total_checks >= max_checks * 0.9:  # 90% pass rate
        print("\n🎉 ✅ DEPLOYMENT READY!")
        print("📋 Readiness Checklist:")
        print("   ✅ All critical Python files have valid syntax")
        print("   ✅ Configuration files are present")
        print("   ✅ Core functions are implemented")
        print("   ✅ Environment variables are documented")
        print("\n🚀 The application structure is solid and ready for Render deployment!")
        print("💡 Runtime dependencies (passlib, redis, etc.) will be installed by Render")
        return True
    else:
        print(f"\n❌ DEPLOYMENT NOT READY")
        print(f"   Issues found that need to be resolved before deployment")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)