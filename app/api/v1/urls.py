from django.urls import path, include
from rest_framework.routers import DefaultRouter
from app.api.v1 import wallet, deposit, moralis_webhook, withdrawals, investment
from app.transactions import views as transaction_views

# Create router for ViewSets
router = DefaultRouter()
router.register(r'wallet-transactions', wallet.WalletTransactionViewSet, basename='wallet-transaction')
router.register(r'usdt-deposits', wallet.USDTDepositViewSet, basename='usdt-deposit')
router.register(r'sweep-logs', wallet.SweepLogViewSet, basename='sweep-log')
router.register(r'deposit-requests', deposit.DepositRequestViewSet, basename='deposit-request')
router.register(r'withdrawals', withdrawals.WithdrawalViewSet, basename='withdrawal')
router.register(r'transactions', transaction_views.TransactionViewSet, basename='transaction')

# URL patterns
urlpatterns = [
    # Withdrawal endpoints (must come BEFORE router to avoid conflicts)
    path('withdraw/', withdrawals.create_withdrawal, name='create-withdrawal'),
    path('withdrawals/user/', withdrawals.user_withdrawals, name='user-withdrawals'),
    path('withdrawals/limits/', withdrawals.withdrawal_limits, name='withdrawal-limits'),
    
    # Include router URLs
    path('', include(router.urls)),
    
    # Wallet endpoints
    path('wallet/balance/', wallet.WalletBalanceView.as_view(), name='wallet-balance'),
    path('wallet/addresses/', wallet.WalletAddressView.as_view(), name='wallet-addresses'),
    path('wallet/address/<str:chain_type>/', wallet.WalletAddressByChainView.as_view(), name='wallet-address-by-chain'),
    path('wallet/add-balance/', wallet.add_balance, name='add-balance'),
    path('wallet/deduct-balance/', wallet.deduct_balance, name='deduct-balance'),
    path('wallet/transaction-history/', wallet.transaction_history, name='transaction-history'),
    path('wallet/transaction-summary/', wallet.transaction_summary, name='transaction-summary'),
    
    # USDT deposit endpoints
    path('usdt/process-deposit/', wallet.process_usdt_deposit, name='process-usdt-deposit'),
    path('usdt/manual-sweep/<uuid:deposit_id>/', wallet.manual_sweep_deposit, name='manual-sweep-deposit'),
    path('usdt/pending-deposits/', wallet.pending_usdt_deposits, name='pending-usdt-deposits'),
    path('usdt/confirmed-deposits/', wallet.confirmed_usdt_deposits, name='confirmed-usdt-deposits'),
    path('usdt/sweep-logs/', wallet.sweep_logs, name='sweep-logs'),
    
    # INR deposit endpoints
    path('deposits/approve/<uuid:deposit_id>/', deposit.approve_deposit, name='approve-deposit'),
    path('deposits/reject/<uuid:deposit_id>/', deposit.reject_deposit, name='reject-deposit'),
    path('deposits/pending/', deposit.pending_deposits, name='pending-deposits'),
    
    # Moralis webhook endpoints
    path('moralis/webhook/usdt/', moralis_webhook.moralis_usdt_webhook, name='moralis-usdt-webhook'),
    path('moralis/webhook/test/', moralis_webhook.moralis_webhook_test, name='moralis-webhook-test'),
    
    # Investment endpoints
    path('investment/', include('app.investment.urls')),
    
    # Transaction endpoints
    path('transactions/', include('app.transactions.urls')),
    
    # User endpoints
    path('', include('app.users.urls')),
] 