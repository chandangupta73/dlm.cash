from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from .models import InvestmentPlan, Investment, BreakdownRequest


@admin.register(InvestmentPlan)
class InvestmentPlanAdmin(admin.ModelAdmin):
    """Admin interface for InvestmentPlan model."""
    
    list_display = [
        'name', 'roi_rate', 'frequency', 'fixed_amount',
        'duration_days', 'breakdown_window_days', 'status', 'is_active',
        'created_at'
    ]
    list_filter = [
        'status', 'is_active', 'frequency', 'roi_rate', 'created_at'
    ]
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'status', 'is_active')
        }),
        ('Investment Parameters', {
            'fields': (
                'fixed_amount', 'roi_rate', 'frequency',
                'duration_days', 'breakdown_window_days'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with related data."""
        return super().get_queryset(request).select_related()
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of plans with active investments."""
        if obj and obj.investments.filter(status='active').exists():
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    """Admin interface for Investment model."""
    
    list_display = [
        'id', 'user', 'plan', 'amount', 'currency', 'payment_method', 'status',
        'roi_accrued', 'start_date', 'end_date', 'is_active', 'approved_by', 'approved_at'
    ]
    list_filter = [
        'status', 'is_active', 'currency', 'payment_method', 'plan__frequency',
        'start_date', 'created_at'
    ]
    search_fields = [
        'user__username', 'user__email', 'plan__name'
    ]
    readonly_fields = [
        'id', 'start_date', 'end_date', 'roi_accrued',
        'last_roi_credit', 'next_roi_date', 'created_at', 'updated_at',
        'approved_by', 'approved_at'
    ]
    list_editable = ['status', 'payment_method']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Investment Details', {
            'fields': (
                'id', 'user', 'plan', 'amount', 'currency', 'payment_method', 'status', 'is_active'
            )
        }),
        ('Admin Approval', {
            'fields': (
                'approved_by', 'approved_at'
            ),
            'classes': ('collapse',)
        }),
        ('ROI Information', {
            'fields': (
                'roi_accrued', 'last_roi_credit', 'next_roi_date'
            )
        }),
        ('Timeline', {
            'fields': ('start_date', 'end_date')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with related data."""
        return super().get_queryset(request).select_related('user', 'plan')
    
    def user_link(self, obj):
        """Create a link to user admin."""
        if obj.user:
            url = reverse('admin:users_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return '-'
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'
    
    def plan_link(self, obj):
        """Create a link to plan admin."""
        if obj.plan:
            url = reverse('admin:investment_investmentplan_change', args=[obj.plan.id])
            return format_html('<a href="{}">{}</a>', url, obj.plan.name)
        return '-'
    plan_link.short_description = 'Plan'
    plan_link.admin_order_field = 'plan__name'
    
    def can_breakdown(self, obj):
        """Show if investment can be broken down."""
        return obj.can_breakdown()
    can_breakdown.boolean = True
    can_breakdown.short_description = 'Can Breakdown'
    
    def breakdown_amount(self, obj):
        """Show breakdown amount if applicable."""
        if obj.can_breakdown():
            return f"{obj.get_breakdown_amount()} {obj.currency.upper()}"
        return '-'
    breakdown_amount.short_description = 'Breakdown Amount'
    
    actions = ['approve_investments', 'reject_investments']
    
    def approve_investments(self, request, queryset):
        """Approve selected pending investments and deduct wallet balance."""
        from django.db import transaction
        from app.wallet.models import WalletTransaction
        from decimal import Decimal
        
        approved_count = 0
        failed_count = 0
        
        for investment in queryset.filter(status='pending_admin_approval'):
            try:
                with transaction.atomic():
                    user = investment.user
                    amount = investment.amount
                    currency = investment.currency
                    
                    # Check if user has sufficient balance
                    if currency.upper() == 'INR':
                        wallet = user.inr_wallet
                        if wallet.balance < amount:
                            raise ValueError(f"Insufficient INR balance. Required: {amount}, Available: {wallet.balance}")
                    else:  # USDT
                        wallet = user.usdt_wallet
                        if wallet.balance < amount:
                            raise ValueError(f"Insufficient USDT balance. Required: {amount}, Available: {wallet.balance}")
                    
                    # Deduct from wallet
                    balance_before = wallet.balance
                    success = wallet.deduct_balance(amount)
                    if not success:
                        raise ValueError("Failed to deduct balance from wallet")
                    
                    wallet.save()
                    
                    # Create wallet transaction record
                    WalletTransaction.objects.create(
                        user=user,
                        transaction_type='investment_purchase',
                        amount=Decimal(str(amount)).quantize(Decimal('0.000001')),
                        wallet_type=currency.lower(),
                        status='completed',
                        reference_id=str(investment.id),
                        description=f'Investment in {investment.plan.name} (Admin Approved)',
                        balance_before=balance_before,
                        balance_after=wallet.balance
                    )
                    
                    # Update investment status and approval info
                    investment.status = 'active'
                    investment.approved_by = request.user
                    investment.approved_at = timezone.now()
                    investment.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
                    
                    approved_count += 1
                    
                    # Send notification to user (you can implement this)
                    self.message_user(
                        request,
                        f"Investment {investment.id} approved for user {investment.user.username}. "
                        f"Wallet deducted: {amount} {currency.upper()}"
                    )
                    
            except Exception as e:
                failed_count += 1
                self.message_user(
                    request,
                    f"Failed to approve investment {investment.id}: {str(e)}",
                    level='ERROR'
                )
        
        if failed_count > 0:
            self.message_user(
                request,
                f"Successfully approved {approved_count} investments. {failed_count} failed.",
                level='WARNING'
            )
        else:
            self.message_user(
                request,
                f"Successfully approved {approved_count} investments."
            )
    approve_investments.short_description = "Approve selected pending investments"
    
    def reject_investments(self, request, queryset):
        """Reject selected pending investments."""
        rejected_count = 0
        for investment in queryset.filter(status='pending_admin_approval'):
            try:
                investment.status = 'cancelled'
                investment.save(update_fields=['status', 'updated_at'])
                rejected_count += 1
                
                # Send notification to user (you can implement this)
                self.message_user(
                    request,
                    f"Investment {investment.id} rejected for user {investment.user.username}"
                )
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to reject investment {investment.id}: {str(e)}",
                    level='ERROR'
                )
        
        self.message_user(
            request,
            f"Successfully rejected {rejected_count} investments."
        )
    reject_investments.short_description = "Reject selected pending investments"
    
    def save_model(self, request, obj, form, change):
        """Override save_model to handle status changes and wallet deductions."""
        if change and 'status' in form.changed_data:
            # Get the old status from the database
            try:
                old_investment = Investment.objects.get(id=obj.id)
                old_status = old_investment.status
            except Investment.DoesNotExist:
                old_status = None
            
            # If status is being changed to 'active' from 'pending_admin_approval'
            if obj.status == 'active' and old_status == 'pending_admin_approval':
                try:
                    from django.db import transaction
                    from app.wallet.models import WalletTransaction
                    from decimal import Decimal
                    
                    with transaction.atomic():
                        user = obj.user
                        amount = obj.amount
                        currency = obj.currency
                        
                        # Check if user has sufficient balance
                        if currency.upper() == 'INR':
                            wallet = user.inr_wallet
                            if wallet.balance < amount:
                                raise ValueError(f"Insufficient INR balance. Required: {amount}, Available: {wallet.balance}")
                        else:  # USDT
                            wallet = user.usdt_wallet
                            if wallet.balance < amount:
                                raise ValueError(f"Insufficient USDT balance. Required: {amount}, Available: {wallet.balance}")
                        
                        # Deduct from wallet
                        balance_before = wallet.balance
                        success = wallet.deduct_balance(amount)
                        if not success:
                            raise ValueError("Failed to deduct balance from wallet")
                        
                        wallet.save()
                        
                        # Create wallet transaction record
                        WalletTransaction.objects.create(
                            user=user,
                            transaction_type='investment_purchase',
                            amount=Decimal(str(amount)).quantize(Decimal('0.000001')),
                            wallet_type=currency.lower(),
                            status='completed',
                            reference_id=str(obj.id),
                            description=f'Investment in {obj.plan.name} (Admin Approved via Status Change)',
                            balance_before=balance_before,
                            balance_after=wallet.balance
                        )
                        
                        # Set approval info
                        obj.approved_by = request.user
                        obj.approved_at = timezone.now()
                        
                        # Show success message
                        self.message_user(
                            request,
                            f"Investment {obj.id} approved and wallet deducted: {amount} {currency.upper()}. "
                            f"User balance: {balance_before} → {wallet.balance}",
                            level='SUCCESS'
                        )
                        
                except Exception as e:
                    # Revert status change and show error
                    obj.status = 'pending_admin_approval'
                    self.message_user(
                        request,
                        f"Failed to approve investment {obj.id}: {str(e)}. Status reverted to pending.",
                        level='ERROR'
                    )
                    return  # Don't save the model
        
        # Call the parent save_model method
        super().save_model(request, obj, form, change)


@admin.register(BreakdownRequest)
class BreakdownRequestAdmin(admin.ModelAdmin):
    """Admin interface for BreakdownRequest model."""
    
    list_display = [
        'id', 'user', 'investment_plan', 'requested_amount', 'final_amount',
        'currency', 'status', 'created_at', 'processed_at'
    ]
    list_filter = [
        'status', 'created_at', 'processed_at', 'investment__currency'
    ]
    search_fields = [
        'user__username', 'user__email', 'investment__plan__name'
    ]
    readonly_fields = [
        'id', 'user', 'investment', 'requested_amount', 'final_amount',
        'created_at', 'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Request Details', {
            'fields': (
                'id', 'user', 'investment', 'requested_amount', 'final_amount'
            )
        }),
        ('Status & Processing', {
            'fields': (
                'status', 'admin_notes', 'processed_by', 'processed_at'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with related data."""
        return super().get_queryset(request).select_related(
            'user', 'investment', 'investment__plan', 'processed_by'
        )
    
    def user_link(self, obj):
        """Create a link to user admin."""
        if obj.user:
            url = reverse('admin:users_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return '-'
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'
    
    def investment_plan(self, obj):
        """Show investment plan name."""
        if obj.investment and obj.investment.plan:
            return obj.investment.plan.name
        return '-'
    investment_plan.short_description = 'Investment Plan'
    
    def currency(self, obj):
        """Show investment currency."""
        if obj.investment:
            return obj.investment.currency.upper()
        return '-'
    currency.short_description = 'Currency'
    
    def investment_link(self, obj):
        """Create a link to investment admin."""
        if obj.investment:
            url = reverse('admin:investment_investment_change', args=[obj.investment.id])
            return format_html('<a href="{}">View Investment</a>', url)
        return '-'
    investment_link.short_description = 'Investment'
    
    def get_readonly_fields(self, request, obj=None):
        """Make fields readonly based on status."""
        if obj and obj.status != 'pending':
            return list(self.readonly_fields) + ['status']
        return self.readonly_fields
    
    def has_add_permission(self, request):
        """Prevent manual creation of breakdown requests."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of breakdown requests."""
        return False
    
    actions = ['approve_breakdowns', 'reject_breakdowns']
    
    def approve_breakdowns(self, request, queryset):
        """Approve selected breakdown requests."""
        approved_count = 0
        for breakdown_request in queryset.filter(status='pending'):
            try:
                breakdown_request.approve(request.user)
                approved_count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to approve breakdown {breakdown_request.id}: {str(e)}",
                    level='ERROR'
                )
        
        self.message_user(
            request,
            f"Successfully approved {approved_count} breakdown requests."
        )
    approve_breakdowns.short_description = "Approve selected breakdown requests"
    
    def reject_breakdowns(self, request, queryset):
        """Reject selected breakdown requests."""
        rejected_count = 0
        for breakdown_request in queryset.filter(status='pending'):
            try:
                breakdown_request.reject(request.user, "Bulk rejection")
                rejected_count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to reject breakdown {breakdown_request.id}: {str(e)}",
                    level='ERROR'
                )
        
        self.message_user(
            request,
            f"Successfully rejected {rejected_count} breakdown requests."
        )
    reject_breakdowns.short_description = "Reject selected breakdown requests"
