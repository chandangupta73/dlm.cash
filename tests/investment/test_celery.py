import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time

from app.investment.models import InvestmentPlan, Investment, BreakdownRequest
from app.investment.tasks import (
    credit_roi_task,
    process_completed_investments,
    cleanup_old_breakdown_requests,
    investment_health_check
)
from app.wallet.models import WalletTransaction


@pytest.mark.celery
class TestCreditROITask:
    """Test the main ROI crediting Celery task"""

    def test_credit_daily_roi_success(self, daily_plan, kyc_user, frozen_time):
        """Test successful daily ROI crediting"""
        # Create investment
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            status='active'
        )
        
        # Mock time to next ROI date
        with frozen_time('2024-01-02 00:00:00'):
            result = credit_roi_task.delay()
            assert result.successful()
            
            # Refresh investment
            investment.refresh_from_db()
            
            # Check ROI was credited
            expected_roi = Decimal('1000') * Decimal('0.02')  # 2% daily
            assert investment.roi_accrued == expected_roi
            assert investment.last_roi_credit == timezone.now().date()
            assert investment.next_roi_date == timezone.now().date() + timedelta(days=1)
            
            # Check wallet balance increased
            wallet = kyc_user.inrwallet
            wallet.refresh_from_db()
            assert wallet.balance == Decimal('1020')  # 1000 + 20 ROI
            
            # Check transaction logged
            transaction = WalletTransaction.objects.filter(
                wallet=wallet,
                transaction_type='ROI',
                amount=expected_roi
            ).first()
            assert transaction is not None
            assert transaction.reference == f"ROI-{investment.id}"

    def test_credit_weekly_roi_success(self, weekly_plan, kyc_user, frozen_time):
        """Test successful weekly ROI crediting"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=weekly_plan,
            amount=Decimal('5000'),
            currency='USDT',
            start_date=timezone.now().date(),
            status='active'
        )
        
        # Mock time to next ROI date (7 days later)
        with frozen_time('2024-01-08 00:00:00'):
            result = credit_roi_task.delay()
            assert result.successful()
            
            investment.refresh_from_db()
            expected_roi = Decimal('5000') * Decimal('0.15')  # 15% weekly
            assert investment.roi_accrued == expected_roi
            assert investment.next_roi_date == timezone.now().date() + timedelta(days=7)
            
            # Check USDT wallet
            wallet = kyc_user.usdtwallet
            wallet.refresh_from_db()
            assert wallet.balance == Decimal('5750')  # 5000 + 750 ROI

    def test_credit_monthly_roi_success(self, monthly_plan, kyc_user, frozen_time):
        """Test successful monthly ROI crediting"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=monthly_plan,
            amount=Decimal('10000'),
            currency='INR',
            start_date=timezone.now().date(),
            status='active'
        )
        
        # Mock time to next ROI date (30 days later)
        with frozen_time('2024-02-01 00:00:00'):
            result = credit_roi_task.delay()
            assert result.successful()
            
            investment.refresh_from_db()
            expected_roi = Decimal('10000') * Decimal('0.60')  # 60% monthly
            assert investment.roi_accrued == expected_roi
            assert investment.next_roi_date == timezone.now().date() + timedelta(days=30)

    def test_roi_skipped_when_paused(self, daily_plan, kyc_user, frozen_time):
        """Test ROI is skipped when investment has breakdown request pending"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            status='active'
        )
        
        # Create breakdown request (pauses ROI)
        BreakdownRequest.objects.create(
            user=kyc_user,
            investment=investment,
            requested_amount=Decimal('1000'),
            final_amount=Decimal('800'),
            status='pending'
        )
        
        # Mock time to next ROI date
        with frozen_time('2024-01-02 00:00:00'):
            initial_roi = investment.roi_accrued
            initial_balance = kyc_user.inrwallet.balance
            
            result = credit_roi_task.delay()
            assert result.successful()
            
            # ROI should not be credited
            investment.refresh_from_db()
            assert investment.roi_accrued == initial_roi
            
            # Wallet balance should not change
            kyc_user.inrwallet.refresh_from_db()
            assert kyc_user.inrwallet.balance == initial_balance

    def test_roi_skipped_for_completed_investments(self, daily_plan, kyc_user, frozen_time):
        """Test ROI is skipped for completed investments"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            status='completed'
        )
        
        with frozen_time('2024-01-02 00:00:00'):
            initial_roi = investment.roi_accrued
            initial_balance = kyc_user.inrwallet.balance
            
            result = credit_roi_task.delay()
            assert result.successful()
            
            # ROI should not be credited
            investment.refresh_from_db()
            assert investment.roi_accrued == initial_roi
            
            # Wallet balance should not change
            kyc_user.inrwallet.refresh_from_db()
            assert kyc_user.inrwallet.balance == initial_balance

    def test_roi_skipped_before_start_date(self, daily_plan, kyc_user, frozen_time):
        """Test ROI is skipped before investment start date"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date() + timedelta(days=1),
            status='active'
        )
        
        with frozen_time('2024-01-01 00:00:00'):
            initial_roi = investment.roi_accrued
            initial_balance = kyc_user.inrwallet.balance
            
            result = credit_roi_task.delay()
            assert result.successful()
            
            # ROI should not be credited
            investment.refresh_from_db()
            assert investment.roi_accrued == initial_roi
            
            # Wallet balance should not change
            kyc_user.inrwallet.refresh_from_db()
            assert kyc_user.inrwallet.balance == initial_balance

    def test_multiple_roi_credits_catch_up(self, daily_plan, kyc_user, frozen_time):
        """Test multiple ROI credits when days are missed"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            status='active'
        )
        
        # Mock time to 3 days later (missed 2 ROI credits)
        with frozen_time('2024-01-04 00:00:00'):
            result = credit_roi_task.delay()
            assert result.successful()
            
            investment.refresh_from_db()
            # Should credit for 3 days: 1000 * 0.02 * 3 = 60
            expected_roi = Decimal('1000') * Decimal('0.02') * 3
            assert investment.roi_accrued == expected_roi
            assert investment.next_roi_date == timezone.now().date() + timedelta(days=1)
            
            # Check wallet balance
            wallet = kyc_user.inrwallet
            wallet.refresh_from_db()
            assert wallet.balance == Decimal('1060')  # 1000 + 60 ROI

    def test_roi_credit_with_decimal_precision(self, daily_plan, kyc_user, frozen_time):
        """Test ROI crediting handles decimal precision correctly"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000.50'),
            currency='INR',
            start_date=timezone.now().date(),
            status='active'
        )
        
        with frozen_time('2024-01-02 00:00:00'):
            result = credit_roi_task.delay()
            assert result.successful()
            
            investment.refresh_from_db()
            expected_roi = Decimal('1000.50') * Decimal('0.02')
            assert investment.roi_accrued == expected_roi
            
            # Check transaction amount matches exactly
            wallet = kyc_user.inrwallet
            transaction = WalletTransaction.objects.filter(
                wallet=wallet,
                transaction_type='ROI'
            ).first()
            assert transaction.amount == expected_roi

    @patch('app.investment.tasks.logger')
    def test_roi_credit_logging(self, mock_logger, daily_plan, kyc_user, frozen_time):
        """Test ROI crediting logs appropriate messages"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            status='active'
        )
        
        with frozen_time('2024-01-02 00:00:00'):
            credit_roi_task.delay()
            
            # Check logging calls
            mock_logger.info.assert_called()
            mock_logger.error.assert_not_called()

    def test_roi_credit_concurrent_investments(self, daily_plan, kyc_user, frozen_time):
        """Test ROI crediting handles multiple concurrent investments"""
        # Create multiple investments
        investments = []
        for i in range(3):
            investment = Investment.objects.create(
                user=kyc_user,
                plan=daily_plan,
                amount=Decimal('1000'),
                currency='INR',
                start_date=timezone.now().date(),
                status='active'
            )
            investments.append(investment)
        
        with frozen_time('2024-01-02 00:00:00'):
            result = credit_roi_task.delay()
            assert result.successful()
            
            # Check all investments got ROI
            for investment in investments:
                investment.refresh_from_db()
                expected_roi = Decimal('1000') * Decimal('0.02')
                assert investment.roi_accrued == expected_roi
            
            # Check total wallet balance
            wallet = kyc_user.inrwallet
            wallet.refresh_from_db()
            expected_total = Decimal('3000') + (Decimal('20') * 3)  # 3 investments + 3 ROI credits
            assert wallet.balance == expected_total


