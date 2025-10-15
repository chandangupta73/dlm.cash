from decimal import Decimal
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from decouple import config
from app.wallet.models import (
    INRWallet, USDTWallet, WalletTransaction, DepositRequest,
    WalletAddress, USDTDepositRequest, SweepLog
)

User = get_user_model()


class WalletAddressService:
    """Service class for multi-chain wallet address operations."""
    
    CHAIN_CONFIGS = {
        'erc20': {
            'prefix': '0x',
            'length': 42,
            'confirmations': 12,
            'gas_token': 'ETH',
            'gas_fee': Decimal('0.005000'),
        },
        'bep20': {
            'prefix': '0x',
            'length': 42,
            'confirmations': 15,
            'gas_token': 'BNB',
            'gas_fee': Decimal('0.000500'),
        }
    }
    
    @staticmethod
    def generate_address(user, chain_type):
        """Generate a unique address for a specific chain. Only ERC20 and BEP20 supported."""
        if chain_type not in WalletAddressService.CHAIN_CONFIGS:
            raise ValueError(f"Unsupported chain type: {chain_type}")
        
        config = WalletAddressService.CHAIN_CONFIGS[chain_type]
        
        # In production, this would integrate with a wallet service like BitGo
        # For now, we'll create a placeholder address
        import hashlib
        import time
        
        # ERC20 and BEP20 use the same address for a user
        unique_string = f"{user.id}_{user.username}_erc20_bep20"
        address_hash = hashlib.sha256(unique_string.encode()).hexdigest()
        address = f"0x{address_hash[:40]}"  # ERC20/BEP20 addresses start with 0x
        
        return address
    
    @staticmethod
    def get_or_create_wallet_address(user, chain_type):
        """Get or create wallet address for a specific chain. Only ERC20 and BEP20 supported."""
        if chain_type not in ['erc20', 'bep20']:
            raise ValueError(f"Unsupported chain type: {chain_type}")
        
        # Try to get the specific chain type first
        try:
            wallet_address = WalletAddress.objects.get(user=user, chain_type=chain_type)
            return wallet_address
        except WalletAddress.DoesNotExist:
            # If not found, create a new one for the specific chain type
            address = WalletAddressService.generate_address(user, chain_type)
            wallet_address = WalletAddress.objects.create(
                user=user,
                chain_type=chain_type,
                address=address
            )
            return wallet_address
    
    @staticmethod
    def get_all_wallet_addresses(user):
        """Get all wallet addresses for a user."""
        addresses = WalletAddress.objects.filter(user=user, is_active=True)
        return addresses
    
    @staticmethod
    def validate_address(address, chain_type):
        """Validate address format for a specific chain."""
        if chain_type not in WalletAddressService.CHAIN_CONFIGS:
            return False
        
        config = WalletAddressService.CHAIN_CONFIGS[chain_type]
        
        if not address or len(address) != config['length']:
            return False
        
        if not address.startswith('0x'):
            return False
        
        return True
    
    @staticmethod
    def get_chain_config(chain_type):
        """Get configuration for a specific chain."""
        return WalletAddressService.CHAIN_CONFIGS.get(chain_type, {})


