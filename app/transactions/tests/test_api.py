import pytest
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from app.transactions.models import Transaction
from app.transactions.tests.conftest import (
    UserFactory, AdminUserFactory, TransactionFactory, 
    DepositTransactionFactory, WithdrawalTransactionFactory
)

User = get_user_model()


class TransactionAPITest(TestCase):
    """Test cases for the Transaction API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory()
        self.admin_user = AdminUserFactory()
        self.transaction = TransactionFactory(user=self.user)
        
        # Create multiple transactions for testing
        for i in range(15):
            TransactionFactory(
                user=self.user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal(f'{100 + i}.00')
            )
    
    def test_transaction_list_requires_authentication(self):
        """Test that transaction list requires authentication."""
        url = reverse('transaction-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_transaction_list_authenticated_user(self):
        """Test that authenticated users can view their transactions."""
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        
        # Should return paginated results
        self.assertLessEqual(len(response.data['results']), 20)  # Default page size
    
    def test_transaction_list_pagination(self):
        """Test transaction list pagination."""
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-list')
        
        # Test first page
        response = self.client.get(url, {'page': 1, 'page_size': 5})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)
        
        # Test second page
        response = self.client.get(url, {'page': 2, 'page_size': 5})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)
        
        # Test pagination info
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
    
    def test_transaction_list_filtering(self):
        """Test transaction list filtering."""
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-list')
        
        # Filter by type
        response = self.client.get(url, {'type': 'DEPOSIT'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # All results should be deposits
        for transaction in response.data['results']:
            self.assertEqual(transaction['type'], 'DEPOSIT')
        
        # Filter by currency
        response = self.client.get(url, {'currency': 'INR'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # All results should be INR
        for transaction in response.data['results']:
            self.assertEqual(transaction['currency'], 'INR')
    
    def test_transaction_list_ordering(self):
        """Test transaction list ordering."""
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-list')
        
        # Test ordering by amount ascending
        response = self.client.get(url, {'ordering': 'amount'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        amounts = [t['amount'] for t in response.data['results']]
        self.assertEqual(amounts, sorted(amounts))
        
        # Test ordering by amount descending
        response = self.client.get(url, {'ordering': '-amount'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        amounts = [t['amount'] for t in response.data['results']]
        self.assertEqual(amounts, sorted(amounts, reverse=True))
    
    def test_transaction_detail_requires_authentication(self):
        """Test that transaction detail requires authentication."""
        url = reverse('transaction-detail', kwargs={'pk': self.transaction.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_transaction_detail_authenticated_user(self):
        """Test that authenticated users can view transaction details."""
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-detail', kwargs={'pk': self.transaction.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.transaction.id))
        self.assertEqual(response.data['type'], self.transaction.type)
        self.assertEqual(response.data['currency'], self.transaction.currency)
        self.assertEqual(response.data['amount'], str(self.transaction.amount))
    
    def test_transaction_detail_other_user_forbidden(self):
        """Test that users cannot view other users' transactions."""
        other_user = UserFactory()
        other_transaction = TransactionFactory(user=other_user)
        
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-detail', kwargs={'pk': other_transaction.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_transaction_summary_endpoint(self):
        """Test the transaction summary endpoint."""
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-summary')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        
        summary = response.data['data']
        self.assertIn('overall', summary)
        self.assertIn('DEPOSIT', summary)
        
        # Verify overall counts
        self.assertEqual(summary['overall']['total_transactions'], 16)  # 15 deposits + 1 from setUp
    
    def test_transaction_summary_with_currency_filter(self):
        """Test transaction summary with currency filter."""
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-summary')
        
        # Test INR summary
        response = self.client.get(url, {'currency': 'INR'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        summary = response.data['data']
        self.assertIn('overall', summary)
        
        # Should only include INR transactions
        self.assertEqual(summary['overall']['total_transactions'], 16)
    
    def test_transaction_filters_endpoint(self):
        """Test the transaction filters endpoint."""
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-filters')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        
        filters = response.data['data']
        self.assertIn('types', filters)
        self.assertIn('currencies', filters)
        self.assertIn('statuses', filters)
        
        # Should include the types we created
        self.assertIn('DEPOSIT', filters['types'])
        self.assertIn('INR', filters['currencies'])


class AdminTransactionAPITest(TestCase):
    """Test cases for the Admin Transaction API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory()
        self.admin_user = AdminUserFactory()
        
        # Create transactions for different users
        for i in range(25):
            user = UserFactory()
            TransactionFactory(
                user=user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal(f'{100 + i}.00')
            )
    
    def test_admin_transaction_list_requires_admin(self):
        """Test that admin transaction list requires admin permissions."""
        # Regular user
        self.client.force_authenticate(user=self.user)
        url = reverse('admin-transaction-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Admin user
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_admin_transaction_list_pagination(self):
        """Test admin transaction list pagination."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('admin-transaction-list')
        
        response = self.client.get(url, {'page': 1, 'page_size': 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should return paginated results
        self.assertLessEqual(len(response.data['results']), 10)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
    
    def test_admin_transaction_list_filtering(self):
        """Test admin transaction list filtering."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('admin-transaction-list')
        
        # Filter by type
        response = self.client.get(url, {'type': 'DEPOSIT'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # All results should be deposits
        for transaction in response.data['results']:
            self.assertEqual(transaction['type'], 'DEPOSIT')
        
        # Filter by currency
        response = self.client.get(url, {'currency': 'INR'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # All results should be INR
        for transaction in response.data['results']:
            self.assertEqual(transaction['currency'], 'INR')
    
    def test_admin_transaction_export_csv(self):
        """Test admin transaction CSV export."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('admin-transaction-export-csv')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
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
    
    def test_admin_transaction_export_csv_with_filters(self):
        """Test admin transaction CSV export with filters."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('admin-transaction-export-csv')
        
        # Export with type filter
        response = self.client.get(url, {'type': 'DEPOSIT'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify CSV content
        csv_content = response.content.decode('utf-8')
        lines = csv_content.strip().split('\n')
        
        # Should have header + filtered data rows
        self.assertGreater(len(lines), 1)
        
        # All data rows should be deposits
        for line in lines[1:]:  # Skip header
            if line.strip():  # Skip empty lines
                self.assertIn('Deposit', line)
    
    def test_admin_transaction_statistics(self):
        """Test admin transaction statistics endpoint."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('admin-transaction-statistics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        
        stats = response.data['data']
        self.assertIn('overall', stats)
        self.assertIn('by_currency', stats)
        self.assertIn('by_type', stats)
        self.assertIn('by_status', stats)
        
        # Verify overall counts
        self.assertEqual(stats['overall']['total_transactions'], 25)
    
    def test_admin_transaction_update_status(self):
        """Test admin transaction status update."""
        transaction = TransactionFactory(user=self.user, status='PENDING')
        
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('admin-transaction-update-status', kwargs={'pk': transaction.id})
        
        # Update status
        response = self.client.patch(url, {
            'status': 'SUCCESS',
            'meta_data': {'admin_note': 'Approved by admin'}
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify transaction was updated
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, 'SUCCESS')
        self.assertIn('admin_note', transaction.meta_data)
        self.assertEqual(transaction.meta_data['admin_note'], 'Approved by admin')
    
    def test_admin_transaction_update_invalid_status(self):
        """Test admin transaction update with invalid status."""
        transaction = TransactionFactory(user=self.user, status='PENDING')
        
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('admin-transaction-update-status', kwargs={'pk': transaction.id})
        
        # Try to update with invalid status
        response = self.client.patch(url, {
            'status': 'INVALID_STATUS',
            'meta_data': {'admin_note': 'Test'}
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data['errors'])
    
    def test_admin_transaction_update_requires_admin(self):
        """Test that transaction update requires admin permissions."""
        transaction = TransactionFactory(user=self.user, status='PENDING')
        
        # Regular user
        self.client.force_authenticate(user=self.user)
        url = reverse('admin-transaction-update-status', kwargs={'pk': transaction.id})
        response = self.client.patch(url, {'status': 'SUCCESS'})
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Admin user
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(url, {'status': 'SUCCESS'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TransactionSerializerTest(TestCase):
    """Test cases for the Transaction serializers."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.transaction = TransactionFactory(user=self.user)
    
    def test_transaction_serializer_validation(self):
        """Test transaction serializer validation."""
        from app.transactions.serializers import TransactionSerializer
        
        # Valid data
        valid_data = {
            'user_id': self.user.id,
            'type': 'DEPOSIT',
            'currency': 'INR',
            'amount': '100.00',
            'reference_id': 'test_ref',
            'meta_data': {'test': 'value'},
            'status': 'SUCCESS'
        }
        
        serializer = TransactionSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        
        # Invalid amount
        invalid_data = valid_data.copy()
        invalid_data['amount'] = '-100.00'
        
        serializer = TransactionSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('amount', serializer.errors)
        
        # Invalid currency
        invalid_data = valid_data.copy()
        invalid_data['currency'] = 'INVALID'
        
        serializer = TransactionSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('currency', serializer.errors)
        
        # Invalid type
        invalid_data = valid_data.copy()
        invalid_data['type'] = 'INVALID_TYPE'
        
        serializer = TransactionSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('type', serializer.errors)
    
    def test_transaction_filter_serializer_validation(self):
        """Test transaction filter serializer validation."""
        from app.transactions.serializers import TransactionFilterSerializer
        
        # Valid filters
        valid_filters = {
            'type': 'DEPOSIT',
            'currency': 'INR',
            'status': 'SUCCESS',
            'date_from': '2024-01-01',
            'date_to': '2024-12-31',
            'min_amount': '10.00',
            'max_amount': '1000.00',
            'search': 'test'
        }
        
        serializer = TransactionFilterSerializer(data=valid_filters)
        self.assertTrue(serializer.is_valid())
        
        # Invalid date range
        invalid_filters = valid_filters.copy()
        invalid_filters['date_from'] = '2024-12-31'
        invalid_filters['date_to'] = '2024-01-01'
        
        serializer = TransactionFilterSerializer(data=invalid_filters)
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)
        
        # Invalid amount range
        invalid_filters = valid_filters.copy()
        invalid_filters['min_amount'] = '1000.00'
        invalid_filters['max_amount'] = '10.00'
        
        serializer = TransactionFilterSerializer(data=invalid_filters)
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)
    
    def test_admin_transaction_update_serializer(self):
        """Test admin transaction update serializer."""
        from app.transactions.serializers import AdminTransactionUpdateSerializer
        
        # Valid update data
        valid_data = {
            'status': 'SUCCESS',
            'meta_data': {'admin_note': 'Approved'}
        }
        
        serializer = AdminTransactionUpdateSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        
        # Invalid status
        invalid_data = valid_data.copy()
        invalid_data['status'] = 'INVALID_STATUS'
        
        serializer = AdminTransactionUpdateSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('status', serializer.errors)
        
        # Invalid metadata
        invalid_data = valid_data.copy()
        invalid_data['meta_data'] = 'not_a_dict'
        
        serializer = AdminTransactionUpdateSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('meta_data', serializer.errors)


class TransactionIntegrationTest(TestCase):
    """Integration tests for transaction API with other modules."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory()
        self.admin_user = AdminUserFactory()
    
    def test_transaction_creation_flow(self):
        """Test the complete transaction creation flow."""
        from app.transactions.services import TransactionService
        
        # Create transaction through service
        transaction = TransactionService.create_transaction(
            user=self.user,
            type='DEPOSIT',
            currency='INR',
            amount=Decimal('100.00'),
            reference_id='test_ref_123',
            meta_data={'payment_method': 'bank_transfer'}
        )
        
        # Verify transaction was created
        self.assertIsNotNone(transaction.id)
        self.assertEqual(transaction.type, 'DEPOSIT')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, Decimal('100.00'))
        
        # Verify transaction can be retrieved via API
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-detail', kwargs={'pk': transaction.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(transaction.id))
        self.assertEqual(response.data['type'], 'DEPOSIT')
    
    def test_transaction_with_wallet_integration(self):
        """Test transaction creation with wallet balance update."""
        from app.transactions.services import TransactionService
        from app.wallet.models import INRWallet
        
        # Get or create wallet
        wallet, created = INRWallet.objects.get_or_create(
            user=self.user,
            defaults={'balance': Decimal('0.00'), 'status': 'active', 'is_active': True}
        )
        
        initial_balance = wallet.balance
        
        # Create transaction
        transaction = TransactionService.create_transaction(
            user=self.user,
            type='DEPOSIT',
            currency='INR',
            amount=Decimal('500.00'),
            reference_id='wallet_test_ref',
            update_wallet=True
        )
        
        # Verify transaction
        self.assertEqual(transaction.type, 'DEPOSIT')
        self.assertEqual(transaction.status, 'SUCCESS')
        
        # Verify wallet balance updated
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, initial_balance + Decimal('500.00'))
        
        # Verify transaction appears in API
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Find our transaction in the results
        transaction_found = False
        for result in response.data['results']:
            if result['reference_id'] == 'wallet_test_ref':
                transaction_found = True
                self.assertEqual(result['type'], 'DEPOSIT')
                self.assertEqual(result['amount'], '500.00')
                break
        
        self.assertTrue(transaction_found, "Transaction should appear in API results")
    
    def test_transaction_error_handling(self):
        """Test transaction error handling and validation."""
        from app.transactions.services import TransactionService
        
        # Try to create transaction with invalid amount
        with self.assertRaises(ValueError):
            TransactionService.create_transaction(
                user=self.user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal('-100.00'),  # Negative amount
                reference_id='invalid_ref'
            )
        
        # Try to create transaction with invalid currency precision
        with self.assertRaises(ValueError):
            TransactionService.create_transaction(
                user=self.user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal('100.123'),  # Too many decimal places for INR
                reference_id='invalid_ref'
            )
        
        # Try to create transaction for inactive user
        inactive_user = UserFactory(is_active=False)
        
        with self.assertRaises(ValueError):
            TransactionService.create_transaction(
                user=inactive_user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal('100.00'),
                reference_id='invalid_ref'
            )
    
    def test_transaction_pagination_and_filtering_integration(self):
        """Test transaction pagination and filtering integration."""
        # Create multiple transactions
        for i in range(30):
            TransactionFactory(
                user=self.user,
                type='DEPOSIT' if i % 2 == 0 else 'WITHDRAWAL',
                currency='INR' if i % 3 == 0 else 'USDT',
                amount=Decimal(f'{100 + i}.00')
            )
        
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-list')
        
        # Test pagination
        response = self.client.get(url, {'page': 1, 'page_size': 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)
        
        # Test filtering by type
        response = self.client.get(url, {'type': 'DEPOSIT'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # All results should be deposits
        for transaction in response.data['results']:
            self.assertEqual(transaction['type'], 'DEPOSIT')
        
        # Test filtering by currency
        response = self.client.get(url, {'currency': 'USDT'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # All results should be USDT
        for transaction in response.data['results']:
            self.assertEqual(transaction['currency'], 'USDT')
        
        # Test combined filtering and pagination
        response = self.client.get(url, {
            'type': 'DEPOSIT',
            'currency': 'INR',
            'page': 1,
            'page_size': 5
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['results']), 5)
        
        # All results should match both filters
        for transaction in response.data['results']:
            self.assertEqual(transaction['type'], 'DEPOSIT')
            self.assertEqual(transaction['currency'], 'INR')
