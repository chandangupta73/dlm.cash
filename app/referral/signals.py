from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

from .models import (
    Referral, ReferralEarning, ReferralMilestone, 
    UserReferralProfile, ReferralConfig
)
from .services import ReferralService

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=User)
def create_user_referral_profile(sender, instance, created, **kwargs):
    """
    Automatically create referral profile when a new user is created.
    """
    if created:
        try:
            # Create referral profile for new user
            profile = UserReferralProfile.objects.create(user=instance)
            profile.generate_referral_code()
            profile.save()
            
            logger.info(f"Created referral profile for user {instance.email}")
            
        except Exception as e:
            logger.error(f"Error creating referral profile for user {instance.email}: {str(e)}")


@receiver(post_save, sender=ReferralEarning)
def update_user_stats_on_earning(sender, instance, created, **kwargs):
    """
    Update user referral statistics when a new earning is created or updated.
    """
    if created or instance.status == 'credited':
        try:
            # Update the user's referral profile stats
            if hasattr(instance.referral, 'user') and instance.referral.user:
                profile = instance.referral.user.referral_profile
                profile.update_stats()
                logger.info(f"Updated stats for user {instance.referral.user.email}")
                
        except Exception as e:
            logger.error(f"Error updating user stats: {str(e)}")


@receiver(post_save, sender=Referral)
def update_referrer_stats_on_referral(sender, instance, created, **kwargs):
    """
    Update referrer statistics when a new referral is created.
    """
    if created:
        try:
            # Update the referrer's stats
            if instance.user:
                profile = instance.user.referral_profile
                profile.update_stats()
                logger.info(f"Updated referrer stats for user {instance.user.email}")
                
        except Exception as e:
            logger.error(f"Error updating referrer stats: {str(e)}")


# Investment-related signals (these will be imported in the investment app)
def investment_post_save_handler(sender, instance, created, **kwargs):
    """
    Handle referral bonus processing when an investment is created.
    This function will be called from the investment app's signals.
    """
    if created:
        try:
            # Process referral bonus for this investment
            success = ReferralService.process_investment_referral_bonus(instance)
            
            if success:
                logger.info(f"Successfully processed referral bonus for investment {instance.id}")
            else:
                logger.warning(f"Failed to process referral bonus for investment {instance.id}")
                
        except Exception as e:
            logger.error(f"Error processing referral bonus for investment {instance.id}: {str(e)}")


# Milestone-related signals
@receiver(post_save, sender=ReferralMilestone)
def milestone_post_save_handler(sender, instance, created, **kwargs):
    """
    Handle milestone creation/updates.
    """
    if created:
        logger.info(f"Created new milestone: {instance.name}")
    else:
        logger.info(f"Updated milestone: {instance.name}")


@receiver(post_save, sender=ReferralConfig)
def config_post_save_handler(sender, instance, created, **kwargs):
    """
    Handle referral configuration changes.
    """
    if created:
        logger.info(f"Created new referral configuration with {instance.max_levels} levels")
    else:
        logger.info(f"Updated referral configuration: L1:{instance.level_1_percentage}%, L2:{instance.level_2_percentage}%, L3:{instance.level_3_percentage}%")


# Cleanup signals
@receiver(post_delete, sender=User)
def cleanup_user_referral_data(sender, instance, **kwargs):
    """
    Clean up referral data when a user is deleted.
    Note: This is a safety measure, but user deletion should be handled carefully.
    """
    try:
        # Delete referral profile
        UserReferralProfile.objects.filter(user=instance).delete()
        
        # Delete referral relationships
        Referral.objects.filter(user=instance).delete()
        Referral.objects.filter(referred_user=instance).delete()
        Referral.objects.filter(referrer=instance).delete()
        
        # Delete referral earnings
        ReferralEarning.objects.filter(referral__user=instance).delete()
        
        logger.info(f"Cleaned up referral data for deleted user {instance.email}")
        
    except Exception as e:
        logger.error(f"Error cleaning up referral data for user {instance.email}: {str(e)}")


# Signal registration function
def register_referral_signals():
    """
    Register all referral-related signals.
    This function can be called from the app's ready() method.
    """
    # The signals are automatically registered when this module is imported
    # This function is provided for explicit registration if needed
    logger.info("Referral signals registered")


def register_signals():
    """
    Alias for register_referral_signals for backward compatibility.
    """
    return register_referral_signals()


# Export the investment handler for use in investment app
__all__ = [
    'investment_post_save_handler',
    'register_referral_signals',
    'register_signals'
]
