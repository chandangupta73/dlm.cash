#!/usr/bin/env python3
"""
Integration Test Runner for Transactions Module

This script provides various ways to run the integration tests:
- All integration tests
- Specific module tests
- Performance tests
- End-to-end tests
- Coverage reports
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {command}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=False,
            text=True
        )
        print(f"\n✅ {description} completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} failed with exit code {e.returncode}")
        return False


def run_integration_tests():
    """Run all integration tests."""
    command = "python -m pytest app/transactions/tests/test_integration.py -v --tb=short"
    return run_command(command, "All Integration Tests")


def run_pytest_integration_tests():
    """Run pytest-style integration tests."""
    command = "python -m pytest app/transactions/tests/test_integration_pytest.py -v --tb=short"
    return run_command(command, "Pytest Integration Tests")


def run_wallet_integration_tests():
    """Run wallet integration tests only."""
    command = "python -m pytest app/transactions/tests/test_integration_pytest.py::TestWalletIntegration -v --tb=short"
    return run_command(command, "Wallet Integration Tests")


def run_investment_integration_tests():
    """Run investment integration tests only."""
    command = "python -m pytest app/transactions/tests/test_integration_pytest.py::TestInvestmentIntegration -v --tb=short"
    return run_command(command, "Investment Integration Tests")


def run_referral_integration_tests():
    """Run referral integration tests only."""
    command = "python -m pytest app/transactions/tests/test_integration_pytest.py::TestReferralIntegration -v --tb=short"
    return run_command(command, "Referral Integration Tests")


def run_e2e_tests():
    """Run end-to-end integration tests only."""
    command = "python -m pytest app/transactions/tests/test_integration_pytest.py::TestEndToEndIntegration -v --tb=short"
    return run_command(command, "End-to-End Integration Tests")


def run_api_integration_tests():
    """Run API integration tests only."""
    command = "python -m pytest app/transactions/tests/test_integration_pytest.py::TestAPIIntegration -v --tb=short"
    return run_command(command, "API Integration Tests")


def run_performance_tests():
    """Run performance tests only."""
    command = "python -m pytest app/transactions/tests/test_integration_pytest.py::TestPerformance -v --tb=short"
    return run_command(command, "Performance Tests")


def run_data_integrity_tests():
    """Run data integrity tests only."""
    command = "python -m pytest app/transactions/tests/test_integration_pytest.py::TestDataIntegrity -v --tb=short"
    return run_command(command, "Data Integrity Tests")


def run_complex_scenario_tests():
    """Run complex scenario tests only."""
    command = "python -m pytest app/transactions/tests/test_integration_pytest.py::TestComplexScenarios -v --tb=short"
    return run_command(command, "Complex Scenario Tests")


def run_with_coverage():
    """Run tests with coverage report."""
    command = "python -m pytest app/transactions/tests/test_integration_pytest.py --cov=app.transactions --cov-report=term-missing --cov-report=html --cov-report=xml --cov-fail-under=85"
    return run_command(command, "Integration Tests with Coverage")


def run_specific_test(test_name):
    """Run a specific test by name."""
    command = f"python -m pytest app/transactions/tests/test_integration_pytest.py::{test_name} -v --tb=short"
    return run_command(command, f"Specific Test: {test_name}")


def run_marked_tests(marker):
    """Run tests with specific marker."""
    command = f"python -m pytest app/transactions/tests/test_integration_pytest.py -m {marker} -v --tb=short"
    return run_command(command, f"Tests with marker: {marker}")


def run_parallel_tests():
    """Run tests in parallel for faster execution."""
    command = "python -m pytest app/transactions/tests/test_integration_pytest.py -n auto -v --tb=short"
    return run_command(command, "Parallel Integration Tests")


def run_slow_tests():
    """Run only slow tests."""
    command = "python -m pytest app/transactions/tests/test_integration_pytest.py -m slow -v --tb=short"
    return run_command(command, "Slow Integration Tests")


def run_fast_tests():
    """Run only fast tests (exclude slow ones)."""
    command = "python -m pytest app/transactions/tests/test_integration_pytest.py -m 'not slow' -v --tb=short"
    return run_command(command, "Fast Integration Tests")


def run_all_tests():
    """Run all tests in the transactions module."""
    command = "python -m pytest app/transactions/tests/ -v --tb=short"
    return run_command(command, "All Transactions Tests")


def show_test_summary():
    """Show a summary of available tests."""
    print("\n" + "="*80)
    print("TRANSACTIONS MODULE INTEGRATION TESTS SUMMARY")
    print("="*80)
    
    print("\n📋 Available Test Categories:")
    print("  1.  Wallet Integration Tests")
    print("  2.  Investment Integration Tests")
    print("  3.  Referral Integration Tests")
    print("  4.  End-to-End Integration Tests")
    print("  5.  API Integration Tests")
    print("  6.  Performance Tests")
    print("  7.  Data Integrity Tests")
    print("  8.  Complex Scenario Tests")
    
    print("\n🚀 Test Execution Options:")
    print("  -a, --all              Run all integration tests")
    print("  -w, --wallet           Run wallet integration tests")
    print("  -i, --investment       Run investment integration tests")
    print("  -r, --referral         Run referral integration tests")
    print("  -e, --e2e              Run end-to-end tests")
    print("  -p, --performance      Run performance tests")
    print("  -c, --coverage         Run with coverage report")
    print("  -s, --slow             Run only slow tests")
    print("  -f, --fast             Run only fast tests")
    print("  -m, --marker MARKER    Run tests with specific marker")
    print("  -t, --test TEST_NAME   Run specific test")
    print("  -j, --parallel         Run tests in parallel")
    
    print("\n📊 Test Markers:")
    print("  @pytest.mark.integration  - All integration tests")
    print("  @pytest.mark.wallet       - Wallet-related tests")
    print("  @pytest.mark.investment   - Investment-related tests")
    print("  @pytest.mark.referral     - Referral-related tests")
    print("  @pytest.mark.api          - API-related tests")
    print("  @pytest.mark.e2e          - End-to-end tests")
    print("  @pytest.mark.performance  - Performance tests")
    print("  @pytest.mark.slow         - Slow-running tests")
    
    print("\n💡 Example Commands:")
    print("  python run_integration_tests.py --all")
    print("  python run_integration_tests.py --wallet")
    print("  python run_integration_tests.py --marker performance")
    print("  python run_integration_tests.py --test TestWalletIntegration")
    print("  python run_integration_tests.py --coverage")


def main():
    """Main function to parse arguments and run tests."""
    parser = argparse.ArgumentParser(
        description="Run Transactions Module Integration Tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_integration_tests.py --all
  python run_integration_tests.py --wallet --investment
  python run_integration_tests.py --marker performance
  python run_integration_tests.py --coverage
        """
    )
    
    parser.add_argument(
        '-a', '--all',
        action='store_true',
        help='Run all integration tests'
    )
    
    parser.add_argument(
        '-w', '--wallet',
        action='store_true',
        help='Run wallet integration tests'
    )
    
    parser.add_argument(
        '-i', '--investment',
        action='store_true',
        help='Run investment integration tests'
    )
    
    parser.add_argument(
        '-r', '--referral',
        action='store_true',
        help='Run referral integration tests'
    )
    
    parser.add_argument(
        '-e', '--e2e',
        action='store_true',
        help='Run end-to-end integration tests'
    )
    
    parser.add_argument(
        '-p', '--performance',
        action='store_true',
        help='Run performance tests'
    )
    
    parser.add_argument(
        '-c', '--coverage',
        action='store_true',
        help='Run tests with coverage report'
    )
    
    parser.add_argument(
        '-s', '--slow',
        action='store_true',
        help='Run only slow tests'
    )
    
    parser.add_argument(
        '-f', '--fast',
        action='store_true',
        help='Run only fast tests'
    )
    
    parser.add_argument(
        '-m', '--marker',
        type=str,
        help='Run tests with specific marker'
    )
    
    parser.add_argument(
        '-t', '--test',
        type=str,
        help='Run specific test by name'
    )
    
    parser.add_argument(
        '-j', '--parallel',
        action='store_true',
        help='Run tests in parallel'
    )
    
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Show test summary and available options'
    )
    
    args = parser.parse_args()
    
    # Show summary if requested
    if args.summary:
        show_test_summary()
        return
    
    # If no arguments provided, show summary
    if not any(vars(args).values()):
        show_test_summary()
        return
    
    # Track test results
    results = []
    
    # Run requested tests
    if args.all:
        results.append(run_integration_tests())
        results.append(run_pytest_integration_tests())
    
    if args.wallet:
        results.append(run_wallet_integration_tests())
    
    if args.investment:
        results.append(run_investment_integration_tests())
    
    if args.referral:
        results.append(run_referral_integration_tests())
    
    if args.e2e:
        results.append(run_e2e_tests())
    
    if args.performance:
        results.append(run_performance_tests())
    
    if args.coverage:
        results.append(run_with_coverage())
    
    if args.slow:
        results.append(run_slow_tests())
    
    if args.fast:
        results.append(run_fast_tests())
    
    if args.marker:
        results.append(run_marked_tests(args.marker))
    
    if args.test:
        results.append(run_specific_test(args.test))
    
    if args.parallel:
        results.append(run_parallel_tests())
    
    # Show final summary
    if results:
        print("\n" + "="*80)
        print("TEST EXECUTION SUMMARY")
        print("="*80)
        
        successful = sum(results)
        total = len(results)
        
        print(f"\n✅ Successful: {successful}/{total}")
        print(f"❌ Failed: {total - successful}/{total}")
        
        if successful == total:
            print("\n🎉 All tests completed successfully!")
        else:
            print("\n⚠️  Some tests failed. Check the output above for details.")
        
        print(f"\n📊 Success Rate: {(successful/total)*100:.1f}%")


if __name__ == "__main__":
    main()
