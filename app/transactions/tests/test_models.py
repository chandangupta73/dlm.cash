import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.contrib.auth import get_user_model

from app.transactions.models import Transaction
from app.transactions.tests.conftest import (
    UserFactory, TransactionFactory, DepositTransactionFactory,
    WithdrawalTransactionFactory, ROITransactionFactory
)

User = get_user_model()


class TransactionModelTest(TestCase):
    """Test cases for the Transaction model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.transaction = TransactionFactory(user=self.user)
    
    def test_transaction_creation(self):
        """Test that transactions can be created successfully."""
        transaction = Transaction.objects.create(
            user=self.user,
            type='DEPOSIT',
            currency='INR',
            amount=Decimal('100.00'),
            reference_id='test_ref_123',
            meta_data={'test_key': 'test_value'},
            status='SUCCESS'
        )
        
        self.assertIsNotNone(transaction.id)
        self.assertEqual(transaction.user, self.user)
        self.assertEqual(transaction.type, 'DEPOSIT')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertEqual(transaction.reference_id, 'test_ref_123')
        self.assertEqual(transaction.meta_data, {'test_key': 'test_value'})
        self.assertEqual(transaction.status, 'SUCCESS')
    
    def test_transaction_string_representation(self):
        """Test the string representation of transactions."""
        transaction = TransactionFactory(
            user=self.user,
            type='DEPOSIT',
            currency='INR',
            amount=Decimal('100.00')
        )
        
        expected_str = f"DEPOSIT - {self.user.username} (INR 100.00) - {transaction.status}"
        self.assertEqual(str(transaction), expected_str)
    
    def test_formatted_amount_property(self):
        """Test the formatted_amount property for different currencies."""
        # Test INR formatting
        inr_transaction = TransactionFactory(
            user=self.user,
            currency='INR',
            amount=Decimal('1234.56')
        )
        self.assertEqual(inr_transaction.formatted_amount, '₹1,234.56')
        
        # Test USDT formatting
        usdt_transaction = TransactionFactory(
            user=self.user,
            currency='USDT',
            amount=Decimal('1234.567890')
        )
        self.assertEqual(usdt_transaction.formatted_amount, '$1,234.567890')
    
    def test_is_credit_property(self):
        """Test the is_credit property for different transaction types."""
        credit_types = ['DEPOSIT', 'ROI', 'REFERRAL_BONUS', 'MILESTONE_BONUS', 'ADMIN_ADJUSTMENT', 'BREAKDOWN_REFUND']
        debit_types = ['WITHDRAWAL', 'PLAN_PURCHASE']
        
        for transaction_type in credit_types:
            transaction = TransactionFactory(user=self.user, type=transaction_type)
            self.assertTrue(transaction.is_credit, f"{transaction_type} should be credit")
        
        for transaction_type in debit_types:
            transaction = TransactionFactory(user=self.user, type=transaction_type)
            self.assertTrue(transaction.is_debit, f"{transaction_type} should be debit")
    
    def test_is_debit_property(self):
        """Test the is_debit property for different transaction types."""
        credit_types = ['DEPOSIT', 'ROI', 'REFERRAL_BONUS', 'MILESTONE_BONUS', 'ADMIN_ADJUSTMENT', 'BREAKDOWN_REFUND']
        debit_types = ['WITHDRAWAL', 'PLAN_PURCHASE']
        
        for transaction_type in credit_types:
            transaction = TransactionFactory(user=self.user, type=transaction_type)
            self.assertFalse(transaction.is_debit, f"{transaction_type} should not be debit")
        
        for transaction_type in debit_types:
            transaction = TransactionFactory(user=self.user, type=transaction_type)
            self.assertTrue(transaction.is_debit, f"{transaction_type} should be debit")
    
    def test_balance_impact_property(self):
        """Test the balance_impact property for different transaction types."""
        # Test credit transactions
        credit_transaction = TransactionFactory(
            user=self.user,
            type='DEPOSIT',
            amount=Decimal('100.00')
        )
        self.assertEqual(credit_transaction.get_balance_impact(), Decimal('100.00'))
        
        # Test debit transactions
        debit_transaction = TransactionFactory(
            user=self.user,
            type='WITHDRAWAL',
            amount=Decimal('50.00')
        )
        self.assertEqual(debit_transaction.get_balance_impact(), Decimal('-50.00'))
    
    def test_update_status_method(self):
        """Test the update_status method."""
        transaction = TransactionFactory(user=self.user, status='PENDING')
        
        # Update status
        transaction.update_status('SUCCESS', {'admin_note': 'Approved'})
        
        self.assertEqual(transaction.status, 'SUCCESS')
        self.assertIn('admin_note', transaction.meta_data)
        self.assertEqual(transaction.meta_data['admin_note'], 'Approved')
    
    def test_add_metadata_method(self):
        """Test the add_metadata method."""
        transaction = TransactionFactory(user=self.user)
        
        # Add metadata
        transaction.add_metadata('test_key', 'test_value')
        
        self.assertIn('test_key', transaction.meta_data)
        self.assertEqual(transaction.meta_data['test_key'], 'test_value')
    
    def test_create_transaction_class_method(self):
        """Test the create_transaction class method."""
        transaction = Transaction.create_transaction(
            user=self.user,
            type='DEPOSIT',
            currency='INR',
            amount=Decimal('100.00'),
            reference_id='test_ref',
            meta_data={'test': 'value'},
            status='SUCCESS'
        )
        
        self.assertIsInstance(transaction, Transaction)
        self.assertEqual(transaction.user, self.user)
        self.assertEqual(transaction.type, 'DEPOSIT')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertEqual(transaction.reference_id, 'test_ref')
        self.assertEqual(transaction.meta_data, {'test': 'value'})
        self.assertEqual(transaction.status, 'SUCCESS')
    
    def test_create_transaction_validation_amount(self):
        """Test that create_transaction validates amount properly."""
        with self.assertRaises(ValueError, msg="Amount must be positive"):
            Transaction.create_transaction(
                user=self.user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal('-100.00')
            )
        
        with self.assertRaises(ValueError, msg="Amount must be positive"):
            Transaction.create_transaction(
                user=self.user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal('0.00')
            )
    
    def test_create_transaction_validation_user_active(self):
        """Test that create_transaction validates user is active."""
        inactive_user = UserFactory(is_active=False)
        
        with self.assertRaises(ValueError, msg="Cannot create transaction for inactive user"):
            Transaction.create_transaction(
                user=inactive_user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal('100.00')
            )
    
    def test_create_transaction_validation_currency_precision(self):
        """Test that create_transaction validates currency-specific precision."""
        # Test INR with too many decimal places
        with self.assertRaises(ValueError, msg="INR amounts cannot have more than 2 decimal places"):
            Transaction.create_transaction(
                user=self.user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal('100.123')
            )
        
        # Test USDT with too many decimal places
        with self.assertRaises(ValueError, msg="USDT amounts cannot have more than 6 decimal places"):
            Transaction.create_transaction(
                user=self.user,
                type='DEPOSIT',
                currency='USDT',
                amount=Decimal('100.1234567')
            )
    
    def test_transaction_choices(self):
        """Test that transaction choices are properly defined."""
        expected_types = [
            'DEPOSIT', 'WITHDRAWAL', 'ROI', 'REFERRAL_BONUS',
            'MILESTONE_BONUS', 'ADMIN_ADJUSTMENT', 'PLAN_PURCHASE', 'BREAKDOWN_REFUND'
        ]
        expected_currencies = ['INR', 'USDT']
        expected_statuses = ['PENDING', 'SUCCESS', 'FAILED']
        
        actual_types = [choice[0] for choice in Transaction.TRANSACTION_TYPE_CHOICES]
        actual_currencies = [choice[0] for choice in Transaction.CURRENCY_CHOICES]
        actual_statuses = [choice[0] for choice in Transaction.STATUS_CHOICES]
        
        self.assertEqual(actual_types, expected_types)
        self.assertEqual(actual_currencies, expected_currencies)
        self.assertEqual(actual_statuses, expected_statuses)
    
    def test_transaction_meta_fields(self):
        """Test that transaction meta fields are properly configured."""
        transaction = TransactionFactory(user=self.user)
        
        # Test that meta_data defaults to empty dict
        self.assertEqual(transaction.meta_data, {})
        
        # Test that meta_data can store complex data
        complex_meta = {
            'tx_hash': '0x1234567890abcdef',
            'block_number': 12345,
            'gas_used': '21000',
            'nested_data': {
                'key1': 'value1',
                'key2': ['item1', 'item2']
            }
        }
        
        transaction.meta_data = complex_meta
        transaction.save()
        
        # Refresh from database
        transaction.refresh_from_db()
        self.assertEqual(transaction.meta_data, complex_meta)
    
    def test_transaction_ordering(self):
        """Test that transactions are ordered by created_at descending."""
        # Create transactions with different timestamps
        transaction1 = TransactionFactory(user=self.user)
        transaction2 = TransactionFactory(user=self.user)
        transaction3 = TransactionFactory(user=self.user)
        
        # Get transactions in default order
        transactions = Transaction.objects.all()
        
        # Should be ordered by created_at descending (newest first)
        self.assertEqual(transactions[0], transaction3)
        self.assertEqual(transactions[1], transaction2)
        self.assertEqual(transactions[2], transaction1)
    
    def test_transaction_indexes(self):
        """Test that transaction indexes are properly configured."""
        # This test verifies that the model has the expected indexes
        # by checking the Meta class configuration
        meta = Transaction._meta
        
        # Check that indexes are defined
        self.assertTrue(hasattr(meta, 'indexes'))
        self.assertGreater(len(meta.indexes), 0)
        
        # Check for specific important indexes
        index_fields = [index.fields for index in meta.indexes]
        
        # Should have user + type index
        self.assertIn(['user', 'type'], index_fields)
        
        # Should have user + currency index
        self.assertIn(['user', 'currency'], index_fields)
        
        # Should have created_at index
        self.assertIn(['created_at'], index_fields)


class TransactionModelIntegrationTest(TestCase):
    """Integration tests for Transaction model with other models."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
    
    def test_transaction_with_wallet_integration(self):
        """Test that transactions can reference wallet-related data."""
        # Create a transaction that references a wallet operation
        transaction = Transaction.create_transaction(
            user=self.user,
            type='DEPOSIT',
            currency='INR',
            amount=Decimal('1000.00'),
            reference_id='wallet_op_123',
            meta_data={
                'wallet_type': 'INR',
                'balance_before': '5000.00',
                'balance_after': '6000.00',
                'operation': 'manual_deposit'
            }
        )
        
        self.assertIsNotNone(transaction.id)
        self.assertEqual(transaction.reference_id, 'wallet_op_123')
        self.assertIn('wallet_type', transaction.meta_data)
        self.assertEqual(transaction.meta_data['operation'], 'manual_deposit')
    
    def test_transaction_with_investment_integration(self):
        """Test that transactions can reference investment data."""
        # Create a transaction that references an investment
        transaction = Transaction.create_transaction(
            user=self.user,
            type='PLAN_PURCHASE',
            currency='USDT',
            amount=Decimal('100.000000'),
            reference_id='investment_456',
            meta_data={
                'plan_name': 'Premium Plan',
                'duration_days': 365,
                'roi_rate': '12.5',
                'investment_type': 'fixed_term'
            }
        )
        
        self.assertIsNotNone(transaction.id)
        self.assertEqual(transaction.reference_id, 'investment_456')
        self.assertIn('plan_name', transaction.meta_data)
        self.assertEqual(transaction.meta_data['investment_type'], 'fixed_term')
    
    def test_transaction_with_referral_integration(self):
        """Test that transactions can reference referral data."""
        # Create a transaction that references a referral
        transaction = Transaction.create_transaction(
            user=self.user,
            type='REFERRAL_BONUS',
            currency='INR',
            amount=Decimal('500.00'),
            reference_id='referral_789',
            meta_data={
                'referrer_id': 'user_123',
                'referred_user_id': 'user_456',
                'level': 1,
                'bonus_percentage': '5.0',
                'referral_date': '2024-01-15'
            }
        )
        
        self.assertIsNotNone(transaction.id)
        self.assertEqual(transaction.reference_id, 'referral_789')
        self.assertIn('referrer_id', transaction.meta_data)
        self.assertEqual(transaction.meta_data['level'], 1)
    
    def test_transaction_currency_validation_integration(self):
        """Test that currency validation works with real-world amounts."""
        # Test INR with valid amounts
        valid_inr_amounts = [
            Decimal('0.01'),      # Minimum valid amount
            Decimal('100.00'),    # Standard amount
            Decimal('999999.99'), # Large amount
            Decimal('1000.50'),   # Amount with cents
        ]
        
        for amount in valid_inr_amounts:
            transaction = Transaction.create_transaction(
                user=self.user,
                type='DEPOSIT',
                currency='INR',
                amount=amount
            )
            self.assertEqual(transaction.amount, amount)
        
        # Test USDT with valid amounts
        valid_usdt_amounts = [
            Decimal('0.000001'),      # Minimum valid amount
            Decimal('100.000000'),    # Standard amount
            Decimal('999999.999999'), # Large amount
            Decimal('1000.123456'),   # Amount with 6 decimal places
        ]
        
        for amount in valid_usdt_amounts:
            transaction = Transaction.create_transaction(
                user=self.user,
                type='DEPOSIT',
                currency='USDT',
                amount=amount
            )
            self.assertEqual(transaction.amount, amount)
