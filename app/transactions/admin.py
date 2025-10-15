from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user_link', 'type', 'currency', 'amount', 'status', 
        'reference_id', 'created_at', 'formatted_amount_display'
    ]
    list_filter = [
        'type', 'currency', 'status', 'created_at',
        ('user', admin.RelatedOnlyFieldListFilter)
    ]
    search_fields = [
        'user__username', 'user__email', 'user__first_name', 
        'user__last_name', 'reference_id'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at', 'formatted_amount_display']
    list_per_page = 50
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'type', 'currency', 'amount', 'status')
        }),
        ('Reference & Metadata', {
            'fields': ('reference_id', 'meta_data'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def formatted_amount_display(self, obj):
        """Display formatted amount with currency symbol."""
        try:
            amount = float(obj.amount)
            if obj.currency == 'INR':
                return format_html('<span style="color: #28a745;">₹{:.2f}</span>', amount)
            elif obj.currency == 'USDT':
                return format_html('<span style="color: #007bff;">${:.6f}</span>', amount)
            return str(amount)
        except (ValueError, TypeError):
            return str(obj.amount)
    formatted_amount_display.short_description = 'Amount'
    formatted_amount_display.admin_order_field = 'amount'
    
    def user_link(self, obj):
        """Create a link to the user admin page."""
        if obj.user:
            try:
                url = reverse('admin:users_user_change', args=[obj.user.id])
                return format_html('<a href="{}">{}</a>', url, obj.user.username)
            except:
                return obj.user.username
        return '-'
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'
    
    def get_list_display(self, request):
        """Customize list display based on user permissions."""
        return super().get_list_display(request)
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly for non-superusers."""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            readonly_fields.extend(['type', 'currency', 'amount', 'user'])
        return readonly_fields
    
    def has_add_permission(self, request):
        """Only superusers can add transactions."""
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete transactions."""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Staff users can change transaction status and metadata."""
        return request.user.is_staff
    
    def get_actions(self, request):
        """Customize available actions."""
        actions = super().get_actions(request)
        if request.user.is_superuser:
            # Add custom actions for superusers
            actions['export_selected_csv'] = (self.export_selected_csv, 'export_selected_csv', 'Export selected transactions to CSV')
        return actions
    
    def export_selected_csv(self, request, queryset):
        """Export selected transactions to CSV."""
        from django.http import HttpResponse
        import csv
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="selected_transactions.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Transaction ID', 'Username', 'Email', 'Type', 'Currency', 
            'Amount', 'Status', 'Reference ID', 'Created At', 'Updated At'
        ])
        
        for transaction in queryset:
            writer.writerow([
                str(transaction.id),
                transaction.user.username,
                transaction.user.email,
                transaction.get_type_display(),
                transaction.get_currency_display(),
                str(transaction.amount),
                transaction.get_status_display(),
                transaction.reference_id or '',
                transaction.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                transaction.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_selected_csv.short_description = "Export selected transactions to CSV"
    
    def changelist_view(self, request, extra_context=None):
        """Add summary statistics to the changelist view."""
        extra_context = extra_context or {}
        
        # Get basic statistics
        queryset = self.get_queryset(request)
        total_transactions = queryset.count()
        total_volume = queryset.aggregate(total=Sum('amount'))['total'] or 0
        
        # Get statistics by currency
        inr_stats = queryset.filter(currency='INR').aggregate(
            count=Count('id'),
            total=Sum('amount')
        )
        usdt_stats = queryset.filter(currency='USDT').aggregate(
            count=Count('id'),
            total=Sum('amount')
        )
        
        # Get statistics by type
        type_stats = {}
        for transaction_type, _ in Transaction.TRANSACTION_TYPE_CHOICES:
            type_count = queryset.filter(type=transaction_type).count()
            if type_count > 0:
                type_stats[transaction_type] = type_count
        
        # Get recent activity (last 7 days)
        week_ago = timezone.now() - timedelta(days=7)
        recent_transactions = queryset.filter(created_at__gte=week_ago).count()
        
        extra_context.update({
            'total_transactions': total_transactions,
            'total_volume': total_volume,
            'inr_stats': inr_stats,
            'usdt_stats': usdt_stats,
            'type_stats': type_stats,
            'recent_transactions': recent_transactions,
        })
        
        return super().changelist_view(request, extra_context)
    
    class Media:
        css = {
            'all': ('admin/css/transaction_admin.css',)
        }
        js = ('admin/js/transaction_admin.js',)


class TransactionTypeFilter(admin.SimpleListFilter):
    """Custom filter for transaction types."""
    title = 'Transaction Type'
    parameter_name = 'transaction_type'
    
    def lookups(self, request, model_admin):
        return Transaction.TRANSACTION_TYPE_CHOICES
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(type=self.value())


class TransactionStatusFilter(admin.SimpleListFilter):
    """Custom filter for transaction status."""
    title = 'Transaction Status'
    parameter_name = 'transaction_status'
    
    def lookups(self, request, model_admin):
        return Transaction.STATUS_CHOICES
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())


class TransactionCurrencyFilter(admin.SimpleListFilter):
    """Custom filter for transaction currency."""
    title = 'Currency'
    parameter_name = 'transaction_currency'
    
    def lookups(self, request, model_admin):
        return Transaction.CURRENCY_CHOICES
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(currency=self.value())


# Add custom filters to the admin
TransactionAdmin.list_filter = [
    TransactionTypeFilter,
    TransactionStatusFilter,
    TransactionCurrencyFilter,
    'created_at',
    ('user', admin.RelatedOnlyFieldListFilter)
]
