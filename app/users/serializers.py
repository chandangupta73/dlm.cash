from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
from .models import OTP, BankDetails, USDTDetails

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 
            'phone_number', 'password', 'password_confirm'
        ]
        read_only_fields = ['id']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    email = serializers.EmailField()
    password = serializers.CharField()
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            user = authenticate(username=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Must include email and password')
        
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'phone_number', 'date_of_birth', 'address', 'city', 
            'state', 'country', 'postal_code', 'is_kyc_verified', 
            'kyc_status', 'email_verified', 'phone_verified',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BankDetailsSerializer(serializers.ModelSerializer):
    """Serializer for BankDetails model"""
    
    class Meta:
        model = BankDetails
        fields = [
            'id', 'account_holder_name', 'account_number', 'ifsc_code',
            'bank_name', 'branch_address', 'is_verified', 'verified_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_verified', 'verified_at', 'created_at', 'updated_at']
    
    def validate_account_number(self, value):
        """Validate account number format."""
        # Remove any spaces or special characters
        clean_value = ''.join(filter(str.isdigit, str(value)))
        if len(clean_value) < 8 or len(clean_value) > 20:
            raise serializers.ValidationError("Account number must be between 8 and 20 digits.")
        return clean_value
    
    def validate_ifsc_code(self, value):
        """Validate IFSC code format."""
        # Remove any spaces or special characters
        clean_value = ''.join(filter(str.isalnum, str(value)))
        if len(clean_value) < 6 or len(clean_value) > 12:
            raise serializers.ValidationError("IFSC code must be between 6 and 12 characters.")
        return clean_value.upper()


class USDTDetailsSerializer(serializers.ModelSerializer):
    """Serializer for USDTDetails model"""
    
    network_display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = USDTDetails
        fields = [
            'id', 'user', 'wallet_address', 'network', 'qr_code',
            'is_verified', 'verified_at', 'created_at', 'updated_at',
            'network_display_name'
        ]
        read_only_fields = ['id', 'user', 'is_verified', 'verified_at', 'created_at', 'updated_at']
    
    def get_network_display_name(self, obj):
        """Get the display name for the network"""
        network_names = {
            'erc20': 'ERC20 (Ethereum)',
            'bep20': 'BEP20 (Binance Smart Chain)',
            'trc20': 'TRC20 (Tron)',
            'polygon': 'Polygon',
            'arbitrum': 'Arbitrum',
            'optimism': 'Optimism'
        }
        return network_names.get(obj.network, obj.network.upper())
    
    def validate_wallet_address(self, value):
        """Validate USDT wallet address format"""
        if not value or len(value) < 26:
            raise serializers.ValidationError("Invalid USDT wallet address format")
        return value
    
    def validate_network(self, value):
        """Validate network choice"""
        valid_networks = ['erc20', 'bep20', 'trc20', 'polygon', 'arbitrum', 'optimism']
        if value not in valid_networks:
            raise serializers.ValidationError("Invalid network selection")
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile with bank details and USDT details."""
    
    bank_details = BankDetailsSerializer(read_only=True)
    usdt_details = USDTDetailsSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'phone_number',
            'is_kyc_verified', 'kyc_status', 'date_of_birth', 'address', 'city',
            'state', 'country', 'postal_code', 'email_verified', 'phone_verified',
            'bank_details', 'usdt_details', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile"""
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone_number', 'date_of_birth',
            'address', 'city', 'state', 'country', 'postal_code'
        ]


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change"""
    old_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match")
        return attrs
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect')
        return value


class OTPRequestSerializer(serializers.Serializer):
    """Serializer for OTP request"""
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False)
    otp_type = serializers.ChoiceField(choices=[('EMAIL', 'Email'), ('PHONE', 'Phone')])
    
    def validate(self, attrs):
        if attrs['otp_type'] == 'EMAIL' and not attrs.get('email'):
            raise serializers.ValidationError('Email is required for email OTP')
        if attrs['otp_type'] == 'PHONE' and not attrs.get('phone_number'):
            raise serializers.ValidationError('Phone number is required for phone OTP')
        return attrs


class OTPVerifySerializer(serializers.Serializer):
    """Serializer for OTP verification"""
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False)
    otp_code = serializers.CharField(max_length=6)
    otp_type = serializers.ChoiceField(choices=[('EMAIL', 'Email'), ('PHONE', 'Phone')])
    
    def validate(self, attrs):
        if attrs['otp_type'] == 'EMAIL' and not attrs.get('email'):
            raise serializers.ValidationError('Email is required for email OTP verification')
        if attrs['otp_type'] == 'PHONE' and not attrs.get('phone_number'):
            raise serializers.ValidationError('Phone number is required for phone OTP verification')
        return attrs


class UserListSerializer(serializers.ModelSerializer):
    """Serializer for listing users (admin only)"""
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'phone_number', 'is_kyc_verified', 'kyc_status', 'is_active',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at'] 