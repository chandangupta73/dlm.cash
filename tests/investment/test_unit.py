import pytest
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from freezegun import freeze_time

from app.investment.models import InvestmentPlan, Investment, BreakdownRequest
from app.wallet.models import INRWallet, USDTWallet
from app.users.models import KYC


@pytest.mark.unit
class TestInvestmentPlan:
    """Unit tests for InvestmentPlan model"""
    
    def test_investment_plan_creation(self, daily_plan):
        """Test basic investment plan creation"""
        assert daily_plan.name == "Daily Growth Plan"
        assert daily_plan.min_amount == Decimal('100.00')
        assert daily_plan.max_amount == Decimal('10000.00')
        assert daily_plan.roi_rate == Decimal('0.5')
        assert daily_plan.frequency == 'DAILY'
        assert daily_plan.duration_days == 30
        assert daily_plan.breakdown_window_days == 10
    
    def test_roi_per_cycle_calculation(self, daily_plan, weekly_plan, monthly_plan):
        """Test ROI per cycle calculations for different frequencies"""
        # Daily: 0.5% per day
        assert daily_plan.get_roi_per_cycle() == Decimal('0.5')
        
        # Weekly: 3% per week
        assert weekly_plan.get_roi_per_cycle() == Decimal('3.0')
        
        # Monthly: 12% per month
        assert monthly_plan.get_roi_per_cycle() == Decimal('12.0')
    
    def test_total_cycles_calculation(self, daily_plan, weekly_plan, monthly_plan):
        """Test total cycles calculation based on duration and frequency"""
        # Daily: 30 days = 30 cycles
        assert daily_plan.get_total_cycles() == 30
        
        # Weekly: 90 days = 12.86 weeks ≈ 13 cycles
        assert weekly_plan.get_total_cycles() == 13
        
        # Monthly: 365 days = 12.17 months ≈ 12 cycles
        assert monthly_plan.get_total_cycles() == 12
    
    def test_plan_validation_min_max_amounts(self):
        """Test validation of min/max amounts"""
        # Valid plan
        plan = InvestmentPlan(
            name="Test Plan",
            min_amount=Decimal('100.00'),
            max_amount=Decimal('1000.00'),
            roi_rate=Decimal('1.0'),
            frequency='DAILY',
            duration_days=30,
            breakdown_window_days=10
        )
        plan.full_clean()  # Should not raise validation error
        
        # Invalid: min > max
        plan.min_amount = Decimal('1000.00')
        plan.max_amount = Decimal('100.00')
        with pytest.raises(ValidationError):
            plan.full_clean()
    
    def test_plan_validation_roi_rate(self):
        """Test ROI rate validation"""
        # Valid ROI rate
        plan = InvestmentPlan(
            name="Test Plan",
            min_amount=Decimal('100.00'),
            max_amount=Decimal('1000.00'),
            roi_rate=Decimal('5.0'),
            frequency='DAILY',
            duration_days=30,
            breakdown_window_days=10
        )
        plan.full_clean()
        
        # Invalid: negative ROI rate
        plan.roi_rate = Decimal('-1.0')
        with pytest.raises(ValidationError):
            plan.full_clean()
        
        # Invalid: extremely high ROI rate (>100%)
        plan.roi_rate = Decimal('150.0')
        with pytest.raises(ValidationError):
            plan.full_clean()
    
    def test_plan_validation_duration(self):
        """Test duration validation"""
        # Valid duration
        plan = InvestmentPlan(
            name="Test Plan",
            min_amount=Decimal('100.00'),
            max_amount=Decimal('1000.00'),
            roi_rate=Decimal('1.0'),
            frequency='DAILY',
            duration_days=30,
            breakdown_window_days=10
        )
        plan.full_clean()
        
        # Invalid: duration too short
        plan.duration_days = 0
        with pytest.raises(ValidationError):
            plan.full_clean()
        
        # Invalid: breakdown window > duration
        plan.duration_days = 30
        plan.breakdown_window_days = 35
        with pytest.raises(ValidationError):
            plan.full_clean()


