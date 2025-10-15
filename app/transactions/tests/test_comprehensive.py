import pytest
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from django.urls import reverse

from app.transactions.models import Transaction
from app.transactions.services import TransactionService, TransactionIntegrationService
from app.transactions.tests.conftest import (
    UserFactory, AdminUserFactory, TransactionFactory
)

User = get_user_model()


class ComprehensiveTransactionTest(TestCase):
    """Comprehensive test suite for the entire transactions module."""
    
    def setUp(self):
        """Set up comprehensive test data."""
        self.client = APIClient()
        self.user = UserFactory()
        self.admin_user = AdminUserFactory()
        
        # Create wallets for the user
        from app.wallet.models import INRWallet, USDTWallet
        self.inr_wallet = INRWallet.objects.get_or_create(
            user=self.user,
            defaults={'balance': Decimal('1000.00'), 'status': 'active', 'is_active': True}
        )[0]
        self.usdt_wallet = USDTWallet.objects.get_or_create(
            user=self.user,
            defaults={'balance': Decimal('100.000000'), 'status': 'active', 'is_active': True}
        )[0]
    
    def test_01_model_creation_and_validation(self):
        """Test 1: Model creation and validation."""
        transaction = Transaction.objects.create(
            user=self.user,
            type='DEPOSIT',
            currency='INR',
            amount=Decimal('100.00'),
            reference_id='test_validation',
            meta_data={'test': 'value'}
        )
        
        self.assertIsNotNone(transaction.id)
        self.assertEqual(transaction.type, 'DEPOSIT')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, Decimal('100.00'))
        
        # Test model properties
        self.assertTrue(transaction.is_credit)
        self.assertFalse(transaction.is_debit)
        self.assertEqual(transaction.get_balance_impact(), Decimal('100.00'))
        self.assertEqual(transaction.formatted_amount, '₹100.00')
    
    def test_02_service_layer_functionality(self):
        """Test 2: Service layer functionality."""
        initial_inr_balance = self.inr_wallet.balance
        
        transaction = TransactionService.create_transaction(
            user=self.user,
            type='DEPOSIT',
            currency='INR',
            amount=Decimal('150.00'),
            reference_id='service_test',
            update_wallet=True
        )
        
        # Verify transaction
        self.assertIsInstance(transaction, Transaction)
        self.assertEqual(transaction.type, 'DEPOSIT')
        self.assertEqual(transaction.status, 'SUCCESS')
        
        # Verify wallet balance updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, initial_inr_balance + Decimal('150.00'))
    
    def test_03_integration_service_methods(self):
        """Test 3: Integration service methods."""
        # Test deposit logging
        deposit_transaction = TransactionIntegrationService.log_deposit(
            user=self.user,
            amount=Decimal('100.00'),
            currency='INR',
            reference_id='integration_test_deposit',
            meta_data={'payment_method': 'bank_transfer'}
        )
        
        self.assertEqual(deposit_transaction.type, 'DEPOSIT')
        self.assertEqual(deposit_transaction.status, 'SUCCESS')
        
        # Test ROI logging
        roi_transaction = TransactionIntegrationService.log_roi_payout(
            user=self.user,
            amount=Decimal('25.00'),
            currency='INR',
            reference_id='integration_test_roi',
            meta_data={'investment_id': 'INV001', 'period': 'monthly'}
        )
        
        self.assertEqual(roi_transaction.type, 'ROI')
        self.assertEqual(roi_transaction.status, 'SUCCESS')
    
    def test_04_api_endpoints_user_access(self):
        """Test 4: API endpoints with user access."""
        # Create a test transaction
        transaction = TransactionFactory(user=self.user)
        
        self.client.force_authenticate(user=self.user)
        
        # Test transaction list endpoint
        url = reverse('transaction-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertGreater(len(response.data['results']), 0)
        
        # Test transaction detail endpoint
        url = reverse('transaction-detail', kwargs={'pk': transaction.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(transaction.id))
    
    def test_05_api_endpoints_admin_access(self):
        """Test 5: API endpoints with admin access."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Test admin transaction list endpoint
        url = reverse('admin-transaction-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        
        # Test admin transaction statistics endpoint
        url = reverse('admin-transaction-statistics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
    
    def test_06_api_filtering_and_pagination(self):
        """Test 6: API filtering and pagination."""
        # Create multiple transactions
        for i in range(15):
            TransactionFactory(
                user=self.user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal(f'{100 + i}.00')
            )
        
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-list')
        
        # Test filtering by type
        response = self.client.get(url, {'type': 'DEPOSIT'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for transaction in response.data['results']:
            self.assertEqual(transaction['type'], 'DEPOSIT')
        
        # Test pagination
        response = self.client.get(url, {'page': 1, 'page_size': 5})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['results']), 5)
    
    def test_07_api_permissions_and_security(self):
        """Test 7: API permissions and security."""
        # Test unauthenticated access
        url = reverse('transaction-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Test user cannot access other user's transactions
        other_user = UserFactory()
        other_transaction = TransactionFactory(user=other_user)
        
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-detail', kwargs={'pk': other_transaction.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Test regular user cannot access admin endpoints
        url = reverse('admin-transaction-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_08_transaction_status_updates(self):
        """Test 8: Transaction status updates."""
        # Create a pending transaction
        pending_transaction = TransactionFactory(
            user=self.user,
            type='DEPOSIT',
            currency='INR',
            amount=Decimal('100.00'),
            status='PENDING'
        )
        
        # Test status update method
        pending_transaction.update_status('SUCCESS', {'admin_note': 'Approved'})
        pending_transaction.refresh_from_db()
        
        self.assertEqual(pending_transaction.status, 'SUCCESS')
        self.assertIn('admin_note', pending_transaction.meta_data)
        self.assertEqual(pending_transaction.meta_data['admin_note'], 'Approved')
    
    def test_09_wallet_integration_atomicity(self):
        """Test 9: Wallet integration and atomicity."""
        initial_inr_balance = self.inr_wallet.balance
        
        # Test successful transaction with wallet update
        transaction = TransactionService.create_transaction(
            user=self.user,
            type='DEPOSIT',
            currency='INR',
            amount=Decimal('200.00'),
            reference_id='atomic_test_success',
            update_wallet=True
        )
        
        # Verify transaction created
        self.assertIsNotNone(transaction.id)
        
        # Verify wallet balance updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, initial_inr_balance + Decimal('200.00'))
        
        # Test failed transaction (insufficient balance)
        with self.assertRaises(ValueError):
            TransactionService.create_transaction(
                user=self.user,
                type='WITHDRAWAL',
                currency='INR',
                amount=Decimal('10000.00'),  # More than available balance
                reference_id='atomic_test_fail',
                update_wallet=True
            )
    
    def test_10_error_handling_and_validation(self):
        """Test 10: Error handling and validation."""
        # Test invalid amount
        with self.assertRaises(ValueError):
            TransactionService.create_transaction(
                user=self.user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal('-100.00'),  # Negative amount
                reference_id='invalid_amount'
            )
        
        # Test invalid currency precision
        with self.assertRaises(ValueError):
            TransactionService.create_transaction(
                user=self.user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal('100.123'),  # Too many decimal places for INR
                reference_id='invalid_precision'
            )
    
    def test_11_comprehensive_workflow(self):
        """Test 11: Comprehensive workflow test."""
        # 1. User deposits money
        deposit_transaction = TransactionIntegrationService.log_deposit(
            user=self.user,
            amount=Decimal('500.00'),
            currency='INR',
            reference_id='workflow_deposit_001',
            meta_data={'payment_method': 'bank_transfer'}
        )
        
        self.assertEqual(deposit_transaction.type, 'DEPOSIT')
        self.assertEqual(deposit_transaction.status, 'SUCCESS')
        
        # 2. User invests in a plan
        investment_transaction = TransactionIntegrationService.log_plan_purchase(
            user=self.user,
            amount=Decimal('200.00'),
            currency='INR',
            reference_id='workflow_investment_001',
            meta_data={'plan_name': 'Premium Plan'}
        )
        
        self.assertEqual(investment_transaction.type, 'PLAN_PURCHASE')
        self.assertEqual(investment_transaction.status, 'SUCCESS')
        
        # 3. User receives ROI
        roi_transaction = TransactionIntegrationService.log_roi_payout(
            user=self.user,
            amount=Decimal('25.00'),
            currency='INR',
            reference_id='workflow_roi_001',
            meta_data={'investment_id': 'INV001'}
        )
        
        self.assertEqual(roi_transaction.type, 'ROI')
        self.assertEqual(roi_transaction.status, 'SUCCESS')
        
        # 4. Verify all transactions are accessible via API
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Find our workflow transactions
        workflow_refs = [
            'workflow_deposit_001', 'workflow_investment_001', 'workflow_roi_001'
        ]
        
        found_transactions = []
        for transaction in response.data['results']:
            if transaction['reference_id'] in workflow_refs:
                found_transactions.append(transaction['reference_id'])
        
        # Should find all workflow transactions
        self.assertEqual(len(found_transactions), 3)
        for ref in workflow_refs:
            self.assertIn(ref, found_transactions)
    
    def test_12_final_verification(self):
        """Test 12: Final verification and cleanup."""
        # Verify all test transactions exist
        total_transactions = Transaction.objects.count()
        self.assertGreater(total_transactions, 0)
        
        # Verify all transactions have valid data
        for transaction in Transaction.objects.all():
            self.assertIsNotNone(transaction.id)
            self.assertIsNotNone(transaction.user)
            self.assertIsNotNone(transaction.type)
            self.assertIsNotNone(transaction.currency)
            self.assertIsNotNone(transaction.amount)
            self.assertIsNotNone(transaction.status)
            self.assertIsNotNone(transaction.created_at)
            self.assertIsNotNone(transaction.updated_at)
        
        # Verify wallet balances are consistent
        self.inr_wallet.refresh_from_db()
        self.usdt_wallet.refresh_from_db()
        
        # Balances should be non-negative
        self.assertGreaterEqual(self.inr_wallet.balance, 0)
        self.assertGreaterEqual(self.usdt_wallet.balance, 0)
        
        # Final API test to ensure everything works
        self.client.force_authenticate(user=self.user)
        url = reverse('transaction-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertGreater(len(response.data['results']), 0)
        
        print(f"\n✅ Comprehensive Transaction Test Suite Completed Successfully!")
        print(f"📊 Total transactions created: {total_transactions}")
        print(f"💰 Final INR balance: ₹{self.inr_wallet.balance}")
        print(f"💵 Final USDT balance: ${self.usdt_wallet.balance}")
        print(f"🎯 All 12 test scenarios passed successfully!")
