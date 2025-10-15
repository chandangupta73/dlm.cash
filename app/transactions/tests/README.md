# Transactions Module Integration Tests

This directory contains comprehensive integration tests for the Transactions module, designed to verify cross-module correctness and ensure all financial operations work seamlessly together.

## 🎯 Test Objectives

The integration tests verify that the Transactions module correctly integrates with:

- **Wallet Module**: Deposits, withdrawals, balance updates
- **Investment Module**: ROI payouts, plan purchases, refunds
- **Referral Module**: Bonus distributions, milestone rewards
- **User Module**: Authentication, permissions, data isolation
- **API Layer**: REST endpoints, filtering, pagination

## 📁 Test Files

### 1. `test_integration.py`
Traditional Django TestCase-based integration tests covering:
- Wallet integration (deposits, withdrawals, balance updates)
- Investment integration (ROI payouts, plan purchases)
- Referral integration (bonuses, milestones)
- End-to-end transaction flows
- API integration testing
- Data integrity validation
- Performance testing

### 2. `test_integration_pytest.py`
Modern pytest-style tests with fixtures and markers:
- Same test coverage as Django TestCase version
- Better test organization with pytest markers
- Reusable fixtures for test data
- Performance monitoring capabilities
- Parallel test execution support

### 3. `conftest.py`
Pytest configuration and fixtures:
- Test data factories
- Common fixtures for users, wallets, investments
- Performance monitoring tools
- Time control utilities
- Database transaction management

## 🚀 Running the Tests

### Quick Start

```bash
# Run all integration tests
python run_integration_tests.py --all

# Run specific module tests
python run_integration_tests.py --wallet
python run_integration_tests.py --investment
python run_integration_tests.py --referral

# Run with coverage
python run_integration_tests.py --coverage
```

### Using pytest directly

```bash
# Run all integration tests
python -m pytest app/transactions/tests/test_integration_pytest.py -v

# Run specific test class
python -m pytest app/transactions/tests/test_integration_pytest.py::TestWalletIntegration -v

# Run tests with specific marker
python -m pytest app/transactions/tests/test_integration_pytest.py -m wallet -v

# Run tests in parallel
python -m pytest app/transactions/tests/test_integration_pytest.py -n auto -v
```

### Using Django test runner

```bash
# Run Django TestCase tests
python manage.py test app.transactions.tests.test_integration

# Run with specific test
python manage.py test app.transactions.tests.test_integration.TransactionWalletIntegrationTest.test_deposit_inr_creates_transaction_and_updates_wallet
```

## 🏷️ Test Markers

The tests use pytest markers for organization:

- `@pytest.mark.integration` - All integration tests
- `@pytest.mark.wallet` - Wallet-related tests
- `@pytest.mark.investment` - Investment-related tests
- `@pytest.mark.referral` - Referral-related tests
- `@pytest.mark.api` - API-related tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.performance` - Performance tests
- `@pytest.mark.slow` - Slow-running tests

## 📊 Test Categories

### 1. Wallet Integration Tests
**File**: `TestWalletIntegration`

Tests the integration between Transactions and Wallet modules:
- ✅ INR deposits create transactions and update wallet balances
- ✅ USDT deposits create transactions and update wallet balances
- ✅ INR withdrawals create transactions and update wallet balances
- ✅ USDT withdrawals create transactions and update wallet balances
- ✅ Insufficient balance withdrawals fail gracefully

### 2. Investment Integration Tests
**File**: `TestInvestmentIntegration`

Tests the integration between Transactions and Investment modules:
- ✅ Investment purchases create transactions and update wallet balances
- ✅ ROI payouts create transactions and update wallet balances
- ✅ Investment breakdown refunds create transactions
- ✅ Time-controlled ROI calculations with freezegun

### 3. Referral Integration Tests
**File**: `TestReferralIntegration`

Tests the integration between Transactions and Referral modules:
- ✅ Referral bonuses create transactions and update wallet balances
- ✅ Milestone bonuses create transactions and update wallet balances
- ✅ Referral relationship tracking
- ✅ Multi-level referral support

### 4. End-to-End Integration Tests
**File**: `TestEndToEndIntegration`

Tests complete transaction flows:
- ✅ Complete flow: deposit → invest → ROI → referral → withdrawal
- ✅ Transaction chronological order verification
- ✅ Multi-user transaction scenarios
- ✅ Complex business logic validation

### 5. API Integration Tests
**File**: `TestAPIIntegration`

Tests API endpoints and functionality:
- ✅ User transactions API returns only own transactions
- ✅ Admin transactions API returns all transactions
- ✅ Transaction filtering works correctly
- ✅ Pagination and search functionality

### 6. Data Integrity Tests
**File**: `TestDataIntegrity`

Tests data consistency and validation:
- ✅ No transactions without linked users
- ✅ No duplicate reference IDs for same transaction type
- ✅ No negative wallet balances
- ✅ Transaction metadata integrity

### 7. Performance Tests
**File**: `TestPerformance`

Tests system performance and scalability:
- ✅ Bulk transaction creation performance
- ✅ Transaction query performance
- ✅ Wallet balance update performance
- ✅ Concurrent transaction handling

### 8. Complex Scenario Tests
**File**: `TestComplexScenarios`

Tests complex business scenarios:
- ✅ Multi-user transaction flows
- ✅ Referral chain operations
- ✅ Concurrent transaction creation
- ✅ Edge case handling

## 🧪 Test Data Management

### Fixtures
The tests use pytest fixtures for consistent test data:

```python
@pytest.fixture
def test_user():
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )

@pytest.fixture
def inr_wallet(test_user):
    """Create INR wallet for test user."""
    return INRWallet.objects.create(
        user=test_user,
        balance=Decimal('0.00')
    )
```

### Test Data Factories
Reusable factories for creating test data:

```python
class TransactionTestDataFactory:
    @staticmethod
    def create_user_with_wallets(username='factoryuser', email='factory@example.com'):
        """Create a user with wallets."""
        # Implementation...
    
    @staticmethod
    def create_transaction_flow(user, amount=Decimal('1000.00')):
        """Create a complete transaction flow for testing."""
        # Implementation...
```

## ⚡ Performance Testing

### Performance Monitoring
Tests include performance monitoring with configurable thresholds:

```python
def test_bulk_transaction_creation_performance(
    self, test_user, inr_wallet, performance_monitor
):
    """Test performance of creating multiple transactions."""
    performance_monitor.start()
    
    # Create 100 transactions
    for i in range(100):
        TransactionIntegrationService.log_deposit(
            user=test_user,
            amount=Decimal('10.00'),
            currency='INR',
            reference_id=f'PERF_TEST_{i}'
        )
    
    performance_monitor.stop()
    
    # Performance should be reasonable (less than 10 seconds for 100 transactions)
    performance_monitor.assert_fast_enough(10.0)
```

### Performance Thresholds
- **Bulk Creation**: 100 transactions in < 10 seconds
- **Query Performance**: Filtered queries in < 1 second
- **Balance Updates**: 100 updates in < 5 seconds
- **Concurrent Operations**: 10 threads in < 5 seconds

## 🔒 Security Testing

### User Isolation
Tests verify that users can only access their own data:

```python
def test_user_transactions_api_returns_only_own_transactions(
    self, test_user, sample_transactions
):
    """Test that user transactions API returns only user's own transactions."""
    # Test implementation...
    
    # Verify all transactions belong to the user
    for transaction in response.data['results']:
        assert transaction['user']['username'] == test_user.username
```

### Data Validation
Tests verify input validation and sanitization:

```python
def test_no_negative_balances_from_mismatched_transactions(
    self, test_user, inr_wallet
):
    """Test that wallet balances never go negative."""
    with pytest.raises(ValueError):
        TransactionIntegrationService.log_withdrawal(
            user=test_user,
            amount=Decimal('2000.00'),  # More than available
            currency='INR',
            reference_id='NEGATIVE_TEST'
        )
```

## 🕒 Time Control Testing

### Freezegun Integration
Tests use freezegun for time-controlled scenarios:

```python
@freeze_time("2024-01-01")
def test_roi_payout_creates_transaction_and_updates_wallet(
    self, test_user, inr_wallet, investment_plan
):
    """Test that ROI payout creates transaction and updates wallet balance."""
    # Test implementation with controlled time...
```

### Chronological Order Testing
Tests verify transaction timestamps and order:

```python
def test_transaction_chronological_order(self, referred_user):
    """Test that transactions are created in correct chronological order."""
    with freeze_time("2024-01-01 10:00:00"):
        deposit_transaction = TransactionIntegrationService.log_deposit(...)
    
    with freeze_time("2024-01-01 10:01:00"):
        investment_transaction = TransactionIntegrationService.log_plan_purchase(...)
    
    # Verify chronological order
    assert transactions[0].created_at < transactions[1].created_at
