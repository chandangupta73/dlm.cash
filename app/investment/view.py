from django.shortcuts import render, redirect, get_object_or_404, reverse, get_list_or_404
from django.contrib.auth.decorators import login_required
from .models import InvestmentPlan, Investment
from django.utils import timezone
from django.http import JsonResponse
import json
from .models import InvestmentPlan
from django.contrib.auth.decorators import login_required
from datetime import datetime
from django.contrib import messages



@login_required(login_url='login')
def Plans(request):
    plans = InvestmentPlan.objects.filter(show_active=True).order_by('package_amount')
    return render(request, 'Plans.html', {'plans': plans})


@login_required(login_url='login')
def select_buy_option(request, plan_id):
    plan = get_object_or_404(InvestmentPlan, id=plan_id)
    return render(request, 'select_buy_option.html', {'plan': plan})


@login_required(login_url='login')
def buy_with_admin(request, plan_id):
    plan = get_object_or_404(InvestmentPlan, id=plan_id)

    if request.method == 'POST':
        investment = Investment.objects.create(
            user=request.user,
            plan=plan,
            amount=plan.package_amount,
            payment_method='admin',
            status='pending',
        )
        messages.success(request, f"Your admin request for '{plan.package_name}' has been submitted.")
        return redirect('plans')

    return redirect('plans')





# @login_required(login_url='login')
# def buy_with_epin(request, plan_id):
#     if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
#         plan = get_object_or_404(InvestmentPlan, pk=plan_id)
#         epin_code_input = request.POST.get('epin_code', '').strip()

#         try:
#             epin_code_obj = EPinCode.objects.select_related('epin').get(code=epin_code_input, is_used=False)
#         except EPinCode.DoesNotExist:
#             return JsonResponse({'status': 'error', 'message': 'Invalid or already used E-Pin code.'})

#         if epin_code_obj.epin.plan != plan:
#             return JsonResponse({'status': 'error', 'message': 'This E-Pin does not match the selected plan.'})

#         if epin_code_obj.epin.expiry_date < timezone.now().date():
#             return JsonResponse({'status': 'error', 'message': 'This E-Pin has expired.'})

#         # Mark E-Pin used
#         epin_code_obj.is_used = True
#         epin_code_obj.save()

#         # Create investment
#         Investment.objects.create(
#             user=request.user,
#             plan=plan,
#             amount=plan.package_amount,
#             payment_method='epin',
#             epin_code=epin_code_input,
#             status='approved'
#         )

#         return JsonResponse({'status': 'success', 'message': 'Your investment request has been submitted with E-Pin.'})

#     return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})



@login_required(login_url='login')
def buy_with_usdt(request, plan_id):
    plan = get_object_or_404(InvestmentPlan, id=plan_id)

    if request.method == 'POST':
        tx_hash = request.POST.get('tx_hash')
        if tx_hash:
            messages.success(request, f"USDT Payment submitted for verification. TX ID: {tx_hash}")
            return redirect('select_buy_option', plan_id=plan.id)
        else:
            messages.error(request, "Transaction ID is required to proceed.")

    return render(request, 'buy_with_usdt.html', {'plan': plan})
