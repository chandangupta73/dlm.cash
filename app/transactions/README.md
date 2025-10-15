# Transactions Module

## Overview
The Transactions module provides a centralized system for managing all financial transactions across the investment platform. It handles deposits, withdrawals, ROI payouts, referral bonuses, and other financial activities with comprehensive logging, validation, and integration capabilities.

## Features

### Core Functionality
- **Centralized Transaction Management**: Single source of truth for all financial activities
- **Multi-Currency Support**: INR and USDT transactions with proper precision handling
- **Comprehensive Transaction Types**: 8 different transaction categories
- **Real-time Balance Updates**: Automatic wallet balance synchronization
- **Transaction Validation**: Built-in validation and fraud detection
- **Audit Trail**: Complete transaction history with metadata

### Transaction Types
1. **DEPOSIT** - User deposits to wallet
2. **WITHDRAWAL** - User withdrawals from wallet
3. **ROI** - Investment return payouts
4. **REFERRAL_BONUS** - Referral program rewards
5. **MILESTONE_BONUS** - Achievement-based bonuses
6. **ADMIN_ADJUSTMENT** - Administrative balance changes
7. **PLAN_PURCHASE** - Investment plan purchases
8. **BREAKDOWN_REFUND** - Investment breakdown refunds

### Currencies
- **INR** (Indian Rupee) - 2 decimal places precision
- **USDT** (Tether) - 6 decimal places precision

### Status Management
- **PENDING** - Transaction awaiting processing
- **SUCCESS** - Transaction completed successfully
- **FAILED** - Transaction failed or rejected

## Architecture

### Models
- **Transaction**: Central transaction model with comprehensive fields
- **TimeStampedModel**: Abstract base for created/updated timestamps

### Services
- **TransactionService**: Core transaction operations and wallet management
- **TransactionIntegrationService**: Integration with existing modules

### Views
- **TransactionViewSet**: User-facing transaction operations
- **AdminTransactionViewSet**: Administrative transaction management
- **Function-based views**: Additional API endpoints

### Serializers
- **TransactionSerializer**: Full transaction serialization
- **TransactionListSerializer**: Optimized for listing
- **TransactionDetailSerializer**: Detailed transaction view
- **TransactionFilterSerializer**: Filter parameter validation
- **AdminTransactionUpdateSerializer**: Admin update operations

## API Endpoints

### User Endpoints
```
GET /api/transactions/                    # List user transactions
GET /api/transactions/{id}/               # Get transaction details
GET /api/transactions/summary/            # Get transaction summary
GET /api/transactions/filters/            # Get available filters
```

### Admin Endpoints
```
GET /api/admin/transactions/              # List all transactions
GET /api/admin/transactions/{id}/         # Get transaction details
PATCH /api/admin/transactions/{id}/       # Update transaction
GET /api/admin/transactions/export_csv/   # Export to CSV
GET /api/admin/transactions/statistics/   # Get statistics
```

### Legacy Endpoints
```
GET /transactions/                        # User transactions (legacy)
GET /transactions/{id}/                   # Transaction detail (legacy)
GET /admin/transactions/                  # Admin transactions (legacy)
PATCH /admin/transactions/{id}/update/    # Admin update (legacy)
```

## Usage Examples

### Creating a Transaction
```python
from app.transactions.services import TransactionService
from decimal import Decimal

# Create a deposit transaction
transaction = TransactionService.create_transaction(
    user=user,
    type='DEPOSIT',
    currency='INR',
    amount=Decimal('1000.00'),
    reference_id='DEP123',
    meta_data={'payment_method': 'bank_transfer'},
    update_wallet=True
)
```

### Using Integration Service
```python
from app.transactions.services import TransactionIntegrationService

# Log ROI payout
TransactionIntegrationService.log_roi_payout(
    user=user,
    amount=Decimal('50.00'),
    currency='USDT',
    reference_id='ROI456',
    meta_data={'investment_id': 'INV789'}
)
```

### Getting Transaction Summary
```python
from app.transactions.services import TransactionService

# Get user transaction summary
summary = TransactionService.get_transaction_summary(
    user=user,
    currency='INR'
)
```

## Management Commands

### Export Transactions
```bash
# Export all transactions
python manage.py export_transactions

# Export with filters
python manage.py export_transactions --user=john --type=DEPOSIT --currency=INR

# Export to specific file
python manage.py export_transactions --output=my_transactions.csv
```

