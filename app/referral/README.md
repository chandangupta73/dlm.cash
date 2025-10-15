# Referral System

A comprehensive multi-level referral system for the Investment & Wallet Management System that supports configurable referral levels, automatic bonus distribution, milestone rewards, and full admin management.

## Features

### 🎯 Core Functionality
- **Multi-level Referrals**: Configurable up to 5 levels (default: 3 levels)
- **Automatic Bonus Distribution**: Percentage-based earnings on qualifying events
- **Milestone System**: Configurable achievement-based bonuses
- **Unique Referral Codes**: Auto-generated for each user
- **Real-time Statistics**: Live tracking of referrals and earnings

### 💰 Referral Earnings
- **Level 1**: 5% (configurable)
- **Level 2**: 3% (configurable)
- **Level 3**: 1% (configurable)
- **Level 4**: 2% (configurable, if enabled)
- **Level 5**: 1% (configurable, if enabled)

### 🏆 Milestone Bonuses
- **Referral Count Milestones**: Bonus for reaching referral targets
- **Earnings Milestones**: Bonus for reaching earnings targets
- **Configurable Conditions**: Admin-defined milestone criteria
- **Automatic Triggering**: Real-time milestone checking

## Models

### ReferralConfig
Configuration for the referral system including percentages and levels.

```python
class ReferralConfig(TimeStampedModel):
    max_levels = models.PositiveIntegerField(default=3)
    level_1_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    level_2_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    level_3_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    level_4_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    level_5_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
```

### UserReferralProfile
User-specific referral information and statistics.

```python
class UserReferralProfile(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    referral_code = models.CharField(max_length=20, unique=True)
    referred_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    total_referrals = models.PositiveIntegerField(default=0)
    total_earnings_inr = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_earnings_usdt = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    last_earning_date = models.DateTimeField(null=True, blank=True)
```

### Referral
Tracks referral relationships between users at different levels.

```python
class Referral(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals')
    referred_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referred_by')
    level = models.PositiveIntegerField()
    referrer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
```

### ReferralEarning
Records all referral earnings and transactions.

```python
class ReferralEarning(TimeStampedModel):
    referral = models.ForeignKey(Referral, on_delete=models.CASCADE)
    investment = models.ForeignKey('investment.Investment', on_delete=models.CASCADE)
    level = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES)
    percentage_used = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    credited_at = models.DateTimeField(null=True, blank=True)
```

### ReferralMilestone
Defines milestone conditions and bonus amounts.

```python
class ReferralMilestone(TimeStampedModel):
    name = models.CharField(max_length=100)
    condition_type = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    condition_value = models.DecimalField(max_digits=15, decimal_places=2)
    bonus_amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES)
    is_active = models.BooleanField(default=True)
```

## API Endpoints

### User Endpoints

#### GET `/referrals/profile/`
Get user's referral profile and statistics.

**Response:**
```json
{
    "user": 1,
    "referral_code": "ABC123",
    "referred_by": null,
    "total_referrals": 5,
    "total_earnings_inr": "150.00",
    "total_earnings_usdt": "25.00",
    "last_earning_date": "2024-01-15T10:30:00Z"
}
```

#### GET `/referrals/tree/`
Get user's referral tree with direct and indirect referrals.

**Response:**
```json
{
    "direct_referrals": [
        {
            "user_id": 2,
            "email": "user2@example.com",
            "level": 1,
            "join_date": "2024-01-10T09:00:00Z"
        }
    ],
    "sub_referrals": [
        {
            "user_id": 3,
            "email": "user3@example.com",
            "level": 2,
            "join_date": "2024-01-12T14:00:00Z"
        }
    ],
    "total_referrals": 2,
    "total_earnings": {
        "inr": "150.00",
        "usdt": "25.00"
    }
}
```

#### GET `/referrals/earnings/`
Get user's referral earnings with optional filters.

**Query Parameters:**
- `currency`: Filter by currency (INR/USDT)
- `level`: Filter by referral level
- `date_from`: Filter by start date
- `date_to`: Filter by end date

**Response:**
```json
[
    {
        "id": 1,
        "level": 1,
        "amount": "50.00",
        "currency": "INR",
        "percentage_used": "5.00",
        "status": "credited",
        "created_at": "2024-01-15T10:30:00Z",
        "credited_at": "2024-01-15T10:30:00Z"
    }
]
```

#### GET `/referrals/earnings/summary/`
Get summary of user's referral earnings.

**Response:**
```json
{
    "total_earnings_inr": "150.00",
    "total_earnings_usdt": "25.00",
    "total_earnings": "175.00",
    "total_referrals": 5,
    "last_earning_date": "2024-01-15T10:30:00Z"
}
```

#### POST `/referrals/validate-code/`
Validate a referral code.

**Request:**
```json
{
    "referral_code": "ABC123"
}
```

**Response:**
```json
{
    "is_valid": true,
    "referrer_id": 1,
    "referrer_email": "user1@example.com"
}
```

### Admin Endpoints

#### GET `/admin/referrals/`
Get list of all referrals with filtering and pagination.

**Query Parameters:**
- `user`: Filter by user ID
- `level`: Filter by referral level
- `created_after`: Filter by creation date
- `page`: Page number for pagination

#### GET `/admin/referrals/earnings/`
Get list of all referral earnings.

