import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from unittest.mock import patch

from app.admin_panel.services import AdminDashboardService
from app.kyc.models import KYCDocument
from app.wallet.models import INRWallet, USDTWallet
from app.investment.models import Investment, InvestmentPlan
from app.withdrawals.models import Withdrawal
from app.referral.models import Referral
from app.wallet.models import WalletTransaction

User = get_user_model()


class AdminDashboardServiceTest(TestCase):
    """Test cases for AdminDashboardService."""
    
    def setUp(self):
        """Set up test data."""
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True,
            is_kyc_verified=True,
            kyc_status='APPROVED'
        )
        
        # Create regular users
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123'
        )
        
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='testpass123',
            is_kyc_verified=True,
            kyc_status='APPROVED'
        )
        
        self.user3 = User.objects.create_user(
            username='user3',
            email='user3@test.com',
            password='testpass123',
            is_kyc_verified=True,
            kyc_status='APPROVED'
        )
        
        # Get or create wallets (signals may have already created them)
        self.inr_wallet1, _ = INRWallet.objects.get_or_create(
            user=self.user1,
            defaults={
                'balance': Decimal('1000.00'),
                'status': 'active',
                'is_active': True
            }
        )
        # Update balance if wallet already existed
        if self.inr_wallet1.balance != Decimal('1000.00'):
            self.inr_wallet1.balance = Decimal('1000.00')
            self.inr_wallet1.status = 'active'
            self.inr_wallet1.is_active = True
            self.inr_wallet1.save()
        
        self.usdt_wallet1, _ = USDTWallet.objects.get_or_create(
            user=self.user1,
            defaults={
                'balance': Decimal('100.000000'),
                'status': 'active',
                'is_active': True
            }
        )
        # Update balance if wallet already existed
        if self.usdt_wallet1.balance != Decimal('100.000000'):
            self.usdt_wallet1.balance = Decimal('100.000000')
            self.usdt_wallet1.status = 'active'
            self.usdt_wallet1.is_active = True
            self.usdt_wallet1.save()
        
        self.inr_wallet2, _ = INRWallet.objects.get_or_create(
            user=self.user2,
            defaults={
                'balance': Decimal('2000.00'),
                'status': 'active',
                'is_active': True
            }
        )
        # Update balance if wallet already existed
        if self.inr_wallet2.balance != Decimal('2000.00'):
            self.inr_wallet2.balance = Decimal('2000.00')
            self.inr_wallet2.status = 'active'
            self.inr_wallet2.is_active = True
            self.inr_wallet2.save()
        
        self.usdt_wallet2, _ = USDTWallet.objects.get_or_create(
            user=self.user2,
            defaults={
                'balance': Decimal('200.000000'),
                'status': 'active',
                'is_active': True
            }
        )
        # Update balance if wallet already existed
        if self.usdt_wallet2.balance != Decimal('200.000000'):
            self.usdt_wallet2.balance = Decimal('200.000000')
            self.usdt_wallet2.status = 'active'
            self.usdt_wallet2.is_active = True
            self.usdt_wallet2.save()
        
        # Create investment plan
        self.plan = InvestmentPlan.objects.create(
            name='Test Plan',
            min_amount=Decimal('100.00'),
            max_amount=Decimal('10000.00'),
            roi_rate=Decimal('5.00'),
            frequency='daily',
            duration_days=30,
            breakdown_window_days=15,
            status='active'
        )
        
        # Create investments
        self.investment1 = Investment.objects.create(
            user=self.user1,
            plan=self.plan,
            amount=Decimal('500.00'),
            status='active',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timezone.timedelta(days=30)
        )
        
        self.investment2 = Investment.objects.create(
            user=self.user2,
            plan=self.plan,
            amount=Decimal('1000.00'),
            status='active',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timezone.timedelta(days=30)
        )
        
        # Create withdrawal requests
        self.withdrawal1 = Withdrawal.objects.create(
            user=self.user1,
            currency='INR',
            amount=Decimal('500.00'),
            fee=Decimal('10.00'),
            payout_method='bank_transfer',
            payout_details='{"account_number": "1234567890", "ifsc_code": "SBIN0001234", "account_holder_name": "Test User", "bank_name": "State Bank of India"}',
            status='PENDING'
        )
        
        self.withdrawal2 = Withdrawal.objects.create(
            user=self.user2,
            currency='USDT',
            amount=Decimal('50.000000'),
            fee=Decimal('1.000000'),
            payout_method='usdt_erc20',
            payout_details='{"wallet_address": "0x1234567890123456789012345678901234567890"}',
            status='PENDING'
        )
        
        # Create referrals
        self.referral1 = Referral.objects.create(
            user=self.user1,
            referred_user=self.user2,
            level=1
        )
        
        self.referral2 = Referral.objects.create(
            user=self.user1,
            referred_user=self.user3,
            level=1
        )
        
        # Create transactions
        self.transaction1 = WalletTransaction.objects.create(
            user=self.user1,
            transaction_type='deposit',
            wallet_type='inr',
            amount=Decimal('1000.00'),
            balance_before=Decimal('0.00'),
            balance_after=Decimal('1000.00'),
            status='completed'
        )
        
        self.transaction2 = WalletTransaction.objects.create(
            user=self.user2,
            transaction_type='deposit',
            wallet_type='usdt',
            amount=Decimal('100.000000'),
            balance_before=Decimal('0.000000'),
            balance_after=Decimal('100.000000'),
            status='completed'
        )
    
    def test_get_dashboard_summary(self):
        """Test getting dashboard summary statistics."""
        summary = AdminDashboardService.get_dashboard_summary()
        
        # Test user statistics
        self.assertEqual(summary['total_users'], 4)  # admin + 3 users
        self.assertEqual(summary['verified_users'], 3)  # admin, user2, user3
        self.assertEqual(summary['pending_kyc_users'], 1)  # user1
        self.assertEqual(summary['active_users'], 4)
        
        # Test wallet statistics
        self.assertGreaterEqual(summary['total_inr_balance'], Decimal('3000.00'))  # At least 3000 (user1 + user2)
        self.assertGreaterEqual(summary['total_usdt_balance'], Decimal('300.000000'))  # At least 300 (user1 + user2)
        self.assertGreaterEqual(summary['total_wallets'], 4)  # At least 4 wallets
        
        # Test investment statistics
        self.assertEqual(summary['active_investments'], 2)
        self.assertEqual(summary['total_investment_amount'], Decimal('1500.00'))
        self.assertEqual(summary['pending_roi_payments'], 2)
        
        # Test withdrawal statistics
        self.assertEqual(summary['pending_withdrawals'], 2)
        self.assertEqual(summary['pending_withdrawal_amount'], Decimal('550.00'))
        
        # Test referral statistics
        self.assertEqual(summary['total_referrals'], 2)
        self.assertEqual(summary['active_referral_chains'], 1)
        
        # Test transaction statistics
        self.assertEqual(summary['today_transactions'], 2)
        self.assertGreaterEqual(summary['this_week_transactions'], 2)
        self.assertGreaterEqual(summary['this_month_transactions'], 2)
        
        # Test system health
        self.assertEqual(summary['system_status'], 'Healthy')
        self.assertIsNone(summary['last_backup'])
    
    def test_dashboard_summary_with_no_data(self):
        """Test dashboard summary when there's no data."""
        # Clear all data including admin user's data
        INRWallet.objects.all().delete()
        USDTWallet.objects.all().delete()
        Investment.objects.all().delete()
        Withdrawal.objects.all().delete()
        Referral.objects.all().delete()
        WalletTransaction.objects.all().delete()
        User.objects.exclude(id=self.admin_user.id).delete()
        
        summary = AdminDashboardService.get_dashboard_summary()
        
        # Test that all counts are 0 except admin user
        self.assertEqual(summary['total_users'], 1)  # Only admin remains
        self.assertEqual(summary['verified_users'], 1)  # Admin user is verified
        self.assertEqual(summary['pending_kyc_users'], 0)
        self.assertEqual(summary['active_users'], 1)  # Admin user is active
        self.assertEqual(summary['total_inr_balance'], Decimal('0.00'))
        self.assertEqual(summary['total_usdt_balance'], Decimal('0.000000'))
        self.assertEqual(summary['total_wallets'], 0)
        self.assertEqual(summary['active_investments'], 0)
        self.assertEqual(summary['total_investment_amount'], Decimal('0.00'))
        self.assertEqual(summary['pending_roi_payments'], 0)
        self.assertEqual(summary['pending_withdrawals'], 0)
        self.assertEqual(summary['pending_withdrawal_amount'], Decimal('0.00'))
        self.assertEqual(summary['total_referrals'], 0)
        self.assertEqual(summary['active_referral_chains'], 0)
        self.assertEqual(summary['today_transactions'], 0)
        self.assertEqual(summary['this_week_transactions'], 0)
        self.assertEqual(summary['this_month_transactions'], 0)
    
    def test_dashboard_summary_with_mixed_statuses(self):
        """Test dashboard summary with mixed user and wallet statuses."""
        # Deactivate some users
        self.user1.is_active = False
        self.user1.save()
        
        # Suspend some wallets
        self.inr_wallet1.status = 'suspended'
        self.inr_wallet1.save()
        
        self.usdt_wallet2.status = 'locked'
        self.usdt_wallet2.save()
        
        # Cancel some investments
        self.investment1.status = 'cancelled'
        self.investment1.save()
        
        # Complete some withdrawals
        self.withdrawal1.status = 'COMPLETED'
        self.withdrawal1.save()
        
        summary = AdminDashboardService.get_dashboard_summary()
        
        # Test updated counts
        self.assertEqual(summary['active_users'], 3)  # admin + user2 + user3
        self.assertEqual(summary['total_inr_balance'], Decimal('2000.00'))  # Only user2's wallet (user1 is deactivated)
        self.assertEqual(summary['total_usdt_balance'], Decimal('0.000000'))  # user1 is deactivated, user2's wallet is locked
        self.assertEqual(summary['active_investments'], 1)  # Only user2's investment
        self.assertEqual(summary['pending_withdrawals'], 1)  # Only user2's withdrawal
    
    def test_dashboard_summary_error_handling(self):
        """Test dashboard summary error handling."""
        # Mock a database error
        with patch('app.admin_panel.services.AdminDashboardService.get_dashboard_summary') as mock_get:
            mock_get.side_effect = Exception("Database connection error")
            
            with self.assertRaises(Exception):
                AdminDashboardService.get_dashboard_summary()
    
    def test_dashboard_summary_performance(self):
        """Test dashboard summary performance with large datasets."""
        # Create many users and transactions to test performance
        users = []
        for i in range(100):
            user = User.objects.create_user(
                username=f'perfuser{i}',
                email=f'perfuser{i}@test.com',
                password='testpass123'
            )
            users.append(user)
            
            # Get or create wallet for each user (signals may have already created them)
            wallet, _ = INRWallet.objects.get_or_create(
                user=user,
                defaults={
                    'balance': Decimal('100.00'),
                    'status': 'active',
                    'is_active': True
                }
            )
            # Update balance if wallet already existed
            if wallet.balance != Decimal('100.00'):
                wallet.balance = Decimal('100.00')
                wallet.status = 'active'
                wallet.is_active = True
                wallet.save()
            
            # Create transaction for each user
            WalletTransaction.objects.create(
                user=user,
                transaction_type='deposit',
                wallet_type='inr',
                amount=Decimal('100.00'),
                balance_before=Decimal('0.00'),
                balance_after=Decimal('100.00'),
                status='completed'
            )
        
        # Test that summary can be generated efficiently
        import time
        start_time = time.time()
        summary = AdminDashboardService.get_dashboard_summary()
        end_time = time.time()
        
        # Should complete within reasonable time (less than 1 second)
        self.assertLess(end_time - start_time, 1.0)
        
        # Verify counts - only check that performance is acceptable
        self.assertGreaterEqual(summary['total_users'], 100)  # At least 100 new users
        self.assertGreaterEqual(summary['total_inr_balance'], Decimal('10000.00'))  # At least 100 * 100
        self.assertGreaterEqual(summary['today_transactions'], 100)  # At least 100 new transactions
