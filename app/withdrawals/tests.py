from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from decimal import Decimal
import json

from .models import Withdrawal

User = get_user_model()


class WithdrawalModelTest(TestCase):
    """Test cases for Withdrawal model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            kyc_status='APPROVED'
        )
    
    def test_withdrawal_creation(self):
        """Test withdrawal creation with valid data."""
        payout_details = {'upi_id': 'test@paytm'}
        
        withdrawal = Withdrawal.objects.create(
            user=self.user,
            currency='INR',
            amount=Decimal('1000.00'),
            fee=Decimal('0.00'),
            payout_method='upi',
            payout_details=json.dumps(payout_details)
        )
        
        self.assertEqual(withdrawal.user, self.user)
        self.assertEqual(withdrawal.currency, 'INR')
        self.assertEqual(withdrawal.amount, Decimal('1000.00'))
        self.assertEqual(withdrawal.status, 'PENDING')
    
    def test_withdrawal_fee_calculation(self):
        """Test withdrawal fee calculation."""
        # INR withdrawal (no fee)
        inr_fee = Withdrawal.calculate_fee('INR', Decimal('1000.00'))
        self.assertEqual(inr_fee, Decimal('0.000000'))
        
        # USDT withdrawal (1% + $2 fixed)
        usdt_fee = Withdrawal.calculate_fee('USDT', Decimal('100.000000'))
        expected_fee = Decimal('3.000000')  # 1% of 100 + $2 fixed
        self.assertEqual(usdt_fee, expected_fee)
    
    def test_withdrawal_limits(self):
        """Test withdrawal limits checking."""
        limits = Withdrawal.get_withdrawal_limits()
        
        self.assertIn('INR', limits)
        self.assertIn('USDT', limits)
        
        inr_limits = limits['INR']
        self.assertEqual(inr_limits['min'], 100.00)
        self.assertEqual(inr_limits['max'], 500000.00)
        
        usdt_limits = limits['USDT']
        self.assertEqual(usdt_limits['min'], 10.000000)
        self.assertEqual(usdt_limits['max'], 50000.000000)


class WithdrawalAPITest(APITestCase):
    """Test cases for withdrawal API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            kyc_status='APPROVED'
        )
        
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
    
    def test_withdrawal_limits_endpoint(self):
        """Test withdrawal limits API endpoint."""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get('/api/v1/withdrawals/limits/', {'currency': 'INR'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('limits', response.data['data'])
    
    def test_unauthorized_access(self):
        """Test unauthorized access to withdrawal endpoints."""
        response = self.client.post('/api/v1/withdraw/', {})
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)