from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from decimal import Decimal
import logging

from .models import Investment
from app.wallet.models import WalletTransaction

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def credit_roi_task(self):
    """
    Celery task to credit ROI for active investments.
    This task should be scheduled to run based on the frequency of each investment plan.
    """
    try:
        with transaction.atomic():
            # Get all active investments that are due for ROI
            now = timezone.now()
            due_investments = Investment.objects.filter(
                Q(status='active') & 
                Q(is_active=True) & 
                Q(next_roi_date__lte=now)
            ).select_related('user', 'plan')
            
            if not due_investments.exists():
                logger.info("No investments due for ROI crediting")
                return "No investments due for ROI crediting"
            
            credited_count = 0
            total_roi_credited = Decimal('0')
            
            for investment in due_investments:
                try:
                    # Calculate ROI amount for this cycle
                    roi_amount = calculate_roi_amount(investment)
                    
                    if roi_amount > 0:
                        # Credit ROI to the investment
                        investment.credit_roi(roi_amount)
                        
                        # Credit ROI to user's wallet
                        credit_roi_to_wallet(investment, roi_amount)
                        
                        credited_count += 1
                        total_roi_credited += roi_amount
                        
                        logger.info(
                            f"ROI credited for investment {investment.id}: "
                            f"{roi_amount} {investment.currency.upper()}"
                        )
                    
                except Exception as e:
                    logger.error(
                        f"Failed to credit ROI for investment {investment.id}: {str(e)}"
                    )
                    # Continue with other investments
                    continue
            
            logger.info(
                f"ROI crediting completed: {credited_count} investments processed, "
                f"Total ROI: {total_roi_credited}"
            )
            
            return f"ROI crediting completed: {credited_count} investments processed"
            
    except Exception as e:
        logger.error(f"ROI crediting task failed: {str(e)}")
        # Retry the task
        raise self.retry(countdown=60, exc=e)


def calculate_roi_amount(investment):
    """
    Calculate ROI amount for a single investment cycle.
    
    Args:
        investment: Investment instance
        
    Returns:
        Decimal: ROI amount for this cycle
    """
    try:
        # Get ROI rate per cycle from the plan
        roi_rate_per_cycle = investment.plan.get_roi_per_cycle()
        
        # Calculate ROI amount
        roi_amount = investment.amount * Decimal(str(roi_rate_per_cycle))
        
        # Round to appropriate decimal places
        if investment.currency == 'inr':
            roi_amount = roi_amount.quantize(Decimal('0.01'))
        else:  # usdt
            roi_amount = roi_amount.quantize(Decimal('0.000001'))
        
        return roi_amount
        
    except Exception as e:
        logger.error(f"Failed to calculate ROI for investment {investment.id}: {str(e)}")
        return Decimal('0')


def credit_roi_to_wallet(investment, roi_amount):
    """
    Credit ROI amount to user's wallet and log the transaction.
    
    Args:
        investment: Investment instance
        roi_amount: ROI amount to credit
    """
    try:
        user = investment.user
        currency = investment.currency
        
        # Get the appropriate wallet
        if currency == 'inr':
            wallet = user.inr_wallet
            chain_type = None
        else:  # usdt
            wallet = user.usdt_wallet
            chain_type = wallet.chain_type
        
        # Record balance before credit
        balance_before = wallet.balance
        
        # Credit ROI to wallet
        wallet.add_balance(roi_amount)
        wallet.save()
        
        # Log the ROI transaction
        WalletTransaction.objects.create(
            user=user,
            transaction_type='roi_credit',
            wallet_type=currency,
            chain_type=chain_type,
            amount=roi_amount,
            balance_before=balance_before,
            balance_after=wallet.balance,
            status='completed',
            reference_id=str(investment.id),
            description=f"ROI credit for {investment.plan.name}",
            metadata={
                'investment_id': str(investment.id),
                'plan_name': investment.plan.name,
                'plan_roi_rate': float(investment.plan.roi_rate),
                'plan_frequency': investment.plan.frequency,
                'roi_cycle_date': timezone.now().isoformat()
            }
        )
        
        logger.info(
            f"ROI credited to {currency.upper()} wallet for user {user.username}: "
            f"{roi_amount} (Balance: {balance_before} → {wallet.balance})"
        )
        
    except Exception as e:
        logger.error(
            f"Failed to credit ROI to wallet for investment {investment.id}: {str(e)}"
        )
        raise


@shared_task
def process_completed_investments():
    """
    Task to process completed investments and mark them as inactive.
    This task should be run daily to clean up completed investments.
    """
    try:
        with transaction.atomic():
            # Get all investments that have reached their end date
            now = timezone.now()
            completed_investments = Investment.objects.filter(
                Q(status='active') & 
                Q(is_active=True) & 
                Q(end_date__lte=now)
            )
            
            if not completed_investments.exists():
                logger.info("No investments to mark as completed")
                return "No investments to mark as completed"
            
            # Mark investments as completed
            for investment in completed_investments:
                investment.status = 'completed'
                investment.is_active = False
                investment.save(update_fields=['status', 'is_active', 'updated_at'])
                
                logger.info(f"Investment {investment.id} marked as completed")
            
            logger.info(f"Processed {completed_investments.count()} completed investments")
            return f"Processed {completed_investments.count()} completed investments"
            
    except Exception as e:
        logger.error(f"Failed to process completed investments: {str(e)}")
        raise


@shared_task
def cleanup_old_breakdown_requests():
    """
    Task to cleanup old processed breakdown requests.
    This task should be run periodically to maintain database performance.
    """
    try:
        # Delete breakdown requests older than 90 days that are not pending
        cutoff_date = timezone.now() - timezone.timedelta(days=90)
        
        old_requests = BreakdownRequest.objects.filter(
            Q(created_at__lt=cutoff_date) & 
            ~Q(status='pending')
        )
        
        if not old_requests.exists():
            logger.info("No old breakdown requests to cleanup")
            return "No old breakdown requests to cleanup"
        
        count = old_requests.count()
        old_requests.delete()
        
        logger.info(f"Cleaned up {count} old breakdown requests")
        return f"Cleaned up {count} old breakdown requests"
        
    except Exception as e:
        logger.error(f"Failed to cleanup old breakdown requests: {str(e)}")
        raise


@shared_task
def investment_health_check():
    """
    Task to perform health checks on the investment system.
    This task should be run periodically to identify potential issues.
    """
    try:
        health_report = {}
        
        # Check for investments with invalid next_roi_date
        invalid_roi_dates = Investment.objects.filter(
            Q(status='active') & 
            Q(is_active=True) & 
            Q(next_roi_date__isnull=True)
        ).count()
        
        health_report['invalid_roi_dates'] = invalid_roi_dates
        
        # Check for investments with negative ROI
        negative_roi = Investment.objects.filter(
            roi_accrued__lt=0
        ).count()
        
        health_report['negative_roi'] = negative_roi
        
        # Check for breakdown requests without investments
        orphaned_breakdowns = BreakdownRequest.objects.filter(
            investment__isnull=True
        ).count()
        
        health_report['orphaned_breakdowns'] = orphaned_breakdowns
        
        # Log health report
        logger.info(f"Investment system health check: {health_report}")
        
        return health_report
        
    except Exception as e:
        logger.error(f"Investment health check failed: {str(e)}")
        raise
