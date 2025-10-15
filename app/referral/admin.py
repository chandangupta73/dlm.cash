from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Referral, ReferralEarning, ReferralMilestone, 
    UserReferralProfile, ReferralConfig
)


@admin.register(UserReferralProfile)
class UserReferralProfileAdmin(admin.ModelAdmin):
    """Admin interface for UserReferralProfile."""
    
    list_display = [
        'user_email', 'referral_code', 'referred_by_email', 
        'total_referrals', 'total_earnings_inr', 'total_earnings_usdt', 'last_earning_date'
    ]
    list_filter = ['created_at', 'last_earning_date', 'referred_by']
    search_fields = ['user__email', 'user__username', 'referral_code', 'referred_by__email']
    readonly_fields = [
        'created_at', 'updated_at', 'user', 'referral_code', 'total_referrals', 'total_earnings',
        'total_earnings_inr', 'total_earnings_usdt', 'last_earning_date'
    ]
    ordering = ['-created_at']
    
    def user_email(self, obj):
        """Display user email with link to user admin."""
        if obj.user:
            url = reverse('admin:users_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return '-'
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'
    
    def referred_by_email(self, obj):
        """Display referrer email with link."""
        if obj.referred_by:
            url = reverse('admin:users_user_change', args=[obj.referred_by.id])
            return format_html('<a href="{}">{}</a>', url, obj.referred_by.email)
        return '-'
    referred_by_email.short_description = 'Referred By'
    
    def total_earnings_display(self, obj):
        """Display total earnings with currency breakdown."""
        if obj.total_earnings > 0:
            return format_html(
                '<strong>Total: {}</strong><br/>'
                '<small>INR: ₹{} | USDT: {}</small>',
                obj.total_earnings, obj.total_earnings_inr, obj.total_earnings_usdt
            )
        return '₹0.00'
    total_earnings_display.short_description = 'Total Earnings'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('user', 'referred_by')
    
    actions = ['regenerate_referral_codes', 'update_stats']
    
    def regenerate_referral_codes(self, request, queryset):
        """Regenerate referral codes for selected profiles."""
        updated = 0
        for profile in queryset:
            profile.generate_referral_code()
            profile.save()
            updated += 1
        
        self.message_user(
            request, 
            f'Successfully regenerated referral codes for {updated} profiles.'
        )
    regenerate_referral_codes.short_description = "Regenerate referral codes"
    
    def update_stats(self, request, queryset):
        """Update statistics for selected profiles."""
        updated = 0
        for profile in queryset:
            profile.update_stats()
            updated += 1
        
        self.message_user(
            request, 
            f'Successfully updated statistics for {updated} profiles.'
        )
    update_stats.short_description = "Update referral statistics"


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    """Admin interface for Referral model."""
    
    list_display = [
        'user_email', 'referred_user_email', 'level', 'referrer_email',
        'created_at', 'is_direct_referral'
    ]
    list_filter = ['level', 'created_at']
    search_fields = [
        'user__email', 'referred_user__email', 'referrer__email'
    ]
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def user_email(self, obj):
        """Display referrer user email with link."""
        if obj.user:
            url = reverse('admin:users_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return '-'
    user_email.short_description = 'Referrer'
    user_email.admin_order_field = 'user__email'
    
    def referred_user_email(self, obj):
        """Display referred user email with link."""
        if obj.referred_user:
            url = reverse('admin:users_user_change', args=[obj.referred_user.id])
            return format_html('<a href="{}">{}</a>', url, obj.referred_user.email)
        return '-'
    referred_user_email.short_description = 'Referred User'
    referred_user_email.admin_order_field = 'referred_user__email'
    
    def referrer_email(self, obj):
        """Display upline referrer email with link."""
        if obj.referrer:
            url = reverse('admin:users_user_change', args=[obj.referrer.id])
            return format_html('<a href="{}">{}</a>', url, obj.referrer.email)
        return '-'
    referrer_email.short_description = 'Upline Referrer'
    
    def is_direct_referral(self, obj):
        """Display if this is a direct referral."""
        if obj.level == 1:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Direct</span>'
            )
        return format_html(
            '<span style="color: orange;">Level {}</span>', obj.level
        )
    is_direct_referral.short_description = 'Type'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'user', 'referred_user', 'referrer'
        )