#### GET `/admin/milestones/`
Get list of all milestones.

#### POST `/admin/milestones/`
Create a new milestone.

**Request:**
```json
{
    "name": "10 Referrals",
    "condition_type": "total_referrals",
    "condition_value": 10,
    "bonus_amount": "100.00",
    "currency": "INR",
    "is_active": true
}
```

#### GET `/admin/milestones/{id}/`
Get milestone details.

#### POST `/admin/milestones/{id}/`
Update existing milestone.

#### GET `/admin/referrals/config/`
Get current referral configuration.

#### POST `/admin/referrals/config/`
Update referral configuration.

**Request:**
```json
{
    "max_levels": 5,
    "level_1_percentage": "7.0",
    "level_2_percentage": "5.0",
    "level_3_percentage": "3.0",
    "level_4_percentage": "2.0",
    "level_5_percentage": "1.0",
    "is_active": true
}
```

#### GET `/admin/referrals/stats/`
Get referral system statistics.

**Response:**
```json
{
    "total_users": 100,
    "total_referrals": 250,
    "total_earnings": {
        "inr": "5000.00",
        "usdt": "750.00"
    },
    "active_milestones": 5
}
```

## Usage

### Setting Up Referral System

1. **Add to INSTALLED_APPS**:
```python
INSTALLED_APPS = [
    # ... other apps
    'app.referral',
]
```

2. **Run Migrations**:
```bash
python manage.py makemigrations
python manage.py migrate
```

3. **Create Initial Configuration**:
```python
from app.referral.models import ReferralConfig

ReferralConfig.objects.create(
    max_levels=3,
    level_1_percentage=5.0,
    level_2_percentage=3.0,
    level_3_percentage=1.0,
    is_active=True
)
```

### Creating Referral Chains

```python
from app.referral.services import ReferralService

# User2 registers using User1's referral code
ReferralService.create_referral_chain(
    user=user2,
    referrer_code=user1.referralprofile.referral_code
)
```

### Processing Investment Referrals

```python
from app.referral.services import ReferralService

# This is automatically called via signals when an investment is created
ReferralService.process_investment_referral_bonus(investment)
```

### Checking Milestones

```python
from app.referral.services import ReferralService

# Check if user has achieved any milestones
triggered_milestones = ReferralService.check_milestones(user)
```

## Signals

The referral system uses Django signals for automatic operations:

- **User Creation**: Automatically creates `UserReferralProfile`
- **Investment Creation**: Triggers referral bonus processing
- **ReferralEarning Creation**: Updates user statistics
- **Referral Creation**: Updates referrer statistics
- **User Deletion**: Cleans up referral data

## Admin Interface

The referral system provides a comprehensive admin interface with:

- **Custom List Views**: Enhanced displays with user-friendly information
- **Filtering & Search**: Advanced filtering and search capabilities
- **Custom Actions**: Regenerate referral codes, update statistics
- **Statistics Dashboard**: Overview of referral system performance

## Testing

### Running Tests

```bash
# Run all referral tests
python app/referral/tests/run_tests.py

# Run with coverage
python app/referral/tests/run_tests.py --coverage

# Run specific test
python app/referral/tests/run_tests.py --test app.referral.tests.test_models
```

### Test Coverage

The referral system includes comprehensive tests covering:

- **Models**: Field validation, relationships, methods
- **Services**: Business logic, calculations, chain creation
- **Views**: API endpoints, permissions, data validation
- **Signals**: Automatic operations, data consistency
- **Admin**: Interface functionality, custom methods
- **Integration**: Complete workflows, error handling

Target coverage: **85%+**

## Configuration

### Environment Variables

```bash
# Referral System Configuration
REFERRAL_MAX_LEVELS=3
REFERRAL_LEVEL_1_PERCENTAGE=5.0
REFERRAL_LEVEL_2_PERCENTAGE=3.0
REFERRAL_LEVEL_3_PERCENTAGE=1.0
```

### Database Configuration

The referral system supports PostgreSQL and includes optimized queries for:

- Referral chain traversal
- Earnings calculations
- Milestone checking
- Statistics aggregation

## Performance Considerations

- **Database Indexes**: Optimized for referral queries
- **Caching**: Configurable caching for frequently accessed data
- **Batch Operations**: Efficient bulk operations for large datasets
- **Async Processing**: Background tasks for non-critical operations

## Security Features

- **Permission Checks**: Role-based access control
- **Data Validation**: Comprehensive input validation
- **SQL Injection Protection**: Parameterized queries
- **XSS Protection**: Output sanitization

## Monitoring & Logging

- **Transaction Logging**: All referral operations are logged
- **Error Tracking**: Comprehensive error logging and monitoring
- **Performance Metrics**: Response time and throughput monitoring
- **Audit Trail**: Complete history of all referral activities

## Future Enhancements

- **Real-time Notifications**: WebSocket support for live updates
- **Advanced Analytics**: Detailed reporting and insights
- **Mobile SDK**: Native mobile app integration
- **Multi-currency Support**: Extended currency support
- **Referral Campaigns**: Time-limited promotional campaigns

## Support

For questions or issues with the referral system:

1. Check the test suite for usage examples
2. Review the admin interface for configuration options
3. Examine the signal handlers for integration points
4. Consult the API documentation for endpoint details

## License

This referral system is part of the Investment & Wallet Management System and follows the same licensing terms.



