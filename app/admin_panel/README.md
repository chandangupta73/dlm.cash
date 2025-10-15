# 🎛️ Admin Panel Module

## Overview

The Admin Panel module provides comprehensive administrative capabilities for the Investment & Wallet Management System. It includes dashboard analytics, user management, KYC processing, wallet operations, investment management, withdrawal approvals, referral management, transaction monitoring, and announcement system.

## 🏗️ Architecture

### Core Components

- **Models**: `Announcement`, `AdminActionLog`
- **Services**: Business logic layer for all admin operations
- **Views**: REST API endpoints with proper permissions
- **Permissions**: Role-based access control system
- **Serializers**: Data validation and transformation
- **Admin Interface**: Django admin customization

### Security Features

- **Role-based Access Control**: Staff vs Superuser permissions
- **Action Logging**: Complete audit trail of all admin actions
- **Permission Validation**: Granular permission checks for sensitive operations
- **IP Address Tracking**: Log admin actions with IP addresses
- **Transaction Logging**: All wallet modifications are logged

## 📊 Features

### 1. Admin Dashboard
- **Real-time Statistics**: User counts, wallet balances, investment status
- **System Health Monitoring**: Active investments, pending requests
- **Quick Actions**: Direct links to common admin tasks
- **Performance Metrics**: Transaction volumes, referral statistics

### 2. User Management
- **Comprehensive User Views**: Profile, wallet balances, KYC status
- **Bulk Operations**: Activate/deactivate multiple users
- **KYC Management**: Bulk KYC verification/rejection
- **User Blocking**: Temporary/permanent user suspension
- **Advanced Filtering**: Date ranges, status filters, search

### 3. KYC Management
- **Document Review**: View uploaded KYC documents
- **Approval Workflow**: Approve/reject with notes
- **Status Tracking**: Monitor KYC verification progress
- **Bulk Processing**: Handle multiple KYC requests

### 4. Wallet Management
- **Balance Adjustments**: Credit/debit user wallets
- **Admin Override**: Superuser-only balance overrides
- **Transaction Logging**: All modifications are tracked
- **Audit Trail**: Complete history of wallet changes

### 5. Investment Management
- **Plan Oversight**: Monitor active investments
- **ROI Distribution**: Manual ROI triggering
- **Investment Cancellation**: Early termination with refunds
- **Performance Tracking**: Investment success rates

### 6. Withdrawal Management
- **Request Processing**: Approve/reject withdrawal requests
- **Transaction Recording**: Track blockchain transactions
- **Refund Handling**: Automatic refunds for rejected withdrawals
- **Fee Management**: Withdrawal fee calculations

### 7. Referral Management
- **Referral Trees**: Multi-level referral visualization
- **Earnings Adjustment**: Manual referral bonus modifications
- **Chain Analysis**: Referral network insights
- **Performance Metrics**: Referral success rates

### 8. Transaction Monitoring
- **Real-time Logs**: Monitor all system transactions
- **Advanced Filtering**: Date ranges, types, users
- **Export Capabilities**: CSV, PDF, Excel formats
- **Audit Compliance**: Complete transaction history

### 9. Announcement System
- **Targeted Messaging**: User group-specific announcements
- **Scheduling**: Time-based announcement display
- **Priority Management**: Pinned and priority announcements
- **View Tracking**: Monitor announcement engagement

## 🔐 Permissions System

### Permission Levels

1. **Staff Users** (`is_staff=True`)
   - View dashboard statistics
   - Manage users (basic operations)
   - Process KYC documents
   - Approve withdrawals
   - Manage investments
   - View transaction logs

2. **Superusers** (`is_superuser=True`)
   - All staff permissions
   - Wallet balance overrides
   - System configuration
   - Delete users
   - Advanced admin operations

### Permission Classes

