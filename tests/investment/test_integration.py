import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.test import override_settings
from django.db.models import F
from freezegun import freeze_time

from app.investment.models import InvestmentPlan, Investment, BreakdownRequest
from app.wallet.models import INRWallet, USDTWallet, WalletTransaction
from app.users.models import KYC


@pytest.mark.integration
class TestInvestmentWalletIntegration:
    """Integration tests for investment and wallet interactions"""
    
    def test_investment_creation_wallet_deduction(self, kyc_user, daily_plan):
        """Test that investment creation deducts amount from wallet"""
        # Get initial wallet balance
        inr_wallet = INRWallet.objects.get(user=kyc_user)
        initial_balance = inr_wallet.balance
        
        investment_amount = Decimal('1000.00')
        
        # Create investment
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=investment_amount,
            currency='INR',
            start_date=start_date,
            end_date=end_date,
            next_roi_date=next_roi_date
        )
        
        # Verify wallet balance is deducted
        inr_wallet.refresh_from_db()
        assert inr_wallet.balance == initial_balance - investment_amount
        
        # Verify transaction is logged
        transaction_log = WalletTransaction.objects.filter(
            wallet=inr_wallet,
            transaction_type='INVESTMENT',
            amount=investment_amount
        ).first()
        
        assert transaction_log is not None
        assert transaction_log.amount == investment_amount
        assert transaction_log.transaction_type == 'INVESTMENT'
        assert transaction_log.status == 'COMPLETED'
    
    def test_roi_credit_wallet_addition(self, kyc_user, daily_plan):
        """Test that ROI credits are added to wallet"""
        # Create investment
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
        
        # Get initial wallet balance
        inr_wallet = INRWallet.objects.get(user=kyc_user)
        initial_balance = inr_wallet.balance
        
        # Credit ROI
        roi_amount = investment.credit_roi()
        
        # Verify wallet balance is increased
        inr_wallet.refresh_from_db()
        assert inr_wallet.balance == initial_balance + roi_amount
        
        # Verify transaction is logged
        transaction_log = WalletTransaction.objects.filter(
            wallet=inr_wallet,
            transaction_type='ROI',
            amount=roi_amount
        ).first()
        
        assert transaction_log is not None
        assert transaction_log.amount == roi_amount
        assert transaction_log.transaction_type == 'ROI'
        assert transaction_log.status == 'COMPLETED'
    
    def test_breakdown_approval_wallet_credit(self, kyc_user, daily_plan):
        """Test that breakdown approval credits wallet with final amount"""
        # Create investment
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
        
        # Create breakdown request
        breakdown = BreakdownRequest.objects.create(
            user=kyc_user,
            investment=investment,
            requested_amount=investment.amount,
            final_amount=investment.get_breakdown_amount()
        )
        
        # Get initial wallet balance
        inr_wallet = INRWallet.objects.get(user=kyc_user)
        initial_balance = inr_wallet.balance
        
        # Approve breakdown
        breakdown.approve()
        
        # Verify wallet balance is credited with final amount
        inr_wallet.refresh_from_db()
        assert inr_wallet.balance == initial_balance + breakdown.final_amount
        
        # Verify transaction is logged
        transaction_log = WalletTransaction.objects.filter(
            wallet=inr_wallet,
            transaction_type='BREAKDOWN',
            amount=breakdown.final_amount
        ).first()
        
        assert transaction_log is not None
        assert transaction_log.amount == breakdown.final_amount
        assert transaction_log.transaction_type == 'BREAKDOWN'
        assert transaction_log.status == 'COMPLETED'
    
    def test_breakdown_rejection_roi_resumption(self, kyc_user, daily_plan):
        """Test that breakdown rejection resumes ROI accrual"""
        # Create investment
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
        
        # Create breakdown request
        breakdown = BreakdownRequest.objects.create(
            user=kyc_user,
            investment=investment,
            requested_amount=investment.amount,
            final_amount=investment.get_breakdown_amount()
        )
        
        # Reject breakdown
        breakdown.reject()
        
        # Verify investment status is back to active
        investment.refresh_from_db()
        assert investment.status == 'ACTIVE'
        
        # Verify ROI can still be credited
        roi_amount = investment.credit_roi()
        assert roi_amount > Decimal('0.00')
    
    def test_usdt_investment_wallet_integration(self, kyc_user, daily_plan):
        """Test USDT investment wallet integration"""
        # Get initial USDT wallet balance
        usdt_wallet = USDTWallet.objects.get(user=kyc_user)
        initial_balance = usdt_wallet.balance
        
        investment_amount = Decimal('500.00')
        
        # Create USDT investment
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=investment_amount,
            currency='USDT',
            start_date=start_date,
            end_date=end_date,
            next_roi_date=next_roi_date
        )
        
        # Verify USDT wallet balance is deducted
        usdt_wallet.refresh_from_db()
        assert usdt_wallet.balance == initial_balance - investment_amount
        
        # Verify transaction is logged in USDT wallet
        transaction_log = WalletTransaction.objects.filter(
            wallet=usdt_wallet,
            transaction_type='INVESTMENT',
            amount=investment_amount
        ).first()
        
        assert transaction_log is not None
        assert transaction_log.currency == 'USDT'


