from decimal import Decimal
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from .models import INRWallet, USDTWallet, WalletTransaction, DepositRequest


class WalletService:
    """Service class for wallet operations."""
    
    @staticmethod
    def get_or_create_inr_wallet(user):
        """Get or create INR wallet for user."""
        wallet, created = INRWallet.objects.get_or_create(
            user=user,
            defaults={'balance': Decimal('0.00')}
        )
        return wallet
    
    @staticmethod
    def get_or_create_usdt_wallet(user):
        """Get or create USDT wallet for user."""
        wallet, created = USDTWallet.objects.get_or_create(
            user=user,
            defaults={'balance': Decimal('0.000000')}
        )
        return wallet
    
    @staticmethod
    def get_wallet_balance(user):
        """Get combined wallet balance for user."""
        inr_wallet = WalletService.get_or_create_inr_wallet(user)
        usdt_wallet = WalletService.get_or_create_usdt_wallet(user)
        
        return {
            'inr_balance': inr_wallet.balance,
            'usdt_balance': usdt_wallet.balance,
            'inr_wallet_status': inr_wallet.status,
            'usdt_wallet_status': usdt_wallet.status,
            'last_updated': timezone.now()
        }
    
    @staticmethod
    @transaction.atomic
    def add_inr_balance(user, amount, transaction_type='admin_adjustment', description='', reference_id=None):
        """Add INR balance to user wallet with transaction log."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        wallet = WalletService.get_or_create_inr_wallet(user)
        
        if not wallet.can_transact():
            raise ValueError("Wallet is not active for transactions")
        
        balance_before = wallet.balance
        if wallet.add_balance(amount):
            # Create transaction log
            WalletTransaction.objects.create(
                user=user,
                transaction_type=transaction_type,
                wallet_type='inr',
                amount=amount,
                balance_before=balance_before,
                balance_after=wallet.balance,
                status='completed',
                reference_id=reference_id,
                description=description
            )
            return True
        return False
    
    @staticmethod
    @transaction.atomic
    def deduct_inr_balance(user, amount, transaction_type='withdrawal', description='', reference_id=None):
        """Deduct INR balance from user wallet with transaction log."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        wallet = WalletService.get_or_create_inr_wallet(user)
        
        if not wallet.can_transact():
            raise ValueError("Wallet is not active for transactions")
        
        if wallet.balance < amount:
            raise ValueError("Insufficient balance")
        
        balance_before = wallet.balance
        if wallet.deduct_balance(amount):
            # Create transaction log
            WalletTransaction.objects.create(
                user=user,
                transaction_type=transaction_type,
                wallet_type='inr',
                amount=amount,
                balance_before=balance_before,
                balance_after=wallet.balance,
                status='completed',
                reference_id=reference_id,
                description=description
            )
            return True
        return False
    
    @staticmethod
    @transaction.atomic
    def add_usdt_balance(user, amount, transaction_type='admin_adjustment', description='', reference_id=None):
        """Add USDT balance to user wallet with transaction log."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        wallet = WalletService.get_or_create_usdt_wallet(user)
        
        if not wallet.can_transact():
            raise ValueError("Wallet is not active for transactions")
        
        balance_before = wallet.balance
        if wallet.add_balance(amount):
            # Create transaction log
            WalletTransaction.objects.create(
                user=user,
                transaction_type=transaction_type,
                wallet_type='usdt',
                amount=amount,
                balance_before=balance_before,
                balance_after=wallet.balance,
                status='completed',
                reference_id=reference_id,
                description=description
            )
            return True
        return False
    
    @staticmethod
    @transaction.atomic
    def deduct_usdt_balance(user, amount, transaction_type='withdrawal', description='', reference_id=None):
        """Deduct USDT balance from user wallet with transaction log."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        wallet = WalletService.get_or_create_usdt_wallet(user)
        
        if not wallet.can_transact():
            raise ValueError("Wallet is not active for transactions")
        
        if wallet.balance < amount:
            raise ValueError("Insufficient balance")
        
        balance_before = wallet.balance
        if wallet.deduct_balance(amount):
            # Create transaction log
            WalletTransaction.objects.create(
                user=user,
                transaction_type=transaction_type,
                wallet_type='usdt',
                amount=amount,
                balance_before=balance_before,
                balance_after=wallet.balance,
                status='completed',
                reference_id=reference_id,
                description=description
            )
            return True
        return False


