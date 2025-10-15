# 🧪 Comprehensive Test Suite for Investment System

This folder contains a comprehensive testing framework for the Investment & Wallet Management System, designed to catch hidden logic bugs, race conditions, and integration mismatches before connecting real USDT.

## 🚀 Quick Start

### Run All Tests
```bash
# Run complete test suite with coverage
python tests/run_all_tests.py --coverage --html

# Run all test categories sequentially
python tests/run_all_tests.py --all

# Run specific category
python tests/run_all_tests.py --category edge_case
```

### Run with pytest directly
```bash
# Run all tests
pytest tests/ -v --cov=app --cov-report=html

# Run specific category
pytest tests/ -m edge_case -v

# Run with parallel execution
pytest tests/ -n auto -v
```

## 📋 Test Categories

### A) Functional Edge-Case Testing (`tests/functional_edge_cases/`)
- **Wallet Edge Cases**: Concurrent deposits, duplicate approvals, exact fee amounts
- **Investment Edge Cases**: Min/max boundaries, ROI eligibility, decimal precision
- **Referral Edge Cases**: Multi-level chains, earnings calculations, milestone bonuses
- **Admin Edge Cases**: Balance editing during pending operations, transaction consistency

### B) Data Integrity Testing (`tests/data_integrity/`)
- **Balance Consistency**: Wallet balances match transaction sums
- **Transaction Integrity**: No orphan transactions, proper rollback behavior
- **Currency Consistency**: Operations only affect specified currency wallets
- **Precision Handling**: Decimal precision maintained throughout system

### C) Security Testing (`tests/security/`)
- **Authentication**: Token validation, expired tokens, brute force protection
- **Authorization**: Admin endpoint access, privilege escalation prevention
- **Data Isolation**: Users cannot access other users' data
- **Input Validation**: SQL injection, XSS prevention, malformed requests

### D) Load & Stress Testing (`tests/load_stress/`)
- **Concurrent Operations**: 20-50 simultaneous operations
- **Database Performance**: Connection pooling, lock handling, memory usage
- **Response Times**: API performance under load
- **Error Handling**: Graceful degradation during stress

### E) Integration Readiness (`tests/integration_readiness/`)
- **API Consistency**: Response formats, error messages, status codes
- **Data Formats**: Decimal precision, UTC timezone, JSON validation
- **Query Parameters**: Pagination, filtering, ordering, search
- **Production Readiness**: CORS headers, rate limiting, logging

## 🛠️ Test Configuration

### pytest.ini
- Coverage target: 90%
- Parallel execution support
- Custom markers for test categorization
- HTML and terminal coverage reports

### conftest.py
- Shared fixtures and utilities
- Test data creation helpers
- Database setup and teardown
- Authentication token management

## 📊 Test Execution Options

### Basic Execution
```bash
# Run all tests
python tests/run_all_tests.py

# Run with coverage
python tests/run_all_tests.py --coverage

# Generate HTML report
python tests/run_all_tests.py --html
```

### Category-Specific Execution
```bash
# Edge cases only
python tests/run_all_tests.py --category edge_case

# Security tests only
python tests/run_all_tests.py --category security

# Load tests only
python tests/run_all_tests.py --category load_test
```

### Performance Options
```bash
# Parallel execution
python tests/run_all_tests.py --parallel

# Skip slow tests
python tests/run_all_tests.py --fast

# Verbose output
python tests/run_all_tests.py --verbose
```

## 🔧 Load Testing with Postman

### Import Collection
1. Import `tests/load_stress/postman_load_test_collection.json` into Postman
2. Set environment variables:
   - `base_url`: Your API base URL
   - `admin_token`: Admin JWT token
   - `user_token`: User JWT token

### Run Load Tests
1. Use Postman Collection Runner
2. Set iterations (e.g., 50-100)
3. Set delay between requests (e.g., 100ms)
4. Monitor response times and error rates

### Load Test Scenarios
- **Concurrent Wallet Operations**: Multiple users checking balances
- **Transaction Queries**: High-volume transaction listing
- **Investment Operations**: Multiple investment creations
- **Admin Operations**: Dashboard queries under load

