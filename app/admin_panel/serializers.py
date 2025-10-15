from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from app.kyc.models import KYCDocument
from app.wallet.models import INRWallet, USDTWallet, WalletTransaction
from app.investment.models import InvestmentPlan, Investment
from app.withdrawals.models import Withdrawal
from app.referral.models import Referral, ReferralMilestone
from .models import Announcement, AdminActionLog

User = get_user_model()


class DashboardSummarySerializer(serializers.Serializer):
    """Serializer for admin dashboard summary statistics."""
    
    # User statistics
    total_users = serializers.IntegerField()
    verified_users = serializers.IntegerField()
    pending_kyc_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    
    # Wallet statistics
    total_inr_balance = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_usdt_balance = serializers.DecimalField(max_digits=20, decimal_places=6)
    total_wallets = serializers.IntegerField()
    
    # Investment statistics
    active_investments = serializers.IntegerField()
    total_investment_amount = serializers.DecimalField(max_digits=20, decimal_places=6)
    pending_roi_payments = serializers.IntegerField()
    
    # Withdrawal statistics
    pending_withdrawals = serializers.IntegerField()
    pending_withdrawal_amount = serializers.DecimalField(max_digits=20, decimal_places=6)
    
    # Referral statistics
    total_referrals = serializers.IntegerField()
    active_referral_chains = serializers.IntegerField()
    
    # Transaction statistics
    today_transactions = serializers.IntegerField()
    this_week_transactions = serializers.IntegerField()
    this_month_transactions = serializers.IntegerField()
    
    # System health
    system_status = serializers.CharField()
    last_backup = serializers.DateTimeField(allow_null=True)
    
    class Meta:
        fields = '__all__'


class UserListSerializer(serializers.ModelSerializer):
    """Serializer for listing users in admin panel."""
    
    kyc_status_display = serializers.CharField(source='get_kyc_status_display', read_only=True)
    wallet_balances = serializers.SerializerMethodField()
    last_login_display = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'phone_number',
            'is_kyc_verified', 'kyc_status', 'kyc_status_display',
            'is_active', 'is_staff', 'is_superuser', 'date_joined',
            'last_login', 'last_login_display', 'wallet_balances'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def get_wallet_balances(self, obj):
        """Get user's wallet balances."""
        try:
            # Force fresh wallet data to avoid caching issues
            inr_wallet = INRWallet.objects.get(user=obj) if hasattr(obj, 'inr_wallet') else None
            usdt_wallet = USDTWallet.objects.get(user=obj) if hasattr(obj, 'usdt_wallet') else None
            return {
                'inr': float(inr_wallet.balance) if inr_wallet else 0.0,
                'usdt': float(usdt_wallet.balance) if usdt_wallet else 0.0
            }
        except:
            return {'inr': 0.0, 'usdt': 0.0}
    
    def get_last_login_display(self, obj):
        """Format last login for display."""
        if obj.last_login:
            return obj.last_login.strftime('%Y-%m-%d %H:%M:%S')
        return 'Never'


