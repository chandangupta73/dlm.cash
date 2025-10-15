#!/usr/bin/env python
"""
Test script for Multi-Chain USDT Deposit Flow
Tests the complete multi-chain USDT deposit flow including:
1. Multi-chain wallet address generation
2. Chain-specific USDT deposit processing
3. Auto/manual sweep functionality per chain
4. Transaction logging with chain information
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


def test_multi_chain_usdt_flow():
    """Test the complete multi-chain USDT deposit flow."""
    print("🧪 Testing Multi-Chain USDT Deposit Flow...")
    
    # Create test user
    user, created = User.objects.get_or_create(
        username='test_multi_chain_user',
        defaults={
            'email': 'test_multi_chain@example.com',
            'first_name': 'Test',
            'last_name': 'Multi-Chain User'
        }
    )
    print(f"✅ Created test user: {user.username}")
    
    # Test 1: Multi-Chain Wallet Address Generation
    print("\n📋 Test 1: Multi-Chain Wallet Address Generation")
    try:
        wallet_addresses = {}
        for chain_type in ['trc20', 'erc20', 'bep20']:
            wallet_address = WalletAddressService.get_or_create_wallet_address(user, chain_type)
            wallet_addresses[chain_type] = wallet_address.address
            print(f"✅ {chain_type.upper()} address created: {wallet_address.address}")
            print(f"   Address type: {wallet_address.chain_type}")
            print(f"   Status: {wallet_address.status}")
            
            # Test address validation
            is_valid = WalletAddressService.validate_address(wallet_address.address, chain_type)
            print(f"   Address validation: {'✅ Valid' if is_valid else '❌ Invalid'}")
        
    except Exception as e:
        print(f"❌ Multi-chain wallet address creation failed: {e}")
        return False
    
    # Test 2: TRC20 USDT Deposit Processing
    print("\n📋 Test 2: TRC20 USDT Deposit Processing")
    try:
        # Simulate TRC20 deposit ($30 - should auto sweep)
        trc20_deposit = USDTDepositService.create_deposit_request(
            user=user,
            amount=Decimal('30.000000'),
            transaction_hash='test_trc20_tx_hash_123',
            from_address='TExternalWallet123456789',
            to_address=wallet_addresses['trc20'],
            chain_type='trc20'
        )
        print(f"✅ TRC20 deposit created: ${trc20_deposit.amount}")
        print(f"   Transaction hash: {trc20_deposit.transaction_hash}")
        print(f"   Chain type: {trc20_deposit.chain_type}")
        print(f"   Sweep type: {trc20_deposit.sweep_type}")
        
        # Process confirmation (12 confirmations for TRC20)
        success = USDTDepositService.process_deposit_confirmation(
            trc20_deposit.id, 12, 12345678
        )
        print(f"   Confirmation processed: {'✅ Success' if success else '❌ Failed'}")
        
        # Check if auto sweep happened
        trc20_deposit.refresh_from_db()
        print(f"   Final status: {trc20_deposit.status}")
        
    except Exception as e:
        print(f"❌ TRC20 deposit processing failed: {e}")
        return False
    
    # Test 3: ERC20 USDT Deposit Processing
    print("\n📋 Test 3: ERC20 USDT Deposit Processing")
    try:
        # Simulate ERC20 deposit ($100 - should manual sweep)
        erc20_deposit = USDTDepositService.create_deposit_request(
            user=user,
            amount=Decimal('100.000000'),
            transaction_hash='test_erc20_tx_hash_456',
            from_address='0xExternalWallet987654321',
            to_address=wallet_addresses['erc20'],
            chain_type='erc20'
        )
        print(f"✅ ERC20 deposit created: ${erc20_deposit.amount}")
        print(f"   Transaction hash: {erc20_deposit.transaction_hash}")
        print(f"   Chain type: {erc20_deposit.chain_type}")
        print(f"   Sweep type: {erc20_deposit.sweep_type}")
        
        # Process confirmation (12 confirmations for ERC20)
        success = USDTDepositService.process_deposit_confirmation(
            erc20_deposit.id, 12, 12345679
        )
        print(f"   Confirmation processed: {'✅ Success' if success else '❌ Failed'}")
        
        # Check status (should be confirmed, not swept)
        erc20_deposit.refresh_from_db()
        print(f"   Status after confirmation: {erc20_deposit.status}")
        
    except Exception as e:
        print(f"❌ ERC20 deposit processing failed: {e}")
        return False
    
    # Test 4: BEP20 USDT Deposit Processing
    print("\n📋 Test 4: BEP20 USDT Deposit Processing")
    try:
        # Simulate BEP20 deposit ($25 - should auto sweep)
        bep20_deposit = USDTDepositService.create_deposit_request(
            user=user,
            amount=Decimal('25.000000'),
            transaction_hash='test_bep20_tx_hash_789',
            from_address='0xBSCExternalWallet123456789',
            to_address=wallet_addresses['bep20'],
            chain_type='bep20'
        )
        print(f"✅ BEP20 deposit created: ${bep20_deposit.amount}")
        print(f"   Transaction hash: {bep20_deposit.transaction_hash}")
        print(f"   Chain type: {bep20_deposit.chain_type}")
        print(f"   Sweep type: {bep20_deposit.sweep_type}")
        
        # Process confirmation (15 confirmations for BEP20)
        success = USDTDepositService.process_deposit_confirmation(
            bep20_deposit.id, 15, 12345680
        )
        print(f"   Confirmation processed: {'✅ Success' if success else '❌ Failed'}")
        
        # Check if auto sweep happened
        bep20_deposit.refresh_from_db()
        print(f"   Final status: {bep20_deposit.status}")
        
    except Exception as e:
        print(f"❌ BEP20 deposit processing failed: {e}")
        return False
    
    # Test 5: Manual Sweep for ERC20
    print("\n📋 Test 5: Manual Sweep for ERC20")
    try:
        # Manually sweep the ERC20 deposit
        success = SweepService.manual_sweep_deposit(erc20_deposit.id, user)
        print(f"   Manual sweep: {'✅ Success' if success else '❌ Failed'}")
        
        # Check final status
        erc20_deposit.refresh_from_db()
        print(f"   Final status: {erc20_deposit.status}")
        print(f"   Sweep TX hash: {erc20_deposit.sweep_tx_hash}")
        
    except Exception as e:
        print(f"❌ Manual sweep failed: {e}")
        return False
    
    # Test 6: Multi-Chain Transaction History
    print("\n📋 Test 6: Multi-Chain Transaction History")
    try:
        # Get user's wallet balance
        balance_data = WalletService.get_wallet_balance(user)
        print(f"✅ Wallet balance retrieved:")
        print(f"   INR Balance: ₹{balance_data['inr_balance']}")
        print(f"   USDT Balance: ${balance_data['usdt_balance']}")
        print(f"   Wallet Addresses:")
        for chain_type, address in balance_data['wallet_addresses'].items():
            print(f"     {chain_type.upper()}: {address}")
        
        # Get transaction history by chain
        from app.crud.wallet import TransactionService
        
        # TRC20 transactions
        trc20_history = TransactionService.get_user_transactions(user, wallet_type='usdt', chain_type='trc20')
        print(f"   TRC20 Transactions: {trc20_history['total_count']} found")
        
        # ERC20 transactions
        erc20_history = TransactionService.get_user_transactions(user, wallet_type='usdt', chain_type='erc20')
        print(f"   ERC20 Transactions: {erc20_history['total_count']} found")
        
        # BEP20 transactions
        bep20_history = TransactionService.get_user_transactions(user, wallet_type='usdt', chain_type='bep20')
        print(f"   BEP20 Transactions: {bep20_history['total_count']} found")
        
    except Exception as e:
        print(f"❌ Transaction history failed: {e}")
        return False
    
    # Test 7: Multi-Chain Sweep Logs
    print("\n📋 Test 7: Multi-Chain Sweep Logs")
    try:
        # Get sweep logs by chain
        trc20_sweeps = SweepService.get_sweep_logs(user=user, chain_type='trc20')
        erc20_sweeps = SweepService.get_sweep_logs(user=user, chain_type='erc20')
        bep20_sweeps = SweepService.get_sweep_logs(user=user, chain_type='bep20')
        
        print(f"✅ Sweep logs found:")
        print(f"   TRC20 Sweeps: {len(trc20_sweeps)}")
        print(f"   ERC20 Sweeps: {len(erc20_sweeps)}")
        print(f"   BEP20 Sweeps: {len(bep20_sweeps)}")
        
        for sweep in trc20_sweeps:
            print(f"     TRC20: {sweep.sweep_type} sweep - ${sweep.amount} ({sweep.status})")
        for sweep in erc20_sweeps:
            print(f"     ERC20: {sweep.sweep_type} sweep - ${sweep.amount} ({sweep.status})")
        for sweep in bep20_sweeps:
            print(f"     BEP20: {sweep.sweep_type} sweep - ${sweep.amount} ({sweep.status})")
        
    except Exception as e:
        print(f"❌ Sweep logs failed: {e}")
        return False
    
    # Test 8: Chain-Specific Configuration
    print("\n📋 Test 8: Chain-Specific Configuration")
    try:
        # Test chain configurations
        for chain_type in ['trc20', 'erc20', 'bep20']:
            config = WalletAddressService.get_chain_config(chain_type)
            print(f"✅ {chain_type.upper()} Configuration:")
            print(f"   Gas Token: {config.get('gas_token', 'Unknown')}")
            print(f"   Gas Fee: {config.get('gas_fee', 'Unknown')}")
            print(f"   Confirmations: {config.get('confirmations', 'Unknown')}")
            print(f"   Address Length: {config.get('length', 'Unknown')}")
        
    except Exception as e:
        print(f"❌ Chain configuration failed: {e}")
        return False
    
    # Test 9: Admin Panel Data
    print("\n📋 Test 9: Admin Panel Data")
    try:
        # Check all models have data
        wallet_addresses_count = WalletAddress.objects.count()
        usdt_deposits_count = USDTDepositRequest.objects.count()
        sweep_logs_count = SweepLog.objects.count()
        usdt_transactions_count = WalletTransaction.objects.filter(wallet_type='usdt').count()
        
        print(f"✅ Admin panel data:")
        print(f"   Wallet Addresses: {wallet_addresses_count}")
        print(f"   USDT Deposits: {usdt_deposits_count}")
        print(f"   Sweep Logs: {sweep_logs_count}")
        print(f"   USDT Transactions: {usdt_transactions_count}")
        
        # Chain breakdown
        for chain_type in ['trc20', 'erc20', 'bep20']:
            deposits = USDTDepositRequest.objects.filter(chain_type=chain_type).count()
            sweeps = SweepLog.objects.filter(chain_type=chain_type).count()
            transactions = WalletTransaction.objects.filter(chain_type=chain_type).count()
            print(f"   {chain_type.upper()}: {deposits} deposits, {sweeps} sweeps, {transactions} transactions")
        
    except Exception as e:
        print(f"❌ Admin panel data failed: {e}")
        return False
    
    print("\n🎉 All multi-chain USDT deposit flow tests completed successfully!")
    return True


def cleanup_test_data():
    """Clean up test data."""
    print("\n🧹 Cleaning up test data...")
    
    try:
        # Delete test user and all related data
        test_user = User.objects.filter(username='test_multi_chain_user').first()
        if test_user:
            test_user.delete()
            print("✅ Test data cleaned up")
        else:
            print("ℹ️ No test data to clean up")
    except Exception as e:
        print(f"⚠️ Cleanup warning: {e}")


if __name__ == "__main__":
    print("🚀 Starting Multi-Chain USDT Deposit Flow Test")
    print("=" * 60)
    
    try:
        success = test_multi_chain_usdt_flow()
        if success:
            print("\n✅ Multi-Chain USDT Deposit Flow Test: PASSED")
        else:
            print("\n❌ Multi-Chain USDT Deposit Flow Test: FAILED")
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup_test_data()
        print("\n�� Test completed") 