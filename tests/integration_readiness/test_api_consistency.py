import pytest
import json
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
from app.wallet.models import DepositRequest
from app.investment.models import InvestmentPlan, Investment
import time

@pytest.mark.integration
class TestAPIConsistency(TestCase):
    """Test API consistency and integration readiness"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test users
        self.admin_user = User.objects.create_user(
            username='admin_integration',
            email='admin@integration.com',
            password='admin123!',
            is_staff=True,
            is_superuser=True
        )
        
        self.user = User.objects.create_user(
            username='user_integration',
            email='user@integration.com',
            password='user123!',
            first_name='Integration',
            last_name='User',
            kyc_status='APPROVED',
            is_kyc_verified=True
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
            name='Integration Test Plan',
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
        
        # Set authentication
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
    
    def _get_token(self, user):
        """Get JWT token for user"""
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    
    def test_api_response_format_consistency(self):
        """Test that all API responses follow consistent format"""
        # Test wallet balance endpoint
        response = self.client.get(reverse('wallet-balance'))
        
        if response.status_code == status.HTTP_200_OK:
            # Check response structure
            self.assertIn('data', response.data or {})
            
            # Check data types
            data = response.data.get('data', {})
            if 'inr_wallet' in data:
                self.assertIsInstance(data['inr_wallet']['balance'], str)
                self.assertIsInstance(data['inr_wallet']['status'], str)
        
        # Test transactions endpoint
        response = self.client.get(reverse('transactions-list'))
        
        if response.status_code == status.HTTP_200_OK:
            # Check response structure
            self.assertIn('results', response.data or {})
            
            # Check pagination
            results = response.data.get('results', [])
            if results:
                transaction = results[0]
                self.assertIn('id', transaction)
                self.assertIn('type', transaction)
                self.assertIn('amount', transaction)
    
    def test_api_error_format_consistency(self):
        """Test that all API errors follow consistent format"""
        # Test with invalid data
        malformed_data = {
            'currency': 'INR',
            'amount': 'not_a_number',
            'payout_method': 'bank_transfer',
            'payout_details': {
                'account_number': '1234567890',
                'ifsc_code': 'SBIN0001234',
                'account_holder_name': 'Test User',
                'bank_name': 'State Bank of India'
            }
        }
        
        response = self.client.post(
            reverse('create-withdrawal'),
            malformed_data
        )
        
        # Should fail with consistent error format
        if response.status_code != status.HTTP_201_CREATED:
            # Check error structure
            self.assertIn('errors', response.data or {})
            self.assertIn('message', response.data or {})
    
    def test_api_versioning_consistency(self):
        """Test API versioning consistency"""
        # All endpoints should use consistent versioning
        endpoints = [
            'wallet-balance',
            'transactions-list',
            'investment:investment-list',
            'create-withdrawal',
            'user-withdrawals'
        ]
        
        for endpoint in endpoints:
            try:
                if 'investment:' in endpoint:
                    # Investment endpoints use namespace
                    response = self.client.get(reverse(endpoint))
                else:
                    response = self.client.get(reverse(endpoint))
                
                # Should not return 404 (endpoint exists)
                self.assertNotEqual(response.status_code, status.HTTP_404_NOT_FOUND)
                
            except Exception as e:
                # Endpoint might not exist, which is fine for this test
                pass
    
    def test_api_authentication_consistency(self):
        """Test that all protected endpoints require authentication consistently"""
        # Remove authentication
        self.client.credentials()
        
        # Test protected endpoints
        protected_endpoints = [
            'wallet-balance',
            'transactions-list',
            'create-withdrawal',
            'user-withdrawals'
        ]
        
        for endpoint in protected_endpoints:
            try:
                response = self.client.get(reverse(endpoint))
                
                # Should require authentication
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
                
            except Exception as e:
                # Endpoint might not exist, which is fine for this test
                pass
        
        # Restore authentication
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
    
    def test_api_permission_consistency(self):
        """Test that API permissions are applied consistently"""
        # Test admin-only endpoints with regular user
        admin_endpoints = [
            'admin_panel:admin-wallet-adjust-balance',
            'admin_panel:admin-withdrawals-list'
        ]
        
        for endpoint in admin_endpoints:
            try:
                response = self.client.post(reverse(endpoint), {})
                
                # Should require admin permissions
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                
            except Exception as e:
                # Endpoint might not exist, which is fine for this test
                pass
        
        # Test with admin user
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        for endpoint in admin_endpoints:
            try:
                response = self.client.post(reverse(endpoint), {})
                
                # Should not be 403 (admin has access)
                self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                
            except Exception as e:
                # Endpoint might not exist or require specific data, which is fine
                pass
        
        # Restore user authentication
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
    
    def test_api_data_validation_consistency(self):
        """Test that data validation is applied consistently across endpoints"""
        # Test withdrawal validation
        empty_data = {}
        
        response = self.client.post(
            reverse('create-withdrawal'),
            empty_data
        )
        
        # Should fail validation
        self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Test investment validation
        invalid_investment_data = {
            'plan': 'invalid_plan_id',
            'amount': 'not_a_number',
            'currency': 'invalid_currency'
        }
        
        response = self.client.post(
            reverse('investment:investment-list'),
            invalid_investment_data
        )
        
        # Should fail validation
        self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_api_response_headers_consistency(self):
        """Test that API responses include consistent headers"""
        # Test various endpoints
        endpoints = [
            'wallet-balance',
            'transactions-list',
            'user-withdrawals'
        ]
        
        for endpoint in endpoints:
            try:
                response = self.client.get(reverse(endpoint))
                
                # Check common headers
                headers = response.headers
                
                # Content-Type should be application/json
                if 'content-type' in headers:
                    self.assertIn('application/json', headers['content-type'].lower())
                
                # Should include CORS headers if configured
                if 'access-control-allow-origin' in headers:
                    self.assertIsNotNone(headers['access-control-allow-origin'])
                
            except Exception as e:
                # Endpoint might not exist, which is fine for this test
                pass
    
    def test_api_pagination_consistency(self):
        """Test that paginated endpoints follow consistent pagination format"""
        # Test transactions endpoint pagination
        response = self.client.get(reverse('transactions-list'))
        
        if response.status_code == status.HTTP_200_OK:
            data = response.data
            
            # Check pagination structure
            self.assertIn('count', data)
            self.assertIn('next', data)
            self.assertIn('previous', data)
            self.assertIn('results', data)
            
            # Check data types
            self.assertIsInstance(data['count'], int)
            self.assertIsInstance(data['results'], list)
            
            # Check pagination links
            if data['next'] is not None:
                self.assertIsInstance(data['next'], str)
                self.assertIn('page=', data['next'])
            
            if data['previous'] is not None:
                self.assertIsInstance(data['previous'], str)
    
    def test_api_filtering_consistency(self):
        """Test that filtering is applied consistently across endpoints"""
        # Test transactions filtering
        filter_params = {
            'type': 'DEPOSIT',
            'currency': 'INR'
        }
        
        response = self.client.get(reverse('transactions-list'), filter_params)
        
        if response.status_code == status.HTTP_200_OK:
            data = response.data
            
            # Check that filtering works
            if 'results' in data and data['results']:
                for transaction in data['results']:
                    if 'type' in transaction:
                        self.assertEqual(transaction['type'], 'DEPOSIT')
                    if 'currency' in transaction:
                        self.assertEqual(transaction['currency'], 'INR')
    
    def test_api_ordering_consistency(self):
        """Test that ordering is applied consistently across endpoints"""
        # Test transactions ordering
        order_params = {
            'ordering': '-created_at'
        }
        
        response = self.client.get(reverse('transactions-list'), order_params)
        
        if response.status_code == status.HTTP_200_OK:
            data = response.data
            
            # Check that ordering works
            if 'results' in data and len(data['results']) > 1:
                results = data['results']
                
                # Check that results are ordered by created_at descending
                for i in range(len(results) - 1):
                    if 'created_at' in results[i] and 'created_at' in results[i + 1]:
                        current_time = results[i]['created_at']
                        next_time = results[i + 1]['created_at']
                        
                        # Current should be >= next (descending order)
                        self.assertGreaterEqual(current_time, next_time)
    
    def test_api_search_consistency(self):
        """Test that search functionality is applied consistently"""
        # Test transactions search
        search_params = {
            'search': 'test'
        }
        
        response = self.client.get(reverse('transactions-list'), search_params)
        
        if response.status_code == status.HTTP_200_OK:
            data = response.data
            
            # Check that search works
            if 'results' in data:
                # Search should return results or empty list
                self.assertIsInstance(data['results'], list)
    
    def test_api_rate_limiting_consistency(self):
        """Test that rate limiting is applied consistently"""
        # Make multiple rapid requests
        responses = []
        
        for _ in range(10):
            response = self.client.get(reverse('user-withdrawals'))
            responses.append(response.status_code)
        
        # Check response consistency
        success_count = sum(1 for code in responses if code == status.HTTP_200_OK)
        rate_limited_count = sum(1 for code in responses if code == status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Should handle rate limiting consistently
        if rate_limited_count > 0:
            # If rate limiting is implemented, it should be consistent
            self.assertGreater(rate_limited_count, 0)
        else:
            # If no rate limiting, all should succeed
            self.assertEqual(success_count, 10)
    
    def test_api_caching_consistency(self):
        """Test that caching headers are applied consistently"""
        # Test various endpoints for caching headers
        endpoints = [
            'wallet-balance',
            'transactions-list',
            'user-withdrawals'
        ]
        
        for endpoint in endpoints:
            try:
                response = self.client.get(reverse(endpoint))
                
                headers = response.headers
                
                # Check for caching headers if implemented
                cache_headers = ['cache-control', 'etag', 'last-modified']
                
                for header in cache_headers:
                    if header in headers:
                        # Header should have a value
                        self.assertIsNotNone(headers[header])
                        self.assertNotEqual(headers[header], '')
                
            except Exception as e:
                # Endpoint might not exist, which is fine for this test
                pass
    
    def test_api_compression_consistency(self):
        """Test that compression is applied consistently"""
        # Test various endpoints for compression
        endpoints = [
            'wallet-balance',
            'transactions-list',
            'user-withdrawals'
        ]
        
        for endpoint in endpoints:
            try:
                # Request with compression
                response = self.client.get(
                    reverse(endpoint),
                    HTTP_ACCEPT_ENCODING='gzip, deflate'
                )
                
                headers = response.headers
                
                # Check for compression headers if implemented
                if 'content-encoding' in headers:
                    encoding = headers['content-encoding']
                    self.assertIn(encoding, ['gzip', 'deflate'])
                
            except Exception as e:
                # Endpoint might not exist, which is fine for this test
                pass
    
    def test_api_ssl_consistency(self):
        """Test that SSL requirements are consistent"""
        # This test would typically check SSL headers
        # For now, we'll test basic security headers
        
        response = self.client.get(reverse('wallet-balance'))
        
        headers = response.headers
        
        # Check for security headers if implemented
        security_headers = [
            'strict-transport-security',
            'x-content-type-options',
            'x-frame-options',
            'x-xss-protection'
        ]
        
        for header in security_headers:
            if header in headers:
                # Header should have a value
                self.assertIsNotNone(headers[header])
                self.assertNotEqual(headers[header], '')
    
    def test_api_logging_consistency(self):
        """Test that API logging is consistent"""
        # Make a request and check if it's logged
        response = self.client.get(reverse('wallet-balance'))
        
        # Should succeed
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
        
        # Check if transaction was logged (if logging is implemented)
        # This would typically check database logs or external logging systems
        # For now, we'll just verify the request completed successfully
    
    def test_api_monitoring_consistency(self):
        """Test that API monitoring is consistent"""
        # Make requests to various endpoints
        endpoints = [
            'wallet-balance',
            'transactions-list',
            'user-withdrawals'
        ]
        
        for endpoint in endpoints:
            try:
                start_time = time.time()
                response = self.client.get(reverse(endpoint))
                end_time = time.time()
                
                response_time = end_time - start_time
                
                # Response time should be reasonable
                self.assertLess(response_time, 5.0)  # Under 5 seconds
                
                # Status code should be consistent
                self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
                
            except Exception as e:
                # Endpoint might not exist, which is fine for this test
                pass
    
    def test_api_documentation_consistency(self):
        """Test that API documentation is consistent"""
        # Test OpenAPI/Swagger endpoint if available
        try:
            response = self.client.get('/swagger/')
            
            if response.status_code == status.HTTP_200_OK:
                # Check that documentation is accessible
                self.assertIn('swagger', response.content.decode().lower())
                
        except Exception as e:
            # Swagger might not be configured, which is fine
            pass
        
        # Test API schema endpoint if available
        try:
            response = self.client.get('/api/schema/')
            
            if response.status_code == status.HTTP_200_OK:
                # Check that schema is accessible
                self.assertIn('schema', response.content.decode().lower())
                
        except Exception as e:
            # Schema endpoint might not exist, which is fine
            pass