@admin.register(ReferralEarning)
class ReferralEarningAdmin(admin.ModelAdmin):
    """Admin interface for ReferralEarning model."""
    
    list_display = [
        'referral_user_email', 'referred_user_email', 'level', 'amount_currency',
        'percentage_used', 'status', 'investment_link', 'created_at'
    ]
    list_filter = ['level', 'currency', 'status', 'created_at']
    search_fields = [
        'referral__user__email', 'referral__referred_user__email',
        'investment__id', 'currency'
    ]
    readonly_fields = [
        'referral', 'investment', 'level', 'amount', 'currency',
        'percentage_used', 'created_at', 'updated_at'
    ]
    ordering = ['-created_at']
    
    def user_email(self, obj):
        """Display earning recipient email with link."""
        if obj.referral and obj.referral.user:
            url = reverse('admin:users_user_change', args=[obj.referral.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.referral.user.email)
        return '-'
    user_email.short_description = 'Earning Recipient'
    
    def referral_user_email(self, obj):
        """Display earning recipient email with link."""
        if obj.referral and obj.referral.user:
            url = reverse('admin:users_user_change', args=[obj.referral.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.referral.user.email)
        return '-'
    referral_user_email.short_description = 'Earning Recipient'
    
    def referred_user_email(self, obj):
        """Display referred user email with link."""
        if obj.referral and obj.referral.referred_user:
            url = reverse('admin:users_user_change', args=[obj.referral.referred_user.id])
            return format_html('<a href="{}">{}</a>', url, obj.referral.referred_user.email)
        return '-'
    referred_user_email.short_description = 'Referred User'
    
    def amount_currency(self, obj):
        """Display amount with currency."""
        currency_symbol = '₹' if obj.currency == 'INR' else '$'
        return f"{currency_symbol}{obj.amount} {obj.currency}"
    amount_currency.short_description = 'Amount'
    
    def investment_link(self, obj):
        """Display investment ID with link."""
        if obj.investment:
            url = reverse('admin:investment_investment_change', args=[obj.investment.id])
            return format_html('<a href="{}">{}</a>', url, str(obj.investment.id)[:8])
        return '-'
    investment_link.short_description = 'Investment'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'referral__user', 'referral__referred_user', 'investment'
        )
    
    actions = ['credit_pending_earnings', 'mark_as_failed']
    
    def credit_pending_earnings(self, request, queryset):
        """Credit pending earnings to wallets."""
        pending_earnings = queryset.filter(status='pending')
        credited = 0
        failed = 0
        
        for earning in pending_earnings:
            if earning.credit_to_wallet():
                credited += 1
            else:
                failed += 1
        
        self.message_user(
            request,
            f'Successfully credited {credited} earnings. Failed: {failed}'
        )
    credit_pending_earnings.short_description = "Credit pending earnings"
    
    def mark_as_failed(self, request, queryset):
        """Mark selected earnings as failed."""
        updated = queryset.update(status='failed')
        self.message_user(
            request,
            f'Marked {updated} earnings as failed.'
        )
    mark_as_failed.short_description = "Mark as failed"


@admin.register(ReferralMilestone)
class ReferralMilestoneAdmin(admin.ModelAdmin):
    """Admin interface for ReferralMilestone model."""
    
    list_display = [
        'name', 'condition_type', 'condition_value', 'bonus_amount',
        'is_active', 'created_at'
    ]
    list_filter = ['condition_type', 'currency', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'condition_type']
    list_editable = ['is_active']
    ordering = ['-created_at']
    
    def bonus_amount_currency(self, obj):
        """Display bonus amount with currency."""
        currency_symbol = '₹' if obj.currency == 'INR' else '$'
        return f"{currency_symbol}{obj.bonus_amount} {obj.currency}"
    bonus_amount_currency.short_description = 'Bonus Amount'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Milestone Conditions', {
            'fields': ('condition_type', 'condition_value')
        }),
        ('Bonus Details', {
            'fields': ('bonus_amount', 'currency')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ReferralConfig)
class ReferralConfigAdmin(admin.ModelAdmin):
    """Admin interface for ReferralConfig model."""
    
    list_display = [
        'max_levels', 'level_1_percentage', 'level_2_percentage',
        'level_3_percentage', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    list_editable = ['is_active']
    search_fields = ['max_levels']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Configuration', {
            'fields': ('max_levels', 'is_active')
        }),
        ('Referral Percentages', {
            'fields': ('level_1_percentage', 'level_2_percentage', 'level_3_percentage'),
            'description': 'Set the referral bonus percentage for each level'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    readonly_fields = ['created_at', 'updated_at']
    
    def has_add_permission(self, request):
        """Only allow one active configuration."""
        if ReferralConfig.objects.filter(is_active=True).exists():
            return False
        return super().has_add_permission(request)
    
    def save_model(self, request, obj, form, change):
        """Ensure only one configuration is active at a time."""
        if obj.is_active:
            # Deactivate all other configurations
            ReferralConfig.objects.exclude(id=obj.id).update(is_active=False)
        super().save_model(request, obj, form, change)


# Custom admin site customization
admin.site.site_header = "Investment System Admin"
admin.site.site_title = "Investment System"
admin.site.index_title = "Referral System Administration"

# Add custom admin actions
def get_referral_stats():
    """Get referral system statistics for admin dashboard."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    stats = {
        'total_users': User.objects.count(),
        'total_profiles': UserReferralProfile.objects.count(),
        'total_referrals': Referral.objects.count(),
        'total_earnings': ReferralEarning.objects.filter(status='credited').aggregate(
            total=Sum('amount')
        )['total'] or 0,
        'active_milestones': ReferralMilestone.objects.filter(is_active=True).count(),
        'pending_earnings': ReferralEarning.objects.filter(status='pending').count(),
    }
    return stats
