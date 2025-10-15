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


class ReferralConfig(TimeStampedModel):
    """Configuration for referral system settings."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    max_levels = models.PositiveIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Maximum referral levels supported"
    )
    level_1_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100.00'))],
        help_text="Referral bonus percentage for level 1"
    )
    level_2_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('3.00'),
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100.00'))],
        help_text="Referral bonus percentage for level 2"
    )
    level_3_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100.00'))],
        help_text="Referral bonus percentage for level 3"
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'referral_config'
        verbose_name = 'Referral Configuration'
        verbose_name_plural = 'Referral Configurations'
    
    def __str__(self):
        return f"Referral Config - {self.max_levels} levels, L1:{self.level_1_percentage}%, L2:{self.level_2_percentage}%, L3:{self.level_3_percentage}%"
    
    @classmethod
    def get_active_config(cls):
        """Get the active referral configuration."""
        return cls.objects.filter(is_active=True).first()
    
    def get_percentage_for_level(self, level):
        """Get referral percentage for a specific level."""
        if level == 1:
            return self.level_1_percentage
        elif level == 2:
            return self.level_2_percentage
        elif level == 3:
            return self.level_3_percentage
        return Decimal('0.00')


class Referral(TimeStampedModel):
    """Model for tracking referral relationships."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referrals_given',
        help_text="User who referred someone"
    )
    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referrals_received',
        help_text="User who was referred"
    )
    level = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Referral level (1 = direct, 2 = indirect, etc.)"
    )
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='downline_referrals',
        null=True,
        blank=True,
        help_text="The user who referred the referrer (for tracking chain)"
    )
    
    class Meta:
        db_table = 'referrals'
        verbose_name = 'Referral'
        verbose_name_plural = 'Referrals'
        unique_together = ['user', 'referred_user', 'level']
        indexes = [
            models.Index(fields=['user', 'level']),
            models.Index(fields=['referred_user']),
            models.Index(fields=['level', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} → {self.referred_user.email} (Level {self.level})"
    
    @property
    def is_direct_referral(self):
        """Check if this is a direct referral (level 1)."""
        return self.level == 1


class ReferralEarning(TimeStampedModel):
    """Model for tracking referral earnings."""
    
    CURRENCY_CHOICES = [
        ('INR', 'Indian Rupee'),
        ('USDT', 'Tether'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('credited', 'Credited'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referral = models.ForeignKey(
        Referral,
        on_delete=models.CASCADE,
        related_name='earnings',
        help_text="The referral relationship that generated this earning"
    )
    investment = models.ForeignKey(
        'investment.Investment',
        on_delete=models.CASCADE,
        related_name='referral_earnings',
        help_text="The investment that triggered this referral earning"
    )
    level = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Referral level for this earning"
    )
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        validators=[MinValueValidator(Decimal('0.000001'))],
        help_text="Referral bonus amount"
    )
    currency = models.CharField(
        max_length=4,
        choices=CURRENCY_CHOICES,
        help_text="Currency of the referral bonus"
    )
    percentage_used = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100.00'))],
        help_text="Percentage used to calculate this bonus"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    credited_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'referral_earnings'
        verbose_name = 'Referral Earning'
        verbose_name_plural = 'Referral Earnings'
        indexes = [
            models.Index(fields=['referral', 'status']),
            models.Index(fields=['investment', 'status']),
            models.Index(fields=['level', 'created_at']),
            models.Index(fields=['currency', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.referral.user.email} - {self.amount} {self.currency} (Level {self.level})"
    
    def credit_to_wallet(self):
        """Credit the referral bonus to the user's wallet."""
        if self.status != 'pending':
            return False
        
        try:
            user = self.referral.user
            
            if self.currency == 'INR':
                # Credit to INR wallet
                from app.wallet.models import INRWallet
                wallet, created = INRWallet.objects.get_or_create(
                    user=user,
                    defaults={'balance': Decimal('0.00'), 'status': 'active', 'is_active': True}
                )
                
                if wallet.add_balance(self.amount):
                    # Create transaction log
                    from app.wallet.models import WalletTransaction
                    WalletTransaction.objects.create(
                        user=user,
                        transaction_type='referral_bonus',
                        wallet_type='inr',
                        amount=self.amount,
                        balance_before=wallet.balance - self.amount,
                        balance_after=wallet.balance,
                        status='completed',
                        reference_id=str(self.investment.id),
                        description=f"Referral bonus from {self.referral.referred_user.email} (Level {self.level})"
                    )
                    
                    self.status = 'credited'
                    self.credited_at = timezone.now()
                    self.save(update_fields=['status', 'credited_at'])
                    return True
                    
            elif self.currency == 'USDT':
                # Credit to USDT wallet
                from app.wallet.models import USDTWallet
                wallet, created = USDTWallet.objects.get_or_create(
                    user=user,
                    defaults={'balance': Decimal('0.000000'), 'status': 'active', 'is_active': True}
                )
                
                if wallet.add_balance(self.amount):
                    # Create transaction log
                    from app.wallet.models import WalletTransaction
                    WalletTransaction.objects.create(
                        user=user,
                        transaction_type='referral_bonus',
                        wallet_type='usdt',
                        amount=self.amount,
                        balance_before=wallet.balance - self.amount,
                        balance_after=wallet.balance,
                        status='completed',
                        reference_id=str(self.investment.id),
                        description=f"Referral bonus from {self.referral.referred_user.email} (Level {self.level})"
                    )
                    
                    self.status = 'credited'
                    self.credited_at = timezone.now()
                    self.save(update_fields=['status', 'credited_at'])
                    return True
            
            return False
            
        except Exception as e:
            self.status = 'failed'
            self.save(update_fields=['status'])
            return False


class ReferralMilestone(TimeStampedModel):
    """Model for defining referral milestones and bonuses."""
    
    CONDITION_TYPE_CHOICES = [
        ('total_referrals', 'Total Referrals'),
        ('total_earnings', 'Total Earnings'),
    ]
    
    CURRENCY_CHOICES = [
        ('INR', 'Indian Rupee'),
        ('USDT', 'Tether'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="Name of the milestone")
    description = models.TextField(blank=True, null=True, help_text="Description of the milestone")
    condition_type = models.CharField(
        max_length=20,
        choices=CONDITION_TYPE_CHOICES,
        help_text="Type of condition to trigger this milestone"
    )
    condition_value = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Value that must be reached to trigger the milestone"
    )
    bonus_amount = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Bonus amount to be credited when milestone is reached"
    )
    currency = models.CharField(
        max_length=4,
        choices=CURRENCY_CHOICES,
        help_text="Currency of the bonus amount"
    )
    is_active = models.BooleanField(default=True, help_text="Whether this milestone is active")
    
    class Meta:
        db_table = 'referral_milestones'
        verbose_name = 'Referral Milestone'
        verbose_name_plural = 'Referral Milestones'
        ordering = ['condition_value']
        indexes = [
            models.Index(fields=['condition_type', 'is_active']),
            models.Index(fields=['currency', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.condition_value} {self.condition_type} → {self.bonus_amount} {self.currency}"


class UserReferralProfile(TimeStampedModel):
    """Extended user profile for referral tracking."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_profile'
    )
    referral_code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Unique referral code for this user"
    )
    referred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='direct_referrals',
        help_text="User who referred this user (direct referrer)"
    )
    total_referrals = models.PositiveIntegerField(
        default=0,
        help_text="Total number of users referred (all levels)"
    )
    total_earnings = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        default=Decimal('0.000000'),
        help_text="Total referral earnings across all levels"
    )
    total_earnings_inr = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total referral earnings in INR"
    )
    total_earnings_usdt = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        default=Decimal('0.000000'),
        help_text="Total referral earnings in USDT"
    )
    last_earning_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'user_referral_profiles'
        verbose_name = 'User Referral Profile'
        verbose_name_plural = 'User Referral Profiles'
        indexes = [
            models.Index(fields=['referral_code']),
            models.Index(fields=['referred_by']),
            models.Index(fields=['total_referrals']),
        ]
    
    def __str__(self):
        return f"Referral Profile - {self.user.email} (Code: {self.referral_code})"
    
    def generate_referral_code(self):
        """Generate a unique referral code for the user."""
        import random
        import string
        
        # Generate 8-character alphanumeric code
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not UserReferralProfile.objects.filter(referral_code=code).exists():
                self.referral_code = code
                break
    
    def update_stats(self):
        """Update referral statistics."""
        # Count total referrals
        self.total_referrals = Referral.objects.filter(user=self.user).count()
        
        # Calculate total earnings
        earnings = ReferralEarning.objects.filter(
            referral__user=self.user,
            status='credited'
        )
        
        self.total_earnings_inr = earnings.filter(currency='INR').aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        self.total_earnings_usdt = earnings.filter(currency='USDT').aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.000000')
        
        self.total_earnings = self.total_earnings_inr + self.total_earnings_usdt
        
        # Update last earning date
        last_earning = earnings.order_by('-credited_at').first()
        if last_earning:
            self.last_earning_date = last_earning.credited_at
        
        self.save()