@pytest.mark.celery
class TestProcessCompletedInvestments:
    """Test the completed investments processing task"""

    def test_mark_completed_investments(self, daily_plan, kyc_user, frozen_time):
        """Test investments are marked as completed when end date is reached"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            status='active'
        )
        
        # Mock time to end date
        with frozen_time('2024-02-01 00:00:00'):
            result = process_completed_investments.delay()
            assert result.successful()
            
            investment.refresh_from_db()
            assert investment.status == 'completed'

    def test_skip_active_investments(self, daily_plan, kyc_user, frozen_time):
        """Test active investments are not marked as completed"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            status='active'
        )
        
        # Mock time before end date
        with frozen_time('2024-01-15 00:00:00'):
            result = process_completed_investments.delay()
            assert result.successful()
            
            investment.refresh_from_db()
            assert investment.status == 'active'

    def test_skip_breakdown_pending_investments(self, daily_plan, kyc_user, frozen_time):
        """Test breakdown pending investments are not marked as completed"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            status='breakdown_pending'
        )
        
        with frozen_time('2024-02-01 00:00:00'):
            result = process_completed_investments.delay()
            assert result.successful()
            
            investment.refresh_from_db()
            assert investment.status == 'breakdown_pending'

    def test_bulk_completion_processing(self, daily_plan, kyc_user, frozen_time):
        """Test multiple investments are processed in bulk"""
        # Create investments with different end dates
        investments = []
        for i in range(3):
            end_date = timezone.now().date() + timedelta(days=30 + i)
            investment = Investment.objects.create(
                user=kyc_user,
                plan=daily_plan,
                amount=Decimal('1000'),
                currency='INR',
                start_date=timezone.now().date(),
                end_date=end_date,
                status='active'
            )
            investments.append(investment)
        
        # Mock time to process first two
        with frozen_time('2024-02-01 00:00:00'):
            result = process_completed_investments.delay()
            assert result.successful()
            
            # First two should be completed
            investments[0].refresh_from_db()
            investments[1].refresh_from_db()
            investments[2].refresh_from_db()
            
            assert investments[0].status == 'completed'
            assert investments[1].status == 'completed'
            assert investments[2].status == 'active'


@pytest.mark.celery
class TestCleanupOldBreakdownRequests:
    """Test the cleanup task for old breakdown requests"""

    def test_cleanup_old_processed_requests(self, kyc_user, daily_plan, frozen_time):
        """Test old processed breakdown requests are cleaned up"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            status='active'
        )
        
        # Create old processed requests
        old_approved = BreakdownRequest.objects.create(
            user=kyc_user,
            investment=investment,
            requested_amount=Decimal('1000'),
            final_amount=Decimal('800'),
            status='approved',
            created_at=timezone.now() - timedelta(days=31)
        )
        
        old_rejected = BreakdownRequest.objects.create(
            user=kyc_user,
            investment=investment,
            requested_amount=Decimal('1000'),
            final_amount=Decimal('800'),
            status='rejected',
            created_at=timezone.now() - timedelta(days=31)
        )
        
        # Create recent and pending requests (should not be cleaned)
        recent_approved = BreakdownRequest.objects.create(
            user=kyc_user,
            investment=investment,
            requested_amount=Decimal('1000'),
            final_amount=Decimal('800'),
            status='approved',
            created_at=timezone.now() - timedelta(days=15)
        )
        
        pending_request = BreakdownRequest.objects.create(
            user=kyc_user,
            investment=investment,
            requested_amount=Decimal('1000'),
            final_amount=Decimal('800'),
            status='pending'
        )
        
        with frozen_time('2024-02-01 00:00:00'):
            result = cleanup_old_breakdown_requests.delay()
            assert result.successful()
            
            # Old processed requests should be deleted
            assert not BreakdownRequest.objects.filter(id=old_approved.id).exists()
            assert not BreakdownRequest.objects.filter(id=old_rejected.id).exists()
            
            # Recent and pending requests should remain
            assert BreakdownRequest.objects.filter(id=recent_approved.id).exists()
            assert BreakdownRequest.objects.filter(id=pending_request.id).exists()

    def test_cleanup_no_old_requests(self, kyc_user, daily_plan):
        """Test cleanup when no old requests exist"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            status='active'
        )
        
        # Create only recent requests
        BreakdownRequest.objects.create(
            user=kyc_user,
            investment=investment,
            requested_amount=Decimal('1000'),
            final_amount=Decimal('800'),
            status='approved',
            created_at=timezone.now() - timedelta(days=15)
        )
        
        initial_count = BreakdownRequest.objects.count()
        
        result = cleanup_old_breakdown_requests.delay()
        assert result.successful()
        
        # Count should remain the same
        assert BreakdownRequest.objects.count() == initial_count


@pytest.mark.celery
class TestInvestmentHealthCheck:
    """Test the investment system health check task"""

    def test_health_check_success(self, kyc_user, daily_plan):
        """Test health check passes when system is healthy"""
        # Create a healthy investment
        Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            status='active'
        )
        
        result = investment_health_check.delay()
        assert result.successful()
        
        # Check the result contains expected data
        health_data = result.result
        assert 'total_investments' in health_data
        assert 'active_investments' in health_data
        assert 'breakdown_requests' in health_data
        assert 'system_status' in health_data
        assert health_data['system_status'] == 'healthy'

    def test_health_check_with_breakdown_requests(self, kyc_user, daily_plan):
        """Test health check includes breakdown request statistics"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            status='active'
        )
        
        # Create breakdown requests
        BreakdownRequest.objects.create(
            user=kyc_user,
            investment=investment,
            requested_amount=Decimal('1000'),
            final_amount=Decimal('800'),
            status='pending'
        )
        
        BreakdownRequest.objects.create(
            user=kyc_user,
            investment=investment,
            requested_amount=Decimal('1000'),
            final_amount=Decimal('800'),
            status='approved'
        )
        
        result = investment_health_check.delay()
        assert result.successful()
        
        health_data = result.result
        assert health_data['breakdown_requests']['pending'] == 1
        assert health_data['breakdown_requests']['approved'] == 1
        assert health_data['breakdown_requests']['rejected'] == 0

    def test_health_check_empty_system(self):
        """Test health check when no investments exist"""
        result = investment_health_check.delay()
        assert result.successful()
        
        health_data = result.result
        assert health_data['total_investments'] == 0
        assert health_data['active_investments'] == 0
        assert health_data['system_status'] == 'healthy'

    @patch('app.investment.tasks.logger')
    def test_health_check_logging(self, mock_logger):
        """Test health check logs appropriate messages"""
        result = investment_health_check.delay()
        assert result.successful()
        
        # Check logging calls
        mock_logger.info.assert_called()
        mock_logger.error.assert_not_called()


