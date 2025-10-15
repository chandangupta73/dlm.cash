from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.conf import settings
import uuid
from decimal import Decimal

User = get_user_model()


class TimeStampedModel(models.Model):
    """Abstract base model with created and updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class WalletAddress(TimeStampedModel):
    """Model for managing multi-chain wallet addresses."""
    
    CHAIN_TYPE_CHOICES = [
        ('erc20', 'ERC20 (Ethereum)'),
        ('bep20', 'BEP20 (Binance Smart Chain)'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet_addresses')
    chain_type = models.CharField(max_length=10, choices=CHAIN_TYPE_CHOICES, default='trc20')
    address = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'wallet_address'
        verbose_name = 'Wallet Address'
        verbose_name_plural = 'Wallet Addresses'
        unique_together = ['user', 'chain_type']  # One address per chain per user
        indexes = [
            models.Index(fields=['user', 'chain_type']),
            models.Index(fields=['address', 'chain_type']),
        ]
    
    def __str__(self):
        return f"{self.chain_type.upper()} Address - {self.user.username} ({self.address[:10]}...)"
    
    def mark_as_used(self):
        """Mark address as recently used."""
        self.last_used = timezone.now()
        self.save(update_fields=['last_used'])


class INRWallet(TimeStampedModel):
    """INR Wallet model for storing Indian Rupee balances."""
    
    WALLET_STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('locked', 'Locked'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inr_wallet')
    balance = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(0)]
    )
    status = models.CharField(
        max_length=20, 
        choices=WALLET_STATUS_CHOICES, 
        default='active'
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'inr_wallet'
        verbose_name = 'INR Wallet'
        verbose_name_plural = 'INR Wallets'
    
    def __str__(self):
        return f"INR Wallet - {self.user.username} (₹{self.balance})"
    
    def can_transact(self):
        """Check if wallet can perform transactions."""
        return self.is_active and self.status == 'active'
    
    def add_balance(self, amount):
        """Add balance to wallet."""
        if amount > 0:
            self.balance = self.balance + amount
            # Don't save here - let the calling code handle it
            return True
        return False
    
    def deduct_balance(self, amount):
        """Deduct balance from wallet."""
        if amount > 0 and self.balance >= amount and self.can_transact():
            self.balance = self.balance - amount
            # Don't save here - let the calling code handle it
            return True
        return False


class USDTWallet(TimeStampedModel):
    """USDT Wallet model for storing Tether balances and real blockchain wallet data."""
    
    WALLET_STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('locked', 'Locked'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='usdt_wallet')
    balance = models.DecimalField(
        max_digits=20, 
        decimal_places=6, 
        default=0.000000,
        validators=[MinValueValidator(0)]
    )
    status = models.CharField(
        max_length=20, 
        choices=WALLET_STATUS_CHOICES, 
        default='active'
    )
    is_active = models.BooleanField(default=True)
    
    # Real blockchain wallet fields
    wallet_address = models.CharField(max_length=255, blank=True, null=True, help_text="User's real blockchain wallet address")
    private_key_encrypted = models.TextField(blank=True, null=True, help_text="Encrypted private key")
    chain_type = models.CharField(
        max_length=10, 
        choices=[
            ('erc20', 'ERC20 (Ethereum)'),
            ('bep20', 'BEP20 (Binance Smart Chain)'),
        ],
        default='erc20',
        help_text="Chain type for this wallet"
    )
    is_real_wallet = models.BooleanField(default=False, help_text="Whether this is a real blockchain wallet or dummy")
    last_sweep_at = models.DateTimeField(null=True, blank=True, help_text="Last time funds were swept to master wallet")
    
    class Meta:
        db_table = 'usdt_wallet'
        verbose_name = 'USDT Wallet'
        verbose_name_plural = 'USDT Wallets'
    
    def __str__(self):
        return f"USDT Wallet - {self.user.username} (${self.balance})"
    
    def can_transact(self):
        """Check if wallet can perform transactions."""
        return self.is_active and self.status == 'active'
    
    def add_balance(self, amount):
        """Add balance to wallet."""
        if amount > 0:
            self.balance = self.balance + amount
            # Don't save here - let the calling code handle it
            return True
        return False
    
    def deduct_balance(self, amount):
        """Deduct balance from wallet."""
        if amount > 0 and self.balance >= amount and self.can_transact():
            self.balance = self.balance - amount
            # Don't save here - let the calling code handle it
            return True
        return False


class USDTDepositRequest(TimeStampedModel):
    """Model for handling multi-chain USDT deposit requests and blockchain confirmations."""
    
    CHAIN_TYPE_CHOICES = [
        ('erc20', 'ERC20 (Ethereum)'),
        ('bep20', 'BEP20 (Binance Smart Chain)'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('swept', 'Swept'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    SWEEP_TYPE_CHOICES = [
        ('auto', 'Auto Sweep'),
        ('manual', 'Manual Sweep'),
        ('none', 'No Sweep'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='usdt_deposits')
    chain_type = models.CharField(max_length=10, choices=CHAIN_TYPE_CHOICES, default='trc20')
    amount = models.DecimalField(max_digits=20, decimal_places=6, validators=[MinValueValidator(0.000001)])
    transaction_hash = models.CharField(max_length=255, unique=True)
    from_address = models.CharField(max_length=255)
    to_address = models.CharField(max_length=255)  # User's wallet address
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sweep_type = models.CharField(max_length=10, choices=SWEEP_TYPE_CHOICES, default='none')
    sweep_tx_hash = models.CharField(max_length=255, blank=True, null=True)
    gas_fee = models.DecimalField(max_digits=20, decimal_places=6, default=0.000000)
    block_number = models.BigIntegerField(null=True, blank=True)
    confirmation_count = models.IntegerField(default=0)
    required_confirmations = models.IntegerField(default=12)  # Default confirmations
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='processed_usdt_deposits'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'usdt_deposit_request'
        verbose_name = 'USDT Deposit Request'
        verbose_name_plural = 'USDT Deposit Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['transaction_hash']),
            models.Index(fields=['to_address', 'chain_type']),
            models.Index(fields=['chain_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"USDT Deposit - {self.user.username} (${self.amount}) - {self.chain_type.upper()} - {self.status}"
    
    def get_required_confirmations(self):
        """Get required confirmations based on chain type."""
        confirmations = {
            'trc20': 12,
            'erc20': 12,
            'bep20': 15,
        }
        return confirmations.get(self.chain_type, 12)
    
    def confirm_deposit(self, admin_user=None):
        """Confirm the USDT deposit and credit user wallet."""
        if self.status == 'pending' and self.confirmation_count >= self.get_required_confirmations():
            self.status = 'confirmed'
            self.processed_by = admin_user
            self.processed_at = timezone.now()
            self.save()
            
            # Add balance to user's USDT wallet
            usdt_wallet, created = USDTWallet.objects.get_or_create(user=self.user)
            if usdt_wallet.add_balance(self.amount):
                # Create transaction log
                WalletTransaction.objects.create(
                    user=self.user,
                    transaction_type='usdt_deposit',
                    wallet_type='usdt',
                    amount=self.amount,
                    balance_before=usdt_wallet.balance - self.amount,
                    balance_after=usdt_wallet.balance,
                    status='completed',
                    reference_id=self.transaction_hash,
                    description=f"USDT deposit confirmed - {self.chain_type.upper()} - TX: {self.transaction_hash[:10]}...",
                    metadata={'chain_type': self.chain_type}
                )
                return True
        return False
    
    def mark_as_swept(self, sweep_tx_hash, gas_fee=0):
        """Mark deposit as swept to master wallet."""
        if self.status == 'confirmed':
            self.status = 'swept'
            self.sweep_tx_hash = sweep_tx_hash
            self.gas_fee = gas_fee
            self.save()
            return True
        return False


class SweepLog(TimeStampedModel):
    """Model for logging sweep operations from user wallets to master wallet."""
    
    CHAIN_TYPE_CHOICES = [
        ('erc20', 'ERC20 (Ethereum)'),
        ('bep20', 'BEP20 (Binance Smart Chain)'),
    ]
    
    SWEEP_TYPE_CHOICES = [
        ('auto', 'Auto Sweep'),
        ('manual', 'Manual Sweep'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sweep_logs')
    chain_type = models.CharField(max_length=10, choices=CHAIN_TYPE_CHOICES, default='trc20')
    from_address = models.CharField(max_length=255)  # User's wallet address
    to_address = models.CharField(max_length=255)    # Master wallet address
    amount = models.DecimalField(max_digits=20, decimal_places=6)
    gas_fee = models.DecimalField(max_digits=20, decimal_places=6, default=0.000000)
    transaction_hash = models.CharField(max_length=255, blank=True, null=True)
    sweep_type = models.CharField(max_length=10, choices=SWEEP_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='initiated_sweeps'
    )
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'sweep_log'
        verbose_name = 'Sweep Log'
        verbose_name_plural = 'Sweep Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['sweep_type', 'created_at']),
            models.Index(fields=['transaction_hash']),
            models.Index(fields=['chain_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"Sweep - {self.user.username} (${self.amount}) - {self.chain_type.upper()} - {self.status}"


class WalletTransaction(TimeStampedModel):
    """Transaction log for all wallet activities."""
    
    TRANSACTION_TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('transfer', 'Transfer'),
        ('roi_credit', 'ROI Credit'),
        ('referral_bonus', 'Referral Bonus'),
        ('admin_adjustment', 'Admin Adjustment'),
        ('investment', 'Investment'),
        ('refund', 'Refund'),
        ('sweep', 'Sweep'),
        ('usdt_deposit', 'USDT Deposit'),
    ]
    
    TRANSACTION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    WALLET_TYPE_CHOICES = [
        ('inr', 'INR'),
        ('usdt', 'USDT'),
    ]
    
    CHAIN_TYPE_CHOICES = [
        ('erc20', 'ERC20 (Ethereum)'),
        ('bep20', 'BEP20 (Binance Smart Chain)'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    wallet_type = models.CharField(max_length=10, choices=WALLET_TYPE_CHOICES)
    chain_type = models.CharField(max_length=10, choices=CHAIN_TYPE_CHOICES, blank=True, null=True)
    amount = models.DecimalField(max_digits=20, decimal_places=6)
    balance_before = models.DecimalField(max_digits=20, decimal_places=6)
    balance_after = models.DecimalField(max_digits=20, decimal_places=6)
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS_CHOICES, default='pending')
    reference_id = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'wallet_transaction'
        verbose_name = 'Wallet Transaction'
        verbose_name_plural = 'Wallet Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'transaction_type']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['wallet_type', 'created_at']),
            models.Index(fields=['chain_type', 'created_at']),
        ]
    
    def __str__(self):
        chain_info = f" - {self.chain_type.upper()}" if self.chain_type else ""
        return f"{self.transaction_type} - {self.user.username} ({self.amount}){chain_info}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate balance after if not set."""
        if not self.balance_after and self.balance_before is not None:
            if self.transaction_type in ['deposit', 'roi_credit', 'referral_bonus', 'admin_adjustment', 'refund', 'usdt_deposit']:
                self.balance_after = self.balance_before + self.amount
            elif self.transaction_type in ['withdrawal', 'transfer', 'investment', 'sweep']:
                self.balance_after = self.balance_before - self.amount
        super().save(*args, **kwargs)


