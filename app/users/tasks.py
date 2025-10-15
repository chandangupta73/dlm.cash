from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import OTP, User


@shared_task
def cleanup_expired_otps():
    """Clean up expired OTPs"""
    expired_otps = OTP.objects.filter(
        expires_at__lt=timezone.now(),
        is_used=False
    )
    count = expired_otps.count()
    expired_otps.delete()
    return f"Cleaned up {count} expired OTPs"


@shared_task
def send_email_otp(user_id, otp_code):
    """Send OTP via email"""
    try:
        user = User.objects.get(id=user_id)
        subject = 'KYC Verification OTP'
        message = f'Your OTP for KYC verification is: {otp_code}\n\nThis OTP will expire in 10 minutes.'
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return f"OTP sent to {user.email}"
    except User.DoesNotExist:
        return "User not found"
    except Exception as e:
        return f"Failed to send OTP: {str(e)}"


@shared_task
def send_sms_otp(user_id, otp_code):
    """Send OTP via SMS using Twilio"""
    try:
        user = User.objects.get(id=user_id)
        
        # Import Twilio client
        from twilio.rest import Client
        
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        message = client.messages.create(
            body=f'Your KYC verification OTP is: {otp_code}. Valid for 10 minutes.',
            from_=settings.TWILIO_PHONE_NUMBER,
            to=user.phone_number
        )
        
        return f"SMS OTP sent to {user.phone_number}"
    except User.DoesNotExist:
        return "User not found"
    except Exception as e:
        return f"Failed to send SMS OTP: {str(e)}"


@shared_task
def send_welcome_email(user_id):
    """Send welcome email to new users"""
    try:
        user = User.objects.get(id=user_id)
        subject = 'Welcome to KYC Platform'
        message = f'''
        Welcome {user.first_name or user.email}!
        
        Thank you for registering with our KYC platform. 
        Please complete your KYC verification to access all features.
        
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
        return f"Welcome email sent to {user.email}"
    except User.DoesNotExist:
        return "User not found"
    except Exception as e:
        return f"Failed to send welcome email: {str(e)}"


@shared_task
def send_kyc_completion_email(user_id):
    """Send email when KYC is completed"""
    try:
        user = User.objects.get(id=user_id)
        subject = 'KYC Verification Completed'
        message = f'''
        Dear {user.first_name or user.email},
        
        Congratulations! Your KYC verification has been completed successfully.
        You now have full access to all platform features.
        
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
        return f"KYC completion email sent to {user.email}"
    except User.DoesNotExist:
        return "User not found"
    except Exception as e:
        return f"Failed to send KYC completion email: {str(e)}" 