@pytest.mark.celery
class TestCeleryTaskErrorHandling:
    """Test error handling in Celery tasks"""

    @patch('app.investment.tasks.logger')
    def test_roi_task_database_error(self, mock_logger, daily_plan, kyc_user, frozen_time):
        """Test ROI task handles database errors gracefully"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            status='active'
        )
        
        # Mock database error
        with patch('app.investment.models.Investment.objects.select_for_update') as mock_select:
            mock_select.side_effect = Exception("Database connection error")
            
            with frozen_time('2024-01-02 00:00:00'):
                result = credit_roi_task.delay()
                
                # Task should fail gracefully
                assert result.failed()
                
                # Error should be logged
                mock_logger.error.assert_called()

    @patch('app.investment.tasks.logger')
    def test_health_check_task_error(self, mock_logger):
        """Test health check task handles errors gracefully"""
        # Mock error in health check
        with patch('app.investment.models.Investment.objects.count') as mock_count:
            mock_count.side_effect = Exception("Unexpected error")
            
            result = investment_health_check.delay()
            
            # Task should fail gracefully
            assert result.failed()
            
            # Error should be logged
            mock_logger.error.assert_called()

    def test_task_retry_on_failure(self, daily_plan, kyc_user, frozen_time):
        """Test tasks can be retried on failure"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            status='active'
        )
        
        # Mock temporary failure then success
        with patch('app.investment.models.Investment.objects.select_for_update') as mock_select:
            mock_select.side_effect = [Exception("Temporary error"), MagicMock()]
            
            with frozen_time('2024-01-02 00:00:00'):
                # First attempt should fail
                result1 = credit_roi_task.delay()
                assert result1.failed()
                
                # Second attempt should succeed
                result2 = credit_roi_task.delay()
                assert result2.successful()


