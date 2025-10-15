from django.urls import path, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
# from .views import welcome_page
from . import views

urlpatterns = [
    # Welcome page - Basic routes that templates expect
    path('', views.home, name='home'),
    path('contact-us', views.Contact, name='contact-us'),
    path('ckeditor/', include('ckeditor_uploader.urls')),

    # Authentication routes - Basic routes that templates expect
    path('auth/login/', views.login_view, name='login'),
    path('auth/sign-up/', views.registration_view, name='sign-up'),
    path('auth/dashboard/', views.dashboard_view, name='dashboard'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/forgot-password/', views.forgot_password_view, name='forgot-password'),
    path('auth/profile/', views.profile_view, name='profile'),
    path('profile/account/', views.profile_view, name='profile-account'),
    path('profile/usdt-details/', views.usdt_details_view, name='usdt-details'),
    path('auth/wallet/', views.wallet_view, name='wallet'),
    path('auth/investments/', views.investments_view, name='investments'),
    path('auth/send-otp/', views.send_otp_view, name='send_otp'),
    path('auth/validate-referral/', views.validate_referral_view, name='validate_referral'),
    
    path('admin/', admin.site.urls),
    
    # User authentication and management (MUST come FIRST to avoid conflicts)
    path('api/v1/', include('app.users.urls')),
    
    # KYC system
    path('api/v1/kyc/', include('app.kyc.urls')),
    
    # Admin Panel
    path('api/v1/admin/', include('app.admin_panel.urls')),
    
    # Referral system
    path('api/v1/referrals/', include('app.referral.urls', namespace='referral')),
    
    # Investment system
    path('api/v1/investment/', include('app.investment.urls')),
    
    # Withdrawals system
    path('api/v1/', include('app.withdrawals.urls')),
    
    # Wallet and deposit system (general api/v1/ routes) - MUST come LAST
    path('api/v1/', include('app.api.v1.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)