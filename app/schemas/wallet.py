from rest_framework import serializers
from django.contrib.auth import get_user_model
from app.wallet.models import (
    INRWallet, USDTWallet, WalletTransaction, DepositRequest,
    WalletAddress, USDTDepositRequest, SweepLog
)

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class WalletAddressSerializer(serializers.ModelSerializer):
    """Serializer for Wallet Address model."""
    
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = WalletAddress
        fields = [
            'id', 'user', 'chain_type', 'address', 'status', 
            'is_active', 'last_used', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'address', 'created_at', 'updated_at']
    
    def validate_address(self, value):
        """Validate wallet address format."""
        if value and len(value) < 26:
            raise serializers.ValidationError("Invalid wallet address format.")
        return value


class WalletAddressesSerializer(serializers.Serializer):
    """Serializer for multiple wallet addresses."""
    
    erc20 = serializers.CharField(allow_null=True)
    bep20 = serializers.CharField(allow_null=True)
    
    def to_representation(self, instance):
        """Convert queryset to dictionary format."""
        addresses = {}
        for address in instance:
            if address.chain_type in ['erc20', 'bep20']:
                addresses[address.chain_type] = address.address
        return addresses


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
        """Create USDT wallet for user."""
        user_id = validated_data.pop('user_id', None)
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                validated_data['user'] = user
            except User.DoesNotExist:
                raise serializers.ValidationError("User not found.")
        
        return super().create(validated_data)


class USDTDepositRequestSerializer(serializers.ModelSerializer):
    """Serializer for USDT Deposit Request model."""
    
    user = UserSerializer(read_only=True)
    processed_by = UserSerializer(read_only=True)
    
    class Meta:
        model = USDTDepositRequest
        fields = [
            'id', 'user', 'chain_type', 'amount', 'transaction_hash', 'from_address', 'to_address',
            'status', 'sweep_type', 'sweep_tx_hash', 'gas_fee', 'block_number',
            'confirmation_count', 'required_confirmations', 'processed_by', 
            'processed_at', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'sweep_tx_hash', 'gas_fee', 'block_number',
            'confirmation_count', 'required_confirmations', 'processed_by', 
            'processed_at', 'created_at', 'updated_at'
        ]
    
    def validate_amount(self, value):
        """Validate USDT amount."""
        if value < 0.000001:
            raise serializers.ValidationError("Minimum USDT amount is 0.000001.")
        if value > 10000.000000:
            raise serializers.ValidationError("Maximum USDT amount is 10,000 USDT.")
        return value
    
    def validate_chain_type(self, value):
        """Validate chain type."""
        if value not in ['trc20', 'erc20', 'bep20']:
            raise serializers.ValidationError("Invalid chain type.")
        return value
    
    def validate_transaction_hash(self, value):
        """Validate transaction hash format."""
        if value and len(value) < 10:
            raise serializers.ValidationError("Invalid transaction hash format.")
        return value


class SweepLogSerializer(serializers.ModelSerializer):
    """Serializer for Sweep Log model."""
    
    user = UserSerializer(read_only=True)
    initiated_by = UserSerializer(read_only=True)
    
    class Meta:
        model = SweepLog
        fields = [
            'id', 'user', 'chain_type', 'from_address', 'to_address', 'amount', 'gas_fee',
            'transaction_hash', 'sweep_type', 'status', 'initiated_by',
            'error_message', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'transaction_hash', 'status', 'error_message', 
            'created_at', 'updated_at'
        ]
    
    def validate_chain_type(self, value):
        """Validate chain type."""
        if value not in ['trc20', 'erc20', 'bep20']:
            raise serializers.ValidationError("Invalid chain type.")
        return value


class WalletTransactionSerializer(serializers.ModelSerializer):
    """Serializer for Wallet Transaction model."""
    
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'user', 'user_id', 'transaction_type', 'wallet_type', 'chain_type',
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
    
    def validate_chain_type(self, value):
        """Validate chain type if provided."""
        if value and value not in ['trc20', 'erc20', 'bep20']:
            raise serializers.ValidationError("Invalid chain type.")
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
    
    def to_representation(self, instance):
        """Transform service data to frontend expected format."""
        # instance is the dict returned by WalletService.get_wallet_balance()
        inr_wallet = {
            'balance': instance.get('inr_balance', 0),
            'status': instance.get('inr_wallet_status', 'active'),
            'is_active': instance.get('inr_wallet_status', 'active') == 'active'
        }
        
        usdt_wallet = {
            'balance': instance.get('usdt_balance', 0),
            'status': instance.get('usdt_wallet_status', 'active'),
            'is_active': instance.get('usdt_wallet_status', 'active') == 'active'
        }
        
        return {
            'inr_wallet': inr_wallet,
            'usdt_wallet': usdt_wallet,
            'wallet_addresses': instance.get('wallet_addresses', {}),
            'last_updated': instance.get('last_updated')
        }


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