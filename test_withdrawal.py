#!/usr/bin/env python3
"""
Test script for withdrawal API
"""
import requests
import json

# Test configuration
BASE_URL = "http://127.0.0.1:8000"
API_BASE = f"{BASE_URL}/api/v1"

def test_withdrawal_api():
    """Test the withdrawal API endpoints"""
    
    print("🧪 Testing Withdrawal API...")
    print("=" * 50)
    
    # Test 1: Check if API is accessible
    try:
        response = requests.get(f"{API_BASE}/kyc/status/")
        print(f"✅ KYC Status API: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"❌ KYC Status API failed: {e}")
    
    # Test 2: Check USDT Details API
    try:
        response = requests.get(f"{API_BASE}/usdt-details/")
        print(f"✅ USDT Details API: {response.status_code}")
        if response.status_code == 200:
            usdt_data = response.json()
            print(f"   Found {len(usdt_data)} USDT details")
            if usdt_data:
                print(f"   First USDT detail: {usdt_data[0]}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ USDT Details API failed: {e}")
    
    # Test 3: Check Profile API
    try:
        response = requests.get(f"{API_BASE}/profile/")
        print(f"✅ Profile API: {response.status_code}")
        if response.status_code == 200:
            profile_data = response.json()
            print(f"   User: {profile_data.get('email', 'N/A')}")
            print(f"   KYC Status: {profile_data.get('kyc_status', 'N/A')}")
            if profile_data.get('bank_details'):
                print(f"   Bank details: Available")
            if profile_data.get('usdt_details'):
                print(f"   USDT details: Available")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Profile API failed: {e}")
    
    # Test 4: Check Wallet Balance API
    try:
        response = requests.get(f"{API_BASE}/wallet/balance/")
        print(f"✅ Wallet Balance API: {response.status_code}")
        if response.status_code == 200:
            wallet_data = response.json()
            print(f"   INR Balance: ₹{wallet_data.get('inr_balance', 'N/A')}")
            print(f"   USDT Balance: ${wallet_data.get('usdt_balance', 'N/A')}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Wallet Balance API failed: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 API Testing Complete!")
    print("\n📝 Next Steps:")
    print("1. Open the frontend at: http://127.0.0.1:8001")
    print("2. Login with testuser1@example.com")
    print("3. Try to withdraw funds using different methods")
    print("4. Check browser console for any errors")

if __name__ == "__main__":
    test_withdrawal_api()
