import pytest
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.contrib.admin.sites import site
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION

from app.transactions.models import Transaction
from app.transactions.admin import TransactionAdmin
from app.transactions.tests.conftest import (
    UserFactory, AdminUserFactory, TransactionFactory,
    DepositTransactionFactory, WithdrawalTransactionFactory
)

User = get_user_model()


class TransactionAdminTest(TestCase):
    """Test cases for the Transaction admin interface."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = UserFactory()
        self.admin_user = AdminUserFactory()
        self.transaction = TransactionFactory(user=self.user)
        
        # Create multiple transactions for testing
        for i in range(20):
            TransactionFactory(
                user=self.user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal(f'{100 + i}.00')
            )
    
    def test_transaction_admin_registration(self):
        """Test that Transaction model is properly registered in admin."""
        self.assertIn(Transaction, site._registry)
        admin_class = site._registry[Transaction]
        self.assertIsInstance(admin_class, TransactionAdmin)
    
    def test_transaction_admin_list_display(self):
        """Test transaction admin list display fields."""
        admin_class = site._registry[Transaction]
        expected_fields = [
            'id', 'user', 'type', 'currency', 'amount', 'status', 
            'reference_id', 'created_at', 'formatted_amount_display'
        ]
        
        for field in expected_fields:
            self.assertIn(field, admin_class.list_display)
    
    def test_transaction_admin_list_filter(self):
        """Test transaction admin list filters."""
        admin_class = site._registry[Transaction]
        expected_filters = [
            'TransactionTypeFilter', 'TransactionStatusFilter', 
            'TransactionCurrencyFilter', 'created_at', 
            ('user', 'RelatedOnlyFieldFilter')
        ]
        
        # Check that all expected filters are present
        filter_names = [filter.__class__.__name__ if hasattr(filter, '__class__') else str(filter) for filter in admin_class.list_filter]
        
        for expected_filter in expected_filters:
            if isinstance(expected_filter, tuple):
                # Handle tuple filters like ('user', 'RelatedOnlyFieldFilter')
                self.assertIn(expected_filter[0], [f[0] for f in admin_class.list_filter if isinstance(f, tuple)])
            else:
                self.assertIn(expected_filter, filter_names)
    
    def test_transaction_admin_search_fields(self):
        """Test transaction admin search fields."""
        admin_class = site._registry[Transaction]
        expected_search_fields = [
            'user__username', 'user__email', 'user__first_name', 
            'user__last_name', 'reference_id'
        ]
        
        for field in expected_search_fields:
            self.assertIn(field, admin_class.search_fields)
    
    def test_transaction_admin_readonly_fields(self):
        """Test transaction admin readonly fields."""
        admin_class = site._registry[Transaction]
        expected_readonly_fields = [
            'id', 'created_at', 'updated_at', 'formatted_amount_display'
        ]
        
        for field in expected_readonly_fields:
            self.assertIn(field, admin_class.readonly_fields)
    
    def test_transaction_admin_fieldsets(self):
        """Test transaction admin fieldsets configuration."""
        admin_class = site._registry[Transaction]
        fieldsets = admin_class.fieldsets
        
        # Check that fieldsets are defined
        self.assertIsNotNone(fieldsets)
        self.assertGreater(len(fieldsets), 0)
        
        # Check for expected fieldset sections
        fieldset_names = [fieldset[0] for fieldset in fieldsets]
        expected_sections = ['Basic Information', 'Reference & Metadata', 'Timestamps']
        
        for section in expected_sections:
            self.assertIn(section, fieldset_names)
    
    def test_transaction_admin_list_per_page(self):
        """Test transaction admin list per page setting."""
        admin_class = site._registry[Transaction]
        self.assertEqual(admin_class.list_per_page, 50)
    
    def test_transaction_admin_date_hierarchy(self):
        """Test transaction admin date hierarchy."""
        admin_class = site._registry[Transaction]
        self.assertEqual(admin_class.date_hierarchy, 'created_at')
    
    def test_transaction_admin_formatted_amount_display(self):
        """Test the formatted amount display method."""
        admin_class = site._registry[Transaction]
        
        # Test INR formatting
        inr_transaction = TransactionFactory(
            user=self.user,
            currency='INR',
            amount=Decimal('1234.56')
        )
        
        formatted_amount = admin_class.formatted_amount_display(inr_transaction)
        self.assertIn('₹1,234.56', formatted_amount)
        self.assertIn('color: #28a745', formatted_amount)
        
        # Test USDT formatting
        usdt_transaction = TransactionFactory(
            user=self.user,
            currency='USDT',
            amount=Decimal('1234.567890')
        )
        
        formatted_amount = admin_class.formatted_amount_display(usdt_transaction)
        self.assertIn('$1,234.567890', formatted_amount)
        self.assertIn('color: #007bff', formatted_amount)
    
    def test_transaction_admin_user_link(self):
        """Test the user link method."""
        admin_class = site._registry[Transaction]
        
        # Test with valid user
        user_link = admin_class.user_link(self.transaction)
        self.assertIn('href', user_link)
        self.assertIn(str(self.user.id), user_link)
        self.assertIn(self.user.username, user_link)
        
        # Test with no user
        transaction_no_user = TransactionFactory(user=None)
        user_link = admin_class.user_link(transaction_no_user)
        self.assertEqual(user_link, '-')
    
    def test_transaction_admin_permissions(self):
        """Test transaction admin permissions."""
        admin_class = site._registry[Transaction]
        
        # Test add permission
        self.assertTrue(admin_class.has_add_permission(self.admin_user))
        self.assertFalse(admin_class.has_add_permission(self.user))
        
        # Test delete permission
        self.assertTrue(admin_class.has_delete_permission(self.admin_user))
        self.assertFalse(admin_class.has_delete_permission(self.user))
        
        # Test change permission
        self.assertTrue(admin_class.has_change_permission(self.admin_user))
        self.assertTrue(admin_class.has_change_permission(self.user))  # Staff users can change
    
    def test_transaction_admin_readonly_fields_by_permission(self):
        """Test that readonly fields change based on user permissions."""
        admin_class = site._registry[Transaction]
        
        # For superuser
        readonly_fields = admin_class.get_readonly_fields(self.admin_user)
        self.assertNotIn('type', readonly_fields)
        self.assertNotIn('currency', readonly_fields)
        self.assertNotIn('amount', readonly_fields)
        self.assertNotIn('user', readonly_fields)
        
        # For regular staff user
        readonly_fields = admin_class.get_readonly_fields(self.user)
        self.assertIn('type', readonly_fields)
        self.assertIn('currency', readonly_fields)
        self.assertIn('amount', readonly_fields)
        self.assertIn('user', readonly_fields)
    
    def test_transaction_admin_list_display_by_permission(self):
        """Test that list display changes based on user permissions."""
        admin_class = site._registry[Transaction]
        
        # For superuser
        list_display = admin_class.get_list_display(self.admin_user)
        self.assertIn('user_link', list_display)
        
        # For regular staff user
        list_display = admin_class.get_list_display(self.user)
        self.assertNotIn('user_link', list_display)
    
    def test_transaction_admin_export_csv_action(self):
        """Test the CSV export action."""
        admin_class = site._registry[Transaction]
        
        # Get the export action
        actions = admin_class.get_actions(self.admin_user)
        self.assertIn('export_selected_csv', actions)
        
        # Test the export method
        response = admin_class.export_selected_csv(
            self.admin_user, 
            Transaction.objects.all()
        )
        
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        
        # Verify CSV content
        csv_content = response.content.decode('utf-8')
        lines = csv_content.strip().split('\n')
        
        # Should have header + data rows
        self.assertGreater(len(lines), 1)
        
        # Check header
        header = lines[0]
        expected_headers = ['Transaction ID', 'Username', 'Email', 'Type', 'Currency', 'Amount', 'Status', 'Reference ID', 'Created At', 'Updated At']
        for header_field in expected_headers:
            self.assertIn(header_field, header)
    
    def test_transaction_admin_changelist_view(self):
        """Test the changelist view with statistics."""
        admin_class = site._registry[Transaction]
        
        # Mock request
        class MockRequest:
            def __init__(self):
                self.user = self.admin_user
        
        request = MockRequest()
        request.user = self.admin_user
        
        # Test changelist view
        extra_context = {}
        response = admin_class.changelist_view(request, extra_context)
        
        # Verify extra context was added
        self.assertIn('total_transactions', extra_context)
        self.assertIn('total_volume', extra_context)
        self.assertIn('inr_stats', extra_context)
        self.assertIn('usdt_stats', extra_context)
        self.assertIn('type_stats', extra_context)
        self.assertIn('recent_transactions', extra_context)
        
        # Verify statistics values
        self.assertEqual(extra_context['total_transactions'], 21)  # 20 + 1 from setUp
        self.assertGreater(extra_context['total_volume'], 0)
        self.assertGreater(extra_context['recent_transactions'], 0)


class TransactionAdminFiltersTest(TestCase):
    """Test cases for the custom admin filters."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        
        # Create transactions of different types
        TransactionFactory(user=self.user, type='DEPOSIT', currency='INR')
        TransactionFactory(user=self.user, type='WITHDRAWAL', currency='INR')
        TransactionFactory(user=self.user, type='ROI', currency='USDT')
        TransactionFactory(user=self.user, type='REFERRAL_BONUS', currency='INR')
    
    def test_transaction_type_filter(self):
        """Test the transaction type filter."""
        from app.transactions.admin import TransactionTypeFilter
        
        filter_instance = TransactionTypeFilter()
        
        # Test lookups
        lookups = filter_instance.lookups(None, None)
        expected_types = ['DEPOSIT', 'WITHDRAWAL', 'ROI', 'REFERRAL_BONUS', 'MILESTONE_BONUS', 'ADMIN_ADJUSTMENT', 'PLAN_PURCHASE', 'BREAKDOWN_REFUND']
        
        for expected_type in expected_types:
            self.assertIn((expected_type, expected_type), lookups)
        
        # Test filtering
        queryset = Transaction.objects.all()
        filtered_queryset = filter_instance.queryset(None, queryset)
        
        # Should return all transactions when no filter applied
        self.assertEqual(filtered_queryset.count(), 4)
        
        # Test with specific type filter
        filter_instance.value = lambda: 'DEPOSIT'
        filtered_queryset = filter_instance.queryset(None, queryset)
        self.assertEqual(filtered_queryset.count(), 1)
        self.assertEqual(filtered_queryset.first().type, 'DEPOSIT')
    
    def test_transaction_status_filter(self):
        """Test the transaction status filter."""
        from app.transactions.admin import TransactionStatusFilter
        
        filter_instance = TransactionStatusFilter()
        
        # Test lookups
        lookups = filter_instance.lookups(None, None)
        expected_statuses = ['PENDING', 'SUCCESS', 'FAILED']
        
        for expected_status in expected_statuses:
            self.assertIn((expected_status, expected_status), lookups)
        
        # Test filtering
        queryset = Transaction.objects.all()
        filtered_queryset = filter_instance.queryset(None, queryset)
        
        # Should return all transactions when no filter applied
        self.assertEqual(filtered_queryset.count(), 4)
        
        # Test with specific status filter
        filter_instance.value = lambda: 'SUCCESS'
        filtered_queryset = filter_instance.queryset(None, queryset)
        self.assertEqual(filtered_queryset.count(), 4)  # All transactions are SUCCESS by default
    
    def test_transaction_currency_filter(self):
        """Test the transaction currency filter."""
        from app.transactions.admin import TransactionCurrencyFilter
        
        filter_instance = TransactionCurrencyFilter()
        
        # Test lookups
        lookups = filter_instance.lookups(None, None)
        expected_currencies = ['INR', 'USDT']
        
        for expected_currency in expected_currencies:
            self.assertIn((expected_currency, expected_currency), lookups)
        
        # Test filtering
        queryset = Transaction.objects.all()
        filtered_queryset = filter_instance.queryset(None, queryset)
        
        # Should return all transactions when no filter applied
        self.assertEqual(filtered_queryset.count(), 4)
        
        # Test with specific currency filter
        filter_instance.value = lambda: 'INR'
        filtered_queryset = filter_instance.queryset(None, queryset)
        self.assertEqual(filtered_queryset.count(), 3)  # 3 INR transactions
        
        filter_instance.value = lambda: 'USDT'
        filtered_queryset = filter_instance.queryset(None, queryset)
        self.assertEqual(filtered_queryset.count(), 1)  # 1 USDT transaction


