from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Withdrawal, WithdrawalSettings
import json
from django.db import models
from django.db.models import Sum
from app.wallet.models import INRWallet, USDTWallet
from django.utils import timezone

print("🚀 WithdrawalRequestSerializer is being loaded!")

User = get_user_model()


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    """Serializer for creating withdrawal requests."""
    
    payout_details = serializers.JSONField()  # Accept JSON input
    
    class Meta:
        model = Withdrawal
        fields = [
            'currency', 'amount', 'payout_method', 'payout_details'
        ]
    
    def validate(self, attrs):
        """Validate withdrawal request data."""
        print("🔍 VALIDATE METHOD CALLED!")
        
        user = self.context['request'].user
        currency = attrs.get('currency')
        amount = attrs.get('amount')
        payout_method = attrs.get('payout_method')
        payout_details = attrs.get('payout_details')
        
        print(f"🔍 VALIDATION DEBUG - Currency: {currency}, Amount: {amount}, Method: {payout_method}")
        print(f"🔍 VALIDATION DEBUG - Payout Details: {payout_details}")
        print(f"🔍 VALIDATION DEBUG - User KYC: {user.kyc_status}")
        
        # Check if user's KYC is approved
        if user.kyc_status != 'APPROVED':
            print(f"❌ VALIDATION FAILED - KYC not approved: {user.kyc_status}")
            raise serializers.ValidationError("KYC must be approved before making withdrawals")
        
        # Check if user has pending withdrawal for same currency
        if Withdrawal.has_pending_withdrawal(user, currency):
            print(f"❌ VALIDATION FAILED - Pending withdrawal exists for {currency}")
            raise serializers.ValidationError(f"You already have a pending {currency} withdrawal request")
        
        # Check daily withdrawal limit
        within_limit, message = Withdrawal.check_daily_limit(user, currency, amount)
        if not within_limit:
            print(f"❌ VALIDATION FAILED - Daily limit exceeded: {message}")
            raise serializers.ValidationError(message)
        
        # Validate minimum amount
        limits = Withdrawal.get_withdrawal_limits()
        min_amount = limits.get(currency, {}).get('min', 0)
        if amount < min_amount:
            print(f"❌ VALIDATION FAILED - Amount {amount} below minimum {min_amount}")
            raise serializers.ValidationError(f"Minimum withdrawal amount for {currency} is {min_amount}")
        
        # Validate payout details format
        try:
            if isinstance(payout_details, str):
                payout_data = json.loads(payout_details)
            else:
                payout_data = payout_details
            print(f"🔍 VALIDATION DEBUG - Payout data parsed: {payout_data}")
        except (json.JSONDecodeError, TypeError) as e:
            print(f"❌ VALIDATION FAILED - Payout details parsing error: {e}")
            raise serializers.ValidationError("Invalid payout details format. Must be valid JSON.")
        
        # Currency and payout method compatibility
        if currency == 'INR' and payout_method not in ['bank_transfer']:
            print(f"❌ VALIDATION FAILED - Invalid INR payout method: {payout_method}")
            raise serializers.ValidationError("Invalid payout method for INR currency. Only Bank Transfer is supported.")
        elif currency == 'USDT' and payout_method not in ['usdt_erc20', 'usdt_bep20', 'usdt_trc20']:
            print(f"❌ VALIDATION FAILED - Invalid USDT payout method: {payout_method}")
            raise serializers.ValidationError("Invalid payout method for USDT currency")
        
        # Check wallet balance
        try:
            if currency == 'INR':
                wallet = INRWallet.objects.get(user=user)
                fee = Withdrawal.calculate_fee(currency, amount)
                total_required = amount + fee
                
                # Get total pending withdrawals for this currency
                total_pending = Withdrawal.objects.filter(
                    user=user,
                    currency=currency,
                    status='PENDING'
                ).aggregate(
                    total=models.Sum('amount')
                )['total'] or 0
                
                # Calculate total required including pending withdrawals
                total_required_with_pending = total_required + total_pending
                
                print(f"🔍 VALIDATION DEBUG - INR Wallet - Balance: {wallet.balance}, Required: {total_required}, Fee: {fee}")
                print(f"🔍 VALIDATION DEBUG - Total Pending: {total_pending}, Total Required with Pending: {total_required_with_pending}")
                
                if wallet.balance < total_required_with_pending:
                    print(f"❌ VALIDATION FAILED - Insufficient INR balance (including pending)")
                    raise serializers.ValidationError(f"Insufficient INR balance. Required: ₹{total_required_with_pending} (including ₹{total_pending} pending), Available: ₹{wallet.balance}")
                
                if not wallet.can_transact():
                    print(f"❌ VALIDATION FAILED - INR wallet not active")
                    raise serializers.ValidationError("INR wallet is not active for transactions")
            
            elif currency == 'USDT':
                wallet = USDTWallet.objects.get(user=user)
                fee = Withdrawal.calculate_fee(currency, amount)
                total_required = amount + fee
                
                # Get total pending withdrawals for this currency
                total_pending = Withdrawal.objects.filter(
                    user=user,
                    currency=currency,
                    status='PENDING'
                ).aggregate(
                    total=models.Sum('amount')
                )['total'] or 0
                
                # Calculate total required including pending withdrawals
                total_required_with_pending = total_required + total_pending
                
                print(f"🔍 VALIDATION DEBUG - USDT Wallet - Balance: {wallet.balance}, Required: {total_required}, Fee: {fee}")
                print(f"🔍 VALIDATION DEBUG - Total Pending: {total_pending}, Total Required with Pending: {total_required_with_pending}")
                
                if wallet.balance < total_required_with_pending:
                    print(f"❌ VALIDATION FAILED - Insufficient USDT balance (including pending)")
                    raise serializers.ValidationError(f"Insufficient USDT balance. Required: ${total_required_with_pending} (including ${total_pending} pending), Available: ${wallet.balance}")
                
                if not wallet.can_transact():
                    print(f"❌ VALIDATION FAILED - USDT wallet not active")
                    raise serializers.ValidationError("USDT wallet is not active for transactions")
        
        except (INRWallet.DoesNotExist, USDTWallet.DoesNotExist) as e:
            print(f"❌ VALIDATION FAILED - Wallet not found: {e}")
            raise serializers.ValidationError(f"{currency} wallet not found")
        
        print(f"✅ VALIDATION PASSED - All checks successful")
        
        # Validate payout details based on method
        try:
            self._validate_payout_details(payout_method, payout_details)
            print(f"✅ Payout details validation passed")
        except Exception as e:
            print(f"❌ VALIDATION FAILED - Payout details validation error: {str(e)}")
            raise
        
        return attrs
    
    def _validate_payout_details(self, payout_method, payout_details):
        """Validate payout details based on the payout method."""
        if not payout_details:
            raise serializers.ValidationError("Payout details are required")
        
        if payout_method == 'bank_transfer':
            # For bank transfer, we need account details
            required_fields = ['account_number', 'ifsc_code', 'account_holder_name', 'bank_name']
            for field in required_fields:
                if not payout_details.get(field):
                    raise serializers.ValidationError(f"Bank transfer requires {field.replace('_', ' ')}")
        
        elif payout_method.startswith('usdt_'):
            # For USDT, we need wallet address and network
            if not payout_details.get('wallet_address'):
                raise serializers.ValidationError("USDT withdrawal requires wallet address")
            if not payout_details.get('network'):
                raise serializers.ValidationError("USDT withdrawal requires network specification")
        
        return True
    
    def create(self, validated_data):
        """Create withdrawal request and deduct balance immediately."""
        user = self.context['request'].user
        request = self.context['request']
        
        currency = validated_data['currency']
        amount = validated_data['amount']
        
        # Convert payout_details to JSON string if it's a dict
        if isinstance(validated_data.get('payout_details'), dict):
            validated_data['payout_details'] = json.dumps(validated_data['payout_details'])
        
        # Calculate fee
        fee = Withdrawal.calculate_fee(currency, amount)
        validated_data['fee'] = fee
        
        # Add tracking information
        validated_data['user'] = user
        validated_data['ip_address'] = self.get_client_ip(request)
        validated_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
        
        # Convert payout_details to JSON string if needed
        if not isinstance(validated_data['payout_details'], str):
            validated_data['payout_details'] = json.dumps(validated_data['payout_details'])
        
        # Create withdrawal instance
        withdrawal = Withdrawal.objects.create(**validated_data)
        
        # Immediately deduct balance to prevent double-spending
        self.deduct_wallet_balance(withdrawal)
        
        # Create transaction log
        self.create_transaction_log(withdrawal)

        # if currency == 'USDT' and amount <= 100:
        #     print(f"✅ Auto-approving small USDT withdrawal (Amount: {amount})")
        #     withdrawal.status = 'APPROVED'
        #     withdrawal.admin_notes = "Auto-approved (≤100 USDT)"
        #     withdrawal.save(update_fields=['status', 'admin_notes'])

        # 🔍 Get admin-defined auto-approve limits
        settings = WithdrawalSettings.objects.first()
        usdt_limit = settings.auto_approve_usdt_limit if settings else 100
        inr_limit = settings.auto_approve_inr_limit if settings else 0

        # ✅ Auto-approve if below limit
        if (currency == 'USDT' and amount <= usdt_limit) or (currency == 'INR' and amount <= inr_limit):
            withdrawal.status = 'APPROVED'
            withdrawal.admin_notes = f"Auto-approved by system (≤ {amount} {currency})"
            # withdrawal.processed_by = "system"
            withdrawal.processed_at = timezone.now()
            withdrawal.save(update_fields=['status', 'admin_notes', 'processed_at'])

            print(f"✅ Auto-approved {currency} withdrawal for {user.email}: Amount = {amount}")
        
        return withdrawal    
    
    def deduct_wallet_balance(self, withdrawal):
        """Deduct withdrawal amount from user's wallet."""
        from app.wallet.models import INRWallet, USDTWallet
        
        # Calculate total amount (amount + fee)
        total_amount = withdrawal.amount + withdrawal.fee
        
        if withdrawal.currency == 'INR':
            wallet = INRWallet.objects.get(user=withdrawal.user)
            if not wallet.deduct_balance(total_amount):
                raise serializers.ValidationError("Failed to deduct balance from INR wallet")
            # Save the wallet after deduction
            wallet.save()
        
        elif withdrawal.currency == 'USDT':
            wallet = USDTWallet.objects.get(user=withdrawal.user)
            if not wallet.deduct_balance(total_amount):
                raise serializers.ValidationError("Failed to deduct balance from USDT wallet")
            # Save the wallet after deduction
            wallet.save()
    
    def create_transaction_log(self, withdrawal):
        """Create transaction log for withdrawal request."""
        from app.wallet.models import WalletTransaction, INRWallet, USDTWallet
        
        # Calculate total amount (amount + fee)
        total_amount = withdrawal.amount + withdrawal.fee
        
        # Get current wallet balance after deduction
        if withdrawal.currency == 'INR':
            wallet = INRWallet.objects.get(user=withdrawal.user)
            wallet_type = 'inr'
        else:
            wallet = USDTWallet.objects.get(user=withdrawal.user)
            wallet_type = 'usdt'
        
        WalletTransaction.objects.create(
            user=withdrawal.user,
            transaction_type='withdrawal',
            wallet_type=wallet_type,
            amount=total_amount,
            balance_before=wallet.balance + total_amount,
            balance_after=wallet.balance,
            status='pending',
            reference_id=str(withdrawal.id),
            description=f"Withdrawal request - {withdrawal.payout_method}",
            metadata={
                'withdrawal_id': str(withdrawal.id),
                'payout_method': withdrawal.payout_method,
                'fee': str(withdrawal.fee)
            }
        )
    
    def get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    