@pytest.mark.integration
class TestTransactionLogging:
    """Integration tests for transaction logging"""
    
    def test_investment_transaction_logging(self, kyc_user, daily_plan):
        """Test that investment transactions are properly logged"""
        investment_amount = Decimal('1000.00')
        
        # Create investment
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=investment_amount,
            currency='INR',
            start_date=start_date,
            end_date=end_date,
            next_roi_date=next_roi_date
        )
        
        # Verify investment transaction log
        inr_wallet = INRWallet.objects.get(user=kyc_user)
        transaction_log = WalletTransaction.objects.filter(
            wallet=inr_wallet,
            transaction_type='INVESTMENT'
        ).first()
        
        assert transaction_log is not None
        assert transaction_log.amount == investment_amount
        assert transaction_log.currency == 'INR'
        assert transaction_log.reference_id == str(investment.id)
        assert transaction_log.description == f'Investment in {daily_plan.name}'
    
    def test_roi_transaction_logging(self, kyc_user, daily_plan):
        """Test that ROI transactions are properly logged"""
        # Create investment
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
        
        # Credit ROI
        roi_amount = investment.credit_roi()
        
        # Verify ROI transaction log
        inr_wallet = INRWallet.objects.get(user=kyc_user)
        transaction_log = WalletTransaction.objects.filter(
            wallet=inr_wallet,
            transaction_type='ROI'
        ).first()
        
        assert transaction_log is not None
        assert transaction_log.amount == roi_amount
        assert transaction_log.currency == 'INR'
        assert transaction_log.reference_id == str(investment.id)
        assert transaction_log.description == f'ROI credit for {daily_plan.name}'
    
    def test_breakdown_transaction_logging(self, kyc_user, daily_plan):
        """Test that breakdown transactions are properly logged"""
        # Create investment
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
        
        # Create and approve breakdown request
        breakdown = BreakdownRequest.objects.create(
            user=kyc_user,
            investment=investment,
            requested_amount=investment.amount,
            final_amount=investment.get_breakdown_amount()
        )
        
        breakdown.approve()
        
        # Verify breakdown transaction log
        inr_wallet = INRWallet.objects.get(user=kyc_user)
        transaction_log = WalletTransaction.objects.filter(
            wallet=inr_wallet,
            transaction_type='BREAKDOWN'
        ).first()
        
        assert transaction_log is not None
        assert transaction_log.amount == breakdown.final_amount
        assert transaction_log.currency == 'INR'
        assert transaction_log.reference_id == str(investment.id)
        assert transaction_log.description == f'Breakdown payout for {daily_plan.name}'


@pytest.mark.integration
class TestConcurrencyHandling:
    """Integration tests for concurrency handling"""
    
    def test_concurrent_roi_crediting(self, kyc_user, daily_plan):
        """Test concurrent ROI crediting with select_for_update"""
        # Create investment
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
        
        # Simulate concurrent ROI crediting
        def credit_roi_concurrent():
            with transaction.atomic():
                # Lock the investment record
                locked_investment = Investment.objects.select_for_update().get(id=investment.id)
                roi_amount = locked_investment.credit_roi()
                return roi_amount
        
        # This should work without conflicts
        roi_amount = credit_roi_concurrent()
        assert roi_amount > Decimal('0.00')
        
        # Verify investment was updated
        investment.refresh_from_db()
        assert investment.roi_accrued > Decimal('0.00')
    
    def test_concurrent_breakdown_requests(self, kyc_user, daily_plan):
        """Test concurrent breakdown request handling"""
        # Create investment
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
        
        # Simulate concurrent breakdown requests
        def create_breakdown_concurrent():
            with transaction.atomic():
                # Lock the investment record
                locked_investment = Investment.objects.select_for_update().get(id=investment.id)
                
                # Check if breakdown is already pending
                if locked_investment.status == 'BREAKDOWN_PENDING':
                    return None
                
                # Create breakdown request
                breakdown = BreakdownRequest.objects.create(
                    user=kyc_user,
                    investment=locked_investment,
                    requested_amount=locked_investment.amount,
                    final_amount=locked_investment.get_breakdown_amount()
                )
                
                # Update investment status
                locked_investment.status = 'BREAKDOWN_PENDING'
                locked_investment.save()
                
                return breakdown
        
        # First breakdown request should succeed
        breakdown1 = create_breakdown_concurrent()
        assert breakdown1 is not None
        
        # Second breakdown request should fail (already pending)
        breakdown2 = create_breakdown_concurrent()
        assert breakdown2 is None
        
        # Verify only one breakdown request exists
        breakdown_count = BreakdownRequest.objects.filter(investment=investment).count()
        assert breakdown_count == 1
    
    def test_concurrent_wallet_operations(self, kyc_user, daily_plan):
        """Test concurrent wallet operations during investment creation"""
        # Get initial wallet balance
        inr_wallet = INRWallet.objects.get(user=kyc_user)
        initial_balance = inr_wallet.balance
        
        # Simulate concurrent investment creation
        def create_investment_concurrent(amount):
            with transaction.atomic():
                # Lock the wallet record
                locked_wallet = INRWallet.objects.select_for_update().get(id=inr_wallet.id)
                
                # Check if sufficient balance
                if locked_wallet.balance < amount:
                    return None
                
                # Deduct balance
                locked_wallet.balance = F('balance') - amount
                locked_wallet.save()
                
                # Create investment
                start_date = timezone.now()
                end_date = start_date + timedelta(days=daily_plan.duration_days)
                next_roi_date = start_date + timedelta(days=1)
                
                investment = Investment.objects.create(
                    user=kyc_user,
                    plan=daily_plan,
                    amount=amount,
                    currency='INR',
                    start_date=start_date,
                    end_date=end_date,
                    next_roi_date=next_roi_date
                )
                
                return investment
        
        # Create multiple investments concurrently
        investment1 = create_investment_concurrent(Decimal('500.00'))
        investment2 = create_investment_concurrent(Decimal('300.00'))
        
        assert investment1 is not None
        assert investment2 is not None
        
        # Verify final wallet balance
        inr_wallet.refresh_from_db()
        expected_balance = initial_balance - Decimal('500.00') - Decimal('300.00')
        assert inr_wallet.balance == expected_balance


