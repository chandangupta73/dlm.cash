"""
Utility functions for transaction operations.
"""
from decimal import Decimal
from typing import Dict, Any, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import models

from .models import Transaction

User = get_user_model()


def format_currency_amount(amount: Decimal, currency: str) -> str:
    """
    Format currency amount with appropriate symbols and precision.
    
    Args:
        amount: Decimal amount
        currency: Currency code (INR, USDT)
    
    Returns:
        Formatted string with currency symbol
    """
    if currency == 'INR':
        return f"₹{amount:,.2f}"
    elif currency == 'USDT':
        return f"${amount:,.6f}"
    return str(amount)


def calculate_transaction_fees(amount: Decimal, currency: str, transaction_type: str) -> Dict[str, Decimal]:
    """
    Calculate transaction fees based on amount, currency, and type.
    
    Args:
        amount: Transaction amount
        currency: Currency code
        transaction_type: Type of transaction
    
    Returns:
        Dictionary with fee breakdown
    """
    fees = {
        'processing_fee': Decimal('0'),
        'network_fee': Decimal('0'),
        'total_fee': Decimal('0')
    }
    
    if currency == 'INR':
        if transaction_type in ['WITHDRAWAL']:
            # INR withdrawal fee: 2% or minimum ₹50
            processing_fee = max(amount * Decimal('0.02'), Decimal('50.00'))
            fees['processing_fee'] = processing_fee
        elif transaction_type in ['DEPOSIT']:
            # INR deposit is usually free
            fees['processing_fee'] = Decimal('0.00')
    
    elif currency == 'USDT':
        if transaction_type in ['WITHDRAWAL']:
            # USDT withdrawal: $1 network fee + 0.5% processing
            network_fee = Decimal('1.000000')
            processing_fee = amount * Decimal('0.005')
            fees['network_fee'] = network_fee
            fees['processing_fee'] = processing_fee
        elif transaction_type in ['DEPOSIT']:
            # USDT deposit is usually free
            fees['processing_fee'] = Decimal('0.000000')
    
    fees['total_fee'] = fees['processing_fee'] + fees['network_fee']
    return fees


