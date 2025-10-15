from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from .models import Withdrawal, WithdrawalSettings
import json


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    """Admin interface for Withdrawal model."""
    
    list_display = [
        'id_short', 'user_email', 'currency', 'amount_display', 
        'fee_display', 'total_amount_display', 'payout_method', 
        'status_display', 'created_at', 'processed_at'
    ]
    
    list_filter = [
        'currency', 'status', 'payout_method', 'chain_type',
        'created_at', 'processed_at'
    ]
    
    search_fields = [
        'user__email', 'user__username', 'tx_hash', 
        'payout_details', 'admin_notes'
    ]
    
    readonly_fields = [
        'id', 'user', 'created_at', 'updated_at', 'ip_address', 
        'user_agent', 'total_amount_display', 'net_amount_display',
        'payout_details_formatted'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'id', 'user', 'currency', 'amount', 'fee', 
                'total_amount_display', 'net_amount_display'
            )
        }),
        ('Payout Details', {
            'fields': (
                'payout_method', 'payout_details', 'payout_details_formatted'
            )
        }),
        ('Status & Processing', {
            'fields': (
                'status', 'processed_by', 'processed_at', 
                'admin_notes', 'rejection_reason'
            )
        }),
        ('Blockchain Details (USDT)', {
            'fields': (
                'tx_hash', 'chain_type', 'gas_fee'
            ),
            'classes': ('collapse',)
        }),
        ('Tracking Information', {
            'fields': (
                'ip_address', 'user_agent', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    ordering = ['-created_at']
    list_per_page = 25
    
    actions = ['approve_selected', 'reject_selected', 'export_to_csv']
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related(
            'user', 'processed_by'
        ).prefetch_related('user__withdrawals')
    
    def id_short(self, obj):
        """Display shortened ID."""
        return str(obj.id)[:8] + '...'
    id_short.short_description = 'ID'
    
    def user_email(self, obj):
        """Display user email with link to user admin."""
        url = reverse('admin:users_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def amount_display(self, obj):
        """Display amount with currency symbol."""
        symbol = '₹' if obj.currency == 'INR' else '$'
        return f"{symbol}{obj.amount}"
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def fee_display(self, obj):
        """Display fee with currency symbol."""
        symbol = '₹' if obj.currency == 'INR' else '$'
        return f"{symbol}{obj.fee}"
    fee_display.short_description = 'Fee'
    fee_display.admin_order_field = 'fee'
    
    def total_amount_display(self, obj):
        """Display total amount with currency symbol."""
        symbol = '₹' if obj.currency == 'INR' else '$'
        return f"{symbol}{obj.total_amount}"
    total_amount_display.short_description = 'Total Amount'
    
    def net_amount_display(self, obj):
        """Display net amount with currency symbol."""
        symbol = '₹' if obj.currency == 'INR' else '$'
        return f"{symbol}{obj.net_amount}"
    net_amount_display.short_description = 'Net Amount'
    
    def status_display(self, obj):
        """Display status with color coding."""
        colors = {
            'PENDING': '#ffc107',      # Yellow
            'APPROVED': '#28a745',     # Green
            'REJECTED': '#dc3545',     # Red
            'PROCESSING': '#17a2b8',   # Blue
            'COMPLETED': '#20c997',    # Teal
            'CANCELLED': '#6c757d',    # Gray
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def payout_details_formatted(self, obj):
        """Display formatted payout details."""
        try:
            details = json.loads(obj.payout_details) if isinstance(obj.payout_details, str) else obj.payout_details
            formatted = json.dumps(details, indent=2)
            return format_html('<pre style="font-size: 12px;">{}</pre>', formatted)
        except (json.JSONDecodeError, TypeError):
            return obj.payout_details
    payout_details_formatted.short_description = 'Payout Details (Formatted)'
    
    def approve_selected(self, request, queryset):
        """Bulk approve selected withdrawals."""
        approved_count = 0
        for withdrawal in queryset.filter(status='PENDING'):
            success, message = withdrawal.approve(request.user, "Bulk approved via admin")
            if success:
                approved_count += 1
        
        self.message_user(
            request,
            f"{approved_count} withdrawal(s) were successfully approved."
        )
    approve_selected.short_description = "Approve selected withdrawals"
    
    def reject_selected(self, request, queryset):
        """Bulk reject selected withdrawals."""
        rejected_count = 0
        for withdrawal in queryset.filter(status='PENDING'):
            success, message = withdrawal.reject(request.user, "Bulk rejected via admin")
            if success:
                rejected_count += 1
        
        self.message_user(
            request,
            f"{rejected_count} withdrawal(s) were successfully rejected."
        )
    reject_selected.short_description = "Reject selected withdrawals"
    
    def export_to_csv(self, request, queryset):
        """Export selected withdrawals to CSV."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="withdrawals_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'User Email', 'Currency', 'Amount', 'Fee', 'Total Amount',
            'Payout Method', 'Status', 'TX Hash', 'Created At', 'Processed At',
            'Admin Notes', 'Rejection Reason'
        ])
        
        for withdrawal in queryset:
            writer.writerow([
                str(withdrawal.id),
                withdrawal.user.email,
                withdrawal.currency,
                str(withdrawal.amount),
                str(withdrawal.fee),
                str(withdrawal.total_amount),
                withdrawal.get_payout_method_display(),
                withdrawal.get_status_display(),
                withdrawal.tx_hash or '',
                withdrawal.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                withdrawal.processed_at.strftime('%Y-%m-%d %H:%M:%S') if withdrawal.processed_at else '',
                withdrawal.admin_notes or '',
                withdrawal.rejection_reason or ''
            ])
        
        return response
    export_to_csv.short_description = "Export selected withdrawals to CSV"
    
    def has_delete_permission(self, request, obj=None):
        """Restrict deletion of withdrawals."""
        # Only allow deletion for cancelled or rejected withdrawals
        if obj and obj.status in ['CANCELLED', 'REJECTED']:
            return super().has_delete_permission(request, obj)
        return False
    
    def save_model(self, request, obj, form, change):
        """Override save to handle status changes."""
        if change:  # If updating existing object
            original = Withdrawal.objects.get(pk=obj.pk)
            
            # If status changed to APPROVED
            if original.status != 'APPROVED' and obj.status == 'APPROVED':
                obj.processed_by = request.user
                obj.processed_at = timezone.now()
            
            # If status changed to REJECTED
            elif original.status != 'REJECTED' and obj.status == 'REJECTED':
                obj.processed_by = request.user
                obj.processed_at = timezone.now()
                # Trigger refund
                obj._refund_to_wallet()
            
            # If status changed to COMPLETED
            elif original.status != 'COMPLETED' and obj.status == 'COMPLETED':
                if not obj.processed_at:
                    obj.processed_at = timezone.now()
        
        super().save_model(request, obj, form, change)
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form based on user permissions and object state."""
        form = super().get_form(request, obj, **kwargs)
        
        # If editing existing withdrawal
        if obj:
            # Make certain fields readonly based on status
            if obj.status in ['COMPLETED', 'CANCELLED']:
                form.base_fields['status'].disabled = True
                form.base_fields['amount'].disabled = True
                form.base_fields['currency'].disabled = True
                form.base_fields['payout_method'].disabled = True
                form.base_fields['payout_details'].disabled = True
        
        return form
    


@admin.register(WithdrawalSettings)
class WithdrawalSettingsAdmin(admin.ModelAdmin):
    list_display = ('auto_approve_usdt_limit', 'auto_approve_inr_limit', 'updated_at')
