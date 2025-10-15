from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()


class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow admin users.
    """
    
    def has_permission(self, request, view):
        # Check if user is authenticated and is admin
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_staff or request.user.is_superuser)
        )


class IsSuperUser(permissions.BasePermission):
    """
    Custom permission to only allow superusers.
    """
    
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_superuser
        )


class IsStaffUser(permissions.BasePermission):
    """
    Custom permission to only allow staff users.
    """
    
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_staff
        )


class AdminActionPermission(permissions.BasePermission):
    """
    Permission for admin actions that require specific admin roles.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Superusers can do everything
        if request.user.is_superuser:
            return True
            
        # Staff users can do most things but not sensitive operations
        if request.user.is_staff:
            # Block sensitive operations for staff users
            sensitive_actions = [
                'admin_override_wallet',
                'delete_user',
                'system_config',
                'bulk_user_operations'
            ]
            
            if hasattr(view, 'action') and view.action in sensitive_actions:
                return False
                
            return True
            
        return False


class WalletOverridePermission(permissions.BasePermission):
    """
    Special permission for wallet override operations.
    Only superusers can override wallet balances.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Only superusers can override wallet balances
        return request.user.is_superuser


class KYCApprovalPermission(permissions.BasePermission):
    """
    Permission for KYC approval operations.
    Staff and superusers can approve KYC.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        return request.user.is_staff or request.user.is_superuser


class WithdrawalApprovalPermission(permissions.BasePermission):
    """
    Permission for withdrawal approval operations.
    Staff and superusers can approve withdrawals.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        return request.user.is_staff or request.user.is_superuser


class InvestmentManagementPermission(permissions.BasePermission):
    """
    Permission for investment management operations.
    Staff and superusers can manage investments.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        return request.user.is_staff or request.user.is_superuser


class ReferralManagementPermission(permissions.BasePermission):
    """
    Permission for referral management operations.
    Staff and superusers can manage referrals.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        return request.user.is_staff or request.user.is_superuser


class AnnouncementPermission(permissions.BasePermission):
    """
    Permission for announcement management operations.
    Staff and superusers can manage announcements.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        return request.user.is_staff or request.user.is_superuser


class UserManagementPermission(permissions.BasePermission):
    """
    Permission for user management operations.
    Staff and superusers can manage users.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        return request.user.is_staff or request.user.is_superuser


class TransactionLogPermission(permissions.BasePermission):
    """
    Permission for transaction log access.
    Staff and superusers can access transaction logs.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        return request.user.is_staff or request.user.is_superuser


def log_admin_action(admin_user, action_type, action_description, target_user=None, 
                    target_model=None, target_id=None, request=None, metadata=None):
    """
    Utility function to log admin actions for audit purposes.
    """
    from .models import AdminActionLog
    
    log_data = {
        'admin_user': admin_user,
        'action_type': action_type,
        'action_description': action_description,
        'target_user': target_user,
        'target_model': target_model,
        'target_id': target_id,
        'metadata': metadata or {}
    }
    
    # Add request information if available
    if request:
        log_data['ip_address'] = self._get_client_ip(request)
        log_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
    
    AdminActionLog.objects.create(**log_data)


def _get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
