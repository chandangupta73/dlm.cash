from django.db import transaction as db_transaction, models
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.utils import timezone
from decimal import Decimal
import csv
import io
from typing import Optional, Dict, Any, List

from .models import Transaction
from app.wallet.models import INRWallet, USDTWallet

User = get_user_model()


class TransactionService:
    """Service class for managing transactions and wallet operations."""
    
    @staticmethod
    def create_transaction(
        user: User,
        type: str,
        currency: str,
        amount: Decimal,
        reference_id: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None,
        status: str = 'SUCCESS',
        update_wallet: bool = True
    ) -> Transaction:
        """
        Create a transaction and optionally update wallet balance.
        
        Args:
            user: User for whom the transaction is created
            type: Transaction type (e.g., 'DEPOSIT', 'WITHDRAWAL')
            currency: Currency of the transaction ('INR' or 'USDT')
            amount: Transaction amount
            reference_id: Optional reference to related object
            meta_data: Optional metadata dictionary
            status: Transaction status (default: 'SUCCESS')
            update_wallet: Whether to update wallet balance (default: True)
        
        Returns:
            Created Transaction instance
        
        Raises:
            ValueError: If transaction creation fails
            Exception: If wallet update fails
        """
        if update_wallet:
            return TransactionService._create_transaction_with_wallet_update(
                user, type, currency, amount, reference_id, meta_data, status
            )
        else:
            return Transaction.create_transaction(
                user, type, currency, amount, reference_id, meta_data, status
            )
    
    @staticmethod
    def _create_transaction_with_wallet_update(
        user: User,
        type: str,
        currency: str,
        amount: Decimal,
        reference_id: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None,
        status: str = 'SUCCESS'
    ) -> Transaction:
        """Create transaction and update wallet balance atomically."""
        try:
            with db_transaction.atomic():
                # Create the transaction first
                transaction = Transaction.create_transaction(
                    user, type, currency, amount, reference_id, meta_data, status
                )
                
                # Update wallet balance if transaction is successful
                if status == 'SUCCESS':
                    TransactionService._update_wallet_balance(
                        user, currency, amount, type
                    )
                
                return transaction
                
        except Exception as e:
            raise Exception(f"Failed to create transaction: {str(e)}")
    
    @staticmethod
    def _update_wallet_balance(user: User, currency: str, amount: Decimal, type: str) -> None:
        """Update wallet balance based on transaction type and amount."""
        if currency == 'INR':
            wallet, created = INRWallet.objects.get_or_create(
                user=user,
                defaults={'balance': Decimal('0.00'), 'status': 'active', 'is_active': True}
            )
            
            if type in ['DEPOSIT', 'ROI', 'REFERRAL_BONUS', 'MILESTONE_BONUS', 'ADMIN_ADJUSTMENT', 'BREAKDOWN_REFUND']:
                wallet.add_balance(amount)
            elif type in ['WITHDRAWAL', 'PLAN_PURCHASE']:
                if not wallet.deduct_balance(amount):
                    raise ValueError(f"Insufficient INR balance for {type}")
                    
        elif currency == 'USDT':
            wallet, created = USDTWallet.objects.get_or_create(
                user=user,
                defaults={'balance': Decimal('0.000000'), 'status': 'active', 'is_active': True}
            )
            
            if type in ['DEPOSIT', 'ROI', 'REFERRAL_BONUS', 'MILESTONE_BONUS', 'ADMIN_ADJUSTMENT', 'BREAKDOWN_REFUND']:
                wallet.add_balance(amount)
            elif type in ['WITHDRAWAL', 'PLAN_PURCHASE']:
                if not wallet.deduct_balance(amount):
                    raise ValueError(f"Insufficient USDT balance for {type}")
    
    @staticmethod
    def get_user_transactions(
        user: User,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Get paginated transactions for a specific user with optional filters.
        
        Args:
            user: User whose transactions to retrieve
            filters: Optional filter dictionary
            page: Page number (1-based)
            page_size: Number of transactions per page
        
        Returns:
            Dictionary with transactions and pagination info
        """
        queryset = Transaction.objects.filter(user=user)
        
        if filters:
            queryset = TransactionService._apply_filters(queryset, filters)
        
        # Calculate pagination
        total_count = queryset.count()
        total_pages = (total_count + page_size - 1) // page_size
        offset = (page - 1) * page_size
        
        # Get paginated results
        transactions = queryset[offset:offset + page_size]
        
        return {
            'transactions': transactions,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_previous': page > 1
            }
        }
    
    @staticmethod
    def get_admin_transactions(
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Get paginated transactions for admin view with optional filters.
        
        Args:
            filters: Optional filter dictionary
            page: Page number (1-based)
            page_size: Number of transactions per page
        
        Returns:
            Dictionary with transactions and pagination info
        """
        queryset = Transaction.objects.select_related('user')
        
        if filters:
            queryset = TransactionService._apply_filters(queryset, filters)
        
        # Calculate pagination
        total_count = queryset.count()
        total_pages = (total_count + page_size - 1) // page_size
        offset = (page - 1) * page_size
        
        # Get paginated results
        transactions = queryset[offset:offset + page_size]
        
        return {
            'transactions': transactions,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_previous': page > 1
            }
        }
    
    @staticmethod
    def _apply_filters(queryset, filters: Dict[str, Any]):
        """Apply filters to transaction queryset."""
        if filters.get('type'):
            queryset = queryset.filter(type=filters['type'])
        
        if filters.get('currency'):
            queryset = queryset.filter(currency=filters['currency'])
        
        if filters.get('status'):
            queryset = queryset.filter(status=filters['status'])
        
        if filters.get('date_from'):
            queryset = queryset.filter(created_at__date__gte=filters['date_from'])
        
        if filters.get('date_to'):
            queryset = queryset.filter(created_at__date__lte=filters['date_to'])
        
        if filters.get('min_amount'):
            queryset = queryset.filter(amount__gte=filters['min_amount'])
        
        if filters.get('max_amount'):
            queryset = queryset.filter(amount__lte=filters['max_amount'])
        
        if filters.get('search'):
            search_term = filters['search']
            from django.db.models import Q
            queryset = queryset.filter(
                Q(reference_id__icontains=search_term) |
                Q(meta_data__icontains=search_term)
            )
        
        return queryset
    
    @staticmethod
    def export_transactions_csv(filters: Optional[Dict[str, Any]] = None) -> HttpResponse:
        """
        Export transactions to CSV format with optional filters.
        
        Args:
            filters: Optional filter dictionary
        
        Returns:
            HttpResponse with CSV file
        """
        queryset = Transaction.objects.select_related('user')
        
        if filters:
            queryset = TransactionService._apply_filters(queryset, filters)
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="transactions_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        # Create CSV writer
        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'Transaction ID',
            'Username',
            'Email',
            'Type',
            'Currency',
            'Amount',
            'Status',
            'Reference ID',
            'Created At',
            'Updated At'
        ])
        
        # Write data rows
        for transaction in queryset:
            writer.writerow([
                str(transaction.id),
                transaction.user.username,
                transaction.user.email,
                transaction.get_type_display(),
                transaction.get_currency_display(),
                str(transaction.amount),
                transaction.get_status_display(),
                transaction.reference_id or '',
                transaction.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                transaction.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    
    @staticmethod
    def get_transaction_summary(user: User, currency: Optional[str] = None) -> Dict[str, Any]:
        """
        Get transaction summary for a user.
        
        Args:
            user: User whose summary to retrieve
            currency: Optional currency filter
        
        Returns:
            Dictionary with transaction summary
        """
        queryset = Transaction.objects.filter(user=user)
        
        if currency:
            queryset = queryset.filter(currency=currency)
        
        # Calculate totals by type
        summary = {}
        for transaction_type, _ in Transaction.TRANSACTION_TYPE_CHOICES:
            type_transactions = queryset.filter(type=transaction_type)
            summary[transaction_type] = {
                'count': type_transactions.count(),
                'total_amount': type_transactions.aggregate(
                    total=models.Sum('amount')
                )['total'] or Decimal('0')
            }
        
        # Calculate overall totals
        summary['overall'] = {
            'total_transactions': queryset.count(),
            'total_volume': queryset.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0'),
            'successful_transactions': queryset.filter(status='SUCCESS').count(),
            'pending_transactions': queryset.filter(status='PENDING').count(),
            'failed_transactions': queryset.filter(status='FAILED').count()
        }
        
        return summary


class TransactionIntegrationService:
    """Service for integrating transactions with existing modules."""
    
    @staticmethod
    def log_deposit(user: User, amount: Decimal, currency: str, reference_id: str, meta_data: Optional[Dict[str, Any]] = None) -> Transaction:
        """Log a deposit transaction."""
        return TransactionService.create_transaction(
            user=user,
            type='DEPOSIT',
            currency=currency,
            amount=amount,
            reference_id=reference_id,
            meta_data=meta_data,
            status='SUCCESS',
            update_wallet=True
        )
    
    @staticmethod
    def log_withdrawal(user: User, amount: Decimal, currency: str, reference_id: str, meta_data: Optional[Dict[str, Any]] = None) -> Transaction:
        """Log a withdrawal transaction."""
        return TransactionService.create_transaction(
            user=user,
            type='WITHDRAWAL',
            currency=currency,
            amount=amount,
            reference_id=reference_id,
            meta_data=meta_data,
            status='SUCCESS',
            update_wallet=True
        )
    
    @staticmethod
    def log_roi_payout(user: User, amount: Decimal, currency: str, reference_id: str, meta_data: Optional[Dict[str, Any]] = None) -> Transaction:
        """Log an ROI payout transaction."""
        return TransactionService.create_transaction(
            user=user,
            type='ROI',
            currency=currency,
            amount=amount,
            reference_id=reference_id,
            meta_data=meta_data,
            status='SUCCESS',
            update_wallet=True
        )
    
    @staticmethod
    def log_referral_bonus(user: User, amount: Decimal, currency: str, reference_id: str, meta_data: Optional[Dict[str, Any]] = None) -> Transaction:
        """Log a referral bonus transaction."""
        return TransactionService.create_transaction(
            user=user,
            type='REFERRAL_BONUS',
            currency=currency,
            amount=amount,
            reference_id=reference_id,
            meta_data=meta_data,
            status='SUCCESS',
            update_wallet=True
        )
    
    @staticmethod
    def log_milestone_bonus(user: User, amount: Decimal, currency: str, reference_id: str, meta_data: Optional[Dict[str, Any]] = None) -> Transaction:
        """Log a milestone bonus transaction."""
        return TransactionService.create_transaction(
            user=user,
            type='MILESTONE_BONUS',
            currency=currency,
            amount=amount,
            reference_id=reference_id,
            meta_data=meta_data,
            status='SUCCESS',
            update_wallet=True
        )
    
    @staticmethod
    def log_admin_adjustment(user: User, amount: Decimal, currency: str, reference_id: str, meta_data: Optional[Dict[str, Any]] = None) -> Transaction:
        """Log an admin adjustment transaction."""
        return TransactionService.create_transaction(
            user=user,
            type='ADMIN_ADJUSTMENT',
            currency=currency,
            amount=amount,
            reference_id=reference_id,
            meta_data=meta_data,
            status='SUCCESS',
            update_wallet=True
        )
    
    @staticmethod
    def log_plan_purchase(user: User, amount: Decimal, currency: str, reference_id: str, meta_data: Optional[Dict[str, Any]] = None) -> Transaction:
        """Log an investment plan purchase transaction."""
        return TransactionService.create_transaction(
            user=user,
            type='PLAN_PURCHASE',
            currency=currency,
            amount=amount,
            reference_id=reference_id,
            meta_data=meta_data,
            status='SUCCESS',
            update_wallet=True
        )
    
    @staticmethod
    def log_breakdown_refund(user: User, amount: Decimal, currency: str, reference_id: str, meta_data: Optional[Dict[str, Any]] = None) -> Transaction:
        """Log an investment breakdown refund transaction."""
        return TransactionService.create_transaction(
            user=user,
            type='BREAKDOWN_REFUND',
            currency=currency,
            amount=amount,
            reference_id=reference_id,
            meta_data=meta_data,
            status='SUCCESS',
            update_wallet=True
        )
