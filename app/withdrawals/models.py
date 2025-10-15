from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
import uuid
import re
import json


class TimeStampedModel(models.Model):
    """Abstract base model with created and updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


from django.db import models

class WithdrawalSettings(models.Model):
    """Global settings for withdrawal rules (editable by admin)."""
    
    auto_approve_usdt_limit = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        default=100,
        help_text="Maximum USDT amount that will be auto-approved"
    )

    auto_approve_inr_limit = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        help_text="Maximum INR amount that will be auto-approved (0 = disabled)"
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Withdrawal Settings (USDT ≤ {self.auto_approve_usdt_limit}, INR ≤ {self.auto_approve_inr_limit})"

    class Meta:
        verbose_name_plural = "Withdrawal Settings"



class Withdrawal(TimeStampedModel):
    """Model for handling withdrawal requests for both INR and USDT."""
    
    CURRENCY_CHOICES = [
        ('INR', 'Indian Rupee'),
        ('USDT', 'Tether USD'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PAYOUT_METHOD_CHOICES = [
        # INR payout methods
        ('bank_transfer', 'Bank Transfer'),
        ('upi_transfer', 'upi Transfer'),
        
        # USDT payout methods
        ('usdt_erc20', 'USDT ERC20'),
        ('usdt_bep20', 'USDT BEP20'),
        ('usdt_trc20', 'USDT TRC20'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='withdrawals')
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES)
    amount = models.DecimalField(
        max_digits=20, 
        decimal_places=6, 
        validators=[MinValueValidator(0.000001)]
    )
    fee = models.DecimalField(
        max_digits=20, 
        decimal_places=6, 
        default=0.000000,
        validators=[MinValueValidator(0)]
    )
    payout_method = models.CharField(max_length=20, choices=PAYOUT_METHOD_CHOICES)
    payout_details = models.TextField(help_text="JSON formatted payout details")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Blockchain specific fields (for USDT)
    tx_hash = models.CharField(max_length=255, blank=True, null=True, help_text="Blockchain transaction hash")
    chain_type = models.CharField(max_length=10, blank=True, null=True, help_text="Chain type for USDT withdrawals")
    gas_fee = models.DecimalField(
        max_digits=20, 
        decimal_places=6, 
        default=0.000000,
        validators=[MinValueValidator(0)]
    )
    
    # Admin processing fields
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='processed_withdrawals'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    # Tracking fields
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'withdrawals'
        verbose_name = 'Withdrawal'
        verbose_name_plural = 'Withdrawals'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['currency', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['payout_method', 'created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name='positive_amount'
            ),
            models.CheckConstraint(
                check=models.Q(fee__gte=0),
                name='non_negative_fee'
            ),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.currency} {self.amount} ({self.status})"
    
    def clean(self):
        """Validate withdrawal request based on currency and payout method."""
        super().clean()
        
        # Validate currency and payout method compatibility
        if self.currency == 'INR':
            if not self.payout_method in ['bank_transfer']:
                raise ValidationError("Invalid payout method for INR currency")
        elif self.currency == 'USDT':
            if not self.payout_method in ['usdt_erc20', 'usdt_bep20', 'usdt_trc20']:
                raise ValidationError("Invalid payout method for USDT currency")
        
        # Validate minimum withdrawal amounts
        min_amounts = {
            'INR': 100.00,  # Minimum ₹100
            'USDT': 10.000000,  # Minimum $10 USDT
        }
        
        if self.amount < min_amounts.get(self.currency, 0):
            raise ValidationError(f"Minimum withdrawal amount for {self.currency} is {min_amounts[self.currency]}")
        
        # Validate payout details based on method
        try:
            payout_data = json.loads(self.payout_details) if isinstance(self.payout_details, str) else self.payout_details
        except (json.JSONDecodeError, TypeError):
            raise ValidationError("Invalid payout details format. Must be valid JSON.")
        
        self._validate_payout_details(payout_data)
    
    def _validate_payout_details(self, payout_data):
        """Validate payout details based on payout method."""
        method = self.payout_method
        
        if method == 'bank_transfer':
            required_fields = ['account_number', 'ifsc_code', 'account_holder_name', 'bank_name']
            for field in required_fields:
                if not payout_data.get(field):
                    raise ValidationError(f"Missing required field for bank transfer: {field}")
            
            # Validate account number
            if not re.match(r'^\d{9,18}$', payout_data['account_number']):
                raise ValidationError("Invalid bank account number format")
            
            # Validate IFSC code
            if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', payout_data['ifsc_code']):
                raise ValidationError("Invalid IFSC code format")
        
        elif method == 'usdt_erc20':
            if not payout_data.get('wallet_address'):
                raise ValidationError("Wallet address is required for USDT ERC20 withdrawals")
            
            if not re.match(r'^0x[a-fA-F0-9]{40}$', payout_data['wallet_address']):
                raise ValidationError("Invalid Ethereum wallet address format")
            
            self.chain_type = 'erc20'
        
        elif method == 'usdt_bep20':
            if not payout_data.get('wallet_address'):
                raise ValidationError("Wallet address is required for USDT BEP20 withdrawals")
            
            if not re.match(r'^0x[a-fA-F0-9]{40}$', payout_data['wallet_address']):
                raise ValidationError("Invalid BSC wallet address format")
            
            self.chain_type = 'bep20'
        
        elif method == 'usdt_trc20':
            if not payout_data.get('wallet_address'):
                raise ValidationError("Wallet address is required for USDT TRC20 withdrawals")
            
            if not re.match(r'^T[A-Za-z1-9]{33}$', payout_data['wallet_address']):
                raise ValidationError("Invalid TRC20 wallet address format")
            
            self.chain_type = 'trc20'
    
    def save(self, *args, **kwargs):
        """Override save to perform validations and set defaults."""
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def total_amount(self):
        """Total amount including fee."""
        # return self.amount + self.fee
        return (self.amount or 0.0) + (self.fee or 0.0)
    
    @property
    def net_amount(self):
        """Net amount after fee deduction."""
        return self.amount
    
    def can_be_processed(self):
        """Check if withdrawal can be processed."""
        return self.status == 'PENDING'
    
    def can_be_cancelled(self):
        """Check if withdrawal can be cancelled."""
        return self.status in ['PENDING', 'PROCESSING']
    
    def approve(self, admin_user, notes=""):
        """Approve the withdrawal request."""
        if not self.can_be_processed():
            return False, "Withdrawal cannot be processed in current status"
        
        self.status = 'APPROVED'
        self.processed_by = admin_user
        self.processed_at = timezone.now()
        self.admin_notes = notes
        self.save()
        
        return True, "Withdrawal approved successfully"
    
    def reject(self, admin_user, reason=""):
        """Reject the withdrawal request and refund balance."""
        if not self.can_be_processed():
            return False, "Withdrawal cannot be processed in current status"
        
        self.status = 'REJECTED'
        self.processed_by = admin_user
        self.processed_at = timezone.now()
        self.rejection_reason = reason
        self.save()
        
        # Refund the amount back to user's wallet
        return self._refund_to_wallet()
    
    def complete(self, admin_user, tx_hash=None, notes=""):
        """Mark withdrawal as completed."""
        if self.status != 'APPROVED':
            return False, "Withdrawal must be approved before completion"
        
        self.status = 'COMPLETED'
        if tx_hash:
            self.tx_hash = tx_hash
        if notes:
            self.admin_notes = notes
        self.save()
        
        return True, "Withdrawal completed successfully"
    
    def cancel(self, admin_user=None, reason=""):
        """Cancel the withdrawal request and refund balance."""
        if not self.can_be_cancelled():
            return False, "Withdrawal cannot be cancelled in current status"
        
        self.status = 'CANCELLED'
        if admin_user:
            self.processed_by = admin_user
            self.processed_at = timezone.now()
        self.rejection_reason = reason
        self.save()
        
        # Refund the amount back to user's wallet
        return self._refund_to_wallet()
    
    def _refund_to_wallet(self):
        """Refund the withdrawal amount back to user's wallet."""
        from app.wallet.models import INRWallet, USDTWallet, WalletTransaction
        
        try:
            if self.currency == 'INR':
                wallet = INRWallet.objects.get(user=self.user)
                if wallet.add_balance(self.total_amount):
                    # Create transaction log
                    WalletTransaction.objects.create(
                        user=self.user,
                        transaction_type='refund',
                        wallet_type='inr',
                        amount=self.total_amount,
                        balance_before=wallet.balance - self.total_amount,
                        balance_after=wallet.balance,
                        status='completed',
                        reference_id=str(self.id),
                        description=f"Withdrawal refund - {self.get_status_display()}",
                        metadata={'withdrawal_id': str(self.id)}
                    )
                    return True, "Amount refunded to INR wallet"
            
            elif self.currency == 'USDT':
                wallet = USDTWallet.objects.get(user=self.user)
                if wallet.add_balance(self.total_amount):
                    # Create transaction log
                    WalletTransaction.objects.create(
                        user=self.user,
                        transaction_type='refund',
                        wallet_type='usdt',
                        amount=self.total_amount,
                        balance_before=wallet.balance - self.total_amount,
                        balance_after=wallet.balance,
                        status='completed',
                        reference_id=str(self.id),
                        description=f"Withdrawal refund - {self.get_status_display()}",
                        metadata={'withdrawal_id': str(self.id)}
                    )
                    return True, "Amount refunded to USDT wallet"
            
            return False, "Failed to refund amount to wallet"
        
        except Exception as e:
            return False, f"Error refunding amount: {str(e)}"
    
    @classmethod
    def get_withdrawal_limits(cls):
        """Get withdrawal limits for different currencies."""
        return {
            'INR': {
                'min': 100.00,
                'max': 500000.00,  # ₹5 Lakh daily limit
                'fee_percentage': 0.0,  # No fee for INR
                'fixed_fee': 0.0,
            },
            'USDT': {
                'min': 10.000000,
                'max': 50000.000000,  # $50K daily limit
                'fee_percentage': 1.0,  # 1% fee
                'fixed_fee': 2.000000,  # $2 fixed fee
            }
        }
    
    @classmethod
    def calculate_fee(cls, currency, amount):
        """Calculate withdrawal fee based on currency and amount."""
        from decimal import Decimal
        
        limits = cls.get_withdrawal_limits()
        currency_limits = limits.get(currency, {})
        
        fee_percentage = Decimal(str(currency_limits.get('fee_percentage', 0.0)))
        fixed_fee = Decimal(str(currency_limits.get('fixed_fee', 0.0)))
        
        percentage_fee = (amount * fee_percentage) / Decimal('100')
        total_fee = percentage_fee + fixed_fee
        
        return total_fee.quantize(Decimal('0.000001'))
    
    @classmethod
    def check_daily_limit(cls, user, currency, amount):
        """Check if withdrawal amount exceeds daily limit."""
        today = timezone.now().date()
        
        # Get today's withdrawals
        today_withdrawals = cls.objects.filter(
            user=user,
            currency=currency,
            created_at__date=today,
            status__in=['PENDING', 'APPROVED', 'PROCESSING', 'COMPLETED']
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        
        limits = cls.get_withdrawal_limits()
        daily_limit = limits.get(currency, {}).get('max', 0)
        
        if (today_withdrawals + amount) > daily_limit:
            return False, f"Daily withdrawal limit of {daily_limit} {currency} exceeded"
        
        return True, "Within daily limit"
    
    @classmethod
    def has_pending_withdrawal(cls, user, currency):
        """Check if user has any pending withdrawal for the currency."""
        # Allow multiple withdrawal requests - only check if total pending amount exceeds wallet balance
        from app.wallet.models import INRWallet, USDTWallet
        
        try:
            if currency == 'INR':
                wallet = INRWallet.objects.get(user=user)
                # Get total pending amount
                total_pending = cls.objects.filter(
                    user=user,
                    currency=currency,
                    status='PENDING'
                ).aggregate(
                    total=models.Sum('amount')
                )['total'] or 0
                
                # Allow multiple withdrawals as long as there's sufficient balance
                # The actual balance check will be done in the serializer
                return False
                
            elif currency == 'USDT':
                wallet = USDTWallet.objects.get(user=user)
                # Get total pending amount
                total_pending = cls.objects.filter(
                    user=user,
                    currency=currency,
                    status='PENDING'
                ).aggregate(
                    total=models.Sum('amount')
                )['total'] or 0
                
                # Allow multiple withdrawals as long as there's sufficient balance
                # The actual balance check will be done in the serializer
                return False
                
        except (INRWallet.DoesNotExist, USDTWallet.DoesNotExist):
            return True  # Block if wallet doesn't exist
        
        return False  # Allow by default