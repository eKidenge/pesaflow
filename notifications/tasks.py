# notifications/tasks.py
import logging
import json
from typing import Dict, List, Optional, Any
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model

from .models import (
    Notification, 
    NotificationTemplate, 
    NotificationPreference,
    NotificationQueue
)

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification(self, notification_id: str) -> Dict[str, Any]:
    """
    Send a single notification asynchronously.
    This is called by views.py with send_notification.delay(notification.id)
    
    Args:
        notification_id: UUID string of the Notification object
        
    Returns:
        Dict with result information
    """
    try:
        with transaction.atomic():
            # Get the notification
            try:
                notification = Notification.objects.select_for_update().get(id=notification_id)
            except Notification.DoesNotExist:
                logger.error(f"Notification {notification_id} not found")
                return {
                    'success': False,
                    'error': 'Notification not found',
                    'notification_id': notification_id
                }
            
            # Check if already sent
            if notification.status in ['sent', 'delivered', 'read']:
                logger.warning(f"Notification {notification_id} already in status: {notification.status}")
                return {
                    'success': True,
                    'status': notification.status,
                    'message': 'Already processed'
                }
            
            # Check if scheduled for future
            if notification.scheduled_for and notification.scheduled_for > timezone.now():
                # Reschedule
                delay_seconds = (notification.scheduled_for - timezone.now()).total_seconds()
                send_notification.apply_async(
                    args=[notification_id],
                    countdown=min(delay_seconds, 3600)  # Max 1 hour delay
                )
                return {
                    'success': True,
                    'status': 'scheduled',
                    'scheduled_for': notification.scheduled_for.isoformat()
                }
            
            # Check recipient preferences if available
            if notification.recipient_type == 'user':
                try:
                    preference = NotificationPreference.objects.get(
                        organization=notification.organization,
                        recipient_type='user',
                        recipient_id=notification.recipient_id
                    )
                    
                    # Check if this channel is enabled for user
                    if notification.channel == 'sms' and not preference.receive_sms:
                        notification.mark_as_failed("User has disabled SMS notifications")
                        return {
                            'success': False,
                            'error': 'User disabled SMS notifications',
                            'notification_id': notification_id
                        }
                    elif notification.channel == 'email' and not preference.receive_email:
                        notification.mark_as_failed("User has disabled email notifications")
                        return {
                            'success': False,
                            'error': 'User disabled email notifications',
                            'notification_id': notification_id
                        }
                    elif notification.channel == 'whatsapp' and not preference.receive_whatsapp:
                        notification.mark_as_failed("User has disabled WhatsApp notifications")
                        return {
                            'success': False,
                            'error': 'User disabled WhatsApp notifications',
                            'notification_id': notification_id
                        }
                    elif notification.channel == 'push' and not preference.receive_push:
                        notification.mark_as_failed("User has disabled push notifications")
                        return {
                            'success': False,
                            'error': 'User disabled push notifications',
                            'notification_id': notification_id
                        }
                    
                    # Check quiet hours
                    if preference.quiet_hours_start and preference.quiet_hours_end:
                        now = timezone.now().time()
                        if preference.quiet_hours_start <= now <= preference.quiet_hours_end:
                            # Reschedule for after quiet hours
                            delay_hours = (preference.quiet_hours_end.hour - now.hour) * 3600
                            send_notification.apply_async(
                                args=[notification_id],
                                countdown=delay_hours
                            )
                            notification.status = 'pending'
                            notification.save()
                            return {
                                'success': True,
                                'status': 'delayed_quiet_hours',
                                'rescheduled_for': timezone.now() + timezone.timedelta(hours=delay_hours/3600)
                            }
                            
                except NotificationPreference.DoesNotExist:
                    # No preferences set, continue with sending
                    pass
            
            # Update status to processing
            notification.status = 'processing'
            notification.delivery_attempts += 1
            notification.save()
            
            # Send based on channel
            try:
                result = _send_by_channel(notification)
                
                if result['success']:
                    notification.mark_as_sent(
                        provider_message_id=result.get('provider_message_id'),
                        provider_response=result.get('response', {})
                    )
                    logger.info(f"Notification {notification_id} sent successfully via {notification.channel}")
                    
                    # For in-app notifications, mark as delivered immediately
                    if notification.channel == 'in_app':
                        notification.status = 'delivered'
                        notification.delivered_at = timezone.now()
                        notification.save()
                    
                    return {
                        'success': True,
                        'status': notification.status,
                        'channel': notification.channel,
                        'notification_id': notification_id,
                        'provider_message_id': result.get('provider_message_id')
                    }
                else:
                    notification.mark_as_failed(result.get('error', 'Unknown error'))
                    logger.error(f"Notification {notification_id} failed: {result.get('error')}")
                    
                    # Retry if we haven't exceeded max attempts
                    if notification.delivery_attempts < 3:
                        retry_delay = 300 * notification.delivery_attempts  # 5, 10, 15 minutes
                        send_notification.apply_async(
                            args=[notification_id],
                            countdown=retry_delay
                        )
                    
                    return {
                        'success': False,
                        'error': result.get('error'),
                        'notification_id': notification_id,
                        'attempts': notification.delivery_attempts
                    }
                    
            except Exception as e:
                logger.error(f"Error sending notification {notification_id}: {str(e)}")
                notification.mark_as_failed(str(e))
                
                # Retry with exponential backoff
                if self.request.retries < self.max_retries:
                    retry_delay = self.default_retry_delay * (2 ** self.request.retries)
                    raise self.retry(exc=e, countdown=retry_delay)
                
                return {
                    'success': False,
                    'error': str(e),
                    'notification_id': notification_id,
                    'retries_exhausted': True
                }
                
    except Exception as e:
        logger.error(f"Unexpected error in send_notification task: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'notification_id': notification_id
        }


