from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta
from .models import Payment, Invoice, PaymentPlan


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin configuration for Payment model"""
    
    list_display = [
        'payment_reference', 'organization', 'customer_display',
        'amount', 'currency', 'payment_method', 'status',
        'is_reversed', 'completed_at', 'created_at'
    ]
    
    list_filter = [
        'status', 'payment_method', 'payment_type', 'is_reversed',
        'organization', 'currency', 'created_at', 'completed_at'
    ]
    
    search_fields = [
        'payment_reference', 'external_reference',
        'payer_phone', 'payer_name', 'payer_email',
        'mpesa_checkout_request_id', 'mpesa_merchant_request_id',
        'customer__first_name', 'customer__last_name',
        'customer__phone_number', 'organization__name'
    ]
    
    readonly_fields = [
        'payment_reference', 'net_amount', 'created_at', 'updated_at',
        'completed_at', 'reversed_at', 'revenue_share'
    ]
    
    fieldsets = (
        (_('Payment Information'), {
            'fields': (
                'payment_reference', 'external_reference', 'organization',
                'customer', 'description', 'payment_type'
            )
        }),
        (_('Amount Details'), {
            'fields': (
                'amount', 'currency', 'transaction_fee', 'net_amount',
                'revenue_share'
            )
        }),
        (_('Payment Method'), {
            'fields': (
                'payment_method', 'mpesa_checkout_request_id',
                'mpesa_merchant_request_id'
            )
        }),
        (_('Status & Dates'), {
            'fields': (
                'status', 'initiated_at', 'completed_at', 'created_at',
                'updated_at'
            )
        }),
        (_('Payer Information'), {
            'fields': ('payer_phone', 'payer_name', 'payer_email')
        }),
        (_('Reversal Information'), {
            'fields': (
                'is_reversed', 'reversal_reason', 'reversed_at'
            ),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': ('metadata', 'notes'),
            'classes': ('collapse',)
        }),
        (_('Audit'), {
            'fields': ('created_by',),
            'classes': ('collapse',)
        }),
    )
    
    raw_id_fields = ['organization', 'customer', 'created_by']
    
    actions = [
        'mark_as_completed', 'mark_as_failed', 'reverse_payments',
        'export_selected_payments', 'resend_notifications'
    ]
    
    def customer_display(self, obj):
        """Display customer information"""
        if obj.customer:
            url = reverse('admin:customers_customer_change', args=[obj.customer.id])
            return format_html(
                '<a href="{}">{} ({})</a>',
                url,
                f"{obj.customer.first_name} {obj.customer.last_name}",
                obj.customer.phone_number
            )
        elif obj.payer_name:
            return f"{obj.payer_name} ({obj.payer_phone})"
        return "N/A"
    customer_display.short_description = 'Customer'
    customer_display.admin_order_field = 'customer'
    
    def revenue_share(self, obj):
        """Calculate revenue share for platform"""
        # Example: 2% platform fee
        platform_fee = obj.amount * 0.02
        return f"KES {platform_fee:,.2f}"
    revenue_share.short_description = 'Platform Fee (2%)'
    
    def mark_as_completed(self, request, queryset):
        """Mark selected payments as completed"""
        updated = queryset.filter(status__in=['pending', 'initiated', 'processing'])
        count = updated.count()
        updated.update(
            status='completed',
            completed_at=timezone.now()
        )
        self.message_user(request, f'{count} payments were marked as completed.')
    mark_as_completed.short_description = "Mark as completed"
    
    def mark_as_failed(self, request, queryset):
        """Mark selected payments as failed"""
        updated = queryset.filter(status__in=['pending', 'initiated', 'processing'])
        count = updated.count()
        updated.update(status='failed')
        self.message_user(request, f'{count} payments were marked as failed.')
    mark_as_failed.short_description = "Mark as failed"
    
    def reverse_payments(self, request, queryset):
        """Reverse selected payments"""
        completed_payments = queryset.filter(
            status='completed',
            is_reversed=False
        )
        count = completed_payments.count()
        completed_payments.update(
            is_reversed=True,
            reversed_at=timezone.now(),
            reversal_reason='Manual reversal by admin'
        )
        self.message_user(request, f'{count} payments were reversed.')
    reverse_payments.short_description = "Reverse payments"
    
    def export_selected_payments(self, request, queryset):
        """Export selected payments to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payments_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Payment Reference', 'Organization', 'Customer', 'Amount',
            'Currency', 'Payment Method', 'Status', 'Completed At',
            'Transaction Fee', 'Net Amount', 'Created At'
        ])
        
        for payment in queryset:
            customer_name = ''
            if payment.customer:
                customer_name = f"{payment.customer.first_name} {payment.customer.last_name}"
            elif payment.payer_name:
                customer_name = payment.payer_name
            
            writer.writerow([
                payment.payment_reference,
                payment.organization.name if payment.organization else '',
                customer_name,
                payment.amount,
                payment.currency,
                payment.payment_method,
                payment.status,
                payment.completed_at.strftime('%Y-%m-%d %H:%M:%S') if payment.completed_at else '',
                payment.transaction_fee,
                payment.net_amount,
                payment.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_selected_payments.short_description = "Export selected payments to CSV"
    
    def resend_notifications(self, request, queryset):
        """Resend notifications for selected payments"""
        from notifications.tasks import send_payment_notification
        
        count = 0
        for payment in queryset.filter(status='completed'):
            send_payment_notification.delay(payment.id)
            count += 1
        
        self.message_user(request, f'{count} payment notifications were queued for resending.')
    resend_notifications.short_description = "Resend notifications"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('organization', 'customer', 'created_by')
        return qs
    
    def changelist_view(self, request, extra_context=None):
        """Add summary statistics to changelist"""
        extra_context = extra_context or {}
        
        # Today's stats
        today = timezone.now().date()
        today_payments = Payment.objects.filter(created_at__date=today)
        
        # This month's stats
        month_start = today.replace(day=1)
        month_payments = Payment.objects.filter(created_at__date__gte=month_start)
        
        # Calculate statistics
        extra_context.update({
            'today_total': today_payments.filter(status='completed').aggregate(
                total=Sum('amount')
            )['total'] or 0,
            'today_count': today_payments.count(),
            'month_total': month_payments.filter(status='completed').aggregate(
                total=Sum('amount')
            )['total'] or 0,
            'month_count': month_payments.count(),
            'success_rate': Payment.objects.filter(
                status='completed'
            ).count() / max(Payment.objects.count(), 1) * 100,
        })
        
        return super().changelist_view(request, extra_context=extra_context)


class InvoiceItemInline(admin.TabularInline):
    """Inline admin for invoice items"""
    model = Invoice.items
    extra = 1
    fields = ['description', 'quantity', 'unit_price', 'total']
    readonly_fields = ['total']
    
    def total(self, obj):
        """Calculate total for item"""
        if obj.get('quantity') and obj.get('unit_price'):
            return obj['quantity'] * obj['unit_price']
        return 0
    total.short_description = 'Total'


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Admin configuration for Invoice model"""
    
    list_display = [
        'invoice_number', 'organization', 'customer_display',
        'total_amount', 'amount_paid', 'balance_due', 'status',
        'issue_date', 'due_date', 'paid_date', 'created_at'
    ]
    
    list_filter = [
        'status', 'organization', 'issue_date', 'due_date',
        'paid_date', 'created_at'
    ]
    
    search_fields = [
        'invoice_number', 'reference',
        'customer__first_name', 'customer__last_name',
        'customer__phone_number', 'organization__name'
    ]
    
    readonly_fields = [
        'invoice_number', 'balance_due', 'created_at', 'updated_at',
        'payment_link', 'days_overdue'
    ]
    
    fieldsets = (
        (_('Invoice Information'), {
            'fields': (
                'invoice_number', 'organization', 'customer', 'reference'
            )
        }),
        (_('Dates'), {
            'fields': ('issue_date', 'due_date', 'paid_date')
        }),
        (_('Amounts'), {
            'fields': (
                'subtotal', 'tax_amount', 'discount_amount',
                'total_amount', 'amount_paid', 'balance_due'
            )
        }),
        (_('Status'), {
            'fields': ('status', 'days_overdue')
        }),
        (_('Items'), {
            'fields': ('items',),
            'classes': ('collapse',)
        }),
        (_('Terms & Notes'), {
            'fields': ('terms_and_conditions', 'notes'),
            'classes': ('collapse',)
        }),
        (_('Payment Link'), {
            'fields': ('payment_link', 'payment_link_expiry'),
            'classes': ('collapse',)
        }),
        (_('Audit'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    raw_id_fields = ['organization', 'customer', 'created_by']
    
    actions = [
        'mark_as_paid', 'mark_as_sent', 'send_invoice_emails',
        'generate_payment_links', 'export_selected_invoices'
    ]
    
    def customer_display(self, obj):
        """Display customer information"""
        if obj.customer:
            url = reverse('admin:customers_customer_change', args=[obj.customer.id])
            return format_html(
                '<a href="{}">{} ({})</a>',
                url,
                f"{obj.customer.first_name} {obj.customer.last_name}",
                obj.customer.phone_number
            )
        return "N/A"
    customer_display.short_description = 'Customer'
    customer_display.admin_order_field = 'customer'
    
    def days_overdue(self, obj):
        """Calculate days overdue"""
        if obj.status == 'overdue' and obj.due_date:
            today = timezone.now().date()
            overdue_days = (today - obj.due_date).days
            return f"{overdue_days} days"
        return "N/A"
    days_overdue.short_description = 'Days Overdue'
    
    def mark_as_paid(self, request, queryset):
        """Mark selected invoices as paid"""
        updated = queryset.filter(status__in=['sent', 'viewed', 'partially_paid'])
        count = updated.count()
        for invoice in updated:
            invoice.status = 'paid'
            invoice.paid_date = timezone.now().date()
            invoice.amount_paid = invoice.total_amount
            invoice.save()
        
        self.message_user(request, f'{count} invoices were marked as paid.')
    mark_as_paid.short_description = "Mark as paid"
    
    def mark_as_sent(self, request, queryset):
        """Mark selected invoices as sent"""
        updated = queryset.filter(status='draft')
        count = updated.count()
        updated.update(status='sent')
        self.message_user(request, f'{count} invoices were marked as sent.')
    mark_as_sent.short_description = "Mark as sent"
    
    def send_invoice_emails(self, request, queryset):
        """Send invoice emails for selected invoices"""
        from notifications.tasks import send_invoice_notification
        
        count = 0
        for invoice in queryset.filter(status__in=['draft', 'sent']):
            send_invoice_notification.delay(invoice.id)
            count += 1
        
        self.message_user(request, f'{count} invoice emails were queued for sending.')
    send_invoice_emails.short_description = "Send invoice emails"
    
    def generate_payment_links(self, request, queryset):
        """Generate payment links for selected invoices"""
        count = 0
        for invoice in queryset.filter(status__in=['sent', 'viewed', 'partially_paid']):
            # Generate payment link (in production, this would create a unique URL)
            invoice.payment_link = f"/pay/invoice/{invoice.invoice_number}/"
            invoice.payment_link_expiry = timezone.now() + timedelta(days=30)
            invoice.save()
            count += 1
        
        self.message_user(request, f'{count} payment links were generated.')
    generate_payment_links.short_description = "Generate payment links"
    
    def export_selected_invoices(self, request, queryset):
        """Export selected invoices to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="invoices_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Invoice Number', 'Organization', 'Customer', 'Total Amount',
            'Amount Paid', 'Balance Due', 'Status', 'Issue Date',
            'Due Date', 'Paid Date', 'Created At'
        ])
        
        for invoice in queryset:
            customer_name = ''
            if invoice.customer:
                customer_name = f"{invoice.customer.first_name} {invoice.customer.last_name}"
            
            writer.writerow([
                invoice.invoice_number,
                invoice.organization.name if invoice.organization else '',
                customer_name,
                invoice.total_amount,
                invoice.amount_paid,
                invoice.balance_due,
                invoice.status,
                invoice.issue_date.strftime('%Y-%m-%d'),
                invoice.due_date.strftime('%Y-%m-%d'),
                invoice.paid_date.strftime('%Y-%m-%d') if invoice.paid_date else '',
                invoice.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_selected_invoices.short_description = "Export selected invoices to CSV"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('organization', 'customer', 'created_by')
        return qs


@admin.register(PaymentPlan)
class PaymentPlanAdmin(admin.ModelAdmin):
    """Admin configuration for PaymentPlan model"""
    
    list_display = [
        'name', 'organization', 'customer_display', 'total_amount',
        'amount_paid', 'balance', 'status', 'start_date', 'end_date',
        'number_of_installments', 'created_at', 'progress_percentage'
    ]
    
    list_filter = [
        'status', 'organization', 'start_date', 'end_date',
        'created_at'
    ]
    
    search_fields = [
        'name', 'description',
        'customer__first_name', 'customer__last_name',
        'customer__phone_number', 'organization__name'
    ]
    
    readonly_fields = [
        'balance', 'installment_amount', 'created_at', 'updated_at',
        'progress_percentage', 'remaining_installments'
    ]
    
    fieldsets = (
        (_('Payment Plan Information'), {
            'fields': (
                'organization', 'customer', 'name', 'description'
            )
        }),
        (_('Financial Details'), {
            'fields': (
                'total_amount', 'amount_paid', 'balance', 'status'
            )
        }),
        (_('Schedule'), {
            'fields': (
                'start_date', 'end_date', 'number_of_installments',
                'installment_amount', 'remaining_installments'
            )
        }),
        (_('Progress'), {
            'fields': ('progress_percentage',),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        (_('Audit'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    raw_id_fields = ['organization', 'customer']
    
    actions = [
        'mark_as_completed', 'mark_as_overdue', 'record_installment',
        'export_selected_plans'
    ]
    
    def customer_display(self, obj):
        """Display customer information"""
        if obj.customer:
            url = reverse('admin:customers_customer_change', args=[obj.customer.id])
            return format_html(
                '<a href="{}">{} ({})</a>',
                url,
                f"{obj.customer.first_name} {obj.customer.last_name}",
                obj.customer.phone_number
            )
        return "N/A"
    customer_display.short_description = 'Customer'
    customer_display.admin_order_field = 'customer'
    
    def progress_percentage(self, obj):
        """Calculate progress percentage"""
        if obj.total_amount > 0:
            percentage = (obj.amount_paid / obj.total_amount) * 100
            return f"{percentage:.1f}%"
        return "0%"
    progress_percentage.short_description = 'Progress'
    
    def remaining_installments(self, obj):
        """Calculate remaining installments"""
        if obj.installment_amount > 0:
            remaining = (obj.total_amount - obj.amount_paid) / obj.installment_amount
            return f"{remaining:.1f}"
        return "0"
    remaining_installments.short_description = 'Remaining Installments'
    
    def mark_as_completed(self, request, queryset):
        """Mark selected payment plans as completed"""
        updated = queryset.filter(status__in=['active', 'overdue'])
        count = updated.count()
        updated.update(
            status='completed',
            amount_paid=models.F('total_amount'),
            balance=0
        )
        self.message_user(request, f'{count} payment plans were marked as completed.')
    mark_as_completed.short_description = "Mark as completed"
    
    def mark_as_overdue(self, request, queryset):
        """Mark selected payment plans as overdue"""
        updated = queryset.filter(status='active')
        count = updated.count()
        updated.update(status='overdue')
        self.message_user(request, f'{count} payment plans were marked as overdue.')
    mark_as_overdue.short_description = "Mark as overdue"
    
    def record_installment(self, request, queryset):
        """Record installment payment for selected plans"""
        from django import forms
        
        class InstallmentForm(forms.Form):
            amount = forms.DecimalField(
                label="Installment Amount",
                max_digits=12,
                decimal_places=2,
                min_value=0.01
            )
            payment_method = forms.ChoiceField(
                choices=[
                    ('mpesa', 'M-Pesa'),
                    ('cash', 'Cash'),
                    ('bank', 'Bank Transfer')
                ],
                initial='mpesa',
                label="Payment Method"
            )
        
        if 'apply' in request.POST:
            form = InstallmentForm(request.POST)
            if form.is_valid():
                amount = form.cleaned_data['amount']
                payment_method = form.cleaned_data['payment_method']
                
                count = 0
                for plan in queryset.filter(status__in=['active', 'overdue']):
                    # Create payment record
                    from payments.models import Payment
                    Payment.objects.create(
                        organization=plan.organization,
                        customer=plan.customer,
                        amount=amount,
                        payment_method=payment_method,
                        payment_type='subscription',
                        description=f"Installment for {plan.name}",
                        payer_phone=plan.customer.phone_number,
                        payer_name=f"{plan.customer.first_name} {plan.customer.last_name}",
                        status='completed',
                        completed_at=timezone.now()
                    )
                    
                    # Update payment plan
                    plan.amount_paid += amount
                    plan.balance = plan.total_amount - plan.amount_paid
                    
                    if plan.balance <= 0:
                        plan.status = 'completed'
                    
                    plan.save()
                    count += 1
                
                self.message_user(
                    request,
                    f'{count} installment payments were recorded.'
                )
                return
        else:
            form = InstallmentForm()
        
        return admin.helpers.action_form(
            self, request, queryset, 'record_installment',
            'Record installment payment',
            form
        )
    record_installment.short_description = "Record installment"
    
    def export_selected_plans(self, request, queryset):
        """Export selected payment plans to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payment_plans_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Organization', 'Customer', 'Total Amount',
            'Amount Paid', 'Balance', 'Status', 'Start Date',
            'End Date', 'Installments', 'Created At'
        ])
        
        for plan in queryset:
            customer_name = ''
            if plan.customer:
                customer_name = f"{plan.customer.first_name} {plan.customer.last_name}"
            
            writer.writerow([
                plan.name,
                plan.organization.name if plan.organization else '',
                customer_name,
                plan.total_amount,
                plan.amount_paid,
                plan.balance,
                plan.status,
                plan.start_date.strftime('%Y-%m-%d'),
                plan.end_date.strftime('%Y-%m-%d'),
                plan.number_of_installments,
                plan.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_selected_plans.short_description = "Export selected payment plans to CSV"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('organization', 'customer')
        return qs