@pytest.mark.celery
class TestCeleryTaskPerformance:
    """Test performance aspects of Celery tasks"""

    def test_roi_task_bulk_processing(self, daily_plan, kyc_user, frozen_time):
        """Test ROI task efficiently processes multiple investments"""
        # Create many investments
        investments = []
        for i in range(100):
            investment = Investment.objects.create(
                user=kyc_user,
                plan=daily_plan,
                amount=Decimal('1000'),
                currency='INR',
                start_date=timezone.now().date(),
                status='active'
            )
            investments.append(investment)
        
        with frozen_time('2024-01-02 00:00:00'):
            import time
            start_time = time.time()
            
            result = credit_roi_task.delay()
            assert result.successful()
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Should process within reasonable time (adjust threshold as needed)
            assert processing_time < 5.0  # 5 seconds max
            
            # Verify all investments got ROI
            for investment in investments:
                investment.refresh_from_db()
                assert investment.roi_accrued > 0

    def test_cleanup_task_efficiency(self, kyc_user, daily_plan, frozen_time):
        """Test cleanup task efficiently removes old records"""
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            status='active'
        )
        
        # Create many old requests
        old_requests = []
        for i in range(1000):
            request = BreakdownRequest.objects.create(
                user=kyc_user,
                investment=investment,
                requested_amount=Decimal('1000'),
                final_amount=Decimal('800'),
                status='approved',
                created_at=timezone.now() - timedelta(days=31)
            )
            old_requests.append(request)
        
        initial_count = BreakdownRequest.objects.count()
        
        with frozen_time('2024-02-01 00:00:00'):
            import time
            start_time = time.time()
            
            result = cleanup_old_breakdown_requests.delay()
            assert result.successful()
            
            end_time = time.time()
            cleanup_time = end_time - start_time
            
            # Should clean up within reasonable time
            assert cleanup_time < 3.0  # 3 seconds max
            
            # Verify old requests were removed
            final_count = BreakdownRequest.objects.count()
            assert final_count < initial_count
            assert final_count == 0  # All old requests should be gone
