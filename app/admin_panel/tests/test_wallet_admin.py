import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from unittest.mock import patch

from app.wallet.models import INRWallet, USDTWallet, WalletTransaction
from app.admin_panel.models import AdminActionLog
from app.admin_panel.services import AdminWalletService
from app.admin_panel.permissions import log_admin_action

User = get_user_model()


class AdminWalletServiceTest(TestCase):
    """Test wallet management service layer"""
    
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
        
        # Get or create wallets (signals may have already created them)
        self.inr_wallet, _ = INRWallet.objects.get_or_create(
            user=self.regular_user,
            defaults={
                'balance': Decimal('1000.00'),
                'status': 'active',
                'is_active': True
            }
        )
        # Update balance if wallet already existed
        if self.inr_wallet.balance != Decimal('1000.00'):
            self.inr_wallet.balance = Decimal('1000.00')
            self.inr_wallet.status = 'active'
            self.inr_wallet.is_active = True
            self.inr_wallet.save()
        
        self.usdt_wallet, _ = USDTWallet.objects.get_or_create(
            user=self.regular_user,
            defaults={
                'balance': Decimal('100.00'),
                'status': 'active',
                'is_active': True
            }
        )
        # Update balance if wallet already existed
        if self.usdt_wallet.balance != Decimal('100.00'):
            self.usdt_wallet.balance = Decimal('100.00')
            self.usdt_wallet.status = 'active'
            self.usdt_wallet.is_active = True
            self.usdt_wallet.save()
        
        self.wallet_service = AdminWalletService()
    
    def test_get_user_wallets(self):
        """Test retrieving user wallets"""
        wallets = self.wallet_service.get_user_wallets(self.regular_user.id)
        
        self.assertEqual(len(wallets), 2)
        inr_wallet = next(w for w in wallets if isinstance(w, INRWallet))
        usdt_wallet = next(w for w in wallets if isinstance(w, USDTWallet))
        
        self.assertEqual(inr_wallet.balance, Decimal('1000.00'))
        self.assertEqual(usdt_wallet.balance, Decimal('100.00'))
    
    def test_get_user_wallets_nonexistent_user(self):
        """Test retrieving wallets for non-existent user"""
        wallets = self.wallet_service.get_user_wallets(99999)
        self.assertEqual(len(wallets), 0)
    
    def test_credit_inr_wallet(self):
        """Test crediting INR wallet"""
        result = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='INR',
            amount=Decimal('500.00'),
            adjustment_type='credit',
            reason='Admin credit for service',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check wallet balance updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('1500.00'))
        
        # Check transaction log created
        transaction = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='admin_credit',
            amount=Decimal('500.00')
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.description, 'Admin credit for service')
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='WALLET_ADJUSTMENT',
            target_user=self.regular_user
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('Admin credit for service', action_log.action_description)
    
    def test_debit_inr_wallet(self):
        """Test debiting INR wallet"""
        result = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='INR',
            amount=Decimal('200.00'),
            adjustment_type='debit',
            reason='Admin debit for fee',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check wallet balance updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('800.00'))
        
        # Check transaction log created
        transaction = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='admin_debit',
            amount=Decimal('200.00')
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.description, 'Admin debit for fee')
    
    def test_credit_usdt_wallet(self):
        """Test crediting USDT wallet"""
        result = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='USDT',
            amount=Decimal('50.00'),
            adjustment_type='credit',
            reason='Admin USDT credit',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check wallet balance updated
        self.usdt_wallet.refresh_from_db()
        self.assertEqual(self.usdt_wallet.balance, Decimal('150.00'))
        
        # Check transaction log created
        transaction = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='admin_credit',
            amount=Decimal('50.00')
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'USDT')
    
    def test_debit_usdt_wallet_sufficient_balance(self):
        """Test debiting USDT wallet with sufficient balance"""
        result = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='USDT',
            amount=Decimal('50.00'),
            adjustment_type='debit',
            reason='Admin USDT debit',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check wallet balance updated
        self.usdt_wallet.refresh_from_db()
        self.assertEqual(self.usdt_wallet.balance, Decimal('50.00'))
    
    def test_debit_usdt_wallet_insufficient_balance(self):
        """Test debiting USDT wallet with insufficient balance"""
        result = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='USDT',
            amount=Decimal('200.00'),
            adjustment_type='debit',
            reason='Admin USDT debit',
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('insufficient balance', result['error'])
        
        # Check wallet balance unchanged
        self.usdt_wallet.refresh_from_db()
        self.assertEqual(self.usdt_wallet.balance, Decimal('100.00'))
    
    def test_admin_override_wallet_balance(self):
        """Test admin override wallet balance (superuser only)"""
        result = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='USDT',
            amount=Decimal('500.00'),
            adjustment_type='override',
            reason='Admin override for correction',
            admin_user=self.admin_user,
            force_negative=True
        )
        
        self.assertTrue(result['success'])
        
        # Check wallet balance updated (can go negative with override)
        self.usdt_wallet.refresh_from_db()
        self.assertEqual(self.usdt_wallet.balance, Decimal('500.00'))
        
        # Check transaction log created
        transaction = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='admin_override',
            amount=Decimal('500.00')
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'USDT')
    
    def test_staff_user_cannot_override_wallet(self):
        """Test staff user cannot override wallet balance"""
        result = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='USDT',
            amount=Decimal('500.00'),
            adjustment_type='override',
            reason='Staff override attempt',
            admin_user=self.staff_user,
            force_negative=True
        )
        
        self.assertFalse(result['success'])
        self.assertIn('permission denied', result['error'])
        
        # Check wallet balance unchanged
        self.usdt_wallet.refresh_from_db()
        self.assertEqual(self.usdt_wallet.balance, Decimal('100.00'))
    
    def test_adjust_nonexistent_user_wallet(self):
        """Test adjusting wallet for non-existent user"""
        result = self.wallet_service.adjust_wallet_balance(
            user_id=99999,
            currency='INR',
            amount=Decimal('100.00'),
            adjustment_type='credit',
            reason='Test',
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
    
    def test_adjust_invalid_currency(self):
        """Test adjusting wallet with invalid currency"""
        result = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='EUR',
            amount=Decimal('100.00'),
            adjustment_type='credit',
            reason='Test',
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('invalid currency', result['error'])
    
    def test_adjust_invalid_amount(self):
        """Test adjusting wallet with invalid amount"""
        result = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='INR',
            amount=Decimal('-100.00'),
            adjustment_type='credit',
            reason='Test',
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('positive amount', result['error'])
    
    def test_adjust_invalid_type(self):
        """Test adjusting wallet with invalid adjustment type"""
        result = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='INR',
            amount=Decimal('100.00'),
            adjustment_type='invalid_type',
            reason='Test',
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('invalid adjustment type', result['error'])
    
    def test_wallet_transaction_logging(self):
        """Test that wallet adjustments create proper transaction logs"""
        result = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='INR',
            amount=Decimal('300.00'),
            adjustment_type='credit',
            reason='Test transaction logging',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check transaction log details
        transaction = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='admin_credit',
            amount=Decimal('300.00')
        ).first()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.user, self.regular_user)
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.transaction_type, 'admin_credit')
        self.assertEqual(transaction.amount, Decimal('300.00'))
        self.assertEqual(transaction.description, 'Test transaction logging')
        self.assertEqual(transaction.admin_user, self.admin_user)
    
    def test_multiple_wallet_adjustments(self):
        """Test multiple wallet adjustments maintain consistency"""
        # First adjustment
        result1 = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='INR',
            amount=Decimal('200.00'),
            adjustment_type='credit',
            reason='First adjustment',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result1['success'])
        
        # Second adjustment
        result2 = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='INR',
            amount=Decimal('100.00'),
            adjustment_type='debit',
            reason='Second adjustment',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result2['success'])
        
        # Check final balance
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('1100.00'))  # 1000 + 200 - 100
        
        # Check transaction count
        transaction_count = WalletTransaction.objects.filter(
            user=self.regular_user,
            currency='INR'
        ).count()
        self.assertEqual(transaction_count, 2)


