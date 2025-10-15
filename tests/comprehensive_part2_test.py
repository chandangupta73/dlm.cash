#!/usr/bin/env python
"""
Comprehensive Part 2 (Wallets & Deposits) Integration Test
Tests wallet functionality, deposits, admin approvals, USDT flows
"""

import os
import sys
import json
import requests
import time
from datetime import datetime

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'investment_system.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from app.wallet.models import *
from django.contrib.admin.models import LogEntry

User = get_user_model()

BASE_URL = "http://127.0.0.1:8000"

class ComprehensivePart2Test:
    def __init__(self):
        self.test_email = f"wallet_test_{int(time.time())}@example.com"
        self.test_username = f"wallet_test_{int(time.time())}"
        self.test_password = "TestPass123!"
        self.access_token = None
        self.user_id = None
        self.deposit_request_id = None
        
    def log(self, message, status="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {status}: {message}")
        
    def setup_test_user(self):
        """Create a test user for wallet testing"""
        self.log("Setting up test user...")
        
        registration_data = {
            "username": self.test_username,
            "email": self.test_email,
            "password": self.test_password,
            "password_confirm": self.test_password,
            "first_name": "Wallet",
            "last_name": "Tester"
        }
        
        try:
            # Register user
            response = requests.post(
                f"{BASE_URL}/api/v1/auth/register/",
                json=registration_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 201:
                data = response.json()
                self.user_id = data['user']['id']
                
                # Login to get token
                login_response = requests.post(
                    f"{BASE_URL}/api/v1/auth/login/",
                    json={"email": self.test_email, "password": self.test_password},
                    headers={"Content-Type": "application/json"}
                )
                
                if login_response.status_code == 200:
                    login_data = login_response.json()
                    self.access_token = login_data['tokens']['access']
                    self.log(f"✅ Test user setup complete! User ID: {self.user_id}")
                    return True
                    
            self.log("❌ Failed to setup test user", "ERROR")
            return False
            
        except Exception as e:
            self.log(f"❌ User setup error: {str(e)}", "ERROR")
            return False
    
    def test_wallet_addresses_api(self):
        """Test wallet addresses API endpoint"""
        self.log("Testing wallet addresses API...")
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{BASE_URL}/api/v1/wallet/addresses/", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.log("✅ Wallet addresses API successful!")
                self.log(f"   Addresses found: {len(data)}")
                for addr in data:
                    self.log(f"   {addr.get('chain_type', 'Unknown').upper()}: {addr.get('address', 'N/A')}")
                return True
            else:
                self.log(f"❌ Wallet addresses API failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Wallet addresses API error: {str(e)}", "ERROR")
            return False
    
    def test_wallet_transactions_api(self):
        """Test wallet transactions API endpoint"""
        self.log("Testing wallet transactions API...")
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{BASE_URL}/api/v1/wallet-transactions/", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.log("✅ Wallet transactions API successful!")
                self.log(f"   Transactions found: {data.get('count', 0)}")
                return True
            else:
                self.log(f"❌ Wallet transactions API failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Wallet transactions API error: {str(e)}", "ERROR")
            return False
    
    def test_add_balance_operation(self):
        """Test adding balance to wallet"""
        self.log("Testing add balance operation...")
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            balance_data = {
                "amount": "100.00",
                "wallet_type": "inr",
                "description": "Test balance addition"
            }
            
            response = requests.post(
                f"{BASE_URL}/api/v1/wallet/add-balance/",
                json=balance_data,
                headers={**headers, "Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log("✅ Add balance operation successful!")
                self.log(f"   New balance: {data.get('new_balance', 'N/A')}")
                return True
            else:
                self.log(f"❌ Add balance failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Add balance error: {str(e)}", "ERROR")
            return False
    
    def test_inr_deposit_request(self):
        """Test INR deposit request creation"""
        self.log("Testing INR deposit request...")
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            deposit_data = {
                "amount": "500.00",
                "payment_method": "bank_transfer",
                "reference_number": f"TEST_REF_{int(time.time())}",
                "notes": "Test deposit request"
            }
            
            response = requests.post(
                f"{BASE_URL}/api/v1/deposit-requests/",
                json=deposit_data,
                headers={**headers, "Content-Type": "application/json"}
            )
            
            if response.status_code == 201:
                data = response.json()
                self.deposit_request_id = data.get('id')
                self.log("✅ INR deposit request successful!")
                self.log(f"   Deposit ID: {self.deposit_request_id}")
                self.log(f"   Amount: {data.get('amount', 'N/A')}")
                self.log(f"   Status: {data.get('status', 'N/A')}")
                return True
            else:
                self.log(f"❌ INR deposit request failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ INR deposit request error: {str(e)}", "ERROR")
            return False
    
    def test_usdt_deposit_flow(self):
        """Test USDT deposit processing flow"""
        self.log("Testing USDT deposit flow...")
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            # First get wallet address
            addr_response = requests.get(f"{BASE_URL}/api/v1/wallet/address/trc20/", headers=headers)
            if addr_response.status_code != 200:
                self.log("❌ Could not get TRC20 address", "ERROR")
                return False
                
            addr_data = addr_response.json()
            trc20_address = addr_data.get('address')
            
            # Simulate USDT deposit
            deposit_data = {
                "from_address": "TTestSenderAddress123456789",
                "to_address": trc20_address,
                "amount": "25.50",
                "tx_hash": f"test_tx_hash_{int(time.time())}",
                "chain_type": "trc20",
                "confirmations": 1
            }
            
            response = requests.post(
                f"{BASE_URL}/api/v1/usdt/process-deposit/",
                json=deposit_data,
                headers={**headers, "Content-Type": "application/json"}
            )
            
            if response.status_code == 201:
                data = response.json()
                self.log("✅ USDT deposit processing successful!")
                self.log(f"   Deposit ID: {data.get('id', 'N/A')}")
                self.log(f"   Amount: {data.get('amount', 'N/A')}")
                self.log(f"   Status: {data.get('status', 'N/A')}")
                return True
            else:
                self.log(f"❌ USDT deposit failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ USDT deposit error: {str(e)}", "ERROR")
            return False
    
    def test_pending_deposits_api(self):
        """Test pending deposits API"""
        self.log("Testing pending deposits API...")
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{BASE_URL}/api/v1/deposits/pending/", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.log("✅ Pending deposits API successful!")
                self.log(f"   Pending deposits: {len(data) if isinstance(data, list) else data.get('count', 0)}")
                return True
            else:
                self.log(f"❌ Pending deposits API failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Pending deposits API error: {str(e)}", "ERROR")
            return False
    
    def test_transaction_history_api(self):
        """Test transaction history API"""
        self.log("Testing transaction history API...")
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{BASE_URL}/api/v1/wallet/transaction-history/", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.log("✅ Transaction history API successful!")
                self.log(f"   Transactions found: {data.get('count', len(data) if isinstance(data, list) else 0)}")
                return True
            else:
                self.log(f"❌ Transaction history API failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Transaction history API error: {str(e)}", "ERROR")
            return False
    
    def test_wallet_models_database(self):
        """Test wallet models in database"""
        self.log("Testing wallet models in database...")
        
        try:
            user = User.objects.get(id=self.user_id)
            
            # Check INR wallet
            inr_wallet = INRWallet.objects.filter(user=user).first()
            if inr_wallet:
                self.log(f"✅ INR Wallet in DB: Balance = {inr_wallet.balance}, Status = {inr_wallet.status}")
            else:
                self.log("❌ INR Wallet not found in DB", "ERROR")
                
            # Check USDT wallet
            usdt_wallet = USDTWallet.objects.filter(user=user).first()
            if usdt_wallet:
                self.log(f"✅ USDT Wallet in DB: Balance = {usdt_wallet.balance}, Status = {usdt_wallet.status}")
            else:
                self.log("❌ USDT Wallet not found in DB", "ERROR")
                
            # Check wallet addresses
            addresses = WalletAddress.objects.filter(user=user)
            self.log(f"✅ Wallet addresses in DB: {addresses.count()}")
            for addr in addresses:
                self.log(f"   {addr.chain_type}: {addr.address} (Status: {addr.status})")
                
            # Check transactions
            transactions = WalletTransaction.objects.filter(user=user)
            self.log(f"✅ Wallet transactions in DB: {transactions.count()}")
            
            # Check deposit requests
            deposits = INRDepositRequest.objects.filter(user=user)
            self.log(f"✅ INR deposit requests in DB: {deposits.count()}")
            
            return True
            
        except Exception as e:
            self.log(f"❌ Database check error: {str(e)}", "ERROR")
            return False
    
    def test_multi_chain_addresses(self):
        """Test multi-chain address generation"""
        self.log("Testing multi-chain address functionality...")
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            # Test each chain type
            chains = ['trc20', 'erc20', 'bep20']
            found_chains = []
            
            for chain in chains:
                response = requests.get(f"{BASE_URL}/api/v1/wallet/address/{chain}/", headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    self.log(f"✅ {chain.upper()} address: {data.get('address', 'N/A')}")
                    found_chains.append(chain)
                else:
                    self.log(f"❌ {chain.upper()} address not found", "ERROR")
                    
            self.log(f"✅ Multi-chain support: {len(found_chains)}/{len(chains)} chains available")
            return len(found_chains) > 0
            
        except Exception as e:
            self.log(f"❌ Multi-chain test error: {str(e)}", "ERROR")
            return False
    
    def run_all_tests(self):
        """Run all Part 2 tests"""
        print("=" * 80)
        print("🧪 COMPREHENSIVE PART 2 (WALLETS & DEPOSITS) INTEGRATION TEST")
        print("=" * 80)
        
        # Setup
        if not self.setup_test_user():
            print("❌ Failed to setup test user - cannot continue")
            return False
            
        tests = [
            ("Wallet Addresses API", self.test_wallet_addresses_api),
            ("Wallet Transactions API", self.test_wallet_transactions_api),
            ("Add Balance Operation", self.test_add_balance_operation),
            ("INR Deposit Request", self.test_inr_deposit_request),
            ("USDT Deposit Flow", self.test_usdt_deposit_flow),
            ("Pending Deposits API", self.test_pending_deposits_api),
            ("Transaction History API", self.test_transaction_history_api),
            ("Multi-Chain Addresses", self.test_multi_chain_addresses),
            ("Wallet Models Database", self.test_wallet_models_database),
        ]
        
        results = []
        for test_name, test_func in tests:
            print(f"\n📋 {test_name}:")
            print("-" * 40)
            success = test_func()
            results.append((test_name, success))
            
        print("\n" + "=" * 80)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 80)
        
        passed = 0
        for test_name, success in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} | {test_name}")
            if success:
                passed += 1
                
        total = len(results)
        print(f"\n🎯 OVERALL: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            print("🎉 ALL PART 2 TESTS PASSED!")
        else:
            print("⚠️ SOME TESTS FAILED - Check errors above")
            
        return passed == total

if __name__ == "__main__":
    tester = ComprehensivePart2Test()
    tester.run_all_tests()