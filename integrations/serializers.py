from rest_framework import serializers
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from .models import Integration, IntegrationType, APILog


class IntegrationTypeSerializer(serializers.ModelSerializer):
    """Serializer for integration types"""
    
    class Meta:
        model = IntegrationType
        fields = ['id', 'name', 'provider', 'category', 'documentation_url', 'is_active']
        read_only_fields = ['id']


class IntegrationSerializer(serializers.ModelSerializer):
    """Serializer for integrations"""
    integration_type_name = serializers.CharField(
        source='integration_type.name', 
        read_only=True
    )
    organization_name = serializers.CharField(
        source='organization.name', 
        read_only=True
    )
    created_by_email = serializers.EmailField(
        source='created_by.email', 
        read_only=True
    )
    
    class Meta:
        model = Integration
        fields = [
            'id', 'organization', 'organization_name', 'integration_type',
            'integration_type_name', 'name', 'environment', 'api_key',
            'api_secret', 'api_url', 'consumer_key', 'consumer_secret',
            'passkey', 'webhook_url', 'webhook_secret', 'status',
            'is_default', 'settings', 'metadata', 'last_used',
            'total_requests', 'successful_requests', 'failed_requests',
            'created_by', 'created_by_email', 'created_at', 'updated_at',
            'validated_at'
        ]
        read_only_fields = [
            'id', 'created_by', 'created_at', 'updated_at', 'validated_at',
            'last_used', 'total_requests', 'successful_requests', 'failed_requests'
        ]
        extra_kwargs = {
            'api_key': {'write_only': True},
            'api_secret': {'write_only': True},
            'consumer_key': {'write_only': True},
            'consumer_secret': {'write_only': True},
            'passkey': {'write_only': True},
            'webhook_secret': {'write_only': True},
        }
    
    def validate_api_url(self, value):
        if value:
            validator = URLValidator()
            try:
                validator(value)
            except ValidationError:
                raise serializers.ValidationError('Enter a valid URL.')
        return value
    
    def validate_webhook_url(self, value):
        if value:
            validator = URLValidator()
            try:
                validator(value)
            except ValidationError:
                raise serializers.ValidationError('Enter a valid URL.')
        return value


class IntegrationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating integrations"""
    
    class Meta:
        model = Integration
        fields = [
            'integration_type', 'name', 'environment', 'api_key', 'api_secret',
            'api_url', 'consumer_key', 'consumer_secret', 'passkey',
            'webhook_url', 'settings'
        ]
    
    def create(self, validated_data):
        # Get organization and created_by from context
        organization = self.context.get('organization')
        created_by = self.context.get('created_by')
        
        if not organization:
            raise serializers.ValidationError('Organization is required.')
        
        # Set default values
        validated_data.setdefault('status', 'inactive')
        
        # Create integration
        integration = Integration.objects.create(
            organization=organization,
            created_by=created_by,
            **validated_data
        )
        
        return integration


class IntegrationUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating integrations"""
    
    class Meta:
        model = Integration
        fields = [
            'name', 'environment', 'api_key', 'api_secret', 'api_url',
            'consumer_key', 'consumer_secret', 'passkey', 'webhook_url',
            'status', 'is_default', 'settings', 'metadata'
        ]
        extra_kwargs = {
            'api_key': {'write_only': True},
            'api_secret': {'write_only': True},
            'consumer_key': {'write_only': True},
            'consumer_secret': {'write_only': True},
            'passkey': {'write_only': True},
            'webhook_secret': {'write_only': True},
        }


class IntegrationTestSerializer(serializers.Serializer):
    """Serializer for testing integrations"""
    test_type = serializers.ChoiceField(
        choices=['authentication', 'balance', 'sms', 'email', 'whatsapp']
    )
    test_phone = serializers.CharField(required=False)
    test_email = serializers.EmailField(required=False)
    test_amount = serializers.DecimalField(
        required=False, 
        max_digits=12, 
        decimal_places=2
    )
    
    def validate(self, data):
        test_type = data['test_type']
        
        if test_type == 'sms' and not data.get('test_phone'):
            raise serializers.ValidationError({
                'test_phone': 'Test phone number is required for SMS test.'
            })
        
        if test_type == 'email' and not data.get('test_email'):
            raise serializers.ValidationError({
                'test_email': 'Test email is required for email test.'
            })
        
        return data


class MpesaCredentialsSerializer(serializers.ModelSerializer):
    """Serializer for M-Pesa credentials"""
    
    class Meta:
        model = Integration
        fields = [
            'consumer_key', 'consumer_secret', 'passkey',
            'api_url', 'webhook_url'
        ]
        extra_kwargs = {
            'consumer_key': {'write_only': True},
            'consumer_secret': {'write_only': True},
            'passkey': {'write_only': True},
        }


class APILogSerializer(serializers.ModelSerializer):
    """Serializer for API logs"""
    integration_name = serializers.CharField(
        source='integration.name', 
        read_only=True
    )
    organization_name = serializers.CharField(
        source='organization.name', 
        read_only=True
    )
    payment_reference = serializers.CharField(
        source='payment.payment_reference', 
        read_only=True
    )
    
    class Meta:
        model = APILog
        fields = [
            'id', 'integration', 'integration_name', 'organization', 'organization_name',
            'request_type', 'endpoint', 'method', 'request_headers', 'request_body',
            'request_timestamp', 'response_status_code', 'response_headers',
            'response_body', 'response_timestamp', 'status', 'error_message',
            'retry_count', 'correlation_id', 'external_id', 'duration_ms',
            'payment', 'payment_reference', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']