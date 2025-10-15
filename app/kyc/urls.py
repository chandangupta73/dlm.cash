from django.urls import path
from .views import (
    KYCDocumentUploadView, KYCDocumentListView, KYCDocumentDetailView, KYCDocumentUpdateView,
    VideoKYCUploadView, VideoKYCListView, VideoKYCUpdateView,
    OfflineKYCRequestView, OfflineKYCRequestListView, OfflineKYCRequestUpdateView,
    KYCStatusView, DocumentTypesView, KYCVerificationLogView,
    AdminKYCDocumentListView, AdminVideoKYCListView, AdminOfflineKYCRequestListView,
    admin_kyc_dashboard
)

app_name = 'kyc'

urlpatterns = [
    # User KYC endpoints
    path('documents/upload/', KYCDocumentUploadView.as_view(), name='document_upload'),
    path('documents/', KYCDocumentListView.as_view(), name='document_list'),
    path('documents/<uuid:pk>/', KYCDocumentDetailView.as_view(), name='document_detail'),
    path('documents/<uuid:pk>/update/', KYCDocumentUpdateView.as_view(), name='document_update'),
    
    # Video KYC endpoints
    path('video/upload/', VideoKYCUploadView.as_view(), name='video_upload'),
    path('video/', VideoKYCListView.as_view(), name='video_list'),
    path('video/<uuid:pk>/update/', VideoKYCUpdateView.as_view(), name='video_update'),
    
    # Offline KYC endpoints
    path('offline/request/', OfflineKYCRequestView.as_view(), name='offline_request'),
    path('offline/requests/', OfflineKYCRequestListView.as_view(), name='offline_request_list'),
    path('offline/requests/<uuid:pk>/update/', OfflineKYCRequestUpdateView.as_view(), name='offline_request_update'),
    
    # Status and utility endpoints
    path('status/', KYCStatusView.as_view(), name='kyc_status'),
    path('document-types/', DocumentTypesView.as_view(), name='document_types'),
    path('logs/', KYCVerificationLogView.as_view(), name='verification_logs'),
    
    # Admin endpoints
    path('admin/documents/', AdminKYCDocumentListView.as_view(), name='admin_document_list'),
    path('admin/videos/', AdminVideoKYCListView.as_view(), name='admin_video_list'),
    path('admin/offline-requests/', AdminOfflineKYCRequestListView.as_view(), name='admin_offline_request_list'),
    path('admin/dashboard/', admin_kyc_dashboard, name='admin_dashboard'),
] 