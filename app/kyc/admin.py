from django.contrib import admin
from .models import KYCDocument, VideoKYC, OfflineKYCRequest, KYCVerificationLog


@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ('user', 'document_type', 'document_number', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'document_type', 'created_at')
    search_fields = ('user__email', 'user__username', 'document_number')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Document Information', {
            'fields': ('user', 'document_type', 'document_number')
        }),
        ('Document Files', {
            'fields': ('document_file', 'document_front', 'document_back')
        }),
        ('Verification Status', {
            'fields': ('status', 'rejection_reason', 'verified_by', 'verified_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(VideoKYC)
class VideoKYCAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_id', 'status', 'duration', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__email', 'user__username', 'session_id')
    ordering = ('-created_at',)
    readonly_fields = ('session_id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Video Information', {
            'fields': ('user', 'session_id', 'video_file', 'duration')
        }),
        ('Verification Status', {
            'fields': ('status', 'rejection_reason', 'verified_by', 'verified_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(OfflineKYCRequest)
class OfflineKYCRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'request_type', 'status', 'assigned_to', 'created_at', 'updated_at')
    list_filter = ('status', 'request_type', 'created_at')
    search_fields = ('user__email', 'user__username', 'description')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Request Information', {
            'fields': ('user', 'request_type', 'description')
        }),
        ('Documents', {
            'fields': ('documents',)
        }),
        ('Status Management', {
            'fields': ('status', 'assigned_to', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ('documents',)


@admin.register(KYCVerificationLog)
class KYCVerificationLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'document_type', 'performed_by', 'created_at')
    list_filter = ('action', 'document_type', 'created_at')
    search_fields = ('user__email', 'user__username', 'details')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Log Information', {
            'fields': ('user', 'action', 'document_type', 'performed_by', 'details')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    ) 