class WithdrawalSerializer(serializers.ModelSerializer):
    """Serializer for withdrawal details (read-only)."""
    
    user_email = serializers.CharField(source='user.email', read_only=True)
    payout_details_parsed = serializers.SerializerMethodField()
    total_amount = serializers.DecimalField(max_digits=20, decimal_places=6, read_only=True)
    net_amount = serializers.DecimalField(max_digits=20, decimal_places=6, read_only=True)
    
    class Meta:
        model = Withdrawal
        fields = [
            'id', 'user_email', 'currency', 'amount', 'fee', 'total_amount', 'net_amount',
            'payout_method', 'payout_details', 'payout_details_parsed', 'status',
            'tx_hash', 'chain_type', 'gas_fee', 'processed_by', 'processed_at',
            'admin_notes', 'rejection_reason', 'created_at', 'updated_at'
        ]
    

    
    def get_payout_details_parsed(self, obj):
        """Parse payout details JSON for display."""
        try:
            return json.loads(obj.payout_details) if isinstance(obj.payout_details, str) else obj.payout_details
        except (json.JSONDecodeError, TypeError):
            return {}


class AdminWithdrawalSerializer(serializers.ModelSerializer):
    """Serializer for admin withdrawal management."""
    
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_kyc_status = serializers.CharField(source='user.kyc_status', read_only=True)
    payout_details_parsed = serializers.SerializerMethodField()
    total_amount = serializers.DecimalField(max_digits=20, decimal_places=6, read_only=True)
    net_amount = serializers.DecimalField(max_digits=20, decimal_places=6, read_only=True)
    
    class Meta:
        model = Withdrawal
        fields = [
            'id', 'user_email', 'user_kyc_status', 'currency', 'amount', 'fee', 
            'total_amount', 'net_amount', 'payout_method', 'payout_details', 
            'payout_details_parsed', 'status', 'tx_hash', 'chain_type', 'gas_fee',
            'processed_by', 'processed_at', 'admin_notes', 'rejection_reason',
            'ip_address', 'user_agent', 'created_at', 'updated_at'
        ]
    
    def get_payout_details_parsed(self, obj):
        """Parse payout details JSON for display."""
        try:
            return json.loads(obj.payout_details) if isinstance(obj.payout_details, str) else obj.payout_details
        except (json.JSONDecodeError, TypeError):
            return {}


