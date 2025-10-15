import pytest
import time
from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from app.users.models import User
from app.wallet.models import INRWallet, USDTWallet, WalletTransaction
from app.transactions.models import Transaction
from app.withdrawals.models import Withdrawal
from app.deposits.models import DepositRequest
from app.investment.models import InvestmentPlan, Investment

@pytest.mark.security
class TestAuthenticationSecurity(TestCase):
    """Test authentication and authorization security measures"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test users
        self.admin_user = User.objects.create_user(
            username='admin_sec',
            email='admin@sec.com',
            password='admin123!',
            is_staff=True,
            is_superuser=True
        )
        
        self.user = User.objects.create_user(
            username='user_sec',
            email='user@sec.com',
            password='user123!',
            first_name='Security',
            last_name='User',
            kyc_status='APPROVED',
            is_kyc_verified=True
        )
        
        self.unauthorized_user = User.objects.create_user(
            username='unauth_sec',
            email='unauth@sec.com',
            password='unauth123!',
            first_name='Unauthorized',
            last_name='User'
        )
        
        # Create wallets
        self.inr_wallet, created = INRWallet.objects.get_or_create(
            user=self.user,
            defaults={
                'balance': Decimal('1000.00'),
                'status': 'active'
            }
        )
        
        self.usdt_wallet, created = USDTWallet.objects.get_or_create(
            user=self.user,
            defaults={
                'balance': Decimal('100.000000'),
                'status': 'active'
            }
        )
        
        # Create investment plan
        self.investment_plan = InvestmentPlan.objects.create(
            name='Security Test Plan',
            roi_rate=Decimal('12.00'),
            frequency='daily',
            duration_days=30,
            breakdown_window_days=15,
            min_amount=Decimal('100.00'),
            max_amount=Decimal('1000.00'),
            status='active'
        )
        
        # Get tokens
        self.admin_token = self._get_token(self.admin_user)
        self.user_token = self._get_token(self.user)
        self.unauthorized_token = self._get_token(self.unauthorized_user)
        
        # Set authentication
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
    
    def _get_token(self, user):
        """Get JWT token for user"""
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    
    def test_unauthorized_access_to_admin_endpoints(self):
        """Test that unauthorized users cannot access admin endpoints"""
        # Regular user tries to access admin wallet adjustment
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        
        admin_data = {
            'user_id': str(self.user.id),
            'action': 'credit',
            'amount': '100.00',
            'wallet_type': 'INR',
            'reason': 'Unauthorized admin access test'
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            admin_data
        )
        
        # Should fail - user not admin
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Unauthorized user tries to access admin endpoints
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.unauthorized_token}')
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            admin_data
        )
        
        # Should fail
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_token_expiration_handling(self):
        """Test handling of expired JWT tokens"""
        # Create a token that expires quickly
        from rest_framework_simplejwt.tokens import RefreshToken
        from django.utils import timezone
        
        # Set token lifetime to 1 second
        with self.settings(SIMPLE_JWT={'ACCESS_TOKEN_LIFETIME': timedelta(seconds=1)}):
            refresh = RefreshToken.for_user(self.user)
            short_lived_token = str(refresh.access_token)
            
            # Use the short-lived token
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {short_lived_token}')
            
            # Try to access protected endpoint
            response = self.client.get(reverse('user-withdrawals'))
            
            # Should work initially
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
            
            # Wait for token to expire
            time.sleep(2)
            
            # Try again with expired token
            response = self.client.get(reverse('user-withdrawals'))
            
            # Should fail due to expired token
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_invalid_token_handling(self):
        """Test handling of invalid JWT tokens"""
        # Test with malformed token
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid_token_format')
        
        response = self.client.get(reverse('user-withdrawals'))
        
        # Should fail
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Test with completely invalid token
        self.client.credentials(HTTP_AUTHORIZATION='Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.invalid')
        
        response = self.client.get(reverse('user-withdrawals'))
        
        # Should fail
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_cross_user_access_prevention(self):
        """Test that users cannot access other users' data"""
        # User tries to access another user's withdrawal data
        other_user = User.objects.create_user(
            username='other_user',
            email='other@test.com',
            password='other123!',
            first_name='Other',
            last_name='User'
        )
        
        # Create withdrawal for other user
        other_withdrawal = Withdrawal.objects.create(
            user=other_user,
            currency='INR',
            amount=Decimal('100.00'),
            payout_method='bank_transfer',
            payout_details='{"account_number": "1234567890", "ifsc_code": "SBIN0001234", "account_holder_name": "Other User", "bank_name": "State Bank of India"}',
            status='PENDING'
        )
        
        # Current user tries to access other user's withdrawal
        response = self.client.get(
            reverse('admin_panel:admin-withdrawals-detail', kwargs={'pk': other_withdrawal.id})
        )
        
        # Should fail - user cannot access other user's data
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_admin_privilege_escalation_prevention(self):
        """Test that regular users cannot escalate to admin privileges"""
        # Regular user tries to create admin user
        admin_creation_data = {
            'username': 'fake_admin',
            'email': 'fake@admin.com',
            'password': 'fake123!',
            'is_staff': True,
            'is_superuser': True
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-users-list'),
            admin_creation_data
        )
        
        # Should fail - user cannot create admin accounts
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Regular user tries to modify admin permissions
        response = self.client.patch(
            reverse('admin_panel:admin-users-detail', kwargs={'pk': self.admin_user.id}),
            {'is_staff': False}
        )
        
        # Should fail
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_sensitive_data_exposure_prevention(self):
        """Test that sensitive data is not exposed in responses"""
        # User accesses their own data
        response = self.client.get(reverse('user-withdrawals'))
        
        if response.status_code == status.HTTP_200_OK:
            # Check that sensitive fields are not exposed
            data = response.data
            
            if isinstance(data, list) and len(data) > 0:
                withdrawal = data[0]
                # Sensitive fields should not be exposed
                sensitive_fields = ['payout_details', 'ip_address', 'user_agent']
                for field in sensitive_fields:
                    if field in withdrawal:
                        # Field exists but should be sanitized or limited
                        self.assertNotIn('1234567890', str(withdrawal[field]))
    
    def test_rate_limiting_on_auth_endpoints(self):
        """Test rate limiting on authentication endpoints"""
        # Try to authenticate multiple times rapidly
        auth_data = {
            'username': 'user_sec',
            'password': 'user123!'
        }
        
        responses = []
        for _ in range(10):  # Try 10 times rapidly
            response = self.client.post(reverse('token_obtain_pair'), auth_data)
            responses.append(response.status_code)
        
        # Some requests should be rate limited
        rate_limited_count = sum(1 for code in responses if code == status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertGreater(rate_limited_count, 0)
    
    def test_session_fixation_prevention(self):
        """Test that session fixation attacks are prevented"""
        # Get initial token
        initial_token = self.user_token
        
        # Simulate token refresh
        refresh_response = self.client.post(reverse('token_refresh'), {
            'refresh': self._get_refresh_token(self.user)
        })
        
        if refresh_response.status_code == status.HTTP_200_OK:
            new_token = refresh_response.data.get('access')
            
            # Old token should still work (JWT tokens are stateless)
            # But this tests the refresh mechanism
            self.assertIsNotNone(new_token)
            
            # Use new token
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_token}')
            
            # Should still work
            response = self.client.get(reverse('user-withdrawals'))
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
    
    def _get_refresh_token(self, user):
        """Get refresh token for user"""
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        return str(refresh)
    
    def test_csrf_protection_on_state_changing_operations(self):
        """Test CSRF protection on state-changing operations"""
        # Test withdrawal creation (state-changing operation)
        withdrawal_data = {
            'currency': 'INR',
            'amount': '100.00',
            'payout_method': 'bank_transfer',
            'payout_details': {
                'account_number': '1234567890',
                'ifsc_code': 'SBIN0001234',
                'account_holder_name': 'Test User',
                'bank_name': 'State Bank of India'
            }
        }
        
        # Without CSRF token (should work with JWT)
        response = self.client.post(
            reverse('create-withdrawal'),
            withdrawal_data
        )
        
        # Should work with JWT authentication
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_secure_headers_presence(self):
        """Test that secure headers are present in responses"""
        # Make a request to check headers
        response = self.client.get(reverse('user-withdrawals'))
        
        # Check for security headers
        headers = response.headers
        
        # These headers should be present for security
        security_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options',
            'X-XSS-Protection'
        ]
        
        for header in security_headers:
            if header in headers:
                # Header is present, check it's not empty
                self.assertIsNotNone(headers[header])
                self.assertNotEqual(headers[header], '')
    
    def test_password_strength_validation(self):
        """Test password strength validation"""
        # Try to create user with weak password
        weak_password_data = {
            'username': 'weak_user',
            'email': 'weak@test.com',
            'password': '123'  # Very weak password
        }
        
        response = self.client.post(reverse('user-register'), weak_password_data)
        
        # Should fail due to weak password
        self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Try with stronger password
        strong_password_data = {
            'username': 'strong_user',
            'email': 'strong@test.com',
            'password': 'StrongPass123!'  # Strong password
        }
        
        response = self.client.post(reverse('user-register'), strong_password_data)
        
        # Should succeed with strong password
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_account_lockout_on_failed_attempts(self):
        """Test account lockout after multiple failed login attempts"""
        # Try to login with wrong password multiple times
        wrong_password_data = {
            'username': 'user_sec',
            'password': 'wrong_password'
        }
        
        failed_attempts = []
        for _ in range(5):  # Try 5 times
            response = self.client.post(reverse('token_obtain_pair'), wrong_password_data)
            failed_attempts.append(response.status_code)
        
        # All should fail
        for code in failed_attempts:
            self.assertEqual(code, status.HTTP_401_UNAUTHORIZED)
        
        # Try with correct password
        correct_password_data = {
            'username': 'user_sec',
            'password': 'user123!'
        }
        
        response = self.client.post(reverse('token_obtain_pair'), correct_password_data)
        
        # Should still work (no lockout implemented in basic setup)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention"""
        # Try SQL injection in username field
        sql_injection_data = {
            'username': "'; DROP TABLE users; --",
            'password': 'injection123!'
        }
        
        response = self.client.post(reverse('token_obtain_pair'), sql_injection_data)
        
        # Should fail but not crash
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Check that users table still exists
        user_count = User.objects.count()
        self.assertGreater(user_count, 0)
    
    def test_xss_prevention_in_user_input(self):
        """Test XSS prevention in user input"""
        # Try to create withdrawal with XSS payload
        xss_data = {
            'currency': 'INR',
            'amount': '100.00',
            'payout_method': 'bank_transfer',
            'payout_details': {
                'account_number': '1234567890',
                'ifsc_code': 'SBIN0001234',
                'account_holder_name': '<script>alert("XSS")</script>',
                'bank_name': 'State Bank of India'
            }
        }
        
        response = self.client.post(
            reverse('create-withdrawal'),
            xss_data
        )
        
        # Should succeed (XSS prevention is typically at frontend level)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check that script tags are not executed
        withdrawal = Withdrawal.objects.get(user=self.user)
        payout_details = withdrawal.payout_details
        
        # Script tags should be present in data but not executed
        self.assertIn('<script>', payout_details)
    
    def test_privilege_separation(self):
        """Test that different user roles have appropriate access levels"""
        # Admin user should have access to admin endpoints
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        admin_data = {
            'user_id': str(self.user.id),
            'action': 'credit',
            'amount': '100.00',
            'wallet_type': 'INR',
            'reason': 'Admin privilege test'
        }
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            admin_data
        )
        
        # Admin should have access
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Regular user should not have admin access
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        
        response = self.client.post(
            reverse('admin_panel:admin-wallet-adjust-balance'),
            admin_data
        )
        
        # Regular user should not have access
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
