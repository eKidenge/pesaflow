from rest_framework import serializers
from django.core.validators import MinValueValidator
from .models import Payment, Invoice, PaymentPlan


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for payments"""
    organization_name = serializers.CharField(
        source='organization.name', 
        read_only=True
    )
    customer_name = serializers.SerializerMethodField()
    customer_phone = serializers.CharField(
        source='customer.phone_number', 
        read_only=True
    )
    created_by_email = serializers.EmailField(
        source='created_by.email', 
        read_only=True
    )
    
    class Meta:
        model = Payment
        fields = [
            'id', 'organization', 'organization_name', 'customer', 'customer_name',
            'customer_phone', 'payment_reference', 'external_reference',
            'description', 'payment_type', 'amount', 'currency', 'transaction_fee',
            'net_amount', 'payment_method', 'mpesa_checkout_request_id',
            'mpesa_merchant_request_id', 'status', 'initiated_at', 'completed_at',
            'payer_phone', 'payer_name', 'payer_email', 'metadata', 'notes',
            'is_reversed', 'reversal_reason', 'reversed_at', 'created_by',
            'created_by_email', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'payment_reference', 'net_amount', 'created_by', 
            'created_at', 'updated_at'
        ]
    
    def get_customer_name(self, obj):
        if obj.customer:
            return f"{obj.customer.first_name} {obj.customer.last_name}"
        return None
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Amount must be greater than zero.')
        return value


class PaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payments"""
    
    class Meta:
        model = Payment
        fields = [
            'customer', 'amount', 'currency', 'payment_method',
            'payment_type', 'description', 'payer_phone', 'payer_name',
            'payer_email', 'transaction_fee', 'notes'
        ]
    
    def create(self, validated_data):
        # Get organization and created_by from context
        organization = self.context.get('organization')
        created_by = self.context.get('created_by')
        
        if not organization:
            raise serializers.ValidationError('Organization is required.')
        
        # Set default values
        validated_data.setdefault('status', 'pending')
        validated_data.setdefault('currency', 'KES')
        
        # Create payment
        payment = Payment.objects.create(
            organization=organization,
            created_by=created_by,
            **validated_data
        )
        
        return payment


class PaymentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating payments"""
    
    class Meta:
        model = Payment
        fields = [
            'status', 'external_reference', 'transaction_fee', 'notes',
            'is_reversed', 'reversal_reason'
        ]
    
    def validate(self, data):
        instance = self.instance
        
        # Check if payment can be reversed
        if data.get('is_reversed') and not instance.is_reversed:
            if instance.status != 'completed':
                raise serializers.ValidationError({
                    'is_reversed': 'Only completed payments can be reversed.'
                })
        
        return data


class MpesaSTKPushSerializer(serializers.Serializer):
    """Serializer for M-Pesa STK Push payment initiation"""
    phone_number = serializers.CharField(required=True)
    amount = serializers.DecimalField(
        required=True, 
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(1)]
    )
    description = serializers.CharField(required=False, default='Payment via PesaFlow')
    payment_type = serializers.CharField(required=False, default='other')
    
    def validate_phone_number(self, value):
        # Format phone number for M-Pesa (ensure it starts with 254)
        if value.startswith('0'):
            value = '254' + value[1:]
        elif value.startswith('+'):
            value = value[1:]
        
        # Ensure it's 12 digits
        if not value.isdigit() or len(value) != 12:
            raise serializers.ValidationError('Invalid phone number format.')
        
        return value
    
    def validate_amount(self, value):
        if value < 1:
            raise serializers.ValidationError('Amount must be at least 1 KSH.')
        if value > 150000:
            raise serializers.ValidationError('Amount cannot exceed 150,000 KSH.')
        return value


class PaymentReversalSerializer(serializers.Serializer):
    """Serializer for payment reversal"""
    reason = serializers.CharField(required=True, max_length=500)


class PaymentStatisticsSerializer(serializers.Serializer):
    """Serializer for payment statistics"""
    total_payments = serializers.IntegerField()
    completed_payments = serializers.IntegerField()
    failed_payments = serializers.IntegerField()
    success_rate = serializers.FloatField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_payment = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_transaction_fees = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    daily_revenue = serializers.ListField()
    payment_method_distribution = serializers.DictField()


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer for invoices"""
    organization_name = serializers.CharField(
        source='organization.name', 
        read_only=True
    )
    customer_name = serializers.SerializerMethodField()
    customer_phone = serializers.CharField(
        source='customer.phone_number', 
        read_only=True
    )
    customer_email = serializers.EmailField(
        source='customer.email', 
        read_only=True
    )
    created_by_email = serializers.EmailField(
        source='created_by.email', 
        read_only=True
    )
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'organization', 'organization_name', 'customer', 'customer_name',
            'customer_phone', 'customer_email', 'invoice_number', 'reference',
            'issue_date', 'due_date', 'paid_date', 'subtotal', 'tax_amount',
            'discount_amount', 'total_amount', 'amount_paid', 'balance_due',
            'status', 'items', 'terms_and_conditions', 'notes', 'payment_link',
            'payment_link_expiry', 'created_by', 'created_by_email', 'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id', 'invoice_number', 'balance_due', 'created_by', 
            'created_at', 'updated_at'
        ]
    
    def get_customer_name(self, obj):
        if obj.customer:
            return f"{obj.customer.first_name} {obj.customer.last_name}"
        return None
    
    def validate(self, data):
        # Validate dates
        if data.get('due_date') and data.get('issue_date'):
            if data['due_date'] < data['issue_date']:
                raise serializers.ValidationError({
                    'due_date': 'Due date must be after issue date.'
                })
        
        # Validate amounts
        if data.get('total_amount') and data['total_amount'] <= 0:
            raise serializers.ValidationError({
                'total_amount': 'Total amount must be greater than zero.'
            })
        
        return data


class InvoiceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating invoices"""
    
    class Meta:
        model = Invoice
        fields = [
            'customer', 'reference', 'issue_date', 'due_date', 'subtotal',
            'tax_amount', 'discount_amount', 'total_amount', 'items',
            'terms_and_conditions', 'notes'
        ]
    
    def create(self, validated_data):
        # Get organization and created_by from context
        organization = self.context.get('organization')
        created_by = self.context.get('created_by')
        
        if not organization:
            raise serializers.ValidationError('Organization is required.')
        
        # Create invoice
        invoice = Invoice.objects.create(
            organization=organization,
            created_by=created_by,
            **validated_data
        )
        
        return invoice


class PaymentPlanSerializer(serializers.ModelSerializer):
    """Serializer for payment plans"""
    organization_name = serializers.CharField(
        source='organization.name', 
        read_only=True
    )
    customer_name = serializers.SerializerMethodField()
    customer_phone = serializers.CharField(
        source='customer.phone_number', 
        read_only=True
    )
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentPlan
        fields = [
            'id', 'organization', 'organization_name', 'customer', 'customer_name',
            'customer_phone', 'name', 'description', 'total_amount', 'amount_paid',
            'balance', 'start_date', 'end_date', 'number_of_installments',
            'installment_amount', 'status', 'metadata', 'created_at', 'updated_at',
            'progress_percentage'
        ]
        read_only_fields = [
            'id', 'balance', 'installment_amount', 'created_at', 'updated_at',
            'progress_percentage'
        ]
    
    def get_customer_name(self, obj):
        if obj.customer:
            return f"{obj.customer.first_name} {obj.customer.last_name}"
        return None
    
    def get_progress_percentage(self, obj):
        if obj.total_amount > 0:
            return (obj.amount_paid / obj.total_amount) * 100
        return 0
    
    def validate(self, data):
        # Validate dates
        if data.get('end_date') and data.get('start_date'):
            if data['end_date'] < data['start_date']:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after start date.'
                })
        
        # Validate amounts
        if data.get('total_amount') and data['total_amount'] <= 0:
            raise serializers.ValidationError({
                'total_amount': 'Total amount must be greater than zero.'
            })
        
        # Validate installments
        if data.get('number_of_installments') and data['number_of_installments'] <= 0:
            raise serializers.ValidationError({
                'number_of_installments': 'Number of installments must be greater than zero.'
            })
        
        return data


class PaymentPlanCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payment plans"""
    
    class Meta:
        model = PaymentPlan
        fields = [
            'customer', 'name', 'description', 'total_amount', 'start_date',
            'end_date', 'number_of_installments', 'metadata'
        ]
    
    def create(self, validated_data):
        # Get organization from context
        organization = self.context.get('organization')
        
        if not organization:
            raise serializers.ValidationError('Organization is required.')
        
        # Calculate installment amount
        total_amount = validated_data['total_amount']
        installments = validated_data['number_of_installments']
        installment_amount = total_amount / installments
        
        # Create payment plan
        payment_plan = PaymentPlan.objects.create(
            organization=organization,
            installment_amount=installment_amount,
            balance=total_amount,
            **validated_data
        )
        
        return payment_plan