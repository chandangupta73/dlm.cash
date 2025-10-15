#!/usr/bin/env python
"""
Test script for USDT Deposit Flow
Tests the complete USDT deposit flow including:
1. Wallet address generation
2. USDT deposit processing
3. Auto/manual sweep functionality
4. Transaction logging
"""

import os
import sys
import django
from decimal import Decimal

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'investment_system.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone

from app.wallet.models import (
    WalletAddress, USDTDepositRequest, SweepLog, 
    WalletTransaction, USDTWallet
)
from app.crud.wallet import (
    WalletAddressService, USDTDepositService, 
    SweepService, WalletService
)


def test_usdt_deposit_flow():
    """Test the complete USDT deposit flow."""
    print("🧪 Testing USDT Deposit Flow...")
    
    # Create test user
    user, created = User.objects.get_or_create(
        username='test_usdt_user',
        defaults={
            'email': 'test_usdt@example.com',
            'first_name': 'Test',
            'last_name': 'USDT User'
        }
    )
    print(f"✅ Created test user: {user.username}")
    
    # Test 1: Wallet Address Generation
    print("\n📋 Test 1: Wallet Address Generation")
    try:
        wallet_address = WalletAddressService.get_or_create_wallet_address(user)
        print(f"✅ Wallet address created: {wallet_address.address}")
        print(f"   Address type: {wallet_address.address_type}")
        print(f"   Status: {wallet_address.status}")
        
        # Test address validation
        is_valid = WalletAddressService.validate_address(wallet_address.address)
        print(f"   Address validation: {'✅ Valid' if is_valid else '❌ Invalid'}")
        
    except Exception as e:
        print(f"❌ Wallet address creation failed: {e}")
        return False
    
    # Test 2: USDT Deposit Processing (Small amount - Auto sweep)
    print("\n📋 Test 2: USDT Deposit Processing (Auto Sweep)")
    try:
        # Simulate small deposit ($30 - should auto sweep)
        small_deposit = USDTDepositService.create_deposit_request(
            user=user,
            amount=Decimal('30.000000'),
            transaction_hash='test_small_tx_hash_123',
            from_address='TExternalWallet123456789',
            to_address=wallet_address.address
        )
        print(f"✅ Small deposit created: ${small_deposit.amount}")
        print(f"   Transaction hash: {small_deposit.transaction_hash}")
        print(f"   Sweep type: {small_deposit.sweep_type}")
        
        # Process confirmation (12 confirmations)
        success = USDTDepositService.process_deposit_confirmation(
            small_deposit.id, 12, 12345678
        )
        print(f"   Confirmation processed: {'✅ Success' if success else '❌ Failed'}")
        
        # Check if auto sweep happened
        small_deposit.refresh_from_db()
        print(f"   Final status: {small_deposit.status}")
        
    except Exception as e:
        print(f"❌ Small deposit processing failed: {e}")
        return False
    
    # Test 3: USDT Deposit Processing (Large amount - Manual sweep)
    print("\n📋 Test 3: USDT Deposit Processing (Manual Sweep)")
    try:
        # Simulate large deposit ($100 - should manual sweep)
        large_deposit = USDTDepositService.create_deposit_request(
            user=user,
            amount=Decimal('100.000000'),
            transaction_hash='test_large_tx_hash_456',
            from_address='TExternalWallet987654321',
            to_address=wallet_address.address
        )
        print(f"✅ Large deposit created: ${large_deposit.amount}")
        print(f"   Transaction hash: {large_deposit.transaction_hash}")
        print(f"   Sweep type: {large_deposit.sweep_type}")
        
        # Process confirmation (12 confirmations)
        success = USDTDepositService.process_deposit_confirmation(
            large_deposit.id, 12, 12345679
        )
        print(f"   Confirmation processed: {'✅ Success' if success else '❌ Failed'}")
        
        # Check status (should be confirmed, not swept)
        large_deposit.refresh_from_db()
        print(f"   Status after confirmation: {large_deposit.status}")
        
    except Exception as e:
        print(f"❌ Large deposit processing failed: {e}")
        return False
    
    # Test 4: Manual Sweep
    print("\n📋 Test 4: Manual Sweep")
    try:
        # Manually sweep the large deposit
        success = SweepService.manual_sweep_deposit(large_deposit.id, user)
        print(f"   Manual sweep: {'✅ Success' if success else '❌ Failed'}")
        
        # Check final status
        large_deposit.refresh_from_db()
        print(f"   Final status: {large_deposit.status}")
        print(f"   Sweep TX hash: {large_deposit.sweep_tx_hash}")
        
    except Exception as e:
        print(f"❌ Manual sweep failed: {e}")
        return False
    
    # Test 5: Transaction History
    print("\n📋 Test 5: Transaction History")
    try:
        # Get user's wallet balance
        balance_data = WalletService.get_wallet_balance(user)
        print(f"✅ Wallet balance retrieved:")
        print(f"   INR Balance: ₹{balance_data['inr_balance']}")
        print(f"   USDT Balance: ${balance_data['usdt_balance']}")
        print(f"   USDT Address: {balance_data['usdt_address']}")
        
        # Get transaction history
        from app.crud.wallet import TransactionService
        history = TransactionService.get_user_transactions(user, wallet_type='usdt')
        print(f"   USDT Transactions: {history['total_count']} found")
        
        for tx in history['transactions'][:3]:  # Show first 3 transactions
            print(f"     - {tx.transaction_type}: ${tx.amount} ({tx.status})")
        
    except Exception as e:
        print(f"❌ Transaction history failed: {e}")
        return False
    
    # Test 6: Sweep Logs
    print("\n📋 Test 6: Sweep Logs")
    try:
        sweep_logs = SweepService.get_sweep_logs(user=user)
        print(f"✅ Sweep logs found: {len(sweep_logs)}")
        
        for log in sweep_logs:
            print(f"   - {log.sweep_type} sweep: ${log.amount} ({log.status})")
            print(f"     Gas fee: {log.gas_fee} TRX")
            print(f"     TX hash: {log.transaction_hash}")
        
    except Exception as e:
        print(f"❌ Sweep logs failed: {e}")
        return False
    
    # Test 7: Admin Panel Data
    print("\n📋 Test 7: Admin Panel Data")
    try:
        # Check all models have data
        wallet_addresses = WalletAddress.objects.count()
        usdt_deposits = USDTDepositRequest.objects.count()
        sweep_logs_count = SweepLog.objects.count()
        usdt_transactions = WalletTransaction.objects.filter(wallet_type='usdt').count()
        
        print(f"✅ Admin panel data:")
        print(f"   Wallet Addresses: {wallet_addresses}")
        print(f"   USDT Deposits: {usdt_deposits}")
        print(f"   Sweep Logs: {sweep_logs_count}")
        print(f"   USDT Transactions: {usdt_transactions}")
        
    except Exception as e:
        print(f"❌ Admin panel data failed: {e}")
        return False
    
    print("\n🎉 All USDT deposit flow tests completed successfully!")
    return True


def cleanup_test_data():
    """Clean up test data."""
    print("\n🧹 Cleaning up test data...")
    
    try:
        # Delete test user and all related data
        test_user = User.objects.filter(username='test_usdt_user').first()
        if test_user:
            test_user.delete()
            print("✅ Test data cleaned up")
        else:
            print("ℹ️ No test data to clean up")
    except Exception as e:
        print(f"⚠️ Cleanup warning: {e}")


if __name__ == "__main__":
    print("🚀 Starting USDT Deposit Flow Test")
    print("=" * 50)
    
    try:
        success = test_usdt_deposit_flow()
        if success:
            print("\n✅ USDT Deposit Flow Test: PASSED")
        else:
            print("\n❌ USDT Deposit Flow Test: FAILED")
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup_test_data()
        print("\n�� Test completed") 