class DepositService:
    """Service class for deposit operations."""
    
    @staticmethod
    def create_deposit_request(user, amount, payment_method, **kwargs):
        """Create a new deposit request."""
        deposit = DepositRequest.objects.create(
            user=user,
            amount=amount,
            payment_method=payment_method,
            **kwargs
        )
        return deposit
    
    @staticmethod
    @transaction.atomic
    def approve_deposit(deposit_id, admin_user, notes=None):
        """Approve a deposit request."""
        try:
            deposit = DepositRequest.objects.get(id=deposit_id, status='pending')
        except DepositRequest.DoesNotExist:
            raise ValueError("Deposit request not found or already processed")
        
        if deposit.approve(admin_user):
            return True
        return False
    
    @staticmethod
    def reject_deposit(deposit_id, admin_user, reason=""):
        """Reject a deposit request."""
        try:
            deposit = DepositRequest.objects.get(id=deposit_id, status='pending')
        except DepositRequest.DoesNotExist:
            raise ValueError("Deposit request not found or already processed")
        
        if deposit.reject(admin_user, reason):
            return True
        return False
    
    @staticmethod
    def get_user_deposits(user, status=None, limit=50):
        """Get deposit requests for a user."""
        queryset = DepositRequest.objects.filter(user=user)
        if status:
            queryset = queryset.filter(status=status)
        return queryset.order_by('-created_at')[:limit]


class TransactionService:
    """Service class for transaction operations."""
    
    @staticmethod
    def get_user_transactions(user, wallet_type=None, transaction_type=None, 
                            status=None, page=1, page_size=20):
        """Get paginated transactions for a user."""
        queryset = WalletTransaction.objects.filter(user=user)
        
        if wallet_type:
            queryset = queryset.filter(wallet_type=wallet_type)
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        if status:
            queryset = queryset.filter(status=status)
        
        total_count = queryset.count()
        offset = (page - 1) * page_size
        
        transactions = queryset.order_by('-created_at')[offset:offset + page_size]
        
        return {
            'transactions': transactions,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'has_next': offset + page_size < total_count,
            'has_previous': page > 1
        }
    
    @staticmethod
    def get_transaction_summary(user, days=30):
        """Get transaction summary for user."""
        from django.utils import timezone
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        transactions = WalletTransaction.objects.filter(
            user=user,
            created_at__gte=start_date,
            status='completed'
        )
        
        summary = {
            'total_deposits': Decimal('0.00'),
            'total_withdrawals': Decimal('0.00'),
            'total_roi': Decimal('0.00'),
            'total_referrals': Decimal('0.00'),
            'transaction_count': transactions.count()
        }
        
        for transaction in transactions:
            if transaction.wallet_type == 'inr':
                amount = transaction.amount
            else:
                # Convert USDT to INR (you might want to use current exchange rate)
                amount = transaction.amount * Decimal('83.00')  # Approximate rate
            
            if transaction.transaction_type == 'deposit':
                summary['total_deposits'] += amount
            elif transaction.transaction_type == 'withdrawal':
                summary['total_withdrawals'] += amount
            elif transaction.transaction_type == 'roi_credit':
                summary['total_roi'] += amount
            elif transaction.transaction_type == 'referral_bonus':
                summary['total_referrals'] += amount
        
        return summary


class WalletValidationService:
    """Service class for wallet validations."""
    
    @staticmethod
    def validate_deposit_amount(amount):
        """Validate deposit amount."""
        if amount < 100:
            return False, "Minimum deposit amount is ₹100"
        if amount > 1000000:
            return False, "Maximum deposit amount is ₹10,00,000"
        return True, "Valid amount"
    
    @staticmethod
    def validate_withdrawal_amount(user, amount, wallet_type='inr'):
        """Validate withdrawal amount."""
        if amount < 100:
            return False, "Minimum withdrawal amount is ₹100"
        
        if wallet_type == 'inr':
            wallet = WalletService.get_or_create_inr_wallet(user)
            if wallet.balance < amount:
                return False, "Insufficient INR balance"
        else:
            wallet = WalletService.get_or_create_usdt_wallet(user)
            if wallet.balance < amount:
                return False, "Insufficient USDT balance"
        
        return True, "Valid withdrawal amount"
    
    @staticmethod
    def validate_wallet_status(user):
        """Validate if user wallets are active."""
        inr_wallet = WalletService.get_or_create_inr_wallet(user)
        usdt_wallet = WalletService.get_or_create_usdt_wallet(user)
        
        if not inr_wallet.can_transact():
            return False, "INR wallet is not active"
        if not usdt_wallet.can_transact():
            return False, "USDT wallet is not active"
        
        return True, "Wallets are active" 