from rest_framework import serializers
from django.contrib.auth.models import User
from .models import INRWallet, USDTWallet, WalletTransaction, DepositRequest


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class INRWalletSerializer(serializers.ModelSerializer):
    """Serializer for INR Wallet model."""
    
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = INRWallet
        fields = [
            'id', 'user', 'user_id', 'balance', 'status', 
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'balance', 'created_at', 'updated_at']
    
    def validate_balance(self, value):
        """Validate balance is non-negative."""
        if value < 0:
            raise serializers.ValidationError("Balance cannot be negative.")
        return value
    
    def create(self, validated_data):
        """Create INR wallet for user."""
        user_id = validated_data.pop('user_id', None)
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                validated_data['user'] = user
            except User.DoesNotExist:
                raise serializers.ValidationError("User not found.")
        
        return super().create(validated_data)


class USDTWalletSerializer(serializers.ModelSerializer):
    """Serializer for USDT Wallet model."""
    
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = USDTWallet
        fields = [
            'id', 'user', 'user_id', 'balance', 'wallet_address', 
            'status', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'balance', 'created_at', 'updated_at']
    
    def validate_balance(self, value):
        """Validate balance is non-negative."""
        if value < 0:
            raise serializers.ValidationError("Balance cannot be negative.")
        return value
    
    def validate_wallet_address(self, value):
        """Validate wallet address format."""
        if value and len(value) < 26:  # Basic USDT address validation
            raise serializers.ValidationError("Invalid wallet address format.")
        return value
    
    def create(self, validated_data):
        """Create USDT wallet for user."""
        user_id = validated_data.pop('user_id', None)
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                validated_data['user'] = user
            except User.DoesNotExist:
                raise serializers.ValidationError("User not found.")
        
        return super().create(validated_data)


class WalletTransactionSerializer(serializers.ModelSerializer):
    """Serializer for Wallet Transaction model."""
    
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'user', 'user_id', 'transaction_type', 'wallet_type',
            'amount', 'balance_before', 'balance_after', 'status',
            'reference_id', 'description', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'balance_before', 'balance_after', 'created_at', 'updated_at'
        ]
    
    def validate_amount(self, value):
        """Validate amount is positive."""
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value
    
    def validate(self, data):
        """Validate transaction data."""
        # Ensure user_id is provided for creation
        if self.instance is None and 'user_id' not in data:
            raise serializers.ValidationError("user_id is required.")
        
        return data
    
    def create(self, validated_data):
        """Create wallet transaction."""
        user_id = validated_data.pop('user_id', None)
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                validated_data['user'] = user
            except User.DoesNotExist:
                raise serializers.ValidationError("User not found.")
        
        return super().create(validated_data)


class DepositRequestSerializer(serializers.ModelSerializer):
    """Serializer for Deposit Request model."""
    
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    processed_by = UserSerializer(read_only=True)
    
    class Meta:
        model = DepositRequest
        fields = [
            'id', 'user', 'user_id', 'amount', 'payment_method', 'status',
            'reference_number', 'transaction_id', 'screenshot', 'notes',
            'admin_notes', 'processed_by', 'processed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'admin_notes', 'processed_by', 
            'processed_at', 'created_at', 'updated_at'
        ]
    
    def validate_amount(self, value):
        """Validate deposit amount."""
        if value < 100:  # Minimum deposit amount
            raise serializers.ValidationError("Minimum deposit amount is ₹100.")
        if value > 1000000:  # Maximum deposit amount
            raise serializers.ValidationError("Maximum deposit amount is ₹10,00,000.")
        return value
    
    def validate(self, data):
        """Validate deposit request data."""
        # Ensure user_id is provided for creation
        if self.instance is None and 'user_id' not in data:
            raise serializers.ValidationError("user_id is required.")
        
        # Validate payment method specific requirements
        payment_method = data.get('payment_method')
        if payment_method == 'bank_transfer' and not data.get('reference_number'):
            raise serializers.ValidationError("Reference number is required for bank transfers.")
        
        return data
    
    def create(self, validated_data):
        """Create deposit request."""
        user_id = validated_data.pop('user_id', None)
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                validated_data['user'] = user
            except User.DoesNotExist:
                raise serializers.ValidationError("User not found.")
        
        return super().create(validated_data)


class DepositRequestCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for creating deposit requests."""
    
    class Meta:
        model = DepositRequest
        fields = [
            'amount', 'payment_method', 'reference_number', 
            'transaction_id', 'screenshot', 'notes'
        ]
    
    def validate_amount(self, value):
        """Validate deposit amount."""
        if value < 100:
            raise serializers.ValidationError("Minimum deposit amount is ₹100.")
        if value > 1000000:
            raise serializers.ValidationError("Maximum deposit amount is ₹10,00,000.")
        return value


class WalletBalanceSerializer(serializers.Serializer):
    """Serializer for wallet balance response."""
    
    inr_balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    usdt_balance = serializers.DecimalField(max_digits=20, decimal_places=6)
    inr_wallet_status = serializers.CharField()
    usdt_wallet_status = serializers.CharField()
    last_updated = serializers.DateTimeField()


class TransactionHistorySerializer(serializers.Serializer):
    """Serializer for transaction history with pagination."""
    
    transactions = WalletTransactionSerializer(many=True)
    total_count = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    has_next = serializers.BooleanField()
    has_previous = serializers.BooleanField()


class DepositRequestListSerializer(serializers.ModelSerializer):
    """Serializer for listing deposit requests."""
    
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = DepositRequest
        fields = [
            'id', 'user', 'amount', 'payment_method', 'status',
            'reference_number', 'created_at'
        ]
        read_only_fields = fields 