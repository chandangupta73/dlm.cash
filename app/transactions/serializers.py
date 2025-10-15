from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Transaction

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction model."""
    
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    formatted_amount = serializers.CharField(read_only=True)
    is_credit = serializers.BooleanField(read_only=True)
    is_debit = serializers.BooleanField(read_only=True)
    balance_impact = serializers.DecimalField(
        max_digits=20, 
        decimal_places=6, 
        read_only=True
    )
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'user', 'user_id', 'type', 'currency', 'amount', 
            'reference_id', 'meta_data', 'status', 'created_at', 'updated_at',
            'formatted_amount', 'is_credit', 'is_debit', 'balance_impact'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'formatted_amount', 'is_credit', 'is_debit', 'balance_impact']
    
    def validate_amount(self, value):
        """Validate transaction amount."""
        if value <= 0:
            raise serializers.ValidationError("Transaction amount must be positive.")
        return value
    
    def validate_currency(self, value):
        """Validate currency choice."""
        valid_currencies = [choice[0] for choice in Transaction.CURRENCY_CHOICES]
        if value not in valid_currencies:
            raise serializers.ValidationError(f"Invalid currency. Must be one of: {', '.join(valid_currencies)}")
        return value
    
    def validate_type(self, value):
        """Validate transaction type."""
        valid_types = [choice[0] for choice in Transaction.TRANSACTION_TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid transaction type. Must be one of: {', '.join(valid_types)}")
        return value
    
    def validate_status(self, value):
        """Validate transaction status."""
        valid_statuses = [choice[0] for choice in Transaction.STATUS_CHOICES]
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return value
    
    def validate_meta_data(self, value):
        """Validate metadata is a dictionary."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a dictionary.")
        return value
    
    def create(self, validated_data):
        """Create transaction with proper user assignment."""
        user_id = validated_data.pop('user_id', None)
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                validated_data['user'] = user
            except User.DoesNotExist:
                raise serializers.ValidationError("User not found.")
        
        return super().create(validated_data)


class TransactionListSerializer(serializers.ModelSerializer):
    """Serializer for listing transactions with minimal fields."""
    
    user = UserSerializer(read_only=True)
    formatted_amount = serializers.CharField(read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'user', 'type', 'currency', 'amount', 'formatted_amount',
            'status', 'created_at'
        ]
        read_only_fields = fields


class TransactionDetailSerializer(TransactionSerializer):
    """Serializer for detailed transaction view."""
    
    class Meta(TransactionSerializer.Meta):
        fields = TransactionSerializer.Meta.fields + ['meta_data']


class TransactionFilterSerializer(serializers.Serializer):
    """Serializer for transaction filtering parameters."""
    
    type = serializers.ChoiceField(
        choices=Transaction.TRANSACTION_TYPE_CHOICES,
        required=False,
        help_text="Filter by transaction type"
    )
    currency = serializers.ChoiceField(
        choices=Transaction.CURRENCY_CHOICES,
        required=False,
        help_text="Filter by currency"
    )
    status = serializers.ChoiceField(
        choices=Transaction.STATUS_CHOICES,
        required=False,
        help_text="Filter by transaction status"
    )
    date_from = serializers.DateField(
        required=False,
        help_text="Filter transactions from this date (YYYY-MM-DD)"
    )
    date_to = serializers.DateField(
        required=False,
        help_text="Filter transactions up to this date (YYYY-MM-DD)"
    )
    min_amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=6,
        required=False,
        help_text="Minimum transaction amount"
    )
    max_amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=6,
        required=False,
        help_text="Maximum transaction amount"
    )
    search = serializers.CharField(
        required=False,
        help_text="Search in reference_id or metadata"
    )
    
    def validate(self, data):
        """Validate filter parameters."""
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError("Date from cannot be after date to.")
        
        min_amount = data.get('min_amount')
        max_amount = data.get('max_amount')
        
        if min_amount and max_amount and min_amount > max_amount:
            raise serializers.ValidationError("Minimum amount cannot be greater than maximum amount.")
        
        return data


class AdminTransactionUpdateSerializer(serializers.ModelSerializer):
    """Serializer for admin to update transaction status and metadata."""
    
    class Meta:
        model = Transaction
        fields = ['status', 'meta_data']
    
    def validate_status(self, value):
        """Validate status change."""
        if value not in Transaction.STATUS_CHOICES:
            raise serializers.ValidationError("Invalid status.")
        return value
    
    def validate_meta_data(self, value):
        """Validate metadata is a dictionary."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a dictionary.")
        return value


class TransactionExportSerializer(serializers.ModelSerializer):
    """Serializer for CSV export of transactions."""
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    currency_display = serializers.CharField(source='get_currency_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'user_username', 'user_email', 'type_display', 'currency_display',
            'amount', 'status_display', 'reference_id', 'created_at', 'updated_at'
        ]
