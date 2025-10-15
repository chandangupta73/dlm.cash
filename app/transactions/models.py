from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.conf import settings
import uuid
from decimal import Decimal

def empty_dict():
    return {}

def get_meta_data_default():
    return {}

User = get_user_model()


class TimeStampedModel(models.Model):
    """Abstract base model with created and updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Transaction(TimeStampedModel):
    """Centralized transaction model for all financial activities across the platform."""
    
    TRANSACTION_TYPE_CHOICES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('ROI', 'ROI Payout'),
        ('REFERRAL_BONUS', 'Referral Bonus'),
        ('MILESTONE_BONUS', 'Milestone Bonus'),
        ('ADMIN_ADJUSTMENT', 'Admin Adjustment'),
        ('PLAN_PURCHASE', 'Investment Plan Purchase'),
        ('BREAKDOWN_REFUND', 'Investment Breakdown Refund'),
    ]
    
    CURRENCY_CHOICES = [
        ('INR', 'Indian Rupee'),
        ('USDT', 'Tether'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='transactions'
    )
    type = models.CharField(
        max_length=20, 
        choices=TRANSACTION_TYPE_CHOICES,
        help_text="Type of transaction"
    )
    currency = models.CharField(
        max_length=10, 
        choices=CURRENCY_CHOICES,
        help_text="Currency of the transaction"
    )
    amount = models.DecimalField(
        max_digits=20, 
        decimal_places=6,  # Consistent with USDT precision
        validators=[MinValueValidator(Decimal('0.000001'))],
        help_text="Transaction amount"
    )
    reference_id = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Reference ID to related object (e.g., investment ID, withdrawal ID)"
    )
    meta_data = models.JSONField(
        default=get_meta_data_default, 
        blank=True,
        help_text="Additional transaction metadata (tx hash, bank details, notes, etc.)"
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='SUCCESS'
    )
    
    class Meta:
        db_table = 'transaction'
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'type']),
            models.Index(fields=['user', 'currency']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['type', 'created_at']),
            models.Index(fields=['currency', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['reference_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.type} - {self.user.username} ({self.currency} {self.amount}) - {self.status}"
    
    @property
    def formatted_amount(self):
        """Return formatted amount based on currency."""
        if self.currency == 'INR':
            return f"₹{self.amount:,.2f}"
        elif self.currency == 'USDT':
            return f"${self.amount:,.6f}"
        return str(self.amount)
    
    @property
    def is_credit(self):
        """Check if transaction is a credit to user's wallet."""
        return self.type in ['DEPOSIT', 'ROI', 'REFERRAL_BONUS', 'MILESTONE_BONUS', 'ADMIN_ADJUSTMENT', 'BREAKDOWN_REFUND']
    
    @property
    def is_debit(self):
        """Check if transaction is a debit from user's wallet."""
        return self.type in ['WITHDRAWAL', 'PLAN_PURCHASE']
    
    def get_balance_impact(self):
        """Get the balance impact of this transaction."""
        if self.is_credit:
            return self.amount
        elif self.is_debit:
            return -self.amount
        return Decimal('0')
    
    def update_status(self, new_status, meta_data_update=None):
        """Update transaction status and optionally add metadata."""
        self.status = new_status
        if meta_data_update:
            self.meta_data.update(meta_data_update)
        self.save(update_fields=['status', 'meta_data', 'updated_at'])
    
    def add_metadata(self, key, value):
        """Add or update metadata key-value pair."""
        self.meta_data[key] = value
        self.save(update_fields=['meta_data', 'updated_at'])
    
    @classmethod
    def create_transaction(cls, user, type, currency, amount, reference_id=None, meta_data=None, status='SUCCESS'):
        """Create a new transaction with proper validation."""
        if amount <= 0:
            raise ValueError("Transaction amount must be positive")
        
        if not user.is_active:
            raise ValueError("Cannot create transaction for inactive user")
        
        # Validate currency-specific amount precision
        if currency == 'INR' and amount.as_tuple().exponent < -2:
            raise ValueError("INR amounts cannot have more than 2 decimal places")
        elif currency == 'USDT' and amount.as_tuple().exponent < -6:
            raise ValueError("USDT amounts cannot have more than 6 decimal places")
        
        transaction = cls.objects.create(
            user=user,
            type=type,
            currency=currency,
            amount=amount,
            reference_id=reference_id,
            meta_data=meta_data or {},
            status=status
        )
        
        return transaction
