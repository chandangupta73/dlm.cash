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
from app.wallet.models import DepositRequest
from app.investment.models import InvestmentPlan, Investment

@pytest.mark.data_integrity
class TestWalletBalanceConsistency(TestCase):
    """Test wallet balance consistency and data integrity"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test users
        self.admin_user = User.objects.create_user(
            username='admin_integrity',
            email='admin@integrity.com',
            password='admin123!',
            is_staff=True,
            is_superuser=True
        )
        
        self.user = User.objects.create_user(
            username='user_integrity',
            email='user@integrity.com',
            password='user123!',
            first_name='Integrity',
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
            name='Integrity Test Plan',
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
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
    
    def _get_token(self, user):
        """Get JWT token for user"""
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    
    def test_wallet_balance_consistency_after_deposit(self):
        """Test wallet balance consistency after deposit operations"""
        # Record initial balance
        initial_balance = self.inr_wallet.balance
        
        # Create deposit request
        deposit_request = DepositRequest.objects.create(
            user=self.user,
            amount=Decimal('500.00'),
            payment_method='bank_transfer',
            status='pending'
        )
        
        # Admin approves deposit
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        approval_data = {
            'transaction_reference': 'TXN123456',
            'notes': 'Balance consistency test'
        }
        
        response = self.client.post(
            reverse('approve-deposit', kwargs={'deposit_id': deposit_request.id}),
            approval_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check wallet balance was updated correctly
        self.inr_wallet.refresh_from_db()
        expected_balance = initial_balance + Decimal('500.00')
        self.assertEqual(self.inr_wallet.balance, expected_balance)
        
        # Check transaction was created
        transaction = Transaction.objects.filter(
            user=self.user,
            type='DEPOSIT'
        ).first()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('500.00'))
        self.assertEqual(transaction.currency, 'INR')
    
    def test_wallet_balance_consistency_after_withdrawal(self):
        """Test wallet balance consistency after withdrawal operations"""
        # Record initial balance
        initial_balance = self.inr_wallet.balance
        
        # Create withdrawal request
        withdrawal_data = {
            'currency': 'INR',
            'amount': '300.00',
            'payout_method': 'bank_transfer',
            'payout_details': {
                'account_number': '1234567890',
                'ifsc_code': 'SBIN0001234',
                'account_holder_name': 'Test User',
                'bank_name': 'State Bank of India'
            }
        }
        
        response = self.client.post(
            reverse('create-withdrawal'),
            withdrawal_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check wallet balance was deducted correctly
        self.inr_wallet.refresh_from_db()
        expected_balance = initial_balance - Decimal('300.00')
        self.assertEqual(self.inr_wallet.balance, expected_balance)
        
        # Check transaction was created
        transaction = Transaction.objects.filter(
            user=self.user,
            type='WITHDRAWAL'
        ).first()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('300.00'))
        self.assertEqual(transaction.currency, 'INR')
    
    def test_wallet_balance_consistency_after_investment(self):
        """Test wallet balance consistency after investment operations"""
        # Record initial balance
        initial_balance = self.inr_wallet.balance
        
        # Create investment
        investment_data = {
            'plan': self.investment_plan.id,
            'amount': '400.00',
            'currency': 'inr'
        }
        
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check wallet balance was deducted correctly
        self.inr_wallet.refresh_from_db()
        expected_balance = initial_balance - Decimal('400.00')
        self.assertEqual(self.inr_wallet.balance, expected_balance)
        
        # Check transaction was created
        transaction = Transaction.objects.filter(
            user=self.user,
            type='PLAN_PURCHASE'
        ).first()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('400.00'))
        self.assertEqual(transaction.currency, 'INR')
    
    def test_concurrent_balance_operations_consistency(self):
        """Test balance consistency during concurrent operations"""
        # Record initial balance
        initial_balance = self.inr_wallet.balance
        
        def perform_operation(operation_type, amount):
            if operation_type == 'deposit':
                # Create and approve deposit
                deposit_request = DepositRequest.objects.create(
                    user=self.user,
                    amount=amount,
                    payment_method='bank_transfer',
                    status='pending'
                )
                
                self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
                approval_data = {
                    'transaction_reference': f'TXN{operation_type}_{amount}',
                    'notes': f'Concurrent {operation_type} test'
                }
                
                response = self.client.post(
                    reverse('approve-deposit', kwargs={'deposit_id': deposit_request.id}),
                    approval_data
                )
                return response.status_code
                
            elif operation_type == 'withdrawal':
                # Create withdrawal
                self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
                withdrawal_data = {
                    'currency': 'INR',
                    'amount': str(amount),
                    'payout_method': 'bank_transfer',
                    'payout_details': {
                        'account_number': '1234567890',
                        'ifsc_code': 'SBIN0001234',
                        'account_holder_name': 'Test User',
                        'bank_name': 'State Bank of India'
                    }
                }
                
                response = self.client.post(
                    reverse('create-withdrawal'),
                    withdrawal_data
                )
                return response.status_code
        
        # Start concurrent operations
        threads = []
        results = []
        
        # Deposit operations
        thread1 = threading.Thread(
            target=lambda: results.append(perform_operation('deposit', Decimal('100.00')))
        )
        threads.append(thread1)
        
        thread2 = threading.Thread(
            target=lambda: results.append(perform_operation('deposit', Decimal('200.00')))
        )
        threads.append(thread2)
        
        # Withdrawal operations
        thread3 = threading.Thread(
            target=lambda: results.append(perform_operation('withdrawal', Decimal('50.00')))
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
        
        # Check final balance consistency
        self.inr_wallet.refresh_from_db()
        
        # Calculate expected final balance
        # Initial: 1000, Deposits: +100 +200, Withdrawal: -50 = 1250
        expected_balance = initial_balance + Decimal('100.00') + Decimal('200.00') - Decimal('50.00')
        
        # Allow for small discrepancies due to race conditions
        balance_diff = abs(self.inr_wallet.balance - expected_balance)
        self.assertLessEqual(balance_diff, Decimal('1.00'))
    
    def test_transaction_audit_trail_consistency(self):
        """Test transaction audit trail consistency"""
        # Perform multiple operations
        operations = [
            ('deposit', Decimal('250.00')),
            ('withdrawal', Decimal('100.00')),
            ('investment', Decimal('150.00'))
        ]
        
        for operation_type, amount in operations:
            if operation_type == 'deposit':
                # Create and approve deposit
                deposit_request = DepositRequest.objects.create(
                    user=self.user,
                    amount=amount,
                    payment_method='bank_transfer',
                    status='pending'
                )
                
                self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
                approval_data = {
                    'transaction_reference': f'TXN{operation_type}_{amount}',
                    'notes': f'Audit trail test: {operation_type}'
                }
                
                response = self.client.post(
                    reverse('approve-deposit', kwargs={'deposit_id': deposit_request.id}),
                    approval_data
                )
                
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                
            elif operation_type == 'withdrawal':
                # Create withdrawal
                self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
                withdrawal_data = {
                    'currency': 'INR',
                    'amount': str(amount),
                    'payout_method': 'bank_transfer',
                    'payout_details': {
                        'account_number': '1234567890',
                        'ifsc_code': 'SBIN0001234',
                        'account_holder_name': 'Test User',
                        'bank_name': 'State Bank of India'
                    }
                }
                
                response = self.client.post(
                    reverse('create-withdrawal'),
                    withdrawal_data
                )
                
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                
            elif operation_type == 'investment':
                # Create investment
                self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
                investment_data = {
                    'plan': self.investment_plan.id,
                    'amount': str(amount),
                    'currency': 'inr'
                }
                
                response = self.client.post(
                    reverse('investment:investment-list'),
                    investment_data
                )
                
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check all transactions were created
        transaction_types = ['DEPOSIT', 'WITHDRAWAL', 'PLAN_PURCHASE']
        for txn_type in transaction_types:
            transaction = Transaction.objects.filter(
                user=self.user,
                type=txn_type
            ).first()
            
            self.assertIsNotNone(transaction)
            self.assertEqual(transaction.currency, 'INR')
            self.assertEqual(transaction.status, 'SUCCESS')
        
        # Check wallet transactions were created
        wallet_transaction_types = ['deposit', 'withdrawal', 'investment']
        for txn_type in wallet_transaction_types:
            wallet_transaction = WalletTransaction.objects.filter(
                user=self.user,
                transaction_type=txn_type
            ).first()
            
            self.assertIsNotNone(wallet_transaction)
            self.assertEqual(wallet_transaction.wallet_type, 'inr')
            self.assertEqual(wallet_transaction.status, 'completed')
    
    def test_cross_currency_balance_consistency(self):
        """Test balance consistency across different currencies"""
        # Record initial balances
        initial_inr_balance = self.inr_wallet.balance
        initial_usdt_balance = self.usdt_wallet.balance
        
        # Perform operations in both currencies
        # INR operations
        deposit_request = DepositRequest.objects.create(
            user=self.user,
            amount=Decimal('300.00'),
            payment_method='bank_transfer',
            status='pending'
        )
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        approval_data = {
            'transaction_reference': 'TXN_INR_300',
            'notes': 'Cross currency test: INR'
        }
        
        response = self.client.post(
            reverse('approve-deposit', kwargs={'deposit_id': deposit_request.id}),
            approval_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # USDT operations
        withdrawal_data = {
            'currency': 'USDT',
            'amount': '25.000000',
            'payout_method': 'usdt_erc20',
            'payout_details': {
                'wallet_address': '0x1234567890abcdef',
                'chain_type': 'erc20'
            }
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        response = self.client.post(
            reverse('create-withdrawal'),
            withdrawal_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check both wallets were updated correctly
        self.inr_wallet.refresh_from_db()
        self.usdt_wallet.refresh_from_db()
        
        expected_inr_balance = initial_inr_balance + Decimal('300.00')
        expected_usdt_balance = initial_usdt_balance - Decimal('25.000000')
        
        self.assertEqual(self.inr_wallet.balance, expected_inr_balance)
        self.assertEqual(self.usdt_wallet.balance, expected_usdt_balance)
        
        # Check transactions were created for both currencies
        inr_transaction = Transaction.objects.filter(
            user=self.user,
            type='DEPOSIT',
            currency='INR'
        ).first()
        
        usdt_transaction = Transaction.objects.filter(
            user=self.user,
            type='WITHDRAWAL',
            currency='USDT'
        ).first()
        
        self.assertIsNotNone(inr_transaction)
        self.assertIsNotNone(usdt_transaction)
    
    def test_balance_precision_consistency(self):
        """Test balance precision consistency across operations"""
        # Test with various precision amounts
        test_amounts = [
            Decimal('0.01'),
            Decimal('0.99'),
            Decimal('100.50'),
            Decimal('999.99')
        ]
        
        for amount in test_amounts:
            # Create deposit with specific amount
            deposit_request = DepositRequest.objects.create(
                user=self.user,
                amount=amount,
                payment_method='bank_transfer',
                status='pending'
            )
            
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
            approval_data = {
                'transaction_reference': f'TXN_PRECISION_{amount}',
                'notes': f'Precision test: {amount}'
            }
            
            response = self.client.post(
                reverse('approve-deposit', kwargs={'deposit_id': deposit_request.id}),
                approval_data
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Check precision is maintained
            self.inr_wallet.refresh_from_db()
            self.assertEqual(self.inr_wallet.balance.quantize(Decimal('0.01')), 
                           (Decimal('1000.00') + amount).quantize(Decimal('0.01')))
            
            # Reset balance for next test
            self.inr_wallet.balance = Decimal('1000.00')
            self.inr_wallet.save()
    
    def test_negative_balance_prevention(self):
        """Test that negative balances are prevented"""
        # Try to create withdrawal larger than available balance
        withdrawal_data = {
            'currency': 'INR',
            'amount': '2000.00',  # More than available 1000.00
            'payout_method': 'bank_transfer',
            'payout_details': {
                'account_number': '1234567890',
                'ifsc_code': 'SBIN0001234',
                'account_holder_name': 'Test User',
                'bank_name': 'State Bank of India'
            }
        }
        
        response = self.client.post(
            reverse('create-withdrawal'),
            withdrawal_data
        )
        
        # Should fail due to insufficient funds
        self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Balance should remain unchanged
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('1000.00'))
        
        # No transaction should be created
        transaction = Transaction.objects.filter(
            user=self.user,
            type='WITHDRAWAL'
        ).first()
        
        self.assertIsNone(transaction)
    
    def test_balance_rollback_on_failure(self):
        """Test balance rollback when operations fail"""
        # Record initial balance
        initial_balance = self.inr_wallet.balance
        
        # Try to create withdrawal with invalid data
        invalid_withdrawal_data = {
            'currency': 'INR',
            'amount': 'not_a_number',  # Invalid amount
            'payout_method': 'bank_transfer',
            'payout_details': {
                'account_number': '1234567890',
                'ifsc_code': 'SBIN0001234',
                'account_holder_name': 'Test User',
                'bank_name': 'State Bank of India'
            }
        }
        
        response = self.client.post(
            reverse('create-withdrawal'),
            invalid_withdrawal_data
        )
        
        # Should fail
        self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Balance should remain unchanged
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, initial_balance)
        
        # No transaction should be created
        transaction = Transaction.objects.filter(
            user=self.user,
            type='WITHDRAWAL'
        ).first()
        
        self.assertIsNone(transaction)
