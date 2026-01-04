from rest_framework import serializers
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .models import NotificationTemplate, Notification, NotificationPreference, NotificationQueue


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """Serializer for notification templates"""
    organization_name = serializers.CharField(
        source='organization.name', 
        read_only=True
    )
    created_by_email = serializers.EmailField(
        source='created_by.email', 
        read_only=True
    )
    
    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'organization', 'organization_name', 'name', 'template_type',
            'channel', 'subject', 'body', 'body_html', 'language',
            'available_variables', 'is_active', 'is_system_template',
            'created_by', 'created_by_email', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def validate(self, data):
        # Validate that system templates don't have organization
        if data.get('is_system_template', False) and data.get('organization'):
            raise serializers.ValidationError({
                'organization': 'System templates cannot be associated with an organization.'
            })
        
        # Validate that organization templates have organization
        if not data.get('is_system_template', False) and not data.get('organization'):
            raise serializers.ValidationError({
                'organization': 'Organization is required for non-system templates.'
            })
        
        return data


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications"""
    organization_name = serializers.CharField(
        source='organization.name', 
        read_only=True
    )
    template_name = serializers.CharField(
        source='template.name', 
        read_only=True
    )
    payment_reference = serializers.CharField(
        source='payment.payment_reference', 
        read_only=True
    )
    invoice_number = serializers.CharField(
        source='invoice.invoice_number', 
        read_only=True
    )
    
    class Meta:
        model = Notification
        fields = [
            'id', 'organization', 'organization_name', 'recipient_type',
            'recipient_id', 'recipient_email', 'recipient_phone',
            'notification_type', 'channel', 'subject', 'message', 'message_html',
            'status', 'priority', 'scheduled_for', 'sent_at', 'delivered_at',
            'read_at', 'provider_message_id', 'provider_response',
            'delivery_attempts', 'failure_reason', 'template', 'template_name',
            'payment', 'payment_reference', 'invoice', 'invoice_number',
            'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'sent_at', 'delivered_at', 'read_at', 'provider_message_id',
            'provider_response', 'delivery_attempts', 'failure_reason',
            'created_at', 'updated_at'
        ]


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notifications"""
    
    class Meta:
        model = Notification
        fields = [
            'recipient_type', 'recipient_id', 'recipient_email', 'recipient_phone',
            'notification_type', 'channel', 'subject', 'message', 'message_html',
            'priority', 'scheduled_for', 'template', 'payment', 'invoice',
            'metadata'
        ]
    
    def validate(self, data):
        recipient_type = data.get('recipient_type')
        recipient_id = data.get('recipient_id')
        recipient_email = data.get('recipient_email')
        recipient_phone = data.get('recipient_phone')
        
        # Validate recipient information based on type
        if recipient_type == 'user':
            if not recipient_id:
                raise serializers.ValidationError({
                    'recipient_id': 'Recipient ID is required for user notifications.'
                })
        elif recipient_type == 'customer':
            if not recipient_id:
                raise serializers.ValidationError({
                    'recipient_id': 'Recipient ID is required for customer notifications.'
                })
        elif recipient_type == 'organization':
            if not recipient_id:
                raise serializers.ValidationError({
                    'recipient_id': 'Recipient ID is required for organization notifications.'
                })
        else:
            # For group or other types, require at least one contact method
            if not recipient_email and not recipient_phone:
                raise serializers.ValidationError({
                    'recipient_email': 'Either email or phone is required.',
                    'recipient_phone': 'Either email or phone is required.'
                })
        
        # Validate email if provided
        if recipient_email:
            try:
                validate_email(recipient_email)
            except ValidationError:
                raise serializers.ValidationError({
                    'recipient_email': 'Enter a valid email address.'
                })
        
        return data