class USDTDepositService:
    """Service class for multi-chain USDT deposit operations."""
    
    @staticmethod
    def create_deposit_request(user, amount, transaction_hash, from_address, to_address, chain_type):
        """Create a new USDT deposit request for a specific chain."""
        # Validate address
        if not WalletAddressService.validate_address(to_address, chain_type):
            raise ValueError(f"Invalid {chain_type.upper()} wallet address")
        
        # Check if transaction already exists
        if USDTDepositRequest.objects.filter(transaction_hash=transaction_hash).exists():
            raise ValueError("Transaction already processed")
        
        # Get chain configuration
        chain_config = WalletAddressService.get_chain_config(chain_type)
        
        # Determine sweep type based on amount and chain
        sweep_thresholds = {
            'erc20': Decimal('50.000000'),
            'bep20': Decimal('50.000000'),
        }
        threshold = sweep_thresholds.get(chain_type, Decimal('50.000000'))
        sweep_type = 'auto' if amount <= threshold else 'manual'
        
        deposit = USDTDepositRequest.objects.create(
            user=user,
            chain_type=chain_type,
            amount=amount,
            transaction_hash=transaction_hash,
            from_address=from_address,
            to_address=to_address,
            sweep_type=sweep_type,
            required_confirmations=chain_config.get('confirmations', 12)
        )
        return deposit
    
    @staticmethod
    def process_deposit_confirmation(deposit_id, confirmation_count, block_number=None):
        """Process deposit confirmation from blockchain."""
        try:
            deposit = USDTDepositRequest.objects.get(id=deposit_id)
        except USDTDepositRequest.DoesNotExist:
            raise ValueError("Deposit request not found")
        
        deposit.confirmation_count = confirmation_count
        if block_number:
            deposit.block_number = block_number
        
        # Auto-confirm if enough confirmations
        required_confirmations = deposit.get_required_confirmations()
        if confirmation_count >= required_confirmations:
            if deposit.confirm_deposit():
                # Auto-sweep if amount <= threshold
                if deposit.sweep_type == 'auto':
                    SweepService.auto_sweep_deposit(deposit)
                return True
        
        deposit.save()
        return False
    
    @staticmethod
    def get_pending_deposits(chain_type=None):
        """Get all pending USDT deposits, optionally filtered by chain."""
        queryset = USDTDepositRequest.objects.filter(status='pending')
        if chain_type:
            queryset = queryset.filter(chain_type=chain_type)
        return queryset.select_related('user').order_by('-created_at')
    
    @staticmethod
    def get_confirmed_deposits(chain_type=None):
        """Get all confirmed USDT deposits ready for sweep, optionally filtered by chain."""
        queryset = USDTDepositRequest.objects.filter(status='confirmed')
        if chain_type:
            queryset = queryset.filter(chain_type=chain_type)
        return queryset.select_related('user').order_by('-created_at')


