#!/usr/bin/env python
"""
Database Integrity and Model Relationship Check
Verifies all models, relationships, and data consistency
"""

import os
import sys
from datetime import datetime

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'investment_system.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from django.db import connection
from django.apps import apps

# Import all models
User = get_user_model()
from app.users.models import OTP
from app.kyc.models import KYCDocument, VideoKYC, OfflineKYCRequest, KYCVerificationLog
from app.wallet.models import *

class DatabaseIntegrityChecker:
    def __init__(self):
        self.issues = []
        self.models_checked = 0
        
    def log(self, message, status="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {status}: {message}")
        
    def add_issue(self, issue):
        self.issues.append(issue)
        
    def check_database_connection(self):
        """Check database connectivity"""
        self.log("Checking database connection...")
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                self.log("✅ Database connection successful")
                
                # Check database type
                db_vendor = connection.vendor
                self.log(f"✅ Database type: {db_vendor}")
                
                # Check if we're using custom user model
                if hasattr(User, 'id') and str(User._meta.get_field('id')).find('UUIDField') != -1:
                    self.log("✅ Custom User model with UUID detected")
                else:
                    self.log("⚠️ Standard User model detected")
                    
                return True
                
        except Exception as e:
            self.log(f"❌ Database connection failed: {str(e)}", "ERROR")
            self.add_issue(f"Database connection: {str(e)}")
            return False
    
    def check_model_tables(self):
        """Check if all model tables exist"""
        self.log("Checking model tables...")
        
        models_to_check = [
            User, OTP, KYCDocument, VideoKYC, OfflineKYCRequest, KYCVerificationLog,
            INRWallet, USDTWallet, WalletAddress, WalletTransaction,
            INRDepositRequest, USDTDepositRequest, SweepLog
        ]
        
        for model in models_to_check:
            try:
                # Try to query the model (this will fail if table doesn't exist)
                count = model.objects.count()
                self.log(f"✅ {model.__name__}: {count} records")
                self.models_checked += 1
                
            except Exception as e:
                self.log(f"❌ {model.__name__}: {str(e)}", "ERROR")
                self.add_issue(f"Model {model.__name__}: {str(e)}")
    
    def check_user_wallet_relationships(self):
        """Check user-wallet relationships"""
        self.log("Checking user-wallet relationships...")
        
        try:
            users = User.objects.all()
            self.log(f"Total users: {users.count()}")
            
            for user in users:
                # Check INR wallet
                inr_wallets = INRWallet.objects.filter(user=user)
                if inr_wallets.count() == 0:
                    self.add_issue(f"User {user.email} has no INR wallet")
                elif inr_wallets.count() > 1:
                    self.add_issue(f"User {user.email} has multiple INR wallets")
                    
                # Check USDT wallet
                usdt_wallets = USDTWallet.objects.filter(user=user)
                if usdt_wallets.count() == 0:
                    self.add_issue(f"User {user.email} has no USDT wallet")
                elif usdt_wallets.count() > 1:
                    self.add_issue(f"User {user.email} has multiple USDT wallets")
                    
                # Check wallet addresses
                addresses = WalletAddress.objects.filter(user=user)
                if addresses.count() == 0:
                    self.add_issue(f"User {user.email} has no wallet addresses")
                    
                # Check for each chain type
                for chain in ['trc20', 'erc20', 'bep20']:
                    chain_addresses = addresses.filter(chain_type=chain)
                    if chain_addresses.count() == 0:
                        self.log(f"⚠️ User {user.email} missing {chain} address")
                    elif chain_addresses.count() > 1:
                        self.add_issue(f"User {user.email} has multiple {chain} addresses")
                        
        except Exception as e:
            self.log(f"❌ Relationship check error: {str(e)}", "ERROR")
            self.add_issue(f"User relationships: {str(e)}")
    
    def check_wallet_address_uniqueness(self):
        """Check wallet address uniqueness constraints"""
        self.log("Checking wallet address uniqueness...")
        
        try:
            # Check for duplicate addresses
            addresses = WalletAddress.objects.all()
            address_values = [addr.address for addr in addresses]
            
            if len(address_values) != len(set(address_values)):
                duplicates = [addr for addr in address_values if address_values.count(addr) > 1]
                self.add_issue(f"Duplicate wallet addresses found: {set(duplicates)}")
            else:
                self.log("✅ All wallet addresses are unique")
                
            # Check unique_together constraint
            user_chain_pairs = [(addr.user_id, addr.chain_type) for addr in addresses]
            if len(user_chain_pairs) != len(set(user_chain_pairs)):
                self.add_issue("Duplicate user-chain combinations found")
            else:
                self.log("✅ User-chain combinations are unique")
                
        except Exception as e:
            self.log(f"❌ Address uniqueness check error: {str(e)}", "ERROR")
            self.add_issue(f"Address uniqueness: {str(e)}")
    
    def check_transaction_integrity(self):
        """Check transaction data integrity"""
        self.log("Checking transaction integrity...")
        
        try:
            transactions = WalletTransaction.objects.all()
            self.log(f"Total transactions: {transactions.count()}")
            
            for transaction in transactions:
                # Check if user exists
                if not transaction.user:
                    self.add_issue(f"Transaction {transaction.id} has no user")
                    
                # Check amount is positive for credits, negative for debits
                if transaction.transaction_type == 'credit' and transaction.amount <= 0:
                    self.add_issue(f"Credit transaction {transaction.id} has non-positive amount")
                elif transaction.transaction_type == 'debit' and transaction.amount >= 0:
                    self.add_issue(f"Debit transaction {transaction.id} has non-negative amount")
                    
        except Exception as e:
            self.log(f"❌ Transaction integrity check error: {str(e)}", "ERROR")
            self.add_issue(f"Transaction integrity: {str(e)}")
    
    def check_kyc_data_integrity(self):
        """Check KYC data integrity"""
        self.log("Checking KYC data integrity...")
        
        try:
            # Check KYC documents
            documents = KYCDocument.objects.all()
            self.log(f"Total KYC documents: {documents.count()}")
            
            for doc in documents:
                if not doc.user:
                    self.add_issue(f"KYC document {doc.id} has no user")
                if not doc.document_file:
                    self.add_issue(f"KYC document {doc.id} has no file")
                    
            # Check video KYC
            videos = VideoKYC.objects.all()
            self.log(f"Total video KYC records: {videos.count()}")
            
            # Check offline requests
            offline = OfflineKYCRequest.objects.all()
            self.log(f"Total offline KYC requests: {offline.count()}")
            
        except Exception as e:
            self.log(f"❌ KYC integrity check error: {str(e)}", "ERROR")
            self.add_issue(f"KYC integrity: {str(e)}")
    
    def check_deposit_integrity(self):
        """Check deposit data integrity"""
        self.log("Checking deposit integrity...")
        
        try:
            # Check INR deposits
            inr_deposits = INRDepositRequest.objects.all()
            self.log(f"Total INR deposits: {inr_deposits.count()}")
            
            # Check USDT deposits
            usdt_deposits = USDTDepositRequest.objects.all()
            self.log(f"Total USDT deposits: {usdt_deposits.count()}")
            
            for deposit in usdt_deposits:
                if not deposit.user:
                    self.add_issue(f"USDT deposit {deposit.id} has no user")
                if deposit.amount <= 0:
                    self.add_issue(f"USDT deposit {deposit.id} has invalid amount")
                    
            # Check sweep logs
            sweeps = SweepLog.objects.all()
            self.log(f"Total sweep logs: {sweeps.count()}")
            
        except Exception as e:
            self.log(f"❌ Deposit integrity check error: {str(e)}", "ERROR")
            self.add_issue(f"Deposit integrity: {str(e)}")
    
    def check_foreign_key_constraints(self):
        """Check foreign key relationships"""
        self.log("Checking foreign key constraints...")
        
        try:
            # Check orphaned records
            
            # Wallets without users
            orphaned_inr = INRWallet.objects.filter(user__isnull=True)
            if orphaned_inr.exists():
                self.add_issue(f"Found {orphaned_inr.count()} INR wallets without users")
                
            orphaned_usdt = USDTWallet.objects.filter(user__isnull=True)
            if orphaned_usdt.exists():
                self.add_issue(f"Found {orphaned_usdt.count()} USDT wallets without users")
                
            # Addresses without users
            orphaned_addr = WalletAddress.objects.filter(user__isnull=True)
            if orphaned_addr.exists():
                self.add_issue(f"Found {orphaned_addr.count()} wallet addresses without users")
                
            # Transactions without users
            orphaned_trans = WalletTransaction.objects.filter(user__isnull=True)
            if orphaned_trans.exists():
                self.add_issue(f"Found {orphaned_trans.count()} transactions without users")
                
            if not self.issues:
                self.log("✅ No orphaned records found")
                
        except Exception as e:
            self.log(f"❌ Foreign key check error: {str(e)}", "ERROR")
            self.add_issue(f"Foreign keys: {str(e)}")
    
    def generate_summary_report(self):
        """Generate summary report"""
        print("\n" + "=" * 80)
        print("📊 DATABASE INTEGRITY CHECK SUMMARY")
        print("=" * 80)
        
        print(f"Models checked: {self.models_checked}")
        print(f"Issues found: {len(self.issues)}")
        
        if self.issues:
            print("\n🚨 ISSUES FOUND:")
            for i, issue in enumerate(self.issues, 1):
                print(f"{i}. {issue}")
        else:
            print("\n🎉 NO ISSUES FOUND - Database integrity is good!")
            
        # Statistics
        print(f"\n📈 DATABASE STATISTICS:")
        try:
            print(f"Total users: {User.objects.count()}")
            print(f"INR wallets: {INRWallet.objects.count()}")
            print(f"USDT wallets: {USDTWallet.objects.count()}")
            print(f"Wallet addresses: {WalletAddress.objects.count()}")
            print(f"Transactions: {WalletTransaction.objects.count()}")
            print(f"KYC documents: {KYCDocument.objects.count()}")
            print(f"INR deposits: {INRDepositRequest.objects.count()}")
            print(f"USDT deposits: {USDTDepositRequest.objects.count()}")
        except Exception as e:
            print(f"Error getting statistics: {e}")
    
    def run_all_checks(self):
        """Run all integrity checks"""
        print("=" * 80)
        print("🔍 DATABASE INTEGRITY & RELATIONSHIP CHECKER")
        print("=" * 80)
        
        checks = [
            ("Database Connection", self.check_database_connection),
            ("Model Tables", self.check_model_tables),
            ("User-Wallet Relationships", self.check_user_wallet_relationships),
            ("Wallet Address Uniqueness", self.check_wallet_address_uniqueness),
            ("Transaction Integrity", self.check_transaction_integrity),
            ("KYC Data Integrity", self.check_kyc_data_integrity),
            ("Deposit Integrity", self.check_deposit_integrity),
            ("Foreign Key Constraints", self.check_foreign_key_constraints),
        ]
        
        for check_name, check_func in checks:
            print(f"\n📋 {check_name}:")
            print("-" * 40)
            check_func()
            
        self.generate_summary_report()
        
        return len(self.issues) == 0

if __name__ == "__main__":
    checker = DatabaseIntegrityChecker()
    checker.run_all_checks()