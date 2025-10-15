from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Announcement, AdminActionLog

User = get_user_model()


@receiver(post_save, sender=Announcement)
def log_announcement_action(sender, instance, created, **kwargs):
    """Log announcement creation/update actions."""
    if created:
        # This will be handled by the service layer
        pass
    else:
        # Log update action
        try:
            AdminActionLog.objects.create(
                admin_user=instance.created_by,
                action_type='ANNOUNCEMENT',
                action_description=f"Updated announcement: {instance.title}",
                target_model='Announcement',
                target_id=str(instance.id),
                metadata={
                    'action': 'update',
                    'title': instance.title,
                    'status': instance.status
                }
            )
        except Exception:
            # Silently fail if logging fails
            pass


@receiver(post_delete, sender=Announcement)
def log_announcement_deletion(sender, instance, **kwargs):
    """Log announcement deletion actions."""
    try:
        AdminActionLog.objects.create(
            admin_user=instance.created_by,
            action_type='ANNOUNCEMENT',
            action_description=f"Deleted announcement: {instance.title}",
            target_model='Announcement',
            target_id=str(instance.id),
            metadata={
                'action': 'delete',
                'title': instance.title,
                'status': instance.status
            }
        )
    except Exception:
        # Silently fail if logging fails
        pass


@receiver(post_save, sender=User)
def log_user_status_change(sender, instance, **kwargs):
    """Log user status changes."""
    if hasattr(instance, '_state') and instance._state.adding:
        # New user created
        return
    
    try:
        # Check if user status changed
        if hasattr(instance, '_original_is_active'):
            if instance._original_is_active != instance.is_active:
                action = 'activated' if instance.is_active else 'deactivated'
                AdminActionLog.objects.create(
                    admin_user=instance,  # User is changing their own status
                    action_type='USER_MANAGEMENT',
                    action_description=f"User {action}: {instance.email}",
                    target_user=instance,
                    target_model='User',
                    target_id=str(instance.id),
                    metadata={
                        'action': action,
                        'previous_status': instance._original_is_active,
                        'new_status': instance.is_active
                    }
                )
    except Exception:
        # Silently fail if logging fails
        pass


def save_original_user_status(sender, instance, **kwargs):
    """Save original user status before save."""
    if not instance._state.adding:
        try:
            original = User.objects.get(pk=instance.pk)
            instance._original_is_active = original.is_active
        except User.DoesNotExist:
            instance._original_is_active = instance.is_active


# Connect the signal
post_save.connect(save_original_user_status, sender=User, dispatch_uid='save_original_user_status')
