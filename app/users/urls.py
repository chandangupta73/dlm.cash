from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'bank-details', views.BankDetailsViewSet, basename='bank-details')
router.register(r'usdt-details', views.USDTDetailsViewSet, basename='usdt-details')

urlpatterns = [
    path('auth/register/', views.register_user, name='user-register'),
    path('auth/login/', views.login_user, name='user-login'),
    
    path('profile/', views.user_profile, name='user-profile'),
    path('', include(router.urls)),
] 