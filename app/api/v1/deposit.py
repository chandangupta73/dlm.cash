from rest_framework import status, viewsets, serializers
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from app.admin_panel.permissions import IsAdminUser

from app.wallet.models import DepositRequest
from app.schemas.wallet import (
    DepositRequestSerializer, DepositRequestCreateSerializer, DepositRequestListSerializer
)
from app.crud.wallet import (
    DepositService, WalletValidationService
)


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
    
    def create(self, request, *args, **kwargs):
        """Create deposit request and return full response with ID."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Get the created deposit and return full response
        deposit = serializer.instance
        full_serializer = DepositRequestSerializer(deposit)
        return Response(full_serializer.data, status=status.HTTP_201_CREATED)
    
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


# Admin-only views for deposit management
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
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
