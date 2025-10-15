import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from unittest.mock import patch
from datetime import datetime, timedelta

from app.wallet.models import INRWallet, USDTWallet, WalletTransaction, DepositRequest
from app.withdrawals.models import Withdrawal
from app.admin_panel.models import AdminActionLog
from app.admin_panel.services import AdminWithdrawalService
from app.admin_panel.permissions import log_admin_action

User = get_user_model()


class AdminDepositWithdrawalServiceTest(TestCase):
    """Test deposit and withdrawal management service layer"""
    
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        self.staff_user = User.objects.create_user(
            username='staff',
            email='staff@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=False
        )
        
        self.regular_user = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123'
        )
        
        self.inr_wallet = INRWallet.objects.create(
            user=self.regular_user,
            balance=Decimal('1000.00')
        )
        
        self.usdt_wallet = USDTWallet.objects.create(
            user=self.regular_user,
            balance=Decimal('100.00')
        )
        
        self.deposit_request = DepositRequest.objects.create(
            user=self.regular_user,
            amount=Decimal('500.00'),
            currency='INR',
            payment_method='BANK_TRANSFER',
            transaction_id='DEP123456',
            status='PENDING'
        )
        
        self.withdrawal_request = Withdrawal.objects.create(
            user=self.regular_user,
            amount=Decimal('200.00'),
            currency='INR',
            payout_method='BANK_TRANSFER',
            bank_account='1234567890',
            ifsc_code='ABCD0001234',
            account_holder='Test User',
            status='PENDING'
        )
        
        self.withdrawal_service = AdminWithdrawalService()
    
    def test_get_pending_deposits(self):
        """Test retrieving pending deposits"""
        deposits = self.withdrawal_service.get_pending_deposits()
        
        self.assertEqual(len(deposits), 1)
        self.assertEqual(deposits[0].id, self.deposit_request.id)
        self.assertEqual(deposits[0].status, 'PENDING')
    
    def test_get_pending_withdrawals(self):
        """Test retrieving pending withdrawals"""
        withdrawals = self.withdrawal_service.get_pending_withdrawals()
        
        self.assertEqual(len(withdrawals), 1)
        self.assertEqual(withdrawals[0].id, self.withdrawal_request.id)
        self.assertEqual(withdrawals[0].status, 'PENDING')
    
    def test_approve_deposit(self):
        """Test approving a deposit request"""
        result = self.withdrawal_service.approve_deposit(
            deposit_id=self.deposit_request.id,
            admin_user=self.admin_user,
            notes='Deposit verified and approved'
        )
        
        self.assertTrue(result['success'])
        
        # Check deposit status updated
        self.deposit_request.refresh_from_db()
        self.assertEqual(self.deposit_request.status, 'APPROVED')
        self.assertEqual(self.deposit_request.processed_by, self.admin_user)
        self.assertEqual(self.deposit_request.admin_notes, 'Deposit verified and approved')
        
        # Check wallet balance updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('1500.00'))  # 1000 + 500
        
        # Check transaction log created
        transaction = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='deposit',
            amount=Decimal('500.00')
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.description, 'Deposit approved by admin')
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='DEPOSIT_APPROVAL',
            target_user=self.regular_user
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('Deposit verified and approved', action_log.action_description)
    
    def test_reject_deposit(self):
        """Test rejecting a deposit request"""
        result = self.withdrawal_service.reject_deposit(
            deposit_id=self.deposit_request.id,
            admin_user=self.admin_user,
            rejection_reason='Invalid transaction ID'
        )
        
        self.assertTrue(result['success'])
        
        # Check deposit status updated
        self.deposit_request.refresh_from_db()
        self.assertEqual(self.deposit_request.status, 'REJECTED')
        self.assertEqual(self.deposit_request.processed_by, self.admin_user)
        self.assertEqual(self.deposit_request.rejection_reason, 'Invalid transaction ID')
        
        # Check wallet balance unchanged
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('1000.00'))
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='DEPOSIT_REJECTION',
            target_user=self.regular_user
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('Invalid transaction ID', action_log.action_description)
    
    def test_approve_withdrawal(self):
        """Test approving a withdrawal request"""
        result = self.withdrawal_service.approve_withdrawal(
            withdrawal_id=self.withdrawal_request.id,
            admin_user=self.admin_user,
            notes='Withdrawal approved',
            tx_hash='0x1234567890abcdef'
        )
        
        self.assertTrue(result['success'])
        
        # Check withdrawal status updated
        self.withdrawal_request.refresh_from_db()
        self.assertEqual(self.withdrawal_request.status, 'APPROVED')
        self.assertEqual(self.withdrawal_request.processed_by, self.admin_user)
        self.assertEqual(self.withdrawal_request.admin_notes, 'Withdrawal approved')
        self.assertEqual(self.withdrawal_request.tx_hash, '0x1234567890abcdef')
        
        # Check wallet balance deducted
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('800.00'))  # 1000 - 200
        
        # Check transaction log created
        transaction = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='withdrawal',
            amount=Decimal('200.00')
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.description, 'Withdrawal approved by admin')
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='WITHDRAWAL_APPROVAL',
            target_user=self.regular_user
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('Withdrawal approved', action_log.action_description)
    
    def test_reject_withdrawal_with_refund(self):
        """Test rejecting a withdrawal request with refund"""
        # First approve the withdrawal to deduct balance
        self.withdrawal_request.status = 'APPROVED'
        self.withdrawal_request.save()
        self.inr_wallet.balance = Decimal('800.00')  # 1000 - 200
        self.inr_wallet.save()
        
        # Now reject it
        result = self.withdrawal_service.reject_withdrawal(
            withdrawal_id=self.withdrawal_request.id,
            admin_user=self.admin_user,
            rejection_reason='Bank account details incorrect'
        )
        
        self.assertTrue(result['success'])
        
        # Check withdrawal status updated
        self.withdrawal_request.refresh_from_db()
        self.assertEqual(self.withdrawal_request.status, 'REJECTED')
        self.assertEqual(self.withdrawal_request.processed_by, self.admin_user)
        self.assertEqual(self.withdrawal_request.rejection_reason, 'Bank account details incorrect')
        
        # Check wallet balance refunded
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('1000.00'))  # 800 + 200
        
        # Check refund transaction log created
        transaction = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='withdrawal_refund',
            amount=Decimal('200.00')
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.description, 'Withdrawal rejected - refund by admin')
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='WITHDRAWAL_REJECTION',
            target_user=self.regular_user
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('Bank account details incorrect', action_log.action_description)
    
    def test_approve_nonexistent_deposit(self):
        """Test approving non-existent deposit"""
        result = self.withdrawal_service.approve_deposit(
            deposit_id=99999,
            admin_user=self.admin_user,
            notes='Test'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
    
    def test_approve_nonexistent_withdrawal(self):
        """Test approving non-existent withdrawal"""
        result = self.withdrawal_service.approve_withdrawal(
            withdrawal_id=99999,
            admin_user=self.admin_user,
            notes='Test'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
    
    def test_approve_already_approved_deposit(self):
        """Test approving already approved deposit"""
        self.deposit_request.status = 'APPROVED'
        self.deposit_request.save()
        
        result = self.withdrawal_service.approve_deposit(
            deposit_id=self.deposit_request.id,
            admin_user=self.admin_user,
            notes='Test'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('already approved', result['error'])
    
    def test_approve_already_approved_withdrawal(self):
        """Test approving already approved withdrawal"""
        self.withdrawal_request.status = 'APPROVED'
        self.withdrawal_request.save()
        
        result = self.withdrawal_service.approve_withdrawal(
            withdrawal_id=self.withdrawal_request.id,
            admin_user=self.admin_user,
            notes='Test'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('already approved', result['error'])
    
    def test_reject_already_rejected_deposit(self):
        """Test rejecting already rejected deposit"""
        self.deposit_request.status = 'REJECTED'
        self.deposit_request.save()
        
        result = self.withdrawal_service.reject_deposit(
            deposit_id=self.deposit_request.id,
            admin_user=self.admin_user,
            rejection_reason='Test'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('already rejected', result['error'])
    
    def test_reject_already_rejected_withdrawal(self):
        """Test rejecting already rejected withdrawal"""
        self.withdrawal_request.status = 'REJECTED'
        self.withdrawal_request.save()
        
        result = self.withdrawal_service.reject_withdrawal(
            withdrawal_id=self.withdrawal_request.id,
            admin_user=self.admin_user,
            rejection_reason='Test'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('already rejected', result['error'])
    
    def test_approve_deposit_insufficient_balance_for_fee(self):
        """Test approving deposit with insufficient balance for fee deduction"""
        # Set wallet balance to 0
        self.inr_wallet.balance = Decimal('0.00')
        self.inr_wallet.save()
        
        # Try to approve deposit (should still work as it's adding money)
        result = self.withdrawal_service.approve_deposit(
            deposit_id=self.deposit_request.id,
            admin_user=self.admin_user,
            notes='Test insufficient balance'
        )
        
        self.assertTrue(result['success'])
        
        # Check wallet balance updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('500.00'))
    
    def test_approve_withdrawal_insufficient_balance(self):
        """Test approving withdrawal with insufficient balance"""
        # Set wallet balance to 100 (less than withdrawal amount 200)
        self.inr_wallet.balance = Decimal('100.00')
        self.inr_wallet.save()
        
        result = self.withdrawal_service.approve_withdrawal(
            withdrawal_id=self.withdrawal_request.id,
            admin_user=self.admin_user,
            notes='Test insufficient balance'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('insufficient balance', result['error'])
        
        # Check wallet balance unchanged
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('100.00'))
    
    def test_deposit_approval_with_notification(self):
        """Test deposit approval triggers notification"""
        with patch('app.admin_panel.services.send_deposit_approval_notification') as mock_notify:
            result = self.withdrawal_service.approve_deposit(
                deposit_id=self.deposit_request.id,
                admin_user=self.admin_user,
                notes='Test notification'
            )
            
            self.assertTrue(result['success'])
            mock_notify.assert_called_once_with(self.regular_user, self.deposit_request)
    
    def test_withdrawal_approval_with_notification(self):
        """Test withdrawal approval triggers notification"""
        with patch('app.admin_panel.services.send_withdrawal_approval_notification') as mock_notify:
            result = self.withdrawal_service.approve_withdrawal(
                withdrawal_id=self.withdrawal_request.id,
                admin_user=self.admin_user,
                notes='Test notification'
            )
            
            self.assertTrue(result['success'])
            mock_notify.assert_called_once_with(self.regular_user, self.withdrawal_request)
    
    def test_deposit_rejection_with_notification(self):
        """Test deposit rejection triggers notification"""
        with patch('app.admin_panel.services.send_deposit_rejection_notification') as mock_notify:
            result = self.withdrawal_service.reject_deposit(
                deposit_id=self.deposit_request.id,
                admin_user=self.admin_user,
                rejection_reason='Test rejection'
            )
            
            self.assertTrue(result['success'])
            mock_notify.assert_called_once_with(self.regular_user, self.deposit_request, 'Test rejection')
    
    def test_withdrawal_rejection_with_notification(self):
        """Test withdrawal rejection triggers notification"""
        with patch('app.admin_panel.services.send_withdrawal_rejection_notification') as mock_notify:
            result = self.withdrawal_service.reject_withdrawal(
                withdrawal_id=self.withdrawal_request.id,
                admin_user=self.admin_user,
                rejection_reason='Test rejection'
            )
            
            self.assertTrue(result['success'])
            mock_notify.assert_called_once_with(self.regular_user, self.withdrawal_request, 'Test rejection')


class AdminDepositWithdrawalAPITest(TestCase):
    """Test deposit and withdrawal management API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        self.staff_user = User.objects.create_user(
            username='staff',
            email='staff@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=False
        )
        
        self.regular_user = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123'
        )
        
        self.inr_wallet = INRWallet.objects.create(
            user=self.regular_user,
            balance=Decimal('1000.00')
        )
        
        self.deposit_request = DepositRequest.objects.create(
            user=self.regular_user,
            amount=Decimal('500.00'),
            currency='INR',
            payment_method='BANK_TRANSFER',
            transaction_id='DEP123456',
            status='PENDING'
        )
        
        self.withdrawal_request = Withdrawal.objects.create(
            user=self.regular_user,
            amount=Decimal('200.00'),
            currency='INR',
            payout_method='BANK_TRANSFER',
            bank_account='1234567890',
            ifsc_code='ABCD0001234',
            account_holder='Test User',
            status='PENDING'
        )
        
        self.client.force_authenticate(user=self.admin_user)
    
    def test_list_pending_deposits(self):
        """Test listing pending deposits"""
        url = reverse('admin-withdrawal-list')
        response = self.client.get(url, {'type': 'deposits', 'status': 'PENDING'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.deposit_request.id)
    
    def test_list_pending_withdrawals(self):
        """Test listing pending withdrawals"""
        url = reverse('admin-withdrawal-list')
        response = self.client.get(url, {'type': 'withdrawals', 'status': 'PENDING'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.withdrawal_request.id)
    
    def test_retrieve_deposit(self):
        """Test retrieving a specific deposit"""
        url = reverse('admin-withdrawal-detail', kwargs={'pk': self.deposit_request.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.deposit_request.id)
        self.assertEqual(response.data['status'], 'PENDING')
    
    def test_retrieve_withdrawal(self):
        """Test retrieving a specific withdrawal"""
        url = reverse('admin-withdrawal-detail', kwargs={'pk': self.withdrawal_request.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.withdrawal_request.id)
        self.assertEqual(response.data['status'], 'PENDING')
    
    def test_approve_deposit_api(self):
        """Test approving deposit via API"""
        url = reverse('admin-withdrawal-approve', kwargs={'pk': self.deposit_request.id})
        data = {'notes': 'Deposit approved via API'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check deposit status updated
        self.deposit_request.refresh_from_db()
        self.assertEqual(self.deposit_request.status, 'APPROVED')
    
    def test_reject_deposit_api(self):
        """Test rejecting deposit via API"""
        url = reverse('admin-withdrawal-reject', kwargs={'pk': self.deposit_request.id})
        data = {'rejection_reason': 'Invalid transaction'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check deposit status updated
        self.deposit_request.refresh_from_db()
        self.assertEqual(self.deposit_request.status, 'REJECTED')
    
    def test_approve_withdrawal_api(self):
        """Test approving withdrawal via API"""
        url = reverse('admin-withdrawal-approve', kwargs={'pk': self.withdrawal_request.id})
        data = {
            'notes': 'Withdrawal approved via API',
            'tx_hash': '0xabcdef123456'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check withdrawal status updated
        self.withdrawal_request.refresh_from_db()
        self.assertEqual(self.withdrawal_request.status, 'APPROVED')
        self.assertEqual(self.withdrawal_request.tx_hash, '0xabcdef123456')
    
    def test_reject_withdrawal_api(self):
        """Test rejecting withdrawal via API"""
        url = reverse('admin-withdrawal-reject', kwargs={'pk': self.withdrawal_request.id})
        data = {'rejection_reason': 'Bank details incorrect'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check withdrawal status updated
        self.withdrawal_request.refresh_from_db()
        self.assertEqual(self.withdrawal_request.status, 'REJECTED')
    
    def test_approve_deposit_validation_error(self):
        """Test deposit approval with validation error"""
        url = reverse('admin-withdrawal-approve', kwargs={'pk': self.deposit_request.id})
        data = {'notes': ''}  # Empty notes
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('notes', response.data)
    
    def test_reject_deposit_validation_error(self):
        """Test deposit rejection with validation error"""
        url = reverse('admin-withdrawal-reject', kwargs={'pk': self.deposit_request.id})
        data = {'rejection_reason': ''}  # Empty reason
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rejection_reason', response.data)
    
    def test_approve_withdrawal_validation_error(self):
        """Test withdrawal approval with validation error"""
        url = reverse('admin-withdrawal-approve', kwargs={'pk': self.withdrawal_request.id})
        data = {'notes': ''}  # Empty notes
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('notes', response.data)
    
    def test_reject_withdrawal_validation_error(self):
        """Test withdrawal rejection with validation error"""
        url = reverse('admin-withdrawal-reject', kwargs={'pk': self.withdrawal_request.id})
        data = {'rejection_reason': ''}  # Empty reason
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rejection_reason', response.data)
    
    def test_deposit_withdrawal_api_permission_denied_non_admin(self):
        """Test API access denied for non-admin users"""
        self.client.force_authenticate(user=self.regular_user)
        
        url = reverse('admin-withdrawal-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_deposit_withdrawal_api_permission_denied_staff(self):
        """Test API access denied for staff users without permission"""
        self.client.force_authenticate(user=self.staff_user)
        
        url = reverse('admin-withdrawal-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_deposit_withdrawal_api_unauthorized(self):
        """Test API access denied for unauthenticated users"""
        self.client.force_authenticate(user=None)
        
        url = reverse('admin-withdrawal-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_approve_nonexistent_deposit(self):
        """Test approving non-existent deposit"""
        url = reverse('admin-withdrawal-approve', kwargs={'pk': 99999})
        data = {'notes': 'Test'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_approve_nonexistent_withdrawal(self):
        """Test approving non-existent withdrawal"""
        url = reverse('admin-withdrawal-approve', kwargs={'pk': 99999})
        data = {'notes': 'Test'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_approve_already_approved_deposit(self):
        """Test approving already approved deposit"""
        self.deposit_request.status = 'APPROVED'
        self.deposit_request.save()
        
        url = reverse('admin-withdrawal-approve', kwargs={'pk': self.deposit_request.id})
        data = {'notes': 'Test'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already approved', response.data['error'])
    
    def test_approve_already_approved_withdrawal(self):
        """Test approving already approved withdrawal"""
        self.withdrawal_request.status = 'APPROVED'
        self.withdrawal_request.save()
        
        url = reverse('admin-withdrawal-approve', kwargs={'pk': self.withdrawal_request.id})
        data = {'notes': 'Test'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already approved', response.data['error'])


class AdminDepositWithdrawalIntegrationTest(TestCase):
    """Test deposit and withdrawal management integration with other modules"""
    
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        self.regular_user = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123'
        )
        
        self.inr_wallet = INRWallet.objects.create(
            user=self.regular_user,
            balance=Decimal('1000.00')
        )
        
        self.usdt_wallet = USDTWallet.objects.create(
            user=self.regular_user,
            balance=Decimal('100.00')
        )
        
        self.deposit_request = DepositRequest.objects.create(
            user=self.regular_user,
            amount=Decimal('500.00'),
            currency='INR',
            payment_method='BANK_TRANSFER',
            transaction_id='DEP123456',
            status='PENDING'
        )
        
        self.withdrawal_request = Withdrawal.objects.create(
            user=self.regular_user,
            amount=Decimal('200.00'),
            currency='INR',
            payout_method='BANK_TRANSFER',
            bank_account='1234567890',
            ifsc_code='ABCD0001234',
            account_holder='Test User',
            status='PENDING'
        )
        
        self.withdrawal_service = AdminWithdrawalService()
    
    def test_deposit_approval_updates_wallet_balance(self):
        """Test that deposit approval correctly updates wallet balance"""
        initial_balance = self.inr_wallet.balance
        
        result = self.withdrawal_service.approve_deposit(
            deposit_id=self.deposit_request.id,
            admin_user=self.admin_user,
            notes='Integration test'
        )
        
        self.assertTrue(result['success'])
        
        # Check wallet balance updated
        self.inr_wallet.refresh_from_db()
        expected_balance = initial_balance + self.deposit_request.amount
        self.assertEqual(self.inr_wallet.balance, expected_balance)
    
    def test_withdrawal_approval_deducts_wallet_balance(self):
        """Test that withdrawal approval correctly deducts wallet balance"""
        initial_balance = self.inr_wallet.balance
        
        result = self.withdrawal_service.approve_withdrawal(
            withdrawal_id=self.withdrawal_request.id,
            admin_user=self.admin_user,
            notes='Integration test'
        )
        
        self.assertTrue(result['success'])
        
        # Check wallet balance deducted
        self.inr_wallet.refresh_from_db()
        expected_balance = initial_balance - self.withdrawal_request.amount
        self.assertEqual(self.inr_wallet.balance, expected_balance)
    
    def test_withdrawal_rejection_refunds_wallet_balance(self):
        """Test that withdrawal rejection correctly refunds wallet balance"""
        # First approve withdrawal to deduct balance
        self.withdrawal_request.status = 'APPROVED'
        self.withdrawal_request.save()
        self.inr_wallet.balance = Decimal('800.00')  # 1000 - 200
        self.inr_wallet.save()
        
        initial_balance = self.inr_wallet.balance
        
        # Now reject it
        result = self.withdrawal_service.reject_withdrawal(
            withdrawal_id=self.withdrawal_request.id,
            admin_user=self.admin_user,
            rejection_reason='Integration test rejection'
        )
        
        self.assertTrue(result['success'])
        
        # Check wallet balance refunded
        self.inr_wallet.refresh_from_db()
        expected_balance = initial_balance + self.withdrawal_request.amount
        self.assertEqual(self.inr_wallet.balance, expected_balance)
    
    def test_deposit_approval_creates_transaction_log(self):
        """Test that deposit approval creates proper transaction log"""
        result = self.withdrawal_service.approve_deposit(
            deposit_id=self.deposit_request.id,
            admin_user=self.admin_user,
            notes='Transaction log test'
        )
        
        self.assertTrue(result['success'])
        
        # Check transaction log exists
        transaction = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='deposit',
            amount=self.deposit_request.amount
        ).first()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.admin_user, self.admin_user)
    
    def test_withdrawal_approval_creates_transaction_log(self):
        """Test that withdrawal approval creates proper transaction log"""
        result = self.withdrawal_service.approve_withdrawal(
            withdrawal_id=self.withdrawal_request.id,
            admin_user=self.admin_user,
            notes='Transaction log test'
        )
        
        self.assertTrue(result['success'])
        
        # Check transaction log exists
        transaction = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='withdrawal',
            amount=self.withdrawal_request.amount
        ).first()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.admin_user, self.admin_user)
    
    def test_withdrawal_rejection_creates_refund_transaction_log(self):
        """Test that withdrawal rejection creates refund transaction log"""
        # First approve withdrawal
        self.withdrawal_request.status = 'APPROVED'
        self.withdrawal_request.save()
        self.inr_wallet.balance = Decimal('800.00')
        self.inr_wallet.save()
        
        # Now reject it
        result = self.withdrawal_service.reject_withdrawal(
            withdrawal_id=self.withdrawal_request.id,
            admin_user=self.admin_user,
            rejection_reason='Refund transaction log test'
        )
        
        self.assertTrue(result['success'])
        
        # Check refund transaction log exists
        transaction = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='withdrawal_refund',
            amount=self.withdrawal_request.amount
        ).first()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.admin_user, self.admin_user)
    
    def test_deposit_approval_logs_admin_action(self):
        """Test that deposit approval creates admin action log"""
        result = self.withdrawal_service.approve_deposit(
            deposit_id=self.deposit_request.id,
            admin_user=self.admin_user,
            notes='Admin action log test'
        )
        
        self.assertTrue(result['success'])
        
        # Check admin action log exists
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='DEPOSIT_APPROVAL',
            target_user=self.regular_user
        ).first()
        
        self.assertIsNotNone(action_log)
        self.assertEqual(action_log.target_model, 'DepositRequest')
        self.assertEqual(action_log.target_id, str(self.deposit_request.id))
    
    def test_withdrawal_approval_logs_admin_action(self):
        """Test that withdrawal approval creates admin action log"""
        result = self.withdrawal_service.approve_withdrawal(
            withdrawal_id=self.withdrawal_request.id,
            admin_user=self.admin_user,
            notes='Admin action log test'
        )
        
        self.assertTrue(result['success'])
        
        # Check admin action log exists
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='WITHDRAWAL_APPROVAL',
            target_user=self.regular_user
        ).first()
        
        self.assertIsNotNone(action_log)
        self.assertEqual(action_log.target_model, 'Withdrawal')
        self.assertEqual(action_log.target_id, str(self.withdrawal_request.id))
    
    def test_multiple_deposit_approvals_maintain_consistency(self):
        """Test that multiple deposit approvals maintain wallet consistency"""
        # Create another deposit request
        deposit2 = DepositRequest.objects.create(
            user=self.regular_user,
            amount=Decimal('300.00'),
            currency='INR',
            payment_method='BANK_TRANSFER',
            transaction_id='DEP789012',
            status='PENDING'
        )
        
        initial_balance = self.inr_wallet.balance
        
        # Approve first deposit
        result1 = self.withdrawal_service.approve_deposit(
            deposit_id=self.deposit_request.id,
            admin_user=self.admin_user,
            notes='First deposit'
        )
        self.assertTrue(result1['success'])
        
        # Approve second deposit
        result2 = self.withdrawal_service.approve_deposit(
            deposit_id=deposit2.id,
            admin_user=self.admin_user,
            notes='Second deposit'
        )
        self.assertTrue(result2['success'])
        
        # Check final balance
        self.inr_wallet.refresh_from_db()
        expected_balance = initial_balance + self.deposit_request.amount + deposit2.amount
        self.assertEqual(self.inr_wallet.balance, expected_balance)
        
        # Check transaction count
        transaction_count = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='deposit'
        ).count()
        self.assertEqual(transaction_count, 2)