```

## 📈 Coverage Requirements

### Minimum Coverage
- **Overall Coverage**: 85% minimum
- **Integration Tests**: 100% of integration points
- **API Tests**: 100% of endpoints
- **Error Handling**: 100% of error scenarios

### Coverage Reports
Generate coverage reports with:

```bash
# Terminal coverage
python -m pytest --cov=app.transactions --cov-report=term-missing

# HTML coverage report
python -m pytest --cov=app.transactions --cov-report=html

# XML coverage report (for CI/CD)
python -m pytest --cov=app.transactions --cov-report=xml
```

## 🚦 CI/CD Integration

### GitHub Actions
The tests are configured for CI/CD pipelines:

```yaml
- name: Run Integration Tests
  run: |
    python -m pytest app/transactions/tests/test_integration_pytest.py \
      --cov=app.transactions \
      --cov-report=xml \
      --cov-fail-under=85 \
      -v
```

### Test Parallelization
Run tests in parallel for faster CI/CD execution:

```bash
python -m pytest app/transactions/tests/test_integration_pytest.py -n auto
```

## 🐛 Debugging Tests

### Verbose Output
Use verbose output for debugging:

```bash
python -m pytest app/transactions/tests/test_integration_pytest.py -v -s
```

### Specific Test Debugging
Debug specific tests:

```bash
# Run single test with maximum verbosity
python -m pytest app/transactions/tests/test_integration_pytest.py::TestWalletIntegration::test_deposit_inr_creates_transaction_and_updates_wallet -v -s

# Run with debugger
python -m pytest app/transactions/tests/test_integration_pytest.py::TestWalletIntegration::test_deposit_inr_creates_transaction_and_updates_wallet -v -s --pdb
```

### Database Inspection
Inspect database state during tests:

```python
def test_with_debugging(self, test_user, inr_wallet):
    """Test with debugging information."""
    # Create transaction
    transaction = TransactionIntegrationService.log_deposit(...)
    
    # Debug: Print database state
    print(f"Transaction: {transaction}")
    print(f"Wallet balance: {inr_wallet.balance}")
    
    # Continue with assertions...
```

## 📝 Adding New Tests

### Test Structure
Follow the established pattern:

```python
@pytest.mark.integration
@pytest.mark.new_feature
class TestNewFeatureIntegration:
    """Test integration for new feature."""
    
    def test_new_feature_creates_transaction(self, test_user, inr_wallet):
        """Test that new feature creates transaction correctly."""
        # Arrange
        # Act
        # Assert
```

### Fixture Dependencies
Use existing fixtures or create new ones:

```python
@pytest.fixture
def new_feature_data(test_user):
    """Create data for new feature testing."""
    return NewFeature.objects.create(
        user=test_user,
        # ... other fields
    )
```

### Test Naming
Use descriptive test names:
- `test_feature_creates_transaction_and_updates_wallet`
- `test_feature_fails_with_invalid_data`
- `test_feature_integration_with_existing_modules`

## 🔍 Test Discovery

### Running All Tests
```bash
# All tests in transactions module
python -m pytest app/transactions/tests/

# All integration tests
python -m pytest app/transactions/tests/ -m integration

# All tests with specific marker
python -m pytest app/transactions/tests/ -m wallet
```

### Test Filtering
```bash
# Tests containing specific text
python -m pytest app/transactions/tests/ -k "deposit"

# Tests excluding specific text
python -m pytest app/transactions/tests/ -k "not slow"

# Tests matching regex pattern
python -m pytest app/transactions/tests/ -k "test_.*_integration"
```

## 📚 Additional Resources

### Documentation
- [Django Testing Documentation](https://docs.djangoproject.com/en/stable/topics/testing/)
- [pytest Documentation](https://docs.pytest.org/)
- [pytest-django Documentation](https://pytest-django.readthedocs.io/)

### Related Files
- `transaction_implementation.txt` - Complete implementation documentation
- `app/transactions/README.md` - Module documentation
- `pytest.ini` - Pytest configuration
- `run_integration_tests.py` - Test runner script

### Support
For questions or issues with the integration tests:
1. Check the test output for specific error messages
2. Review the test data setup in fixtures
3. Verify database migrations are up to date
4. Check that all required modules are properly configured

---

**Last Updated**: Current session  
**Test Coverage**: 85%+ target  
**Status**: Ready for CI/CD integration
