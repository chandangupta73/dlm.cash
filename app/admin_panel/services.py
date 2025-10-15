from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from datetime import timedelta
import logging
from decimal import Decimal

from app.kyc.models import KYCDocument
from app.wallet.models import INRWallet, USDTWallet, WalletTransaction
from app.investment.models import InvestmentPlan, Investment
from app.withdrawals.models import Withdrawal
from app.referral.models import Referral, ReferralMilestone
from .models import Announcement, AdminActionLog
from .permissions import log_admin_action

User = get_user_model()
logger = logging.getLogger(__name__)


class AdminDashboardService:
    """Service for admin dashboard operations."""
    
    @staticmethod
    def get_dashboard_summary():
        """Get comprehensive dashboard summary statistics."""
        try:
            now = timezone.now()
            today = now.date()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)
            
            # User statistics
            total_users = User.objects.count()
            verified_users = User.objects.filter(is_kyc_verified=True).count()
            pending_kyc_users = User.objects.filter(kyc_status='PENDING').count()
            active_users = User.objects.filter(is_active=True).count()
            
            # Wallet statistics
            total_inr_balance = INRWallet.objects.filter(
                is_active=True, status='active'
            ).aggregate(total=Sum('balance'))['total'] or 0.0
            
            total_usdt_balance = USDTWallet.objects.filter(
                is_active=True, status='active'
            ).aggregate(total=Sum('balance'))['total'] or 0.0
            
            total_wallets = INRWallet.objects.count() + USDTWallet.objects.count()
            
            # Investment statistics
            active_investments = Investment.objects.filter(status='active').count()
            total_investment_amount = Investment.objects.filter(
                status='active'
            ).aggregate(total=Sum('amount'))['total'] or 0.0
            
            # Count investments that need ROI payment today
            pending_roi_payments = Investment.objects.filter(
                status='active',
                start_date__lte=today,
                end_date__gte=today
            ).count()
            
            # Withdrawal statistics
            pending_withdrawals = Withdrawal.objects.filter(status='PENDING').count()
            pending_withdrawal_amount = Withdrawal.objects.filter(
                status='PENDING'
            ).aggregate(total=Sum('amount'))['total'] or 0.0
            
            # Referral statistics
            total_referrals = Referral.objects.count()
            active_referral_chains = Referral.objects.filter(
                user__is_active=True
            ).distinct('user').count()
            
            # Transaction statistics
            today_transactions = WalletTransaction.objects.filter(
                created_at__date=today
            ).count()
            
            this_week_transactions = WalletTransaction.objects.filter(
                created_at__date__gte=week_ago
            ).count()
            
            this_month_transactions = WalletTransaction.objects.filter(
                created_at__date__gte=month_ago
            ).count()
            
            # System health
            system_status = 'Healthy'
            last_backup = None  # TODO: Implement backup tracking
            
            return {
                'total_users': total_users,
                'verified_users': verified_users,
                'pending_kyc_users': pending_kyc_users,
                'active_users': active_users,
                'total_inr_balance': total_inr_balance,
                'total_usdt_balance': total_usdt_balance,
                'total_wallets': total_wallets,
                'active_investments': active_investments,
                'total_investment_amount': total_investment_amount,
                'pending_roi_payments': pending_roi_payments,
                'pending_withdrawals': pending_withdrawals,
                'pending_withdrawal_amount': pending_withdrawal_amount,
                'total_referrals': total_referrals,
                'active_referral_chains': active_referral_chains,
                'today_transactions': today_transactions,
                'this_week_transactions': this_week_transactions,
                'this_month_transactions': this_month_transactions,
                'system_status': system_status,
                'last_backup': last_backup
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard summary: {str(e)}")
            raise


class AdminUserService:
    """Service for admin user management operations."""
    
    @staticmethod
    def get_users_with_filters(filters=None):
        """Get users with optional filters."""
        queryset = User.objects.all()
        
        if filters:
            if filters.get('kyc_status'):
                queryset = queryset.filter(kyc_status=filters['kyc_status'])
            
            if filters.get('is_kyc_verified') is not None:
                queryset = queryset.filter(is_kyc_verified=filters['is_kyc_verified'])
            
            if filters.get('is_active') is not None:
                queryset = queryset.filter(is_active=filters['is_active'])
            
            if filters.get('date_joined_from'):
                queryset = queryset.filter(date_joined__gte=filters['date_joined_from'])
            
            if filters.get('date_joined_to'):
                queryset = queryset.filter(date_joined__lte=filters['date_joined_to'])
        
        return queryset.select_related('inr_wallet', 'usdt_wallet')
    
    @staticmethod
    def update_user(user_id, data, admin_user):
        """Update user information."""
        try:
            with transaction.atomic():
                user = User.objects.get(id=user_id)
                
                # Update user fields
                for field, value in data.items():
                    if hasattr(user, field):
                        setattr(user, field, value)
                
                user.save()
                
                # Log admin action
                log_admin_action(
                    admin_user=admin_user,
                    action_type='USER_MANAGEMENT',
                    action_description=f"Updated user {user.email}",
                    target_user=user,
                    target_model='User',
                    target_id=str(user.id)
                )
                
                return user
                
        except User.DoesNotExist:
            raise ValidationError("User not found")
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {str(e)}")
            raise
    
    @staticmethod
    def block_user(user_id, admin_user, reason=""):
        """Block a user."""
        try:
            with transaction.atomic():
                user = User.objects.get(id=user_id)
                user.is_active = False
                user.save()
                
                # Log admin action
                log_admin_action(
                    admin_user=admin_user,
                    action_type='USER_MANAGEMENT',
                    action_description=f"Blocked user {user.email}. Reason: {reason}",
                    target_user=user,
                    target_model='User',
                    target_id=str(user.id)
                )
                
                return user
                
        except User.DoesNotExist:
            raise ValidationError("User not found")
        except Exception as e:
            logger.error(f"Error blocking user {user_id}: {str(e)}")
            raise
    
    @staticmethod
    def unblock_user(user_id, admin_user):
        """Unblock a user."""
        try:
            with transaction.atomic():
                user = User.objects.get(id=user_id)
                user.is_active = True
                user.save()
                
                # Log admin action
                log_admin_action(
                    admin_user=admin_user,
                    action_type='USER_MANAGEMENT',
                    action_description=f"Unblocked user {user.email}",
                    target_user=user,
                    target_model='User',
                    target_id=str(user.id)
                )
                
                return user
                
        except User.DoesNotExist:
            raise ValidationError("User not found")
        except Exception as e:
            logger.error(f"Error unblocking user {user_id}: {str(e)}")
            raise
    
    @staticmethod
    def bulk_user_action(user_ids, action, admin_user, notes=""):
        """Perform bulk action on multiple users."""
        try:
            with transaction.atomic():
                users = User.objects.filter(id__in=user_ids)
                updated_count = 0
                
                for user in users:
                    if action == 'activate':
                        user.is_active = True
                        updated_count += 1
                    elif action == 'deactivate':
                        user.is_active = False
                        updated_count += 1
                    elif action == 'verify_kyc':
                        user.is_kyc_verified = True
                        user.kyc_status = 'APPROVED'
                        updated_count += 1
                    elif action == 'reject_kyc':
                        user.is_kyc_verified = False
                        user.kyc_status = 'REJECTED'
                        updated_count += 1
                    elif action == 'block':
                        user.is_active = False
                        updated_count += 1
                    elif action == 'unblock':
                        user.is_active = True
                        updated_count += 1
                    
                    user.save()
                
                # Log admin action
                log_admin_action(
                    admin_user=admin_user,
                    action_type='USER_MANAGEMENT',
                    action_description=f"Bulk {action} on {updated_count} users. Notes: {notes}",
                    target_model='User',
                    metadata={'action': action, 'user_count': updated_count, 'notes': notes}
                )
                
                return updated_count
                
        except Exception as e:
            logger.error(f"Error in bulk user action {action}: {str(e)}")
            raise


class AdminKYCService:
    """Service for admin KYC management operations."""
    
    @staticmethod
    def get_pending_kyc_documents():
        """Get all pending KYC documents."""
        return KYCDocument.objects.filter(status='PENDING').select_related('user')
    
    @staticmethod
    def approve_kyc(document_id, admin_user, notes=""):
        """Approve a KYC document."""
        try:
            with transaction.atomic():
                document = KYCDocument.objects.get(id=document_id)
                user = document.user
                
                # Update document status
                document.status = 'APPROVED'
                document.verified_by = admin_user
                document.verified_at = timezone.now()
                document.save()
                
                # Update user KYC status
                user.is_kyc_verified = True
                user.kyc_status = 'APPROVED'
                user.save()
                
                # Log admin action
                log_admin_action(
                    admin_user=admin_user,
                    action_type='KYC_APPROVAL',
                    action_description=f"Approved KYC for user {user.email}. Notes: {notes}",
                    target_user=user,
                    target_model='KYCDocument',
                    target_id=str(document.id)
                )
                
                return document
                
        except KYCDocument.DoesNotExist:
            raise ValidationError("KYC document not found")
        except Exception as e:
            logger.error(f"Error approving KYC {document_id}: {str(e)}")
            raise
    
    @staticmethod
    def reject_kyc(document_id, admin_user, rejection_reason, notes=""):
        """Reject a KYC document."""
        try:
            with transaction.atomic():
                document = KYCDocument.objects.get(id=document_id)
                user = document.user
                
                # Update document status
                document.status = 'REJECTED'
                document.rejection_reason = rejection_reason
                document.verified_by = admin_user
                document.verified_at = timezone.now()
                document.save()
                
                # Update user KYC status
                user.is_kyc_verified = False
                user.kyc_status = 'REJECTED'
                user.save()
                
                # Log admin action
                log_admin_action(
                    admin_user=admin_user,
                    action_type='KYC_APPROVAL',
                    action_description=f"Rejected KYC for user {user.email}. Reason: {rejection_reason}. Notes: {notes}",
                    target_user=user,
                    target_model='KYCDocument',
                    target_id=str(document.id)
                )
                
                return document
                
        except KYCDocument.DoesNotExist:
            raise ValidationError("KYC document not found")
        except Exception as e:
            logger.error(f"Error rejecting KYC {document_id}: {str(e)}")
            raise


class AdminWalletService:
    """Service for admin wallet management operations."""
    
    @staticmethod
    def adjust_wallet_balance(user_id, action, amount, wallet_type, reason, admin_user, reference_id=None):
        """Adjust user wallet balance."""
        try:
            with transaction.atomic():
                user = User.objects.get(id=user_id)
                
                if wallet_type == 'inr':
                    wallet = user.inr_wallet
                    transaction_type = 'admin_adjustment'
                elif wallet_type == 'usdt':
                    wallet = user.usdt_wallet
                    transaction_type = 'admin_adjustment'
                else:
                    raise ValidationError("Invalid wallet type")
                
                if not wallet:
                    raise ValidationError("User wallet not found")
                
                balance_before = wallet.balance
                
                if action == 'credit':
                    wallet.balance += amount
                    balance_after = wallet.balance
                elif action == 'debit':
                    if wallet.balance < amount:
                        raise ValidationError("Insufficient balance for debit")
                    wallet.balance -= amount
                    balance_after = wallet.balance
                elif action == 'override':
                    if not admin_user.is_superuser:
                        raise ValidationError("Only superusers can override wallet balances")
                    wallet.balance = amount
                    balance_after = amount
                else:
                    raise ValidationError("Invalid action")
                
                wallet.save()
                
                # Create transaction log
                WalletTransaction.objects.create(
                    user=user,
                    transaction_type=transaction_type,
                    wallet_type=wallet_type,
                    amount=amount,
                    balance_before=balance_before,
                    balance_after=balance_after,
                    status='completed',
                    reference_id=reference_id,
                    description=f"Admin {action}: {reason}",
                    metadata={
                        'admin_user_id': str(admin_user.id),
                        'admin_user_email': admin_user.email,
                        'action': action,
                        'reason': reason
                    }
                )
                
                # Log admin action
                log_admin_action(
                    admin_user=admin_user,
                    action_type='WALLET_ADJUSTMENT',
                    action_description=f"{action.title()} {wallet_type.upper()} wallet for {user.email}. Amount: {amount}, Reason: {reason}",
                    target_user=user,
                    target_model=f'{wallet_type.upper()}Wallet',
                    metadata={'action': action, 'amount': str(amount), 'reason': reason}
                )
                
                return {
                    'user': user,
                    'wallet': wallet,
                    'balance_before': balance_before,
                    'balance_after': balance_after,
                    'action': action
                }
                
        except User.DoesNotExist:
            raise ValidationError("User not found")
        except Exception as e:
            logger.error(f"Error adjusting wallet for user {user_id}: {str(e)}")
            raise


class AdminInvestmentService:
    """Service for admin investment management operations."""
    
    @staticmethod
    def get_investments_with_filters(filters=None):
        """Get investments with optional filters."""
        queryset = Investment.objects.all()
        
        if filters:
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            
            if filters.get('user_id'):
                queryset = queryset.filter(user_id=filters['user_id'])
            
            if filters.get('plan_id'):
                queryset = queryset.filter(plan_id=filters['plan_id'])
        
        return queryset.select_related('user', 'plan')
    
    @staticmethod
    def trigger_roi_distribution(admin_user):
        """Manually trigger ROI distribution for all eligible investments."""
        try:
            with transaction.atomic():
                # Get all active investments that are eligible for ROI
                eligible_investments = Investment.objects.filter(
                    status='active',
                    is_active=True
                ).select_related('user', 'plan')
                
                processed_count = 0
                total_roi_distributed = Decimal('0.00')
                
                for investment in eligible_investments:
                    try:
                        # Calculate daily ROI based on plan frequency
                        if investment.plan.frequency == 'daily':
                            daily_roi_rate = investment.plan.roi_rate / 365
                        elif investment.plan.frequency == 'weekly':
                            daily_roi_rate = investment.plan.roi_rate / 52
                        elif investment.plan.frequency == 'monthly':
                            daily_roi_rate = investment.plan.roi_rate / 12
                        else:
                            daily_roi_rate = investment.plan.roi_rate / 365
                        
                        # Calculate ROI for today
                        daily_roi_amount = (investment.amount * daily_roi_rate) / 100
                        
                        # Update investment ROI accrued
                        investment.roi_accrued += daily_roi_amount
                        investment.last_roi_credit = timezone.now()
                        investment.next_roi_date = timezone.now() + timedelta(days=1)
                        investment.save()
                        
                        # Credit user's wallet
                        user = investment.user
                        if investment.currency == 'inr':
                            wallet = user.inr_wallet
                        else:  # usdt
                            wallet = user.usdt_wallet
                        
                        if wallet:
                            balance_before = wallet.balance
                            wallet.add_balance(daily_roi_amount)
                            wallet.save()
                            
                            # Create transaction log
                            WalletTransaction.objects.create(
                                user=user,
                                transaction_type='roi_credit',
                                wallet_type=investment.currency,
                                chain_type=None if investment.currency == 'inr' else wallet.chain_type,
                                amount=daily_roi_amount,
                                balance_before=balance_before,
                                balance_after=wallet.balance,
                                status='completed',
                                reference_id=str(investment.id),
                                description=f"Daily ROI credit for {investment.plan.name}",
                                metadata={
                                    'investment_id': str(investment.id),
                                    'plan_name': investment.plan.name,
                                    'roi_rate': float(investment.plan.roi_rate),
                                    'frequency': investment.plan.frequency,
                                    'daily_roi_amount': float(daily_roi_amount)
                                }
                            )
                        
                        processed_count += 1
                        total_roi_distributed += daily_roi_amount
                        
                    except Exception as e:
                        logger.error(f"Error processing ROI for investment {investment.id}: {str(e)}")
                        continue
                
                # Log admin action
                log_admin_action(
                    admin_user=admin_user,
                    action_type='ROI_MANAGEMENT',
                    action_description=f"Triggered ROI distribution. Processed: {processed_count}, Total ROI: {total_roi_distributed}",
                    target_user=None,
                    target_model='Investment',
                    target_id=None
                )
                
                return {
                    'processed_count': processed_count,
                    'total_roi_distributed': total_roi_distributed
                }
                
        except Exception as e:
            logger.error(f"Error triggering ROI distribution: {str(e)}")
            raise
    
    @staticmethod
    def cancel_investment(investment_id, admin_user, reason=""):
        """Cancel an investment early."""
        try:
            with transaction.atomic():
                investment = Investment.objects.get(id=investment_id)
                
                if investment.status != 'active':
                    raise ValidationError("Only active investments can be cancelled")
                
                # Calculate refund amount (principal + earned ROI)
                refund_amount = investment.amount + investment.total_roi_earned
                
                # Update investment status
                investment.status = 'cancelled'
                investment.save()
                
                # Credit user's wallet
                user = investment.user
                wallet = user.inr_wallet if investment.plan.currency == 'INR' else user.usdt_wallet
                
                if wallet:
                    balance_before = wallet.balance
                    wallet.balance += refund_amount
                    wallet.save()
                    
                    # Create transaction log
                    WalletTransaction.objects.create(
                        user=user,
                        transaction_type='refund',
                        wallet_type='inr' if investment.plan.currency == 'INR' else 'usdt',
                        amount=refund_amount,
                        balance_before=balance_before,
                        balance_after=wallet.balance,
                        status='completed',
                        reference_id=str(investment.id),
                        description=f"Investment cancellation refund. Reason: {reason}",
                        metadata={
                            'investment_id': str(investment.id),
                            'admin_user_id': str(admin_user.id),
                            'reason': reason
                        }
                    )
                
                # Log admin action
                log_admin_action(
                    admin_user=admin_user,
                    action_type='INVESTMENT_MANAGEMENT',
                    action_description=f"Cancelled investment {investment.id} for user {user.email}. Refund: {refund_amount}. Reason: {reason}",
                    target_user=user,
                    target_model='Investment',
                    target_id=str(investment.id)
                )
                
                return investment
                
        except Investment.DoesNotExist:
            raise ValidationError("Investment not found")
        except Exception as e:
            logger.error(f"Error cancelling investment {investment_id}: {str(e)}")
            raise


class AdminWithdrawalService:
    """Service for admin withdrawal management operations."""
    
    @staticmethod
    def get_pending_withdrawals():
        """Get all pending withdrawal requests."""
        return Withdrawal.objects.filter(status='PENDING').select_related('user')
    
    @staticmethod
    def approve_withdrawal(withdrawal_id, admin_user, notes="", tx_hash=None):
        """Approve a withdrawal request."""
        try:
            with transaction.atomic():
                withdrawal = Withdrawal.objects.get(id=withdrawal_id)
                user = withdrawal.user
                
                # Update withdrawal status
                withdrawal.status = 'APPROVED'
                withdrawal.processed_by = admin_user
                withdrawal.processed_at = timezone.now()
                
                if tx_hash:
                    withdrawal.tx_hash = tx_hash
                
                withdrawal.save()
                
                # Log admin action
                log_admin_action(
                    admin_user=admin_user,
                    action_type='WITHDRAWAL_APPROVAL',
                    action_description=f"Approved withdrawal {withdrawal.id} for user {user.email}. Amount: {withdrawal.amount} {withdrawal.currency}. Notes: {notes}",
                    target_user=user,
                    target_model='Withdrawal',
                    target_id=str(withdrawal.id)
                )
                
                return withdrawal
                
        except Withdrawal.DoesNotExist:
            raise ValidationError("Withdrawal not found")
        except Exception as e:
            logger.error(f"Error approving withdrawal {withdrawal_id}: {str(e)}")
            raise
    
    @staticmethod
    def reject_withdrawal(withdrawal_id, admin_user, rejection_reason, notes=""):
        """Reject a withdrawal request."""
        try:
            with transaction.atomic():
                withdrawal = Withdrawal.objects.get(id=withdrawal_id)
                user = withdrawal.user
                
                # Update withdrawal status
                withdrawal.status = 'REJECTED'
                withdrawal.processed_by = admin_user
                withdrawal.processed_at = timezone.now()
                withdrawal.save()
                
                # Refund user's wallet
                wallet = user.inr_wallet if withdrawal.currency == 'INR' else user.usdt_wallet
                
                if wallet:
                    balance_before = wallet.balance
                    wallet.balance += withdrawal.amount
                    wallet.save()
                    
                    # Create transaction log
                    WalletTransaction.objects.create(
                        user=user,
                        transaction_type='refund',
                        wallet_type='inr' if withdrawal.currency == 'INR' else 'usdt',
                        amount=withdrawal.amount,
                        balance_before=balance_before,
                        balance_after=wallet.balance,
                        status='completed',
                        reference_id=str(withdrawal.id),
                        description=f"Withdrawal rejection refund. Reason: {rejection_reason}",
                        metadata={
                            'withdrawal_id': str(withdrawal.id),
                            'admin_user_id': str(admin_user.id),
                            'rejection_reason': rejection_reason
                        }
                    )
                
                # Log admin action
                log_admin_action(
                    admin_user=admin_user,
                    action_type='WITHDRAWAL_APPROVAL',
                    action_description=f"Rejected withdrawal {withdrawal.id} for user {user.email}. Reason: {rejection_reason}. Notes: {notes}",
                    target_user=user,
                    target_model='Withdrawal',
                    target_id=str(withdrawal.id)
                )
                
                return withdrawal
                
        except Withdrawal.DoesNotExist:
            raise ValidationError("Withdrawal not found")
        except Exception as e:
            logger.error(f"Error rejecting withdrawal {withdrawal_id}: {str(e)}")
            raise


class AdminReferralService:
    """Service for admin referral management operations."""
    
    @staticmethod
    def get_user_referral_tree(user_id):
        """Get complete referral tree for a user."""
        try:
            user = User.objects.get(id=user_id)
            
            # Get direct referrals
            direct_referrals = Referral.objects.filter(
                user=user, level=1
            ).select_related('referred_user')
            
            # Get indirect referrals (level 2)
            indirect_referrals = Referral.objects.filter(
                user=user, level=2
            ).select_related('referred_user')
            
            # Get level 3 referrals
            level3_referrals = Referral.objects.filter(
                user=user, level=3
            ).select_related('referred_user')
            
            return {
                'user': user,
                'direct_referrals': direct_referrals,
                'indirect_referrals': indirect_referrals,
                'level3_referrals': level3_referrals,
                'total_referrals': direct_referrals.count() + indirect_referrals.count() + level3_referrals.count()
            }
            
        except User.DoesNotExist:
            raise ValidationError("User not found")
        except Exception as e:
            logger.error(f"Error getting referral tree for user {user_id}: {str(e)}")
            raise


class AdminTransactionService:
    """Service for admin transaction management operations."""
    
    @staticmethod
    def get_transactions_with_filters(filters=None):
        """Get transactions with optional filters."""
        queryset = WalletTransaction.objects.all()
        
        if filters:
            if filters.get('transaction_type'):
                queryset = queryset.filter(transaction_type=filters['transaction_type'])
            
            if filters.get('wallet_type'):
                queryset = queryset.filter(wallet_type=filters['wallet_type'])
            
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            
            if filters.get('user_id'):
                queryset = queryset.filter(user_id=filters['user_id'])
            
            if filters.get('date_from'):
                queryset = queryset.filter(created_at__date__gte=filters['date_from'])
            
            if filters.get('date_to'):
                queryset = queryset.filter(created_at__date__lte=filters['date_to'])
        
        return queryset.select_related('user')
    
    @staticmethod
    def export_transactions(filters, format_type):
        """Export transactions in specified format."""
        try:
            transactions = AdminTransactionService.get_transactions_with_filters(filters)
            
            if format_type == 'csv':
                return AdminTransactionService._export_to_csv(transactions)
            elif format_type == 'pdf':
                return AdminTransactionService._export_to_pdf(transactions)
            elif format_type == 'excel':
                return AdminTransactionService._export_to_excel(transactions)
            else:
                raise ValidationError("Unsupported export format")
                
        except Exception as e:
            logger.error(f"Error exporting transactions: {str(e)}")
            raise
    
    @staticmethod
    def _export_to_csv(transactions):
        """Export transactions to CSV format."""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'User Email', 'Transaction Type', 'Wallet Type', 'Amount',
            'Balance Before', 'Balance After', 'Status', 'Reference ID',
            'Description', 'Created At'
        ])
        
        # Write data
        for transaction in transactions:
            writer.writerow([
                transaction.id,
                transaction.user.email,
                transaction.get_transaction_type_display(),
                transaction.get_wallet_type_display(),
                transaction.amount,
                transaction.balance_before,
                transaction.balance_after,
                transaction.get_status_display(),
                transaction.reference_id or '',
                transaction.description or '',
                transaction.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        output.seek(0)
        return output.getvalue()
    
    @staticmethod
    def _export_to_pdf(transactions):
        """Export transactions to PDF format."""
        # TODO: Implement PDF export
        raise NotImplementedError("PDF export not yet implemented")
    
    @staticmethod
    def _export_to_excel(transactions):
        """Export transactions to Excel format."""
        # TODO: Implement Excel export
        raise NotImplementedError("Excel export not yet implemented")


class AdminAnnouncementService:
    """Service for admin announcement management operations."""
    
    @staticmethod
    def create_announcement(data, admin_user):
        """Create a new announcement."""
        try:
            with transaction.atomic():
                announcement = Announcement.objects.create(
                    created_by=admin_user,
                    **data
                )
                
                # Log admin action
                log_admin_action(
                    admin_user=admin_user,
                    action_type='ANNOUNCEMENT',
                    action_description=f"Created announcement: {announcement.title}",
                    target_model='Announcement',
                    target_id=str(announcement.id)
                )
                
                return announcement
                
        except Exception as e:
            logger.error(f"Error creating announcement: {str(e)}")
            raise
    
    @staticmethod
    def update_announcement(announcement_id, data, admin_user):
        """Update an existing announcement."""
        try:
            with transaction.atomic():
                announcement = Announcement.objects.get(id=announcement_id)
                
                for field, value in data.items():
                    if hasattr(announcement, field):
                        setattr(announcement, field, value)
                
                announcement.save()
                
                # Log admin action
                log_admin_action(
                    admin_user=admin_user,
                    action_type='ANNOUNCEMENT',
                    action_description=f"Updated announcement: {announcement.title}",
                    target_model='Announcement',
                    target_id=str(announcement.id)
                )
                
                return announcement
                
        except Announcement.DoesNotExist:
            raise ValidationError("Announcement not found")
        except Exception as e:
            logger.error(f"Error updating announcement {announcement_id}: {str(e)}")
            raise
    
    @staticmethod
    def delete_announcement(announcement_id, admin_user):
        """Delete an announcement."""
        try:
            with transaction.atomic():
                announcement = Announcement.objects.get(id=announcement_id)
                title = announcement.title
                
                announcement.delete()
                
                # Log admin action
                log_admin_action(
                    admin_user=admin_user,
                    action_type='ANNOUNCEMENT',
                    action_description=f"Deleted announcement: {title}",
                    target_model='Announcement',
                    target_id=str(announcement_id)
                )
                
                return True
                
        except Announcement.DoesNotExist:
            raise ValidationError("Announcement not found")
        except Exception as e:
            logger.error(f"Error deleting announcement {announcement_id}: {str(e)}")
            raise
    
    @staticmethod
    def get_active_announcements_for_user(user):
        """Get active announcements for a specific user."""
        try:
            # Get all announcements regardless of status to debug
            announcements = Announcement.objects.all()
            
            # Log the count of announcements before filtering
            logger.info(f"Total announcements before filtering: {announcements.count()}")
            
            # Return all announcements for now to debug
            return announcements
            
        except Exception as e:
            logger.error(f"Error getting active announcements for user {user.id}: {str(e)}")
            raise