class WithdrawalApprovalSerializer(serializers.Serializer):
    """Serializer for withdrawal approval."""
    
    admin_notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        withdrawal = self.context['withdrawal']
        
        if not withdrawal.can_be_processed():
            raise serializers.ValidationError("Withdrawal cannot be processed in current status")
        
        return attrs


class WithdrawalRejectionSerializer(serializers.Serializer):
    """Serializer for withdrawal rejection."""
    
    rejection_reason = serializers.CharField(required=True)
    
    def validate(self, attrs):
        withdrawal = self.context['withdrawal']
        
        if not withdrawal.can_be_processed():
            raise serializers.ValidationError("Withdrawal cannot be processed in current status")
        
        if not attrs.get('rejection_reason'):
            raise serializers.ValidationError("Rejection reason is required")
        
        return attrs


class WithdrawalCompletionSerializer(serializers.Serializer):
    """Serializer for withdrawal completion (USDT with tx_hash)."""
    
    tx_hash = serializers.CharField(required=False, allow_blank=True)
    admin_notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        withdrawal = self.context['withdrawal']
        
        if withdrawal.status != 'APPROVED':
            raise serializers.ValidationError("Withdrawal must be approved before completion")
        
        # For USDT withdrawals, tx_hash is required
        if withdrawal.currency == 'USDT' and not attrs.get('tx_hash'):
            raise serializers.ValidationError("Transaction hash is required for USDT withdrawals")
        
        return attrs


class WithdrawalLimitsSerializer(serializers.Serializer):
    """Serializer for withdrawal limits information."""
    
    currency = serializers.ChoiceField(choices=['INR', 'USDT'])
    
    def to_representation(self, instance):
        """Return withdrawal limits for the specified currency."""
        currency = self.context.get('currency', 'INR')
        limits = Withdrawal.get_withdrawal_limits()
        
        return {
            'currency': currency,
            'limits': limits.get(currency, {}),
            'current_usage': self.get_current_usage(currency)
        }
    
    def get_current_usage(self, currency):
        """Get current day's withdrawal usage for the user."""
        user = self.context['request'].user
        from django.utils import timezone
        from decimal import Decimal
        
        today = timezone.now().date()
        
        today_withdrawals = Withdrawal.objects.filter(
            user=user,
            currency=currency,
            created_at__date=today,
            status__in=['PENDING', 'APPROVED', 'PROCESSING', 'COMPLETED']
        ).aggregate(
            total=serializers.models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        limits = Withdrawal.get_withdrawal_limits()
        max_limit = Decimal(str(limits[currency]['max']))  # Convert float to Decimal
        
        return {
            'today_total': today_withdrawals,
            'remaining': max_limit - today_withdrawals  # Now both are Decimal
        }
