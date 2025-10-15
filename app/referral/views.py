from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Sum, Count
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import (
    ReferralConfig, UserReferralProfile, Referral,
    ReferralEarning, ReferralMilestone
)
from .serializers import (
    UserReferralProfileSerializer, ReferralSerializer,
    ReferralEarningSerializer, ReferralMilestoneSerializer,
    ReferralConfigSerializer, ReferralTreeSerializer,
    ReferralEarningFilterSerializer, ReferralCodeSerializer,
    ReferralStatsSerializer, AdminReferralSearchSerializer,
    MilestoneCreateUpdateSerializer, ReferralEarningSummarySerializer
)
from .services import ReferralService

User = get_user_model()


class IsOwnerOrAdmin(permissions.BasePermission):
    """Custom permission to allow users to access their own data or admins to access all."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Admin can access everything
        if request.user.is_staff:
            return True
        
        # Users can only access their own data
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'referral') and hasattr(obj.referral, 'user'):
            return obj.referral.user == request.user
        elif hasattr(obj, 'referred_by'):
            return obj.referred_by == request.user
        
        return False


# User-facing Views
class ReferralProfileView(viewsets.ReadOnlyModelViewSet):
    """View for user's own referral profile."""
    serializer_class = UserReferralProfileSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    
    def get_queryset(self):
        return UserReferralProfile.objects.filter(user=self.request.user)
    
    def get_object(self):
        return self.get_queryset().first()
    
    def list(self, request, *args, **kwargs):
        """Override list to return single profile object."""
        profile = self.get_object()
        if profile:
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)


class ReferralTreeView(viewsets.ReadOnlyModelViewSet):
    """View for user's referral tree."""
    serializer_class = UserReferralProfileSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    
    def get_queryset(self):
        return UserReferralProfile.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get user's referral tree."""
        user = request.user
        max_levels = int(request.query_params.get('max_levels', 3))
        
        tree_data = ReferralService.get_user_referral_tree(user, max_levels)
        return Response(tree_data)


class ReferralEarningsView(viewsets.ReadOnlyModelViewSet):
    """View for user's referral earnings."""
    serializer_class = ReferralEarningSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['currency', 'level', 'status']
    search_fields = ['referral__referred_user__email']
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return ReferralEarning.objects.filter(referral__user=self.request.user)


class ReferralEarningsSummaryView(viewsets.ReadOnlyModelViewSet):
    """View for user's referral earnings summary."""
    serializer_class = ReferralEarningSummarySerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    
    def get_queryset(self):
        return UserReferralProfile.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get user's referral earnings summary."""
        user = request.user
        summary_data = ReferralService.get_referral_earnings_summary(user)
        return Response(summary_data)