## 📈 Coverage Reports

### Generate Reports
```bash
# Terminal coverage
python tests/run_all_tests.py --coverage

# HTML coverage report
python tests/run_all_tests.py --html

# Both
python tests/run_all_tests.py --coverage --html
```

### Coverage Targets
- **Overall Coverage**: 90% minimum
- **Critical Paths**: 95% minimum
- **Edge Cases**: 85% minimum
- **Security Tests**: 100% coverage

## 🚨 Test Data Management

### Isolation
- Each test creates unique test data
- Tests clean up after themselves
- No cross-test data contamination
- Database transactions ensure rollback

### Test Users
- `admin_test`: Admin user with full privileges
- `user_test`: Regular user for basic operations
- `kyc_user`: KYC-verified user for referral tests
- Category-specific users for load testing

### Test Wallets
- INR wallet for basic operations
- USDT wallet for cryptocurrency tests
- Multiple wallets for concurrent testing
- Balance precision testing

## 🔍 Debugging Tests

### Verbose Output
```bash
pytest tests/ -v -s --tb=long
```

### Specific Test Execution
```bash
# Run specific test file
pytest tests/functional_edge_cases/test_wallet_edge_cases.py -v

# Run specific test method
pytest tests/functional_edge_cases/test_wallet_edge_cases.py::TestWalletEdgeCases::test_concurrent_deposits_prevent_double_credit -v
```

### Test Markers
```bash
# Run only edge case tests
pytest tests/ -m edge_case

# Run only security tests
pytest tests/ -m security

# Skip slow tests
pytest tests/ -m "not slow"
```

## 🚀 CI/CD Integration

### GitHub Actions Example
```yaml
name: Test Suite
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python tests/run_all_tests.py --coverage --html
      - name: Upload coverage
        uses: codecov/codecov-action@v1
```

### Jenkins Pipeline Example
```groovy
pipeline {
    agent any
    stages {
        stage('Test') {
            steps {
                sh 'python tests/run_all_tests.py --coverage --html'
            }
        }
        stage('Coverage Report') {
            steps {
                publishHTML([
                    allowMissing: false,
                    alwaysLinkToLastBuild: true,
                    keepAll: true,
                    reportDir: 'htmlcov',
                    reportFiles: 'index.html',
                    reportName: 'Coverage Report'
                ])
            }
        }
    }
}
```

## 📝 Test Development

### Adding New Tests
1. Create test file in appropriate category directory
2. Inherit from `django.test.TestCase`
3. Use appropriate pytest markers
4. Follow naming convention: `test_*.py`
5. Include proper setup and teardown

### Test Structure
```python
@pytest.mark.edge_case
class TestNewFeature(TestCase):
    def setUp(self):
        # Setup test data
        
    def test_feature_behavior(self):
        # Test implementation
        
    def tearDown(self):
        # Cleanup if needed
```

### Fixtures Usage
```python
def test_with_fixtures(self, admin_user, regular_user, test_wallet):
    # Use shared fixtures for common test data
    pass
```

## 🎯 Production Readiness Checklist

- [ ] All test categories pass
- [ ] Coverage meets 90% target
- [ ] Load tests complete successfully
- [ ] Security tests pass
- [ ] Edge cases handled properly
- [ ] Data integrity verified
- [ ] API consistency confirmed
- [ ] Error handling tested
- [ ] Performance benchmarks met
- [ ] Documentation complete

## 📞 Support

For questions about the test suite:
1. Check test output for specific errors
2. Review test data setup in `conftest.py`
3. Verify database configuration
4. Check pytest configuration in `pytest.ini`

## 🔄 Maintenance

### Regular Updates
- Update test data as models change
- Add new test cases for new features
- Review and update security test vectors
- Monitor performance benchmarks

### Test Data Refresh
- Update test user credentials if needed
- Refresh test wallet balances
- Update test investment plans
- Maintain test referral chains

---

**Last updated:** December 2024
**Test Framework Version:** 2.0  
**Coverage Target:** 90%  
**CI/CD Ready:** ✅ Yes