### Cleanup Transactions
```bash
# Cleanup failed transactions older than 90 days
python manage.py cleanup_transactions

# Cleanup pending transactions older than 30 days
python manage.py cleanup_transactions --days=30 --status=PENDING

# Dry run to see what would be cleaned up
python manage.py cleanup_transactions --dry-run
```

## Utility Functions

### Format Currency Amounts
```python
from app.transactions.utils import format_currency_amount

formatted = format_currency_amount(Decimal('1000.50'), 'INR')
# Returns: "₹1,000.50"
```

### Calculate Transaction Fees
```python
from app.transactions.utils import calculate_transaction_fees

fees = calculate_transaction_fees(Decimal('1000.00'), 'INR', 'WITHDRAWAL')
# Returns: {'processing_fee': Decimal('50.00'), 'network_fee': Decimal('0'), 'total_fee': Decimal('50.00')}
```

### Validate Transaction Data
```python
from app.transactions.utils import validate_transaction_data

validation = validate_transaction_data('WITHDRAWAL', 'INR', Decimal('500.00'), user)
if validation['is_valid']:
    # Proceed with transaction
    pass
else:
    # Handle validation errors
    print(validation['errors'])
```

## Integration

### Signals
The module automatically integrates with existing systems through Django signals:
- **Wallet Transactions**: Migrates old wallet transactions
- **Investment ROI**: Logs ROI payouts automatically
- **Referral Bonuses**: Tracks referral rewards

### Existing Module Integration
- **Wallet Module**: Automatic balance updates
- **Investment Module**: ROI payout logging
- **Referral Module**: Bonus transaction tracking

## Security Features

### Data Validation
- Amount validation (positive values only)
- Currency precision validation
- User status verification
- Balance sufficiency checks

### Fraud Detection
- Transaction frequency monitoring
- Large amount warnings
- Suspicious activity detection

### Access Control
- User isolation (users can only see their own transactions)
- Admin-only operations for sensitive functions
- Audit trail for all changes

## Performance Optimizations

### Database Indexes
- User and transaction type combinations
- Currency and date ranges
- Status and creation time
- Reference ID lookups

### Query Optimization
- Select related for user data
- Efficient filtering and pagination
- Aggregation queries for statistics

### Caching
- Transaction summary caching
- Filter options caching
- Statistics caching

## Testing

### Test Coverage
- **Models**: 400+ lines of comprehensive tests
- **Services**: 629+ lines of service layer tests
- **API**: 671+ lines of API endpoint tests
- **Admin**: 588+ lines of admin interface tests
- **Integration**: 367+ lines of end-to-end tests

### Test Categories
- Unit tests for models and methods
- Integration tests for services
- API tests for all endpoints
- Admin interface tests
- Comprehensive workflow tests

## Configuration

### Django Settings
```python
INSTALLED_APPS = [
    # ... other apps
    'app.transactions',
]
```

### Environment Variables
```bash
# Transaction cleanup settings
TRANSACTION_CLEANUP_DAYS=90
TRANSACTION_CLEANUP_STATUS=FAILED

# Export settings
TRANSACTION_EXPORT_MAX_ROWS=10000
```

## Monitoring and Logging

### Transaction Logging
- All transactions are logged with detailed information
- Metadata includes relevant context and references
- Audit trail for status changes and updates

### Error Handling
- Comprehensive error handling and logging
- Transaction rollback on failures
- Detailed error messages for debugging

### Performance Metrics
- Transaction processing time tracking
- Success/failure rate monitoring
- Volume and frequency analytics

## Future Enhancements

### Planned Features
- **Real-time Notifications**: WebSocket-based transaction updates
- **Advanced Analytics**: Machine learning-based fraud detection
- **Multi-chain Support**: Additional blockchain networks
- **Batch Processing**: Bulk transaction operations
- **API Rate Limiting**: Enhanced security controls

### Scalability Improvements
- **Database Partitioning**: Time-based transaction partitioning
- **Async Processing**: Background transaction processing
- **Microservice Architecture**: Service decomposition
- **Caching Layer**: Redis-based caching

## Support and Maintenance

### Regular Maintenance
- Transaction cleanup (automated)
- Database optimization
- Index maintenance
- Performance monitoring

### Troubleshooting
- Common transaction issues
- Balance reconciliation
- Error resolution guides
- Performance optimization tips

## Contributing

### Development Guidelines
- Follow Django best practices
- Maintain comprehensive test coverage
- Document all new features
- Follow the existing code style

### Code Review Process
- All changes require code review
- Tests must pass before merging
- Documentation updates required
- Performance impact assessment

---

For more information, contact the development team or refer to the API documentation.
