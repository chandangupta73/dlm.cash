from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from app.withdrawals.models import Withdrawal
from app.withdrawals.serializers import (
    WithdrawalRequestSerializer,
    WithdrawalSerializer,
    AdminWithdrawalSerializer,
    WithdrawalApprovalSerializer,
    WithdrawalRejectionSerializer,
    WithdrawalCompletionSerializer,
    WithdrawalLimitsSerializer
)
from app.wallet.models import WalletTransaction


class WithdrawalViewSet(ModelViewSet):
    """ViewSet for user withdrawal operations."""
    
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['currency', 'status', 'payout_method']
    search_fields = ['payout_method', 'status']
    ordering_fields = ['created_at', 'amount', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return user's own withdrawals only."""
        return Withdrawal.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return WithdrawalRequestSerializer
        return WithdrawalSerializer
    
    def create(self, request):
        """Create a new withdrawal request."""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    withdrawal = serializer.save()
                    return Response(
                        {
                            'success': True,
                            'message': 'Withdrawal request created successfully',
                            'data': WithdrawalSerializer(withdrawal).data
                        },
                        status=status.HTTP_201_CREATED
                    )
            except Exception as e:
                return Response(
                    {
                        'success': False,
                        'message': f'Failed to create withdrawal request: {str(e)}'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(
            {
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a withdrawal request (user can cancel their own pending withdrawals)."""
        withdrawal = get_object_or_404(Withdrawal, pk=pk, user=request.user)
        
        if not withdrawal.can_be_cancelled():
            return Response(
                {
                    'success': False,
                    'message': 'Withdrawal cannot be cancelled in current status'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                success, message = withdrawal.cancel(reason="Cancelled by user")
                
                if success:
                    # Update transaction log
                    WalletTransaction.objects.filter(
                        reference_id=str(withdrawal.id),
                        transaction_type='withdrawal'
                    ).update(status='cancelled')
                    
                    return Response(
                        {
                            'success': True,
                            'message': message,
                            'data': WithdrawalSerializer(withdrawal).data
                        },
                        status=status.HTTP_200_OK
                    )
                else:
                    return Response(
                        {
                            'success': False,
                            'message': message
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'Failed to cancel withdrawal: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def limits(self, request):
        """Get withdrawal limits for different currencies."""
        currency = request.query_params.get('currency', 'INR')
        
        if currency not in ['INR', 'USDT']:
            return Response(
                {
                    'success': False,
                    'message': 'Invalid currency. Must be INR or USDT'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = WithdrawalLimitsSerializer(
            data={},
            context={'request': request, 'currency': currency}
        )
        
        return Response(
            {
                'success': True,
                'data': serializer.to_representation({})
            },
            status=status.HTTP_200_OK
        )


class AdminWithdrawalViewSet(ModelViewSet):
    """ViewSet for admin withdrawal management."""
    
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    serializer_class = AdminWithdrawalSerializer
    queryset = Withdrawal.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['currency', 'status', 'payout_method', 'user']
    search_fields = ['user__email', 'user__username', 'payout_method', 'tx_hash']
    ordering_fields = ['created_at', 'amount', 'status', 'processed_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return all withdrawals for admin."""
        queryset = super().get_queryset()
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by currency if provided
        currency_filter = self.request.query_params.get('currency')
        if currency_filter:
            queryset = queryset.filter(currency=currency_filter)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a withdrawal request."""
        withdrawal = get_object_or_404(Withdrawal, pk=pk)
        
        serializer = WithdrawalApprovalSerializer(
            data=request.data,
            context={'withdrawal': withdrawal}
        )
        
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    notes = serializer.validated_data.get('admin_notes', '')
                    success, message = withdrawal.approve(request.user, notes)
                    
                    if success:
                        # Update transaction log
                        WalletTransaction.objects.filter(
                            reference_id=str(withdrawal.id),
                            transaction_type='withdrawal'
                        ).update(status='approved')
                        
                        return Response(
                            {
                                'success': True,
                                'message': message,
                                'data': AdminWithdrawalSerializer(withdrawal).data
                            },
                            status=status.HTTP_200_OK
                        )
                    else:
                        return Response(
                            {
                                'success': False,
                                'message': message
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )
            except Exception as e:
                return Response(
                    {
                        'success': False,
                        'message': f'Failed to approve withdrawal: {str(e)}'
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(
            {
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a withdrawal request."""
        withdrawal = get_object_or_404(Withdrawal, pk=pk)
        
        serializer = WithdrawalRejectionSerializer(
            data=request.data,
            context={'withdrawal': withdrawal}
        )
        
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    reason = serializer.validated_data['rejection_reason']
                    success, message = withdrawal.reject(request.user, reason)
                    
                    if success:
                        # Update transaction log
                        WalletTransaction.objects.filter(
                            reference_id=str(withdrawal.id),
                            transaction_type='withdrawal'
                        ).update(status='failed')
                        
                        return Response(
                            {
                                'success': True,
                                'message': message,
                                'data': AdminWithdrawalSerializer(withdrawal).data
                            },
                            status=status.HTTP_200_OK
                        )
                    else:
                        return Response(
                            {
                                'success': False,
                                'message': message
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )
            except Exception as e:
                return Response(
                    {
                        'success': False,
                        'message': f'Failed to reject withdrawal: {str(e)}'
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(
            {
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark withdrawal as completed (with optional tx_hash for USDT)."""
        withdrawal = get_object_or_404(Withdrawal, pk=pk)
        
        serializer = WithdrawalCompletionSerializer(
            data=request.data,
            context={'withdrawal': withdrawal}
        )
        
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    tx_hash = serializer.validated_data.get('tx_hash')
                    notes = serializer.validated_data.get('admin_notes', '')
                    
                    success, message = withdrawal.complete(request.user, tx_hash, notes)
                    
                    if success:
                        # Update transaction log
                        WalletTransaction.objects.filter(
                            reference_id=str(withdrawal.id),
                            transaction_type='withdrawal'
                        ).update(status='completed')
                        
                        return Response(
                            {
                                'success': True,
                                'message': message,
                                'data': AdminWithdrawalSerializer(withdrawal).data
                            },
                            status=status.HTTP_200_OK
                        )
                    else:
                        return Response(
                            {
                                'success': False,
                                'message': message
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )
            except Exception as e:
                return Response(
                    {
                        'success': False,
                        'message': f'Failed to complete withdrawal: {str(e)}'
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(
            {
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending withdrawals."""
        pending_withdrawals = self.get_queryset().filter(status='PENDING')
        serializer = self.get_serializer(pending_withdrawals, many=True)
        
        return Response(
            {
                'success': True,
                'count': pending_withdrawals.count(),
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get withdrawal statistics."""
        from django.db.models import Sum, Count
        
        queryset = self.get_queryset()
        
        # Get statistics by status
        stats_by_status = {}
        for status_choice, _ in Withdrawal.STATUS_CHOICES:
            status_queryset = queryset.filter(status=status_choice)
            stats_by_status[status_choice.lower()] = {
                'count': status_queryset.count(),
                'total_amount': status_queryset.aggregate(Sum('amount'))['amount__sum'] or 0
            }
        
        # Get statistics by currency
        stats_by_currency = {}
        for currency_choice, _ in Withdrawal.CURRENCY_CHOICES:
            currency_queryset = queryset.filter(currency=currency_choice)
            stats_by_currency[currency_choice.lower()] = {
                'count': currency_queryset.count(),
                'total_amount': currency_queryset.aggregate(Sum('amount'))['amount__sum'] or 0
            }
        
        # Get today's statistics
        today = timezone.now().date()
        today_queryset = queryset.filter(created_at__date=today)
        today_stats = {
            'count': today_queryset.count(),
            'total_amount': today_queryset.aggregate(Sum('amount'))['amount__sum'] or 0
        }
        
        return Response(
            {
                'success': True,
                'data': {
                    'by_status': stats_by_status,
                    'by_currency': stats_by_currency,
                    'today': today_stats
                }
            },
            status=status.HTTP_200_OK
        )


# Function-based views for simple operations

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_withdrawal(request):
    """Create a new withdrawal request."""
    serializer = WithdrawalRequestSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        try:
            with transaction.atomic():
                withdrawal = serializer.save()
                return Response(
                    {
                        'success': True,
                        'message': 'Withdrawal request created successfully',
                        'data': WithdrawalSerializer(withdrawal).data
                    },
                    status=status.HTTP_201_CREATED
                )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'Failed to create withdrawal request: {str(e)}'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
    
    return Response(
        {
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        },
        status=status.HTTP_400_BAD_REQUEST
    )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_withdrawals(request):
    """Get user's withdrawal history."""
    withdrawals = Withdrawal.objects.filter(user=request.user).order_by('-created_at')
    
    # Apply filters
    currency = request.query_params.get('currency')
    if currency:
        withdrawals = withdrawals.filter(currency=currency)
    
    status_filter = request.query_params.get('status')
    if status_filter:
        withdrawals = withdrawals.filter(status=status_filter)
    
    # Pagination
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    paginator.page_size = 10
    result_page = paginator.paginate_queryset(withdrawals, request)
    
    serializer = WithdrawalSerializer(result_page, many=True)
    
    return paginator.get_paginated_response({
        'success': True,
        'data': serializer.data
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def withdrawal_limits(request):
    """Get withdrawal limits for a currency."""
    currency = request.query_params.get('currency', 'INR')
    
    if currency not in ['INR', 'USDT']:
        return Response(
            {
                'success': False,
                'message': 'Invalid currency. Must be INR or USDT'
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    serializer = WithdrawalLimitsSerializer(
        data={},
        context={'request': request, 'currency': currency}
    )
    
    return Response(
        {
            'success': True,
            'data': serializer.to_representation({})
        },
        status=status.HTTP_200_OK
    )
