#!/usr/bin/env python3
"""
Simple test to verify the file structure and basic imports work
"""

import os
import sys

def test_structure():
    """Test that all required files exist"""
    required_files = [
        'agent.py',
        'interactive_login.py',
        'requirements.txt',
        'README.md',
        'config.json'
    ]

    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)

    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    else:
        print("✅ All required files present")
        return True

def test_imports():
    """Test that basic imports work"""
    try:
        import gradio
        import playwright
        import ollama
        import pandas
        import sqlite3
        print("✅ Basic imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Job Search Agent Structure")
    print("=" * 40)

    structure_ok = test_structure()
    imports_ok = test_imports()

    if structure_ok and imports_ok:
        print("\n🎉 Structure test passed!")
        print("📝 Next steps:")
        print("   1. Install dependencies: pip install -r requirements.txt")
        print("   2. Install Playwright: playwright install")
        print("   3. Install and run Ollama: https://ollama.ai/")
        print("   4. Pull a model: ollama pull llama3")
        print("   5. Run interactive login: python interactive_login.py")
        print("   6. Start agent: python agent.py")
    else:
        print("\n💥 Structure test failed!")
        sys.exit(1)