class AdminWalletAPITest(TestCase):
    """Test wallet management API endpoints"""
    
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
        
        # Get or create wallets (signals may have already created them)
        self.inr_wallet, _ = INRWallet.objects.get_or_create(
            user=self.regular_user,
            defaults={
                'balance': Decimal('1000.00'),
                'status': 'active',
                'is_active': True
            }
        )
        # Update balance if wallet already existed
        if self.inr_wallet.balance != Decimal('1000.00'):
            self.inr_wallet.balance = Decimal('1000.00')
            self.inr_wallet.status = 'active'
            self.inr_wallet.is_active = True
            self.inr_wallet.save()
        
        self.usdt_wallet, _ = USDTWallet.objects.get_or_create(
            user=self.regular_user,
            defaults={
                'balance': Decimal('100.00'),
                'status': 'active',
                'is_active': True
            }
        )
        # Update balance if wallet already existed
        if self.usdt_wallet.balance != Decimal('100.00'):
            self.usdt_wallet.balance = Decimal('100.00')
            self.usdt_wallet.status = 'active'
            self.usdt_wallet.is_active = True
            self.usdt_wallet.save()
        
        self.client.force_authenticate(user=self.admin_user)
    
    def test_list_user_wallets(self):
        """Test listing user wallets"""
        url = reverse('admin-wallet-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_list_user_wallets_with_filters(self):
        """Test listing user wallets with filters"""
        url = reverse('admin-wallet-list')
        response = self.client.get(url, {
            'user_id': self.regular_user.id,
            'currency': 'INR'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['currency'], 'INR')
    
    def test_retrieve_user_wallet(self):
        """Test retrieving a specific user wallet"""
        url = reverse('admin-wallet-detail', kwargs={'pk': self.inr_wallet.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.inr_wallet.id)
        self.assertEqual(response.data['currency'], 'INR')
    
    def test_credit_wallet_api(self):
        """Test crediting wallet via API"""
        url = reverse('admin-wallet-adjust-balance', kwargs={'pk': self.inr_wallet.id})
        data = {
            'amount': '500.00',
            'adjustment_type': 'credit',
            'reason': 'API credit test'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check wallet balance updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('1500.00'))
    
    def test_debit_wallet_api(self):
        """Test debiting wallet via API"""
        url = reverse('admin-wallet-adjust-balance', kwargs={'pk': self.inr_wallet.id})
        data = {
            'amount': '200.00',
            'adjustment_type': 'debit',
            'reason': 'API debit test'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check wallet balance updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('800.00'))
    
    def test_override_wallet_api(self):
        """Test overriding wallet via API (superuser only)"""
        url = reverse('admin-wallet-adjust-balance', kwargs={'pk': self.usdt_wallet.id})
        data = {
            'amount': '500.00',
            'adjustment_type': 'override',
            'reason': 'API override test',
            'force_negative': True
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check wallet balance updated
        self.usdt_wallet.refresh_from_db()
        self.assertEqual(self.usdt_wallet.balance, Decimal('500.00'))
    
    def test_staff_user_cannot_override_wallet_api(self):
        """Test staff user cannot override wallet via API"""
        self.client.force_authenticate(user=self.staff_user)
        
        url = reverse('admin-wallet-adjust-balance', kwargs={'pk': self.usdt_wallet.id})
        data = {
            'amount': '500.00',
            'adjustment_type': 'override',
            'reason': 'Staff override attempt',
            'force_negative': True
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_wallet_adjustment_validation_error(self):
        """Test wallet adjustment with validation error"""
        url = reverse('admin-wallet-adjust-balance', kwargs={'pk': self.inr_wallet.id})
        data = {
            'amount': '-100.00',  # Invalid negative amount
            'adjustment_type': 'credit',
            'reason': 'Test'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('amount', response.data)
    
    def test_wallet_adjustment_insufficient_balance(self):
        """Test wallet debit with insufficient balance"""
        url = reverse('admin-wallet-adjust-balance', kwargs={'pk': self.usdt_wallet.id})
        data = {
            'amount': '200.00',
            'adjustment_type': 'debit',
            'reason': 'Test insufficient balance'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('insufficient balance', response.data['error'])
    
    def test_wallet_api_permission_denied_non_admin(self):
        """Test wallet API access denied for non-admin users"""
        self.client.force_authenticate(user=self.regular_user)
        
        url = reverse('admin-wallet-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_wallet_api_unauthorized(self):
        """Test wallet API access denied for unauthenticated users"""
        self.client.force_authenticate(user=None)
        
        url = reverse('admin-wallet-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_wallet_adjustment_nonexistent_wallet(self):
        """Test adjusting non-existent wallet"""
        url = reverse('admin-wallet-adjust-balance', kwargs={'pk': 99999})
        data = {
            'amount': '100.00',
            'adjustment_type': 'credit',
            'reason': 'Test'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AdminWalletIntegrationTest(TestCase):
    """Test wallet management integration with other modules"""
    
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
        
        # Get or create wallets (signals may have already created them)
        self.inr_wallet, _ = INRWallet.objects.get_or_create(
            user=self.regular_user,
            defaults={
                'balance': Decimal('1000.00'),
                'status': 'active',
                'is_active': True
            }
        )
        # Update balance if wallet already existed
        if self.inr_wallet.balance != Decimal('1000.00'):
            self.inr_wallet.balance = Decimal('1000.00')
            self.inr_wallet.status = 'active'
            self.inr_wallet.is_active = True
            self.inr_wallet.save()
        
        self.usdt_wallet, _ = USDTWallet.objects.get_or_create(
            user=self.regular_user,
            defaults={
                'balance': Decimal('100.00'),
                'status': 'active',
                'is_active': True
            }
        )
        # Update balance if wallet already existed
        if self.usdt_wallet.balance != Decimal('100.00'):
            self.usdt_wallet.balance = Decimal('100.00')
            self.usdt_wallet.status = 'active'
            self.usdt_wallet.is_active = True
            self.usdt_wallet.save()
        
        self.wallet_service = AdminWalletService()
    
    def test_wallet_adjustment_creates_transaction_log(self):
        """Test that wallet adjustments create proper transaction logs"""
        result = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='INR',
            amount=Decimal('300.00'),
            adjustment_type='credit',
            reason='Integration test',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check transaction log exists
        transaction = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='admin_credit',
            amount=Decimal('300.00')
        ).first()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.admin_user, self.admin_user)
    
    def test_wallet_adjustment_logs_admin_action(self):
        """Test that wallet adjustments create admin action logs"""
        result = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='USDT',
            amount=Decimal('50.00'),
            adjustment_type='debit',
            reason='Integration test',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check admin action log exists
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='WALLET_ADJUSTMENT',
            target_user=self.regular_user
        ).first()
        
        self.assertIsNotNone(action_log)
        self.assertEqual(action_log.target_model, 'Wallet')
        self.assertIn('Integration test', action_log.action_description)
    
    def test_wallet_balance_consistency(self):
        """Test that wallet balances remain consistent after multiple adjustments"""
        initial_inr_balance = self.inr_wallet.balance
        initial_usdt_balance = self.usdt_wallet.balance
        
        # Multiple adjustments
        adjustments = [
            ('INR', Decimal('100.00'), 'credit'),
            ('INR', Decimal('50.00'), 'debit'),
            ('USDT', Decimal('25.00'), 'credit'),
            ('USDT', Decimal('10.00'), 'debit')
        ]
        
        for currency, amount, adj_type in adjustments:
            result = self.wallet_service.adjust_wallet_balance(
                user_id=self.regular_user.id,
                currency=currency,
                amount=amount,
                adjustment_type=adj_type,
                reason=f'Balance consistency test - {adj_type}',
                admin_user=self.admin_user
            )
            self.assertTrue(result['success'])
        
        # Check final balances
        self.inr_wallet.refresh_from_db()
        self.usdt_wallet.refresh_from_db()
        
        expected_inr = initial_inr_balance + Decimal('100.00') - Decimal('50.00')
        expected_usdt = initial_usdt_balance + Decimal('25.00') - Decimal('10.00')
        
        self.assertEqual(self.inr_wallet.balance, expected_inr)
        self.assertEqual(self.usdt_wallet.balance, expected_usdt)
        
        # Check transaction count
        inr_transactions = WalletTransaction.objects.filter(
            user=self.regular_user,
            currency='INR'
        ).count()
        usdt_transactions = WalletTransaction.objects.filter(
            user=self.regular_user,
            currency='USDT'
        ).count()
        
        self.assertEqual(inr_transactions, 2)
        self.assertEqual(usdt_transactions, 2)
    
    def test_wallet_adjustment_withdrawal_impact(self):
        """Test that wallet adjustments don't interfere with withdrawal logic"""
        # Initial balance
        initial_balance = self.inr_wallet.balance
        
        # Credit wallet
        result = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='INR',
            amount=Decimal('500.00'),
            adjustment_type='credit',
            reason='Withdrawal impact test',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check balance increased
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, initial_balance + Decimal('500.00'))
        
        # Simulate withdrawal (debit)
        result = self.wallet_service.adjust_wallet_balance(
            user_id=self.regular_user.id,
            currency='INR',
            amount=Decimal('200.00'),
            adjustment_type='debit',
            reason='Simulated withdrawal',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check final balance
        self.inr_wallet.refresh_from_db()
        expected_balance = initial_balance + Decimal('500.00') - Decimal('200.00')
        self.assertEqual(self.inr_wallet.balance, expected_balance)
