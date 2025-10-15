from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for ViewSets
router = DefaultRouter()
router.register(r'transactions', views.TransactionViewSet, basename='transaction')
router.register(r'admin/transactions', views.AdminTransactionViewSet, basename='admin-transaction')

# URL patterns
urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # User endpoints
    path('transactions/', views.user_transactions, name='user-transactions'),
    path('transactions/<uuid:transaction_id>/', views.transaction_detail, name='transaction-detail'),
    
    # Admin endpoints
    path('admin/transactions/', views.admin_transactions, name='admin-transactions'),
    path('admin/transactions/<uuid:transaction_id>/update/', views.admin_transaction_update, name='admin-transaction-update'),
]
