from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class Announcement(models.Model):
    """Model for system-wide announcements displayed to users."""
    
    TARGET_GROUP_CHOICES = [
        ('ALL', 'All Users'),
        ('VERIFIED_ONLY', 'Verified Users Only'),
        ('UNVERIFIED_ONLY', 'Unverified Users Only'),
        ('ACTIVE_INVESTORS', 'Active Investors Only'),
        ('ADMIN_ONLY', 'Admin Users Only'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('SCHEDULED', 'Scheduled'),
        ('EXPIRED', 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    message = models.TextField()
    target_group = models.CharField(
        max_length=20, 
        choices=TARGET_GROUP_CHOICES, 
        default='ALL'
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='ACTIVE'
    )
    priority = models.PositiveIntegerField(
        default=1,
        help_text="Higher number = higher priority (1-10)"
    )
    display_from = models.DateTimeField(
        default=timezone.now,
        help_text="When to start displaying this announcement"
    )
    display_until = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When to stop displaying this announcement (leave blank for permanent)"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='announcements_created'
    )
    is_pinned = models.BooleanField(
        default=False,
        help_text="Pinned announcements appear at the top"
    )
    view_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this announcement has been viewed"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'announcement'
        verbose_name = 'Announcement'
        verbose_name_plural = 'Announcements'
        ordering = ['-priority', '-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['status', 'target_group']),
            models.Index(fields=['display_from', 'display_until']),
            models.Index(fields=['is_pinned', 'priority']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.get_target_group_display()}"
    
    def is_active(self):
        """Check if announcement should be displayed based on time constraints."""
        now = timezone.now()
        
        if self.status != 'ACTIVE':
            return False
            
        if now < self.display_from:
            return False
            
        if self.display_until and now > self.display_until:
            return False
            
        return True
    
    def increment_view_count(self):
        """Increment the view count."""
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def clean(self):
        """Validate that display_until is after display_from."""
        if self.display_until and self.display_from and self.display_until <= self.display_from:
            raise models.ValidationError("Display until date must be after display from date.")
    
    def save(self, *args, **kwargs):
        """Auto-update status based on time constraints."""
        if self.status == 'ACTIVE':
            now = timezone.now()
            if self.display_until and now > self.display_until:
                self.status = 'EXPIRED'
        super().save(*args, **kwargs)


class AdminActionLog(models.Model):
    """Log for all admin actions for audit purposes."""
    
    ACTION_TYPE_CHOICES = [
        ('USER_MANAGEMENT', 'User Management'),
        ('KYC_APPROVAL', 'KYC Approval'),
        ('WALLET_ADJUSTMENT', 'Wallet Adjustment'),
        ('INVESTMENT_MANAGEMENT', 'Investment Management'),
        ('WITHDRAWAL_APPROVAL', 'Withdrawal Approval'),
        ('REFERRAL_MANAGEMENT', 'Referral Management'),
        ('ANNOUNCEMENT', 'Announcement Management'),
        ('SYSTEM_CONFIG', 'System Configuration'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='admin_actions'
    )
    action_type = models.CharField(max_length=30, choices=ACTION_TYPE_CHOICES)
    action_description = models.TextField()
    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='admin_actions_received',
        null=True,
        blank=True
    )
    target_model = models.CharField(max_length=100, blank=True, null=True)
    target_id = models.CharField(max_length=100, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'admin_action_log'
        verbose_name = 'Admin Action Log'
        verbose_name_plural = 'Admin Action Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['admin_user', 'action_type']),
            models.Index(fields=['action_type', 'created_at']),
            models.Index(fields=['target_user', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.action_type} by {self.admin_user.username} - {self.created_at}"
    

class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=150)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Contact from {self.name} - {self.subject}"
