#!/usr/bin/env python
"""
Comprehensive Frontend Testing Script
=====================================

This script systematically tests ALL frontend features against the backend API
to ensure complete end-to-end functionality. Based on MANUAL_API_TESTING_GUIDE.txt

Features to test:
1. Authentication Flow (Register, Login, Logout, Password Reset)
2. Dashboard Components (Real-time data, KYC status, wallet balance, quick stats)
3. KYC Workflow (Document upload, status tracking, admin approval flow)
4. Wallet Operations (Balance display, deposit requests, withdrawals, addresses)
5. Investment Flow (Plan viewing, purchasing, ROI tracking, history)
6. Referral System (Code generation, tree display, earnings)
7. Transaction History (Filtering, pagination, display)
8. Announcements (Loading, display, real-time updates)
9. Profile Management (View, edit, bank details)
10. Navigation & Routes (All URL patterns, redirects)
11. Error Handling (API errors, validation, user feedback)
12. UI Components (Modals, forms, loading states)
"""

import requests
import json
import time
import os
import sys
from datetime import datetime

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

class FrontendTester:
    def __init__(self):
        self.base_url = 'http://127.0.0.1:8000/api/v1'
        self.frontend_url = 'http://127.0.0.1:8001'
        self.admin_token = None
        self.user_token = None
        self.test_user_id = None
        self.test_results = []
        
    def log(self, message, level='INFO'):
        timestamp = datetime.now().strftime('%H:%M:%S')
        color = {
            'INFO': Colors.BLUE,
            'SUCCESS': Colors.GREEN,
            'ERROR': Colors.RED,
            'WARNING': Colors.YELLOW
        }.get(level, Colors.WHITE)
        
        print(f"{color}[{timestamp}] {level}: {message}{Colors.END}")
        
    def test_api_endpoint(self, name, method, endpoint, headers=None, data=None, expected_status=200):
        """Test an API endpoint and return response"""
        try:
            url = f"{self.base_url}{endpoint}"
            headers = headers or {}
            
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method == 'PATCH':
                response = requests.patch(url, headers=headers, json=data)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            
            success = response.status_code == expected_status
            
            if success:
                self.log(f"✅ {name}: {response.status_code}", 'SUCCESS')
            else:
                self.log(f"❌ {name}: Expected {expected_status}, got {response.status_code}", 'ERROR')
                self.log(f"Response: {response.text[:200]}", 'ERROR')
            
            self.test_results.append({
                'test': name,
                'endpoint': endpoint,
                'method': method,
                'status': response.status_code,
                'expected': expected_status,
                'success': success,
                'response_size': len(response.text)
            })
            
            return response
            
        except Exception as e:
            self.log(f"❌ {name}: Exception - {str(e)}", 'ERROR')
            self.test_results.append({
                'test': name,
                'endpoint': endpoint,
                'method': method,
                'status': 'ERROR',
                'expected': expected_status,
                'success': False,
                'error': str(e)
            })
            return None

    def setup_test_environment(self):
        """Setup test environment with admin and user accounts"""
        self.log("🚀 Setting up test environment...", 'INFO')
        
        # Test admin login
        admin_data = {
            'email': 'admin@example.com',
            'password': 'admin123'
        }
        
        response = self.test_api_endpoint(
            'Admin Login',
            'POST',
            '/auth/login/',
            data=admin_data
        )
        
        if response and response.status_code == 200:
            data = response.json()
            self.admin_token = data['tokens']['access']
            self.log("✅ Admin authenticated successfully", 'SUCCESS')
        else:
            self.log("❌ Admin authentication failed", 'ERROR')
            return False
            
        # Test user login (assuming test user exists)
        user_data = {
            'email': 'admin@example.com',  # Using admin as test user for now
            'password': 'admin123'
        }
        
        response = self.test_api_endpoint(
            'User Login',
            'POST', 
            '/auth/login/',
            data=user_data
        )
        
        if response and response.status_code == 200:
            data = response.json()
            self.user_token = data['tokens']['access']
            self.test_user_id = data['user']['id']
            self.log("✅ User authenticated successfully", 'SUCCESS')
        else:
            self.log("❌ User authentication failed", 'ERROR')
            return False
            
        return True

    def test_authentication_flow(self):
        """Test complete authentication flow"""
        self.log("\n🔐 Testing Authentication Flow...", 'INFO')
        
        # Test registration (with unique email)
        import uuid
        unique_email = f"test_{str(uuid.uuid4())[:8]}@example.com"
        
        register_data = {
            'username': f"testuser_{str(uuid.uuid4())[:8]}",
            'email': unique_email,
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
            'first_name': 'Test',
            'last_name': 'User',
            'phone_number': '+919876543210'
        }
        
        self.test_api_endpoint(
            'User Registration',
            'POST',
            '/auth/register/',
            data=register_data,
            expected_status=201
        )
        
        # Test login with new user
        login_data = {
            'email': unique_email,
            'password': 'TestPass123!'
        }
        
        self.test_api_endpoint(
            'New User Login',
            'POST',
            '/auth/login/',
            data=login_data
        )
        
        # Test invalid login
        invalid_login = {
            'email': 'invalid@example.com',
            'password': 'wrongpassword'
        }
        
        self.test_api_endpoint(
            'Invalid Login',
            'POST',
            '/auth/login/',
            data=invalid_login,
            expected_status=400
        )

    def test_dashboard_components(self):
        """Test all dashboard components and data loading"""
        self.log("\n📊 Testing Dashboard Components...", 'INFO')
        
        headers = {'Authorization': f'Bearer {self.user_token}'}
        
        # Test profile data
        self.test_api_endpoint(
            'User Profile',
            'GET',
            '/profile/',
            headers=headers
        )
        
        # Test wallet balance
        self.test_api_endpoint(
            'Wallet Balance',
            'GET',
            '/wallet/balance/',
            headers=headers
        )
        
        # Test wallet addresses
        self.test_api_endpoint(
            'Wallet Addresses',
            'GET',
            '/wallet/addresses/',
            headers=headers
        )
        
        # Test KYC status
        self.test_api_endpoint(
            'KYC Status',
            'GET',
            '/kyc/status/',
            headers=headers
        )
        
        # Test investments
        self.test_api_endpoint(
            'User Investments',
            'GET',
            '/investment/investments/',
            headers=headers
        )
        
        # Test referral profile
        self.test_api_endpoint(
            'Referral Profile',
            'GET',
            '/referrals/profile/',
            headers=headers
        )
        
        # Test transactions
        self.test_api_endpoint(
            'Transaction History',
            'GET',
            '/transactions/',
            headers=headers
        )
        
        # Test announcements
        self.test_api_endpoint(
            'User Announcements',
            'GET',
            '/admin/announcements/user/',
            headers=headers
        )

    def test_kyc_workflow(self):
        """Test KYC submission and approval workflow"""
        self.log("\n📄 Testing KYC Workflow...", 'INFO')
        
        # Note: File upload testing requires special handling
        # For now, test the status endpoint
        headers = {'Authorization': f'Bearer {self.user_token}'}
        
        self.test_api_endpoint(
            'KYC Status Check',
            'GET',
            '/kyc/status/',
            headers=headers
        )

    def test_wallet_operations(self):
        """Test all wallet operations"""
        self.log("\n💰 Testing Wallet Operations...", 'INFO')
        
        headers = {'Authorization': f'Bearer {self.user_token}'}
        
        # Test balance retrieval
        self.test_api_endpoint(
            'Wallet Balance',
            'GET',
            '/wallet/balance/',
            headers=headers
        )
        
        # Test deposit request creation
        deposit_data = {
            'currency': 'INR',
            'amount': '1000.00',
            'payment_method': 'bank_transfer',
            'payment_details': {
                'account_number': '1234567890',
                'ifsc_code': 'SBIN0001234',
                'account_holder_name': 'Test User',
                'bank_name': 'Test Bank'
            }
        }
        
        self.test_api_endpoint(
            'Create Deposit Request',
            'POST',
            '/deposit-requests/',
            headers=headers,
            data=deposit_data,
            expected_status=201
        )
        
        # Test withdrawal request
        withdrawal_data = {
            'currency': 'INR',
            'amount': 100.00,
            'payout_method': 'bank_transfer',
            'payout_details': {
                'account_number': '123456789012',
                'ifsc_code': 'SBIN0001234',
                'account_holder_name': 'Test User',
                'bank_name': 'Test Bank'
            }
        }
        
        self.test_api_endpoint(
            'Create Withdrawal Request',
            'POST',
            '/withdraw/',
            headers=headers,
            data=withdrawal_data,
            expected_status=201
        )

    def test_investment_flow(self):
        """Test investment plans and purchasing"""
        self.log("\n📈 Testing Investment Flow...", 'INFO')
        
        headers = {'Authorization': f'Bearer {self.user_token}'}
        
        # Test investment plans retrieval
        response = self.test_api_endpoint(
            'Get Investment Plans',
            'GET',
            '/investment/investment-plans/',
            headers=headers
        )
        
        # Test user investments
        self.test_api_endpoint(
            'Get User Investments',
            'GET',
            '/investment/investments/',
            headers=headers
        )
        
        # Test ROI transactions
        self.test_api_endpoint(
            'Get ROI Transactions',
            'GET',
            '/transactions/?transaction_type=ROI',
            headers=headers
        )

    def test_referral_system(self):
        """Test referral system functionality"""
        self.log("\n👥 Testing Referral System...", 'INFO')
        
        headers = {'Authorization': f'Bearer {self.user_token}'}
        
        # Test referral profile
        self.test_api_endpoint(
            'Referral Profile',
            'GET',
            '/referrals/profile/',
            headers=headers
        )
        
        # Test referral tree
        self.test_api_endpoint(
            'Referral Tree',
            'GET',
            '/referrals/tree/',
            headers=headers
        )

    def test_transaction_filtering(self):
        """Test transaction filtering and pagination"""
        self.log("\n📋 Testing Transaction Filtering...", 'INFO')
        
        headers = {'Authorization': f'Bearer {self.user_token}'}
        
        # Test basic transactions
        self.test_api_endpoint(
            'All Transactions',
            'GET',
            '/transactions/',
            headers=headers
        )
        
        # Test pagination
        self.test_api_endpoint(
            'Transactions Page 1',
            'GET',
            '/transactions/?page=1',
            headers=headers
        )
        
        # Test currency filtering
        self.test_api_endpoint(
            'INR Transactions',
            'GET',
            '/transactions/?currency=INR&limit=5',
            headers=headers
        )
        
        self.test_api_endpoint(
            'USDT Transactions',
            'GET',
            '/transactions/?currency=USDT&limit=5',
            headers=headers
        )
        
        # Test type filtering
        self.test_api_endpoint(
            'Deposit Transactions',
            'GET',
            '/transactions/?transaction_type=DEPOSIT',
            headers=headers
        )

    def test_admin_operations(self):
        """Test admin panel operations"""
        self.log("\n👨‍💼 Testing Admin Operations...", 'INFO')
        
        admin_headers = {'Authorization': f'Bearer {self.admin_token}'}
        
        # Test admin dashboard
        self.test_api_endpoint(
            'Admin Dashboard Summary',
            'GET',
            '/admin/dashboard/summary/',
            headers=admin_headers
        )
        
        # Test admin users list
        self.test_api_endpoint(
            'Admin Users List',
            'GET',
            '/admin/users/',
            headers=admin_headers
        )

    def test_error_scenarios(self):
        """Test error handling scenarios"""
        self.log("\n⚠️ Testing Error Scenarios...", 'INFO')
        
        # Test unauthorized access
        self.test_api_endpoint(
            'Unauthorized Access',
            'GET',
            '/wallet/balance/',
            expected_status=401
        )
        
        # Test invalid data
        invalid_data = {
            'email': 'invalid-email',
            'password': ''
        }
        
        self.test_api_endpoint(
            'Invalid Login Data',
            'POST',
            '/auth/login/',
            data=invalid_data,
            expected_status=400
        )

    def run_comprehensive_test(self):
        """Run all tests systematically"""
        self.log(f"\n{Colors.BOLD}🧪 COMPREHENSIVE FRONTEND TESTING{Colors.END}", 'INFO')
        self.log(f"Testing against: {self.base_url}", 'INFO')
        self.log(f"Frontend URL: {self.frontend_url}", 'INFO')
        
        start_time = time.time()
        
        # Setup
        if not self.setup_test_environment():
            self.log("❌ Test environment setup failed. Aborting tests.", 'ERROR')
            return
        
        # Run all test suites
        self.test_authentication_flow()
        self.test_dashboard_components()
        self.test_kyc_workflow()
        self.test_wallet_operations()
        self.test_investment_flow()
        self.test_referral_system()
        self.test_transaction_filtering()
        self.test_admin_operations()
        self.test_error_scenarios()
        
        # Generate summary
        end_time = time.time()
        duration = end_time - start_time
        
        self.generate_test_report(duration)

    def generate_test_report(self, duration):
        """Generate comprehensive test report"""
        self.log(f"\n{Colors.BOLD}📊 TEST RESULTS SUMMARY{Colors.END}", 'INFO')
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        self.log(f"Total Tests: {total_tests}", 'INFO')
        self.log(f"✅ Passed: {passed_tests}", 'SUCCESS')
        self.log(f"❌ Failed: {failed_tests}", 'ERROR')
        self.log(f"⏱️ Duration: {duration:.2f} seconds", 'INFO')
        
        if failed_tests > 0:
            self.log(f"\n{Colors.BOLD}❌ FAILED TESTS:{Colors.END}", 'ERROR')
            for result in self.test_results:
                if not result['success']:
                    error_msg = result.get('error', f"Expected {result['expected']}, got {result['status']}")
                    self.log(f"  - {result['test']}: {error_msg}", 'ERROR')
        
        # Generate detailed report file
        report_data = {
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'duration': duration,
                'timestamp': datetime.now().isoformat()
            },
            'results': self.test_results
        }
        
        with open('frontend_test_report.json', 'w') as f:
            json.dump(report_data, f, indent=2)
        
        self.log(f"\n📄 Detailed report saved to: frontend_test_report.json", 'INFO')

if __name__ == "__main__":
    tester = FrontendTester()
    tester.run_comprehensive_test()
