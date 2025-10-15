from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from django.utils import timezone

from .models import KYCDocument, VideoKYC, OfflineKYCRequest, KYCVerificationLog
from .serializers import (
    KYCDocumentSerializer, KYCDocumentListSerializer, KYCDocumentUpdateSerializer,
    VideoKYCSerializer, VideoKYCListSerializer, VideoKYCUpdateSerializer,
    OfflineKYCRequestSerializer, OfflineKYCRequestListSerializer, OfflineKYCRequestUpdateSerializer,
    KYCVerificationLogSerializer, KYCStatusSerializer, DocumentTypeSerializer,
    KYCUploadResponseSerializer
)


class KYCDocumentUploadView(APIView):
    """Upload KYC documents"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = KYCDocumentSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            document = serializer.save()
            
            # Create verification log
            KYCVerificationLog.objects.create(
                user=request.user,
                action='DOCUMENT_UPLOADED',
                document_type=document.document_type,
                performed_by=request.user,
                details=f'Document {document.document_type} uploaded'
            )
            
            return Response({
                'message': 'Document uploaded successfully',
                'document_id': document.id,
                'status': document.status
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class KYCDocumentListView(generics.ListAPIView):
    """List user's KYC documents"""
    serializer_class = KYCDocumentListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return KYCDocument.objects.none()
        return KYCDocument.objects.filter(user=self.request.user)


class KYCDocumentDetailView(generics.RetrieveAPIView):
    """Get specific KYC document details"""
    serializer_class = KYCDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return KYCDocument.objects.none()
        return KYCDocument.objects.filter(user=self.request.user)


