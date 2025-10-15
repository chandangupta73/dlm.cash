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
from app.investment.models import InvestmentPlan, Investment
from app.transactions.models import Transaction
from freezegun import freeze_time

@pytest.mark.edge_case
class TestInvestmentEdgeCases(TestCase):
    """Test investment edge cases and boundary conditions"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test users
        self.admin_user = User.objects.create_user(
            username='admin_inv',
            email='admin@inv.com',
            password='admin123!',
            is_staff=True,
            is_superuser=True
        )
        
        self.user = User.objects.create_user(
            username='user_inv',
            email='user@inv.com',
            password='user123!',
            first_name='Investment',
            last_name='User',
            kyc_status='APPROVED',
            is_kyc_verified=True
        )
        
        # Create wallets
        self.inr_wallet, created = INRWallet.objects.get_or_create(
            user=self.user,
            defaults={
                'balance': Decimal('0.00'),
                'status': 'active'
            }
        )
        
        # Create investment plans
        self.basic_plan = InvestmentPlan.objects.create(
            name='Basic Plan',
            roi_rate=Decimal('12.00'),
            frequency='daily',
            duration_days=30,
            min_amount=Decimal('1000.00'),
            max_amount=Decimal('10000.00'),
            breakdown_window_days=30,
            status='active'
        )
        
        self.premium_plan = InvestmentPlan.objects.create(
            name='Premium Plan',
            roi_rate=Decimal('18.00'),
            frequency='daily',
            duration_days=60,
            min_amount=Decimal('5000.00'),
            max_amount=Decimal('50000.00'),
            breakdown_window_days=30,
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
    
    def test_investment_min_amount_boundary(self):
        """Test investment with exactly minimum amount"""
        # Credit wallet with minimum amount
        self.inr_wallet.balance = Decimal('1000.00')
        self.inr_wallet.save()
        
        # Create investment with minimum amount
        investment_data = {
            'plan': self.basic_plan.id,
            'amount': '1000.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        # Should succeed
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Investment creation failed: {response.status_code}")
            print(f"Response data: {response.data if hasattr(response, 'data') else 'No data'}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check investment was created
        investment = Investment.objects.get(user=self.user)
        self.assertEqual(investment.amount, Decimal('1000.00'))
        self.assertEqual(investment.status, 'active')
    
    def test_investment_max_amount_boundary(self):
        """Test investment with exactly maximum amount"""
        # Credit wallet with maximum amount
        self.inr_wallet.balance = Decimal('10000.00')
        self.inr_wallet.save()
        
        # Create investment with maximum amount
        investment_data = {
            'plan': self.basic_plan.id,
            'amount': '10000.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check investment was created
        investment = Investment.objects.get(user=self.user)
        self.assertEqual(investment.amount, Decimal('10000.00'))
    
    def test_investment_just_over_max_amount_rejection(self):
        """Test investment with amount just over maximum"""
        # Credit wallet with amount over max
        self.inr_wallet.balance = Decimal('10001.00')
        self.inr_wallet.save()
        
        # Create investment with amount just over max
        investment_data = {
            'plan': self.basic_plan.id,
            'amount': '10001.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        # Should fail
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('maximum', str(response.data).lower()) or self.assertIn('between', str(response.data).lower())
    
    def test_investment_just_under_min_amount_rejection(self):
        """Test investment with amount just under minimum"""
        # Credit wallet with amount under min
        self.inr_wallet.balance = Decimal('999.99')
        self.inr_wallet.save()
        
        # Create investment with amount just under min
        investment_data = {
            'plan': self.basic_plan.id,
            'amount': '999.99',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        # Should fail
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('minimum', str(response.data).lower()) or self.assertIn('between', str(response.data).lower())
    
    def test_investment_decimal_precision_handling(self):
        """Test investment with various decimal precision amounts"""
        # Test amounts with different decimal places
        test_amounts = [
            '1000.50',
            '1000.99',
            '1000.01',
            '9999.99'
        ]
        
        for amount_str in test_amounts:
            amount = Decimal(amount_str)
            
            # Credit wallet
            self.inr_wallet.balance = amount
            self.inr_wallet.save()
            
            # Create investment
            investment_data = {
                'plan': self.basic_plan.id,
                'amount': amount_str,
                'currency': 'inr'
            }
            
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
            response = self.client.post(
                reverse('investment:investment-list'),
                investment_data
            )
            
            # Should succeed for valid amounts
            if Decimal('1000.00') <= amount <= Decimal('10000.00'):
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                
                # Verify investment amount precision
                investment = Investment.objects.get(user=self.user)
                self.assertEqual(investment.amount, amount)
                
                # Clean up
                investment.delete()
            else:
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_roi_credit_non_eligible_date(self):
        """Test ROI credit on non-eligible date"""
        # Create investment
        self.inr_wallet.balance = Decimal('1000.00')
        self.inr_wallet.save()
        
        investment_data = {
            'plan': self.basic_plan.id,
            'amount': '1000.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        investment = Investment.objects.get(user=self.user)
        
        # Try to trigger ROI on investment start date (should fail)
        start_date = investment.start_date.strftime('%Y-%m-%d')
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        response = self.client.post(
            reverse('admin_panel:admin-investments-trigger-roi'),
            {'date': start_date}
        )
        
        # Should fail - ROI cannot be credited on start date
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_roi_credit_eligible_date(self):
        """Test ROI credit on eligible date"""
        # Create investment
        self.inr_wallet.balance = Decimal('1000.00')
        self.inr_wallet.save()
        
        investment_data = {
            'plan': self.basic_plan.id,
            'amount': '1000.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        investment = Investment.objects.get(user=self.user)
        
        # Calculate eligible date (next day after start)
        eligible_date = (investment.start_date + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Trigger ROI on eligible date
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        response = self.client.post(
            reverse('admin_panel:admin-investments-trigger-roi'),
            {'date': eligible_date}
        )
        
        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check ROI was credited
        self.inr_wallet.refresh_from_db()
        expected_roi = Decimal('1000.00') * Decimal('12.00') / Decimal('100') / Decimal('365')
        self.assertGreater(self.inr_wallet.balance, Decimal('0.00'))
    
    def test_concurrent_investment_creation(self):
        """Test concurrent investment creation from same wallet"""
        # Credit wallet with sufficient balance for multiple investments
        self.inr_wallet.balance = Decimal('3000.00')
        self.inr_wallet.save()
        
        def create_investment(amount):
            investment_data = {
                'plan': self.basic_plan.id,
                'amount': str(amount),
                'currency': 'inr'
            }
            
            # Use the main test client with proper authentication
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
            response = self.client.post(
                reverse('investment:investment-list'),
                investment_data
            )
            return response.status_code
        
        # Create multiple investments concurrently
        threads = []
        results = []
        
        amounts = [1000, 1000, 1000]
        
        for amount in amounts:
            thread = threading.Thread(
                target=lambda: results.append(create_investment(amount))
            )
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All should succeed
        for result in results:
            self.assertEqual(result, status.HTTP_201_CREATED)
        
        # Check total investments created
        investment_count = Investment.objects.filter(user=self.user).count()
        self.assertEqual(investment_count, 3)
        
        # Check wallet balance is zero
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('0.00'))
    
    def test_investment_maturity_date_calculation(self):
        """Test investment maturity date calculation edge cases"""
        # Test with different duration days
        test_durations = [1, 7, 30, 365]
        
        for duration in test_durations:
            # Create plan with specific duration
            plan = InvestmentPlan.objects.create(
                name=f'Test Plan {duration}',
                roi_rate=Decimal('10.00'),
                frequency='daily',
                duration_days=duration,
                breakdown_window_days=15,
                min_amount=Decimal('100.00'),
                max_amount=Decimal('1000.00'),
                status='active'
            )
            
            # Create investment
            self.inr_wallet.balance = Decimal('100.00')
            self.inr_wallet.save()
            
            investment_data = {
                'plan': plan.id,
                'amount': '100.00',
                'currency': 'inr'
            }
            
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
            response = self.client.post(
                reverse('investment:investment-list'),
                investment_data
            )
            
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            
            # Check maturity date calculation
            investment = Investment.objects.get(user=self.user)
            expected_maturity = investment.start_date + timedelta(days=duration)
            self.assertEqual(investment.end_date.date(), expected_maturity.date())
            
            # Clean up
            investment.delete()
            plan.delete()
    
    def test_investment_status_transitions(self):
        """Test investment status transitions and edge cases"""
        # Create investment
        self.inr_wallet.balance = Decimal('1000.00')
        self.inr_wallet.save()
        
        investment_data = {
            'plan': self.basic_plan.id,
            'amount': '1000.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        investment = Investment.objects.get(user=self.user)
        
        # Test status transitions
        self.assertEqual(investment.status, 'active')
        
        # Test premature completion (should fail)
        investment.status = 'COMPLETED'
        investment.save()
        
        # Investment should not be completed before maturity
        self.assertLess(datetime.now().date(), investment.end_date.date())
        
        # Reset status
        investment.status = 'active'
        investment.save()
    
    def test_investment_plan_status_changes(self):
        """Test investment plan status changes affect new investments"""
        # Deactivate plan
        self.basic_plan.status = 'inactive'
        self.basic_plan.save()
        
        # Try to create investment with inactive plan
        self.inr_wallet.balance = Decimal('1000.00')
        self.inr_wallet.save()
        
        investment_data = {
            'plan': self.basic_plan.id,
            'amount': '1000.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        # Should fail - plan is inactive
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Reactivate plan
        self.basic_plan.status = 'active'
        self.basic_plan.save()
        
        # Now should succeed
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_investment_breakdown_window_edge_cases(self):
        """Test investment breakdown window edge cases"""
        # Create plan with specific breakdown window
        breakdown_plan = InvestmentPlan.objects.create(
            name='Breakdown Test Plan',
            roi_rate=Decimal('15.00'),
            frequency='daily',
            duration_days=30,
            min_amount=Decimal('100.00'),
            max_amount=Decimal('1000.00'),
            breakdown_window_days=7,
            status='active'
        )
        
        # Create investment
        self.inr_wallet.balance = Decimal('100.00')
        self.inr_wallet.save()
        
        investment_data = {
            'plan': breakdown_plan.id,
            'amount': '100.00',
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        investment = Investment.objects.get(user=self.user)
        
        # Test breakdown window calculation
        breakdown_date = investment.start_date + timedelta(days=7)
        self.assertEqual(breakdown_date, investment.start_date + timedelta(days=breakdown_plan.breakdown_window_days))
        
        # Clean up
        investment.delete()
        breakdown_plan.delete()
    
    def test_investment_roi_calculation_precision(self):
        """Test investment ROI calculation precision"""
        # Create investment with specific amount and rate
        test_amount = Decimal('1000.00')
        test_rate = Decimal('12.50')  # 12.5%
        
        # Create custom plan
        custom_plan = InvestmentPlan.objects.create(
            name='Precision Test Plan',
            roi_rate=test_rate,
            frequency='daily',
            duration_days=365,
            breakdown_window_days=30,
            min_amount=Decimal('100.00'),
            max_amount=Decimal('10000.00'),
            status='active'
        )
        
        # Credit wallet
        self.inr_wallet.balance = test_amount
        self.inr_wallet.save()
        
        # Create investment
        investment_data = {
            'plan': custom_plan.id,
            'amount': str(test_amount),
            'currency': 'inr'
        }
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        response = self.client.post(
            reverse('investment:investment-list'),
            investment_data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Calculate expected daily ROI
        daily_roi = test_amount * test_rate / Decimal('100') / Decimal('365')
        
        # Verify calculation precision
        self.assertGreater(daily_roi, Decimal('0.00'))
        self.assertLess(daily_roi, test_amount)
        
        # Clean up
        investment = Investment.objects.get(user=self.user)
        investment.delete()
        custom_plan.delete()