class TransactionAdminIntegrationTest(TestCase):
    """Integration tests for transaction admin functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = UserFactory()
        self.admin_user = AdminUserFactory()
        
        # Create transactions
        for i in range(10):
            TransactionFactory(
                user=self.user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal(f'{100 + i}.00')
            )
    
    def test_admin_login_required(self):
        """Test that admin requires login."""
        url = reverse('admin:app_transactions_transaction_changelist')
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_admin_staff_access(self):
        """Test that staff users can access admin."""
        self.client.force_login(self.user)
        url = reverse('admin:app_transactions_transaction_changelist')
        response = self.client.get(url)
        
        # Staff users can access admin
        self.assertEqual(response.status_code, 200)
    
    def test_admin_superuser_access(self):
        """Test that superusers can access admin with full permissions."""
        self.client.force_login(self.admin_user)
        url = reverse('admin:app_transactions_transaction_changelist')
        response = self.client.get(url)
        
        # Superusers can access admin
        self.assertEqual(response.status_code, 200)
        
        # Check that admin interface shows expected elements
        self.assertIn('Transaction', response.content.decode())
        self.assertIn('Add transaction', response.content.decode())
    
    def test_admin_transaction_list_view(self):
        """Test the admin transaction list view."""
        self.client.force_login(self.admin_user)
        url = reverse('admin:app_transactions_transaction_changelist')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that transactions are displayed
        content = response.content.decode()
        self.assertIn('DEPOSIT', content)
        self.assertIn('INR', content)
        self.assertIn('100.00', content)
    
    def test_admin_transaction_detail_view(self):
        """Test the admin transaction detail view."""
        transaction = Transaction.objects.first()
        
        self.client.force_login(self.admin_user)
        url = reverse('admin:app_transactions_transaction_change', args=[transaction.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that transaction details are displayed
        content = response.content.decode()
        self.assertIn(str(transaction.id), content)
        self.assertIn(transaction.type, content)
        self.assertIn(transaction.currency, content)
    
    def test_admin_transaction_change_permissions(self):
        """Test transaction change permissions in admin."""
        transaction = Transaction.objects.first()
        
        # Regular staff user
        self.client.force_login(self.user)
        url = reverse('admin:app_transactions_transaction_change', args=[transaction.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that certain fields are readonly for staff users
        content = response.content.decode()
        # The readonly fields should be enforced by the form
    
    def test_admin_transaction_add_permission(self):
        """Test transaction add permission in admin."""
        # Regular staff user
        self.client.force_login(self.user)
        url = reverse('admin:app_transactions_transaction_add')
        response = self.client.get(url)
        
        # Staff users cannot add transactions
        self.assertEqual(response.status_code, 403)
        
        # Superuser
        self.client.force_login(self.admin_user)
        response = self.client.get(url)
        
        # Superusers can add transactions
        self.assertEqual(response.status_code, 200)
    
    def test_admin_transaction_delete_permission(self):
        """Test transaction delete permission in admin."""
        transaction = Transaction.objects.first()
        
        # Regular staff user
        self.client.force_login(self.user)
        url = reverse('admin:app_transactions_transaction_delete', args=[transaction.id])
        response = self.client.get(url)
        
        # Staff users cannot delete transactions
        self.assertEqual(response.status_code, 403)
        
        # Superuser
        self.client.force_login(self.admin_user)
        response = self.client.get(url)
        
        # Superusers can delete transactions
        self.assertEqual(response.status_code, 200)
    
    def test_admin_transaction_search(self):
        """Test transaction search functionality in admin."""
        self.client.force_login(self.admin_user)
        url = reverse('admin:app_transactions_transaction_changelist')
        
        # Search by username
        response = self.client.get(url, {'q': self.user.username})
        self.assertEqual(response.status_code, 200)
        
        # Search by email
        response = self.client.get(url, {'q': self.user.email})
        self.assertEqual(response.status_code, 200)
        
        # Search by reference ID
        transaction = Transaction.objects.first()
        if transaction.reference_id:
            response = self.client.get(url, {'q': transaction.reference_id})
            self.assertEqual(response.status_code, 200)
    
    def test_admin_transaction_filtering(self):
        """Test transaction filtering in admin."""
        self.client.force_login(self.admin_user)
        url = reverse('admin:app_transactions_transaction_changelist')
        
        # Filter by type
        response = self.client.get(url, {'type': 'DEPOSIT'})
        self.assertEqual(response.status_code, 200)
        
        # Filter by currency
        response = self.client.get(url, {'currency': 'INR'})
        self.assertEqual(response.status_code, 200)
        
        # Filter by status
        response = self.client.get(url, {'status': 'SUCCESS'})
        self.assertEqual(response.status_code, 200)
    
    def test_admin_transaction_ordering(self):
        """Test transaction ordering in admin."""
        self.client.force_login(self.admin_user)
        url = reverse('admin:app_transactions_transaction_changelist')
        
        # Order by created_at descending (default)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Order by amount
        response = self.client.get(url, {'o': '1.1'})  # amount ascending
        self.assertEqual(response.status_code, 200)
        
        response = self.client.get(url, {'o': '-1.1'})  # amount descending
        self.assertEqual(response.status_code, 200)
    
    def test_admin_transaction_actions(self):
        """Test transaction admin actions."""
        self.client.force_login(self.admin_user)
        url = reverse('admin:app_transactions_transaction_changelist')
        
        # Get the changelist to see available actions
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Check that export action is available for superusers
        content = response.content.decode()
        self.assertIn('Export selected transactions to CSV', content)
    
    def test_admin_transaction_export_action(self):
        """Test the CSV export action from admin interface."""
        self.client.force_login(self.admin_user)
        
        # Select some transactions
        transactions = Transaction.objects.all()[:5]
        transaction_ids = [str(t.id) for t in transactions]
        
        # Perform export action
        url = reverse('admin:app_transactions_transaction_changelist')
        response = self.client.post(url, {
            'action': 'export_selected_csv',
            '_selected_action': transaction_ids
        })
        
        # Should get CSV response
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        
        # Verify CSV content
        csv_content = response.content.decode('utf-8')
        lines = csv_content.strip().split('\n')
        
        # Should have header + selected data rows
        self.assertEqual(len(lines), 6)  # 1 header + 5 data rows
        
        # Check header
        header = lines[0]
        expected_headers = ['Transaction ID', 'Username', 'Email', 'Type', 'Currency', 'Amount', 'Status', 'Reference ID', 'Created At', 'Updated At']
        for header_field in expected_headers:
            self.assertIn(header_field, header)