@shared_task
def send_bulk_notification(
    organization_id: str,
    recipient_ids: List[str],
    recipient_type: str,
    notification_type: str,
    channel: str,
    message: str,
    subject: str = '',
    template_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send bulk notifications to multiple recipients.
    This is called by views.py with send_bulk_notification.delay(...)
    
    Args:
        organization_id: UUID string of organization
        recipient_ids: List of recipient IDs
        recipient_type: Type of recipient ('user', 'customer', etc.)
        notification_type: Type of notification
        channel: Channel to use ('email', 'sms', etc.)
        message: Message content
        subject: Subject (for email)
        template_id: Optional template ID
        
    Returns:
        Dict with result information
    """
    try:
        from .models import Organization
        
        organization = Organization.objects.get(id=organization_id)
        
        # Get template if provided
        template = None
        if template_id:
            try:
                template = NotificationTemplate.objects.get(id=template_id, organization=organization)
            except NotificationTemplate.DoesNotExist:
                logger.warning(f"Template {template_id} not found, using custom message")
        
        created_count = 0
        failed_count = 0
        notification_ids = []
        
        for recipient_id in recipient_ids:
            try:
                # Get recipient details based on type
                recipient_email = ''
                recipient_phone = ''
                
                if recipient_type == 'user':
                    try:
                        user = User.objects.get(id=recipient_id)
                        recipient_email = user.email
                        recipient_phone = getattr(user, 'phone_number', '')
                    except User.DoesNotExist:
                        logger.warning(f"User {recipient_id} not found")
                        continue
                
                # Create notification for each recipient
                notification_data = {
                    'organization': organization,
                    'recipient_type': recipient_type,
                    'recipient_id': recipient_id,
                    'recipient_email': recipient_email,
                    'recipient_phone': recipient_phone,
                    'notification_type': notification_type,
                    'channel': channel,
                    'subject': subject,
                    'message': message,
                    'template': template
                }
                
                # If template exists, use its content
                if template:
                    notification_data['subject'] = template.subject
                    # Here you would replace template variables with actual data
                    # For now, using template body as-is
                    notification_data['message'] = template.body
                    notification_data['message_html'] = template.body_html
                
                notification = Notification.objects.create(**notification_data)
                notification_ids.append(str(notification.id))
                created_count += 1
                
                # Queue for sending
                send_notification.delay(str(notification.id))
                
            except Exception as e:
                logger.error(f"Failed to create notification for {recipient_id}: {str(e)}")
                failed_count += 1
        
        # Create queue entries for batch tracking
        if notification_ids:
            try:
                NotificationQueue.objects.create(
                    notification_id=notification_ids[0],  # Reference first notification
                    status='processed',
                    metadata={
                        'batch_size': len(recipient_ids),
                        'created_count': created_count,
                        'failed_count': failed_count,
                        'notification_ids': notification_ids,
                        'channel': channel,
                        'notification_type': notification_type
                    }
                )
            except Exception as e:
                logger.error(f"Failed to create queue entry: {str(e)}")
        
        return {
            'success': True,
            'total_recipients': len(recipient_ids),
            'created_notifications': created_count,
            'failed_creations': failed_count,
            'notification_ids': notification_ids,
            'organization_id': organization_id
        }
        
    except Organization.DoesNotExist:
        logger.error(f"Organization {organization_id} not found")
        return {
            'success': False,
            'error': 'Organization not found',
            'organization_id': organization_id
        }
    except Exception as e:
        logger.error(f"Error in send_bulk_notification: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'organization_id': organization_id
        }


def _send_by_channel(notification: Notification) -> Dict[str, Any]:
    """
    Internal function to send notification based on channel.
    
    Args:
        notification: Notification object
        
    Returns:
        Dict with send result
    """
    channel = notification.channel
    
    if channel == 'email':
        return _send_email(notification)
    elif channel == 'sms':
        return _send_sms(notification)
    elif channel == 'whatsapp':
        return _send_whatsapp(notification)
    elif channel == 'push':
        return _send_push_notification(notification)
    elif channel == 'in_app':
        return _send_in_app(notification)
    else:
        return {
            'success': False,
            'error': f'Unsupported channel: {channel}'
        }


def _send_email(notification: Notification) -> Dict[str, Any]:
    """
    Send email notification.
    Integrate with your email service (SendGrid, AWS SES, etc.)
    """
    try:
        # TODO: Integrate with your email service
        # Example with Django's send_mail (configure EMAIL_BACKEND in settings)
        if settings.DEBUG:
            # In development, just log
            logger.info(f"[EMAIL] To: {notification.recipient_email}")
            logger.info(f"[EMAIL] Subject: {notification.subject}")
            logger.info(f"[EMAIL] Message: {notification.message[:100]}...")
            
            return {
                'success': True,
                'provider_message_id': f'dev-{notification.id}',
                'response': {'simulated': True}
            }
        else:
            # Production implementation
            from django.core.mail import send_mail
            
            send_mail(
                subject=notification.subject,
                message=notification.message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.recipient_email],
                html_message=notification.message_html
            )
            
            return {
                'success': True,
                'provider_message_id': f'email-{notification.id}',
                'response': {'sent': True}
            }
            
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def _send_sms(notification: Notification) -> Dict[str, Any]:
    """
    Send SMS notification.
    Integrate with your SMS service (Twilio, Africa's Talking, etc.)
    """
    try:
        # TODO: Integrate with your SMS service
        if settings.DEBUG:
            # In development, just log
            logger.info(f"[SMS] To: {notification.recipient_phone}")
            logger.info(f"[SMS] Message: {notification.message}")
            
            return {
                'success': True,
                'provider_message_id': f'dev-{notification.id}',
                'response': {'simulated': True}
            }
        else:
            # Example with Africa's Talking (common in Kenya)
            # import africastalking
            
            # africastalking.initialize(
            #     username=settings.AFRICASTALKING_USERNAME,
            #     api_key=settings.AFRICASTALKING_API_KEY
            # )
            # sms = africastalking.SMS
            # response = sms.send(
            #     message=notification.message,
            #     recipients=[notification.recipient_phone]
            # )
            
            # return {
            #     'success': True,
            #     'provider_message_id': response['SMSMessageData']['MessageId'],
            #     'response': response
            # }
            
            # For now, simulate success
            return {
                'success': True,
                'provider_message_id': f'sms-{notification.id}',
                'response': {'simulated': True}
            }
            
    except Exception as e:
        logger.error(f"SMS sending failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def _send_whatsapp(notification: Notification) -> Dict[str, Any]:
    """
    Send WhatsApp notification.
    Integrate with WhatsApp Business API or service like Twilio WhatsApp
    """
    try:
        if settings.DEBUG:
            logger.info(f"[WHATSAPP] To: {notification.recipient_phone}")
            logger.info(f"[WHATSAPP] Message: {notification.message}")
            
            return {
                'success': True,
                'provider_message_id': f'dev-{notification.id}',
                'response': {'simulated': True}
            }
        else:
            # TODO: Implement WhatsApp integration
            # This would use Twilio WhatsApp API or similar
            return {
                'success': True,
                'provider_message_id': f'whatsapp-{notification.id}',
                'response': {'simulated': True}
            }
            
    except Exception as e:
        logger.error(f"WhatsApp sending failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def _send_push_notification(notification: Notification) -> Dict[str, Any]:
    """
    Send push notification.
    Integrate with Firebase Cloud Messaging (FCM) or similar
    """
    try:
        if settings.DEBUG:
            logger.info(f"[PUSH] To user: {notification.recipient_id}")
            logger.info(f"[PUSH] Title: {notification.subject}")
            logger.info(f"[PUSH] Body: {notification.message}")
            
            return {
                'success': True,
                'provider_message_id': f'dev-{notification.id}',
                'response': {'simulated': True}
            }
        else:
            # TODO: Implement FCM or similar
            # This would send to user's device tokens
            return {
                'success': True,
                'provider_message_id': f'push-{notification.id}',
                'response': {'simulated': True}
            }
            
    except Exception as e:
        logger.error(f"Push notification failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def _send_in_app(notification: Notification) -> Dict[str, Any]:
    """
    Create in-app notification (stored in database).
    """
    try:
        # In-app notifications are just stored in DB
        # They will be retrieved by the frontend via API
        
        # Add to notification queue for organization dashboard
        NotificationQueue.objects.create(
            notification=notification,
            status='processed',
            metadata={
                'type': 'in_app',
                'user_id': notification.recipient_id
            }
        )
        
        return {
            'success': True,
            'provider_message_id': f'in-app-{notification.id}',
            'response': {'stored': True}
        }
        
    except Exception as e:
        logger.error(f"In-app notification failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def process_notification_queue():
    """
    Process queued notifications.
    This task should be scheduled to run regularly via Celery beat.
    """
    try:
        # Get queued notifications ready for processing
        queue_items = NotificationQueue.objects.filter(
            status='queued',
            next_scheduled_time__lte=timezone.now()
        ).order_by('-priority', 'created_at')[:50]
        
        processed_count = 0
        for queue_item in queue_items:
            try:
                queue_item.status = 'processing'
                queue_item.last_processing_attempt = timezone.now()
                queue_item.processing_attempts += 1
                queue_item.save()
                
                # Process the notification
                send_notification.delay(str(queue_item.notification.id))
                
                queue_item.status = 'processed'
                queue_item.save()
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Failed to process queue item {queue_item.id}: {str(e)}")
                queue_item.status = 'failed'
                queue_item.save()
        
        logger.info(f"Processed {processed_count} queued notifications")
        return {'processed': processed_count}
        
    except Exception as e:
        logger.error(f"Error processing notification queue: {str(e)}")
        return {'error': str(e)}


@shared_task
def cleanup_old_notifications(days_to_keep: int = 90):
    """
    Clean up old notifications to save database space.
    
    Args:
        days_to_keep: Number of days to keep notifications
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days_to_keep)
        
        # Archive or delete old notifications
        # In production, you might want to archive to cold storage
        deleted_count, _ = Notification.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['sent', 'delivered', 'failed']
        ).delete()
        
        # Clean up old queue entries
        queue_deleted_count, _ = NotificationQueue.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['processed', 'failed']
        ).delete()
        
        logger.info(f"Cleaned up {deleted_count} notifications and {queue_deleted_count} queue entries older than {days_to_keep} days")
        
        return {
            'notifications_deleted': deleted_count,
            'queue_entries_deleted': queue_deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up old notifications: {str(e)}")
        return {'error': str(e)}


# Helper function for direct synchronous calls (optional)
def send_notification_sync(notification_id: str) -> Dict[str, Any]:
    """
    Synchronous version for immediate sending.
    Use with caution - blocks until complete.
    """
    # This just calls the async task synchronously
    return send_notification.apply(args=[notification_id]).get()