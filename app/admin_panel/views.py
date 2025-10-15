from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

# Import models from other apps
from app.users.models import User
from app.kyc.models import KYCDocument
from app.wallet.models import INRWallet, USDTWallet, WalletTransaction, DepositRequest
from app.withdrawals.models import Withdrawal
from app.investment.models import InvestmentPlan, Investment, BreakdownRequest
from app.investment.serializers import InvestmentPlanSerializer, BreakdownRequestAdminSerializer
from app.referral.models import Referral, ReferralMilestone
from app.transactions.models import Transaction

# Import models from admin_panel app
from .models import Announcement, AdminActionLog

from .permissions import (
    IsAdminUser, IsSuperUser, AdminActionPermission, WalletOverridePermission,
    KYCApprovalPermission, WithdrawalApprovalPermission, InvestmentManagementPermission,
    ReferralManagementPermission, AnnouncementPermission, UserManagementPermission,
    TransactionLogPermission
)
from .serializers import (
    DashboardSummarySerializer, UserListSerializer, UserDetailSerializer, UserUpdateSerializer,
    KYCDocumentSerializer, KYCApprovalSerializer, WalletAdjustmentSerializer,
    InvestmentSerializer, WithdrawalSerializer,
    WithdrawalApprovalSerializer, ReferralSerializer, ReferralMilestoneSerializer,
    TransactionSerializer, AnnouncementSerializer, AnnouncementCreateSerializer,
    AdminActionLogSerializer, BulkUserActionSerializer, ExportTransactionsSerializer
)
from .services import (
    AdminDashboardService, AdminUserService, AdminKYCService, AdminWalletService,
    AdminInvestmentService, AdminWithdrawalService, AdminReferralService,
    AdminTransactionService, AdminAnnouncementService
)

# User model is now imported from app.users.models