class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed user information in admin panel."""
    
    kyc_documents = serializers.SerializerMethodField()
    wallet_details = serializers.SerializerMethodField()
    investment_summary = serializers.SerializerMethodField()
    referral_summary = serializers.SerializerMethodField()
    transaction_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'phone_number',
            'date_of_birth', 'address', 'city', 'state', 'country', 'postal_code',
            'is_kyc_verified', 'kyc_status', 'email_verified', 'phone_verified',
            'is_active', 'is_staff', 'is_superuser', 'date_joined', 'last_login',
            'kyc_documents', 'wallet_details', 'investment_summary',
            'referral_summary', 'transaction_summary'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def get_kyc_documents(self, obj):
        """Get user's KYC documents."""
        documents = obj.kyc_documents.all()
        return KYCDocumentSerializer(documents, many=True).data
    
    def get_wallet_details(self, obj):
        """Get detailed wallet information."""
        try:
            # Force fresh wallet data to avoid caching issues
            inr_wallet = INRWallet.objects.get(user=obj) if hasattr(obj, 'inr_wallet') else None
            usdt_wallet = USDTWallet.objects.get(user=obj) if hasattr(obj, 'usdt_wallet') else None
            
            return {
                'inr_wallet': {
                    'balance': float(inr_wallet.balance) if inr_wallet else 0.0,
                    'status': inr_wallet.status if inr_wallet else None,
                    'is_active': inr_wallet.is_active if inr_wallet else False
                },
                'usdt_wallet': {
                    'balance': float(usdt_wallet.balance) if usdt_wallet else 0.0,
                    'status': usdt_wallet.status if usdt_wallet else None,
                    'is_active': usdt_wallet.is_active if usdt_wallet else False,
                    'wallet_address': usdt_wallet.wallet_address if usdt_wallet else None
                }
            }
        except:
            return {'inr_wallet': {}, 'usdt_wallet': {}}
    
    def get_investment_summary(self, obj):
        """Get user's investment summary."""
        investments = obj.investments.all()
        active_investments = investments.filter(status='active')
        
        return {
            'total_investments': investments.count(),
            'active_investments': active_investments.count(),
            'total_invested': float(investments.aggregate(
                total=Sum('amount')
            )['total'] or 0.0),
            'active_invested': float(active_investments.aggregate(
                total=Sum('amount')
            )['total'] or 0.0)
        }
    
    def get_referral_summary(self, obj):
        """Get user's referral summary."""
        referrals_given = obj.referrals_given.count()
        referrals_received = obj.referrals_received.count()
        
        return {
            'referrals_given': referrals_given,
            'referrals_received': referrals_received,
            'total_referral_income': float(obj.wallet_transactions.filter(
                transaction_type='referral_bonus'
            ).aggregate(total=Sum('amount'))['total'] or 0.0)
        }
    
    def get_transaction_summary(self, obj):
        """Get user's transaction summary."""
        transactions = obj.wallet_transactions.all()
        
        return {
            'total_transactions': transactions.count(),
            'total_deposits': float(transactions.filter(
                transaction_type='deposit'
            ).aggregate(total=Sum('amount'))['total'] or 0.0),
            'total_withdrawals': float(transactions.filter(
                transaction_type='withdrawal'
            ).aggregate(total=Sum('amount'))['total'] or 0.0),
            'total_roi_credits': float(transactions.filter(
                transaction_type='roi_credit'
            ).aggregate(total=Sum('amount'))['total'] or 0.0)
        }


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user information."""
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone_number', 'date_of_birth',
            'address', 'city', 'state', 'country', 'postal_code',
            'is_active', 'is_staff', 'is_superuser'
        ]


class KYCDocumentSerializer(serializers.ModelSerializer):
    """Serializer for KYC documents."""
    
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = KYCDocument
        fields = [
            'id', 'user', 'user_email', 'document_type', 'document_type_display',
            'document_number', 'document_file', 'document_front', 'document_back',
            'status', 'status_display', 'rejection_reason', 'verified_by',
            'verified_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class KYCApprovalSerializer(serializers.Serializer):
    """Serializer for KYC approval/rejection."""
    
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    notes = serializers.CharField(required=False, allow_blank=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate that rejection_reason is provided when rejecting."""
        if data['action'] == 'reject' and not data.get('rejection_reason'):
            raise serializers.ValidationError(
                "Rejection reason is required when rejecting KYC."
            )
        return data


class WalletAdjustmentSerializer(serializers.Serializer):
    """Serializer for wallet adjustments."""
    
    action = serializers.ChoiceField(choices=['credit', 'debit', 'override'])
    amount = serializers.DecimalField(max_digits=20, decimal_places=6)
    wallet_type = serializers.ChoiceField(choices=['inr', 'usdt'])
    reason = serializers.CharField()
    reference_id = serializers.CharField(required=False, allow_blank=True)
    
    def validate_amount(self, value):
        """Validate amount is positive."""
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value