@pytest.mark.unit
class TestInvestment:
    """Unit tests for Investment model"""
    
    def test_investment_creation(self, kyc_user, daily_plan):
        """Test basic investment creation"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=start_date,
            end_date=end_date,
            next_roi_date=next_roi_date
        )
        
        assert investment.user == kyc_user
        assert investment.plan == daily_plan
        assert investment.amount == Decimal('1000.00')
        assert investment.currency == 'INR'
        assert investment.status == 'ACTIVE'
        assert investment.roi_accrued == Decimal('0.00')
    
    def test_investment_roi_calculation(self, kyc_user, daily_plan):
        """Test ROI calculation for different scenarios"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=start_date,
            end_date=end_date,
            next_roi_date=next_roi_date
        )
        
        # Calculate ROI for one cycle (daily)
        roi_amount = investment.calculate_roi_amount()
        expected_roi = Decimal('1000.00') * Decimal('0.005')  # 0.5%
        assert roi_amount == expected_roi
        
        # Calculate ROI for multiple cycles
        roi_amount_5_days = investment.calculate_roi_amount(cycles=5)
        expected_roi_5_days = Decimal('1000.00') * Decimal('0.005') * 5
        assert roi_amount_5_days == expected_roi_5_days
    
    def test_investment_breakdown_eligibility(self, kyc_user, daily_plan):
        """Test breakdown eligibility based on time window"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=start_date,
            end_date=end_date,
            next_roi_date=next_roi_date
        )
        
        # Within breakdown window (10 days)
        with freeze_time(start_date + timedelta(days=5)):
            assert investment.can_breakdown() is True
        
        # Outside breakdown window (15 days)
        with freeze_time(start_date + timedelta(days=15)):
            assert investment.can_breakdown() is False
        
        # On boundary day (10 days)
        with freeze_time(start_date + timedelta(days=10)):
            assert investment.can_breakdown() is True
    
    def test_investment_breakdown_amount_calculation(self, kyc_user, daily_plan):
        """Test breakdown amount calculation with ROI deductions"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=start_date,
            end_date=end_date,
            next_roi_date=next_roi_date
        )
        
        # No ROI received yet
        breakdown_amount = investment.get_breakdown_amount()
        expected_amount = Decimal('1000.00') * Decimal('0.8')  # 80% of investment
        assert breakdown_amount == expected_amount
        
        # With ROI received
        investment.roi_accrued = Decimal('50.00')
        breakdown_amount = investment.get_breakdown_amount()
        roi_deduction = Decimal('50.00') * Decimal('0.5')  # 50% of ROI
        expected_amount = (Decimal('1000.00') * Decimal('0.8')) - roi_deduction
        assert breakdown_amount == expected_amount
        
        # Edge case: ROI large enough to risk negative payout
        investment.roi_accrued = Decimal('2000.00')  # More than 80% of investment
        breakdown_amount = investment.get_breakdown_amount()
        # Should not go below 0
        assert breakdown_amount >= Decimal('0.00')
    
    def test_investment_status_transitions(self, kyc_user, daily_plan):
        """Test investment status transitions"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=start_date,
            end_date=end_date,
            next_roi_date=next_roi_date
        )
        
        # Initial status
        assert investment.status == 'ACTIVE'
        
        # Request breakdown
        investment.status = 'BREAKDOWN_PENDING'
        investment.save()
        assert investment.status == 'BREAKDOWN_PENDING'
        
        # Complete investment
        investment.status = 'COMPLETED'
        investment.save()
        assert investment.status == 'COMPLETED'
    
    def test_investment_validation_amount_limits(self, kyc_user, daily_plan):
        """Test investment amount validation against plan limits"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        # Amount below minimum
        with pytest.raises(ValidationError):
            investment = Investment(
                user=kyc_user,
                plan=daily_plan,
                amount=Decimal('50.00'),  # Below min_amount (100.00)
                currency='INR',
                start_date=start_date,
                end_date=end_date,
                next_roi_date=next_roi_date
            )
            investment.full_clean()
        
        # Amount above maximum
        with pytest.raises(ValidationError):
            investment = Investment(
                user=kyc_user,
                plan=daily_plan,
                amount=Decimal('15000.00'),  # Above max_amount (10000.00)
                currency='INR',
                start_date=start_date,
                end_date=end_date,
                next_roi_date=next_roi_date
            )
            investment.full_clean()
        
        # Valid amount
        investment = Investment(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000.00'),  # Within limits
            currency='INR',
            start_date=start_date,
            end_date=end_date,
            next_roi_date=next_roi_date
        )
        investment.full_clean()  # Should not raise error