class AdminDashboardView(generics.GenericAPIView):
    """Admin dashboard overview with summary statistics."""
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = DashboardSummarySerializer
    
    def get(self, request):
        """Get dashboard summary statistics."""
        try:
            summary = AdminDashboardService.get_dashboard_summary()
            serializer = self.get_serializer(summary)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminUserViewSet(viewsets.ModelViewSet):
    """ViewSet for admin user management."""
    
    permission_classes = [IsAuthenticated, UserManagementPermission]
    serializer_class = UserListSerializer
    queryset = User.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['kyc_status', 'is_kyc_verified', 'is_active', 'is_staff', 'is_superuser']
    search_fields = ['email', 'username', 'first_name', 'last_name', 'phone_number']
    ordering_fields = ['created_at', 'last_login', 'email', 'username']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'retrieve':
            return UserDetailSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserListSerializer
    
    def get_queryset(self):
        """Return filtered queryset."""
        # Force fresh queryset to avoid caching issues after updates
        queryset = User.objects.all()
        
        # Apply additional filters
        kyc_status = self.request.query_params.get('kyc_status')
        if kyc_status:
            queryset = queryset.filter(kyc_status=kyc_status)
        
        date_from = self.request.query_params.get('date_joined_from')
        if date_from:
            queryset = queryset.filter(date_joined__date__gte=date_from)
        
        date_to = self.request.query_params.get('date_joined_to')
        if date_to:
            queryset = queryset.filter(date_joined__date__lte=date_to)
        
        return queryset.select_related('inr_wallet', 'usdt_wallet')
    
    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        """Block a user."""
        try:
            user = self.get_object()
            reason = request.data.get('reason', '')
            
            AdminUserService.block_user(user.id, request.user, reason)
            
            return Response({
                'message': f'User {user.email} has been blocked.',
                'reason': reason
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        """Unblock a user."""
        try:
            user = self.get_object()
            AdminUserService.unblock_user(user.id, request.user)
            
            return Response({
                'message': f'User {user.email} has been unblocked.'
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """Perform bulk action on multiple users."""
        serializer = BulkUserActionSerializer(data=request.data)
        if serializer.is_valid():
            try:
                action = serializer.validated_data['action']
                user_ids = serializer.validated_data['user_ids']
                notes = serializer.validated_data.get('notes', '')
                
                updated_count = AdminUserService.bulk_user_action(
                    user_ids, action, request.user, notes
                )
                
                return Response({
                    'message': f'Successfully processed {updated_count} users.',
                    'action': action,
                    'updated_count': updated_count
                })
            except Exception as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(
            serializer.errors, 
            status=status.HTTP_400_BAD_REQUEST
        )


class AdminKYCViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for admin KYC management."""
    
    permission_classes = [IsAuthenticated, KYCApprovalPermission]
    serializer_class = KYCDocumentSerializer
    queryset = KYCDocument.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'document_type']
    search_fields = ['user__email', 'user__username', 'document_number']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return filtered queryset."""
        queryset = super().get_queryset()
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.select_related('user', 'verified_by')
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a KYC document."""
        serializer = KYCApprovalSerializer(data=request.data)
        if serializer.is_valid():
            try:
                document = self.get_object()
                notes = serializer.validated_data.get('notes', '')
                
                AdminKYCService.approve_kyc(document.id, request.user, notes)
                
                return Response({
                    'message': f'KYC for {document.user.email} has been approved.',
                    'notes': notes
                })
            except Exception as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(
            serializer.errors, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a KYC document."""
        serializer = KYCApprovalSerializer(data=request.data)
        if serializer.is_valid():
            try:
                document = self.get_object()
                rejection_reason = serializer.validated_data.get('rejection_reason', '')
                notes = serializer.validated_data.get('notes', '')
                
                AdminKYCService.reject_kyc(
                    document.id, request.user, rejection_reason, notes
                )
                
                return Response({
                    'message': f'KYC for {document.user.email} has been rejected.',
                    'rejection_reason': rejection_reason,
                    'notes': notes
                })
            except Exception as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(
            serializer.errors, 
            status=status.HTTP_400_BAD_REQUEST
        )


class AdminWalletViewSet(viewsets.GenericViewSet):
    """ViewSet for admin wallet management."""
    
    permission_classes = [IsAuthenticated, AdminActionPermission]
    
    @action(detail=False, methods=['post'])
    def adjust_balance(self, request):
        """Adjust user wallet balance."""
        serializer = WalletAdjustmentSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user_id = request.data.get('user_id')
                action = serializer.validated_data['action']
                amount = serializer.validated_data['amount']
                wallet_type = serializer.validated_data['wallet_type']
                reason = serializer.validated_data['reason']
                reference_id = serializer.validated_data.get('reference_id')
                
                # Check permissions for override action
                if action == 'override' and not request.user.is_superuser:
                    return Response(
                        {'error': 'Only superusers can override wallet balances.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                result = AdminWalletService.adjust_wallet_balance(
                    user_id, action, amount, wallet_type, reason, 
                    request.user, reference_id
                )
                
                return Response({
                    'message': f'Wallet balance adjusted successfully.',
                    'user_email': result['user'].email,
                    'action': action,
                    'amount': amount,
                    'balance_before': result['balance_before'],
                    'balance_after': result['balance_after']
                })
            except Exception as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(
            serializer.errors, 
            status=status.HTTP_400_BAD_REQUEST
        )


class AdminInvestmentViewSet(viewsets.ModelViewSet):
    """ViewSet for admin investment management."""
    
    permission_classes = [IsAuthenticated, InvestmentManagementPermission]
    serializer_class = InvestmentSerializer
    queryset = Investment.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'plan']
    search_fields = ['user__email', 'user__username']
    ordering_fields = ['created_at', 'amount', 'total_roi_earned']
    ordering = ['-created_at']
    
    @action(detail=False, methods=['post'])
    def test_post(self, request):
        """Test endpoint to verify POST is working."""
        return Response({
            'message': 'POST method is working!',
            'timestamp': timezone.now().isoformat()
        })
    
    @action(detail=False, methods=['post'])
    def trigger_roi(self, request):
        """Manually trigger ROI distribution."""
        try:
            result = AdminInvestmentService.trigger_roi_distribution(request.user)
            
            return Response({
                'message': 'ROI distribution triggered successfully.',
                'processed_count': result['processed_count'],
                'total_roi_distributed': result['total_roi_distributed']
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def get_queryset(self):
        """Return filtered queryset."""
        queryset = super().get_queryset()
        
        # Filter by user if provided
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        return queryset.select_related('user', 'plan')
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an investment early."""
        try:
            investment = self.get_object()
            reason = request.data.get('reason', '')
            
            AdminInvestmentService.cancel_investment(
                investment.id, request.user, reason
            )
            
            return Response({
                'message': f'Investment {investment.id} has been cancelled.',
                'reason': reason
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class AdminWithdrawalViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for admin withdrawal management."""
    
    permission_classes = [IsAuthenticated, WithdrawalApprovalPermission]
    serializer_class = WithdrawalSerializer
    queryset = Withdrawal.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['currency', 'status', 'payout_method']
    search_fields = ['user__email', 'user__username', 'payout_method', 'tx_hash']
    ordering_fields = ['created_at', 'amount', 'status', 'processed_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return filtered queryset."""
        queryset = super().get_queryset()
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.select_related('user', 'processed_by')
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a withdrawal request."""
        serializer = WithdrawalApprovalSerializer(data=request.data)
        if serializer.is_valid():
            try:
                withdrawal = self.get_object()
                notes = serializer.validated_data.get('notes', '')
                tx_hash = serializer.validated_data.get('tx_hash')
                
                AdminWithdrawalService.approve_withdrawal(
                    withdrawal.id, request.user, notes, tx_hash
                )
                
                return Response({
                    'message': f'Withdrawal {withdrawal.id} has been approved.',
                    'notes': notes,
                    'tx_hash': tx_hash
                })
            except Exception as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(
            serializer.errors, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a withdrawal request."""
        serializer = WithdrawalApprovalSerializer(data=request.data)
        if serializer.is_valid():
            try:
                withdrawal = self.get_object()
                rejection_reason = serializer.validated_data.get('rejection_reason', '')
                notes = serializer.validated_data.get('notes', '')
                
                AdminWithdrawalService.reject_withdrawal(
                    withdrawal.id, request.user, rejection_reason, notes
                )
                
                return Response({
                    'message': f'Withdrawal {withdrawal.id} has been rejected.',
                    'rejection_reason': rejection_reason,
                    'notes': notes
                })
            except Exception as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(
            serializer.errors, 
            status=status.HTTP_400_BAD_REQUEST
        )


class AdminReferralViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for admin referral management."""
    
    permission_classes = [IsAuthenticated, ReferralManagementPermission]
    serializer_class = ReferralSerializer
    queryset = Referral.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['level']
    search_fields = ['user__email', 'referred_user__email']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return filtered queryset."""
        queryset = super().get_queryset()
        
        # Filter by user if provided
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        return queryset.select_related('user', 'referred_user', 'referrer')
    
    @action(detail=False, methods=['get'])
    def user_tree(self, request):
        """Get referral tree for a specific user."""
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response(
                {'error': 'user_id parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            tree = AdminReferralService.get_user_referral_tree(user_id)
            
            return Response({
                'user_email': tree['user'].email,
                'direct_referrals': ReferralSerializer(
                    tree['direct_referrals'], many=True
                ).data,
                'indirect_referrals': ReferralSerializer(
                    tree['indirect_referrals'], many=True
                ).data,
                'level3_referrals': ReferralSerializer(
                    tree['level3_referrals'], many=True
                ).data,
                'total_referrals': tree['total_referrals']
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class AdminTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for admin transaction management."""
    
    permission_classes = [IsAuthenticated, TransactionLogPermission]
    serializer_class = TransactionSerializer
    queryset = WalletTransaction.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['transaction_type', 'wallet_type', 'status', 'chain_type']
    search_fields = ['user__email', 'user__username', 'reference_id', 'description']
    ordering_fields = ['created_at', 'amount', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return filtered queryset."""
        queryset = super().get_queryset()
        
        # Apply additional filters
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        return queryset.select_related('user')
    
    @action(detail=False, methods=['post'])
    def export(self, request):
        """Export transactions in specified format."""
        serializer = ExportTransactionsSerializer(data=request.data)
        if serializer.is_valid():
            try:
                filters = {
                    'date_from': serializer.validated_data.get('date_from'),
                    'date_to': serializer.validated_data.get('date_to'),
                    'transaction_type': serializer.validated_data.get('transaction_type'),
                    'wallet_type': serializer.validated_data.get('wallet_type'),
                    'user_id': serializer.validated_data.get('user_id')
                }
                
                format_type = serializer.validated_data['format']
                
                if format_type == 'csv':
                    csv_data = AdminTransactionService.export_transactions(filters, format_type)
                    
                    from django.http import HttpResponse
                    response = HttpResponse(csv_data, content_type='text/csv')
                    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
                    return response
                else:
                    return Response({
                        'error': f'{format_type.upper()} export not yet implemented.'
                    }, status=status.HTTP_501_NOT_IMPLEMENTED)
                    
            except Exception as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(
            serializer.errors, 
            status=status.HTTP_400_BAD_REQUEST
        )


class AdminAnnouncementViewSet(viewsets.ModelViewSet):
    """ViewSet for admin announcement management."""
    
    permission_classes = [IsAuthenticated, AnnouncementPermission]
    serializer_class = AnnouncementSerializer
    queryset = Announcement.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'target_group', 'is_pinned']
    search_fields = ['title', 'message']
    ordering_fields = ['created_at', 'priority', 'display_from']
    ordering = ['-priority', '-is_pinned', '-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return AnnouncementCreateSerializer
        return AnnouncementSerializer
    
    def get_queryset(self):
        """Return filtered queryset."""
        queryset = super().get_queryset()
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.select_related('created_by')
    
    def perform_create(self, serializer):
        """Create announcement with current user as creator."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def active_for_user(self, request):
        """Get active announcements for the current user."""
        try:
            # Override permission check for this endpoint
            self.permission_classes = [IsAuthenticated]
            self.check_permissions(request)
            
            announcements = AdminAnnouncementService.get_active_announcements_for_user(
                request.user
            )
            
            serializer = self.get_serializer(announcements, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class AdminActionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for admin action logs."""
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = AdminActionLogSerializer
    queryset = AdminActionLog.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['action_type', 'admin_user', 'target_user']
    search_fields = ['action_description', 'target_model']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return filtered queryset."""
        queryset = super().get_queryset()
        
        # Filter by action type if provided
        action_type = self.request.query_params.get('action_type')
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        
        # Filter by admin user if provided
        admin_user_id = self.request.query_params.get('admin_user_id')
        if admin_user_id:
            queryset = queryset.filter(admin_user_id=admin_user_id)
        
        return queryset.select_related('admin_user', 'target_user')


class AdminInvestmentPlanViewSet(viewsets.ModelViewSet):
    """Admin ViewSet for managing investment plans."""
    
    queryset = InvestmentPlan.objects.all()
    serializer_class = InvestmentPlanSerializer
    permission_classes = [IsAuthenticated, InvestmentManagementPermission]
    filterset_fields = ['status', 'is_active', 'frequency']
    search_fields = ['name', 'description']
    
    def perform_create(self, serializer):
        """Create investment plan."""
        serializer.save()
    
    def perform_update(self, serializer):
        """Update investment plan."""
        serializer.save()


class AdminBreakdownRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin ViewSet for managing breakdown requests."""
    
    queryset = BreakdownRequest.objects.all()
    serializer_class = BreakdownRequestAdminSerializer
    permission_classes = [IsAuthenticated, InvestmentManagementPermission]
    filterset_fields = ['status', 'created_at']
    search_fields = ['user__username', 'investment__plan__name']
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a breakdown request."""
        breakdown_request = self.get_object()
        
        if breakdown_request.status != 'pending':
            return Response(
                {"error": "Only pending requests can be approved."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Approve breakdown request
                breakdown_request.approve(request.user)
                
                # Credit final amount to user's wallet
                investment = breakdown_request.investment
                final_amount = breakdown_request.final_amount
                currency = investment.currency
                user = investment.user
                
                if currency == 'inr':
                    wallet = user.inr_wallet
                else:  # usdt
                    wallet = user.usdt_wallet
                
                # Record balance before credit
                balance_before = wallet.balance
                
                # Credit balance
                wallet.add_balance(final_amount)
                wallet.save()
                
                # Log transaction
                from app.wallet.models import WalletTransaction
                WalletTransaction.objects.create(
                    user=user,
                    transaction_type='refund',
                    wallet_type=currency,
                    chain_type=None if currency == 'inr' else wallet.chain_type,
                    amount=final_amount,
                    balance_before=balance_before,
                    balance_after=wallet.balance,
                    status='completed',
                    reference_id=str(breakdown_request.id),
                    description=f"Breakdown payout for {investment.plan.name}",
                    metadata={
                        'investment_id': str(investment.id),
                        'plan_name': investment.plan.name,
                        'original_amount': float(investment.amount),
                        'roi_accrued': float(investment.roi_accrued),
                        'breakdown_type': 'approved'
                    }
                )
                
                # If ROI was accrued, credit it to wallet
                if investment.roi_accrued > 0:
                    roi_balance_before = wallet.balance
                    wallet.add_balance(investment.roi_accrued)
                    wallet.save()
                    
                    WalletTransaction.objects.create(
                        user=user,
                        transaction_type='roi_credit',
                        wallet_type=currency,
                        chain_type=None if currency == 'inr' else wallet.chain_type,
                        amount=investment.roi_accrued,
                        balance_before=roi_balance_before,
                        balance_after=wallet.balance,
                        status='completed',
                        reference_id=str(investment.id),
                        description=f"ROI settlement for {investment.plan.name} breakdown",
                        metadata={
                            'investment_id': str(investment.id),
                            'plan_name': investment.plan.name,
                            'breakdown_type': 'roi_settlement'
                        }
                    )
                
                return Response({
                    'message': f'Breakdown request {breakdown_request.id} has been approved.',
                    'final_amount': final_amount,
                    'roi_accrued': investment.roi_accrued
                })
                
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class UserAnnouncementView(APIView):
    """View for user-facing announcements.
    
    This view is separate from the admin announcement management and only requires
    regular user authentication.
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get active announcements for the current user."""
        try:
            # Get all announcements directly from the database
            announcements = Announcement.objects.all()
            
            # If no announcements exist, create a default one
            if not announcements.exists():
                admin_user = User.objects.filter(is_staff=True).first()
                if admin_user:
                    announcement = Announcement.objects.create(
                        title="System Announcement",
                        message="This is a system announcement",
                        status="ACTIVE",
                        target_group="ALL",
                        created_by=admin_user
                    )
                    announcements = [announcement]
            
            serializer = AnnouncementSerializer(announcements, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
