from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for ViewSets
router = DefaultRouter()
router.register(r'transactions', views.WalletTransactionViewSet, basename='wallet-transaction')
router.register(r'deposits', views.DepositRequestViewSet, basename='deposit-request')

# URL patterns
urlpatterns = [
    # Wallet balance
    path('balance/', views.WalletBalanceView.as_view(), name='wallet-balance'),
    
    # Balance operations
    path('add-balance/', views.add_balance, name='add-balance'),
    path('deduct-balance/', views.deduct_balance, name='deduct-balance'),
    
    # Transaction history
    path('transaction-history/', views.transaction_history, name='transaction-history'),
    path('transaction-summary/', views.transaction_summary, name='transaction-summary'),
    
    # Include ViewSet URLs
    path('', include(router.urls)),
    
    # Admin deposit management
    path('admin/approve-deposit/<uuid:deposit_id>/', views.approve_deposit, name='approve-deposit'),
    path('admin/reject-deposit/<uuid:deposit_id>/', views.reject_deposit, name='reject-deposit'),
    path('admin/pending-deposits/', views.pending_deposits, name='pending-deposits'),
] 