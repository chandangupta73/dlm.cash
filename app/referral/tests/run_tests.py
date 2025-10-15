#!/usr/bin/env python
"""
Test runner for the referral system.
This script runs all referral system tests and provides coverage information.
"""

import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'investment_system.settings')
django.setup()

def run_referral_tests():
    """Run all referral system tests."""
    print("🚀 Starting Referral System Tests...")
    print("=" * 50)
    
    # Get the test runner
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False)
    
    # Define test modules to run
    test_modules = [
        'app.referral.tests.test_models',
        'app.referral.tests.test_services',
        'app.referral.tests.test_views',
        'app.referral.tests.test_signals',
        'app.referral.tests.test_admin',
        'app.referral.tests.test_integration',
    ]
    
    # Run tests
    failures = test_runner.run_tests(test_modules)
    
    print("=" * 50)
    if failures:
        print(f"❌ Tests failed: {failures}")
        return False
    else:
        print("✅ All tests passed!")
        return True

def run_coverage_tests():
    """Run tests with coverage reporting."""
    try:
        import coverage
        print("📊 Running tests with coverage...")
        print("=" * 50)
        
        # Start coverage measurement
        cov = coverage.Coverage()
        cov.start()
        
        # Run tests
        success = run_referral_tests()
        
        # Stop coverage measurement
        cov.stop()
        cov.save()
        
        # Generate coverage report
        print("\n📈 Coverage Report:")
        print("=" * 30)
        cov.report()
        
        # Generate HTML report
        cov.html_report(directory='coverage_html')
        print(f"\n📁 HTML coverage report generated in: coverage_html/")
        
        return success
        
    except ImportError:
        print("⚠️  Coverage package not installed. Install with: pip install coverage")
        print("Running tests without coverage...")
        return run_referral_tests()

def run_specific_test(test_name):
    """Run a specific test module or test case."""
    print(f"🎯 Running specific test: {test_name}")
    print("=" * 50)
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False)
    
    failures = test_runner.run_tests([test_name])
    
    if failures:
        print(f"❌ Test failed: {failures}")
        return False
    else:
        print("✅ Test passed!")
        return False

def main():
    """Main function to run tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run referral system tests')
    parser.add_argument('--coverage', action='store_true', help='Run tests with coverage')
    parser.add_argument('--test', type=str, help='Run specific test module or test case')
    
    args = parser.parse_args()
    
    if args.test:
        success = run_specific_test(args.test)
    elif args.coverage:
        success = run_coverage_tests()
    else:
        success = run_referral_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()



