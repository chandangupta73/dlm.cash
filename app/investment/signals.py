from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Investment, InvestmentPlan

@receiver(post_save, sender=Investment)
def investment_post_save_handler(sender, instance, created, **kwargs):
    """Handle post-save events for Investment model."""
    if created:
        # Log investment creation
        print(f"New investment created: {instance.id} for user {instance.user.id}")
        
        # Trigger referral bonus processing
        try:
            from app.referral.services import ReferralService
            ReferralService.process_investment_referral_bonus(instance)
        except ImportError:
            # Referral app might not be available
            pass
    else:
        # Log investment updates
        print(f"Investment updated: {instance.id}")

@receiver(post_delete, sender=Investment)
def investment_post_delete_handler(sender, instance, **kwargs):
    """Handle post-delete events for Investment model."""
    print(f"Investment deleted: {instance.id} for user {instance.user.id}")

@receiver(post_save, sender=InvestmentPlan)
def investment_plan_post_save_handler(sender, instance, created, **kwargs):
    """Handle post-save events for InvestmentPlan model."""
    if created:
        print(f"New investment plan created: {instance.name}")
    else:
        print(f"Investment plan updated: {instance.name}")

@receiver(post_delete, sender=InvestmentPlan)
def investment_plan_post_delete_handler(sender, instance, **kwargs):
    """Handle post-delete events for InvestmentPlan model."""
    print(f"Investment plan deleted: {instance.name}")



