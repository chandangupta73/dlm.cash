#!/usr/bin/env python
"""
Simple test runner for the Investment System
This script properly initializes Django before running tests
"""

import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

def main():
    """Main test runner function"""
    # Add the project root to Python path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    
    # Set Django settings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'investment_system.settings')
    
    # Setup Django
    django.setup()
    
    # Get test runner
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    
    # Discover and run tests
    print("🧪 Running Investment System Tests...")
    print("=" * 50)
    
    # Test categories to run
    test_categories = [
        'tests.functional_edge_cases',
        'tests.data_integrity', 
        'tests.security',
        'tests.load_stress',
        'tests.integration_readiness'
    ]
    
    total_failures = 0
    total_tests = 0
    
    for category in test_categories:
        print(f"\n📁 Testing {category}...")
        try:
            failures = test_runner.run_tests([category])
            total_failures += failures
            print(f"✅ {category}: Completed")
        except Exception as e:
            print(f"❌ {category}: Error - {e}")
            total_failures += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Summary:")
    print(f"   Total Failures: {total_failures}")
    
    if total_failures == 0:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed!")
        return 1

if __name__ == '__main__':
    sys.exit(main())

