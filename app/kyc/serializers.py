from rest_framework import serializers
from django.utils import timezone
from .models import KYCDocument, VideoKYC, OfflineKYCRequest, KYCVerificationLog


class KYCDocumentSerializer(serializers.ModelSerializer):
    """Serializer for KYC document upload and management"""
    
    class Meta:
        model = KYCDocument
        fields = [
            'id', 'document_type', 'document_number', 'document_file',
            'document_front', 'document_back', 'status', 'rejection_reason',
            'verified_by', 'verified_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'rejection_reason', 'verified_by', 
                           'verified_at', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        
        # Check if user already has this document type
        existing_doc = KYCDocument.objects.filter(
            user=validated_data['user'],
            document_type=validated_data['document_type']
        ).first()
        
        if existing_doc:
            # Update existing document instead of creating new one
            for field, value in validated_data.items():
                setattr(existing_doc, field, value)
            # Reset status to pending for re-verification
            existing_doc.status = 'PENDING'
            existing_doc.rejection_reason = ''
            existing_doc.verified_by = None
            existing_doc.verified_at = None
            existing_doc.save()
            return existing_doc
        
        return super().create(validated_data)


class KYCDocumentListSerializer(serializers.ModelSerializer):
    """Serializer for listing KYC documents"""
    
    class Meta:
        model = KYCDocument
        fields = [
            'id', 'document_type', 'document_number', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']


class KYCDocumentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating KYC document status (admin only)"""
    
    class Meta:
        model = KYCDocument
        fields = ['status', 'rejection_reason']
    
    def update(self, instance, validated_data):
        if 'status' in validated_data:
            instance.verified_by = self.context['request'].user
            instance.verified_at = timezone.now()
        return super().update(instance, validated_data)


class VideoKYCSerializer(serializers.ModelSerializer):
    """Serializer for video KYC upload"""
    
    class Meta:
        model = VideoKYC
        fields = [
            'id', 'video_file', 'session_id', 'status', 'rejection_reason',
            'verified_by', 'verified_at', 'duration', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'session_id', 'status', 'rejection_reason',
                           'verified_by', 'verified_at', 'duration', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        # Generate session ID
        import uuid
        validated_data['session_id'] = str(uuid.uuid4())
        return super().create(validated_data)


class VideoKYCListSerializer(serializers.ModelSerializer):
    """Serializer for listing video KYC sessions"""
    
    class Meta:
        model = VideoKYC
        fields = [
            'id', 'session_id', 'status', 'duration', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'session_id', 'status', 'duration', 'created_at', 'updated_at']


class VideoKYCUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating video KYC status (admin only)"""
    
    class Meta:
        model = VideoKYC
        fields = ['status', 'rejection_reason']
    
    def update(self, instance, validated_data):
        if 'status' in validated_data:
            instance.verified_by = self.context['request'].user
            instance.verified_at = timezone.now()
        return super().update(instance, validated_data)


class OfflineKYCRequestSerializer(serializers.ModelSerializer):
    """Serializer for offline KYC requests"""
    
    class Meta:
        model = OfflineKYCRequest
        fields = [
            'id', 'request_type', 'description', 'documents', 'status',
            'assigned_to', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'assigned_to', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class OfflineKYCRequestListSerializer(serializers.ModelSerializer):
    """Serializer for listing offline KYC requests"""
    
    class Meta:
        model = OfflineKYCRequest
        fields = [
            'id', 'request_type', 'description', 'status', 'assigned_to',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'assigned_to', 'created_at', 'updated_at']


class OfflineKYCRequestUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating offline KYC requests (admin only)"""
    
    class Meta:
        model = OfflineKYCRequest
        fields = ['status', 'assigned_to', 'notes']
    
    def update(self, instance, validated_data):
        if 'status' in validated_data:
            instance.updated_at = timezone.now()
        return super().update(instance, validated_data)


class KYCVerificationLogSerializer(serializers.ModelSerializer):
    """Serializer for KYC verification logs"""
    
    class Meta:
        model = KYCVerificationLog
        fields = [
            'id', 'action', 'document_type', 'performed_by', 'details', 'created_at'
        ]
        read_only_fields = ['id', 'performed_by', 'created_at']


class KYCStatusSerializer(serializers.Serializer):
    """Serializer for KYC status summary"""
    total_documents = serializers.IntegerField()
    approved_documents = serializers.IntegerField()
    pending_documents = serializers.IntegerField()
    rejected_documents = serializers.IntegerField()
    video_kyc_status = serializers.CharField()
    overall_kyc_status = serializers.CharField()
    is_kyc_verified = serializers.BooleanField()


class DocumentTypeSerializer(serializers.Serializer):
    """Serializer for document types"""
    value = serializers.CharField()
    label = serializers.CharField()


class KYCUploadResponseSerializer(serializers.Serializer):
    """Serializer for KYC upload response"""
    message = serializers.CharField()
    document_id = serializers.UUIDField()
    status = serializers.CharField() 