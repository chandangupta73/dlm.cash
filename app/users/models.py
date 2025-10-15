from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.conf import settings
import uuid
from django.utils import timezone


class User(AbstractUser):
    """Custom User model with additional fields for KYC"""
    
    # Basic fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ],
        blank=True,
        null=True
    )
    
    # KYC related fields
    is_kyc_verified = models.BooleanField(default=False)
    kyc_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('APPROVED', 'Approved'),
            ('REJECTED', 'Rejected'),
        ],
        default='PENDING'
    )
    
    # Profile fields
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    
    # Verification fields
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Override username to use email
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.email
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class BankDetails(models.Model):
    """Model for storing user bank account details"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='bank_details')
    account_holder_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=50)
    ifsc_code = models.CharField(max_length=20)
    bank_name = models.CharField(max_length=255)
    branch_address = models.TextField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'bank_details'
        verbose_name = 'Bank Details'
        verbose_name_plural = 'Bank Details'
    
    def __str__(self):
        return f"{self.user.email} - {self.bank_name}"


class USDTDetails(models.Model):
    """Model for storing user USDT wallet details for withdrawals"""
    
    NETWORK_CHOICES = [
        ('erc20', 'ERC20 (Ethereum)'),
        ('bep20', 'BEP20 (Binance Smart Chain)'),
        ('trc20', 'TRC20 (Tron)'),
        ('polygon', 'Polygon'),
        ('arbitrum', 'Arbitrum'),
        ('optimism', 'Optimism'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='usdt_details')
    wallet_address = models.CharField(max_length=255, help_text="USDT wallet address for withdrawals")
    network = models.CharField(max_length=20, choices=NETWORK_CHOICES, default='trc20')
    qr_code = models.ImageField(upload_to='usdt_qr_codes/', blank=True, null=True, help_text="QR code image for the wallet address")
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'usdt_details'
        verbose_name = 'USDT Details'
        verbose_name_plural = 'USDT Details'
    
    def __str__(self):
        return f"{self.user.email} - {self.network.upper()} ({self.wallet_address[:10]}...)"
    
    @property
    def network_display_name(self):
        """Get the display name for the network"""
        return dict(self.NETWORK_CHOICES).get(self.network, self.network.upper())


class OTP(models.Model):
    """OTP model for email and phone verification"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='otps')
    otp_type = models.CharField(
        max_length=10,
        choices=[
            ('EMAIL', 'Email'),
            ('PHONE', 'Phone'),
        ]
    )
    otp_code = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'otps'
        verbose_name = 'OTP'
        verbose_name_plural = 'OTPs'
    
    def __str__(self):
        return f"{self.user.email} - {self.otp_type} - {self.otp_code}"


class UserSession(models.Model):
    """User session tracking for security"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=40)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_sessions'
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
    
    def __str__(self):
        return f"{self.user.email} - {self.ip_address}" 