class DepositRequest(TimeStampedModel):
    """Model for handling INR deposit requests."""
    
    PAYMENT_METHOD_CHOICES = [
        ('bank_transfer', 'Bank Transfer'),
        ('upi', 'UPI'),
        ('razorpay', 'Razorpay'),
        ('crypto', 'Cryptocurrency'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='deposit_requests')
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.01)])
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reference_number = models.CharField(max_length=255, blank=True, null=True)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    screenshot = models.ImageField(upload_to='deposits/', blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    admin_notes = models.TextField(blank=True, null=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='processed_deposits'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'deposit_request'
        verbose_name = 'Deposit Request'
        verbose_name_plural = 'Deposit Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['payment_method', 'created_at']),
        ]
    
    def __str__(self):
        return f"Deposit - {self.user.username} (₹{self.amount}) - {self.status}"
    
    def approve(self, admin_user):
        """Approve the deposit request."""
        if self.status == 'pending':
            self.status = 'approved'
            self.processed_by = admin_user
            self.processed_at = timezone.now()
            self.save()
            
            # Add balance to user's INR wallet
            inr_wallet, created = INRWallet.objects.get_or_create(
                user=self.user,
                defaults={
                    'balance': Decimal('0.00'),
                    'status': 'active',
                    'is_active': True
                }
            )
            
            # Ensure amount is Decimal
            amount = Decimal(str(self.amount))
            
            if inr_wallet.add_balance(amount):
                # Save the wallet with updated balance
                inr_wallet.save()
                
                # Create transaction log
                WalletTransaction.objects.create(
                    user=self.user,
                    transaction_type='deposit',
                    wallet_type='inr',
                    amount=amount,
                    balance_before=inr_wallet.balance - amount,
                    balance_after=inr_wallet.balance,
                    status='completed',
                    reference_id=self.transaction_id or str(self.id),
                    description=f"Deposit via {self.get_payment_method_display()}"
                )
                return True
        return False
    
    def reject(self, admin_user, reason=""):
        """Reject the deposit request."""
        if self.status == 'pending':
            self.status = 'rejected'
            self.processed_by = admin_user
            self.processed_at = timezone.now()
            self.admin_notes = reason
            self.save()
            return True
        return False
