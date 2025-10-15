import pytest
import threading
import time
from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from app.users.models import User
from app.wallet.models import INRWallet, USDTWallet, WalletTransaction
from app.transactions.models import Transaction
from app.withdrawals.models import Withdrawal
from app.deposits.models import DepositRequest
from app.investment.models import InvestmentPlan, Investment

@pytest.mark.edge_case
class TestAdminEdgeCases(TestCase):
    """Test admin panel edge cases and transaction consistency"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test users
        self.admin_user = User.objects.create_user(
            username='admin_edge',
            email='admin@edge.com',
            password='admin123!',
            is_staff=True,
            is_superuser=True
        )
        
        self.user = User.objects.create_user(
            username='user_edge',
            email='user@edge.com',
            password='user123!',
            first_name='Edge',
            last_name='User',
            kyc_status='APPROVED',
            is_kyc_verified=True
        )
        
        # Create wallets
        self.inr_wallet, created = INRWallet.objects.get_or_create(
            user=self.user,
            defaults={
                'balance': Decimal('1000.00'),
                'status': 'active'
            }
        )
        
        self.usdt_wallet, created = USDTWallet.objects.get_or_create(
            user=self.user,
            defaults={
                'balance': Decimal('100.000000'),
                'status': 'active'
            }
        )
        
        # Create investment plan
        self.investment_plan = InvestmentPlan.objects.create(
            name='Admin Test Plan',
            roi_rate=Decimal('12.00'),
            frequency='daily',
            duration_days=30,
            breakdown_window_days=15,
            min_amount=Decimal('100.00'),
            max_amount=Decimal('1000.00'),
            status='active'
        )
        
        # Get tokens
        self.admin_token = self._get_token(self.admin_user)
        self.user_token = self._get_token(self.user)
        
        # Set authentication
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
    
    def _get_token(self, user):
        """Get JWT token for user"""
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    
    def test_admin_edit_balance_during_pending_withdrawal(self):
        """Test admin editing balance while withdrawal is pending"""
        # Create withdrawal request
        withdrawal_data = {
            'currency': 'INR',
            'amount': '500.00',
            'payout_method': 'bank_transfer',
            'payout_details': {
                'account_number': '1234567890',
                'ifsc_code': 'SBIN0001234',
                'account_holder_name': 'Test User',
                'bank_name': 'State Bank of India'
            }
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        response = self.client.post(
            reverse('create-withdrawal'),
            withdrawal_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        withdrawal = Withdrawal.objects.get(user=self.user)
        
        # Admin attempts to edit balance while withdrawal is pending
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        # Try to credit wallet
        credit_data = {
            'user_id': str(self.user.id),
            'action': 'credit',
            'amount': '200.00',
            'wallet_type': 'INR',
            'reason': 'Bonus credit during pending withdrawal'
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            credit_data
        )
        
        # Should succeed - admin can edit balance even with pending withdrawal
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check wallet balance was updated
        self.inr_wallet.refresh_from_db()
        expected_balance = Decimal('1000.00') + Decimal('200.00')  # Original + credit
        self.assertEqual(self.inr_wallet.balance, expected_balance)
        
        # Check transaction was created
        transaction = Transaction.objects.filter(
            user=self.user,
            type='ADMIN_ADJUSTMENT'
        ).first()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('200.00'))
    
    def test_admin_edit_balance_during_pending_deposit(self):
        """Test admin editing balance while deposit is pending"""
        # Create deposit request
        deposit_request = DepositRequest.objects.create(
            user=self.user,
            amount=Decimal('300.00'),
            payment_method='bank_transfer',
            status='pending'
        )
        
        # Admin attempts to edit balance while deposit is pending
        debit_data = {
            'user_id': str(self.user.id),
            'action': 'debit',
            'amount': '100.00',
            'wallet_type': 'INR',
            'reason': 'Adjustment during pending deposit'
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            debit_data
        )
        
        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check wallet balance was updated
        self.inr_wallet.refresh_from_db()
        expected_balance = Decimal('1000.00') - Decimal('100.00')  # Original - debit
        self.assertEqual(self.inr_wallet.balance, expected_balance)
    
    def test_admin_edit_balance_during_active_investment(self):
        """Test admin editing balance while investment is active"""
        # Create investment
        investment_data = {
            'plan': self.investment_plan.id,
            'amount': '500.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Admin attempts to edit balance while investment is active
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        credit_data = {
            'user_id': str(self.user.id),
            'action': 'credit',
            'amount': '150.00',
            'wallet_type': 'INR',
            'reason': 'Bonus during active investment'
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            credit_data
        )
        
        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check wallet balance was updated
        self.inr_wallet.refresh_from_db()
        expected_balance = Decimal('500.00') + Decimal('150.00')  # Remaining after investment + credit
        self.assertEqual(self.inr_wallet.balance, expected_balance)
    
    def test_admin_edit_balance_concurrent_operations(self):
        """Test admin editing balance with concurrent operations"""
        # Create multiple admin operations concurrently
        def admin_operation(amount, action):
            data = {
                'user_id': str(self.user.id),
                'action': action,
                'amount': str(amount),
                'wallet_type': 'INR',
                'reason': f'Concurrent {action} operation'
            }
            
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
            response = client.post(
                reverse('admin_panel:admin-wallet-adjust-balance'),
                data
            )
            return response.status_code
        
        # Start concurrent operations
        threads = []
        results = []
        
        # Credit operations
        thread1 = threading.Thread(
            target=lambda: results.append(admin_operation('100.00', 'credit'))
        )
        threads.append(thread1)
        
        thread2 = threading.Thread(
            target=lambda: results.append(admin_operation('200.00', 'credit'))
        )
        threads.append(thread2)
        
        # Debit operations
        thread3 = threading.Thread(
            target=lambda: results.append(admin_operation('50.00', 'debit'))
        )
        threads.append(thread3)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All should succeed
        for result in results:
            self.assertEqual(result, status.HTTP_200_OK)
        
        # Check final balance
        self.inr_wallet.refresh_from_db()
        expected_balance = Decimal('1000.00') + Decimal('100.00') + Decimal('200.00') - Decimal('50.00')
        self.assertEqual(self.inr_wallet.balance, expected_balance)
    
    def test_admin_edit_balance_precision_handling(self):
        """Test admin editing balance with precision handling"""
        # Test various precision amounts
        test_amounts = [
            '0.01',
            '0.99',
            '100.50',
            '999.99'
        ]
        
        for amount_str in test_amounts:
            amount = Decimal(amount_str)
            
            # Credit amount
            credit_data = {
                'user_id': str(self.user.id),
                'action': 'credit',
                'amount': amount_str,
                'wallet_type': 'INR',
                'reason': f'Precision test: {amount_str}'
            }
            
            response = self.client.post(
                reverse('admin_panel:admin-wallet-adjust-balance'),
                credit_data
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Check precision is maintained
            self.inr_wallet.refresh_from_db()
            self.assertEqual(self.inr_wallet.balance.quantize(Decimal('0.01')), 
                           (Decimal('1000.00') + amount).quantize(Decimal('0.01')))
            
            # Reset balance for next test
            self.inr_wallet.balance = Decimal('1000.00')
            self.inr_wallet.save()
    
    def test_admin_edit_balance_invalid_actions(self):
        """Test admin editing balance with invalid actions"""
        # Test invalid action
        invalid_data = {
            'user_id': str(self.user.id),
            'action': 'invalid_action',
            'amount': '100.00',
            'wallet_type': 'INR',
            'reason': 'Invalid action test'
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            invalid_data
        )
        
        # Should fail
        self.assertNotEqual(response.status_code, status.HTTP_200_OK)
        
        # Test negative amount
        negative_data = {
            'user_id': str(self.user.id),
            'action': 'credit',
            'amount': '-100.00',
            'wallet_type': 'INR',
            'reason': 'Negative amount test'
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            negative_data
        )
        
        # Should fail
        self.assertNotEqual(response.status_code, status.HTTP_200_OK)
    
    def test_admin_edit_balance_insufficient_funds(self):
        """Test admin editing balance with insufficient funds"""
        # Try to debit more than available balance
        debit_data = {
            'user_id': str(self.user.id),
            'action': 'debit',
            'amount': '2000.00',  # More than available 1000.00
            'wallet_type': 'INR',
            'reason': 'Insufficient funds test'
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            debit_data
        )
        
        # Should fail
        self.assertNotEqual(response.status_code, status.HTTP_200_OK)
        
        # Balance should remain unchanged
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('1000.00'))
    
    def test_admin_edit_balance_audit_trail(self):
        """Test admin editing balance creates proper audit trail"""
        # Perform balance edit
        edit_data = {
            'user_id': str(self.user.id),
            'action': 'credit',
            'amount': '250.00',
            'wallet_type': 'INR',
            'reason': 'Audit trail test'
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            edit_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check transaction was created
        transaction = Transaction.objects.filter(
            user=self.user,
            type='ADMIN_ADJUSTMENT'
        ).first()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('250.00'))
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.status, 'SUCCESS')
        
        # Check wallet transaction was created
        wallet_transaction = WalletTransaction.objects.filter(
            user=self.user,
            transaction_type='admin_adjustment'
        ).first()
        
        self.assertIsNotNone(wallet_transaction)
        self.assertEqual(wallet_transaction.amount, Decimal('250.00'))
        self.assertEqual(wallet_transaction.wallet_type, 'inr')
    
    def test_admin_edit_balance_cross_currency(self):
        """Test admin editing balance across different currencies"""
        # Edit INR wallet
        inr_data = {
            'user_id': str(self.user.id),
            'action': 'credit',
            'amount': '500.00',
            'wallet_type': 'INR',
            'reason': 'INR credit test'
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            inr_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Edit USDT wallet
        usdt_data = {
            'user_id': str(self.user.id),
            'action': 'credit',
            'amount': '50.000000',
            'wallet_type': 'USDT',
            'reason': 'USDT credit test'
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            usdt_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check both wallets were updated
        self.inr_wallet.refresh_from_db()
        self.usdt_wallet.refresh_from_db()
        
        self.assertEqual(self.inr_wallet.balance, Decimal('1500.00'))
        self.assertEqual(self.usdt_wallet.balance, Decimal('150.000000'))
    
    def test_admin_edit_balance_user_permissions(self):
        """Test that regular users cannot edit balances"""
        # Regular user tries to edit balance
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        
        edit_data = {
            'user_id': str(self.user.id),
            'action': 'credit',
            'amount': '100.00',
            'wallet_type': 'INR',
            'reason': 'Unauthorized edit attempt'
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            edit_data
        )
        
        # Should fail - user not admin
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Balance should remain unchanged
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('1000.00'))
    
    def test_admin_edit_balance_nonexistent_user(self):
        """Test admin editing balance for nonexistent user"""
        # Try to edit balance for non-existent user
        edit_data = {
            'user_id': '00000000-0000-0000-0000-000000000000',
            'action': 'credit',
            'amount': '100.00',
            'wallet_type': 'INR',
            'reason': 'Nonexistent user test'
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            edit_data
        )
        
        # Should fail
        self.assertNotEqual(response.status_code, status.HTTP_200_OK)
    
    def test_admin_edit_balance_malformed_data(self):
        """Test admin editing balance with malformed data"""
        # Test missing required fields
        malformed_data = {
            'user_id': str(self.user.id),
            'action': 'credit',
            # Missing amount
            'wallet_type': 'INR',
            'reason': 'Malformed data test'
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            malformed_data
        )
        
        # Should fail
        self.assertNotEqual(response.status_code, status.HTTP_200_OK)
        
        # Test invalid amount format
        invalid_amount_data = {
            'user_id': str(self.user.id),
            'action': 'credit',
            'amount': 'not_a_number',
            'wallet_type': 'INR',
            'reason': 'Invalid amount test'
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            invalid_amount_data
        )
        
        # Should fail
        self.assertNotEqual(response.status_code, status.HTTP_200_OK)