@pytest.mark.unit
class TestBreakdownRequest:
    """Unit tests for BreakdownRequest model"""
    
    def test_breakdown_request_creation(self, kyc_user, active_investment):
        """Test basic breakdown request creation"""
        breakdown = BreakdownRequest.objects.create(
            user=kyc_user,
            investment=active_investment,
            requested_amount=active_investment.amount,
            final_amount=active_investment.get_breakdown_amount()
        )
        
        assert breakdown.user == kyc_user
        assert breakdown.investment == active_investment
        assert breakdown.status == 'PENDING'
        assert breakdown.requested_amount == active_investment.amount
    
    def test_breakdown_request_status_transitions(self, kyc_user, active_investment):
        """Test breakdown request status transitions"""
        breakdown = BreakdownRequest.objects.create(
            user=kyc_user,
            investment=active_investment,
            requested_amount=active_investment.amount,
            final_amount=active_investment.get_breakdown_amount()
        )
        
        # Initial status
        assert breakdown.status == 'PENDING'
        
        # Approve breakdown
        breakdown.status = 'APPROVED'
        breakdown.save()
        assert breakdown.status == 'APPROVED'
        
        # Reject breakdown
        breakdown.status = 'REJECTED'
        breakdown.save()
        assert breakdown.status == 'REJECTED'
    
    def test_breakdown_request_validation(self, kyc_user, active_investment):
        """Test breakdown request validation"""
        # Valid breakdown request
        breakdown = BreakdownRequest(
            user=kyc_user,
            investment=active_investment,
            requested_amount=active_investment.amount,
            final_amount=active_investment.get_breakdown_amount()
        )
        breakdown.full_clean()
        
        # Invalid: requested amount > investment amount
        breakdown.requested_amount = active_investment.amount + Decimal('100.00')
        with pytest.raises(ValidationError):
            breakdown.full_clean()
        
        # Invalid: negative amounts
        breakdown.requested_amount = active_investment.amount
        breakdown.final_amount = Decimal('-100.00')
        with pytest.raises(ValidationError):
            breakdown.full_clean()
    
    def test_breakdown_request_final_amount_calculation(self, kyc_user, active_investment):
        """Test final amount calculation for breakdown requests"""
        # Set some ROI accrued
        active_investment.roi_accrued = Decimal('100.00')
        active_investment.save()
        
        breakdown = BreakdownRequest.objects.create(
            user=kyc_user,
            investment=active_investment,
            requested_amount=active_investment.amount,
            final_amount=active_investment.get_breakdown_amount()
        )
        
        # Verify final amount calculation
        expected_final_amount = (active_investment.amount * Decimal('0.8')) - (active_investment.roi_accrued * Decimal('0.5'))
        assert breakdown.final_amount == expected_final_amount


@pytest.mark.unit
class TestInvestmentEdgeCases:
    """Unit tests for edge cases and boundary conditions"""
    
    def test_roi_calculation_precision(self, kyc_user, daily_plan):
        """Test ROI calculation precision with decimal arithmetic"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        # Use very small amounts to test precision
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('0.01'),  # 1 cent
            currency='INR',
            start_date=start_date,
            end_date=end_date,
            next_roi_date=next_roi_date
        )
        
        roi_amount = investment.calculate_roi_amount()
        expected_roi = Decimal('0.01') * Decimal('0.005')  # 0.5%
        assert roi_amount == expected_roi
        assert roi_amount > Decimal('0.00')  # Should be positive
    
    def test_breakdown_on_boundary_days(self, kyc_user, daily_plan):
        """Test breakdown eligibility on exact boundary days"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=start_date,
            end_date=end_date,
            next_roi_date=next_roi_date
        )
        
        # Test breakdown window boundary (10 days)
        breakdown_window_end = start_date + timedelta(days=daily_plan.breakdown_window_days)
        
        # Just before boundary
        with freeze_time(breakdown_window_end - timedelta(seconds=1)):
            assert investment.can_breakdown() is True
        
        # Exactly on boundary
        with freeze_time(breakdown_window_end):
            assert investment.can_breakdown() is True
        
        # Just after boundary
        with freeze_time(breakdown_window_end + timedelta(seconds=1)):
            assert investment.can_breakdown() is False
    
    def test_large_roi_breakdown_scenario(self, kyc_user, daily_plan):
        """Test breakdown when ROI is very large relative to investment"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=start_date,
            end_date=end_date,
            next_roi_date=next_roi_date
        )
        
        # Set ROI larger than 80% of investment
        investment.roi_accrued = Decimal('900.00')  # 90% of investment
        
        breakdown_amount = investment.get_breakdown_amount()
        # Should not go below 0
        assert breakdown_amount >= Decimal('0.00')
        
        # Verify calculation
        base_amount = Decimal('1000.00') * Decimal('0.8')  # 800
        roi_deduction = Decimal('900.00') * Decimal('0.5')  # 450
        expected_amount = base_amount - roi_deduction  # 800 - 450 = 350
        assert breakdown_amount == expected_amount
    
    def test_zero_amount_investment(self, kyc_user, daily_plan):
        """Test edge case with zero amount investment"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        # This should raise validation error
        with pytest.raises(ValidationError):
            investment = Investment(
                user=kyc_user,
                plan=daily_plan,
                amount=Decimal('0.00'),
                currency='INR',
                start_date=start_date,
                end_date=end_date,
                next_roi_date=next_roi_date
            )
            investment.full_clean()
    
    def test_currency_validation(self, kyc_user, daily_plan):
        """Test currency validation for investments"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        # Valid currencies
        valid_currencies = ['INR', 'USDT']
        for currency in valid_currencies:
            investment = Investment(
                user=kyc_user,
                plan=daily_plan,
                amount=Decimal('1000.00'),
                currency=currency,
                start_date=start_date,
                end_date=end_date,
                next_roi_date=next_roi_date
            )
            investment.full_clean()
        
        # Invalid currency
        with pytest.raises(ValidationError):
            investment = Investment(
                user=kyc_user,
                plan=daily_plan,
                amount=Decimal('1000.00'),
                currency='INVALID',
                start_date=start_date,
                end_date=end_date,
                next_roi_date=next_roi_date
            )
            investment.full_clean()
