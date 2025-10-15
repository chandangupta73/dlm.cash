from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
import uuid

from .models import InvestmentPlan, Investment, BreakdownRequest
from app.wallet.models import INRWallet, USDTWallet, WalletTransaction

User = get_user_model()


class InvestmentPlanModelTest(TestCase):
    """Test cases for InvestmentPlan model."""
    
    def setUp(self):
        """Set up test data."""
        self.plan = InvestmentPlan.objects.create(
            name="Test Daily Plan",
            description="A test daily investment plan",
            min_amount=Decimal('100.00'),
            max_amount=Decimal('10000.00'),
            roi_rate=Decimal('2.50'),
            frequency='daily',
            duration_days=30,
            breakdown_window_days=10
        )
    
    def test_investment_plan_creation(self):
        """Test investment plan creation."""
        self.assertEqual(self.plan.name, "Test Daily Plan")
        self.assertEqual(self.plan.roi_rate, Decimal('2.50'))
        self.assertEqual(self.plan.frequency, 'daily')
        self.assertEqual(self.plan.duration_days, 30)
        self.assertEqual(self.plan.breakdown_window_days, 10)
        self.assertTrue(self.plan.is_active)
        self.assertEqual(self.plan.status, 'active')
    
    def test_roi_per_cycle_calculation(self):
        """Test ROI per cycle calculation."""
        # Daily: 2.5% / 1 = 2.5%
        self.assertEqual(self.plan.get_roi_per_cycle(), Decimal('0.025'))
        
        # Weekly: 2.5% / 7 ≈ 0.357%
        weekly_plan = InvestmentPlan.objects.create(
            name="Test Weekly Plan",
            min_amount=Decimal('100.00'),
            max_amount=Decimal('10000.00'),
            roi_rate=Decimal('2.50'),
            frequency='weekly',
            duration_days=30,
            breakdown_window_days=10
        )
        self.assertAlmostEqual(
            weekly_plan.get_roi_per_cycle(), 
            Decimal('0.025') / 7, 
            places=6
        )
        
        # Monthly: 2.5% / 30 ≈ 0.083%
        monthly_plan = InvestmentPlan.objects.create(
            name="Test Monthly Plan",
            min_amount=Decimal('100.00'),
            max_amount=Decimal('10000.00'),
            roi_rate=Decimal('2.50'),
            frequency='monthly',
            duration_days=30,
            breakdown_window_days=10
        )
        self.assertAlmostEqual(
            monthly_plan.get_roi_per_cycle(), 
            Decimal('0.025') / 30, 
            places=6
        )
    
    def test_total_cycles_calculation(self):
        """Test total cycles calculation."""
        # Daily: 30 days = 30 cycles
        self.assertEqual(self.plan.get_total_cycles(), 30)
        
        # Weekly: 30 days = 4 cycles (30 // 7)
        weekly_plan = InvestmentPlan.objects.create(
            name="Test Weekly Plan",
            min_amount=Decimal('100.00'),
            max_amount=Decimal('10000.00'),
            roi_rate=Decimal('2.50'),
            frequency='weekly',
            duration_days=30,
            breakdown_window_days=10
        )
        self.assertEqual(weekly_plan.get_total_cycles(), 4)
    
    def test_plan_validation(self):
        """Test plan validation."""
        # Test that max_amount must be greater than min_amount
        # This should be handled by the model's clean method or validation
        # For now, we'll test that the model allows valid ranges
        valid_plan = InvestmentPlan.objects.create(
            name="Valid Plan",
            min_amount=Decimal('100.00'),
            max_amount=Decimal('1000.00'),
            roi_rate=Decimal('2.50'),
            frequency='daily',
            duration_days=30,
            breakdown_window_days=10
        )
        self.assertIsNotNone(valid_plan.id)