```python
# Available permission classes
IsAdminUser          # Staff or superuser
IsSuperUser          # Superuser only
IsStaffUser          # Staff only
AdminActionPermission # Role-based admin actions
WalletOverridePermission # Wallet override operations
KYCApprovalPermission # KYC management
WithdrawalApprovalPermission # Withdrawal processing
InvestmentManagementPermission # Investment operations
ReferralManagementPermission # Referral management
AnnouncementPermission # Announcement system
UserManagementPermission # User operations
TransactionLogPermission # Transaction access
```

## 🚀 API Endpoints

### Base URL: `/api/v1/admin/`

#### Dashboard
- `GET /dashboard/summary/` - Dashboard statistics

#### User Management
- `GET /users/` - List users with filters
- `GET /users/{id}/` - User details
- `PATCH /users/{id}/` - Update user
- `POST /users/{id}/block/` - Block user
- `POST /users/{id}/unblock/` - Unblock user
- `POST /users/bulk_action/` - Bulk user operations

#### KYC Management
- `GET /kyc/` - List KYC documents
- `GET /kyc/{id}/` - KYC document details
- `POST /kyc/{id}/approve/` - Approve KYC
- `POST /kyc/{id}/reject/` - Reject KYC

#### Wallet Management
- `POST /wallet/adjust_balance/` - Adjust wallet balance

#### Investment Management
- `GET /investments/` - List investments
- `GET /investments/{id}/` - Investment details
- `POST /investments/{id}/cancel/` - Cancel investment
- `POST /investments/trigger_roi/` - Trigger ROI distribution

#### Withdrawal Management
- `GET /withdrawals/` - List withdrawals
- `GET /withdrawals/{id}/` - Withdrawal details
- `POST /withdrawals/{id}/approve/` - Approve withdrawal
- `POST /withdrawals/{id}/reject/` - Reject withdrawal

#### Referral Management
- `GET /referrals/` - List referrals
- `GET /referrals/user_tree/` - User referral tree

#### Transaction Monitoring
- `GET /transactions/` - List transactions
- `POST /transactions/export/` - Export transactions

#### Announcement System
- `GET /announcements/` - List announcements
- `POST /announcements/` - Create announcement
- `GET /announcements/{id}/` - Announcement details
- `PATCH /announcements/{id}/` - Update announcement
- `DELETE /announcements/{id}/` - Delete announcement
- `GET /announcements/active_for_user/` - User-specific announcements

#### Admin Action Logs
- `GET /action-logs/` - View admin action history

## 🧪 Testing

### Test Coverage Requirements
- **Minimum Coverage**: 85%
- **Test Types**: Unit, Integration, API, Permission
- **Test Data**: Factory Boy for test data generation
- **Mocking**: Unittest.mock for external dependencies

### Running Tests

```bash
# Run all admin panel tests
python manage.py test app.admin_panel

# Run specific test file
python manage.py test app.admin_panel.tests.test_admin_dashboard

# Run with coverage
pytest --cov=app.admin_panel --cov-report=html

# Run specific test class
python manage.py test app.admin_panel.tests.test_admin_dashboard.AdminDashboardServiceTest
```

### Test Categories

1. **Service Layer Tests**
   - Business logic validation
   - Error handling
   - Transaction management
   - Performance testing

2. **API Tests**
   - Endpoint functionality
   - Permission enforcement
   - Data validation
   - Response formatting

3. **Permission Tests**
   - Role-based access control
   - Permission inheritance
   - Security validation

4. **Integration Tests**
   - Cross-module functionality
   - Database consistency
   - Signal handling

## 📁 File Structure

```
app/admin_panel/
├── __init__.py
├── admin.py              # Django admin interface
├── apps.py               # App configuration
├── models.py             # Data models
├── permissions.py        # Permission classes
├── serializers.py        # Data serialization
├── services.py           # Business logic
├── signals.py            # Django signals
├── urls.py               # URL routing
├── views.py              # API views
├── tests/                # Test suite
│   ├── __init__.py
│   ├── test_admin_dashboard.py
│   ├── test_admin_users.py
│   ├── test_admin_kyc.py
│   ├── test_admin_wallet.py
│   ├── test_admin_investments.py
│   ├── test_admin_withdrawals.py
│   ├── test_admin_referrals.py
│   ├── test_admin_transactions.py
│   └── test_admin_announcements.py
└── README.md             # This file
```

