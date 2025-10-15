from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings


def home(request):
    # Simple home view without database dependencies
    context = {
        'categories': [],
        'blogs': [],
    }
    return render(request, 'index.html', context)


def Contact(request):
    # Simple contact view without database dependencies
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('massage', '').strip()

        # For now, just show success message without database operations
        # TODO: Implement proper contact form handling when needed
        messages.success(request, "Your message has been sent successfully!")
        return redirect('contact-us')

    return render(request, 'contact.html')


# Authentication views - Simple views that serve templates with API integration
def login_view(request):
    """Serve login template with API integration"""
    return render(request, 'login.html')


def registration_view(request):
    """Serve registration template with API integration"""
    return render(request, 'registration.html')


def dashboard_view(request):
    """Serve dashboard template with API integration"""
    return render(request, 'new_dashboard.html')


def logout_view(request):
    """Simple logout view - redirect to home"""
    return redirect('home')


def forgot_password_view(request):
    """Serve forgot password template - simple placeholder"""
    return render(request, 'login.html')  # For now, redirect to login


def profile_view(request):
    """Serve profile template with API integration"""
    # Check if this is the bank details page
    if request.path.endswith('/account/'):
        return render(request, 'bank_details.html')
    else:
        return render(request, 'profile_simple.html')


def send_otp_view(request):
    """Handle OTP sending - return JSON response for AJAX calls"""
    if request.method == 'POST':
        # For now, return a simple success response
        # In a real implementation, this would send OTP via backend API
        from django.http import JsonResponse
        return JsonResponse({'success': True, 'message': 'OTP sent successfully'})
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def validate_referral_view(request):
    """Handle referral validation - return JSON response for AJAX calls"""
    if request.method == 'POST':
        # For now, return a simple success response
        # In a real implementation, this would validate referral via backend API
        from django.http import JsonResponse
        return JsonResponse({'valid': True, 'message': 'Referral code is valid'})
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def wallet_view(request):
    """Serve wallet template with API integration"""
    return render(request, 'wallet.html')


def investments_view(request):
    """Serve investments template with API integration"""
    return render(request, 'investments.html')


def plans_view(request):
    """Serve investment plans template with API integration"""
    return render(request, 'Plans.html')


def buy_plan_view(request, plan_id):
    """View for buying a specific investment plan."""
    return render(request, 'buy_plan.html', {
        'plan_id': plan_id
    })


def usdt_details_view(request):
    """Serve USDT details template with API integration"""
    return render(request, 'usdt_details.html')



