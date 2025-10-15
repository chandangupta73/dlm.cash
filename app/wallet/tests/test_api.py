from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
import uuid
import json

from app.wallet.models import (
    INRWallet, USDTWallet, WalletAddress, WalletTransaction, 
    DepositRequest, USDTDepositRequest
)
from app.wallet.signals import create_user_wallets, save_user_wallets
from app.core.signals import create_user_wallets as core_create_user_wallets, save_user_wallets as core_save_user_wallets

User = get_user_model()


class WalletAPITest(TestCase):
    """API tests for wallet endpoints."""
    
    def setUp(self):
        """Disable wallet creation signals and set up test data."""
        # Disconnect the wallet app signals
        post_save.disconnect(create_user_wallets, sender=User)
        post_save.disconnect(save_user_wallets, sender=User)
        
        # Disconnect the core app signals
        post_save.disconnect(core_create_user_wallets, sender=User)
        post_save.disconnect(core_save_user_wallets, sender=User)
        
        # Create test users
        unique_id = str(uuid.uuid4())[:8]
        self.user = User.objects.create_user(
            username=f'apiuser_{unique_id}',
            email=f'api_{unique_id}@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_user(
            username=f'admin_{unique_id}',
            email=f'admin_{unique_id}@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Create wallets
        self.inr_wallet = INRWallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            status='active',
            is_active=True
        )
        
        self.usdt_wallet = USDTWallet.objects.create(
            user=self.user,
            balance=Decimal('500.000000'),
            wallet_address='0x1234567890abcdef1234567890abcdef12345678',
            chain_type='erc20',
            is_real_wallet=False
        )
        
        # Set up API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        """Reconnect wallet creation signals after test."""
        # Reconnect the wallet app signals
        post_save.connect(create_user_wallets, sender=User)
        post_save.connect(save_user_wallets, sender=User)
        
        # Reconnect the core app signals
        post_save.connect(core_create_user_wallets, sender=User)
        post_save.connect(core_save_user_wallets, sender=User)

    def test_wallet_balance_view(self):
        """Test wallet balance endpoint."""
        url = reverse('wallet-balance')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertIn('inr_balance', data)
        self.assertIn('usdt_balance', data)
        self.assertIn('inr_wallet_status', data)
        self.assertIn('usdt_wallet_status', data)
        
        self.assertEqual(data['inr_balance'], '1000.00')
        self.assertEqual(data['usdt_balance'], '500.000000')
        self.assertEqual(data['inr_wallet_status'], 'active')
        self.assertEqual(data['usdt_wallet_status'], 'active')

    def test_wallet_balance_view_unauthenticated(self):
        """Test wallet balance endpoint without authentication."""
        self.client.force_authenticate(user=None)
        url = reverse('wallet-balance')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wallet_transactions_viewset_list(self):
        """Test wallet transactions list endpoint."""
        # Create a transaction
        transaction = WalletTransaction.objects.create(
            user=self.user,
            transaction_type='deposit',
            wallet_type='inr',
            amount=Decimal('100.00'),
            balance_before=Decimal('0.00'),
            balance_after=Decimal('100.00'),
            status='completed',
            reference_id='REF123',
            description='Test deposit'
        )
        
        url = reverse('wallet-transaction-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertIn('results', data)
        self.assertEqual(len(data['results']), 1)
        # The serializer returns the exact decimal format from the database
        self.assertEqual(data['results'][0]['amount'], '100.000000')
        self.assertEqual(data['results'][0]['transaction_type'], 'deposit')
        self.assertEqual(data['results'][0]['wallet_type'], 'inr')

    def test_wallet_transactions_viewset_filtering(self):
        """Test wallet transactions filtering."""
        # Create transactions of different types
        WalletTransaction.objects.create(
            user=self.user,
            transaction_type='deposit',
            wallet_type='inr',
            amount=Decimal('100.00'),
            balance_before=Decimal('900.00'),
            balance_after=Decimal('1000.00'),
            status='completed',
            reference_id='REF123',
            description='Test deposit'
        )
        
        WalletTransaction.objects.create(
            user=self.user,
            transaction_type='withdrawal',
            wallet_type='inr',
            amount=Decimal('50.00'),
            balance_before=Decimal('1000.00'),
            balance_after=Decimal('950.00'),
            status='completed',
            reference_id='REF124',
            description='Test withdrawal'
        )
        
        # Test filtering by transaction type
        url = reverse('wallet-transaction-list')
        response = self.client.get(url, {'transaction_type': 'deposit'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['transaction_type'], 'deposit')
        
        # Test filtering by wallet type
        response = self.client.get(url, {'wallet_type': 'inr'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data['results']), 2)

    def test_deposit_request_viewset_create(self):
        """Test creating a deposit request."""
        url = reverse('deposit-request-list')
        data = {
            'amount': '500.00',
            'payment_method': 'bank_transfer',
            'reference_number': 'DEP123',
            'notes': 'Test deposit request'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        
        # Check only the fields that are actually returned by DepositRequestCreateSerializer
        self.assertEqual(response_data['amount'], '500.00')
        self.assertEqual(response_data['payment_method'], 'bank_transfer')
        self.assertEqual(response_data['reference_number'], 'DEP123')
        self.assertEqual(response_data['notes'], 'Test deposit request')
        
        # Check if deposit request was created in database by finding it using amount and user
        deposit = DepositRequest.objects.get(
            amount=Decimal('500.00'),
            user=self.user,
            payment_method='bank_transfer'
        )
        self.assertEqual(deposit.amount, Decimal('500.00'))
        self.assertEqual(deposit.user, self.user)
        self.assertEqual(deposit.status, 'pending')  # Check status in database

    def test_deposit_request_viewset_list(self):
        """Test listing deposit requests."""
        # Create some deposit requests
        DepositRequest.objects.create(
            user=self.user,
            amount=Decimal('100.00'),
            payment_method='upi',
            status='pending',
            reference_number='DEP123'
        )
        
        DepositRequest.objects.create(
            user=self.user,
            amount=Decimal('200.00'),
            payment_method='bank_transfer',
            status='approved',
            reference_number='DEP124'
        )
        
        url = reverse('deposit-request-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertIn('results', data)
        self.assertEqual(len(data['results']), 2)

    def test_deposit_request_viewset_retrieve(self):
        """Test retrieving a specific deposit request."""
        deposit = DepositRequest.objects.create(
            user=self.user,
            amount=Decimal('100.00'),
            payment_method='upi',
            status='pending',
            reference_number='DEP123'
        )
        
        url = reverse('deposit-request-detail', kwargs={'pk': deposit.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(data['id'], str(deposit.id))
        self.assertEqual(data['amount'], '100.00')
        self.assertEqual(data['payment_method'], 'upi')
        self.assertEqual(data['status'], 'pending')

    def test_deposit_request_viewset_update(self):
        """Test updating a deposit request."""
        deposit = DepositRequest.objects.create(
            user=self.user,
            amount=Decimal('100.00'),
            payment_method='upi',
            status='pending',
            reference_number='DEP123'
        )
        
        url = reverse('deposit-request-detail', kwargs={'pk': deposit.id})
        data = {
            'notes': 'Updated notes'
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertEqual(response_data['notes'], 'Updated notes')
        
        # Check database
        deposit.refresh_from_db()
        self.assertEqual(deposit.notes, 'Updated notes')

    def test_deposit_request_viewset_delete(self):
        """Test deleting a deposit request."""
        deposit = DepositRequest.objects.create(
            user=self.user,
            amount=Decimal('100.00'),
            payment_method='upi',
            status='pending',
            reference_number='DEP123'
        )
        
        url = reverse('deposit-request-detail', kwargs={'pk': deposit.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Check if deposit request was deleted
        self.assertFalse(DepositRequest.objects.filter(id=deposit.id).exists())

    def test_deposit_request_validation(self):
        """Test deposit request validation."""
        url = reverse('deposit-request-list')
        
        # Test invalid amount
        data = {
            'amount': '-100.00',
            'payment_method': 'bank_transfer'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test invalid payment method
        data = {
            'amount': '100.00',
            'payment_method': 'invalid_method'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_deposit_approval(self):
        """Test admin deposit approval."""
        # Create a deposit request
        deposit = DepositRequest.objects.create(
            user=self.user,
            amount=Decimal('100.00'),
            payment_method='upi',
            status='pending',
            reference_number='DEP123'
        )
        
        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('approve-deposit', kwargs={'deposit_id': deposit.id})
        
        # Use POST method as the view only accepts POST
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertIn('message', response_data)
        
        # Check database
        deposit.refresh_from_db()
        self.assertEqual(deposit.status, 'approved')
        self.assertEqual(deposit.processed_by, self.admin_user)

    def test_admin_deposit_rejection(self):
        """Test admin deposit rejection."""
        # Create a deposit request
        deposit = DepositRequest.objects.create(
            user=self.user,
            amount=Decimal('100.00'),
            payment_method='upi',
            status='pending',
            reference_number='DEP123'
        )
        
        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('reject-deposit', kwargs={'deposit_id': deposit.id})
        
        # Use POST method with reason as the view only accepts POST
        data = {'reason': 'Invalid payment proof'}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertIn('message', response_data)
        
        # Check database
        deposit.refresh_from_db()
        self.assertEqual(deposit.status, 'rejected')
        self.assertEqual(deposit.processed_by, self.admin_user)

    def test_wallet_address_endpoints(self):
        """Test wallet address related endpoints."""
        # Create wallet address
        address = WalletAddress.objects.create(
            user=self.user,
            chain_type='erc20',
            address='0x1234567890abcdef1234567890abcdef12345678',
            status='active',
            is_active=True
        )
        
        # Test getting wallet address
        url = reverse('wallet-address-by-chain', kwargs={'chain_type': 'erc20'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(data['chain_type'], 'erc20')
        self.assertEqual(data['address'], '0x1234567890abcdef1234567890abcdef12345678')
        self.assertEqual(data['status'], 'active')

    def test_wallet_address_not_found(self):
        """Test wallet address endpoint when address doesn't exist."""
        # The view always creates an address if one doesn't exist, so we expect 200
        url = reverse('wallet-address-by-chain', kwargs={'chain_type': 'erc20'})
        response = self.client.get(url)
        
        # Should return 200 since the view creates the address automatically
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('address', data)  # The field is named 'address', not 'wallet_address'

    def test_wallet_address_invalid_chain(self):
        """Test wallet address endpoint with invalid chain type."""
        url = reverse('wallet-address-by-chain', kwargs={'chain_type': 'invalid_chain'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_wallet_transaction_detail(self):
        """Test retrieving a specific wallet transaction."""
        transaction = WalletTransaction.objects.create(
            user=self.user,
            transaction_type='deposit',
            wallet_type='inr',
            amount=Decimal('100.00'),
            balance_before=Decimal('0.00'),
            balance_after=Decimal('100.00'),
            status='completed',
            reference_id='REF123',
            description='Test deposit'
        )
        
        url = reverse('wallet-transaction-detail', kwargs={'pk': transaction.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(data['id'], str(transaction.id))
        # The serializer returns the exact decimal format from the database
        self.assertEqual(data['amount'], '100.000000')
        self.assertEqual(data['transaction_type'], 'deposit')
        self.assertEqual(data['wallet_type'], 'inr')

    def test_wallet_transaction_not_found(self):
        """Test retrieving non-existent transaction."""
        fake_id = str(uuid.uuid4())
        url = reverse('wallet-transaction-detail', kwargs={'pk': fake_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_wallet_transaction_unauthorized_access(self):
        """Test accessing transaction of another user."""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        
        transaction = WalletTransaction.objects.create(
            user=other_user,
            transaction_type='deposit',
            wallet_type='inr',
            amount=Decimal('100.00'),
            balance_before=Decimal('0.00'),
            balance_after=Decimal('100.00'),
            status='completed',
            reference_id='REF123',
            description='Other user transaction'
        )
        
        url = reverse('wallet-transaction-detail', kwargs={'pk': transaction.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_pagination(self):
        """Test pagination in list endpoints."""
        # Create multiple transactions
        for i in range(25):
            WalletTransaction.objects.create(
                user=self.user,
                transaction_type='deposit',
                wallet_type='inr',
                amount=Decimal('10.00'),
                balance_before=Decimal('0.00'),
                balance_after=Decimal('10.00'),
                status='completed',
                reference_id=f'REF{i}',
                description=f'Test transaction {i}'
            )
        
        url = reverse('wallet-transaction-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertIn('count', data)
        self.assertIn('next', data)
        self.assertIn('previous', data)
        self.assertIn('results', data)
        
        self.assertEqual(data['count'], 25)
        self.assertIsNotNone(data['next'])  # Should have next page
        self.assertIsNone(data['previous'])  # First page

    def test_search_functionality(self):
        """Test filtering functionality in transaction list."""
        # Create transactions with different types
        WalletTransaction.objects.create(
            user=self.user,
            transaction_type='deposit',
            wallet_type='inr',
            amount=Decimal('100.00'),
            balance_before=Decimal('0.00'),
            balance_after=Decimal('100.00'),
            status='completed',
            reference_id='REF1',
            description='Test deposit'
        )
        
        WalletTransaction.objects.create(
            user=self.user,
            transaction_type='withdrawal',
            wallet_type='inr',
            amount=Decimal('50.00'),
            balance_before=Decimal('100.00'),
            balance_after=Decimal('50.00'),
            status='completed',
            reference_id='REF2',
            description='Test withdrawal'
        )
        
        # Test filtering by transaction type
        url = reverse('wallet-transaction-list')
        response = self.client.get(url, {'transaction_type': 'deposit'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Should only return deposit transactions
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['transaction_type'], 'deposit')
