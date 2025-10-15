from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta

from .models import Announcement, AdminActionLog, ContactMessage


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    """Admin interface for Announcement model."""
    
    list_display = [
        'title', 'target_group', 'status', 'priority', 'is_pinned', 
        'display_from', 'display_until', 'created_by', 'view_count', 'created_at'
    ]
    list_filter = [
        'status', 'target_group', 'is_pinned', 'priority',
        'display_from', 'display_until', 'created_at'
    ]
    search_fields = ['title', 'message', 'created_by__email', 'created_by__username']
    readonly_fields = ['id', 'created_at', 'updated_at', 'view_count']
    list_per_page = 20
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'id', 'title', 'message', 'target_group', 'status', 'priority'
            )
        }),
        ('Display Settings', {
            'fields': (
                'display_from', 'display_until', 'is_pinned'
            )
        }),
        ('Creator Information', {
            'fields': ('created_by', 'view_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by')
    
    def created_by_link(self, obj):
        """Display creator as a link."""
        if obj.created_by:
            url = reverse('admin:users_user_change', args=[obj.created_by.id])
            return format_html('<a href="{}">{}</a>', url, obj.created_by.email)
        return '-'
    created_by_link.short_description = 'Created By'
    created_by_link.admin_order_field = 'created_by__email'
    
    def is_active_display(self, obj):
        """Display whether announcement is currently active."""
        if obj.is_active():
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Active</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ Inactive</span>'
            )
    is_active_display.short_description = 'Active Status'
    
    def get_list_display(self, request):
        """Customize list display based on user permissions."""
        list_display = list(super().get_list_display(request))
        if request.user.is_superuser:
            list_display.insert(-1, 'is_active_display')
        return list_display
    
    def save_model(self, request, obj, form, change):
        """Set created_by field when creating new announcement."""
        if not change:  # New announcement
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['activate_announcements', 'deactivate_announcements', 'pin_announcements', 'unpin_announcements']
    
    def activate_announcements(self, request, queryset):
        """Activate selected announcements."""
        updated = queryset.update(status='ACTIVE')
        self.message_user(
            request, 
            f'Successfully activated {updated} announcement(s).'
        )
    activate_announcements.short_description = "Activate selected announcements"
    
    def deactivate_announcements(self, request, queryset):
        """Deactivate selected announcements."""
        updated = queryset.update(status='INACTIVE')
        self.message_user(
            request, 
            f'Successfully deactivated {updated} announcement(s).'
        )
    deactivate_announcements.short_description = "Deactivate selected announcements"
    
    def pin_announcements(self, request, queryset):
        """Pin selected announcements."""
        updated = queryset.update(is_pinned=True)
        self.message_user(
            request, 
            f'Successfully pinned {updated} announcement(s).'
        )
    pin_announcements.short_description = "Pin selected announcements"
    
    def unpin_announcements(self, request, queryset):
        """Unpin selected announcements."""
        updated = queryset.update(is_pinned=False)
        self.message_user(
            request, 
            f'Successfully unpinned {updated} announcement(s).'
        )
    unpin_announcements.short_description = "Unpin selected announcements"


@admin.register(AdminActionLog)
class AdminActionLogAdmin(admin.ModelAdmin):
    """Admin interface for AdminActionLog model."""
    
    list_display = [
        'action_type', 'admin_user_link', 'target_user_link', 'target_model',
        'action_description', 'ip_address', 'created_at'
    ]
    list_filter = [
        'action_type', 'admin_user', 'target_model', 'created_at'
    ]
    search_fields = [
        'action_description', 'admin_user__email', 'admin_user__username',
        'target_user__email', 'target_user__username', 'target_model'
    ]
    readonly_fields = [
        'id', 'admin_user', 'action_type', 'action_description', 'target_user',
        'target_model', 'target_id', 'ip_address', 'user_agent', 'metadata',
        'created_at', 'updated_at'
    ]
    list_per_page = 50
    
    fieldsets = (
        ('Action Information', {
            'fields': (
                'id', 'action_type', 'action_description', 'admin_user'
            )
        }),
        ('Target Information', {
            'fields': ('target_user', 'target_model', 'target_id')
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Additional Data', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('admin_user', 'target_user')
    
    def admin_user_link(self, obj):
        """Display admin user as a link."""
        if obj.admin_user:
            url = reverse('admin:users_user_change', args=[obj.admin_user.id])
            return format_html('<a href="{}">{}</a>', url, obj.admin_user.email)
        return '-'
    admin_user_link.short_description = 'Admin User'
    admin_user_link.admin_order_field = 'admin_user__email'
    
    def target_user_link(self, obj):
        """Display target user as a link."""
        if obj.target_user:
            url = reverse('admin:users_user_change', args=[obj.target_user.id])
            return format_html('<a href="{}">{}</a>', url, obj.target_user.email)
        return '-'
    target_user_link.short_description = 'Target User'
    target_user_link.admin_order_field = 'target_user__email'
    
    def has_add_permission(self, request):
        """Prevent manual creation of action logs."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of action logs."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete action logs."""
        return request.user.is_superuser
    
    def get_actions(self, request):
        """Remove bulk actions for action logs."""
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


class AdminDashboardAdmin(admin.ModelAdmin):
    """Admin interface for dashboard overview."""
    
    change_list_template = 'admin/admin_dashboard.html'
    
    def changelist_view(self, request, extra_context=None):
        """Override changelist view to show dashboard."""
        extra_context = extra_context or {}
        
        # Get summary statistics
        try:
            from .services import AdminDashboardService
            summary = AdminDashboardService.get_dashboard_summary()
            extra_context['dashboard_summary'] = summary
        except Exception as e:
            extra_context['dashboard_error'] = str(e)
        
        # Get recent admin actions
        recent_actions = AdminActionLog.objects.select_related('admin_user').order_by('-created_at')[:10]
        extra_context['recent_actions'] = recent_actions
        
        # Get pending items counts
        from app.kyc.models import KYCDocument
        from app.withdrawals.models import Withdrawal
        from app.investment.models import Investment
        
        extra_context['pending_kyc_count'] = KYCDocument.objects.filter(status='PENDING').count()
        extra_context['pending_withdrawals_count'] = Withdrawal.objects.filter(status='PENDING').count()
        extra_context['active_investments_count'] = Investment.objects.filter(status='active').count()
        
        return super().changelist_view(request, extra_context)


# Note: Custom admin dashboard view would need to be implemented via custom admin templates
# For now, the AdminDashboardAdmin class provides the foundation for a custom dashboard


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'is_resolved', 'created_at')
    list_filter = ('is_resolved', 'created_at')
    search_fields = ('name', 'email', 'subject')