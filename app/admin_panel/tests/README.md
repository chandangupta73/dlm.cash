# Admin Panel Test Suite

This directory contains the comprehensive test suite for the Admin Panel module (Part 7) of the Investment & Wallet Management System.

## Test Coverage Overview

The test suite covers all major admin panel functionality with a target of **85%+ coverage**:

- **User Management**: User CRUD, filtering, blocking/unblocking, bulk actions
- **KYC Management**: Document approval/rejection, status updates, logging
- **Wallet Management**: Balance adjustments, overrides, transaction logging
- **Deposit/Withdrawal Management**: Approval/rejection workflows, refunds
- **Investment Management**: Plan CRUD, ROI triggering, investment cancellation
- **Referral Management**: Tree visualization, milestone management, earnings adjustment
- **Announcement Management**: CRUD operations, target group filtering, visibility
- **Security & Permissions**: Role-based access control, authentication enforcement

## Running Tests

### Prerequisites

Ensure you have the required testing dependencies installed:

```bash
pip install pytest pytest-django factory-boy freezegun coverage
```

### Running All Admin Panel Tests

```bash
# Run all admin panel tests
pytest app/admin_panel/tests/ -v

# Run with coverage report
pytest app/admin_panel/tests/ --cov=app.admin_panel --cov-report=html --cov-report=term-missing

# Run specific test file
pytest app/admin_panel/tests/test_users_admin.py -v

# Run specific test class
pytest app/admin_panel/tests/test_users_admin.py::AdminUserServiceTest -v

# Run specific test method
pytest app/admin_panel/tests/test_users_admin.py::AdminUserServiceTest::test_get_users_with_filters -v
```

### Running Tests with Django TestCase

```bash
# Run Django TestCase tests
python manage.py test app.admin_panel.tests

# Run specific test file
python manage.py test app.admin_panel.tests.test_users_admin

# Run with coverage
coverage run --source='app.admin_panel' manage.py test app.admin_panel.tests
coverage report
coverage html
```

### Test Categories

Each test file contains three main test categories:

1. **Service Tests**: Unit tests for business logic in service classes
2. **API Tests**: Integration tests for API endpoints and views
3. **Integration Tests**: End-to-end tests ensuring data consistency across modules

## Test Files Structure

```
tests/
├── __init__.py
├── test_admin_dashboard.py      # Dashboard summary and statistics
├── test_admin_users.py          # User management operations
├── test_kyc_admin.py           # KYC approval/rejection workflows
├── test_wallet_admin.py        # Wallet balance adjustments
├── test_deposit_withdrawal_admin.py  # Deposit/withdrawal approval
├── test_investment_admin.py    # Investment plans and ROI management
├── test_referral_admin.py      # Referral chains and milestones
├── test_announcements_admin.py # System announcements
└── test_permissions_admin.py   # Security and access control
```

## Test Fixtures and Data

### Factory Boy Factories

The test suite uses factory-boy for generating test data:

- **UserFactory**: Creates regular users, staff users, and superusers
- **WalletFactory**: Generates INR and USDT wallets with balances
- **InvestmentFactory**: Creates investment plans and user investments
- **KYCFactory**: Generates KYC documents in various states
- **TransactionFactory**: Creates wallet transactions for testing

### Test Data Setup

Each test class includes a comprehensive `setUp` method that creates:

- Admin users (staff and superuser)
- Regular users with various KYC statuses
- Wallets with different balance amounts
- Investments in different states
- KYC documents pending approval
- Withdrawal requests
- Referral relationships
- Sample transactions

### Mock Objects

Tests use `unittest.mock.patch` for:

- Notification functions (email, SMS)
- External API calls
- File operations
- Time-based operations

## Coverage Targets

### Module Coverage: 85%+

- **Models**: 100% - All model methods and validation
- **Services**: 90% - Business logic and edge cases
- **Views**: 85% - API endpoints and permission checks
- **Serializers**: 90% - Data validation and transformation
- **Permissions**: 100% - Access control enforcement
- **Admin Interface**: 80% - Django admin customization

### Test Categories Coverage

- **Happy Path**: 100% - All successful operations
- **Error Handling**: 90% - Validation errors and edge cases
- **Permission Checks**: 100% - Access control verification
- **Integration**: 85% - Cross-module data consistency
- **Performance**: 80% - Large dataset handling

## Running Specific Test Categories

### Service Layer Tests

```bash
# Run only service tests
pytest app/admin_panel/tests/ -k "ServiceTest" -v

# Run specific service tests
pytest app/admin_panel/tests/ -k "AdminUserService" -v
```

### API Endpoint Tests

```bash
# Run only API tests
pytest app/admin_panel/tests/ -k "APITest" -v

# Run specific API tests
pytest app/admin_panel/tests/ -k "AdminUserAPITest" -v
```

### Integration Tests