def get_transaction_summary_by_period(
    user: User, 
    currency: Optional[str] = None, 
    period: str = 'month'
) -> Dict[str, Any]:
    """
    Get transaction summary for a user grouped by time period.
    
    Args:
        user: User object
        currency: Optional currency filter
        period: Time period ('day', 'week', 'month', 'year')
    
    Returns:
        Dictionary with transaction summary by period
    """
    queryset = Transaction.objects.filter(user=user)
    
    if currency:
        queryset = queryset.filter(currency=currency)
    
    # Calculate date range
    now = timezone.now()
    if period == 'day':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        date_format = '%Y-%m-%d'
    elif period == 'week':
        start_date = now - timezone.timedelta(days=7)
        date_format = '%Y-%m-%d'
    elif period == 'month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        date_format = '%Y-%m'
    elif period == 'year':
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        date_format = '%Y'
    else:
        raise ValueError("Invalid period. Must be 'day', 'week', 'month', or 'year'")
    
    # Filter by date range
    queryset = queryset.filter(created_at__gte=start_date)
    
    # Group by date and calculate totals
    summary = {}
    
    if period == 'day':
        # Group by day for the last 30 days
        for i in range(30):
            date = now - timezone.timedelta(days=i)
            date_str = date.strftime(date_format)
            
            day_transactions = queryset.filter(
                created_at__date=date.date()
            )
            
            summary[date_str] = {
                'total_volume': day_transactions.aggregate(
                    total=models.Sum('amount')
                )['total'] or Decimal('0'),
                'transaction_count': day_transactions.count(),
                'credits': day_transactions.filter(
                    type__in=['DEPOSIT', 'ROI', 'REFERRAL_BONUS', 'MILESTONE_BONUS']
                ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0'),
                'debits': day_transactions.filter(
                    type__in=['WITHDRAWAL', 'PLAN_PURCHASE']
                ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0'),
            }
    
    else:
        # For other periods, group by the period
        queryset = queryset.extra(
            select={'period': f"DATE_TRUNC('{period}', created_at)"}
        ).values('period').annotate(
            total_volume=models.Sum('amount'),
            transaction_count=models.Count('id'),
            credits=models.Sum(
                models.Case(
                    models.When(
                        type__in=['DEPOSIT', 'ROI', 'REFERRAL_BONUS', 'MILESTONE_BONUS'],
                        then=models.F('amount')
                    ),
                    default=Decimal('0')
                )
            ),
            debits=models.Sum(
                models.Case(
                    models.When(
                        type__in=['WITHDRAWAL', 'PLAN_PURCHASE'],
                        then=models.F('amount')
                    ),
                    default=Decimal('0')
                )
            )
        ).order_by('period')
        
        for item in queryset:
            period_str = item['period'].strftime(date_format)
            summary[period_str] = {
                'total_volume': item['total_volume'] or Decimal('0'),
                'transaction_count': item['transaction_count'],
                'credits': item['credits'] or Decimal('0'),
                'debits': item['debits'] or Decimal('0'),
            }
    
    return summary


def validate_transaction_data(
    transaction_type: str,
    currency: str,
    amount: Decimal,
    user: User
) -> Dict[str, Any]:
    """
    Validate transaction data before creation.
    
    Args:
        transaction_type: Type of transaction
        currency: Currency code
        amount: Transaction amount
        user: User object
    
    Returns:
        Dictionary with validation result and any errors
    """
    errors = []
    warnings = []
    
    # Validate amount
    if amount <= 0:
        errors.append("Transaction amount must be positive")
    
    # Validate currency-specific constraints
    if currency == 'INR':
        if amount.as_tuple().exponent < -2:
            errors.append("INR amounts cannot have more than 2 decimal places")
        
        # INR amount limits
        if amount > Decimal('1000000.00'):  # 10 Lakhs
            warnings.append("Large INR transaction amount")
    
    elif currency == 'USDT':
        if amount.as_tuple().exponent < -6:
            errors.append("USDT amounts cannot have more than 6 decimal places")
        
        # USDT amount limits
        if amount > Decimal('100000.000000'):  # 100k USDT
            warnings.append("Large USDT transaction amount")
    
    # Validate transaction type constraints
    if transaction_type in ['WITHDRAWAL', 'PLAN_PURCHASE']:
        # Check if user has sufficient balance
        if currency == 'INR':
            try:
                wallet = user.inr_wallet
                if wallet.balance < amount:
                    errors.append(f"Insufficient INR balance. Available: ₹{wallet.balance}")
            except:
                errors.append("INR wallet not found")
        
        elif currency == 'USDT':
            try:
                wallet = user.usdt_wallet
                if wallet.balance < amount:
                    errors.append(f"Insufficient USDT balance. Available: ${wallet.balance}")
            except:
                errors.append("USDT wallet not found")
    
    # Validate user status
    if not user.is_active:
        errors.append("Cannot create transaction for inactive user")
    
    # Check for suspicious activity (basic fraud detection)
    recent_transactions = Transaction.objects.filter(
        user=user,
        created_at__gte=timezone.now() - timezone.timedelta(hours=1)
    )
    
    if recent_transactions.count() > 10:
        warnings.append("High transaction frequency detected")
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }


def generate_transaction_reference(
    transaction_type: str,
    user_id: int,
    timestamp: Optional[timezone.datetime] = None
) -> str:
    """
    Generate a unique reference ID for transactions.
    
    Args:
        transaction_type: Type of transaction
        user_id: User ID
        timestamp: Optional timestamp (defaults to now)
    
    Returns:
        Unique reference string
    """
    if timestamp is None:
        timestamp = timezone.now()
    
    # Format: TYPE-USERID-TIMESTAMP-RANDOM
    timestamp_str = timestamp.strftime('%Y%m%d%H%M%S')
    
    # Generate a short random suffix
    import random
    import string
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    
    return f"{transaction_type}-{user_id}-{timestamp_str}-{suffix}"


def get_transaction_statistics(
    user: Optional[User] = None,
    currency: Optional[str] = None,
    date_from: Optional[timezone.datetime] = None,
    date_to: Optional[timezone.datetime] = None
) -> Dict[str, Any]:
    """
    Get comprehensive transaction statistics.
    
    Args:
        user: Optional user filter
        currency: Optional currency filter
        date_from: Optional start date
        date_to: Optional end date
    
    Returns:
        Dictionary with transaction statistics
    """
    queryset = Transaction.objects.all()
    
    if user:
        queryset = queryset.filter(user=user)
    
    if currency:
        queryset = queryset.filter(currency=currency)
    
    if date_from:
        queryset = queryset.filter(created_at__gte=date_from)
    
    if date_to:
        queryset = queryset.filter(created_at__lte=date_to)
    
    # Basic counts
    total_transactions = queryset.count()
    successful_transactions = queryset.filter(status='SUCCESS').count()
    pending_transactions = queryset.filter(status='PENDING').count()
    failed_transactions = queryset.filter(status='FAILED').count()
    
    # Volume statistics
    total_volume = queryset.aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')
    
    successful_volume = queryset.filter(status='SUCCESS').aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')
    
    # Statistics by type
    type_stats = {}
    for transaction_type, _ in Transaction.TRANSACTION_TYPE_CHOICES:
        type_queryset = queryset.filter(type=transaction_type)
        type_stats[transaction_type] = {
            'count': type_queryset.count(),
            'volume': type_queryset.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0'),
            'success_rate': (
                type_queryset.filter(status='SUCCESS').count() / 
                max(type_queryset.count(), 1) * 100
            )
        }
    
    # Statistics by currency
    currency_stats = {}
    for currency_choice, _ in Transaction.CURRENCY_CHOICES:
        currency_queryset = queryset.filter(currency=currency_choice)
        currency_stats[currency_choice] = {
            'count': currency_queryset.count(),
            'volume': currency_queryset.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0'),
            'avg_amount': currency_queryset.aggregate(
                avg=models.Avg('amount')
            )['avg'] or Decimal('0')
        }
    
    return {
        'overall': {
            'total_transactions': total_transactions,
            'total_volume': total_volume,
            'successful_transactions': successful_transactions,
            'pending_transactions': pending_transactions,
            'failed_transactions': failed_transactions,
            'success_rate': (successful_transactions / max(total_transactions, 1)) * 100,
            'successful_volume': successful_volume
        },
        'by_type': type_stats,
        'by_currency': currency_stats
    }
