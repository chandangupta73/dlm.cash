from rest_framework import status, generics, viewsets, serializers
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from app.wallet.models import (
    INRWallet, USDTWallet, WalletTransaction, DepositRequest,
    WalletAddress, USDTDepositRequest, SweepLog
)
from app.schemas.wallet import (
    INRWalletSerializer, USDTWalletSerializer, WalletTransactionSerializer,
    DepositRequestSerializer, DepositRequestCreateSerializer, WalletBalanceSerializer,
    TransactionHistorySerializer, DepositRequestListSerializer,
    WalletAddressSerializer, USDTDepositRequestSerializer, SweepLogSerializer
)
from app.crud.wallet import (
    WalletService, DepositService, TransactionService, WalletValidationService,
    WalletAddressService, USDTDepositService, SweepService
)


class WalletBalanceView(generics.RetrieveAPIView):
    """Get user's wallet balance."""
    permission_classes = [IsAuthenticated]
    serializer_class = WalletBalanceSerializer
    
    def get_object(self):
        """Return wallet balance data for the authenticated user."""
        balance_data = WalletService.get_wallet_balance(self.request.user)
        return balance_data


class WalletAddressView(APIView):
    """Get user's wallet addresses for ERC20 and BEP20 (same address for both networks)."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Return wallet addresses for the authenticated user."""
        user = request.user
        
        # Get or create ERC20 address (this is the master address for both ERC20 and BEP20)
        erc20_address = WalletAddressService.get_or_create_wallet_address(user, 'erc20')
        
        # ERC20 and BEP20 use the same address for compatibility
        response_data = {
            'erc20': erc20_address.address,
            'bep20': erc20_address.address  # Same address for both networks
        }
        
        return Response(response_data)


class WalletAddressByChainView(generics.RetrieveAPIView):
    """Get user's wallet address for a specific chain."""
    permission_classes = [IsAuthenticated]
    serializer_class = WalletAddressSerializer
    
    def get_object(self):
        """Return wallet address for the specified chain."""
        chain_type = self.kwargs.get('chain_type')
        if chain_type not in ['erc20', 'bep20']:
            raise serializers.ValidationError("Invalid chain type")
        
        wallet_address = WalletAddressService.get_or_create_wallet_address(self.request.user, chain_type)
        return wallet_address


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
        chain_type = self.request.query_params.get('chain_type')
        transaction_type = self.request.query_params.get('transaction_type')
        status = self.request.query_params.get('status')
        
        if wallet_type:
            queryset = queryset.filter(wallet_type=wallet_type)
        if chain_type:
            queryset = queryset.filter(chain_type=chain_type)
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


class USDTDepositViewSet(viewsets.ModelViewSet):
    """ViewSet for USDT deposits."""
    permission_classes = [IsAuthenticated]
    serializer_class = USDTDepositRequestSerializer
    pagination_class = PageNumberPagination
    
    def get_queryset(self):
        """Filter USDT deposits for the authenticated user."""
        queryset = USDTDepositRequest.objects.filter(user=self.request.user)
        
        # Apply chain filter if provided
        chain_type = self.request.query_params.get('chain_type')
        if chain_type:
            queryset = queryset.filter(chain_type=chain_type)
        
        return queryset.select_related('user').order_by('-created_at')
    
    def perform_create(self, serializer):
        """Create USDT deposit request."""
        serializer.save(user=self.request.user)


class SweepLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for sweep logs."""
    permission_classes = [IsAuthenticated]
    serializer_class = SweepLogSerializer
    pagination_class = PageNumberPagination
    
    def get_queryset(self):
        """Filter sweep logs for the authenticated user."""
        queryset = SweepLog.objects.filter(user=self.request.user)
        
        # Apply filters
        chain_type = self.request.query_params.get('chain_type')
        sweep_type = self.request.query_params.get('sweep_type')
        status = self.request.query_params.get('status')
        
        if chain_type:
            queryset = queryset.filter(chain_type=chain_type)
        if sweep_type:
            queryset = queryset.filter(sweep_type=sweep_type)
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.select_related('user', 'initiated_by').order_by('-created_at')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_balance(request):
    """Add balance to user wallet (admin function)."""
    wallet_type = request.data.get('wallet_type', 'inr')
    amount = request.data.get('amount')
    transaction_type = request.data.get('transaction_type', 'admin_adjustment')
    description = request.data.get('description', '')
    reference_id = request.data.get('reference_id')
    chain_type = request.data.get('chain_type')  # For USDT transactions
    
    if not amount or float(amount) <= 0:
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
                request.user, amount, transaction_type, description, reference_id, chain_type
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
    chain_type = request.data.get('chain_type')  # For USDT transactions
    
    if not amount or float(amount) <= 0:
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
                request.user, amount, transaction_type, description, reference_id, chain_type
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_usdt_deposit(request):
    """Process USDT deposit from blockchain webhook."""
    amount = request.data.get('amount')
    transaction_hash = request.data.get('transaction_hash')
    from_address = request.data.get('from_address')
    to_address = request.data.get('to_address')
    chain_type = request.data.get('chain_type')
    confirmation_count = request.data.get('confirmation_count', 0)
    block_number = request.data.get('block_number')
    
    if not all([amount, transaction_hash, from_address, to_address, chain_type]):
        return Response(
            {'error': 'Missing required fields'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if chain_type not in ['trc20', 'erc20', 'bep20']:
        return Response(
            {'error': 'Invalid chain type'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Validate USDT amount
        is_valid, message = WalletValidationService.validate_usdt_deposit_amount(amount)
        if not is_valid:
            return Response(
                {'error': message},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find user by wallet address and chain type
        try:
            wallet_address = WalletAddress.objects.get(address=to_address, chain_type=chain_type)
            user = wallet_address.user
        except WalletAddress.DoesNotExist:
            return Response(
                {'error': 'Invalid wallet address or chain type'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create or update deposit request
        deposit, created = USDTDepositRequest.objects.get_or_create(
            transaction_hash=transaction_hash,
            defaults={
                'user': user,
                'chain_type': chain_type,
                'amount': amount,
                'from_address': from_address,
                'to_address': to_address
            }
        )
        
        if not created:
            # Update confirmation count
            USDTDepositService.process_deposit_confirmation(
                deposit.id, confirmation_count, block_number
            )
        
        return Response({
            'message': 'USDT deposit processed successfully',
            'deposit_id': str(deposit.id),
            'status': deposit.status,
            'chain_type': deposit.chain_type
        })
        
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manual_sweep_deposit(request, deposit_id):
    """Manually sweep a confirmed USDT deposit (admin only)."""
    try:
        success = SweepService.manual_sweep_deposit(deposit_id, request.user)
        if success:
            return Response({'message': 'Deposit swept successfully'})
        else:
            return Response(
                {'error': 'Failed to sweep deposit'},
                status=status.HTTP_400_BAD_REQUEST
            )
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_usdt_deposits(request):
    """Get all pending USDT deposits (admin only)."""
    chain_type = request.query_params.get('chain_type')
    deposits = USDTDepositService.get_pending_deposits(chain_type)
    serializer = USDTDepositRequestSerializer(deposits, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def confirmed_usdt_deposits(request):
    """Get all confirmed USDT deposits ready for sweep (admin only)."""
    chain_type = request.query_params.get('chain_type')
    deposits = USDTDepositService.get_confirmed_deposits(chain_type)
    serializer = USDTDepositRequestSerializer(deposits, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sweep_logs(request):
    """Get sweep logs with optional filters (admin only)."""
    user_id = request.query_params.get('user_id')
    chain_type = request.query_params.get('chain_type')
    sweep_type = request.query_params.get('sweep_type')
    status = request.query_params.get('status')
    
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
    else:
        user = None
    
    sweep_logs = SweepService.get_sweep_logs(user, chain_type, sweep_type, status)
    serializer = SweepLogSerializer(sweep_logs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_history(request):
    """Get paginated transaction history."""
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    wallet_type = request.query_params.get('wallet_type')
    chain_type = request.query_params.get('chain_type')
    transaction_type = request.query_params.get('transaction_type')
    status = request.query_params.get('status')
    
    history_data = TransactionService.get_user_transactions(
        request.user, wallet_type, chain_type, transaction_type, status, page, page_size
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

    sweep_type = request.query_params.get('sweep_type')
    status = request.query_params.get('status')
    
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
    else:
        user = None
    
    sweep_logs = SweepService.get_sweep_logs(user, chain_type, sweep_type, status)
    serializer = SweepLogSerializer(sweep_logs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_history(request):
    """Get paginated transaction history."""
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    wallet_type = request.query_params.get('wallet_type')
    chain_type = request.query_params.get('chain_type')
    transaction_type = request.query_params.get('transaction_type')
    status = request.query_params.get('status')
    
    history_data = TransactionService.get_user_transactions(
        request.user, wallet_type, chain_type, transaction_type, status, page, page_size
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