class InvestmentModelTest(TestCase):
    """Test cases for Investment model."""
    
    def setUp(self):
        """Set up test data."""
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create investment plan
        self.plan = InvestmentPlan.objects.create(
            name="Test Plan",
            min_amount=Decimal('100.00'),
            max_amount=Decimal('10000.00'),
            roi_rate=Decimal('2.00'),
            frequency='daily',
            duration_days=30,
            breakdown_window_days=10
        )
        
        # Create wallets only if they don't exist
        self.inr_wallet, created = INRWallet.objects.get_or_create(
            user=self.user,
            defaults={'balance': Decimal('10000.00')}
        )
        if not created:
            self.inr_wallet.balance = Decimal('10000.00')
            self.inr_wallet.save()
            
        self.usdt_wallet, created = USDTWallet.objects.get_or_create(
            user=self.user,
            defaults={'balance': Decimal('1000.00')}
        )
        if not created:
            self.usdt_wallet.balance = Decimal('1000.00')
            self.usdt_wallet.save()
    
    def test_investment_creation(self):
        """Test investment creation."""
        investment = Investment.objects.create(
            user=self.user,
            plan=self.plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=timezone.now()
        )
        
        self.assertEqual(investment.user, self.user)
        self.assertEqual(investment.plan, self.plan)
        self.assertEqual(investment.amount, Decimal('1000.00'))
        self.assertEqual(investment.currency, 'INR')
        self.assertEqual(investment.status, 'active')
        self.assertIsNotNone(investment.end_date)
        self.assertIsNotNone(investment.next_roi_date)
    
    def test_breakdown_calculation(self):
        """Test breakdown amount calculation."""
        investment = Investment.objects.create(
            user=self.user,
            plan=self.plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=timezone.now()
        )
        
        # Test breakdown without ROI
        breakdown_amount = investment.get_breakdown_amount()
        expected_amount = Decimal('1000.00') * Decimal('0.8')  # 80% of investment
        self.assertEqual(breakdown_amount, expected_amount)
        
        # Test breakdown with ROI
        investment.roi_accrued = Decimal('100.00')
        breakdown_amount = investment.get_breakdown_amount()
        expected_amount = (Decimal('1000.00') * Decimal('0.8')) - (Decimal('100.00') * Decimal('0.5'))
        self.assertEqual(breakdown_amount, expected_amount)
    
    def test_breakdown_eligibility(self):
        """Test breakdown eligibility."""
        investment = Investment.objects.create(
            user=self.user,
            plan=self.plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=timezone.now()
        )
        
        # Should be eligible within breakdown window
        self.assertTrue(investment.can_breakdown())
        
        # Test boundary condition - exactly on breakdown deadline
        from freezegun import freeze_time
        breakdown_deadline = investment.start_date + timedelta(days=self.plan.breakdown_window_days)
        with freeze_time(breakdown_deadline):
            self.assertTrue(investment.can_breakdown())
    
    def test_roi_crediting(self):
        """Test ROI crediting."""
        investment = Investment.objects.create(
            user=self.user,
            plan=self.plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=timezone.now()
        )
        
        initial_roi = investment.roi_accrued
        roi_amount = Decimal('20.00')
        
        investment.credit_roi(roi_amount)
        
        self.assertEqual(investment.roi_accrued, initial_roi + roi_amount)
        self.assertIsNotNone(investment.last_roi_credit)
        self.assertIsNotNone(investment.next_roi_date)
    
    def test_breakdown_request(self):
        """Test breakdown request."""
        investment = Investment.objects.create(
            user=self.user,
            plan=self.plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=timezone.now()
        )
        
        investment.request_breakdown()
        self.assertEqual(investment.status, 'breakdown_pending')
    
    def test_breakdown_approval(self):
        """Test breakdown approval."""
        investment = Investment.objects.create(
            user=self.user,
            plan=self.plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=timezone.now()
        )
        
        investment.request_breakdown()
        investment.approve_breakdown()
        
        self.assertEqual(investment.status, 'breakdown_approved')
        self.assertFalse(investment.is_active)
    
    def test_breakdown_rejection(self):
        """Test breakdown rejection."""
        investment = Investment.objects.create(
            user=self.user,
            plan=self.plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=timezone.now()
        )
        
        investment.request_breakdown()
        investment.reject_breakdown()
        
        self.assertEqual(investment.status, 'active')
        self.assertTrue(investment.is_active)


class BreakdownRequestModelTest(TestCase):
    """Test cases for BreakdownRequest model."""
    
    def setUp(self):
        """Set up test data."""
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        # Create investment plan
        self.plan = InvestmentPlan.objects.create(
            name="Test Plan 2",
            min_amount=Decimal('100.00'),
            max_amount=Decimal('10000.00'),
            roi_rate=Decimal('2.00'),
            frequency='daily',
            duration_days=30,
            breakdown_window_days=10
        )
        
        # Create investment
        self.investment = Investment.objects.create(
            user=self.user,
            plan=self.plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=timezone.now()
        )
        
        # Create wallets only if they don't exist
        self.inr_wallet, created = INRWallet.objects.get_or_create(
            user=self.user,
            defaults={'balance': Decimal('10000.00')}
        )
        if not created:
            self.inr_wallet.balance = Decimal('10000.00')
            self.inr_wallet.save()
            
        self.usdt_wallet, created = USDTWallet.objects.get_or_create(
            user=self.user,
            defaults={'balance': Decimal('1000.00')}
        )
        if not created:
            self.usdt_wallet.balance = Decimal('1000.00')
            self.usdt_wallet.save()
    
    def test_breakdown_request_creation(self):
        """Test breakdown request creation."""
        breakdown_request = BreakdownRequest.objects.create(
            user=self.user,
            investment=self.investment,
            requested_amount=Decimal('800.00'),
            final_amount=Decimal('750.00')
        )
        
        self.assertEqual(breakdown_request.user, self.user)
        self.assertEqual(breakdown_request.investment, self.investment)
        self.assertEqual(breakdown_request.status, 'pending')
    
    def test_breakdown_request_approval(self):
        """Test breakdown request approval."""
        breakdown_request = BreakdownRequest.objects.create(
            user=self.user,
            investment=self.investment,
            requested_amount=Decimal('800.00'),
            final_amount=Decimal('750.00')
        )
        
        # Set investment status to breakdown_pending first
        self.investment.status = 'breakdown_pending'
        self.investment.save()
        
        breakdown_request.approve(self.user)
        
        self.assertEqual(breakdown_request.status, 'approved')
        self.assertEqual(breakdown_request.processed_by, self.user)
        self.assertIsNotNone(breakdown_request.processed_at)
    
    def test_breakdown_request_rejection(self):
        """Test breakdown request rejection."""
        breakdown_request = BreakdownRequest.objects.create(
            user=self.user,
            investment=self.investment,
            requested_amount=Decimal('800.00'),
            final_amount=Decimal('750.00')
        )
        
        # Set investment status to breakdown_pending first
        self.investment.status = 'breakdown_pending'
        self.investment.save()
        
        breakdown_request.reject(self.user, "Test rejection")
        
        self.assertEqual(breakdown_request.status, 'rejected')
        self.assertEqual(breakdown_request.processed_by, self.user)
        self.assertIsNotNone(breakdown_request.processed_at)


