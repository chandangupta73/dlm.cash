from django.shortcuts import render
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

from .models import Withdrawal
from .serializers import (
    WithdrawalRequestSerializer,
    WithdrawalSerializer,
    AdminWithdrawalSerializer,
    WithdrawalApprovalSerializer,
    WithdrawalRejectionSerializer,
    WithdrawalCompletionSerializer,
    WithdrawalLimitsSerializer
)
from app.wallet.models import WalletTransaction

# Create your views here.

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
    
    def perform_create(self, serializer):
        """Create withdrawal request for the current user."""
        serializer.save(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Create a new withdrawal request."""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    withdrawal = serializer.save(user=request.user)
                    
                    # Calculate total and net amounts
                    total_amount = withdrawal.amount + withdrawal.fee
                    net_amount = withdrawal.amount
                    
                    return Response(
                        {
                            'success': True,
                            'message': 'Withdrawal request created successfully',
                            'fee': float(withdrawal.fee),
                            'net_amount': float(net_amount),
                            'total_amount': float(total_amount),
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
                status=status.HTTP_400_BAD_REQUEST
            )