class SendNotificationSerializer(serializers.Serializer):
    """Serializer for sending notifications"""
    recipient_type = serializers.ChoiceField(
        choices=['user', 'customer', 'organization', 'group']
    )
    recipient_id = serializers.CharField(required=False)
    recipient_email = serializers.EmailField(required=False)
    recipient_phone = serializers.CharField(required=False)
    notification_type = serializers.CharField(required=True)
    channel = serializers.ChoiceField(
        choices=['sms', 'email', 'whatsapp', 'push', 'in_app']
    )
    subject = serializers.CharField(required=False, allow_blank=True)
    message = serializers.CharField(required=True)
    message_html = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(
        choices=['low', 'normal', 'high', 'urgent'],
        default='normal'
    )
    scheduled_for = serializers.DateTimeField(required=False)
    metadata = serializers.JSONField(required=False, default=dict)
    
    def validate(self, data):
        recipient_type = data['recipient_type']
        recipient_id = data.get('recipient_id')
        recipient_email = data.get('recipient_email')
        recipient_phone = data.get('recipient_phone')
        
        # Validate recipient information based on type
        if recipient_type in ['user', 'customer', 'organization']:
            if not recipient_id:
                raise serializers.ValidationError({
                    'recipient_id': f'Recipient ID is required for {recipient_type} notifications.'
                })
        else:
            # For group or other types, require at least one contact method
            if not recipient_email and not recipient_phone:
                raise serializers.ValidationError({
                    'recipient_email': 'Either email or phone is required.',
                    'recipient_phone': 'Either email or phone is required.'
                })
        
        # Validate channel-specific requirements
        channel = data['channel']
        if channel == 'email' and not recipient_email:
            raise serializers.ValidationError({
                'recipient_email': 'Email is required for email notifications.'
            })
        
        if channel == 'sms' and not recipient_phone:
            raise serializers.ValidationError({
                'recipient_phone': 'Phone number is required for SMS notifications.'
            })
        
        if channel == 'whatsapp' and not recipient_phone:
            raise serializers.ValidationError({
                'recipient_phone': 'Phone number is required for WhatsApp notifications.'
            })
        
        return data


class BulkNotificationSerializer(serializers.Serializer):
    """Serializer for bulk notifications"""
    recipient_ids = serializers.ListField(
        child=serializers.CharField(),
        required=True
    )
    recipient_type = serializers.ChoiceField(
        choices=['customer', 'user', 'group'],
        required=True
    )
    notification_type = serializers.CharField(required=True)
    channel = serializers.ChoiceField(
        choices=['sms', 'email', 'whatsapp'],
        required=True
    )
    subject = serializers.CharField(required=False, allow_blank=True)
    message = serializers.CharField(required=True)
    template_id = serializers.UUIDField(required=False)
    
    def validate(self, data):
        recipient_ids = data['recipient_ids']
        recipient_type = data['recipient_type']
        channel = data['channel']
        
        # Validate recipient IDs
        if not recipient_ids:
            raise serializers.ValidationError({
                'recipient_ids': 'At least one recipient ID is required.'
            })
        
        # Limit bulk notifications
        if len(recipient_ids) > 1000:
            raise serializers.ValidationError({
                'recipient_ids': 'Maximum 1000 recipients allowed for bulk notifications.'
            })
        
        # Validate channel
        if channel == 'email' and not data.get('subject'):
            raise serializers.ValidationError({
                'subject': 'Subject is required for email notifications.'
            })
        
        return data


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for notification preferences"""
    organization_name = serializers.CharField(
        source='organization.name', 
        read_only=True
    )
    
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'organization', 'organization_name', 'recipient_type',
            'recipient_id', 'preferences', 'receive_sms', 'receive_email',
            'receive_whatsapp', 'receive_push', 'quiet_hours_start',
            'quiet_hours_end', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        # Validate quiet hours
        quiet_start = data.get('quiet_hours_start')
        quiet_end = data.get('quiet_hours_end')
        
        if quiet_start and quiet_end:
            if quiet_start >= quiet_end:
                raise serializers.ValidationError({
                    'quiet_hours_start': 'Start time must be before end time.',
                    'quiet_hours_end': 'End time must be after start time.'
                })
        
        return data


class NotificationQueueSerializer(serializers.ModelSerializer):
    """Serializer for notification queue"""
    notification_details = NotificationSerializer(
        source='notification', 
        read_only=True
    )
    
    class Meta:
        model = NotificationQueue
        fields = [
            'id', 'notification', 'notification_details', 'status', 'priority',
            'processing_attempts', 'last_processing_attempt', 'is_recurring',
            'recurrence_pattern', 'next_scheduled_time', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']