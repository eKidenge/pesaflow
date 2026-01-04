from rest_framework import serializers
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from accounts.serializers import UserSerializer
from .models import Organization, OrganizationType, OrganizationMember


class OrganizationTypeSerializer(serializers.ModelSerializer):
    """Serializer for organization types"""
    
    class Meta:
        model = OrganizationType
        fields = ['id', 'name', 'description', 'icon', 'is_active']
        read_only_fields = ['id']


class OrganizationSerializer(serializers.ModelSerializer):
    """Serializer for organizations"""
    organization_type_name = serializers.CharField(
        source='organization_type.name', 
        read_only=True
    )
    created_by_email = serializers.EmailField(
        source='created_by.email', 
        read_only=True
    )
    member_count = serializers.SerializerMethodField()
    active_customer_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'legal_name', 'organization_type', 'organization_type_name',
            'phone_number', 'email', 'website', 'address', 'city', 'county', 'country',
            'postal_code', 'registration_number', 'tax_id', 'business_license',
            'currency', 'timezone', 'status', 'is_verified', 'is_active',
            'logo', 'primary_color', 'secondary_color', 'mpesa_paybill',
            'mpesa_till_number', 'payment_methods', 'subscription_plan',
            'subscription_status', 'subscription_expiry', 'max_users',
            'max_customers', 'monthly_transaction_limit', 'settings',
            'metadata', 'created_by', 'created_by_email', 'created_at',
            'updated_at', 'member_count', 'active_customer_count'
        ]
        read_only_fields = [
            'id', 'created_by', 'created_at', 'updated_at', 'is_verified',
            'member_count', 'active_customer_count'
        ]
    
    def get_member_count(self, obj):
        return obj.members.count()
    
    def get_active_customer_count(self, obj):
        from customers.models import Customer
        return Customer.objects.filter(organization=obj, status='active').count()
    
    def validate_email(self, value):
        # Check if email is already used by another organization
        if self.instance:
            if Organization.objects.filter(email=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError(
                    'An organization with this email already exists.'
                )
        else:
            if Organization.objects.filter(email=value).exists():
                raise serializers.ValidationError(
                    'An organization with this email already exists.'
                )
        return value
    
    def validate_phone_number(self, value):
        # Check if phone number is already used by another organization
        if self.instance:
            if Organization.objects.filter(phone_number=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError(
                    'An organization with this phone number already exists.'
                )
        else:
            if Organization.objects.filter(phone_number=value).exists():
                raise serializers.ValidationError(
                    'An organization with this phone number already exists.'
                )
        return value


class OrganizationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating organizations"""
    
    class Meta:
        model = Organization
        fields = [
            'name', 'legal_name', 'organization_type', 'phone_number',
            'email', 'website', 'address', 'city', 'county', 'country',
            'postal_code', 'registration_number', 'tax_id', 'business_license',
            'currency', 'timezone', 'logo', 'primary_color', 'secondary_color',
            'mpesa_paybill', 'mpesa_till_number', 'payment_methods',
            'subscription_plan'
        ]
    
    def create(self, validated_data):
        # Set default values
        validated_data.setdefault('status', 'pending')
        validated_data.setdefault('subscription_status', 'trial')
        
        # Create organization
        organization = Organization.objects.create(**validated_data)
        return organization


class OrganizationSettingsSerializer(serializers.ModelSerializer):
    """Serializer for organization settings"""
    
    class Meta:
        model = Organization
        fields = [
            'settings', 'payment_methods', 'mpesa_paybill', 'mpesa_till_number',
            'primary_color', 'secondary_color', 'logo', 'timezone', 'currency'
        ]


class OrganizationStatisticsSerializer(serializers.Serializer):
    """Serializer for organization statistics"""
    total_customers = serializers.IntegerField()
    active_customers = serializers.IntegerField()
    total_users = serializers.IntegerField()
    total_payments = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    pending_invoices = serializers.IntegerField()
    overdue_invoices = serializers.IntegerField()
    payment_methods = serializers.DictField()


class OrganizationMemberSerializer(serializers.ModelSerializer):
    """Serializer for organization members"""
    user_details = UserSerializer(source='user', read_only=True)
    invited_by_email = serializers.EmailField(source='invited_by.email', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    
    class Meta:
        model = OrganizationMember
        fields = [
            'id', 'organization', 'organization_name', 'user', 'user_details',
            'role', 'can_manage_payments', 'can_manage_customers',
            'can_manage_staff', 'can_view_reports', 'is_active',
            'invited_by', 'invited_by_email', 'invitation_accepted',
            'joined_at', 'updated_at'
        ]
        read_only_fields = ['id', 'invited_by', 'joined_at', 'updated_at']
    
    def validate(self, data):
        # Check if user is already a member of the organization
        if self.instance is None:  # Only check on creation
            organization = data.get('organization')
            user = data.get('user')
            
            if organization and user:
                if OrganizationMember.objects.filter(
                    organization=organization,
                    user=user
                ).exists():
                    raise serializers.ValidationError({
                        'user': 'This user is already a member of the organization.'
                    })
        
        return data