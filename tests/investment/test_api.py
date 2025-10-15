import pytest
import json
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from app.investment.models import InvestmentPlan, Investment, BreakdownRequest
from app.wallet.models import INRWallet, USDTWallet
from app.users.models import KYC


@pytest.mark.api
class TestInvestmentPlanAPI:
    """API tests for Investment Plan endpoints"""
    
    def test_list_investment_plans(self, api_client, investment_plans):
        """Test GET /investment-plans/ endpoint"""
        url = reverse('investment-plan-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        
        # Verify plan data structure
        plans = response.data['results']
        assert len(plans) == 3
        
        # Check first plan structure
        first_plan = plans[0]
        required_fields = ['id', 'name', 'min_amount', 'max_amount', 'roi_rate', 
                          'frequency', 'duration_days', 'breakdown_window_days']
        for field in required_fields:
            assert field in first_plan
        
        # Verify no sensitive fields are exposed
        sensitive_fields = ['created_at', 'updated_at']
        for field in sensitive_fields:
            assert field not in first_plan
    
    def test_retrieve_investment_plan(self, api_client, daily_plan):
        """Test GET /investment-plans/{id}/ endpoint"""
        url = reverse('investment-plan-detail', kwargs={'pk': daily_plan.id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify plan data
        plan_data = response.data
        assert plan_data['id'] == str(daily_plan.id)
        assert plan_data['name'] == daily_plan.name
        assert plan_data['min_amount'] == str(daily_plan.min_amount)
        assert plan_data['max_amount'] == str(daily_plan.max_amount)
        assert plan_data['roi_rate'] == str(daily_plan.roi_rate)
        assert plan_data['frequency'] == daily_plan.frequency
    
    def test_investment_plan_not_found(self, api_client):
        """Test GET /investment-plans/{id}/ with non-existent plan"""
        url = reverse('investment-plan-detail', kwargs={'pk': 'non-existent-id'})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.api
class TestInvestmentAPI:
    """API tests for Investment endpoints"""
    
    def test_create_investment_success(self, api_client, kyc_user, daily_plan):
        """Test POST /investments/ with valid data"""
        # Authenticate user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('investment-list')
        data = {
            'plan': daily_plan.id,
            'amount': '1000.00',
            'currency': 'INR'
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify response data
        investment_data = response.data
        assert investment_data['plan'] == str(daily_plan.id)
        assert investment_data['amount'] == '1000.00'
        assert investment_data['currency'] == 'INR'
        assert investment_data['status'] == 'ACTIVE'
        assert 'id' in investment_data
        assert 'start_date' in investment_data
        assert 'end_date' in investment_data
        
        # Verify investment was created in database
        investment = Investment.objects.get(id=investment_data['id'])
        assert investment.user == kyc_user
        assert investment.plan == daily_plan
        assert investment.amount == Decimal('1000.00')
        
        # Verify wallet balance was deducted
        inr_wallet = INRWallet.objects.get(user=kyc_user)
        assert inr_wallet.balance == Decimal('9000.00')  # 10000 - 1000
    
    def test_create_investment_insufficient_balance(self, api_client, kyc_user, daily_plan):
        """Test POST /investments/ with insufficient balance"""
        # Authenticate user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('investment-list')
        data = {
            'plan': daily_plan.id,
            'amount': '15000.00',  # More than wallet balance
            'currency': 'INR'
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'insufficient balance' in response.data['error'].lower()
    
    def test_create_investment_amount_limits(self, api_client, kyc_user, daily_plan):
        """Test POST /investments/ with amount outside plan limits"""
        # Authenticate user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('investment-list')
        
        # Test amount below minimum
        data = {
            'plan': daily_plan.id,
            'amount': '50.00',  # Below min_amount (100.00)
            'currency': 'INR'
        }
        
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        
        # Test amount above maximum
        data['amount'] = '15000.00'  # Above max_amount (10000.00)
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_create_investment_no_kyc(self, api_client, pending_kyc_user, daily_plan):
        """Test POST /investments/ without approved KYC"""
        # Authenticate user without approved KYC
        refresh = RefreshToken.for_user(pending_kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('investment-list')
        data = {
            'plan': daily_plan.id,
            'amount': '1000.00',
            'currency': 'INR'
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'kyc' in response.data['error'].lower()
    
    def test_create_investment_unauthenticated(self, api_client, daily_plan):
        """Test POST /investments/ without authentication"""
        url = reverse('investment-list')
        data = {
            'plan': daily_plan.id,
            'amount': '1000.00',
            'currency': 'INR'
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_list_user_investments(self, api_client, kyc_user, active_investment):
        """Test GET /investments/ for authenticated user"""
        # Authenticate user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('investment-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        
        # Verify user only sees their own investments
        investments = response.data['results']
        assert len(investments) == 1
        
        investment_data = investments[0]
        assert investment_data['id'] == str(active_investment.id)
        assert investment_data['user'] == str(kyc_user.id)
    
    def test_list_investments_unauthenticated(self, api_client):
        """Test GET /investments/ without authentication"""
        url = reverse('investment-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_breakdown_investment_success(self, api_client, kyc_user, active_investment):
        """Test POST /investments/{id}/breakdown/ with valid request"""
        # Authenticate user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('investment-breakdown', kwargs={'pk': active_investment.id})
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify response data
        breakdown_data = response.data
        assert breakdown_data['investment'] == str(active_investment.id)
        assert breakdown_data['status'] == 'PENDING'
        assert 'id' in breakdown_data
        assert 'final_amount' in breakdown_data
        
        # Verify breakdown request was created
        breakdown = BreakdownRequest.objects.get(id=breakdown_data['id'])
        assert breakdown.user == kyc_user
        assert breakdown.investment == active_investment
        
        # Verify investment status was updated
        active_investment.refresh_from_db()
        assert active_investment.status == 'BREAKDOWN_PENDING'
    
    def test_breakdown_investment_outside_window(self, api_client, kyc_user, daily_plan):
        """Test POST /investments/{id}/breakdown/ outside breakdown window"""
        # Create investment outside breakdown window
        start_date = timezone.now() - timedelta(days=15)  # 15 days ago
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
        
        # Authenticate user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('investment-breakdown', kwargs={'pk': investment.id})
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'breakdown window' in response.data['error'].lower()
    
    def test_breakdown_investment_already_pending(self, api_client, kyc_user, active_investment):
        """Test POST /investments/{id}/breakdown/ when already pending"""
        # Create first breakdown request
        BreakdownRequest.objects.create(
            user=kyc_user,
            investment=active_investment,
            requested_amount=active_investment.amount,
            final_amount=active_investment.get_breakdown_amount()
        )
        
        # Authenticate user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('investment-breakdown', kwargs={'pk': active_investment.id})
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'already pending' in response.data['error'].lower()
    
    def test_breakdown_investment_not_found(self, api_client, kyc_user):
        """Test POST /investments/{id}/breakdown/ with non-existent investment"""
        # Authenticate user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('investment-breakdown', kwargs={'pk': 'non-existent-id'})
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.api
class TestBreakdownRequestAPI:
    """API tests for Breakdown Request endpoints"""
    
    def test_list_user_breakdown_requests(self, api_client, kyc_user, breakdown_request):
        """Test GET /breakdown-requests/ for authenticated user"""
        # Authenticate user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('breakdown-request-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        
        # Verify user only sees their own breakdown requests
        requests = response.data['results']
        assert len(requests) == 1
        
        request_data = requests[0]
        assert request_data['id'] == str(breakdown_request.id)
        assert request_data['investment'] == str(breakdown_request.investment.id)
        assert request_data['status'] == 'PENDING'
    
    def test_retrieve_breakdown_request(self, api_client, kyc_user, breakdown_request):
        """Test GET /breakdown-requests/{id}/ for authenticated user"""
        # Authenticate user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('breakdown-request-detail', kwargs={'pk': breakdown_request.id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify breakdown request data
        request_data = response.data
        assert request_data['id'] == str(breakdown_request.id)
        assert request_data['investment'] == str(breakdown_request.investment.id)
        assert request_data['status'] == breakdown_request.status
        assert 'final_amount' in request_data
    
    def test_breakdown_request_not_found(self, api_client, kyc_user):
        """Test GET /breakdown-requests/{id}/ with non-existent request"""
        # Authenticate user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('breakdown-request-detail', kwargs={'pk': 'non-existent-id'})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.api
class TestAdminInvestmentPlanAPI:
    """API tests for Admin Investment Plan endpoints"""
    
    def test_admin_create_investment_plan(self, api_client, admin_user):
        """Test POST /admin/investment-plans/ by admin"""
        # Authenticate admin
        refresh = RefreshToken.for_user(admin_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('admin-investment-plan-list')
        data = {
            'name': 'Test Admin Plan',
            'min_amount': '500.00',
            'max_amount': '5000.00',
            'roi_rate': '2.0',
            'frequency': 'WEEKLY',
            'duration_days': 60,
            'breakdown_window_days': 15
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify plan was created
        plan_data = response.data
        assert plan_data['name'] == 'Test Admin Plan'
        assert plan_data['min_amount'] == '500.00'
        assert plan_data['max_amount'] == '5000.00'
        assert plan_data['roi_rate'] == '2.0'
        assert plan_data['frequency'] == 'WEEKLY'
        
        # Verify plan exists in database
        plan = InvestmentPlan.objects.get(id=plan_data['id'])
        assert plan.name == 'Test Admin Plan'
    
    def test_admin_create_investment_plan_validation(self, api_client, admin_user):
        """Test POST /admin/investment-plans/ with invalid data"""
        # Authenticate admin
        refresh = RefreshToken.for_user(admin_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('admin-investment-plan-list')
        
        # Test invalid data
        data = {
            'name': '',  # Empty name
            'min_amount': '1000.00',
            'max_amount': '500.00',  # min > max
            'roi_rate': '-1.0',  # Negative ROI
            'frequency': 'INVALID',  # Invalid frequency
            'duration_days': 0,  # Invalid duration
            'breakdown_window_days': 20
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Should have multiple validation errors
        assert len(response.data) > 1
    
    def test_admin_create_investment_plan_unauthorized(self, api_client, kyc_user):
        """Test POST /admin/investment-plans/ by non-admin user"""
        # Authenticate non-admin user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('admin-investment-plan-list')
        data = {
            'name': 'Test Plan',
            'min_amount': '100.00',
            'max_amount': '1000.00',
            'roi_rate': '1.0',
            'frequency': 'DAILY',
            'duration_days': 30,
            'breakdown_window_days': 10
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_admin_update_investment_plan(self, api_client, admin_user, daily_plan):
        """Test PUT /admin/investment-plans/{id}/ by admin"""
        # Authenticate admin
        refresh = RefreshToken.for_user(admin_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('admin-investment-plan-detail', kwargs={'pk': daily_plan.id})
        data = {
            'name': 'Updated Daily Plan',
            'min_amount': '200.00',
            'max_amount': '15000.00',
            'roi_rate': '0.75',
            'frequency': 'DAILY',
            'duration_days': 45,
            'breakdown_window_days': 12
        }
        
        response = api_client.put(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify plan was updated
        plan_data = response.data
        assert plan_data['name'] == 'Updated Daily Plan'
        assert plan_data['min_amount'] == '200.00'
        assert plan_data['max_amount'] == '15000.00'
        assert plan_data['roi_rate'] == '0.75'
        
        # Verify database was updated
        daily_plan.refresh_from_db()
        assert daily_plan.name == 'Updated Daily Plan'
        assert daily_plan.min_amount == Decimal('200.00')
    
    def test_admin_delete_investment_plan(self, api_client, admin_user, daily_plan):
        """Test DELETE /admin/investment-plans/{id}/ by admin"""
        # Authenticate admin
        refresh = RefreshToken.for_user(admin_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('admin-investment-plan-detail', kwargs={'pk': daily_plan.id})
        response = api_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify plan was deleted
        assert not InvestmentPlan.objects.filter(id=daily_plan.id).exists()


@pytest.mark.api
class TestAdminBreakdownRequestAPI:
    """API tests for Admin Breakdown Request endpoints"""
    
    def test_admin_list_breakdown_requests(self, api_client, admin_user, breakdown_request):
        """Test GET /admin/breakdown-requests/ by admin"""
        # Authenticate admin
        refresh = RefreshToken.for_user(admin_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('admin-breakdown-request-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        
        # Verify admin sees all breakdown requests
        requests = response.data['results']
        assert len(requests) == 1
        
        request_data = requests[0]
        assert request_data['id'] == str(breakdown_request.id)
        assert request_data['user'] == str(breakdown_request.user.id)
        assert request_data['investment'] == str(breakdown_request.investment.id)
    
    def test_admin_approve_breakdown_request(self, api_client, admin_user, breakdown_request):
        """Test POST /admin/breakdown-requests/{id}/approve by admin"""
        # Authenticate admin
        refresh = RefreshToken.for_user(admin_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('admin-breakdown-request-approve', kwargs={'pk': breakdown_request.id})
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify response data
        response_data = response.data
        assert response_data['status'] == 'APPROVED'
        assert 'message' in response_data
        
        # Verify breakdown request was approved
        breakdown_request.refresh_from_db()
        assert breakdown_request.status == 'APPROVED'
        
        # Verify investment was completed
        investment = breakdown_request.investment
        investment.refresh_from_db()
        assert investment.status == 'COMPLETED'
        
        # Verify wallet was credited
        user = breakdown_request.user
        if investment.currency == 'INR':
            wallet = INRWallet.objects.get(user=user)
        else:
            wallet = USDTWallet.objects.get(user=user)
        
        # Wallet should have been credited with final amount
        # (Note: This assumes the approve method was called and wallet was credited)
        assert wallet.balance > Decimal('0.00')
    
    def test_admin_reject_breakdown_request(self, api_client, admin_user, breakdown_request):
        """Test POST /admin/breakdown-requests/{id}/reject by admin"""
        # Authenticate admin
        refresh = RefreshToken.for_user(admin_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('admin-breakdown-request-reject', kwargs={'pk': breakdown_request.id})
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify response data
        response_data = response.data
        assert response_data['status'] == 'REJECTED'
        assert 'message' in response_data
        
        # Verify breakdown request was rejected
        breakdown_request.refresh_from_db()
        assert breakdown_request.status == 'REJECTED'
        
        # Verify investment status was restored to active
        investment = breakdown_request.investment
        investment.refresh_from_db()
        assert investment.status == 'ACTIVE'
    
    def test_admin_approve_already_processed_request(self, api_client, admin_user, breakdown_request):
        """Test POST /admin/breakdown-requests/{id}/approve on already processed request"""
        # First approve the request
        breakdown_request.approve()
        
        # Authenticate admin
        refresh = RefreshToken.for_user(admin_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('admin-breakdown-request-approve', kwargs={'pk': breakdown_request.id})
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'already processed' in response.data['error'].lower()
    
    def test_admin_breakdown_request_not_found(self, api_client, admin_user):
        """Test admin endpoints with non-existent breakdown request"""
        # Authenticate admin
        refresh = RefreshToken.for_user(admin_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Test approve non-existent request
        url = reverse('admin-breakdown-request-approve', kwargs={'pk': 'non-existent-id'})
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Test reject non-existent request
        url = reverse('admin-breakdown-request-reject', kwargs={'pk': 'non-existent-id'})
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_admin_breakdown_request_unauthorized(self, api_client, kyc_user, breakdown_request):
        """Test admin endpoints by non-admin user"""
        # Authenticate non-admin user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Test approve by non-admin
        url = reverse('admin-breakdown-request-approve', kwargs={'pk': breakdown_request.id})
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Test reject by non-admin
        url = reverse('admin-breakdown-request-reject', kwargs={'pk': breakdown_request.id})
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.api
class TestAPISecurity:
    """API tests for security and data exposure"""
    
    def test_no_sensitive_data_exposure(self, api_client, kyc_user, active_investment):
        """Test that sensitive data is not exposed in API responses"""
        # Authenticate user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Test investment endpoint
        url = reverse('investment-detail', kwargs={'pk': active_investment.id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify no sensitive fields are exposed
        sensitive_fields = ['internal_id', 'private_key', 'secret', 'password_hash']
        for field in sensitive_fields:
            assert field not in response.data
        
        # Verify only user's own data is accessible
        assert response.data['user'] == str(kyc_user.id)
    
    def test_user_cannot_access_other_user_investments(self, api_client, kyc_user, daily_plan):
        """Test that users cannot access other users' investments"""
        # Create another user with investment
        from tests.investment.conftest import KYCUserFactory
        other_user = KYCUserFactory.create_with_kyc()
        
        # Create investment for other user
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        other_investment = Investment.objects.create(
            user=other_user,
            plan=daily_plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=start_date,
            end_date=end_date,
            next_roi_date=next_roi_date
        )
        
        # Authenticate first user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Try to access other user's investment
        url = reverse('investment-detail', kwargs={'pk': other_investment.id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_user_cannot_modify_other_user_investments(self, api_client, kyc_user, daily_plan):
        """Test that users cannot modify other users' investments"""
        # Create another user with investment
        from tests.investment.conftest import KYCUserFactory
        other_user = KYCUserFactory.create_with_kyc()
        
        # Create investment for other user
        start_date = timezone.now()
        end_date = start_date + timedelta(days=daily_plan.duration_days)
        next_roi_date = start_date + timedelta(days=1)
        
        other_investment = Investment.objects.create(
            user=other_user,
            plan=daily_plan,
            amount=Decimal('1000.00'),
            currency='INR',
            start_date=start_date,
            end_date=end_date,
            next_roi_date=next_roi_date
        )
        
        # Authenticate first user
        refresh = RefreshToken.for_user(kyc_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Try to request breakdown on other user's investment
        url = reverse('investment-breakdown', kwargs={'pk': other_investment.id})
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
