from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AdminDashboardView, AdminUserViewSet, AdminKYCViewSet, AdminWalletViewSet,
    AdminInvestmentViewSet, AdminWithdrawalViewSet, AdminReferralViewSet,
    AdminTransactionViewSet, AdminAnnouncementViewSet, AdminActionLogViewSet,
    AdminInvestmentPlanViewSet, AdminBreakdownRequestViewSet, UserAnnouncementView
)

# Create router for ViewSets
router = DefaultRouter()
router.register(r'users', AdminUserViewSet, basename='admin-users')
router.register(r'kyc', AdminKYCViewSet, basename='admin-kyc')
router.register(r'wallet', AdminWalletViewSet, basename='admin-wallet')
router.register(r'investments', AdminInvestmentViewSet, basename='admin-investments')
router.register(r'investment-plans', AdminInvestmentPlanViewSet, basename='admin-investment-plans')
router.register(r'breakdown-requests', AdminBreakdownRequestViewSet, basename='admin-breakdown-requests')
router.register(r'withdrawals', AdminWithdrawalViewSet, basename='admin-withdrawals')
router.register(r'referrals', AdminReferralViewSet, basename='admin-referrals')
router.register(r'transactions', AdminTransactionViewSet, basename='admin-transactions')
router.register(r'announcements', AdminAnnouncementViewSet, basename='admin-announcements')
router.register(r'action-logs', AdminActionLogViewSet, basename='admin-action-logs')

app_name = 'admin_panel'

urlpatterns = [
    # Dashboard
    path('dashboard/summary/', AdminDashboardView.as_view(), name='admin-dashboard-summary'),
    
    # User-facing endpoints
    path('announcements/user/', UserAnnouncementView.as_view(), name='user-announcements'),
    
    # Include router URLs
    path('', include(router.urls)),
]