class SweepService:
    """Service class for multi-chain sweep operations."""
    
    MASTER_WALLET_ADDRESSES = {
        'erc20': "0xMasterWalletAddress123456789",
        'bep20': "0xMasterWalletAddressBSC123456789",
    }
    
    @staticmethod
    def auto_sweep_deposit(deposit):
        """Automatically sweep a confirmed deposit to master wallet."""
        try:
            # Get chain configuration
            chain_config = WalletAddressService.get_chain_config(deposit.chain_type)
            master_address = SweepService.MASTER_WALLET_ADDRESSES.get(deposit.chain_type)
            
            # In production, this would call the blockchain API
            # For now, we'll simulate the sweep
            sweep_tx_hash = f"sweep_{deposit.chain_type}_{deposit.transaction_hash[:20]}"
            gas_fee = chain_config.get('gas_fee', Decimal('0.001000'))
            
            # Create sweep log
            sweep_log = SweepLog.objects.create(
                user=deposit.user,
                chain_type=deposit.chain_type,
                from_address=deposit.to_address,
                to_address=master_address,
                amount=deposit.amount,
                gas_fee=gas_fee,
                transaction_hash=sweep_tx_hash,
                sweep_type='auto',
                status='completed'
            )
            
            # Mark deposit as swept
            deposit.mark_as_swept(sweep_tx_hash, gas_fee)
            
            # Create transaction log
            WalletTransaction.objects.create(
                user=deposit.user,
                transaction_type='sweep',
                wallet_type='usdt',
                chain_type=deposit.chain_type,
                amount=deposit.amount,
                balance_before=deposit.user.usdt_wallet.balance,
                balance_after=deposit.user.usdt_wallet.balance - deposit.amount,
                status='completed',
                reference_id=sweep_tx_hash,
                description=f"Auto sweep to master wallet - {deposit.chain_type.upper()} - Gas: {gas_fee} {chain_config.get('gas_token', 'ETH')}",
                metadata={'chain_type': deposit.chain_type, 'gas_token': chain_config.get('gas_token')}
            )
            
            # Deduct from user wallet
            usdt_wallet = deposit.user.usdt_wallet
            usdt_wallet.deduct_balance(deposit.amount)
            
            return True
            
        except Exception as e:
            # Log error
            SweepLog.objects.create(
                user=deposit.user,
                chain_type=deposit.chain_type,
                from_address=deposit.to_address,
                to_address=SweepService.MASTER_WALLET_ADDRESSES.get(deposit.chain_type, ''),
                amount=deposit.amount,
                sweep_type='auto',
                status='failed',
                error_message=str(e)
            )
            return False
    
    @staticmethod
    def manual_sweep_deposit(deposit_id, admin_user):
        """Manually sweep a confirmed deposit to master wallet."""
        try:
            deposit = USDTDepositRequest.objects.get(id=deposit_id, status='confirmed')
        except USDTDepositRequest.DoesNotExist:
            raise ValueError("Deposit not found or not confirmed")
        
        # Get chain configuration
        chain_config = WalletAddressService.get_chain_config(deposit.chain_type)
        master_address = SweepService.MASTER_WALLET_ADDRESSES.get(deposit.chain_type)
        
        # In production, this would call the blockchain API
        sweep_tx_hash = f"manual_sweep_{deposit.chain_type}_{deposit.transaction_hash[:20]}"
        gas_fee = chain_config.get('gas_fee', Decimal('0.001000'))
        
        # Create sweep log
        sweep_log = SweepLog.objects.create(
            user=deposit.user,
            chain_type=deposit.chain_type,
            from_address=deposit.to_address,
            to_address=master_address,
            amount=deposit.amount,
            gas_fee=gas_fee,
            transaction_hash=sweep_tx_hash,
            sweep_type='manual',
            status='completed',
            initiated_by=admin_user
        )
        
        # Mark deposit as swept
        deposit.mark_as_swept(sweep_tx_hash, gas_fee)
        
        # Create transaction log
        WalletTransaction.objects.create(
            user=deposit.user,
            transaction_type='sweep',
            wallet_type='usdt',
            chain_type=deposit.chain_type,
            amount=deposit.amount,
            balance_before=deposit.user.usdt_wallet.balance,
            balance_after=deposit.user.usdt_wallet.balance - deposit.amount,
            status='completed',
            reference_id=sweep_tx_hash,
            description=f"Manual sweep to master wallet - {deposit.chain_type.upper()} - Gas: {gas_fee} {chain_config.get('gas_token', 'ETH')}",
            metadata={'chain_type': deposit.chain_type, 'gas_token': chain_config.get('gas_token')}
        )
        
        # Deduct from user wallet
        usdt_wallet = deposit.user.usdt_wallet
        usdt_wallet.deduct_balance(deposit.amount)
        
        return True
        
    @staticmethod
    def get_sweep_logs(user=None, chain_type=None, sweep_type=None, status=None):
        """Get sweep logs with optional filters."""
        queryset = SweepLog.objects.all()
        
        if user:
            queryset = queryset.filter(user=user)
        if chain_type:
            queryset = queryset.filter(chain_type=chain_type)
        if sweep_type:
            queryset = queryset.filter(sweep_type=sweep_type)
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.select_related('user', 'initiated_by').order_by('-created_at')


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
        """Get or create USDT wallet for user with real wallet generation if needed."""
        wallet, created = USDTWallet.objects.get_or_create(
            user=user,
            defaults={'balance': Decimal('0.000000')}
        )
        
        # Check if we should use real wallets
        use_real_wallets = config('USE_DUMMY_WALLETS', default='True').lower() == 'false'
        
        if use_real_wallets and not wallet.is_real_wallet:
            # Import here to avoid circular imports
            from app.services.real_wallet_service import real_wallet_service
            
            # Generate real wallet
            result = real_wallet_service.generate_real_wallet(user, 'erc20')
            if result['success']:
                wallet.refresh_from_db()
        
        return wallet
    
    @staticmethod
    def get_wallet_balance(user):
        """Get combined wallet balance for user."""
        inr_wallet = WalletService.get_or_create_inr_wallet(user)
        usdt_wallet = WalletService.get_or_create_usdt_wallet(user)
        
        # Get user's wallet addresses for all chains
        wallet_addresses = {}
        for address in WalletAddressService.get_all_wallet_addresses(user):
            wallet_addresses[address.chain_type] = address.address
        
        return {
            'inr_balance': inr_wallet.balance,
            'usdt_balance': usdt_wallet.balance,
            'wallet_addresses': wallet_addresses,
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
            # Save the wallet after balance update
            wallet.save()
            
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
            # Save the wallet after balance update
            wallet.save()
            
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
    def add_usdt_balance(user, amount, transaction_type='admin_adjustment', description='', reference_id=None, chain_type=None):
        """Add USDT balance to user wallet with transaction log."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        wallet = WalletService.get_or_create_usdt_wallet(user)
        
        if not wallet.can_transact():
            raise ValueError("Wallet is not active for transactions")
        
        balance_before = wallet.balance
        if wallet.add_balance(amount):
            # Save the wallet after balance update
            wallet.save()
            
            # Create transaction log
            metadata = {'chain_type': chain_type} if chain_type else {}
            WalletTransaction.objects.create(
                user=user,
                transaction_type=transaction_type,
                wallet_type='usdt',
                chain_type=chain_type,
                amount=amount,
                balance_before=balance_before,
                balance_after=wallet.balance,
                status='completed',
                reference_id=reference_id,
                description=description,
                metadata=metadata
            )
            return True
        return False
    
    @staticmethod
    @transaction.atomic
    def deduct_usdt_balance(user, amount, transaction_type='withdrawal', description='', reference_id=None, chain_type=None):
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
            # Save the wallet after balance update
            wallet.save()
            
            # Create transaction log
            metadata = {'chain_type': chain_type} if chain_type else {}
            WalletTransaction.objects.create(
                user=user,
                transaction_type=transaction_type,
                wallet_type='usdt',
                chain_type=chain_type,
                amount=amount,
                balance_before=balance_before,
                balance_after=wallet.balance,
                status='completed',
                reference_id=reference_id,
                description=description,
                metadata=metadata
            )
            return True
        return False


class DepositService:
    """Service class for INR deposit operations."""
    
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
    def get_user_transactions(user, wallet_type=None, chain_type=None, transaction_type=None, 
                            status=None, page=1, page_size=20):
        """Get paginated transactions for a user."""
        queryset = WalletTransaction.objects.filter(user=user)
        
        if wallet_type:
            queryset = queryset.filter(wallet_type=wallet_type)
        if chain_type:
            queryset = queryset.filter(chain_type=chain_type)
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
            'transaction_count': transactions.count(),
            'chain_breakdown': {}
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
            
            # Track chain breakdown for USDT transactions
            if transaction.wallet_type == 'usdt' and transaction.chain_type:
                if transaction.chain_type not in summary['chain_breakdown']:
                    summary['chain_breakdown'][transaction.chain_type] = {
                        'deposits': Decimal('0.00'),
                        'withdrawals': Decimal('0.00'),
                        'sweeps': Decimal('0.00'),
                    }
                
                if transaction.transaction_type == 'usdt_deposit':
                    summary['chain_breakdown'][transaction.chain_type]['deposits'] += transaction.amount
                elif transaction.transaction_type == 'withdrawal':
                    summary['chain_breakdown'][transaction.chain_type]['withdrawals'] += transaction.amount
                elif transaction.transaction_type == 'sweep':
                    summary['chain_breakdown'][transaction.chain_type]['sweeps'] += transaction.amount
        
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
    def validate_usdt_deposit_amount(amount):
        """Validate USDT deposit amount."""
        if amount < Decimal('0.000001'):
            return False, "Minimum USDT deposit amount is 0.000001"
        if amount > Decimal('10000.000000'):
            return False, "Maximum USDT deposit amount is 10,000 USDT"
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