from rest_framework import status, generics, viewsets, serializers
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from .models import INRWallet, USDTWallet, WalletTransaction, DepositRequest
from .serializers import (
    INRWalletSerializer, USDTWalletSerializer, WalletTransactionSerializer,
    DepositRequestSerializer, DepositRequestCreateSerializer, WalletBalanceSerializer,
    TransactionHistorySerializer, DepositRequestListSerializer
)
from .services import (
    WalletService, DepositService, TransactionService, WalletValidationService
)


class WalletBalanceView(generics.RetrieveAPIView):
    """Get user's wallet balance."""
    permission_classes = [IsAuthenticated]
    serializer_class = WalletBalanceSerializer
    
    def get_object(self):
        """Return wallet balance data for the authenticated user."""
        balance_data = WalletService.get_wallet_balance(self.request.user)
        return balance_data


class WalletTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for wallet transactions."""
    permission_classes = [IsAuthenticated]
    serializer_class = WalletTransactionSerializer
    pagination_class = PageNumberPagination
    
    def get_queryset(self):
        """Filter transactions for the authenticated user."""
        queryset = WalletTransaction.objects.filter(user=self.request.user)
        
        # Apply filters
        wallet_type = self.request.query_params.get('wallet_type')
        transaction_type = self.request.query_params.get('transaction_type')
        status = self.request.query_params.get('status')
        
        if wallet_type:
            queryset = queryset.filter(wallet_type=wallet_type)
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.select_related('user').order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get transaction summary for the user."""
        days = int(request.query_params.get('days', 30))
        summary = TransactionService.get_transaction_summary(request.user, days)
        return Response(summary)


class DepositRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for deposit requests."""
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return DepositRequestCreateSerializer
        return DepositRequestSerializer
    
    def get_queryset(self):
        """Filter deposit requests for the authenticated user."""
        return DepositRequest.objects.filter(user=self.request.user).select_related('user').order_by('-created_at')
    
    def perform_create(self, serializer):
        """Create deposit request for the authenticated user."""
        # Validate amount
        amount = serializer.validated_data['amount']
        is_valid, message = WalletValidationService.validate_deposit_amount(amount)
        if not is_valid:
            raise serializers.ValidationError(message)
        
        # Validate wallet status
        is_valid, message = WalletValidationService.validate_wallet_status(self.request.user)
        if not is_valid:
            raise serializers.ValidationError(message)
        
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a pending deposit request."""
        deposit = self.get_object()
        
        if deposit.status != 'pending':
            return Response(
                {'error': 'Only pending deposits can be cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        deposit.status = 'cancelled'
        deposit.save()
        
        return Response({'message': 'Deposit request cancelled successfully'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_balance(request):
    """Add balance to user wallet (admin function)."""
    wallet_type = request.data.get('wallet_type', 'inr')
    amount = request.data.get('amount')
    transaction_type = request.data.get('transaction_type', 'admin_adjustment')
    description = request.data.get('description', '')
    reference_id = request.data.get('reference_id')
    
    if not amount or amount <= 0:
        return Response(
            {'error': 'Valid amount is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        if wallet_type == 'inr':
            success = WalletService.add_inr_balance(
                request.user, amount, transaction_type, description, reference_id
            )
        elif wallet_type == 'usdt':
            success = WalletService.add_usdt_balance(
                request.user, amount, transaction_type, description, reference_id
            )
        else:
            return Response(
                {'error': 'Invalid wallet type'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if success:
            balance_data = WalletService.get_wallet_balance(request.user)
            return Response({
                'message': 'Balance added successfully',
                'balance': balance_data
            })
        else:
            return Response(
                {'error': 'Failed to add balance'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deduct_balance(request):
    """Deduct balance from user wallet."""
    wallet_type = request.data.get('wallet_type', 'inr')
    amount = request.data.get('amount')
    transaction_type = request.data.get('transaction_type', 'withdrawal')
    description = request.data.get('description', '')
    reference_id = request.data.get('reference_id')
    
    if not amount or amount <= 0:
        return Response(
            {'error': 'Valid amount is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate withdrawal amount
    is_valid, message = WalletValidationService.validate_withdrawal_amount(
        request.user, amount, wallet_type
    )
    if not is_valid:
        return Response(
            {'error': message},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        if wallet_type == 'inr':
            success = WalletService.deduct_inr_balance(
                request.user, amount, transaction_type, description, reference_id
            )
        elif wallet_type == 'usdt':
            success = WalletService.deduct_usdt_balance(
                request.user, amount, transaction_type, description, reference_id
            )
        else:
            return Response(
                {'error': 'Invalid wallet type'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if success:
            balance_data = WalletService.get_wallet_balance(request.user)
            return Response({
                'message': 'Balance deducted successfully',
                'balance': balance_data
            })
        else:
            return Response(
                {'error': 'Failed to deduct balance'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_history(request):
    """Get paginated transaction history."""
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    wallet_type = request.query_params.get('wallet_type')
    transaction_type = request.query_params.get('transaction_type')
    status = request.query_params.get('status')
    
    history_data = TransactionService.get_user_transactions(
        request.user, wallet_type, transaction_type, status, page, page_size
    )
    
    serializer = WalletTransactionSerializer(history_data['transactions'], many=True)
    
    return Response({
        'transactions': serializer.data,
        'total_count': history_data['total_count'],
        'page': history_data['page'],
        'page_size': history_data['page_size'],
        'has_next': history_data['has_next'],
        'has_previous': history_data['has_previous']
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_summary(request):
    """Get transaction summary."""
    days = int(request.query_params.get('days', 30))
    summary = TransactionService.get_transaction_summary(request.user, days)
    return Response(summary)


# Admin-only views for deposit management
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_deposit(request, deposit_id):
    """Approve a deposit request (admin only)."""
    try:
        success = DepositService.approve_deposit(deposit_id, request.user)
        if success:
            return Response({'message': 'Deposit approved successfully'})
        else:
            return Response(
                {'error': 'Failed to approve deposit'},
                status=status.HTTP_400_BAD_REQUEST
            )
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_deposit(request, deposit_id):
    """Reject a deposit request (admin only)."""
    reason = request.data.get('reason', '')
    
    try:
        success = DepositService.reject_deposit(deposit_id, request.user, reason)
        if success:
            return Response({'message': 'Deposit rejected successfully'})
        else:
            return Response(
                {'error': 'Failed to reject deposit'},
                status=status.HTTP_400_BAD_REQUEST
            )
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_deposits(request):
    """Get all pending deposits (admin only)."""
    deposits = DepositRequest.objects.filter(status='pending').select_related('user').order_by('-created_at')
    serializer = DepositRequestListSerializer(deposits, many=True)
    return Response(serializer.data) 