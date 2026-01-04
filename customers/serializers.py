from rest_framework import serializers
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .models import Customer, CustomerGroup


class CustomerSerializer(serializers.ModelSerializer):
    """Serializer for customers"""
    organization_name = serializers.CharField(
        source='organization.name', 
        read_only=True
    )
    created_by_email = serializers.EmailField(
        source='created_by.email', 
        read_only=True
    )
    full_name = serializers.SerializerMethodField()
    groups_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Customer
        fields = [
            'id', 'customer_code', 'organization', 'organization_name',
            'first_name', 'middle_name', 'last_name', 'full_name',
            'email', 'phone_number', 'alternate_phone', 'gender',
            'date_of_birth', 'nationality', 'national_id', 'passport_number',
            'address', 'city', 'county', 'postal_code', 'customer_type',
            'registration_number', 'account_balance', 'credit_limit',
            'discount_rate', 'status', 'tags', 'guardian_name',
            'guardian_phone', 'guardian_relationship', 'employer_name',
            'employer_address', 'school_name', 'course', 'year_of_study',
            'receive_sms', 'receive_email', 'receive_whatsapp',
            'preferred_language', 'custom_fields', 'notes', 'created_by',
            'created_by_email', 'created_at', 'updated_at', 'last_payment_date',
            'groups_count'
        ]
        read_only_fields = [
            'id', 'customer_code', 'created_by', 'created_at', 
            'updated_at', 'last_payment_date', 'groups_count'
        ]
    
    def get_full_name(self, obj):
        names = [obj.first_name]
        if obj.middle_name:
            names.append(obj.middle_name)
        names.append(obj.last_name)
        return ' '.join(names)
    
    def get_groups_count(self, obj):
        return obj.groups.count()
    
    def validate_phone_number(self, value):
        instance = getattr(self, 'instance', None)
        organization = self.context.get('organization')
        
        if instance:
            # Check if phone number is being changed
            if value != instance.phone_number:
                # Check if another customer in the same organization has this phone
                if Customer.objects.filter(
                    organization=instance.organization,
                    phone_number=value
                ).exclude(id=instance.id).exists():
                    raise serializers.ValidationError(
                        'A customer with this phone number already exists in this organization.'
                    )
        elif organization:
            # Check if phone number already exists in this organization
            if Customer.objects.filter(
                organization=organization,
                phone_number=value
            ).exists():
                raise serializers.ValidationError(
                    'A customer with this phone number already exists in this organization.'
                )
        
        return value
    
    def validate_email(self, value):
        if not value:
            return value
        
        instance = getattr(self, 'instance', None)
        organization = self.context.get('organization')
        
        try:
            validate_email(value)
        except ValidationError:
            raise serializers.ValidationError('Enter a valid email address.')
        
        if instance and value:
            if value != instance.email:
                if Customer.objects.filter(
                    organization=instance.organization,
                    email=value
                ).exclude(id=instance.id).exists():
                    raise serializers.ValidationError(
                        'A customer with this email already exists in this organization.'
                    )
        elif organization and value:
            if Customer.objects.filter(
                organization=organization,
                email=value
            ).exists():
                raise serializers.ValidationError(
                    'A customer with this email already exists in this organization.'
                )
        
        return value


class CustomerCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating customers"""
    
    class Meta:
        model = Customer
        fields = [
            'first_name', 'middle_name', 'last_name', 'email', 'phone_number',
            'alternate_phone', 'gender', 'date_of_birth', 'nationality',
            'national_id', 'passport_number', 'address', 'city', 'county',
            'postal_code', 'customer_type', 'registration_number',
            'credit_limit', 'discount_rate', 'tags', 'guardian_name',
            'guardian_phone', 'guardian_relationship', 'employer_name',
            'employer_address', 'school_name', 'course', 'year_of_study',
            'receive_sms', 'receive_email', 'receive_whatsapp',
            'preferred_language', 'custom_fields', 'notes'
        ]
        required_fields = ['first_name', 'phone_number', 'customer_type']
    
    def create(self, validated_data):
        # Get organization from context
        organization = self.context.get('organization')
        created_by = self.context.get('created_by')
        
        if not organization:
            raise serializers.ValidationError('Organization is required.')
        
        # Create customer
        customer = Customer.objects.create(
            organization=organization,
            created_by=created_by,
            **validated_data
        )
        
        return customer


class CustomerUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating customers"""
    
    class Meta:
        model = Customer
        fields = [
            'first_name', 'middle_name', 'last_name', 'email', 'phone_number',
            'alternate_phone', 'gender', 'date_of_birth', 'nationality',
            'national_id', 'passport_number', 'address', 'city', 'county',
            'postal_code', 'customer_type', 'registration_number',
            'account_balance', 'credit_limit', 'discount_rate', 'status',
            'tags', 'guardian_name', 'guardian_phone', 'guardian_relationship',
            'employer_name', 'employer_address', 'school_name', 'course',
            'year_of_study', 'receive_sms', 'receive_email', 'receive_whatsapp',
            'preferred_language', 'custom_fields', 'notes'
        ]


class CustomerStatisticsSerializer(serializers.Serializer):
    """Serializer for customer statistics"""
    total_customers = serializers.IntegerField()
    active_customers = serializers.IntegerField()
    inactive_customers = serializers.IntegerField()
    recent_customers = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_payment = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_payments = serializers.IntegerField()
    customer_type_distribution = serializers.DictField()
    account_balance_summary = serializers.DictField()


class CustomerImportSerializer(serializers.Serializer):
    """Serializer for customer import"""
    file = serializers.FileField(required=True)
    
    def validate_file(self, value):
        # Check file extension
        if not value.name.endswith('.csv'):
            raise serializers.ValidationError('Only CSV files are allowed.')
        
        # Check file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if value.size > max_size:
            raise serializers.ValidationError('File size must be less than 5MB.')
        
        return value


class CustomerGroupSerializer(serializers.ModelSerializer):
    """Serializer for customer groups"""
    organization_name = serializers.CharField(
        source='organization.name', 
        read_only=True
    )
    customer_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomerGroup
        fields = [
            'id', 'organization', 'organization_name', 'name', 'description',
            'group_type', 'is_active', 'default_payment_amount',
            'payment_frequency', 'customers', 'metadata', 'created_at',
            'updated_at', 'customer_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'customer_count']
    
    def get_customer_count(self, obj):
        return obj.customers.count()
    
    def validate_name(self, value):
        instance = getattr(self, 'instance', None)
        organization = self.context.get('organization')
        
        if instance:
            # Check if name is being changed and already exists in organization
            if value != instance.name:
                if CustomerGroup.objects.filter(
                    organization=instance.organization,
                    name=value
                ).exclude(id=instance.id).exists():
                    raise serializers.ValidationError(
                        'A group with this name already exists in this organization.'
                    )
        elif organization:
            # Check if name already exists in organization
            if CustomerGroup.objects.filter(
                organization=organization,
                name=value
            ).exists():
                raise serializers.ValidationError(
                    'A group with this name already exists in this organization.'
                )
        
        return value