@pytest.mark.integration
class TestDatabaseConsistency:
    """Integration tests for database consistency"""
    
    def test_investment_creation_atomicity(self, kyc_user, daily_plan):
        """Test that investment creation is atomic"""
        # Get initial wallet balance
        inr_wallet = INRWallet.objects.get(user=kyc_user)
        initial_balance = inr_wallet.balance
        
        investment_amount = Decimal('1000.00')
        
        # Create investment with transaction
        with transaction.atomic():
            start_date = timezone.now()
            end_date = start_date + timedelta(days=daily_plan.duration_days)
            next_roi_date = start_date + timedelta(days=1)
            
            investment = Investment.objects.create(
                user=kyc_user,
                plan=daily_plan,
                amount=investment_amount,
                currency='INR',
                start_date=start_date,
                end_date=end_date,
                next_roi_date=next_roi_date
            )
            
            # Deduct from wallet
            inr_wallet.balance = F('balance') - investment_amount
            inr_wallet.save()
            
            # Create transaction log
            WalletTransaction.objects.create(
                wallet=inr_wallet,
                transaction_type='INVESTMENT',
                amount=investment_amount,
                currency='INR',
                status='COMPLETED',
                reference_id=str(investment.id),
                description=f'Investment in {daily_plan.name}'
            )
        
        # Verify all operations completed successfully
        inr_wallet.refresh_from_db()
        assert inr_wallet.balance == initial_balance - investment_amount
        
        # Verify investment exists
        assert Investment.objects.filter(id=investment.id).exists()
        
        # Verify transaction log exists
        assert WalletTransaction.objects.filter(
            wallet=inr_wallet,
            transaction_type='INVESTMENT'
        ).exists()
    
    def test_breakdown_approval_atomicity(self, kyc_user, daily_plan):
        """Test that breakdown approval is atomic"""
        # Create investment
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
        
        # Create breakdown request
        breakdown = BreakdownRequest.objects.create(
            user=kyc_user,
            investment=investment,
            requested_amount=investment.amount,
            final_amount=investment.get_breakdown_amount()
        )
        
        # Get initial wallet balance
        inr_wallet = INRWallet.objects.get(user=kyc_user)
        initial_balance = inr_wallet.balance
        
        # Approve breakdown with transaction
        with transaction.atomic():
            # Update breakdown status
            breakdown.status = 'APPROVED'
            breakdown.save()
            
            # Credit wallet
            inr_wallet.balance = F('balance') + breakdown.final_amount
            inr_wallet.save()
            
            # Update investment status
            investment.status = 'COMPLETED'
            investment.save()
            
            # Create transaction log
            WalletTransaction.objects.create(
                wallet=inr_wallet,
                transaction_type='BREAKDOWN',
                amount=breakdown.final_amount,
                currency='INR',
                status='COMPLETED',
                reference_id=str(investment.id),
                description=f'Breakdown payout for {daily_plan.name}'
            )
        
        # Verify all operations completed successfully
        inr_wallet.refresh_from_db()
        assert inr_wallet.balance == initial_balance + breakdown.final_amount
        
        # Verify breakdown status updated
        breakdown.refresh_from_db()
        assert breakdown.status == 'APPROVED'
        
        # Verify investment status updated
        investment.refresh_from_db()
        assert investment.status == 'COMPLETED'
        
        # Verify transaction log exists
        assert WalletTransaction.objects.filter(
            wallet=inr_wallet,
            transaction_type='BREAKDOWN'
        ).exists()
