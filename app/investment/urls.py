from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, view

# Create router for ViewSets (user-facing only)
router = DefaultRouter()
router.register(r'investment-plans', views.InvestmentPlanViewSet, basename='investment-plan')
router.register(r'investments', views.InvestmentViewSet, basename='investment')
router.register(r'breakdown-requests', views.BreakdownRequestViewSet, basename='breakdown-request')

# app_name = 'investment'

urlpatterns = [
    # User endpoints only
    path('', include(router.urls)),
    # path('', views.Plans, name='investment_home'),
    path('plans', view.Plans, name='plans'),
    path('buy/<int:plan_id>/', view.select_buy_option, name='select_buy_option'),
    path('buy-request/<int:plan_id>/', view.buy_with_admin, name='buy_with_admin'),
    # path('buy-epin/<int:plan_id>/', view.buy_with_epin, name='buy_with_epin'),
    path('buy-usdt/<int:plan_id>/', view.buy_with_usdt, name='buy_with_usdt'),
]
