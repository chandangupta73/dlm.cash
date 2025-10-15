import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time

from app.investment.models import InvestmentPlan, Investment, BreakdownRequest
from app.wallet.models import WalletTransaction
from app.users.models import KYC


@pytest.mark.e2e
class TestCompleteInvestmentFlow:
    """Test the complete end-to-end investment flow"""

    def test_complete_investment_journey(self, daily_plan, kyc_user, admin_user, api_client, frozen_time):
        """Test complete user journey: invest → ROI credits → breakdown → admin approval"""
        
        # Step 1: User creates investment
        initial_balance = kyc_user.inrwallet.balance
        investment_data = {
            'plan': daily_plan.id,
            'amount': '1000',
            'currency': 'INR'
        }
        
        api_client.force_authenticate(user=kyc_user)
        response = api_client.post('/api/v1/investment/investments/', investment_data)
        assert response.status_code == 201
        
        investment = Investment.objects.get(id=response.data['id'])
        assert investment.status == 'active'
        assert investment.amount == Decimal('1000')
        
        # Check wallet was deducted
        kyc_user.inrwallet.refresh_from_db()
        assert kyc_user.inrwallet.balance == initial_balance - Decimal('1000')
        
        # Check transaction logged
        transaction = WalletTransaction.objects.filter(
            wallet=kyc_user.inrwallet,
            transaction_type='INVESTMENT',
            amount=Decimal('-1000')
        ).first()
        assert transaction is not None
        
        # Step 2: Multiple ROI credits over time
        with frozen_time('2024-01-02 00:00:00'):
            # First ROI credit
            from app.investment.tasks import credit_roi_task
            credit_roi_task.delay()
            
            investment.refresh_from_db()
            expected_roi_1 = Decimal('1000') * Decimal('0.02')  # 2% daily
            assert investment.roi_accrued == expected_roi_1
            
            # Check wallet balance increased
            kyc_user.inrwallet.refresh_from_db()
            expected_balance_1 = initial_balance - Decimal('1000') + expected_roi_1
            assert kyc_user.inrwallet.balance == expected_balance_1
        
        with frozen_time('2024-01-03 00:00:00'):
            # Second ROI credit
            credit_roi_task.delay()
            
            investment.refresh_from_db()
            expected_roi_2 = expected_roi_1 + (Decimal('1000') * Decimal('0.02'))
            assert investment.roi_accrued == expected_roi_2
            
            # Check wallet balance increased again
            kyc_user.inrwallet.refresh_from_db()
            expected_balance_2 = expected_balance_1 + (Decimal('1000') * Decimal('0.02'))
            assert kyc_user.inrwallet.balance == expected_balance_2
        
        # Step 3: User requests breakdown
        breakdown_data = {
            'requested_amount': '1000'
        }
        
        response = api_client.post(
            f'/api/v1/investment/investments/{investment.id}/breakdown/',
            breakdown_data
        )
        assert response.status_code == 201
        
        # Check breakdown request created
        breakdown_request = BreakdownRequest.objects.get(investment=investment)
        assert breakdown_request.status == 'pending'
        
        # Check investment status changed
        investment.refresh_from_db()
        assert investment.status == 'breakdown_pending'
        
        # Step 4: Admin approves breakdown
        api_client.force_authenticate(user=admin_user)
        
        response = api_client.post(
            f'/api/v1/investment/admin/breakdown-requests/{breakdown_request.id}/approve/'
        )
        assert response.status_code == 200
        
        # Check breakdown request approved
        breakdown_request.refresh_from_db()
        assert breakdown_request.status == 'approved'
        
        # Check investment closed
        investment.refresh_from_db()
        assert investment.status == 'completed'
        
        # Check final amount credited to wallet
        kyc_user.inrwallet.refresh_from_db()
        
        # Calculate expected final amount:
        # Investment: 1000, ROI received: 40 (20 + 20)
        # Step 1: 1000 * 0.8 = 800
        # Step 2: 40 * 0.5 = 20
        # Final: 800 - 20 = 780
        expected_final_amount = (Decimal('1000') * Decimal('0.8')) - (Decimal('40') * Decimal('0.5'))
        expected_total_balance = expected_balance_2 + expected_final_amount
        
        assert kyc_user.inrwallet.balance == expected_total_balance
        
        # Check transaction logged for breakdown payout
        breakdown_transaction = WalletTransaction.objects.filter(
            wallet=kyc_user.inrwallet,
            transaction_type='BREAKDOWN',
            amount=expected_final_amount
        ).first()
        assert breakdown_transaction is not None
        assert breakdown_transaction.reference == f"BREAKDOWN-{investment.id}"

    def test_complete_usdt_investment_flow(self, weekly_plan, kyc_user, admin_user, api_client, frozen_time):
        """Test complete USDT investment flow with weekly ROI"""
        
        # Step 1: Create USDT investment
        initial_usdt_balance = kyc_user.usdtwallet.balance
        investment_data = {
            'plan': weekly_plan.id,
            'amount': '5000',
            'currency': 'USDT'
        }
        
        api_client.force_authenticate(user=kyc_user)
        response = api_client.post('/api/v1/investment/investments/', investment_data)
        assert response.status_code == 201
        
        investment = Investment.objects.get(id=response.data['id'])
        
        # Check USDT wallet was deducted
        kyc_user.usdtwallet.refresh_from_db()
        assert kyc_user.usdtwallet.balance == initial_usdt_balance - Decimal('5000')
        
        # Step 2: Weekly ROI credit
        with frozen_time('2024-01-08 00:00:00'):  # 7 days later
            from app.investment.tasks import credit_roi_task
            credit_roi_task.delay()
            
            investment.refresh_from_db()
            expected_roi = Decimal('5000') * Decimal('0.15')  # 15% weekly
            assert investment.roi_accrued == expected_roi
            
            # Check USDT wallet balance increased
            kyc_user.usdtwallet.refresh_from_db()
            expected_balance = initial_usdt_balance - Decimal('5000') + expected_roi
            assert kyc_user.usdtwallet.balance == expected_balance
        
        # Step 3: Request breakdown
        breakdown_data = {
            'requested_amount': '5000'
        }
        
        response = api_client.post(
            f'/api/v1/investment/investments/{investment.id}/breakdown/',
            breakdown_data
        )
        assert response.status_code == 201
        
        breakdown_request = BreakdownRequest.objects.get(investment=investment)
        
        # Step 4: Admin rejects breakdown (resumes ROI)
        api_client.force_authenticate(user=admin_user)
        
        response = api_client.post(
            f'/api/v1/investment/admin/breakdown-requests/{breakdown_request.id}/reject/'
        )
        assert response.status_code == 200
        
        # Check breakdown request rejected
        breakdown_request.refresh_from_db()
        assert breakdown_request.status == 'rejected'
        
        # Check investment status back to active
        investment.refresh_from_db()
        assert investment.status == 'active'
        
        # Check all held ROI is settled to wallet
        kyc_user.usdtwallet.refresh_from_db()
        expected_settled_balance = expected_balance + expected_roi  # ROI settled + previous balance
        assert kyc_user.usdtwallet.balance == expected_settled_balance
        
        # Check transaction logged for ROI settlement
        settlement_transaction = WalletTransaction.objects.filter(
            wallet=kyc_user.usdtwallet,
            transaction_type='ROI_SETTLEMENT',
            amount=expected_roi
        ).first()
        assert settlement_transaction is not None

    def test_investment_with_kyc_revocation_mid_flow(self, daily_plan, kyc_user, admin_user, api_client, frozen_time):
        """Test investment behavior when KYC is revoked mid-investment"""
        
        # Step 1: Create investment
        investment_data = {
            'plan': daily_plan.id,
            'amount': '1000',
            'currency': 'INR'
        }
        
        api_client.force_authenticate(user=kyc_user)
        response = api_client.post('/api/v1/investment/investments/', investment_data)
        assert response.status_code == 201
        
        investment = Investment.objects.get(id=response.data['id'])
        
        # Step 2: Some ROI credits
        with frozen_time('2024-01-02 00:00:00'):
            from app.investment.tasks import credit_roi_task
            credit_roi_task.delay()
            
            investment.refresh_from_db()
            assert investment.roi_accrued > 0
        
        # Step 3: Revoke KYC
        kyc = KYC.objects.get(user=kyc_user)
        kyc.status = 'rejected'
        kyc.save()
        
        # Step 4: Try to request breakdown (should fail due to KYC)
        breakdown_data = {
            'requested_amount': '1000'
        }
        
        response = api_client.post(
            f'/api/v1/investment/investments/{investment.id}/breakdown/',
            breakdown_data
        )
        assert response.status_code == 400
        assert 'KYC' in response.data['error']
        
        # Investment should still be active but ROI paused
        investment.refresh_from_db()
        assert investment.status == 'active'
        
        # Step 5: ROI should be skipped due to KYC status
        with frozen_time('2024-01-03 00:00:00'):
            initial_roi = investment.roi_accrued
            initial_balance = kyc_user.inrwallet.balance
            
            credit_roi_task.delay()
            
            # ROI should not be credited
            investment.refresh_from_db()
            assert investment.roi_accrued == initial_roi
            
            # Wallet balance should not change
            kyc_user.inrwallet.refresh_from_db()
            assert kyc_user.inrwallet.balance == initial_balance

    def test_multiple_investments_concurrent_roi(self, daily_plan, weekly_plan, kyc_user, frozen_time):
        """Test multiple investments with concurrent ROI processing"""
        
        # Create multiple investments
        investments = []
        for i in range(3):
            plan = daily_plan if i % 2 == 0 else weekly_plan
            currency = 'INR' if i % 2 == 0 else 'USDT'
            amount = Decimal('1000') if i % 2 == 0 else Decimal('5000')
            
            investment = Investment.objects.create(
                user=kyc_user,
                plan=plan,
                amount=amount,
                currency=currency,
                start_date=timezone.now().date(),
                status='active'
            )
            investments.append(investment)
        
        # Process ROI for all investments
        with frozen_time('2024-01-02 00:00:00'):
            from app.investment.tasks import credit_roi_task
            credit_roi_task.delay()
            
            # Check all investments got ROI
            for i, investment in enumerate(investments):
                investment.refresh_from_db()
                if i % 2 == 0:  # Daily plan
                    expected_roi = Decimal('1000') * Decimal('0.02')
                else:  # Weekly plan
                    expected_roi = Decimal('5000') * Decimal('0.15')
                assert investment.roi_accrued == expected_roi
        
        # Check wallet balances
        kyc_user.inrwallet.refresh_from_db()
        kyc_user.usdtwallet.refresh_from_db()
        
        # INR wallet: 2 investments of 1000 each + 2 ROI credits of 20 each
        expected_inr_balance = Decimal('2000') + (Decimal('20') * 2)
        assert kyc_user.inrwallet.balance == expected_inr_balance
        
        # USDT wallet: 1 investment of 5000 + 1 ROI credit of 750
        expected_usdt_balance = Decimal('5000') + Decimal('750')
        assert kyc_user.usdtwallet.balance == expected_usdt_balance

    def test_breakdown_request_edge_cases(self, daily_plan, kyc_user, admin_user, api_client, frozen_time):
        """Test edge cases in breakdown request flow"""
        
        # Create investment
        investment_data = {
            'plan': daily_plan.id,
            'amount': '1000',
            'currency': 'INR'
        }
        
        api_client.force_authenticate(user=kyc_user)
        response = api_client.post('/api/v1/investment/investments/', investment_data)
        assert response.status_code == 201
        
        investment = Investment.objects.get(id=response.data['id'])
        
        # Test 1: Double breakdown request (should fail)
        breakdown_data = {
            'requested_amount': '1000'
        }
        
        # First request
        response = api_client.post(
            f'/api/v1/investment/investments/{investment.id}/breakdown/',
            breakdown_data
        )
        assert response.status_code == 201
        
        # Second request should fail
        response = api_client.post(
            f'/api/v1/investment/investments/{investment.id}/breakdown/',
            breakdown_data
        )
        assert response.status_code == 400
        assert 'already pending' in response.data['error']
        
        # Test 2: Approve already processed breakdown
        breakdown_request = BreakdownRequest.objects.get(investment=investment)
        
        api_client.force_authenticate(user=admin_user)
        
        # First approval
        response = api_client.post(
            f'/api/v1/investment/admin/breakdown-requests/{breakdown_request.id}/approve/'
        )
        assert response.status_code == 200
        
        # Second approval should fail
        response = api_client.post(
            f'/api/v1/investment/admin/breakdown-requests/{breakdown_request.id}/approve/'
        )
        assert response.status_code == 400
        assert 'already processed' in response.data['error']

    def test_investment_plan_changes_affect_existing_investments(self, daily_plan, kyc_user, admin_user, api_client, frozen_time):
        """Test that changes to investment plans don't affect existing investments"""
        
        # Create investment with original plan
        investment_data = {
            'plan': daily_plan.id,
            'amount': '1000',
            'currency': 'INR'
        }
        
        api_client.force_authenticate(user=kyc_user)
        response = api_client.post('/api/v1/investment/investments/', investment_data)
        assert response.status_code == 201
        
        investment = Investment.objects.get(id=response.data['id'])
        original_roi_rate = investment.plan.roi_rate
        
        # Admin changes the plan
        api_client.force_authenticate(user=admin_user)
        plan_update_data = {
            'roi_rate': '0.05'  # Change from 2% to 5%
        }
        
        response = api_client.patch(
            f'/api/v1/investment/admin/investment-plans/{daily_plan.id}/',
            plan_update_data
        )
        assert response.status_code == 200
        
        # Existing investment should still use original ROI rate
        investment.refresh_from_db()
        assert investment.plan.roi_rate == Decimal('0.05')  # Plan updated
        
        # But ROI calculation should use the rate at investment time
        with frozen_time('2024-01-02 00:00:00'):
            from app.investment.tasks import credit_roi_task
            credit_roi_task.delay()
            
            investment.refresh_from_db()
            # Should use original rate (2%) not new rate (5%)
            expected_roi = Decimal('1000') * Decimal('0.02')
            assert investment.roi_accrued == expected_roi

    def test_investment_completion_flow(self, daily_plan, kyc_user, frozen_time):
        """Test investment completion when end date is reached"""
        
        # Create investment with 30-day duration
        investment = Investment.objects.create(
            user=kyc_user,
            plan=daily_plan,
            amount=Decimal('1000'),
            currency='INR',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            status='active'
        )
        
        # Add some ROI
        with frozen_time('2024-01-02 00:00:00'):
            from app.investment.tasks import credit_roi_task
            credit_roi_task.delay()
            
            investment.refresh_from_db()
            assert investment.roi_accrued > 0
        
        # Mock time to end date
        with frozen_time('2024-02-01 00:00:00'):
            from app.investment.tasks import process_completed_investments
            process_completed_investments.delay()
            
            investment.refresh_from_db()
            assert investment.status == 'completed'
            
            # ROI should still be in wallet
            kyc_user.inrwallet.refresh_from_db()
            assert kyc_user.inrwallet.balance > Decimal('1000')  # Original + ROI

    def test_negative_balance_prevention(self, daily_plan, kyc_user, api_client):
        """Test that investments cannot create negative wallet balances"""
        
        # Try to invest more than wallet balance
        large_amount = kyc_user.inrwallet.balance + Decimal('1000')
        investment_data = {
            'plan': daily_plan.id,
            'amount': str(large_amount),
            'currency': 'INR'
        }
        
        api_client.force_authenticate(user=kyc_user)
        response = api_client.post('/api/v1/investment/investments/', investment_data)
        assert response.status_code == 400
        assert 'insufficient balance' in response.data['error']
        
        # Check no investment was created
        assert Investment.objects.count() == 0
        
        # Check wallet balance unchanged
        kyc_user.inrwallet.refresh_from_db()
        original_balance = kyc_user.inrwallet.balance
        assert kyc_user.inrwallet.balance == original_balance

    def test_breakdown_window_boundary_conditions(self, daily_plan, kyc_user, api_client, frozen_time):
        """Test breakdown requests at boundary conditions"""
        
        # Create investment
        investment_data = {
            'plan': daily_plan.id,
            'amount': '1000',
            'currency': 'INR'
        }
        
        api_client.force_authenticate(user=kyc_user)
        response = api_client.post('/api/v1/investment/investments/', investment_data)
        assert response.status_code == 201
        
        investment = Investment.objects.get(id=response.data['id'])
        breakdown_window = investment.plan.breakdown_window_days
        
        # Test breakdown request on last allowed day
        with frozen_time(f'2024-01-{breakdown_window + 1:02d} 00:00:00'):
            breakdown_data = {
                'requested_amount': '1000'
            }
            
            response = api_client.post(
                f'/api/v1/investment/investments/{investment.id}/breakdown/',
                breakdown_data
            )
            assert response.status_code == 201
        
        # Test breakdown request one day after window closes
        with frozen_time(f'2024-01-{breakdown_window + 2:02d} 00:00:00'):
            breakdown_data = {
                'requested_amount': '1000'
            }
            
            response = api_client.post(
                f'/api/v1/investment/investments/{investment.id}/breakdown/',
                breakdown_data
            )
            assert response.status_code == 400
            assert 'breakdown window' in response.data['error']
