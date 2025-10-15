from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.exceptions import ValidationError
from decimal import Decimal
import logging
from django.db import models

from .models import Transaction
from .serializers import (
    TransactionSerializer, TransactionListSerializer, TransactionDetailSerializer,
    TransactionFilterSerializer, AdminTransactionUpdateSerializer
)
from .services import TransactionService, TransactionIntegrationService

User = get_user_model()
logger = logging.getLogger(__name__)


class TransactionPagination(PageNumberPagination):
    """Custom pagination for transactions."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for user transaction operations."""
    
    permission_classes = [IsAuthenticated]
    pagination_class = TransactionPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['type', 'currency', 'status']
    ordering_fields = ['created_at', 'amount', 'type']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return transactions for the authenticated user only."""
        return Transaction.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'retrieve':
            return TransactionDetailSerializer
        return TransactionListSerializer
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get transaction summary for the authenticated user."""
        try:
            currency = request.query_params.get('currency')
            summary = TransactionService.get_transaction_summary(
                user=request.user,
                currency=currency
            )
            return Response({
                'success': True,
                'data': summary
            })
        except Exception as e:
            logger.error(f"Error getting transaction summary: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to get transaction summary'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def filters(self, request):
        """Get available filter options for transactions."""
        try:
            # Get unique values for filter options
            user_transactions = self.get_queryset()
            
            filter_options = {
                'types': list(user_transactions.values_list('type', flat=True).distinct()),
                'currencies': list(user_transactions.values_list('currency', flat=True).distinct()),
                'statuses': list(user_transactions.values_list('status', flat=True).distinct()),
            }
            
            return Response({
                'success': True,
                'data': filter_options
            })
        except Exception as e:
            logger.error(f"Error getting filter options: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to get filter options'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminTransactionViewSet(viewsets.ModelViewSet):
    """ViewSet for admin transaction operations."""
    
    permission_classes = [IsAdminUser]
    pagination_class = TransactionPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['type', 'currency', 'status', 'user']
    ordering_fields = ['created_at', 'amount', 'type', 'user__username']
    ordering = ['-created_at']
    serializer_class = TransactionSerializer
    
    def get_queryset(self):
        """Return all transactions for admin view."""
        return Transaction.objects.select_related('user').all()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action in ['update', 'partial_update']:
            return AdminTransactionUpdateSerializer
        return TransactionSerializer
    
    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        """Export transactions to CSV with optional filters."""
        try:
            # Parse filter parameters
            filter_serializer = TransactionFilterSerializer(data=request.query_params)
            if filter_serializer.is_valid():
                filters = filter_serializer.validated_data
            else:
                filters = {}
            
            # Export to CSV
            response = TransactionService.export_transactions_csv(filters)
            return response
            
        except Exception as e:
            logger.error(f"Error exporting transactions to CSV: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to export transactions'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get transaction statistics for admin dashboard."""
        try:
            queryset = self.get_queryset()
            
            # Basic statistics
            total_transactions = queryset.count()
            total_volume = queryset.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0')
            
            # Statistics by currency
            inr_stats = queryset.filter(currency='INR').aggregate(
                count=models.Count('id'),
                total=models.Sum('amount'),
                avg=models.Avg('amount')
            )
            
            usdt_stats = queryset.filter(currency='USDT').aggregate(
                count=models.Count('id'),
                total=models.Sum('amount'),
                avg=models.Avg('amount')
            )
            
            # Statistics by type
            type_stats = {}
            for transaction_type, _ in Transaction.TRANSACTION_TYPE_CHOICES:
                type_queryset = queryset.filter(type=transaction_type)
                type_stats[transaction_type] = {
                    'count': type_queryset.count(),
                    'total_amount': type_queryset.aggregate(
                        total=models.Sum('amount')
                    )['total'] or Decimal('0')
                }
            
            # Statistics by status
            status_stats = {}
            for status_choice, _ in Transaction.STATUS_CHOICES:
                status_queryset = queryset.filter(status=status_choice)
                status_stats[status_choice] = {
                    'count': status_queryset.count(),
                    'total_amount': status_queryset.aggregate(
                        total=models.Sum('amount')
                    )['total'] or Decimal('0')
                }
            
            statistics = {
                'overall': {
                    'total_transactions': total_transactions,
                    'total_volume': total_volume
                },
                'by_currency': {
                    'INR': inr_stats,
                    'USDT': usdt_stats
                },
                'by_type': type_stats,
                'by_status': status_stats
            }
            
            return Response({
                'success': True,
                'data': statistics
            })
            
        except Exception as e:
            logger.error(f"Error getting transaction statistics: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to get transaction statistics'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """Update transaction status and metadata."""
        try:
            transaction = self.get_object()
            serializer = AdminTransactionUpdateSerializer(
                transaction, 
                data=request.data, 
                partial=True
            )
            
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'success': True,
                    'data': TransactionSerializer(transaction).data
                })
            else:
                return Response({
                    'success': False,
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error updating transaction status: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to update transaction status'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# User API endpoints
def user_transactions(request):
    """Get user's own transactions with filtering and pagination."""
    try:
        # Parse filter parameters
        filter_serializer = TransactionFilterSerializer(data=request.GET)
        if filter_serializer.is_valid():
            filters = filter_serializer.validated_data
        else:
            return Response({
                'success': False,
                'errors': filter_serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get pagination parameters
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        
        # Get transactions
        result = TransactionService.get_user_transactions(
            user=request.user,
            filters=filters,
            page=page,
            page_size=page_size
        )
        
        # Serialize transactions
        transactions_data = TransactionListSerializer(
            result['transactions'], 
            many=True
        ).data
        
        return Response({
            'success': True,
            'data': {
                'transactions': transactions_data,
                'pagination': result['pagination']
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting user transactions: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to get transactions'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def transaction_detail(request, transaction_id):
    """Get detailed information about a specific transaction."""
    try:
        # Get transaction for the authenticated user
        try:
            transaction = Transaction.objects.get(
                id=transaction_id, 
                user=request.user
            )
        except Transaction.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Transaction not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Serialize transaction
        transaction_data = TransactionDetailSerializer(transaction).data
        
        return Response({
            'success': True,
            'data': transaction_data
        })
        
    except Exception as e:
        logger.error(f"Error getting transaction detail: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to get transaction details'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Admin API endpoints
def admin_transactions(request):
    """Get all transactions for admin view with filtering and pagination."""
    try:
        # Parse filter parameters
        filter_serializer = TransactionFilterSerializer(data=request.GET)
        if filter_serializer.is_valid():
            filters = filter_serializer.validated_data
        else:
            return Response({
                'success': False,
                'errors': filter_serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get pagination parameters
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        
        # Get transactions
        result = TransactionService.get_admin_transactions(
            filters=filters,
            page=page,
            page_size=page_size
        )
        
        # Serialize transactions
        transactions_data = TransactionSerializer(
            result['transactions'], 
            many=True
        ).data
        
        return Response({
            'success': True,
            'data': {
                'transactions': transactions_data,
                'pagination': result['pagination']
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting admin transactions: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to get transactions'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def admin_transaction_update(request, transaction_id):
    """Update transaction status and metadata (admin only)."""
    try:
        # Get transaction
        try:
            transaction = Transaction.objects.get(id=transaction_id)
        except Transaction.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Transaction not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Update transaction
        serializer = AdminTransactionUpdateSerializer(
            transaction, 
            data=request.data, 
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'data': TransactionSerializer(transaction).data
            })
        else:
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error updating admin transaction: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to update transaction'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