class InvestmentPlanSerializer(serializers.ModelSerializer):
    """Serializer for investment plans."""
    
    class Meta:
        model = InvestmentPlan
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class InvestmentSerializer(serializers.ModelSerializer):
    """Serializer for investments."""
    
    user_email = serializers.CharField(source='user.email', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Investment
        fields = [
            'id', 'user', 'user_email', 'plan', 'plan_name', 'amount',
            'status', 'status_display', 'start_date', 'end_date',
            'total_roi_earned', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class WithdrawalSerializer(serializers.ModelSerializer):
    """Serializer for withdrawals."""
    
    user_email = serializers.CharField(source='user.email', read_only=True)
    currency_display = serializers.CharField(source='get_currency_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payout_method_display = serializers.CharField(source='get_payout_method_display', read_only=True)
    
    class Meta:
        model = Withdrawal
        fields = [
            'id', 'user', 'user_email', 'currency', 'currency_display',
            'amount', 'fee', 'payout_method', 'payout_method_display',
            'payout_details', 'status', 'status_display', 'tx_hash',
            'chain_type', 'processed_by', 'processed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class WithdrawalApprovalSerializer(serializers.Serializer):
    """Serializer for withdrawal approval/rejection."""
    
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    notes = serializers.CharField(required=False, allow_blank=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)
    tx_hash = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate required fields based on action."""
        if data['action'] == 'reject' and not data.get('rejection_reason'):
            raise serializers.ValidationError(
                "Rejection reason is required when rejecting withdrawal."
            )
        return data


class ReferralSerializer(serializers.ModelSerializer):
    """Serializer for referrals."""
    
    user_email = serializers.CharField(source='user.email', read_only=True)
    referred_user_email = serializers.CharField(source='referred_user.email', read_only=True)
    
    class Meta:
        model = Referral
        fields = [
            'id', 'user', 'user_email', 'referred_user', 'referred_user_email',
            'level', 'referrer', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ReferralMilestoneSerializer(serializers.ModelSerializer):
    """Serializer for referral milestones."""
    
    class Meta:
        model = ReferralMilestone
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for transactions."""
    
    user_email = serializers.CharField(source='user.email', read_only=True)
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    wallet_type_display = serializers.CharField(source='get_wallet_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'user', 'user_email', 'transaction_type', 'transaction_type_display',
            'wallet_type', 'wallet_type_display', 'chain_type', 'amount',
            'balance_before', 'balance_after', 'status', 'status_display',
            'reference_id', 'description', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AnnouncementSerializer(serializers.ModelSerializer):
    """Serializer for announcements."""
    
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    target_group_display = serializers.CharField(source='get_target_group_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Announcement
        fields = [
            'id', 'title', 'message', 'target_group', 'target_group_display',
            'status', 'status_display', 'priority', 'display_from', 'display_until',
            'created_by', 'created_by_email', 'is_pinned', 'view_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'view_count']


class AnnouncementCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating announcements."""
    
    class Meta:
        model = Announcement
        fields = [
            'title', 'message', 'target_group', 'status', 'priority',
            'display_from', 'display_until', 'is_pinned'
        ]
    
    def create(self, validated_data):
        """Set the created_by field to the current user."""
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class AdminActionLogSerializer(serializers.ModelSerializer):
    """Serializer for admin action logs."""
    
    admin_user_email = serializers.CharField(source='admin_user.email', read_only=True)
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)
    target_user_email = serializers.CharField(source='target_user.email', read_only=True)
    
    class Meta:
        model = AdminActionLog
        fields = [
            'id', 'admin_user', 'admin_user_email', 'action_type', 'action_type_display',
            'action_description', 'target_user', 'target_user_email', 'target_model',
            'target_id', 'ip_address', 'user_agent', 'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class BulkUserActionSerializer(serializers.Serializer):
    """Serializer for bulk user actions."""
    
    user_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=100
    )
    action = serializers.ChoiceField(choices=[
        'activate', 'deactivate', 'verify_kyc', 'reject_kyc', 'block', 'unblock'
    ])
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_user_ids(self, value):
        """Validate that all user IDs exist."""
        existing_users = User.objects.filter(id__in=value)
        if len(existing_users) != len(value):
            raise serializers.ValidationError("Some user IDs do not exist.")
        return value


class ExportTransactionsSerializer(serializers.Serializer):
    """Serializer for transaction export requests."""
    
    format = serializers.ChoiceField(choices=['csv', 'pdf', 'excel'])
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    transaction_type = serializers.ChoiceField(
        choices=[choice[0] for choice in WalletTransaction.TRANSACTION_TYPE_CHOICES],
        required=False
    )
    wallet_type = serializers.ChoiceField(
        choices=[choice[0] for choice in WalletTransaction.WALLET_TYPE_CHOICES],
        required=False
    )
    user_id = serializers.UUIDField(required=False)
    
    def validate(self, data):
        """Validate date range."""
        if data.get('date_from') and data.get('date_to'):
            if data['date_from'] > data['date_to']:
                raise serializers.ValidationError(
                    "Date from must be before date to."
                )
        return data
