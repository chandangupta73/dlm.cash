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
    DepositRequest, USDTDepositRequest, SweepLog
)
from app.wallet.signals import create_user_wallets, save_user_wallets
from app.core.signals import create_user_wallets as core_create_user_wallets, save_user_wallets as core_save_user_wallets
from app.wallet.services import WalletService, DepositService, TransactionService
from app.crud.wallet import WalletAddressService, USDTDepositService
from app.wallet.services import WalletValidationService

User = get_user_model()


class WalletE2ETest(TestCase):
    """End-to-end tests for complete wallet workflows."""
    
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
            username=f'e2euser_{unique_id}',
            email=f'e2e_{unique_id}@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_user(
            username=f'e2eadmin_{unique_id}',
            email=f'e2eadmin_{unique_id}@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Create wallets for the user
        self.inr_wallet = INRWallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            status='active',
            is_active=True
        )
        
        self.usdt_wallet = USDTWallet.objects.create(
            user=self.user,
            balance=Decimal('100.000000'),
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

    def test_complete_inr_deposit_workflow(self):
        """Test complete INR deposit workflow from request to balance update."""
        # Step 1: Create deposit request
        url = reverse('deposit-request-list')
        data = {
            'amount': '1000.00',
            'payment_method': 'bank_transfer',
            'reference_number': 'DEP001',
            'notes': 'Salary deposit'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Get the created deposit from database
        deposit = DepositRequest.objects.get(
            amount=Decimal('1000.00'),
            user=self.user,
            payment_method='bank_transfer'
        )
        
        # Step 2: Admin approves deposit
        self.client.force_authenticate(user=self.admin_user)
        approval_url = reverse('approve-deposit', kwargs={'deposit_id': deposit.id})
        response = self.client.post(approval_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 3: Check wallet balance was updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('2000.00'))  # 1000 + 1000
        
        # Step 4: Check transaction was created
        transaction = WalletTransaction.objects.filter(
            user=self.user,
            transaction_type='deposit',
            wallet_type='inr'
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('1000.00'))
        self.assertEqual(transaction.status, 'completed')

    def test_complete_usdt_deposit_workflow(self):
        """Test complete USDT deposit workflow from blockchain to wallet."""
        # Step 1: Use existing USDT wallet and create address
        wallet_address = WalletAddress.objects.create(
            user=self.user,
            chain_type='erc20',
            address='0x1234567890abcdef1234567890abcdef12345678',
            status='active',
            is_active=True
        )
        
        # Step 2: Create USDT deposit request
        deposit = USDTDepositRequest.objects.create(
            user=self.user,
            chain_type='erc20',
            amount=Decimal('100.000000'),
            transaction_hash='0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
            from_address='0x1111111111111111111111111111111111111111',
            to_address=wallet_address.address,
            sweep_type='auto'
        )
        
        # Step 3: Simulate deposit confirmation
        success = USDTDepositService.process_deposit_confirmation(
            deposit.id, 
            confirmation_count=12,  # Enough confirmations
            block_number=12345
        )
        
        self.assertTrue(success)
        
        # Step 4: Check deposit status
        deposit.refresh_from_db()
        # After auto-sweep, status should be 'swept', not 'confirmed'
        self.assertEqual(deposit.status, 'swept')
        
        # Step 5: Check if auto-sweep was triggered
        sweep_logs = SweepLog.objects.filter(
            user=self.user,
            chain_type='erc20'
        )
        self.assertEqual(sweep_logs.count(), 1)
        
        sweep_log = sweep_logs.first()
        self.assertEqual(sweep_log.status, 'completed')
        self.assertEqual(sweep_log.amount, Decimal('100.000000'))

    def test_complete_wallet_management_workflow(self):
        """Test complete wallet management workflow including status changes."""
        # Step 1: Test wallet status management
        # Use existing wallet
        inr_wallet = self.inr_wallet
        
        # Test wallet validation
        validation = WalletValidationService.validate_wallet_status(self.user)
        self.assertTrue(validation[0])  # First element is the boolean result
        
        # Step 2: Test wallet suspension
        inr_wallet.status = 'suspended'
        inr_wallet.save()
        
        # Test validation after suspension
        validation = WalletValidationService.validate_wallet_status(self.user)
        self.assertFalse(validation[0])  # Should be False now
        
        # Step 3: Test wallet reactivation
        inr_wallet.status = 'active'
        inr_wallet.save()
        
        # Test validation after reactivation
        validation = WalletValidationService.validate_wallet_status(self.user)
        self.assertTrue(validation[0])  # Should be True again
        
        # Step 4: Test balance operations
        # Add balance
        success = WalletService.add_inr_balance(
            self.user, 
            Decimal('500.00'), 
            'admin_adjustment',
            'Test balance addition'
        )
        self.assertTrue(success)
        
        # Check balance was updated
        inr_wallet.refresh_from_db()
        self.assertEqual(inr_wallet.balance, Decimal('1500.00'))  # 1000 + 500
        
        # Deduct balance
        success = WalletService.deduct_inr_balance(
            self.user, 
            Decimal('200.00'), 
            'withdrawal',
            'Test balance deduction'
        )
        self.assertTrue(success)
        
        # Check balance was updated
        inr_wallet.refresh_from_db()
        self.assertEqual(inr_wallet.balance, Decimal('1300.00'))  # 1500 - 200
        
        # Step 5: Test transaction logging
        transactions = WalletTransaction.objects.filter(
            user=self.user,
            wallet_type='inr'
        ).order_by('-created_at')
        
        self.assertEqual(transactions.count(), 2)
        
        # Check first transaction (deduction)
        deduction_tx = transactions[0]
        self.assertEqual(deduction_tx.transaction_type, 'withdrawal')
        self.assertEqual(deduction_tx.amount, Decimal('200.00'))
        self.assertEqual(deduction_tx.status, 'completed')
        
        # Check second transaction (addition)
        addition_tx = transactions[1]
        self.assertEqual(addition_tx.transaction_type, 'admin_adjustment')
        self.assertEqual(addition_tx.amount, Decimal('500.00'))
        self.assertEqual(addition_tx.status, 'completed')

    def test_complete_multi_chain_workflow(self):
        """Test complete multi-chain workflow including address management."""
        # Step 1: Create wallet addresses for multiple chains
        # Use addresses with exactly 42 characters (including 0x prefix)
        erc20_address = WalletAddress.objects.create(
            user=self.user,
            chain_type='erc20',
            address='0x1234567890abcdef1234567890abcdef12345678',
            status='active',
            is_active=True
        )
        
        bep20_address = WalletAddress.objects.create(
            user=self.user,
            chain_type='bep20',
            address='0x876543210fedcba9876543210fedcba987654321',
            status='active',
            is_active=True
        )
        
        # Step 2: Test address retrieval
        addresses = WalletAddressService.get_all_wallet_addresses(self.user)
        self.assertEqual(addresses.count(), 2)
        
        # Step 3: Test address validation
        # Verify address lengths
        self.assertEqual(len(erc20_address.address), 42)
        self.assertEqual(len(bep20_address.address), 42)
        
        valid_erc20 = WalletAddressService.validate_address(
            '0x1234567890abcdef1234567890abcdef12345678', 'erc20'
        )
        self.assertTrue(valid_erc20)
        
        valid_bep20 = WalletAddressService.validate_address(
            '0x876543210fedcba9876543210fedcba987654321', 'bep20'
        )
        self.assertTrue(valid_bep20)
        
        # Step 4: Test invalid addresses
        invalid_address = WalletAddressService.validate_address(
            'invalid_address', 'erc20'
        )
        self.assertFalse(invalid_address)
        
        # Step 5: Test address uniqueness constraints
        # Create a different user to test the unique constraint
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        # This should work since it's a different user
        other_address = WalletAddress.objects.create(
            user=other_user,
            chain_type='erc20',
            address='0x9999999999999999999999999999999999999999',
            status='active',
            is_active=True
        )
        
        # This should fail due to unique constraint (same user, same chain type)
        with self.assertRaises(Exception):
            WalletAddress.objects.create(
                user=self.user,
                chain_type='erc20',  # Same chain type for same user
                address='0x9999999999999999999999999999999999999999',
                status='active',
                is_active=True
            )

    def test_complete_error_handling_workflow(self):
        """Test complete error handling workflow including edge cases."""
        # Step 1: Use existing wallet with limited balance
        inr_wallet = self.inr_wallet
        # Reset balance to 100 for testing
        inr_wallet.balance = Decimal('100.00')
        inr_wallet.save()
        
        # Step 2: Test insufficient balance
        with self.assertRaises(ValueError):
            WalletService.deduct_inr_balance(
                self.user, 
                Decimal('200.00'), 
                'withdrawal'
            )
        
        # Step 3: Test negative amount
        with self.assertRaises(ValueError):
            WalletService.add_inr_balance(
                self.user, 
                Decimal('-50.00'), 
                'admin_adjustment'
            )
        
        # Step 4: Test inactive wallet
        inr_wallet.is_active = False
        inr_wallet.save()
        
        with self.assertRaises(ValueError):
            WalletService.add_inr_balance(
                self.user, 
                Decimal('100.00'), 
                'admin_adjustment'
            )
        
        # Step 5: Test suspended wallet
        inr_wallet.is_active = True
        inr_wallet.status = 'suspended'
        inr_wallet.save()
        
        with self.assertRaises(ValueError):
            WalletService.add_inr_balance(
                self.user, 
                Decimal('100.00'), 
                'admin_adjustment'
            )
        
        # Step 6: Verify wallet balance unchanged
        inr_wallet.refresh_from_db()
        self.assertEqual(inr_wallet.balance, Decimal('100.00'))

    def test_complete_transaction_reporting_workflow(self):
        """Test complete transaction reporting and summary workflow."""
        # Create multiple transactions
        transaction_types = ['deposit', 'withdrawal', 'admin_adjustment']
        for i, tx_type in enumerate(transaction_types):
            WalletTransaction.objects.create(
                user=self.user,
                transaction_type=tx_type,
                wallet_type='inr',
                amount=Decimal('100.00'),
                balance_before=Decimal('1000.00') + Decimal(i * 100),
                balance_after=Decimal('1000.00') + Decimal((i + 1) * 100),
                status='completed',
                reference_id=f'REF{i}',
                description=f'Test {tx_type} transaction'
            )
        
        # Test transaction list endpoint
        transactions_url = reverse('wallet-transaction-list')
        response = self.client.get(transactions_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertEqual(len(data['results']), 3)
        
        # Test transaction summary endpoint
        summary_url = reverse('transaction-summary')
        response = self.client.get(summary_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        summary_data = response.json()
        # Check summary data matches what TransactionService.get_transaction_summary returns
        self.assertEqual(summary_data['transaction_count'], 3)
        self.assertEqual(summary_data['total_deposits'], Decimal('100.00'))
        self.assertEqual(summary_data['total_withdrawals'], Decimal('100.00'))
        self.assertEqual(summary_data['total_roi'], Decimal('0.00'))

    def test_complete_admin_workflow(self):
        """Test complete admin workflow including deposit management."""
        # Create multiple deposit requests
        deposit1 = DepositRequest.objects.create(
            user=self.user,
            amount=Decimal('500.00'),
            payment_method='upi',
            status='pending',
            reference_number='DEP001'
        )
        
        deposit2 = DepositRequest.objects.create(
            user=self.user,
            amount=Decimal('750.00'),
            payment_method='bank_transfer',
            status='pending',
            reference_number='DEP002'
        )
        
        # Admin approves first deposit
        self.client.force_authenticate(user=self.admin_user)
        approval_url = reverse('approve-deposit', kwargs={'deposit_id': deposit1.id})
        response = self.client.post(approval_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Admin rejects second deposit
        rejection_url = reverse('reject-deposit', kwargs={'deposit_id': deposit2.id})
        rejection_data = {'reason': 'Invalid payment proof'}
        response = self.client.post(rejection_url, rejection_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check database states
        deposit1.refresh_from_db()
        deposit2.refresh_from_db()
        
        self.assertEqual(deposit1.status, 'approved')
        self.assertEqual(deposit1.processed_by, self.admin_user)
        self.assertEqual(deposit2.status, 'rejected')
        self.assertEqual(deposit2.processed_by, self.admin_user)
        
        # Check wallet balance was updated for approved deposit
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('1500.00'))  # 1000 + 500
        
        # Check transactions were created
        approved_transaction = WalletTransaction.objects.filter(
            user=self.user,
            transaction_type='deposit',
            wallet_type='inr',
            amount=Decimal('500.00')
        ).first()
        self.assertIsNotNone(approved_transaction)
        self.assertEqual(approved_transaction.status, 'completed')