class KYCDocumentUpdateView(generics.UpdateAPIView):
    """Update KYC document status (admin only)"""
    serializer_class = KYCDocumentUpdateSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = KYCDocument.objects.all()
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            old_status = instance.status
            document = serializer.save()
            
            # Create verification log
            action = 'DOCUMENT_APPROVED' if document.status == 'APPROVED' else 'DOCUMENT_REJECTED'
            KYCVerificationLog.objects.create(
                user=document.user,
                action=action,
                document_type=document.document_type,
                performed_by=request.user,
                details=f'Document {document.document_type} {document.status.lower()}'
            )
            
            return Response({
                'message': f'Document {document.status.lower()} successfully',
                'document': KYCDocumentSerializer(document).data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VideoKYCUploadView(APIView):
    """Upload video KYC"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = VideoKYCSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            video_kyc = serializer.save()
            
            # Create verification log
            KYCVerificationLog.objects.create(
                user=request.user,
                action='VIDEO_KYC_UPLOADED',
                performed_by=request.user,
                details=f'Video KYC uploaded with session {video_kyc.session_id}'
            )
            
            return Response({
                'message': 'Video KYC uploaded successfully',
                'session_id': video_kyc.session_id,
                'status': video_kyc.status
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VideoKYCListView(generics.ListAPIView):
    """List user's video KYC sessions"""
    serializer_class = VideoKYCListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return VideoKYC.objects.none()
        return VideoKYC.objects.filter(user=self.request.user)


class VideoKYCUpdateView(generics.UpdateAPIView):
    """Update video KYC status (admin only)"""
    serializer_class = VideoKYCUpdateSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = VideoKYC.objects.all()
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            old_status = instance.status
            video_kyc = serializer.save()
            
            # Create verification log
            action = 'VIDEO_KYC_APPROVED' if video_kyc.status == 'APPROVED' else 'VIDEO_KYC_REJECTED'
            KYCVerificationLog.objects.create(
                user=video_kyc.user,
                action=action,
                performed_by=request.user,
                details=f'Video KYC {video_kyc.status.lower()}'
            )
            
            return Response({
                'message': f'Video KYC {video_kyc.status.lower()} successfully',
                'video_kyc': VideoKYCSerializer(video_kyc).data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OfflineKYCRequestView(APIView):
    """Create offline KYC request"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = OfflineKYCRequestSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            offline_request = serializer.save()
            
            # Create verification log
            KYCVerificationLog.objects.create(
                user=request.user,
                action='OFFLINE_REQUEST_CREATED',
                performed_by=request.user,
                details=f'Offline KYC request created: {offline_request.request_type}'
            )
            
            return Response({
                'message': 'Offline KYC request created successfully',
                'request_id': offline_request.id,
                'status': offline_request.status
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OfflineKYCRequestListView(generics.ListAPIView):
    """List user's offline KYC requests"""
    serializer_class = OfflineKYCRequestListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return OfflineKYCRequest.objects.none()
        return OfflineKYCRequest.objects.filter(user=self.request.user)


class OfflineKYCRequestUpdateView(generics.UpdateAPIView):
    """Update offline KYC request (admin only)"""
    serializer_class = OfflineKYCRequestUpdateSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = OfflineKYCRequest.objects.all()
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            old_status = instance.status
            offline_request = serializer.save()
            
            # Create verification log if status changed
            if old_status != offline_request.status:
                action = 'OFFLINE_REQUEST_COMPLETED' if offline_request.status == 'COMPLETED' else 'OFFLINE_REQUEST_CREATED'
                KYCVerificationLog.objects.create(
                    user=offline_request.user,
                    action=action,
                    performed_by=request.user,
                    details=f'Offline KYC request {offline_request.status.lower()}'
                )
            
            return Response({
                'message': f'Offline KYC request {offline_request.status.lower()} successfully',
                'request': OfflineKYCRequestSerializer(offline_request).data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class KYCStatusView(APIView):
    """Get user's KYC status summary"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get document counts
        documents = KYCDocument.objects.filter(user=user)
        total_documents = documents.count()
        approved_documents = documents.filter(status='APPROVED').count()
        pending_documents = documents.filter(status='PENDING').count()
        rejected_documents = documents.filter(status='REJECTED').count()
        
        # Get video KYC status
        video_kyc = VideoKYC.objects.filter(user=user).order_by('-created_at').first()
        video_kyc_status = video_kyc.status if video_kyc else 'NOT_UPLOADED'
        
        # Overall KYC status
        overall_kyc_status = user.kyc_status
        is_kyc_verified = user.is_kyc_verified
        
        data = {
            'total_documents': total_documents,
            'approved_documents': approved_documents,
            'pending_documents': pending_documents,
            'rejected_documents': rejected_documents,
            'video_kyc_status': video_kyc_status,
            'overall_kyc_status': overall_kyc_status,
            'is_kyc_verified': is_kyc_verified,
        }
        
        serializer = KYCStatusSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DocumentTypesView(APIView):
    """Get available document types"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        document_types = [
            {'value': 'PAN', 'label': 'PAN Card'},
            {'value': 'AADHAAR', 'label': 'Aadhaar Card'},
            {'value': 'PASSPORT', 'label': 'Passport'},
            {'value': 'DRIVING_LICENSE', 'label': 'Driving License'},
            {'value': 'VOTER_ID', 'label': 'Voter ID'},
        ]
        serializer = DocumentTypeSerializer(document_types, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class KYCVerificationLogView(generics.ListAPIView):
    """Get user's KYC verification logs"""
    serializer_class = KYCVerificationLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return KYCVerificationLog.objects.none()
        return KYCVerificationLog.objects.filter(user=self.request.user)


# Admin views for managing all KYC data
class AdminKYCDocumentListView(generics.ListAPIView):
    """List all KYC documents (admin only)"""
    serializer_class = KYCDocumentSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = KYCDocument.objects.all()
    filterset_fields = ['status', 'document_type', 'user']
    search_fields = ['user__email', 'user__username', 'document_number']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']


class AdminVideoKYCListView(generics.ListAPIView):
    """List all video KYC sessions (admin only)"""
    serializer_class = VideoKYCSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = VideoKYC.objects.all()
    filterset_fields = ['status', 'user']
    search_fields = ['user__email', 'user__username', 'session_id']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']


class AdminOfflineKYCRequestListView(generics.ListAPIView):
    """List all offline KYC requests (admin only)"""
    serializer_class = OfflineKYCRequestSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = OfflineKYCRequest.objects.all()
    filterset_fields = ['status', 'request_type', 'user']
    search_fields = ['user__email', 'user__username', 'description']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']


@api_view(['GET'])
@permission_classes([permissions.IsAdminUser])
def admin_kyc_dashboard(request):
    """Admin dashboard with KYC statistics"""
    total_users = request.user.__class__.objects.count()
    kyc_verified_users = request.user.__class__.objects.filter(is_kyc_verified=True).count()
    pending_documents = KYCDocument.objects.filter(status='PENDING').count()
    pending_videos = VideoKYC.objects.filter(status='PENDING').count()
    pending_requests = OfflineKYCRequest.objects.filter(status='PENDING').count()
    
    data = {
        'total_users': total_users,
        'kyc_verified_users': kyc_verified_users,
        'pending_documents': pending_documents,
        'pending_videos': pending_videos,
        'pending_requests': pending_requests,
        'verification_rate': round((kyc_verified_users / total_users * 100), 2) if total_users > 0 else 0
    }
    
    return Response(data, status=status.HTTP_200_OK) 