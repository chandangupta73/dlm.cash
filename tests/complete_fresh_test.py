#!/usr/bin/env python
"""
Complete Fresh Integration Test
Tests entire flow with fresh data to verify Part 1 & Part 2 integration
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
from app.users.models import OTP
from app.kyc.models import KYCDocument, KYCVerificationLog
from app.wallet.models import INRWallet, USDTWallet, WalletAddress, WalletTransaction

User = get_user_model()

BASE_URL = "http://127.0.0.1:8000"

class CompleteFreshTest:
    def __init__(self):
        self.test_email = f"fresh_test_{int(time.time())}@investment.com"
        self.test_username = f"fresh_user_{int(time.time())}"
        self.test_password = "FreshTest123!"
        self.access_token = None
        self.user_id = None
        self.step_count = 0
        
    def log(self, message, status="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.step_count += 1
        print(f"[{timestamp}] Step {self.step_count}: {message}")
        
    def test_step_1_user_registration(self):
        """Step 1: Register new user and verify wallet creation"""
        self.log("🔐 Testing user registration...")
        
        registration_data = {
            "username": self.test_username,
            "email": self.test_email,
            "password": self.test_password,
            "password_confirm": self.test_password,
            "first_name": "Fresh",
            "last_name": "Tester"
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/auth/register/",
                json=registration_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 201:
                data = response.json()
                self.user_id = data['user']['id']
                self.log(f"✅ User registered successfully!")
                self.log(f"   User ID: {self.user_id}")
                self.log(f"   Email: {data['user']['email']}")
                
                # Check if wallets were created automatically
                user = User.objects.get(id=self.user_id)
                inr_wallet = INRWallet.objects.filter(user=user).first()
                usdt_wallet = USDTWallet.objects.filter(user=user).first()
                addresses = WalletAddress.objects.filter(user=user)
                
                if inr_wallet and usdt_wallet and addresses.count() >= 2:
                    self.log(f"✅ Wallets auto-created via signals!")
                    self.log(f"   INR Wallet: Balance = {inr_wallet.balance}")
                    self.log(f"   USDT Wallet: Balance = {usdt_wallet.balance}")
                    self.log(f"   Addresses: {addresses.count()} chains")
                    for addr in addresses:
                        self.log(f"     {addr.chain_type.upper()}: {addr.address}")
                    return True
                else:
                    self.log("❌ Wallets not created automatically", "ERROR")
                    return False
                    
            else:
                self.log(f"❌ Registration failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Registration error: {str(e)}", "ERROR")
            return False
    
    def test_step_2_user_login(self):
        """Step 2: Login and get JWT tokens"""
        self.log("🔑 Testing user login...")
        
        login_data = {
            "email": self.test_email,
            "password": self.test_password
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/auth/login/",
                json=login_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data['tokens']['access']
                self.log(f"✅ Login successful!")
                self.log(f"   Access token length: {len(self.access_token)}")
                return True
            else:
                self.log(f"❌ Login failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Login error: {str(e)}", "ERROR")
            return False
    
    def test_step_3_wallet_balance_api(self):
        """Step 3: Check wallet balance via API"""
        self.log("💰 Testing wallet balance API...")
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{BASE_URL}/api/v1/wallet/balance/", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.log("✅ Wallet balance API working!")
                self.log(f"   INR Balance: ₹{data.get('inr_balance', 'N/A')}")
                self.log(f"   USDT Balance: ${data.get('usdt_balance', 'N/A')}")
                
                wallet_addresses = data.get('wallet_addresses', {})
                self.log(f"   Multi-chain addresses: {len(wallet_addresses)}")
                for chain, address in wallet_addresses.items():
                    self.log(f"     {chain.upper()}: {address}")
                
                return True
            else:
                self.log(f"❌ Wallet balance API failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Wallet balance error: {str(e)}", "ERROR")
            return False
    
    def test_step_4_kyc_status_api(self):
        """Step 4: Check KYC status"""
        self.log("📋 Testing KYC status API...")
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{BASE_URL}/api/v1/kyc/status/", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.log("✅ KYC status API working!")
                self.log(f"   Overall status: {data.get('overall_kyc_status', 'N/A')}")
                self.log(f"   Documents: {data.get('total_documents', 0)}")
                self.log(f"   Is verified: {data.get('is_kyc_verified', False)}")
                return True
            else:
                self.log(f"❌ KYC status API failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ KYC status error: {str(e)}", "ERROR")
            return False
    
    def test_step_5_profile_api(self):
        """Step 5: Check user profile API"""
        self.log("👤 Testing user profile API...")
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{BASE_URL}/api/v1/profile/", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.log("✅ Profile API working!")
                self.log(f"   User ID: {data.get('id', 'N/A')}")
                self.log(f"   Email: {data.get('email', 'N/A')}")
                self.log(f"   KYC Status: {data.get('kyc_status', 'N/A')}")
                self.log(f"   Email Verified: {data.get('email_verified', False)}")
                return True
            else:
                self.log(f"❌ Profile API failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Profile error: {str(e)}", "ERROR")
            return False
    
    def test_step_6_transaction_history(self):
        """Step 6: Check transaction history"""
        self.log("📊 Testing transaction history API...")
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{BASE_URL}/api/v1/wallet/transaction-history/", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.log("✅ Transaction history API working!")
                if isinstance(data, dict) and 'count' in data:
                    self.log(f"   Total transactions: {data.get('count', 0)}")
                else:
                    self.log(f"   Transactions found: {len(data) if isinstance(data, list) else 0}")
                return True
            else:
                self.log(f"❌ Transaction history failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Transaction history error: {str(e)}", "ERROR")
            return False
    
    def test_step_7_admin_panel_check(self):
        """Step 7: Verify admin panel is accessible"""
        self.log("🔧 Testing admin panel accessibility...")
        
        try:
            response = requests.get(f"{BASE_URL}/admin/")
            
            if response.status_code == 200 and "Django administration" in response.text:
                self.log("✅ Admin panel is accessible!")
                self.log("   Django admin login page loaded successfully")
                return True
            else:
                self.log(f"❌ Admin panel issue: Status {response.status_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Admin panel error: {str(e)}", "ERROR")
            return False
    
    def test_step_8_database_verification(self):
        """Step 8: Verify database records"""
        self.log("🗄️ Verifying database records...")
        
        try:
            # Check user exists
            user = User.objects.get(id=self.user_id)
            self.log(f"✅ User in database: {user.email}")
            
            # Check wallets
            inr_wallet = INRWallet.objects.filter(user=user).first()
            usdt_wallet = USDTWallet.objects.filter(user=user).first()
            
            if inr_wallet and usdt_wallet:
                self.log(f"✅ Wallets in database:")
                self.log(f"   INR: ID={inr_wallet.id}, Balance={inr_wallet.balance}")
                self.log(f"   USDT: ID={usdt_wallet.id}, Balance={usdt_wallet.balance}")
            
            # Check addresses
            addresses = WalletAddress.objects.filter(user=user)
            self.log(f"✅ Wallet addresses: {addresses.count()} records")
            for addr in addresses:
                self.log(f"   {addr.chain_type}: {addr.address}")
            
            # Check transactions
            transactions = WalletTransaction.objects.filter(user=user)
            self.log(f"✅ Transactions: {transactions.count()} records")
            
            return True
            
        except Exception as e:
            self.log(f"❌ Database verification error: {str(e)}", "ERROR")
            return False
    
    def run_complete_test(self):
        """Run complete fresh integration test"""
        print("=" * 80)
        print("🧪 COMPLETE FRESH INTEGRATION TEST")
        print("Testing Part 1 (Users & KYC) + Part 2 (Wallets & Deposits)")
        print("=" * 80)
        
        tests = [
            ("User Registration & Wallet Auto-Creation", self.test_step_1_user_registration),
            ("User Login & JWT Tokens", self.test_step_2_user_login),
            ("Wallet Balance API", self.test_step_3_wallet_balance_api),
            ("KYC Status API", self.test_step_4_kyc_status_api),
            ("User Profile API", self.test_step_5_profile_api),
            ("Transaction History API", self.test_step_6_transaction_history),
            ("Admin Panel Accessibility", self.test_step_7_admin_panel_check),
            ("Database Records Verification", self.test_step_8_database_verification),
        ]
        
        results = []
        for test_name, test_func in tests:
            print(f"\n📋 {test_name}")
            print("-" * 60)
            success = test_func()
            results.append((test_name, success))
            
        print("\n" + "=" * 80)
        print("📊 FRESH INTEGRATION TEST RESULTS")
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
            print("🎉 ALL TESTS PASSED! System is working perfectly!")
            print("\n🚀 NEXT STEPS:")
            print("1. Access admin panel: http://127.0.0.1:8000/admin/")
            print("2. Login with: admin / [your_password]")
            print("3. Explore user data and wallet records")
            print("4. Test additional functionality")
        else:
            print("⚠️ SOME TESTS FAILED - Check errors above")
            
        print(f"\n📋 TEST USER CREDENTIALS:")
        print(f"Email: {self.test_email}")
        print(f"Password: {self.test_password}")
        print(f"User ID: {self.user_id}")
            
        return passed == total

if __name__ == "__main__":
    tester = CompleteFreshTest()
    tester.run_complete_test()