class ValidateReferralCodeView(viewsets.GenericViewSet):
    """View for validating referral codes."""
    serializer_class = ReferralCodeSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def validate(self, request):
        """Validate a referral code."""
        referral_code = request.data.get('referral_code')
        
        if not referral_code:
            return Response({
                'is_valid': False,
                'referrer_id': None,
                'referrer_email': None,
                'message': 'Referral code is required.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if code exists and is not the user's own code
        try:
            profile = UserReferralProfile.objects.get(referral_code=referral_code)
            if profile.user == request.user:
                return Response({
                    'is_valid': False,
                    'referrer_id': None,
                    'referrer_email': None,
                    'message': 'You cannot use your own referral code.'
                })
            
            return Response({
                'is_valid': True,
                'referrer_id': profile.user.id,
                'referrer_email': profile.user.email,
                'message': 'Referral code is valid.'
            })
        except UserReferralProfile.DoesNotExist:
            return Response({
                'is_valid': False,
                'referrer_id': None,
                'referrer_email': None,
                'message': 'Invalid referral code.'
            })


# Admin-facing Views
class AdminReferralListView(viewsets.ReadOnlyModelViewSet):
    """Admin view for listing referrals."""
    serializer_class = ReferralSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['level', 'created_at']
    search_fields = ['user__email', 'referred_user__email', 'referrer__email']
    ordering_fields = ['created_at', 'level']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = Referral.objects.all()
        
        # Apply filters
        user_id = self.request.query_params.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        level = self.request.query_params.get('level')
        if level:
            queryset = queryset.filter(level=level)
        
        created_after = self.request.query_params.get('created_after')
        if created_after:
            queryset = queryset.filter(created_at__gte=created_after)
        
        return queryset


class AdminReferralEarningListView(viewsets.ReadOnlyModelViewSet):
    """Admin view for listing referral earnings."""
    serializer_class = ReferralEarningSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['level', 'currency', 'status', 'created_at']
    search_fields = ['referral__user__email', 'currency']
    ordering_fields = ['created_at', 'amount', 'level']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return ReferralEarning.objects.all()


class AdminMilestoneListView(viewsets.ReadOnlyModelViewSet):
    """Admin view for listing milestones."""
    serializer_class = ReferralMilestoneSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['condition_type', 'currency', 'is_active', 'created_at']
    search_fields = ['name', 'condition_type']
    ordering_fields = ['created_at', 'condition_value', 'bonus_amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return ReferralMilestone.objects.all()


class AdminMilestoneDetailView(viewsets.ModelViewSet):
    """Admin view for creating/updating milestones."""
    serializer_class = MilestoneCreateUpdateSerializer
    permission_classes = [IsAdminUser]
    queryset = ReferralMilestone.objects.all()


class AdminReferralConfigView(viewsets.ModelViewSet):
    """Admin view for managing referral configuration."""
    serializer_class = ReferralConfigSerializer
    permission_classes = [IsAdminUser]
    queryset = ReferralConfig.objects.all()
    
    @action(detail=False, methods=['get', 'post'])
    def config(self, request):
        """Get or update referral configuration."""
        if request.method == 'GET':
            config = ReferralConfig.get_active_config()
            if config:
                serializer = self.get_serializer(config)
                return Response(serializer.data)
            return Response({'message': 'No active configuration found.'})
        
        elif request.method == 'POST':
            # Deactivate all existing configs
            ReferralConfig.objects.filter(is_active=True).update(is_active=False)
            
            # Create new config
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(is_active=True)
            
            return Response(serializer.data, status=status.HTTP_200_OK)


class AdminReferralStatsView(viewsets.ReadOnlyModelViewSet):
    """Admin view for referral statistics."""
    serializer_class = ReferralStatsSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        return UserReferralProfile.objects.all()
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get referral system statistics."""
        from .admin import get_referral_stats
        stats = get_referral_stats()
        return Response(stats)


# Utility Views
class ProcessReferralBonusView(viewsets.GenericViewSet):
    """Utility view for manually processing referral bonuses."""
    permission_classes = [IsAdminUser]
    
    @action(detail=False, methods=['post'])
    def process(self, request):
        """Manually process referral bonus for an investment."""
        investment_id = request.data.get('investment_id')
        amount = request.data.get('amount')
        currency = request.data.get('currency')
        user_id = request.data.get('user_id')
        
        if not all([investment_id, amount, currency, user_id]):
            return Response({
                'success': False,
                'message': 'Missing required fields: investment_id, amount, currency, user_id'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            from app.investment.models import Investment
            
            # Create a real investment object for testing
            from app.investment.models import InvestmentPlan
            
            # Get or create a default plan
            plan, created = InvestmentPlan.objects.get_or_create(
                name="Test Plan",
                defaults={
                    'min_amount': Decimal('100.00'),
                    'max_amount': Decimal('10000.00'),
                    'roi_percentage': Decimal('10.00'),
                    'duration_days': 30,
                    'frequency': 'daily',
                    'breakdown_window_days': 7,
                    'is_active': True
                }
            )
            
            investment = Investment.objects.create(
                user=user,
                amount=Decimal(amount),
                currency=currency,
                plan=plan,
                status='active'
            )
            
            # Process referral bonus
            result = ReferralService.process_investment_referral_bonus(investment)
            
            if result:
                return Response({
                    'success': True,
                    'message': 'Referral bonus processed successfully.'
                })
            else:
                return Response({
                    'success': False,
                    'message': 'Failed to process referral bonus.'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error processing referral bonus: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)


class CheckUserMilestonesView(viewsets.GenericViewSet):
    """Utility view for manually checking user milestones."""
    permission_classes = [IsAdminUser]
    
    @action(detail=False, methods=['post'])
    def check(self, request):
        """Manually check milestones for a user."""
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response({
                'success': False,
                'message': 'Missing user_id field.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check milestones
        triggered_milestones = ReferralService.check_milestones(user)
        
        return Response({
            'success': True,
            'message': f'Found {len(triggered_milestones)} eligible milestones.',
            'triggered_milestones': [milestone.name for milestone in triggered_milestones]
        })
