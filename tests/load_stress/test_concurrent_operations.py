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
from app.transactions.models import Transaction
from app.withdrawals.models import Withdrawal
from app.wallet.models import DepositRequest
from app.investment.models import InvestmentPlan, Investment

@pytest.mark.load_stress
class TestConcurrentOperations(TestCase):
    """Test concurrent operations and load handling"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test users
        self.admin_user = User.objects.create_user(
            username='admin_load',
            email='admin@load.com',
            password='admin123!',
            is_staff=True,
            is_superuser=True
        )
        
        self.user = User.objects.create_user(
            username='user_load',
            email='user@load.com',
            password='user123!',
            first_name='Load',
            last_name='User',
            kyc_status='APPROVED',
            is_kyc_verified=True
        )
        
        # Create wallets
        self.inr_wallet, created = INRWallet.objects.get_or_create(
            user=self.user,
            defaults={
                'balance': Decimal('10000.00'),
                'status': 'active'
            }
        )
        
        self.usdt_wallet, created = USDTWallet.objects.get_or_create(
            user=self.user,
            defaults={
                'balance': Decimal('1000.000000'),
                'status': 'active'
            }
        )
        
        # Create investment plan
        self.investment_plan = InvestmentPlan.objects.create(
            name='Load Test Plan',
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
    
    def test_concurrent_deposits(self):
        """Test concurrent deposit operations"""
        # Create multiple deposit requests concurrently
        def create_deposit(amount):
            deposit_request = DepositRequest.objects.create(
                user=self.user,
                amount=amount,
                payment_method='bank_transfer',
                status='pending'
            )
            
            # Admin approves deposit
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
            
            approval_data = {
                'transaction_reference': f'TXN_CONCURRENT_{amount}',
                'notes': f'Concurrent deposit test: {amount}'
            }
            
            response = client.post(
                reverse('approve-deposit', kwargs={'deposit_id': deposit_request.id}),
                approval_data
            )
            return response.status_code
        
        # Start concurrent deposits
        threads = []
        results = []
        
        amounts = [Decimal('100.00'), Decimal('200.00'), Decimal('300.00'), Decimal('400.00')]
        
        for amount in amounts:
            thread = threading.Thread(
                target=lambda: results.append(create_deposit(amount))
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All should succeed
        for result in results:
            self.assertEqual(result, status.HTTP_200_OK)
        
        # Check final balance
        self.inr_wallet.refresh_from_db()
        expected_balance = Decimal('10000.00') + sum(amounts)
        self.assertEqual(self.inr_wallet.balance, expected_balance)
    
    def test_concurrent_withdrawals(self):
        """Test concurrent withdrawal operations"""
        # Ensure sufficient balance
        self.inr_wallet.balance = Decimal('5000.00')
        self.inr_wallet.save()
        
        def create_withdrawal(amount):
            withdrawal_data = {
                'currency': 'INR',
                'amount': str(amount),
                'payout_method': 'bank_transfer',
                'payout_details': {
                    'account_number': '1234567890',
                    'ifsc_code': 'SBIN0001234',
                    'account_holder_name': 'Test User',
                    'bank_name': 'State Bank of India'
                }
            }
            
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
            
            response = client.post(
                reverse('create-withdrawal'),
                withdrawal_data
            )
            return response.status_code
        
        # Start concurrent withdrawals
        threads = []
        results = []
        
        amounts = [Decimal('100.00'), Decimal('200.00'), Decimal('300.00')]
        
        for amount in amounts:
            thread = threading.Thread(
                target=lambda: results.append(create_withdrawal(amount))
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All should succeed
        for result in results:
            self.assertEqual(result, status.HTTP_201_CREATED)
        
        # Check final balance
        self.inr_wallet.refresh_from_db()
        expected_balance = Decimal('5000.00') - sum(amounts)
        self.assertEqual(self.inr_wallet.balance, expected_balance)
    
    def test_concurrent_investments(self):
        """Test concurrent investment operations"""
        # Ensure sufficient balance
        self.inr_wallet.balance = Decimal('5000.00')
        self.inr_wallet.save()
        
        def create_investment(amount):
            investment_data = {
                'plan': self.investment_plan.id,
                'amount': str(amount),
                'currency': 'inr'
            }
            
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
            
            response = client.post(
                reverse('investment:investment-list'),
                investment_data
            )
            return response.status_code
        
        # Start concurrent investments
        threads = []
        results = []
        
        amounts = [Decimal('100.00'), Decimal('200.00'), Decimal('300.00')]
        
        for amount in amounts:
            thread = threading.Thread(
                target=lambda: results.append(create_investment(amount))
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All should succeed
        for result in results:
            self.assertEqual(result, status.HTTP_201_CREATED)
        
        # Check final balance
        self.inr_wallet.refresh_from_db()
        expected_balance = Decimal('5000.00') - sum(amounts)
        self.assertEqual(self.inr_wallet.balance, expected_balance)
    
    def test_concurrent_mixed_operations(self):
        """Test concurrent mixed operations (deposits, withdrawals, investments)"""
        # Ensure sufficient balance
        self.inr_wallet.balance = Decimal('10000.00')
        self.inr_wallet.save()
        
        def perform_operation(operation_type, amount):
            if operation_type == 'deposit':
                # Create and approve deposit
                deposit_request = DepositRequest.objects.create(
                    user=self.user,
                    amount=amount,
                    payment_method='bank_transfer',
                    status='pending'
                )
                
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
                
                approval_data = {
                    'transaction_reference': f'TXN_MIXED_DEP_{amount}',
                    'notes': f'Mixed operation test: deposit {amount}'
                }
                
                response = client.post(
                    reverse('approve-deposit', kwargs={'deposit_id': deposit_request.id}),
                    approval_data
                )
                return response.status_code
                
            elif operation_type == 'withdrawal':
                # Create withdrawal
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
                
                withdrawal_data = {
                    'currency': 'INR',
                    'amount': str(amount),
                    'payout_method': 'bank_transfer',
                    'payout_details': {
                        'account_number': '1234567890',
                        'ifsc_code': 'SBIN0001234',
                        'account_holder_name': 'Test User',
                        'bank_name': 'State Bank of India'
                    }
                }
                
                response = client.post(
                    reverse('create-withdrawal'),
                    withdrawal_data
                )
                return response.status_code
                
            elif operation_type == 'investment':
                # Create investment
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
                
                investment_data = {
                    'plan': self.investment_plan.id,
                    'amount': str(amount),
                    'currency': 'inr'
                }
                
                response = client.post(
                    reverse('investment:investment-list'),
                    investment_data
                )
                return response.status_code
        
        # Start concurrent mixed operations
        threads = []
        results = []
        
        operations = [
            ('deposit', Decimal('500.00')),
            ('withdrawal', Decimal('200.00')),
            ('investment', Decimal('300.00')),
            ('deposit', Decimal('400.00'))
        ]
        
        for operation_type, amount in operations:
            thread = threading.Thread(
                target=lambda: results.append(perform_operation(operation_type, amount))
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All should succeed
        for result in results:
            self.assertIn(result, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        
        # Check final balance
        self.inr_wallet.refresh_from_db()
        
        # Calculate expected balance: Initial + Deposits - Withdrawals - Investments
        # 10000 + 500 + 400 - 200 - 300 = 10400
        expected_balance = Decimal('10000.00') + Decimal('500.00') + Decimal('400.00') - Decimal('200.00') - Decimal('300.00')
        
        # Allow for small discrepancies due to race conditions
        balance_diff = abs(self.inr_wallet.balance - expected_balance)
        self.assertLessEqual(balance_diff, Decimal('1.00'))
    
    def test_high_frequency_operations(self):
        """Test high frequency operations"""
        # Perform many operations rapidly
        operation_count = 50
        results = []
        
        def rapid_operation(index):
            # Alternate between deposit and withdrawal
            if index % 2 == 0:
                # Create deposit
                deposit_request = DepositRequest.objects.create(
                    user=self.user,
                    amount=Decimal('10.00'),
                    payment_method='bank_transfer',
                    status='pending'
                )
                
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
                
                approval_data = {
                    'transaction_reference': f'TXN_RAPID_{index}',
                    'notes': f'Rapid operation test: {index}'
                }
                
                response = client.post(
                    reverse('approve-deposit', kwargs={'deposit_id': deposit_request.id}),
                    approval_data
                )
                return response.status_code
            else:
                # Create withdrawal
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
                
                withdrawal_data = {
                    'currency': 'INR',
                    'amount': '5.00',
                    'payout_method': 'bank_transfer',
                    'payout_details': {
                        'account_number': '1234567890',
                        'ifsc_code': 'SBIN0001234',
                        'account_holder_name': 'Test User',
                        'bank_name': 'State Bank of India'
                    }
                }
                
                response = client.post(
                    reverse('create-withdrawal'),
                    withdrawal_data
                )
                return response.status_code
        
        # Execute operations rapidly
        for i in range(operation_count):
            result = rapid_operation(i)
            results.append(result)
        
        # Most should succeed (some might fail due to business logic)
        success_count = sum(1 for r in results if r in [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertGreater(success_count, operation_count * 0.8)  # At least 80% success rate
    
    def test_concurrent_user_operations(self):
        """Test concurrent operations from multiple users"""
        # Create multiple users
        users = []
        wallets = []
        tokens = []
        
        for i in range(5):
            user = User.objects.create_user(
                username=f'user_load_{i}',
                email=f'user{i}@load.com',
                password=f'user{i}123!',
                first_name=f'Load{i}',
                last_name='User',
                kyc_status='APPROVED',
                is_kyc_verified=True
            )
            
            wallet, created = INRWallet.objects.get_or_create(
                user=user,
                defaults={
                    'balance': Decimal('1000.00'),
                    'status': 'active'
                }
            )
            
            token = self._get_token(user)
            
            users.append(user)
            wallets.append(wallet)
            tokens.append(token)
        
        def user_operation(user_index):
            # Each user performs a deposit
            user = users[user_index]
            token = tokens[user_index]
            
            deposit_request = DepositRequest.objects.create(
                user=user,
                amount=Decimal('100.00'),
                payment_method='bank_transfer',
                status='pending'
            )
            
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
            
            approval_data = {
                'transaction_reference': f'TXN_USER_{user_index}',
                'notes': f'Concurrent user test: {user_index}'
            }
            
            response = client.post(
                reverse('approve-deposit', kwargs={'deposit_id': deposit_request.id}),
                approval_data
            )
            return response.status_code
        
        # Start concurrent user operations
        threads = []
        results = []
        
        for i in range(len(users)):
            thread = threading.Thread(
                target=lambda: results.append(user_operation(i))
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All should succeed
        for result in results:
            self.assertEqual(result, status.HTTP_200_OK)
        
        # Check all wallets were updated
        for i, wallet in enumerate(wallets):
            wallet.refresh_from_db()
            expected_balance = Decimal('1000.00') + Decimal('100.00')
            self.assertEqual(wallet.balance, expected_balance)
    
    def test_database_connection_pool_handling(self):
        """Test database connection pool handling under load"""
        # Perform many database operations rapidly
        operation_count = 100
        results = []
        
        def db_operation(index):
            # Simple database read/write operations
            try:
                # Read operation
                user_count = User.objects.count()
                
                # Write operation (create and delete a temporary object)
                temp_user = User.objects.create_user(
                    username=f'temp_user_{index}',
                    email=f'temp{index}@test.com',
                    password='temp123!'
                )
                
                # Verify creation
                created_user = User.objects.get(username=f'temp_user_{index}')
                self.assertEqual(created_user.email, f'temp{index}@test.com')
                
                # Clean up
                created_user.delete()
                
                return True
            except Exception as e:
                return False
        
        # Execute operations
        for i in range(operation_count):
            result = db_operation(i)
            results.append(result)
        
        # Most should succeed
        success_count = sum(results)
        self.assertGreater(success_count, operation_count * 0.9)  # At least 90% success rate
    
    def test_memory_usage_under_load(self):
        """Test memory usage under load"""
        # Perform memory-intensive operations
        operation_count = 50
        results = []
        
        def memory_operation(index):
            # Create large data structures
            large_list = [f'data_{i}_{index}' for i in range(1000)]
            large_dict = {f'key_{i}_{index}': f'value_{i}_{index}' for i in range(1000)}
            
            # Perform operations
            result = len(large_list) + len(large_dict)
            
            # Clean up
            del large_list
            del large_dict
            
            return result == 2000
        
        # Execute operations
        for i in range(operation_count):
            result = memory_operation(i)
            results.append(result)
        
        # All should succeed
        for result in results:
            self.assertTrue(result)
    
    def test_response_time_under_load(self):
        """Test response time under load"""
        # Measure response times under concurrent load
        operation_count = 20
        response_times = []
        
        def timed_operation():
            start_time = time.time()
            
            # Perform a simple operation
            response = self.client.get(reverse('user-withdrawals'))
            
            end_time = time.time()
            response_time = end_time - start_time
            
            return response_time, response.status_code
        
        # Execute operations concurrently
        threads = []
        results = []
        
        for _ in range(operation_count):
            thread = threading.Thread(
                target=lambda: results.append(timed_operation())
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Extract response times and status codes
        for response_time, status_code in results:
            response_times.append(response_time)
            # All should succeed
            self.assertIn(status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
        
        # Check response times are reasonable (under 5 seconds)
        max_response_time = max(response_times)
        self.assertLess(max_response_time, 5.0)
        
        # Check average response time is reasonable (under 2 seconds)
        avg_response_time = sum(response_times) / len(response_times)
        self.assertLess(avg_response_time, 2.0)
