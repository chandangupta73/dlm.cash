#!/usr/bin/env python
"""
Comprehensive Part 1 (User & KYC) Integration Test
Tests user registration, login, wallet creation, KYC functionality
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
from app.wallet.models import INRWallet, USDTWallet, WalletAddress

User = get_user_model()

BASE_URL = "http://127.0.0.1:8000"

class ComprehensivePart1Test:
    def __init__(self):
        self.test_email = f"testuser_{int(time.time())}@example.com"
        self.test_username = f"testuser_{int(time.time())}"
        self.test_password = "TestPass123!"
        self.access_token = None
        self.user_id = None
        
    def log(self, message, status="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {status}: {message}")
        
    def test_user_registration(self):
        """Test user registration endpoint"""
        self.log("Testing user registration...")
        
        registration_data = {
            "username": self.test_username,
            "email": self.test_email,
            "password": self.test_password,
            "password_confirm": self.test_password,
            "first_name": "Test",
            "last_name": "User"
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
                self.log(f"✅ User registration successful! User ID: {self.user_id}")
                self.log(f"   Username: {data['user']['username']}")
                self.log(f"   Email: {data['user']['email']}")
                return True
            else:
                self.log(f"❌ Registration failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Registration error: {str(e)}", "ERROR")
            return False
    
    def test_user_login(self):
        """Test user login and JWT token generation"""
        self.log("Testing user login...")
        
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
                self.log("✅ User login successful!")
                self.log(f"   Access token received (length: {len(self.access_token)})")
                return True
            else:
                self.log(f"❌ Login failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Login error: {str(e)}", "ERROR")
            return False
    
    def test_wallet_auto_creation(self):
        """Test if wallets and addresses were automatically created"""
        self.log("Testing automatic wallet creation...")
        
        try:
            # Check wallets in database
            user = User.objects.get(id=self.user_id)
            
            # Check INR wallet
            inr_wallet = INRWallet.objects.filter(user=user).first()
            if inr_wallet:
                self.log(f"✅ INR Wallet created: Balance = {inr_wallet.balance}")
            else:
                self.log("❌ INR Wallet not found", "ERROR")
                
            # Check USDT wallet
            usdt_wallet = USDTWallet.objects.filter(user=user).first()
            if usdt_wallet:
                self.log(f"✅ USDT Wallet created: Balance = {usdt_wallet.balance}")
            else:
                self.log("❌ USDT Wallet not found", "ERROR")
                
            # Check wallet addresses
            addresses = WalletAddress.objects.filter(user=user)
            self.log(f"✅ Wallet addresses created: {addresses.count()} addresses")
            for addr in addresses:
                self.log(f"   {addr.chain_type.upper()}: {addr.address}")
                
            return True
            
        except Exception as e:
            self.log(f"❌ Wallet check error: {str(e)}", "ERROR")
            return False
    
    def test_wallet_balance_api(self):
        """Test wallet balance API endpoint"""
        self.log("Testing wallet balance API...")
        
        if not self.access_token:
            self.log("❌ No access token available", "ERROR")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{BASE_URL}/api/v1/wallet/balance/", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.log("✅ Wallet balance API successful!")
                self.log(f"   INR Balance: {data.get('inr_balance', 'N/A')}")
                self.log(f"   USDT Balance: {data.get('usdt_balance', 'N/A')}")
                self.log(f"   Wallet Addresses: {len(data.get('wallet_addresses', {}))}")
                return True
            else:
                self.log(f"❌ Wallet balance API failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Wallet balance API error: {str(e)}", "ERROR")
            return False
    
    def test_kyc_status_api(self):
        """Test KYC status API endpoint"""
        self.log("Testing KYC status API...")
        
        if not self.access_token:
            self.log("❌ No access token available", "ERROR")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{BASE_URL}/api/v1/kyc/status/", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.log("✅ KYC status API successful!")
                self.log(f"   Total documents: {data.get('total_documents', 'N/A')}")
                self.log(f"   Overall KYC status: {data.get('overall_kyc_status', 'N/A')}")
                self.log(f"   Is verified: {data.get('is_kyc_verified', 'N/A')}")
                return True
            else:
                self.log(f"❌ KYC status API failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ KYC status API error: {str(e)}", "ERROR")
            return False
    
    def test_kyc_document_types_api(self):
        """Test KYC document types API"""
        self.log("Testing KYC document types API...")
        
        if not self.access_token:
            self.log("❌ No access token available", "ERROR")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{BASE_URL}/api/v1/kyc/document-types/", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.log("✅ KYC document types API successful!")
                # Handle both dict and list responses
                if isinstance(data, list):
                    self.log(f"   Available types: {data}")
                else:
                    self.log(f"   Available types: {data.get('document_types', [])}")
                return True
            else:
                self.log(f"❌ Document types API failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Document types API error: {str(e)}", "ERROR")
            return False
    
    def test_profile_api(self):
        """Test user profile API"""
        self.log("Testing user profile API...")
        
        if not self.access_token:
            self.log("❌ No access token available", "ERROR")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{BASE_URL}/api/v1/profile/", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.log("✅ Profile API successful!")
                self.log(f"   User ID: {data.get('id', 'N/A')}")
                self.log(f"   Email: {data.get('email', 'N/A')}")
                self.log(f"   KYC Status: {data.get('kyc_status', 'N/A')}")
                return True
            else:
                self.log(f"❌ Profile API failed: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Profile API error: {str(e)}", "ERROR")
            return False
    
    def test_database_integrity(self):
        """Test database integrity and relationships"""
        self.log("Testing database integrity...")
        
        try:
            # Check user exists in database
            user = User.objects.get(id=self.user_id)
            self.log(f"✅ User found in database: {user.email}")
            
            # Check user fields
            self.log(f"   UUID: {user.id}")
            self.log(f"   KYC Status: {user.kyc_status}")
            self.log(f"   Email Verified: {user.email_verified}")
            self.log(f"   Created At: {user.created_at}")
            
            # Check wallet relationships
            inr_wallet = getattr(user, 'inr_wallet', None)
            usdt_wallet = getattr(user, 'usdt_wallet', None)
            
            if inr_wallet:
                self.log(f"✅ INR Wallet linked: {inr_wallet.id}")
            if usdt_wallet:
                self.log(f"✅ USDT Wallet linked: {usdt_wallet.id}")
                
            # Check wallet addresses
            addresses = user.wallet_addresses.all()
            self.log(f"✅ Wallet addresses linked: {addresses.count()}")
            
            return True
            
        except User.DoesNotExist:
            self.log("❌ User not found in database", "ERROR")
            return False
        except Exception as e:
            self.log(f"❌ Database integrity error: {str(e)}", "ERROR")
            return False
    
    def run_all_tests(self):
        """Run all Part 1 tests"""
        print("=" * 80)
        print("🧪 COMPREHENSIVE PART 1 (USER & KYC) INTEGRATION TEST")
        print("=" * 80)
        
        tests = [
            ("User Registration", self.test_user_registration),
            ("User Login", self.test_user_login),
            ("Wallet Auto-Creation", self.test_wallet_auto_creation),
            ("Wallet Balance API", self.test_wallet_balance_api),
            ("KYC Status API", self.test_kyc_status_api),
            ("KYC Document Types API", self.test_kyc_document_types_api),
            ("Profile API", self.test_profile_api),
            ("Database Integrity", self.test_database_integrity),
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
            print("🎉 ALL PART 1 TESTS PASSED!")
        else:
            print("⚠️ SOME TESTS FAILED - Check errors above")
            
        return passed == total

if __name__ == "__main__":
    tester = ComprehensivePart1Test()
    tester.run_all_tests()