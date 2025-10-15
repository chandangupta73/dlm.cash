from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
import uuid
import os


def kyc_document_path(instance, filename):
    """Generate file path for KYC documents"""
    ext = filename.split('.')[-1]
    filename = f"{instance.user.id}/{instance.document_type}/{uuid.uuid4()}.{ext}"
    return os.path.join('kyc_documents', filename)


def video_kyc_path(instance, filename):
    """Generate file path for video KYC"""
    ext = filename.split('.')[-1]
    filename = f"{instance.user.id}/video_kyc/{uuid.uuid4()}.{ext}"
    return os.path.join('video_kyc', filename)


class KYCDocument(models.Model):
    """KYC Document model for storing uploaded documents"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kyc_documents')
    document_type = models.CharField(
        max_length=20,
        choices=[
            ('PAN', 'PAN Card'),
            ('AADHAAR', 'Aadhaar Card'),
            ('PASSPORT', 'Passport'),
            ('DRIVING_LICENSE', 'Driving License'),
            ('VOTER_ID', 'Voter ID'),
        ]
    )
    document_number = models.CharField(max_length=50, blank=True, null=True)
    document_file = models.FileField(
        upload_to=kyc_document_path,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])]
    )
    document_front = models.FileField(
        upload_to=kyc_document_path,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])],
        blank=True,
        null=True
    )
    document_back = models.FileField(
        upload_to=kyc_document_path,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])],
        blank=True,
        null=True
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('APPROVED', 'Approved'),
            ('REJECTED', 'Rejected'),
        ],
        default='PENDING'
    )
    rejection_reason = models.TextField(blank=True, null=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_documents'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'kyc_documents'
        verbose_name = 'KYC Document'
        verbose_name_plural = 'KYC Documents'
        unique_together = ['user', 'document_type']
    
    def __str__(self):
        return f"{self.user.email} - {self.document_type}"
    
    def save(self, *args, **kwargs):
        # Update user KYC status when document is approved/rejected
        if self.pk:
            try:
                old_instance = KYCDocument.objects.get(pk=self.pk)
                if old_instance.status != self.status:
                    if self.status == 'APPROVED':
                        self.user.kyc_status = 'APPROVED'
                        self.user.is_kyc_verified = True
                    elif self.status == 'REJECTED':
                        self.user.kyc_status = 'REJECTED'
                        self.user.is_kyc_verified = False
                    self.user.save()
            except KYCDocument.DoesNotExist:
                # This is a new instance, no need to check old status
                pass
        super().save(*args, **kwargs)


class VideoKYC(models.Model):
    """Video KYC model for storing video verification sessions"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='video_kycs')
    video_file = models.FileField(
        upload_to=video_kyc_path,
        validators=[FileExtensionValidator(allowed_extensions=['mp4', 'avi', 'mov', 'mkv'])]
    )
    session_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('APPROVED', 'Approved'),
            ('REJECTED', 'Rejected'),
        ],
        default='PENDING'
    )
    rejection_reason = models.TextField(blank=True, null=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_videos'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(help_text='Duration in seconds', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'video_kycs'
        verbose_name = 'Video KYC'
        verbose_name_plural = 'Video KYCs'
    
    def __str__(self):
        return f"{self.user.email} - {self.session_id}"


class OfflineKYCRequest(models.Model):
    """Offline KYC request model for manual document uploads"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offline_kyc_requests')
    request_type = models.CharField(
        max_length=20,
        choices=[
            ('DOCUMENT_UPLOAD', 'Document Upload'),
            ('VIDEO_KYC', 'Video KYC'),
            ('MANUAL_VERIFICATION', 'Manual Verification'),
        ]
    )
    description = models.TextField()
    documents = models.ManyToManyField(KYCDocument, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('IN_PROGRESS', 'In Progress'),
            ('COMPLETED', 'Completed'),
            ('REJECTED', 'Rejected'),
        ],
        default='PENDING'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_kyc_requests'
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'offline_kyc_requests'
        verbose_name = 'Offline KYC Request'
        verbose_name_plural = 'Offline KYC Requests'
    
    def __str__(self):
        return f"{self.user.email} - {self.request_type}"


class KYCVerificationLog(models.Model):
    """Log model for tracking KYC verification activities"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kyc_logs')
    action = models.CharField(
        max_length=50,
        choices=[
            ('DOCUMENT_UPLOADED', 'Document Uploaded'),
            ('DOCUMENT_APPROVED', 'Document Approved'),
            ('DOCUMENT_REJECTED', 'Document Rejected'),
            ('VIDEO_KYC_UPLOADED', 'Video KYC Uploaded'),
            ('VIDEO_KYC_APPROVED', 'Video KYC Approved'),
            ('VIDEO_KYC_REJECTED', 'Video KYC Rejected'),
            ('OFFLINE_REQUEST_CREATED', 'Offline Request Created'),
            ('OFFLINE_REQUEST_COMPLETED', 'Offline Request Completed'),
        ]
    )
    document_type = models.CharField(max_length=20, blank=True, null=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performed_kyc_actions'
    )
    details = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'kyc_verification_logs'
        verbose_name = 'KYC Verification Log'
        verbose_name_plural = 'KYC Verification Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.action} - {self.created_at}" 