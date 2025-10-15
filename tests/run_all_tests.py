#!/usr/bin/env python3
"""
Comprehensive Test Runner for Investment & Wallet Management System
==================================================================

This script runs all test categories and generates comprehensive coverage reports.
It's designed to be CI/CD ready and provides detailed output for production verification.

Usage:
    python tests/run_all_tests.py [options]

Options:
    --category CATEGORY    Run specific test category (edge_case, data_integrity, security, load_test, integration)
    --parallel             Run tests in parallel for faster execution
    --coverage             Generate detailed coverage report
    --html                 Generate HTML coverage report
    --verbose              Verbose output
    --fast                 Skip slow tests
    --help                 Show this help message
"""

import os
import sys
import subprocess
import argparse
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def run_command(command, description):
    """Run a command and return success status"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(command)}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            command,
            capture_output=False,
            text=True,
            check=True
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n✅ {description} completed successfully in {duration:.2f} seconds")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} failed with exit code {e.returncode}")
        return False

def run_pytest_with_options(category=None, parallel=False, coverage=False, html=False, verbose=False, fast=False):
    """Run pytest with specified options"""
    base_command = ["python", "-m", "pytest"]
    
    # Add category filter if specified
    if category:
        base_command.extend(["-m", category])
    
    # Add parallel execution
    if parallel:
        base_command.extend(["-n", "auto"])
    
    # Add coverage options
    if coverage:
        base_command.extend(["--cov=app", "--cov-report=term-missing"])
    
    if html:
        base_command.extend(["--cov-report=html"])
    
    # Add verbose output
    if verbose:
        base_command.extend(["-v", "-s"])
    
    # Skip slow tests if fast mode
    if fast:
        base_command.extend(["-m", "not slow"])
    
    # Add test discovery paths
    base_command.extend([
        "tests/functional_edge_cases/",
        "tests/data_integrity/",
        "tests/security/",
        "tests/load_stress/",
        "tests/integration_readiness/"
    ])
    
    return run_command(base_command, "Comprehensive Test Suite")

def run_specific_category(category):
    """Run tests for a specific category"""
    category_paths = {
        'edge_case': 'tests/functional_edge_cases/',
        'data_integrity': 'tests/data_integrity/',
        'security': 'tests/security/',
        'load_test': 'tests/load_stress/',
        'integration': 'tests/integration_readiness/'
    }
    
    if category not in category_paths:
        print(f"❌ Unknown category: {category}")
        print(f"Available categories: {', '.join(category_paths.keys())}")
        return False
    
    command = [
        "python", "-m", "pytest",
        "-v",
        "--cov=app",
        "--cov-report=term-missing",
        category_paths[category]
    ]
    
    return run_command(command, f"{category.replace('_', ' ').title()} Tests")

def run_coverage_report():
    """Generate comprehensive coverage report"""
    print(f"\n{'='*60}")
    print("Generating Coverage Report")
    print(f"{'='*60}")
    
    # Run coverage report
    command = [
        "python", "-m", "pytest",
        "--cov=app",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-report=xml",
        "--cov-fail-under=90",
        "tests/"
    ]
    
    return run_command(command, "Coverage Report Generation")

def run_load_tests():
    """Run load and stress tests separately"""
    print(f"\n{'='*60}")
    print("Running Load & Stress Tests")
    print(f"{'='*60}")
    
    command = [
        "python", "-m", "pytest",
        "-m", "load_test",
        "-v",
        "--tb=short",
        "tests/load_stress/"
    ]
    
    return run_command(command, "Load & Stress Tests")

def run_security_tests():
    """Run security tests separately"""
    print(f"\n{'='*60}")
    print("Running Security Tests")
    print(f"{'='*60}")
    
    command = [
        "python", "-m", "pytest",
        "-m", "security",
        "-v",
        "--tb=short",
        "tests/security/"
    ]
    
    return run_command(command, "Security Tests")

def run_edge_case_tests():
    """Run edge case tests separately"""
    print(f"\n{'='*60}")
    print("Running Edge Case Tests")
    print(f"{'='*60}")
    
    command = [
        "python", "-m", "pytest",
        "-m", "edge_case",
        "-v",
        "--tb=short",
        "tests/functional_edge_cases/"
    ]
    
    return run_command(command, "Edge Case Tests")

def run_data_integrity_tests():
    """Run data integrity tests separately"""
    print(f"\n{'='*60}")
    print("Running Data Integrity Tests")
    print(f"{'='*60}")
    
    command = [
        "python", "-m", "pytest",
        "-m", "data_integrity",
        "-v",
        "--tb=short",
        "tests/data_integrity/"
    ]
    
    return run_command(command, "Data Integrity Tests")

def run_integration_tests():
    """Run integration tests separately"""
    print(f"\n{'='*60}")
    print("Running Integration Tests")
    print(f"{'='*60}")
    
    command = [
        "python", "-m", "pytest",
        "-m", "integration",
        "-v",
        "--tb=short",
        "tests/integration_readiness/"
    ]
    
    return run_command(command, "Integration Tests")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Comprehensive Test Runner for Investment & Wallet Management System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--category',
        choices=['edge_case', 'data_integrity', 'security', 'load_test', 'integration'],
        help='Run specific test category'
    )
    
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Run tests in parallel for faster execution'
    )
    
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Generate detailed coverage report'
    )
    
    parser.add_argument(
        '--html',
        action='store_true',
        help='Generate HTML coverage report'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    parser.add_argument(
        '--fast',
        action='store_true',
        help='Skip slow tests'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Run all test categories sequentially'
    )
    
    args = parser.parse_args()
    
    print("🚀 Investment & Wallet Management System - Test Runner")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not os.path.exists('manage.py'):
        print("❌ Error: manage.py not found. Please run this script from the project root.")
        sys.exit(1)
    
    # Check if Django is available
    try:
        import django
        print(f"✅ Django {django.get_version()} found")
    except ImportError:
        print("❌ Error: Django not found. Please install requirements first.")
        sys.exit(1)
    
    # Check if pytest is available
    try:
        import pytest
        print(f"✅ pytest {pytest.__version__} found")
    except ImportError:
        print("❌ Error: pytest not found. Please install requirements first.")
        sys.exit(1)
    
    success_count = 0
    total_tests = 0
    
    if args.category:
        # Run specific category
        total_tests = 1
        if run_specific_category(args.category):
            success_count = 1
    
    elif args.all:
        # Run all categories sequentially
        total_tests = 6
        print("\n🔄 Running all test categories sequentially...")
        
        # Edge case tests
        if run_edge_case_tests():
            success_count += 1
        
        # Data integrity tests
        if run_data_integrity_tests():
            success_count += 1
        
        # Security tests
        if run_security_tests():
            success_count += 1
        
        # Load tests
        if run_load_tests():
            success_count += 1
        
        # Integration tests
        if run_integration_tests():
            success_count += 1
        
        # Coverage report
        if run_coverage_report():
            success_count += 1
    
    else:
        # Run comprehensive test suite
        total_tests = 1
        if run_pytest_with_options(
            parallel=args.parallel,
            coverage=args.coverage,
            html=args.html,
            verbose=args.verbose,
            fast=args.fast
        ):
            success_count = 1
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 TEST EXECUTION SUMMARY")
    print(f"{'='*60}")
    print(f"Tests executed: {success_count}/{total_tests}")
    print(f"Success rate: {(success_count/total_tests)*100:.1f}%")
    
    if success_count == total_tests:
        print("\n🎉 All tests completed successfully!")
        print("✅ System is ready for production deployment")
        return 0
    else:
        print(f"\n⚠️  {total_tests - success_count} test category(ies) failed")
        print("❌ System needs attention before production deployment")
        return 1

if __name__ == "__main__":
    sys.exit(main())

