from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, OTP, BankDetails, USDTDetails
from django.utils import timezone


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'first_name', 'last_name', 'is_kyc_verified', 'kyc_status', 'is_active']
    list_filter = ['is_kyc_verified', 'kyc_status', 'is_active', 'date_joined']
    search_fields = ['email', 'username', 'first_name', 'last_name']
    ordering = ['-date_joined']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('KYC Information', {'fields': ('is_kyc_verified', 'kyc_status')}),
        ('Profile Information', {'fields': ('phone_number', 'date_of_birth', 'address', 'city', 'state', 'country', 'postal_code')}),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Profile Information', {'fields': ('phone_number', 'date_of_birth', 'address', 'city', 'state', 'country', 'postal_code')}),
    )


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ['user', 'otp_type', 'is_used', 'created_at', 'expires_at']
    list_filter = ['otp_type', 'is_used', 'created_at']
    search_fields = ['user__email', 'otp_code']
    readonly_fields = ['created_at', 'expires_at']


@admin.register(BankDetails)
class BankDetailsAdmin(admin.ModelAdmin):
    list_display = ['user', 'bank_name', 'account_holder_name', 'is_verified', 'created_at']
    list_filter = ['is_verified', 'bank_name', 'created_at']
    search_fields = ['user__email', 'account_holder_name', 'bank_name', 'account_number']
    readonly_fields = ['created_at', 'updated_at']
    
    actions = ['verify_bank_details', 'unverify_bank_details']
    
    def verify_bank_details(self, request, queryset):
        updated = queryset.update(is_verified=True, verified_at=timezone.now())
        self.message_user(request, f'{updated} bank detail(s) marked as verified.')
    verify_bank_details.short_description = "Mark selected bank details as verified"
    
    def unverify_bank_details(self, request, queryset):
        updated = queryset.update(is_verified=False, verified_at=None)
        self.message_user(request, f'{updated} bank detail(s) marked as unverified.')
    unverify_bank_details.short_description = "Mark selected bank details as unverified"


@admin.register(USDTDetails)
class USDTDetailsAdmin(admin.ModelAdmin):
    list_display = ['user', 'network', 'wallet_address_short', 'is_verified', 'created_at']
    list_filter = ['is_verified', 'network', 'created_at']
    search_fields = ['user__email', 'wallet_address']
    readonly_fields = ['created_at', 'updated_at', 'wallet_address_short']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Wallet Details', {
            'fields': ('wallet_address', 'network', 'qr_code')
        }),
        ('Verification', {
            'fields': ('is_verified', 'verified_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['verify_usdt_details', 'unverify_usdt_details']
    
    def wallet_address_short(self, obj):
        """Display shortened wallet address"""
        if obj.wallet_address:
            return f"{obj.wallet_address[:10]}...{obj.wallet_address[-10:]}"
        return "N/A"
    wallet_address_short.short_description = "Wallet Address"
    
    def verify_usdt_details(self, request, queryset):
        updated = queryset.update(is_verified=True, verified_at=timezone.now())
        self.message_user(request, f'{updated} USDT detail(s) marked as verified.')
    verify_usdt_details.short_description = "Mark selected USDT details as verified"
    
    def unverify_usdt_details(self, request, queryset):
        updated = queryset.update(is_verified=False, verified_at=None)
        self.message_user(request, f'{updated} USDT detail(s) marked as unverified.')
    unverify_usdt_details.short_description = "Mark selected USDT details as unverified" 