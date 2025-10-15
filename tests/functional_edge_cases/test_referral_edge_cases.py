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
from app.referral.models import ReferralConfig, ReferralEarning, ReferralMilestone
from app.transactions.models import Transaction
from app.investment.models import InvestmentPlan, Investment

@pytest.mark.edge_case
class TestReferralEdgeCases(TestCase):
    """Test referral system edge cases and multi-level scenarios"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test users
        self.admin_user = User.objects.create_user(
            username='admin_ref',
            email='admin@ref.com',
            password='admin123!',
            is_staff=True,
            is_superuser=True
        )
        
        # Create referral chain users
        self.referrer = User.objects.create_user(
            username='referrer',
            email='referrer@test.com',
            password='ref123!',
            first_name='Referrer',
            last_name='User',
            kyc_status='APPROVED',
            is_kyc_verified=True
        )
        
        self.level1_user = User.objects.create_user(
            username='level1',
            email='level1@test.com',
            password='level123!',
            first_name='Level1',
            last_name='User',
            kyc_status='APPROVED',
            is_kyc_verified=True
        )
        
        self.level2_user = User.objects.create_user(
            username='level2',
            email='level2@test.com',
            password='level223!',
            first_name='Level2',
            last_name='User',
            kyc_status='APPROVED',
            is_kyc_verified=True
        )
        
        self.level3_user = User.objects.create_user(
            username='level3',
            email='level3@test.com',
            password='level323!',
            first_name='Level3',
            last_name='User',
            kyc_status='APPROVED',
            is_kyc_verified=True
        )
        
        # Create wallets for all users
        self.referrer_wallet, created = INRWallet.objects.get_or_create(
            user=self.referrer,
            defaults={
                'balance': Decimal('0.00'),
                'status': 'active'
            }
        )
        
        self.level1_wallet, created = INRWallet.objects.get_or_create(
            user=self.level1_user,
            defaults={
                'balance': Decimal('0.00'),
                'status': 'active'
            }
        )
        
        self.level2_wallet, created = INRWallet.objects.get_or_create(
            user=self.level2_user,
            defaults={
                'balance': Decimal('0.00'),
                'status': 'active'
            }
        )
        
        self.level3_wallet, created = INRWallet.objects.get_or_create(
            user=self.level3_user,
            defaults={
                'balance': Decimal('0.00'),
                'status': 'active'
            }
        )
        
        # Create referral configuration
        self.referral_config = ReferralConfig.objects.create(
            level_1_percentage=Decimal('5.00'),
            level_2_percentage=Decimal('3.00'),
            level_3_percentage=Decimal('1.00'),
            is_active=True
        )
        
        # Create investment plan
        self.investment_plan = InvestmentPlan.objects.create(
            name='Referral Test Plan',
            roi_rate=Decimal('12.00'),
            frequency='daily',
            duration_days=30,
            breakdown_window_days=15,
            min_amount=Decimal('1000.00'),
            max_amount=Decimal('10000.00'),
            status='active'
        )
        
        # Get tokens
        self.admin_token = self._get_token(self.admin_user)
        self.referrer_token = self._get_token(self.referrer)
        self.level1_token = self._get_token(self.level1_user)
        self.level2_token = self._get_token(self.level2_user)
        self.level3_token = self._get_token(self.level3_user)
        
        # Set authentication
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
    
    def _get_token(self, user):
        """Get JWT token for user"""
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    
    def test_full_three_level_referral_chain(self):
        """Test complete 3-level referral chain with earnings"""
        # Set up referral relationships
        self.level1_user.referrer = self.referrer
        self.level1_user.save()
        
        self.level2_user.referrer = self.level1_user
        self.level2_user.save()
        
        self.level3_user.referrer = self.level2_user
        self.level3_user.save()
        
        # Credit level 3 user for investment
        self.level3_wallet.balance = Decimal('1000.00')
        self.level3_wallet.save()
        
        # Create investment from level 3 user
        investment_data = {
            'plan': self.investment_plan.id,
            'amount': '1000.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.level3_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Calculate expected referral earnings
        investment_amount = Decimal('1000.00')
        level1_earning = investment_amount * Decimal('5.00') / Decimal('100')  # 5%
        level2_earning = investment_amount * Decimal('3.00') / Decimal('100')  # 3%
        level3_earning = investment_amount * Decimal('1.00') / Decimal('100')  # 1%
        
        # Check referral earnings were created
        level1_earning_obj = ReferralEarning.objects.filter(
            referral__user=self.referrer,
            investment__user=self.level1_user
        ).first()
        
        level2_earning_obj = ReferralEarning.objects.filter(
            referral__user=self.level1_user,
            investment__user=self.level2_user
        ).first()
        
        level3_earning_obj = ReferralEarning.objects.filter(
            referral__user=self.level2_user,
            investment__user=self.level3_user
        ).first()
        
        self.assertIsNotNone(level1_earning_obj)
        self.assertIsNotNone(level2_earning_obj)
        self.assertIsNotNone(level3_earning_obj)
        
        # Verify earnings amounts
        self.assertEqual(level1_earning_obj.amount, level1_earning)
        self.assertEqual(level2_earning_obj.amount, level2_earning)
        self.assertEqual(level3_earning_obj.amount, level3_earning)
    
    def test_referral_earnings_wallet_credit(self):
        """Test that referral earnings are properly credited to wallets"""
        # Set up referral relationship
        self.level1_user.referrer = self.referrer
        self.level1_user.save()
        
        # Credit level 1 user for investment
        self.level1_wallet.balance = Decimal('1000.00')
        self.level1_wallet.save()
        
        # Create investment
        investment_data = {
            'plan': self.investment_plan.id,
            'amount': '1000.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.level1_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check referrer wallet was credited
        self.referrer_wallet.refresh_from_db()
        expected_earning = Decimal('1000.00') * Decimal('5.00') / Decimal('100')
        self.assertEqual(self.referrer_wallet.balance, expected_earning)
        
        # Check transaction was created
        transaction = Transaction.objects.filter(
            user=self.referrer,
            type='REFERRAL_BONUS'
        ).first()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, expected_earning)
    
    def test_referral_chain_break_handling(self):
        """Test handling when referral chain is broken"""
        # Set up partial referral chain
        self.level1_user.referrer = self.referrer
        self.level1_user.save()
        
        # Level 2 has no referrer (broken chain)
        self.level2_user.referrer = None
        self.level2_user.save()
        
        # Level 3 refers to level 2
        self.level3_user.referrer = self.level2_user
        self.level3_user.save()
        
        # Credit level 3 user for investment
        self.level3_wallet.balance = Decimal('1000.00')
        self.level3_wallet.save()
        
        # Create investment from level 3 user
        investment_data = {
            'plan': self.investment_plan.id,
            'amount': '1000.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.level3_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Only level 2 should get earnings (level 1 gets nothing due to broken chain)
        level2_earning = ReferralEarning.objects.filter(
            referral__user=self.level2_user,
            investment__user=self.level3_user
        ).first()
        
        level1_earning = ReferralEarning.objects.filter(
            referral__user=self.referrer,
            investment__user=self.level2_user
        ).first()
        
        self.assertIsNotNone(level2_earning)
        self.assertIsNone(level1_earning)
    
    def test_referral_earnings_precision(self):
        """Test referral earnings calculation precision"""
        # Set up referral relationship
        self.level1_user.referrer = self.referrer
        self.level1_user.save()
        
        # Test with various investment amounts
        test_amounts = [
            '1000.00',
            '1000.50',
            '1000.99',
            '9999.99'
        ]
        
        for amount_str in test_amounts:
            amount = Decimal(amount_str)
            
            # Credit user
            self.level1_wallet.balance = amount
            self.level1_wallet.save()
            
            # Create investment
            investment_data = {
                'plan': self.investment_plan.id,
                'amount': amount_str,
                'currency': 'inr'
            }
            
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.level1_token}')
            response = self.client.post(
                reverse('investment:investment-list'),
                investment_data
            )
            
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            
            # Calculate expected earning
            expected_earning = amount * Decimal('5.00') / Decimal('100')
            
            # Check earning precision
            earning = ReferralEarning.objects.filter(
                referral__user=self.referrer,
                investment__user=self.level1_user
            ).first()
            
            self.assertIsNotNone(earning)
            self.assertEqual(earning.amount, expected_earning)
            
            # Clean up
            investment = Investment.objects.get(user=self.level1_user)
            investment.delete()
            
            # Reset wallet
            self.level1_wallet.balance = Decimal('0.00')
            self.level1_wallet.save()
    
    def test_concurrent_referral_earnings(self):
        """Test concurrent referral earnings processing"""
        # Set up multiple referral relationships
        self.level1_user.referrer = self.referrer
        self.level1_user.save()
        
        self.level2_user.referrer = self.referrer
        self.level2_user.save()
        
        # Credit both users
        self.level1_wallet.balance = Decimal('1000.00')
        self.level1_wallet.save()
        
        self.level2_wallet.balance = Decimal('1000.00')
        self.level2_wallet.save()
        
        def create_investment(user_token, wallet):
            investment_data = {
                'plan': self.investment_plan.id,
                'amount': '1000.00',
                'currency': 'inr'
            }
            
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {user_token}')
            response = client.post(
                reverse('investment:investment-list'),
                investment_data
            )
            return response.status_code
        
        # Create investments concurrently
        threads = []
        results = []
        
        # Level 1 user investment
        thread1 = threading.Thread(
            target=lambda: results.append(create_investment(self.level1_token, self.level1_wallet))
        )
        threads.append(thread1)
        
        # Level 2 user investment
        thread2 = threading.Thread(
            target=lambda: results.append(create_investment(self.level2_token, self.level2_wallet))
        )
        threads.append(thread2)
        
        # Start threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All should succeed
        for result in results:
            self.assertEqual(result, status.HTTP_201_CREATED)
        
        # Check total earnings
        self.referrer_wallet.refresh_from_db()
        expected_total = Decimal('2000.00') * Decimal('5.00') / Decimal('100')  # 5% of 2000
        self.assertEqual(self.referrer_wallet.balance, expected_total)
        
        # Check earnings count
        earnings_count = ReferralEarning.objects.filter(referral__user=self.referrer).count()
        self.assertEqual(earnings_count, 2)
    
    def test_referral_milestone_achievement(self):
        """Test referral milestone achievement and bonus"""
        # Create referral milestone
        milestone = ReferralMilestone.objects.create(
            name='First Referral Bonus',
            description='Bonus for first successful referral',
            condition_type='total_referrals',
            condition_value=Decimal('1.00'),
            bonus_amount=Decimal('100.00'),
            currency='INR',
            is_active=True
        )
        
        # Set up referral relationship
        self.level1_user.referrer = self.referrer
        self.level1_user.save()
        
        # Credit level 1 user for investment
        self.level1_wallet.balance = Decimal('1000.00')
        self.level1_wallet.save()
        
        # Create investment
        investment_data = {
            'plan': self.investment_plan.id,
            'amount': '1000.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.level1_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check milestone bonus was credited
        self.referrer_wallet.refresh_from_db()
        
        # Should have both referral earning and milestone bonus
        referral_earning = Decimal('1000.00') * Decimal('5.00') / Decimal('100')
        milestone_bonus = Decimal('100.00')
        expected_total = referral_earning + milestone_bonus
        
        self.assertEqual(self.referrer_wallet.balance, expected_total)
    
    def test_referral_earnings_withdrawal_scenario(self):
        """Test referral earnings in withdrawal scenarios"""
        # Set up referral relationship
        self.level1_user.referrer = self.referrer
        self.level1_user.save()
        
        # Credit level 1 user for investment
        self.level1_wallet.balance = Decimal('1000.00')
        self.level1_wallet.save()
        
        # Create investment
        investment_data = {
            'plan': self.investment_plan.id,
            'amount': '1000.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.level1_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Referrer should have earnings
        self.referrer_wallet.refresh_from_db()
        expected_earning = Decimal('1000.00') * Decimal('5.00') / Decimal('100')
        self.assertEqual(self.referrer_wallet.balance, expected_earning)
        
        # Referrer creates withdrawal
        withdrawal_data = {
            'currency': 'INR',
            'amount': str(expected_earning),
            'payout_method': 'bank_transfer',
            'payout_details': {
                'account_number': '1234567890',
                'ifsc_code': 'SBIN0001234',
                'account_holder_name': 'Test User',
                'bank_name': 'State Bank of India'
            }
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.referrer_token}')
        response = self.client.post(
            reverse('create-withdrawal'),
            withdrawal_data
        )
        
        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Wallet balance should be zero
        self.referrer_wallet.refresh_from_db()
        self.assertEqual(self.referrer_wallet.balance, Decimal('0.00'))
    
    def test_referral_earnings_kyc_requirement(self):
        """Test referral earnings require KYC verification"""
        # Set up referral relationship
        self.level1_user.referrer = self.referrer
        self.level1_user.save()
        
        # Ensure referrer is not KYC verified (but level1_user should be verified to invest)
        self.referrer.is_kyc_verified = False
        self.referrer.kyc_status = 'PENDING'
        self.referrer.save()
        
        # Ensure level1_user has KYC verification to make investment
        self.level1_user.is_kyc_verified = True
        self.level1_user.kyc_status = 'APPROVED'
        self.level1_user.save()
        
        # Credit level 1 user for investment
        self.level1_wallet.balance = Decimal('1000.00')
        self.level1_wallet.save()
        
        # Create investment
        investment_data = {
            'plan': self.investment_plan.id,
            'amount': '1000.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.level1_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        # Debug: Print response details if it fails
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Investment creation failed: {response.status_code}")
            print(f"Response data: {response.data if hasattr(response, 'data') else 'No data'}")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Referrer should not get earnings without KYC
        self.referrer_wallet.refresh_from_db()
        self.assertEqual(self.referrer_wallet.balance, Decimal('0.00'))
        
        # Verify no referral earnings were created
        earnings = ReferralEarning.objects.filter(referral__user=self.referrer)
        self.assertEqual(earnings.count(), 0)
    
    def test_referral_earnings_currency_handling(self):
        """Test referral earnings with different currencies"""
        # Create USDT wallet for referrer
        referrer_usdt_wallet, created = USDTWallet.objects.get_or_create(
            user=self.referrer,
            defaults={
                'balance': Decimal('0.000000'),
                'status': 'active'
            }
        )
        
        # Set up referral relationship
        self.level1_user.referrer = self.referrer
        self.level1_user.save()
        
        # Create USDT investment plan
        usdt_plan = InvestmentPlan.objects.create(
            name='USDT Test Plan',
            roi_rate=Decimal('10.00'),
            frequency='daily',
            duration_days=30,
            breakdown_window_days=15,
            min_amount=Decimal('100.00'),
            max_amount=Decimal('1000.00'),
            status='active'
        )
        
        # Credit level 1 user with USDT
        self.level1_wallet.balance = Decimal('100.00')
        self.level1_wallet.save()
        
        # Create USDT investment
        investment_data = {
            'plan': usdt_plan.id,
            'amount': '100.00',
            'currency': 'usdt'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.level1_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Referrer should get earnings in USDT
        referrer_usdt_wallet.refresh_from_db()
        expected_earning = Decimal('100.00') * Decimal('5.00') / Decimal('100')
        self.assertEqual(referrer_usdt_wallet.balance, expected_earning)
        
        # Clean up
        usdt_plan.delete()
        referrer_usdt_wallet.delete()
    
    def test_referral_earnings_inactive_config(self):
        """Test referral earnings when config is inactive"""
        # Deactivate referral config
        self.referral_config.is_active = False
        self.referral_config.save()
        
        # Set up referral relationship
        self.level1_user.referrer = self.referrer
        self.level1_user.save()
        
        # Credit level 1 user for investment
        self.level1_wallet.balance = Decimal('1000.00')
        self.level1_wallet.save()
        
        # Create investment
        investment_data = {
            'plan': self.investment_plan.id,
            'amount': '1000.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.level1_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Referrer should not get earnings when config is inactive
        self.referrer_wallet.refresh_from_db()
        self.assertEqual(self.referrer_wallet.balance, Decimal('0.00'))
        
        # Reactivate config
        self.referral_config.is_active = True
        self.referral_config.save()
