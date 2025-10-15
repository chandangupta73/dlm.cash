from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count, Q
from decimal import Decimal

from .models import InvestmentPlan, Investment, BreakdownRequest
from .serializers import (
    InvestmentPlanSerializer, InvestmentPlanListSerializer,
    InvestmentSerializer, InvestmentCreateSerializer,
    BreakdownRequestSerializer, BreakdownRequestCreateSerializer,
    BreakdownRequestAdminSerializer, InvestmentStatsSerializer
)


class InvestmentPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for investment plans (read-only for users)."""
    
    queryset = InvestmentPlan.objects.filter(is_active=True, status='active')
    serializer_class = InvestmentPlanListSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['frequency', 'roi_rate']
    search_fields = ['name', 'description']
    
    def get_queryset(self):
        """Filter active plans only."""
        return InvestmentPlan.objects.filter(is_active=True, status='active')


class InvestmentViewSet(viewsets.ModelViewSet):
    """ViewSet for user investments."""
    
    serializer_class = InvestmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # Disable pagination to get all investments
    
    def get_queryset(self):
        """Return investments for the current user only."""
        return Investment.objects.filter(user=self.request.user).select_related('plan')
    
    def get_serializer_class(self):
        """Use different serializers for different actions."""
        if self.action == 'create':
            return InvestmentCreateSerializer
        return InvestmentSerializer
    
    # Remove custom create method - let the serializer handle it
    # The serializer will properly handle payment_method, status, and wallet deduction
    
    @action(detail=True, methods=['post'])
    def breakdown(self, request, pk=None):
        """Request breakdown for an investment."""
        investment = self.get_object()
        
        # Check if investment can be broken down
        if not investment.can_breakdown():
            return Response(
                {"error": "Investment cannot be broken down."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if breakdown request already exists
        if hasattr(investment, 'breakdown_request'):
            return Response(
                {"error": "Breakdown request already exists."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create breakdown request
        serializer = BreakdownRequestCreateSerializer(
            data={'investment': investment.id},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        breakdown_request = serializer.save()
        
        response_serializer = BreakdownRequestSerializer(breakdown_request)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get investment statistics for the user."""
        user = request.user
        
        # Calculate statistics
        total_investments = Investment.objects.filter(user=user).count()
        active_investments = Investment.objects.filter(
            user=user, 
            status='active', 
            is_active=True
        ).count()
        completed_investments = Investment.objects.filter(
            user=user, 
            status='completed'
        ).count()
        
        total_invested = Investment.objects.filter(user=user).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        total_roi_earned = Investment.objects.filter(user=user).aggregate(
            total=Sum('roi_accrued')
        )['total'] or Decimal('0')
        
        pending_breakdowns = BreakdownRequest.objects.filter(
            user=user, 
            status='pending'
        ).count()
        
        stats = {
            'total_investments': total_investments,
            'active_investments': active_investments,
            'completed_investments': completed_investments,
            'total_invested': total_invested,
            'total_roi_earned': total_roi_earned,
            'pending_breakdowns': pending_breakdowns
        }
        
        serializer = InvestmentStatsSerializer(stats)
        return Response(serializer.data)


class BreakdownRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for breakdown requests (read-only for users)."""
    
    serializer_class = BreakdownRequestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return breakdown requests for the current user only."""
        return BreakdownRequest.objects.filter(user=self.request.user)


# Admin Views
class AdminInvestmentPlanViewSet(viewsets.ModelViewSet):
    """Admin ViewSet for managing investment plans."""
    
    queryset = InvestmentPlan.objects.all()
    serializer_class = InvestmentPlanSerializer
    permission_classes = [IsAdminUser]
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
    permission_classes = [IsAdminUser]
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
                            'breakdown_type': 'approved'
                        }
                    )
                
                return Response({"message": "Breakdown request approved successfully."})
                
        except Exception as e:
            return Response(
                {"error": f"Failed to approve breakdown: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a breakdown request."""
        breakdown_request = self.get_object()
        
        if breakdown_request.status != 'pending':
            return Response(
                {"error": "Only pending requests can be rejected."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notes = request.data.get('notes', '')
        
        try:
            with transaction.atomic():
                # Reject breakdown request
                breakdown_request.reject(request.user, notes)
                
                # Credit all accrued ROI to user's wallet
                investment = breakdown_request.investment
                if investment.roi_accrued > 0:
                    currency = investment.currency
                    user = investment.user
                    
                    if currency == 'inr':
                        wallet = user.inr_wallet
                    else:  # usdt
                        wallet = user.usdt_wallet
                    
                    # Record balance before credit
                    balance_before = wallet.balance
                    
                    # Credit ROI
                    wallet.add_balance(investment.roi_accrued)
                    wallet.save()
                    
                    # Log transaction
                    WalletTransaction.objects.create(
                        user=user,
                        transaction_type='roi_credit',
                        wallet_type=currency,
                        chain_type=None if currency == 'inr' else wallet.chain_type,
                        amount=investment.roi_accrued,
                        balance_before=balance_before,
                        balance_after=wallet.balance,
                        status='completed',
                        reference_id=str(investment.id),
                        description=f"ROI settlement for {investment.plan.name} breakdown rejection",
                        metadata={
                            'investment_id': str(investment.id),
                            'plan_name': investment.plan.name,
                            'breakdown_type': 'rejected'
                        }
                    )
                
                return Response({"message": "Breakdown request rejected successfully."})
                
        except Exception as e:
            return Response(
                {"error": f"Failed to reject breakdown: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get breakdown request statistics for admin."""
        total_requests = BreakdownRequest.objects.count()
        pending_requests = BreakdownRequest.objects.filter(status='pending').count()
        approved_requests = BreakdownRequest.objects.filter(status='approved').count()
        rejected_requests = BreakdownRequest.objects.filter(status='rejected').count()
        
        stats = {
            'total_requests': total_requests,
            'pending_requests': pending_requests,
            'approved_requests': approved_requests,
            'rejected_requests': rejected_requests
        }
        
        return Response(stats)
