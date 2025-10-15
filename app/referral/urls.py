from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'referral'

# User-facing URLs
user_patterns = [
    path('profile/', views.ReferralProfileView.as_view({'get': 'list'}), name='profile'),
    path('tree/', views.ReferralTreeView.as_view({'get': 'tree'}), name='tree'),
    path('earnings/', views.ReferralEarningsView.as_view({'get': 'list'}), name='earnings'),
    path('earnings-summary/', views.ReferralEarningsSummaryView.as_view({'get': 'summary'}), name='earnings-summary'),
    path('validate-code/', views.ValidateReferralCodeView.as_view({'post': 'validate'}), name='validate-code'),
]

# Admin-facing URLs
admin_router = DefaultRouter()
admin_router.register(r'referrals', views.AdminReferralListView, basename='admin-referral-list')
admin_router.register(r'earnings', views.AdminReferralEarningListView, basename='admin-earning-list')
admin_router.register(r'milestones', views.AdminMilestoneListView, basename='admin-milestone-list')
admin_router.register(r'milestone', views.AdminMilestoneDetailView, basename='admin-milestone-detail')
admin_router.register(r'config', views.AdminReferralConfigView, basename='admin-config')
admin_router.register(r'stats', views.AdminReferralStatsView, basename='admin-stats')

# Utility URLs
utility_patterns = [
    path('process-bonus/', views.ProcessReferralBonusView.as_view({'post': 'process'}), name='process-bonus'),
    path('check-milestones/', views.CheckUserMilestonesView.as_view({'post': 'check'}), name='check-milestones'),
]

# Combine all patterns
urlpatterns = [
    # User endpoints
    path('', include(user_patterns)),
    
    # Admin endpoints
    path('admin/', include(admin_router.urls)),
    
    # Utility endpoints
    path('utility/', include(utility_patterns)),
]
