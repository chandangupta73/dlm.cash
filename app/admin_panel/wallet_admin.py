from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from app.wallet.models import INRWallet, USDTWallet, WalletTransaction, DepositRequest, WalletAddress
from app.crud.wallet import WalletAddressService
from app.services.real_wallet_service import RealWalletService


@admin.register(INRWallet)
class INRWalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'status', 'is_active', 'created_at']
    list_filter = ['status', 'is_active', 'created_at']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_per_page = 20
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'balance', 'status', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return '-'
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'


@admin.register(USDTWallet)
class USDTWalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'wallet_address', 'status', 'is_active', 'created_at']
    list_filter = ['status', 'is_active', 'created_at']
    search_fields = ['user__username', 'user__email', 'wallet_address']
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_per_page = 20
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'balance', 'wallet_address', 'status', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return '-'
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'transaction_type', 'wallet_type', 'amount', 
        'status', 'created_at'
    ]
    list_filter = [
        'transaction_type', 'wallet_type', 'status', 'created_at'
    ]
    search_fields = [
        'user__username', 'user__email', 'reference_id', 'description'
    ]
    readonly_fields = [
        'id', 'balance_before', 'balance_after', 'created_at', 'updated_at'
    ]
    list_per_page = 50
    
    fieldsets = (
        ('Transaction Details', {
            'fields': (
                'id', 'user', 'transaction_type', 'wallet_type', 'amount',
                'balance_before', 'balance_after', 'status'
            )
        }),
        ('Additional Information', {
            'fields': ('reference_id', 'description', 'metadata'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return '-'
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'
    
    def amount_display(self, obj):
        if obj.wallet_type == 'inr':
            return f"₹{obj.amount}"
        else:
            return f"${obj.amount}"
    amount_display.short_description = 'Amount'


@admin.register(DepositRequest)
class DepositRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'amount', 'payment_method', 'status', 
        'created_at', 'processed_at'
    ]
    list_filter = [
        'status', 'payment_method', 'created_at', 'processed_at'
    ]
    search_fields = [
        'user__username', 'user__email', 'reference_number', 
        'transaction_id', 'notes'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'processed_at'
    ]
    list_per_page = 20
    
    fieldsets = (
        ('Request Details', {
            'fields': (
                'id', 'user', 'amount', 'payment_method', 'status'
            )
        }),
        ('Payment Information', {
            'fields': ('reference_number', 'transaction_id', 'screenshot'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes', 'admin_notes'),
            'classes': ('collapse',)
        }),
        ('Processing', {
            'fields': ('processed_by', 'processed_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_deposits', 'reject_deposits']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'processed_by')
    
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return '-'
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'
    
    def amount_display(self, obj):
        return f"₹{obj.amount}"
    amount_display.short_description = 'Amount'
    
    def approve_deposits(self, request, queryset):
        approved_count = 0
        for deposit in queryset.filter(status='pending'):
            if deposit.approve(request.user):
                approved_count += 1
        
        self.message_user(
            request, 
            f'Successfully approved {approved_count} deposit request(s).'
        )
    approve_deposits.short_description = "Approve selected deposits"
    
    def reject_deposits(self, request, queryset):
        rejected_count = 0
        for deposit in queryset.filter(status='pending'):
            if deposit.reject(request.user, "Bulk rejection"):
                rejected_count += 1
        
        self.message_user(
            request, 
            f'Successfully rejected {rejected_count} deposit request(s).'
        )
    reject_deposits.short_description = "Reject selected deposits"
    
    def has_add_permission(self, request):
        return False  # Deposits should only be created via API 


@admin.register(WalletAddress)
class WalletAddressAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'chain_type', 'address', 'is_active', 'created_at'
    ]
    list_filter = ['chain_type', 'is_active', 'created_at']
    search_fields = [
        'user__username', 'user__email', 'address', 'chain_type'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'decrypted_private_key'
    ]
    list_per_page = 20
    
    fieldsets = (
        ('Address Information', {
            'fields': (
                'id', 'user', 'chain_type', 'address', 'is_active'
            )
        }),
        ('Security Information', {
            'fields': ('encrypted_private_key', 'decrypted_private_key'),
            'classes': ('collapse',),
            'description': 'Private key is encrypted in database but shown decrypted here for admin convenience.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def decrypted_private_key(self, obj):
        """Display decrypted private key for admin convenience."""
        if obj.encrypted_private_key:
            try:
                # Decrypt the private key
                wallet_service = RealWalletService()
                decrypted_key = wallet_service.decrypt_private_key(obj.encrypted_private_key)
                return format_html(
                    '<code style="background: #f0f0f0; padding: 2px 4px; border-radius: 3px;">{}</code>',
                    decrypted_key
                )
            except Exception as e:
                return f"Error decrypting: {str(e)}"
        return "No private key"
    decrypted_private_key.short_description = "Decrypted Private Key"
    decrypted_private_key.allow_tags = True
    
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return '-'
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username' 