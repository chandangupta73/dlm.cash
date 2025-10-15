from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import KYCDocument, VideoKYC, OfflineKYCRequest, User


@shared_task
def send_kyc_reminders():
    """Send reminders to users who haven't completed KYC"""
    users_without_kyc = User.objects.filter(
        is_kyc_verified=False,
        created_at__lt=timezone.now() - timezone.timedelta(days=7)
    )
    
    for user in users_without_kyc:
        subject = 'Complete Your KYC Verification'
        message = f'''
        Dear {user.first_name or user.email},
        
        We noticed that you haven't completed your KYC verification yet.
        Please complete your verification to access all platform features.
        
        Best regards,
        KYC Team
        '''
        
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Failed to send reminder to {user.email}: {str(e)}")
    
    return f"Sent reminders to {users_without_kyc.count()} users"


@shared_task
def process_document_verification(document_id):
    """Process document verification (placeholder for AI/ML integration)"""
    try:
        document = KYCDocument.objects.get(id=document_id)
        
        # TODO: Integrate with AI/ML service for document verification
        # For now, just simulate processing
        import time
        time.sleep(2)  # Simulate processing time
        
        # Randomly approve or reject for demo purposes
        import random
        if random.choice([True, False]):
            document.status = 'APPROVED'
            document.verified_at = timezone.now()
        else:
            document.status = 'REJECTED'
            document.rejection_reason = 'Document verification failed'
        
        document.save()
        
        return f"Document {document_id} processed"
    except KYCDocument.DoesNotExist:
        return f"Document {document_id} not found"
    except Exception as e:
        return f"Failed to process document {document_id}: {str(e)}"


@shared_task
def process_video_kyc_verification(video_id):
    """Process video KYC verification (placeholder for AI/ML integration)"""
    try:
        video_kyc = VideoKYC.objects.get(id=video_id)
        
        # TODO: Integrate with AI/ML service for video verification
        # For now, just simulate processing
        import time
        time.sleep(5)  # Simulate processing time
        
        # Randomly approve or reject for demo purposes
        import random
        if random.choice([True, False]):
            video_kyc.status = 'APPROVED'
            video_kyc.verified_at = timezone.now()
        else:
            video_kyc.status = 'REJECTED'
            video_kyc.rejection_reason = 'Video verification failed'
        
        video_kyc.save()
        
        return f"Video KYC {video_id} processed"
    except VideoKYC.DoesNotExist:
        return f"Video KYC {video_id} not found"
    except Exception as e:
        return f"Failed to process video KYC {video_id}: {str(e)}"


@shared_task
def send_document_approval_email(document_id):
    """Send email when document is approved"""
    try:
        document = KYCDocument.objects.get(id=document_id)
        user = document.user
        
        subject = 'Document Verification Approved'
        message = f'''
        Dear {user.first_name or user.email},
        
        Your {document.document_type} document has been approved!
        
        Document Details:
        - Type: {document.document_type}
        - Number: {document.document_number or 'N/A'}
        - Approved on: {document.verified_at}
        
        Best regards,
        KYC Team
        '''
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return f"Approval email sent to {user.email}"
    except KYCDocument.DoesNotExist:
        return f"Document {document_id} not found"
    except Exception as e:
        return f"Failed to send approval email: {str(e)}"


@shared_task
def send_document_rejection_email(document_id):
    """Send email when document is rejected"""
    try:
        document = KYCDocument.objects.get(id=document_id)
        user = document.user
        
        subject = 'Document Verification Rejected'
        message = f'''
        Dear {user.first_name or user.email},
        
        Your {document.document_type} document has been rejected.
        
        Document Details:
        - Type: {document.document_type}
        - Number: {document.document_number or 'N/A'}
        - Rejection Reason: {document.rejection_reason}
        
        Please upload a new document or contact support for assistance.
        
        Best regards,
        KYC Team
        '''
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return f"Rejection email sent to {user.email}"
    except KYCDocument.DoesNotExist:
        return f"Document {document_id} not found"
    except Exception as e:
        return f"Failed to send rejection email: {str(e)}"


@shared_task
def cleanup_old_documents():
    """Clean up old rejected documents"""
    cutoff_date = timezone.now() - timezone.timedelta(days=90)
    old_rejected_documents = KYCDocument.objects.filter(
        status='REJECTED',
        created_at__lt=cutoff_date
    )
    count = old_rejected_documents.count()
    old_rejected_documents.delete()
    return f"Cleaned up {count} old rejected documents"


@shared_task
def generate_kyc_report():
    """Generate KYC verification report"""
    total_users = User.objects.count()
    verified_users = User.objects.filter(is_kyc_verified=True).count()
    pending_documents = KYCDocument.objects.filter(status='PENDING').count()
    approved_documents = KYCDocument.objects.filter(status='APPROVED').count()
    rejected_documents = KYCDocument.objects.filter(status='REJECTED').count()
    
    report = {
        'total_users': total_users,
        'verified_users': verified_users,
        'verification_rate': round((verified_users / total_users * 100), 2) if total_users > 0 else 0,
        'pending_documents': pending_documents,
        'approved_documents': approved_documents,
        'rejected_documents': rejected_documents,
        'generated_at': timezone.now().isoformat()
    }
    
    # TODO: Save report to database or send to admin
    print(f"KYC Report: {report}")
    return report 