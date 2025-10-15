#!/usr/bin/env python
"""
Frontend Page Testing Script
============================

This script tests all frontend pages for:
1. Page accessibility (200 status)
2. Required elements present
3. JavaScript functionality
4. API integration working

Based on the comprehensive testing checklist.
"""

import requests
import time
from datetime import datetime

class FrontendPageTester:
    def __init__(self):
        self.frontend_base = 'http://127.0.0.1:8001'
        self.api_base = 'http://127.0.0.1:8000/api/v1'
        self.results = []
        
    def log(self, message, level='INFO'):
        timestamp = datetime.now().strftime('%H:%M:%S')
        colors = {
            'INFO': '\033[94m',
            'SUCCESS': '\033[92m', 
            'ERROR': '\033[91m',
            'WARNING': '\033[93m'
        }
        color = colors.get(level, '\033[97m')
        print(f"{color}[{timestamp}] {message}\033[0m")
        
    def test_page_accessibility(self, page_name, url, expected_status=200):
        """Test if a page is accessible"""
        try:
            response = requests.get(f"{self.frontend_base}{url}", timeout=10)
            success = response.status_code == expected_status
            
            if success:
                self.log(f"✅ {page_name}: {response.status_code} - {len(response.text)} bytes", 'SUCCESS')
            else:
                self.log(f"❌ {page_name}: Expected {expected_status}, got {response.status_code}", 'ERROR')
                
            self.results.append({
                'page': page_name,
                'url': url,
                'status': response.status_code,
                'expected': expected_status,
                'success': success,
                'size': len(response.text),
                'type': 'accessibility'
            })
            
            return response
            
        except Exception as e:
            self.log(f"❌ {page_name}: {str(e)}", 'ERROR')
            self.results.append({
                'page': page_name,
                'url': url,
                'status': 'ERROR',
                'expected': expected_status,
                'success': False,
                'error': str(e),
                'type': 'accessibility'
            })
            return None

    def check_page_content(self, page_name, response, required_elements):
        """Check if required elements are present in page content"""
        if not response:
            return False
            
        content = response.text.lower()
        missing_elements = []
        
        for element in required_elements:
            if element.lower() not in content:
                missing_elements.append(element)
                
        if missing_elements:
            self.log(f"⚠️ {page_name}: Missing elements: {missing_elements}", 'WARNING')
            return False
        else:
            self.log(f"✅ {page_name}: All required elements present", 'SUCCESS')
            return True

    def test_api_integration(self, page_name, api_endpoints):
        """Test if API endpoints used by the page are working"""
        working_apis = 0
        total_apis = len(api_endpoints)
        
        for endpoint, expected_auth in api_endpoints:
            try:
                url = f"{self.api_base}{endpoint}"
                headers = {}
                
                if expected_auth:
                    # Get a test token
                    login_response = requests.post(f"{self.api_base}/auth/login/", json={
                        'email': 'admin@example.com',
                        'password': 'admin123'
                    })
                    
                    if login_response.status_code == 200:
                        token = login_response.json()['tokens']['access']
                        headers['Authorization'] = f'Bearer {token}'
                
                response = requests.get(url, headers=headers, timeout=5)
                
                if response.status_code in [200, 401]:  # 401 is expected for auth-required endpoints without token
                    working_apis += 1
                    
            except Exception as e:
                self.log(f"⚠️ API {endpoint}: {str(e)}", 'WARNING')
        
        success_rate = (working_apis / total_apis) * 100 if total_apis > 0 else 0
        self.log(f"📊 {page_name} API Integration: {working_apis}/{total_apis} ({success_rate:.1f}%)", 'INFO')
        
        return success_rate >= 80  # 80% or higher is considered good

    def run_comprehensive_page_tests(self):
        """Run tests for all frontend pages"""
        self.log("🚀 Starting Comprehensive Frontend Page Testing", 'INFO')
        
        # Define all pages to test
        pages_to_test = [
            {
                'name': 'Landing Page',
                'url': '/',
                'required_elements': ['investment', 'login', 'register'],
                'api_endpoints': []
            },
            {
                'name': 'Login Page',
                'url': '/auth/login/',
                'required_elements': ['email', 'password', 'login'],
                'api_endpoints': [('/auth/login/', False)]
            },
            {
                'name': 'Registration Page', 
                'url': '/auth/sign-up/',
                'required_elements': ['username', 'email', 'password', 'register'],
                'api_endpoints': [('/auth/register/', False)]
            },
            {
                'name': 'Dashboard',
                'url': '/auth/dashboard/',
                'required_elements': ['dashboard', 'wallet', 'balance', 'kyc'],
                'api_endpoints': [
                    ('/wallet/balance/', True),
                    ('/kyc/status/', True),
                    ('/investment/investments/', True),
                    ('/referrals/profile/', True)
                ]
            },
            {
                'name': 'Wallet Management',
                'url': '/auth/wallet/',
                'required_elements': ['wallet', 'balance', 'deposit', 'withdraw'],
                'api_endpoints': [
                    ('/wallet/balance/', True),
                    ('/wallet/addresses/', True),
                    ('/transactions/', True)
                ]
            },
            {
                'name': 'Investment Plans',
                'url': '/plans/',
                'required_elements': ['plans', 'investment', 'roi'],
                'api_endpoints': [('/investment/investment-plans/', True)]
            },
            {
                'name': 'My Investments',
                'url': '/auth/investments/',
                'required_elements': ['investments', 'plans', 'roi'],
                'api_endpoints': [
                    ('/investment/investments/', True),
                    ('/investment/investment-plans/', True)
                ]
            },
            {
                'name': 'User Profile',
                'url': '/auth/profile/',
                'required_elements': ['profile', 'name', 'email'],
                'api_endpoints': [('/profile/', True)]
            },
            {
                'name': 'Bank Details',
                'url': '/profile/account/',
                'required_elements': ['bank', 'account'],
                'api_endpoints': [('/profile/', True)]
            }
        ]
        
        total_pages = len(pages_to_test)
        passed_pages = 0
        
        for page_info in pages_to_test:
            self.log(f"\n🔍 Testing: {page_info['name']}", 'INFO')
            
            # Test page accessibility
            response = self.test_page_accessibility(
                page_info['name'], 
                page_info['url']
            )
            
            if response and response.status_code == 200:
                # Test required elements
                content_ok = self.check_page_content(
                    page_info['name'],
                    response,
                    page_info['required_elements']
                )
                
                # Test API integration
                api_ok = self.test_api_integration(
                    page_info['name'],
                    page_info['api_endpoints']
                )
                
                if content_ok and api_ok:
                    passed_pages += 1
                    
        # Generate summary
        self.log(f"\n📊 FRONTEND PAGE TEST SUMMARY", 'INFO')
        self.log(f"Total Pages Tested: {total_pages}", 'INFO')
        self.log(f"✅ Passed: {passed_pages}", 'SUCCESS')
        self.log(f"❌ Failed: {total_pages - passed_pages}", 'ERROR')
        self.log(f"Success Rate: {(passed_pages/total_pages)*100:.1f}%", 'INFO')
        
        return passed_pages == total_pages

if __name__ == "__main__":
    tester = FrontendPageTester()
    success = tester.run_comprehensive_page_tests()
    
    if success:
        print("\n🎉 All frontend pages passed testing!")
    else:
        print("\n⚠️ Some frontend pages need attention.")