class InvestmentIntegrationTest(TestCase):
    """Integration tests for investment system."""
    
    def setUp(self):
        """Set up test data."""
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser3',
            email='test3@example.com',
            password='testpass123'
        )
        
        # Create investment plan
        self.plan = InvestmentPlan.objects.create(
            name="Test Plan 3",
            min_amount=Decimal('100.00'),
            max_amount=Decimal('10000.00'),
            roi_rate=Decimal('2.00'),
            frequency='daily',
            duration_days=30,
            breakdown_window_days=10
        )
        
        # Create wallets only if they don't exist
        self.inr_wallet, created = INRWallet.objects.get_or_create(
            user=self.user,
            defaults={'balance': Decimal('10000.00')}
        )
        if not created:
            self.inr_wallet.balance = Decimal('10000.00')
            self.inr_wallet.save()
            
        self.usdt_wallet, created = USDTWallet.objects.get_or_create(
            user=self.user,
            defaults={'balance': Decimal('1000.00')}
        )
        if not created:
            self.usdt_wallet.balance = Decimal('1000.00')
            self.usdt_wallet.save()
    
    def test_complete_investment_flow(self):
        """Test complete investment flow from creation to breakdown."""
        # Create investment
        investment = Investment.objects.create(
            user=self.user,
            plan=self.plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=timezone.now()
        )
        
        # Credit ROI
        investment.credit_roi(Decimal('20.00'))
        self.assertEqual(investment.roi_accrued, Decimal('20.00'))
        
        # Request breakdown
        investment.request_breakdown()
        self.assertEqual(investment.status, 'breakdown_pending')
        
        # Create breakdown request
        breakdown_request = BreakdownRequest.objects.create(
            user=self.user,
            investment=investment,
            requested_amount=Decimal('800.00'),
            final_amount=Decimal('750.00')
        )
        
        # Approve breakdown
        breakdown_request.approve(self.user)
        self.assertEqual(breakdown_request.status, 'approved')
    
    def test_roi_calculation_accuracy(self):
        """Test ROI calculation accuracy over multiple cycles."""
        investment = Investment.objects.create(
            user=self.user,
            plan=self.plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=timezone.now()
        )
        
        # Credit ROI multiple times
        for i in range(5):
            investment.credit_roi(Decimal('20.00'))
        
        expected_roi = Decimal('100.00')  # 5 * 20
        self.assertEqual(investment.roi_accrued, expected_roi)


class InvestmentValidationTest(TestCase):
    """Test cases for investment validation."""
    
    def setUp(self):
        """Set up test data."""
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser4',
            email='test4@example.com',
            password='testpass123'
        )
        
        # Create investment plan
        self.plan = InvestmentPlan.objects.create(
            name="Test Plan 4",
            min_amount=Decimal('100.00'),
            max_amount=Decimal('10000.00'),
            roi_rate=Decimal('2.00'),
            frequency='daily',
            duration_days=30,
            breakdown_window_days=10
        )
        
        # Create wallets only if they don't exist
        self.inr_wallet, created = INRWallet.objects.get_or_create(
            user=self.user,
            defaults={'balance': Decimal('10000.00')}
        )
        if not created:
            self.inr_wallet.balance = Decimal('10000.00')
            self.inr_wallet.save()
            
        self.usdt_wallet, created = USDTWallet.objects.get_or_create(
            user=self.user,
            defaults={'balance': Decimal('1000.00')}
        )
        if not created:
            self.usdt_wallet.balance = Decimal('1000.00')
            self.usdt_wallet.save()
    
    def test_invalid_breakdown_requests(self):
        """Test invalid breakdown request scenarios."""
        investment = Investment.objects.create(
            user=self.user,
            plan=self.plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=timezone.now()
        )
        
        # Test breakdown outside window
        from freezegun import freeze_time
        outside_window = investment.start_date + timedelta(days=self.plan.breakdown_window_days + 1)
        with freeze_time(outside_window):
            self.assertFalse(investment.can_breakdown())
    
    def test_invalid_breakdown_approval(self):
        """Test invalid breakdown approval scenarios."""
        investment = Investment.objects.create(
            user=self.user,
            plan=self.plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=timezone.now()
        )
        
        # Test approving non-pending investment
        with self.assertRaises(ValueError):
            investment.approve_breakdown()