```bash
# Run only integration tests
pytest app/admin_panel/tests/ -k "IntegrationTest" -v

# Run specific integration tests
pytest app/admin_panel/tests/ -k "AdminUserIntegrationTest" -v
```

## Performance Testing

The test suite includes performance tests for:

- **Large Dataset Handling**: Testing with 1000+ users, transactions
- **Bulk Operations**: Bulk user actions, mass KYC processing
- **Database Queries**: Optimized queries with proper indexing
- **Memory Usage**: Efficient test data cleanup

## Continuous Integration

### CI/CD Pipeline Integration

Tests are automatically run in the CI/CD pipeline:

```yaml
# .github/workflows/test.yml
- name: Run Admin Panel Tests
  run: |
    pytest app/admin_panel/tests/ --cov=app.admin_panel --cov-report=xml
    coverage report --fail-under=85
```

### Pre-commit Hooks

Local development includes pre-commit hooks:

```bash
# Install pre-commit hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## Debugging Tests

### Verbose Output

```bash
# Maximum verbosity
pytest app/admin_panel/tests/ -vvv -s

# Show local variables on failure
pytest app/admin_panel/tests/ --tb=long -s
```

### Database Inspection

```bash
# Run tests with database inspection
pytest app/admin_panel/tests/ --reuse-db --create-db

# Debug specific test with database access
pytest app/admin_panel/tests/ -s --pdb
```

### Coverage Analysis

```bash
# Generate detailed coverage report
pytest app/admin_panel/tests/ --cov=app.admin_panel --cov-report=html

# View coverage in browser
open htmlcov/index.html
```

## Test Data Management

### Test Database

- Uses separate test database
- Automatic cleanup after each test
- Transaction rollback for data isolation
- Factory-generated test data

### Data Cleanup

```python
def tearDown(self):
    """Clean up test data after each test"""
    # Django automatically handles cleanup
    pass
```

## Common Test Patterns

### Permission Testing

```python
def test_non_admin_access_denied(self):
    """Test that non-admin users cannot access admin endpoints"""
    self.client.force_authenticate(user=self.regular_user)
    response = self.client.get(self.url)
    self.assertEqual(response.status_code, 403)
```

### Validation Testing

```python
def test_invalid_data_validation(self):
    """Test that invalid data is properly validated"""
    invalid_data = {'amount': -100}
    response = self.client.post(self.url, invalid_data)
    self.assertEqual(response.status_code, 400)
    self.assertIn('amount', response.data)
```

### Integration Testing

```python
def test_wallet_adjustment_updates_balance(self):
    """Test that wallet adjustment correctly updates balance"""
    original_balance = self.user_wallet.balance
    self.service.adjust_balance(self.user_wallet, 100, 'credit')
    self.user_wallet.refresh_from_db()
    self.assertEqual(self.user_wallet.balance, original_balance + 100)
```

## Troubleshooting

### Common Issues

1. **Database Connection**: Ensure test database is properly configured
2. **Factory Dependencies**: Check that all required factories are available
3. **Permission Issues**: Verify user roles and permissions are correctly set
4. **Transaction Rollback**: Ensure tests don't interfere with each other

### Debug Commands

```bash
# Check test database
python manage.py dbshell --database=default

# Verify test settings
python manage.py check --deploy

# Run specific test with debugging
pytest app/admin_panel/tests/ -s --pdb -k "test_name"
```

## Contributing to Tests

### Adding New Tests

1. Follow existing naming conventions
2. Include comprehensive test coverage
3. Add both positive and negative test cases
4. Ensure proper cleanup and isolation
5. Update this README if adding new test categories

### Test Naming Convention

- **Service Tests**: `test_method_name_scenario`
- **API Tests**: `test_endpoint_action_scenario`
- **Integration Tests**: `test_module_integration_scenario`

### Code Quality

- Use descriptive test names
- Include docstrings explaining test purpose
- Follow PEP 8 style guidelines
- Ensure tests are deterministic and repeatable

## Future Enhancements

### Planned Test Improvements

- **Load Testing**: Simulate high-traffic admin operations
- **Security Testing**: Penetration testing for admin endpoints
- **API Contract Testing**: Validate API response schemas
- **Cross-browser Testing**: Admin interface compatibility testing

### Coverage Expansion

- **Edge Cases**: Additional boundary condition testing
- **Error Scenarios**: More comprehensive error handling tests
- **Performance**: Load testing with realistic data volumes
- **Integration**: End-to-end workflow testing

## Support and Resources

### Documentation

- [Django Testing Documentation](https://docs.djangoproject.com/en/stable/topics/testing/)
- [pytest Documentation](https://docs.pytest.org/)
- [Factory Boy Documentation](https://factoryboy.readthedocs.io/)

### Team Resources

- **Test Lead**: [Contact Information]
- **Coverage Reports**: [Coverage Dashboard URL]
- **Test Results**: [CI/CD Dashboard URL]

---

*Last Updated: [Current Date]*
*Test Suite Version: 1.0.0*