## 🔧 Configuration

### Environment Variables

```bash
# Admin panel specific settings
ADMIN_PANEL_LOG_LEVEL=INFO
ADMIN_PANEL_MAX_BULK_OPERATIONS=100
ADMIN_PANEL_EXPORT_MAX_RECORDS=10000
```

### Django Settings

```python
# Add to INSTALLED_APPS
INSTALLED_APPS = [
    # ... other apps
    'app.admin_panel.apps.AdminPanelConfig',
]

# Admin panel specific settings
ADMIN_PANEL = {
    'MAX_BULK_OPERATIONS': 100,
    'EXPORT_MAX_RECORDS': 10000,
    'ENABLE_ACTION_LOGGING': True,
    'LOG_IP_ADDRESSES': True,
}
```

## 🚀 Deployment

### Production Considerations

1. **Security**
   - HTTPS enforcement
   - IP whitelisting for admin access
   - Rate limiting on admin endpoints
   - Session timeout configuration

2. **Performance**
   - Database query optimization
   - Caching for dashboard statistics
   - Background task processing
   - Connection pooling

3. **Monitoring**
   - Admin action logging
   - Performance metrics
   - Error tracking
   - Audit trail maintenance

### Health Checks

```python
# Admin panel health check endpoint
@action(detail=False, methods=['get'])
def health_check(self, request):
    """Admin panel health check."""
    try:
        # Test database connectivity
        User.objects.count()
        
        # Test service functionality
        AdminDashboardService.get_dashboard_summary()
        
        return Response({'status': 'healthy'})
    except Exception as e:
        return Response(
            {'status': 'unhealthy', 'error': str(e)},
            status=500
        )
```

## 📚 API Documentation

### Swagger/OpenAPI

The admin panel API is documented using drf-yasg. Access the interactive API documentation at:

- **Swagger UI**: `/api/docs/`
- **ReDoc**: `/api/redoc/`

### API Response Format

```json
{
    "data": {...},
    "message": "Operation successful",
    "status": "success",
    "timestamp": "2024-01-01T00:00:00Z"
}
```

### Error Handling

```json
{
    "error": "Error description",
    "code": "ERROR_CODE",
    "details": {...},
    "timestamp": "2024-01-01T00:00:00Z"
}
```

## 🤝 Contributing

### Development Guidelines

1. **Code Style**: Follow PEP 8 and Django conventions
2. **Testing**: Write tests for all new functionality
3. **Documentation**: Update README and docstrings
4. **Security**: Validate all user inputs and permissions
5. **Performance**: Optimize database queries and operations

### Pull Request Process

1. Create feature branch from `main`
2. Implement changes with tests
3. Update documentation
4. Ensure test coverage > 85%
5. Submit pull request with description

## 📞 Support

### Getting Help

- **Documentation**: Check this README first
- **Issues**: Report bugs via GitHub issues
- **Discussions**: Use GitHub discussions for questions
- **Code Review**: Request review for complex changes

### Common Issues

1. **Permission Denied**: Check user role and permissions
2. **Database Errors**: Verify model relationships and constraints
3. **Performance Issues**: Check query optimization and indexing
4. **Export Failures**: Verify file permissions and memory limits

## 📈 Roadmap

### Future Enhancements

- **Advanced Analytics**: Machine learning insights
- **Real-time Notifications**: WebSocket support
- **Mobile Admin App**: React Native admin interface
- **Multi-language Support**: Internationalization
- **Advanced Reporting**: Custom report builder
- **Workflow Automation**: Business process automation
- **Integration APIs**: Third-party system integration

---

**Last Updated**: January 2024  
**Version**: 1.0.0  
**Maintainer**: Development Team
