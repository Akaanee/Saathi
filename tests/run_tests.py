#!/usr/bin/env python3
"""
SAATHI Test Suite Runner
Run all tests for the Saathi legal aid application
"""

import sys
import os
import subprocess
from pathlib import Path

def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def run_test_file(test_file, description):
    print_header(f"{description}")
    
    test_path = Path(__file__).parent / test_file
    
    if not test_path.exists():
        print(f"⚠ Test file not found: {test_file}")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(test_path)],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"✗ Test timed out: {test_file}")
        return False
    except Exception as e:
        print(f"✗ Error running {test_file}: {e}")
        return False

def main():
    print_header("SAATHI - Legal Aid Application Test Suite")
    
    print("\nProject: Voice-First Multi-Agent Legal Aid for India's Informal Workers")
    print("Testing: Configuration, Services, and Agents\n")
    
    test_results = []
    
    test_results.append((
        "test_config.py",
        "Configuration Tests",
        run_test_file("test_config.py", "Configuration Tests")
    ))
    
    test_results.append((
        "test_services.py",
        "Service Tests",
        run_test_file("test_services.py", "Service Tests")
    ))
    
    test_results.append((
        "test_agents.py",
        "Agent Tests",
        run_test_file("test_agents.py", "Agent Tests")
    ))
    
    print_header("Test Suite Summary")
    
    passed = sum(1 for _, _, result in test_results if result)
    total = len(test_results)
    
    for test_file, description, result in test_results:
        status = "✓ PASS" if result else "⚠ WARN"
        print(f"{status}  {description}")
    
    print("-" * 70)
    print(f"Results: {passed}/{total} test suites completed")
    
    if passed == total:
        print("\n✓ All test suites passed successfully!")
        print("\nNext steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Start Ollama: ollama serve")
        print("3. Pull models: ollama pull llama3.1:8b-instruct-q4_K_M")
        print("4. Run the application: python app/main.py")
        return 0
    else:
        print(f"\n⚠ {total - passed} test suite(s) had warnings")
        print("\nCommon issues:")
        print("- Missing dependencies: Run 'pip install -r requirements.txt'")
        print("- Ollama not running: Start with 'ollama serve'")
        print("- Models not downloaded: Pull with 'ollama pull llama3.1:8b-instruct-q4_K_M'")
        return 1

if __name__ == "__main__":
    sys.exit(main())
