from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

from .models import Transaction
from .services import TransactionIntegrationService

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=Transaction)
def transaction_post_save(sender, instance, created, **kwargs):
    """Handle post-save events for transactions."""
    if created:
        logger.info(f"New transaction created: {instance.id} - {instance.type} - {instance.currency} {instance.amount}")
        
        # You can add additional logic here, such as:
        # - Sending notifications
        # - Updating analytics
        # - Triggering webhooks
        # - Logging to external systems
        
    else:
        logger.info(f"Transaction updated: {instance.id} - Status: {instance.status}")


@receiver(post_delete, sender=Transaction)
def transaction_post_delete(sender, instance, **kwargs):
    """Handle post-delete events for transactions."""
    logger.warning(f"Transaction deleted: {instance.id} - {instance.type} - {instance.currency} {instance.amount}")
    
    # Note: In a production system, you might want to prevent deletion
    # and instead mark transactions as cancelled or archived


# Integration signals for existing modules
# These signals will be connected when the respective modules are imported

def connect_integration_signals():
    """Connect signals for integrating with existing modules."""
    try:
        # Try to import models, but don't fail if they don't exist
        try:
            from app.wallet.models import WalletTransaction as OldWalletTransaction
        except ImportError:
            OldWalletTransaction = None
            logger.info("Old wallet transaction model not available")
        
        try:
            from app.investment.models import Investment, InvestmentROI
        except ImportError:
            Investment = None
            InvestmentROI = None
            logger.info("Investment models not available")
        
        try:
            from app.referral.models import ReferralBonus
        except ImportError:
            ReferralBonus = None
            logger.info("Referral models not available")
        
        # Temporarily disabled to fix investment creation issues
        # Only connect signals if models exist
        # if OldWalletTransaction:
        #     @receiver(post_save, sender=OldWalletTransaction)
        #     def migrate_old_wallet_transaction(sender, instance, created, **kwargs):
        #         """Migrate old wallet transactions to new centralized system."""
        #         if created:
        #             try:
        #                 # Map old transaction types to new ones
        #                 type_mapping = {
        #                     'deposit': 'DEPOSIT',
        #                     'withdrawal': 'WITHDRAWAL',
        #                     'roi_credit': 'ROI',
        #                     'referral_bonus': 'REFERRAL_BONUS',
        #                     'admin_adjustment': 'ADMIN_ADJUSTMENT',
        #                     'investment': 'PLAN_PURCHASE',
        #                     'refund': 'BREAKDOWN_REFUND',
        #                     'usdt_deposit': 'DEPOSIT',
        #                 }
        #                 
        #                 new_type = type_mapping.get(instance.transaction_type, 'ADMIN_ADJUSTMENT')
        #                 
        #                 # Create new centralized transaction
        #                 TransactionIntegrationService.log_deposit(
        #                     user=instance.user,
        #                     amount=instance.amount,
        #                     currency=instance.wallet_type.upper(),
        #                     reference_id=str(instance.id),
        #                     meta_data={
        #                     'migrated_from': 'old_wallet_transaction',
        #                     'old_transaction_id': str(instance.id),
        #                     'old_type': instance.transaction_type,
        #                     'balance_before': str(instance.balance_before),
        #                     'balance_after': str(instance.balance_after),
        #                     description': instance.description or '',
        #                     'chain_type': instance.chain_type or '',
        #                 }
        #                 )
        #                 
        #                 logger.info(f"Migrated old wallet transaction {instance.id} to new centralized system")
        #                 
        #             except Exception as e:
        #                 logger.error(f"Failed to migrate old wallet transaction {instance.id}: {str(e)}")
        
        if InvestmentROI:
            @receiver(post_save, sender=InvestmentROI)
            def log_investment_roi(sender, instance, created, **kwargs):
                """Log investment ROI payouts to centralized transaction system."""
                if created and instance.status == 'paid':
                    try:
                        TransactionIntegrationService.log_roi_payout(
                            user=instance.investment.user,
                            amount=instance.amount,
                            currency=instance.investment.currency,
                            reference_id=str(instance.id),
                            meta_data={
                                'investment_id': str(instance.investment.id),
                                'roi_period': instance.period,
                                'roi_rate': str(instance.rate),
                                'investment_amount': str(instance.investment.amount),
                            }
                        )
                        
                        logger.info(f"Logged ROI payout {instance.id} to centralized transaction system")
                        
                    except Exception as e:
                        logger.error(f"Failed to log ROI payout {instance.id}: {str(e)}")
        
        if ReferralBonus:
            @receiver(post_save, sender=ReferralBonus)
            def log_referral_bonus(sender, instance, created, **kwargs):
                """Log referral bonuses to centralized transaction system."""
                if created and instance.status == 'paid':
                    try:
                        TransactionIntegrationService.log_referral_bonus(
                            user=instance.user,
                            amount=instance.amount,
                            currency=instance.currency,
                            reference_id=str(instance.id),
                            meta_data={
                                'referral_id': str(instance.referral.id),
                                'level': instance.level,
                                'referrer_username': instance.referral.user.username,
                                'referred_username': instance.referral.referred_user.username,
                            }
                        )
                        
                        logger.info(f"Logged referral bonus {instance.id} to centralized transaction system")
                        
                    except Exception as e:
                        logger.error(f"Failed to log referral bonus {instance.id}: {str(e)}")
        
        logger.info("Connected integration signals for existing modules")
        
    except Exception as e:
        logger.error(f"Error connecting integration signals: {str(e)}")


# Connect signals when the module is imported
try:
    connect_integration_signals()
except Exception as e:
    logger.error(f"Failed to connect integration signals: {str(e)}")
