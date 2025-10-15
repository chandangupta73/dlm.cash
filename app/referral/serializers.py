from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Referral, ReferralEarning, ReferralMilestone, 
    UserReferralProfile, ReferralConfig
)

User = get_user_model()


class UserReferralProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserReferralProfile model."""
    
    user = serializers.UUIDField(source='user.id', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    referred_by = serializers.UUIDField(source='referred_by.id', read_only=True, allow_null=True)
    referred_by_email = serializers.EmailField(source='referred_by.email', read_only=True, allow_null=True)
    
    class Meta:
        model = UserReferralProfile
        fields = [
            'id', 'user', 'user_email', 'referral_code', 'referred_by', 'referred_by_email',
            'total_referrals', 'total_earnings', 'total_earnings_inr',
            'total_earnings_usdt', 'last_earning_date', 'created_at'
        ]
        read_only_fields = [
            'id', 'user', 'user_email', 'referral_code', 'referred_by', 'referred_by_email',
            'total_referrals', 'total_earnings', 'total_earnings_inr',
            'total_earnings_usdt', 'last_earning_date', 'created_at'
        ]


class ReferralSerializer(serializers.ModelSerializer):
    """Serializer for Referral model."""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    referred_user_email = serializers.EmailField(source='referred_user.email', read_only=True)
    referrer_email = serializers.EmailField(source='referrer.email', read_only=True)
    
    class Meta:
        model = Referral
        fields = [
            'id', 'user_email', 'referred_user_email', 'level',
            'referrer_email', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ReferralEarningSerializer(serializers.ModelSerializer):
    """Serializer for ReferralEarning model."""
    
    user_email = serializers.EmailField(source='referral.user.email', read_only=True)
    referred_user_email = serializers.EmailField(source='referral.referred_user.email', read_only=True)
    investment_id = serializers.UUIDField(source='investment.id', read_only=True)
    
    class Meta:
        model = ReferralEarning
        fields = [
            'id', 'user_email', 'referred_user_email', 'level',
            'amount', 'currency', 'percentage_used', 'status',
            'investment_id', 'created_at', 'credited_at'
        ]
        read_only_fields = ['id', 'created_at', 'credited_at']


class ReferralMilestoneSerializer(serializers.ModelSerializer):
    """Serializer for ReferralMilestone model."""
    
    class Meta:
        model = ReferralMilestone
        fields = [
            'id', 'name', 'description', 'condition_type',
            'condition_value', 'bonus_amount', 'currency',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ReferralConfigSerializer(serializers.ModelSerializer):
    """Serializer for ReferralConfig model."""
    
    class Meta:
        model = ReferralConfig
        fields = [
            'id', 'max_levels', 'level_1_percentage', 'level_2_percentage',
            'level_3_percentage', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ReferralTreeSerializer(serializers.Serializer):
    """Serializer for referral tree data."""
    
    user = serializers.DictField()
    direct_referrals = serializers.ListField()
    sub_referrals = serializers.ListField()
    total_referrals = serializers.IntegerField()
    total_earnings = serializers.CharField()


class ReferralEarningFilterSerializer(serializers.Serializer):
    """Serializer for filtering referral earnings."""
    
    currency = serializers.ChoiceField(
        choices=[('INR', 'INR'), ('USDT', 'USDT')],
        required=False
    )
    level = serializers.IntegerField(
        min_value=1,
        max_value=10,
        required=False
    )
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    status = serializers.ChoiceField(
        choices=[
            ('pending', 'Pending'),
            ('credited', 'Credited'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled')
        ],
        required=False
    )


class ReferralCodeSerializer(serializers.Serializer):
    """Serializer for referral code validation."""
    
    referral_code = serializers.CharField(
        max_length=20,
        min_length=1,
        help_text="Referral code to validate"
    )
    
    def validate_referral_code(self, value):
        """Validate that the referral code exists and is not the user's own code."""
        try:
            profile = UserReferralProfile.objects.get(referral_code=value)
            return value
        except UserReferralProfile.DoesNotExist:
            raise serializers.ValidationError("Invalid referral code")


class ReferralStatsSerializer(serializers.Serializer):
    """Serializer for referral statistics."""
    
    total_referrals = serializers.IntegerField()
    total_earnings_inr = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_earnings_usdt = serializers.DecimalField(max_digits=20, decimal_places=6)
    total_earnings = serializers.DecimalField(max_digits=20, decimal_places=6)
    last_earning_date = serializers.DateTimeField(allow_null=True)
    referral_code = serializers.CharField()


class AdminReferralSearchSerializer(serializers.Serializer):
    """Serializer for admin referral search."""
    
    user_email = serializers.EmailField(required=False)
    level = serializers.IntegerField(min_value=1, max_value=10, required=False)
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    status = serializers.ChoiceField(
        choices=[
            ('all', 'All'),
            ('active', 'Active'),
            ('inactive', 'Inactive')
        ],
        required=False,
        default='all'
    )


class MilestoneCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating milestones."""
    
    class Meta:
        model = ReferralMilestone
        fields = [
            'name', 'description', 'condition_type', 'condition_value',
            'bonus_amount', 'currency', 'is_active'
        ]
    
    def validate(self, data):
        """Validate milestone data."""
        # Ensure condition_value is positive
        if data['condition_value'] <= 0:
            raise serializers.ValidationError("Condition value must be positive")
        
        # Ensure bonus_amount is positive
        if data['bonus_amount'] <= 0:
            raise serializers.ValidationError("Bonus amount must be positive")
        
        return data


class ReferralEarningSummarySerializer(serializers.Serializer):
    """Serializer for referral earnings summary."""
    
    total_earnings = serializers.CharField()
    total_earnings_inr = serializers.CharField()
    total_earnings_usdt = serializers.CharField()
    total_referrals = serializers.IntegerField()
    last_earning_date = serializers.DateTimeField(allow_null=True)
    recent_earnings = serializers.ListField(child=serializers.DictField())
