from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import uuid

User = get_user_model()


class TimeStampedModel(models.Model):
    """Abstract base model with created and updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class InvestmentPlan(TimeStampedModel):
    """Model for investment plans that users can invest in."""
    
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    fixed_amount = models.DecimalField(
        max_digits=20, 
        decimal_places=6, 
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Fixed investment amount for this plan"
    )
    roi_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        validators=[
            MinValueValidator(Decimal('0.01')),
            MaxValueValidator(Decimal('100.00'))
        ],
        help_text="ROI rate as percentage per cycle"
    )
    frequency = models.CharField(
        max_length=10, 
        choices=FREQUENCY_CHOICES, 
        default='daily'
    )
    duration_days = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Total duration of investment in days"
    )
    breakdown_window_days = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Days from start date when breakdown is allowed"
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='active'
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'investment_plan'
        verbose_name = 'Investment Plan'
        verbose_name_plural = 'Investment Plans'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['frequency', 'status']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.roi_rate}% {self.frequency}"
    
    def clean(self):
        """Validate that fixed_amount is positive."""
        if self.fixed_amount <= 0:
            raise models.ValidationError("Fixed amount must be greater than 0.")
    
    def get_roi_per_cycle(self):
        """Calculate ROI amount per cycle based on frequency."""
        if self.frequency == 'daily':
            return self.roi_rate / 100
        elif self.frequency == 'weekly':
            return (self.roi_rate / 100) / 7
        elif self.frequency == 'monthly':
            return (self.roi_rate / 100) / 30
        return 0
    
    def get_total_cycles(self):
        """Calculate total number of ROI cycles for the investment duration."""
        if self.frequency == 'daily':
            return self.duration_days
        elif self.frequency == 'weekly':
            return self.duration_days // 7
        elif self.frequency == 'monthly':
            return self.duration_days // 30
        return 0


class Investment(TimeStampedModel):
    """Model for user investments in specific plans."""
    
    CURRENCY_CHOICES = [
        ('INR', 'INR'),
        ('USDT', 'USDT'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('breakdown_pending', 'Breakdown Pending'),
        ('breakdown_approved', 'Breakdown Approved'),
        ('breakdown_rejected', 'Breakdown Rejected'),
        ('cancelled', 'Cancelled'),
        ('pending_admin_approval', 'Pending Admin Approval'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='investments'
    )
    plan = models.ForeignKey(
        InvestmentPlan, 
        on_delete=models.CASCADE, 
        related_name='investments'
    )
    amount = models.DecimalField(
        max_digits=20, 
        decimal_places=6, 
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES)
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('direct_payment', 'Direct Payment'),
            ('admin_request', 'Admin Request'),
        ],
        default='direct_payment',
        help_text="Method used to pay for this investment"
    )
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    roi_accrued = models.DecimalField(
        max_digits=20, 
        decimal_places=6, 
        default=Decimal('0.000000')
    )
    last_roi_credit = models.DateTimeField(null=True, blank=True)
    next_roi_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=25,  # Increased from 20 to accommodate 'pending_admin_approval'
        choices=STATUS_CHOICES, 
        default='active'
    )
    is_active = models.BooleanField(default=True)
    
    # Admin approval tracking
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_investments',
        help_text="Admin user who approved this investment"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this investment was approved by admin"
    )
    
    class Meta:
        db_table = 'investment'
        verbose_name = 'Investment'
        verbose_name_plural = 'Investments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['plan', 'status']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['next_roi_date']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.amount} {self.currency})"
    
    def save(self, *args, **kwargs):
        """Set end_date and next_roi_date on creation or if not set."""
        if not self.end_date and hasattr(self, 'plan') and self.plan:
            self.end_date = self.start_date + timezone.timedelta(days=self.plan.duration_days)
        if not self.next_roi_date and hasattr(self, 'plan') and self.plan:
            self.next_roi_date = self.start_date + self._get_frequency_timedelta()
        super().save(*args, **kwargs)
    
    def _get_frequency_timedelta(self):
        """Get timedelta for ROI frequency."""
        if self.plan.frequency == 'daily':
            return timezone.timedelta(days=1)
        elif self.plan.frequency == 'weekly':
            return timezone.timedelta(weeks=1)
        elif self.plan.frequency == 'monthly':
            return timezone.timedelta(days=30)
        return timezone.timedelta(days=1)
    
    def can_breakdown(self):
        """Check if investment can be broken down."""
        if self.status != 'active':
            return False
        
        breakdown_deadline = self.start_date + timezone.timedelta(
            days=self.plan.breakdown_window_days
        )
        return timezone.now() <= breakdown_deadline
    
    def get_breakdown_amount(self):
        """Calculate breakdown amount after deductions."""
        # Step 1: 80% of original investment
        base_amount = self.amount * Decimal('0.8')
        
        # Step 2: Deduct 50% of ROI received
        roi_deduction = self.roi_accrued * Decimal('0.5')
        
        final_amount = base_amount - roi_deduction
        return max(final_amount, Decimal('0'))
    
    def credit_roi(self, roi_amount):
        """Credit ROI to the investment."""
        self.roi_accrued += roi_amount
        self.last_roi_credit = timezone.now()
        
        # Ensure next_roi_date is set before incrementing
        if not self.next_roi_date:
            self.next_roi_date = self.start_date + self._get_frequency_timedelta()
        else:
            self.next_roi_date = self.next_roi_date + self._get_frequency_timedelta()
        
        # Check if investment is completed
        if timezone.now() >= self.end_date:
            self.status = 'completed'
            self.is_active = False
        
        self.save(update_fields=[
            'roi_accrued', 'last_roi_credit', 'next_roi_date', 
            'status', 'is_active', 'updated_at'
        ])
    
    def request_breakdown(self):
        """Request breakdown for the investment."""
        if not self.can_breakdown():
            raise ValueError("Investment cannot be broken down")
        
        self.status = 'breakdown_pending'
        self.save(update_fields=['status', 'updated_at'])
    
    def approve_breakdown(self):
        """Approve breakdown request."""
        if self.status != 'breakdown_pending':
            raise ValueError("Investment is not in breakdown pending status")
        
        self.status = 'breakdown_approved'
        self.is_active = False
        self.save(update_fields=['status', 'is_active', 'updated_at'])
    
    def reject_breakdown(self):
        """Reject breakdown request and continue investment."""
        if self.status != 'breakdown_pending':
            raise ValueError("Investment is not in breakdown pending status")
        
        self.status = 'active'
        self.save(update_fields=['status', 'updated_at'])


class BreakdownRequest(TimeStampedModel):
    """Model for handling investment breakdown requests."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='breakdown_requests'
    )
    investment = models.OneToOneField(
        Investment, 
        on_delete=models.CASCADE, 
        related_name='breakdown_request'
    )
    requested_amount = models.DecimalField(
        max_digits=20, 
        decimal_places=6,
        help_text="Amount requested for breakdown"
    )
    final_amount = models.DecimalField(
        max_digits=20, 
        decimal_places=6,
        help_text="Final amount after deductions"
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    admin_notes = models.TextField(blank=True, null=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='processed_breakdowns'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'breakdown_request'
        verbose_name = 'Breakdown Request'
        verbose_name_plural = 'Breakdown Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.investment.plan.name} Breakdown"
    
    def approve(self, admin_user):
        """Approve the breakdown request."""
        if self.status != 'pending':
            raise ValueError("Breakdown request is not pending")
        
        self.status = 'approved'
        self.processed_by = admin_user
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'processed_by', 'processed_at', 'updated_at'])
        
        # Credit the user's wallet with the breakdown amount
        from app.wallet.models import INRWallet, WalletTransaction
        from app.wallet.services import WalletService
        
        if self.investment.currency == 'inr':
            # Credit INR wallet
            success = WalletService.add_inr_balance(
                self.user,
                self.final_amount,
                'breakdown_payout',
                f'Breakdown payout from {self.investment.plan.name}'
            )
            if not success:
                raise ValueError("Failed to credit INR wallet")
        else:
            # Credit USDT wallet
            success = WalletService.add_usdt_balance(
                self.user,
                self.final_amount,
                'breakdown_payout',
                f'Breakdown payout from {self.investment.plan.name}'
            )
            if not success:
                raise ValueError("Failed to credit USDT wallet")
        
        # Approve the investment breakdown
        self.investment.approve_breakdown()
    
    def reject(self, admin_user, notes=""):
        """Reject the breakdown request."""
        if self.status != 'pending':
            raise ValueError("Breakdown request is not pending")
        
        self.status = 'rejected'
        self.admin_notes = notes
        self.processed_by = admin_user
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'admin_notes', 'processed_by', 'processed_at', 'updated_at'])
        
        # Reject the investment breakdown
        self.investment.reject_breakdown()
