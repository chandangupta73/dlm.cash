from rest_framework import serializers
from .models import InvestmentPlan, Investment, BreakdownRequest
from app.users.models import User


class InvestmentPlanSerializer(serializers.ModelSerializer):
    """Serializer for InvestmentPlan model."""
    
    class Meta:
        model = InvestmentPlan
        fields = [
            'id', 'name', 'description', 'fixed_amount',
            'roi_rate', 'frequency', 'duration_days', 'breakdown_window_days',
            'status', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate that fixed_amount is positive."""
        if data.get('fixed_amount') and data.get('fixed_amount') <= 0:
            raise serializers.ValidationError(
                "Fixed amount must be greater than 0."
            )
        return data


class InvestmentPlanListSerializer(serializers.ModelSerializer):
    """Serializer for listing investment plans (user view)."""
    
    class Meta:
        model = InvestmentPlan
        fields = [
            'id', 'name', 'description', 'fixed_amount',
            'roi_rate', 'frequency', 'duration_days', 'breakdown_window_days'
        ]


class InvestmentSerializer(serializers.ModelSerializer):
    """Serializer for Investment model."""
    
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_roi_rate = serializers.DecimalField(
        source='plan.roi_rate', 
        max_digits=5, 
        decimal_places=2, 
        read_only=True
    )
    plan_frequency = serializers.CharField(source='plan.frequency', read_only=True)
    plan_duration_days = serializers.IntegerField(source='plan.duration_days', read_only=True)
    can_breakdown = serializers.BooleanField(read_only=True)
    breakdown_amount = serializers.DecimalField(
        max_digits=20, 
        decimal_places=6, 
        read_only=True
    )
    
    class Meta:
        model = Investment
        fields = [
            'id', 'plan', 'plan_name', 'plan_roi_rate', 'plan_frequency', 'plan_duration_days',
            'amount', 'currency', 'payment_method', 'start_date', 'end_date', 'roi_accrued',
            'last_roi_credit', 'next_roi_date', 'status', 'is_active',
            'can_breakdown', 'breakdown_amount', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'plan_name', 'plan_roi_rate', 'plan_frequency', 'plan_duration_days',
            'start_date', 'end_date', 'roi_accrued', 'last_roi_credit',
            'next_roi_date', 'status', 'is_active', 'can_breakdown',
            'breakdown_amount', 'created_at', 'updated_at'
        ]
    
    def to_representation(self, instance):
        """Add computed fields to representation."""
        data = super().to_representation(instance)
        data['can_breakdown'] = instance.can_breakdown()
        data['breakdown_amount'] = instance.get_breakdown_amount()
        return data


class InvestmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new investments."""
    
    payment_method = serializers.CharField(required=False, default='direct_payment')
    
    class Meta:
        model = Investment
        fields = ['plan', 'amount', 'currency', 'payment_method']
        extra_kwargs = {
            'payment_method': {'write_only': False}
        }
    
    def validate(self, data):
        """Validate investment creation."""
        plan = data['plan']
        amount = data['amount']
        currency = data['currency']
        payment_method = data.get('payment_method', 'direct_payment')
        user = self.context['request'].user
        
        # Debug logging for validation
        print(f"DEBUG VALIDATION: Received data - plan: {plan}, amount: {amount}, currency: {currency}, payment_method: {payment_method}")
        print(f"DEBUG VALIDATION: Data keys: {list(data.keys())}")
        print(f"DEBUG VALIDATION: Raw data: {data}")
        

        
        # Check if plan is active
        if not plan.is_active or plan.status != 'active':
            raise serializers.ValidationError("Selected plan is not available.")
        
        # Check amount matches fixed plan amount (convert to Decimal for comparison)
        from decimal import Decimal
        amount_decimal = Decimal(str(amount))
        plan_amount_decimal = Decimal(str(plan.fixed_amount))
        
        # For USDT payments, convert plan amount to USDT equivalent
        if currency.upper() == 'USDT':
            # Assuming 1 USDT = ₹83 (this should be configurable)
            usdt_rate = Decimal('83')
            expected_usdt_amount = (plan_amount_decimal / usdt_rate).quantize(Decimal('0.000001'))
            
            if amount_decimal != expected_usdt_amount:
                raise serializers.ValidationError(
                    f"Amount must be exactly {expected_usdt_amount} USDT for this plan (₹{plan.fixed_amount} / ₹83)"
                )
        else:
            # For INR payments, amount must match exactly
            if amount_decimal != plan_amount_decimal:
                raise serializers.ValidationError(
                    f"Amount must be exactly {plan.fixed_amount} INR for this plan"
                )
        
        # Check user KYC status
        if not user.is_kyc_verified:
            raise serializers.ValidationError("KYC verification required to invest.")
        
        # For direct payments, check wallet balance
        if payment_method == 'direct_payment':
            if currency.upper() == 'INR':
                wallet = user.inr_wallet
            else:  # USDT
                wallet = user.usdt_wallet
            
            if not wallet.can_transact():
                raise serializers.ValidationError(f"Your {currency.upper()} wallet is not active.")
            
            if wallet.balance < amount:
                raise serializers.ValidationError(
                    f"Insufficient {currency.upper()} balance. Required: {amount}, Available: {wallet.balance}"
                )
        
        return data
    
    def create(self, validated_data):
        """Create investment with proper wallet management."""
        from django.db import transaction
        
        user = self.context['request'].user
        plan = validated_data['plan']
        amount = validated_data['amount']
        currency = validated_data['currency']
        payment_method = validated_data.get('payment_method', 'direct_payment')
        
        # Debug logging
        print(f"DEBUG CREATE: Creating investment with payment_method: {payment_method}")
        print(f"DEBUG CREATE: Will set status to: {'active' if payment_method == 'direct_payment' else 'pending_admin_approval'}")
        print(f"DEBUG CREATE: Investment data - user: {user.username}, plan: {plan.name}, amount: {amount}, currency: {currency}")
        print(f"DEBUG CREATE: Validated data keys: {list(validated_data.keys())}")
        print(f"DEBUG CREATE: Payment method from validated_data: {validated_data.get('payment_method', 'NOT_FOUND')}")
        
        # Use database transaction to ensure consistency
        with transaction.atomic():
            # Create the investment
            investment = Investment.objects.create(
                user=user,
                plan=plan,
                amount=amount,
                currency=currency,
                payment_method=payment_method,  # Explicitly set payment_method
                status='active' if payment_method == 'direct_payment' else 'pending_admin_approval'
            )
            
            print(f"DEBUG CREATE: Investment created with ID: {investment.id}, status: {investment.status}, payment_method: {investment.payment_method}")
            print(f"DEBUG CREATE: Investment payment_method field value: {getattr(investment, 'payment_method', 'FIELD_NOT_FOUND')}")
            
            # For direct payments, deduct from wallet and create transaction
            if payment_method == 'direct_payment':
                self._process_direct_payment(user, amount, currency, investment)
            
            return investment
    
    def _process_direct_payment(self, user, amount, currency, investment):
        """Process direct payment by deducting from wallet and creating transaction."""
        from app.wallet.models import WalletTransaction
        from decimal import Decimal
        
        try:
            if currency.upper() == 'INR':
                # Get INR wallet and deduct balance
                inr_wallet = user.inr_wallet
                balance_before = inr_wallet.balance
                
                print(f"DEBUG WALLET: Processing INR payment - Amount: {amount}, Balance Before: {balance_before}")
                
                # Check if sufficient balance
                if inr_wallet.balance < amount:
                    raise serializers.ValidationError(f"Insufficient INR balance. Required: {amount}, Available: {inr_wallet.balance}")
                
                # Deduct balance and save
                success = inr_wallet.deduct_balance(amount)
                print(f"DEBUG WALLET: INR deduction success: {success}, New balance: {inr_wallet.balance}")
                
                if not success:
                    raise serializers.ValidationError("Failed to deduct INR balance")
                
                inr_wallet.save()
                print(f"DEBUG WALLET: INR wallet saved, final balance: {inr_wallet.balance}")
                
                # Create transaction record
                transaction = WalletTransaction.objects.create(
                    user=user,
                    transaction_type='investment_purchase',
                    amount=Decimal(str(amount)).quantize(Decimal('0.01')),
                    wallet_type='inr',
                    status='completed',
                    reference_id=str(investment.id),
                    description=f'Investment in {investment.plan.name}',
                    balance_before=balance_before,
                    balance_after=inr_wallet.balance
                )
                print(f"DEBUG WALLET: INR transaction created: {transaction.id}")
                
            else:  # USDT
                # Get USDT wallet and deduct balance
                usdt_wallet = user.usdt_wallet
                balance_before = usdt_wallet.balance
                
                print(f"DEBUG WALLET: Processing USDT payment - Amount: {amount}, Balance Before: {balance_before}")
                
                # Check if sufficient balance
                if usdt_wallet.balance < amount:
                    raise serializers.ValidationError(f"Insufficient USDT balance. Required: {amount}, Available: {usdt_wallet.balance}")
                
                # Deduct balance and save
                success = usdt_wallet.deduct_balance(amount)
                print(f"DEBUG WALLET: USDT deduction success: {success}, New balance: {usdt_wallet.balance}")
                
                if not success:
                    raise serializers.ValidationError("Failed to deduct USDT balance")
                
                usdt_wallet.save()
                print(f"DEBUG WALLET: USDT wallet saved, final balance: {usdt_wallet.balance}")
                
                # Create transaction record
                transaction = WalletTransaction.objects.create(
                    user=user,
                    transaction_type='investment_purchase',
                    amount=Decimal(str(amount)).quantize(Decimal('0.000001')),
                    wallet_type='usdt',
                    status='completed',
                    reference_id=str(investment.id),
                    description=f'Investment in {investment.plan.name}',
                    balance_before=balance_before,
                    balance_after=usdt_wallet.balance
                )
                print(f"DEBUG WALLET: USDT transaction created: {transaction.id}")
                
        except Exception as e:
            # If wallet deduction fails, delete the investment and raise error
            print(f"DEBUG WALLET: Error in payment processing: {str(e)}")
            investment.delete()
            raise serializers.ValidationError(f"Payment processing failed: {str(e)}")


class BreakdownRequestSerializer(serializers.ModelSerializer):
    """Serializer for BreakdownRequest model."""
    
    investment_details = InvestmentSerializer(source='investment', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = BreakdownRequest
        fields = [
            'id', 'user', 'user_username', 'investment', 'investment_details',
            'requested_amount', 'final_amount', 'status', 'admin_notes',
            'processed_by', 'processed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user_username', 'investment_details', 'final_amount',
            'status', 'processed_by', 'processed_at', 'created_at', 'updated_at'
        ]


class BreakdownRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating breakdown requests."""
    
    class Meta:
        model = BreakdownRequest
        fields = ['investment']
    
    def validate(self, data):
        """Validate breakdown request creation."""
        investment = data['investment']
        user = self.context['request'].user
        
        # Check if investment belongs to user
        if investment.user != user:
            raise serializers.ValidationError("Investment not found.")
        
        # Check if investment can be broken down
        if not investment.can_breakdown():
            raise serializers.ValidationError("Investment cannot be broken down.")
        
        # Check if breakdown request already exists
        if hasattr(investment, 'breakdown_request'):
            raise serializers.ValidationError("Breakdown request already exists for this investment.")
        
        return data
    
    def create(self, validated_data):
        """Create breakdown request with computed fields."""
        investment = validated_data['investment']
        user = self.context['request'].user
        
        # Calculate final amount
        final_amount = investment.get_breakdown_amount()
        
        # Create breakdown request
        breakdown_request = BreakdownRequest.objects.create(
            user=user,
            investment=investment,
            requested_amount=investment.amount,
            final_amount=final_amount
        )
        
        # Request breakdown on investment
        investment.request_breakdown()
        
        return breakdown_request


class BreakdownRequestAdminSerializer(serializers.ModelSerializer):
    """Serializer for admin operations on breakdown requests."""
    
    investment_details = InvestmentSerializer(source='investment', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = BreakdownRequest
        fields = [
            'id', 'user', 'user_username', 'investment', 'investment_details',
            'requested_amount', 'final_amount', 'status', 'admin_notes',
            'processed_by', 'processed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'user_username', 'investment', 'investment_details',
            'requested_amount', 'final_amount', 'status', 'processed_by',
            'processed_at', 'created_at', 'updated_at'
        ]


class InvestmentStatsSerializer(serializers.Serializer):
    """Serializer for investment statistics."""
    
    total_investments = serializers.IntegerField()
    active_investments = serializers.IntegerField()
    total_invested = serializers.DecimalField(max_digits=20, decimal_places=6)
    total_roi_earned = serializers.DecimalField(max_digits=20, decimal_places=6)
    pending_breakdowns = serializers.IntegerField()
    completed_investments = serializers.IntegerField()
