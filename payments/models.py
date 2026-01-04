from django.db import models
from django.core.validators import MinValueValidator
import uuid
from django.utils.translation import gettext_lazy as _


class Payment(models.Model):
    """Payment transactions"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('initiated', 'Initiated'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('reversed', 'Reversed'),
        ('partially_paid', 'Partially Paid'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('mpesa', 'M-Pesa'),
        ('card', 'Credit/Debit Card'),
        ('bank', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('wallet', 'Mobile Wallet'),
        ('cheque', 'Cheque'),
    )
    
    PAYMENT_TYPE_CHOICES = (
        ('invoice', 'Invoice Payment'),
        ('subscription', 'Subscription'),
        ('fee', 'Fee Payment'),
        ('rent', 'Rent Payment'),
        ('donation', 'Donation'),
        ('refund', 'Refund'),
        ('other', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # References
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='payments'
    )
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='payments',
        null=True,
        blank=True
    )
    
    # Payment Details
    payment_reference = models.CharField(max_length=100, unique=True, editable=False)
    external_reference = models.CharField(max_length=100, blank=True)  # M-Pesa Transaction ID
    description = models.TextField()
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='other')
    
    # Amounts
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    currency = models.CharField(max_length=3, default='KES')
    transaction_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Payment Method
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='mpesa')
    mpesa_checkout_request_id = models.CharField(max_length=100, blank=True)
    mpesa_merchant_request_id = models.CharField(max_length=100, blank=True)
    
    # Status & Dates
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    initiated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Payer Information
    payer_phone = models.CharField(max_length=17)
    payer_name = models.CharField(max_length=200, blank=True)
    payer_email = models.EmailField(blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)  # Raw response from payment gateway
    notes = models.TextField(blank=True)
    
    # Reversal Information
    is_reversed = models.BooleanField(default=False)
    reversal_reason = models.TextField(blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)
    
    # Audit
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_payments'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['payment_reference']),
            models.Index(fields=['external_reference']),
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['organization', 'status']),
        ]
    
    def __str__(self):
        return f"{self.payment_reference} - {self.amount} {self.currency}"
    
    def save(self, *args, **kwargs):
        if not self.payment_reference:
            from django.utils import timezone
            import random
            date_part = timezone.now().strftime('%Y%m%d')
            random_part = str(random.randint(10000, 99999))
            org_prefix = self.organization.name[:3].upper()
            self.payment_reference = f"PAY-{org_prefix}-{date_part}-{random_part}"
        
        # Calculate net amount
        self.net_amount = self.amount - self.transaction_fee
        
        super().save(*args, **kwargs)
    
    def mark_as_completed(self, external_ref=None):
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        if external_ref:
            self.external_reference = external_ref
        self.save()
        
        # Update customer's last payment date
        if self.customer:
            self.customer.last_payment_date = timezone.now()
            self.customer.save()


class Invoice(models.Model):
    """Invoices for payments"""
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('viewed', 'Viewed'),
        ('paid', 'Paid'),
        ('partially_paid', 'Partially Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='invoices'
    )
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='invoices'
    )
    
    # Invoice Details
    invoice_number = models.CharField(max_length=100, unique=True, editable=False)
    reference = models.CharField(max_length=100, blank=True)  # Client's reference
    
    # Dates
    issue_date = models.DateField()
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    
    # Amounts
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    balance_due = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Items
    items = models.JSONField(default=list)  # List of items with description, quantity, price
    
    # Terms & Notes
    terms_and_conditions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    # Payment Link
    payment_link = models.URLField(blank=True)
    payment_link_expiry = models.DateTimeField(null=True, blank=True)
    
    # Audit
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_invoices'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-issue_date']
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        indexes = [
            models.Index(fields=['invoice_number']),
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['due_date', 'status']),
        ]
    
    def __str__(self):
        return f"Invoice #{self.invoice_number} - {self.customer}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            from django.utils import timezone
            date_part = timezone.now().strftime('%Y%m')
            last_invoice = Invoice.objects.filter(
                organization=self.organization
            ).order_by('-created_at').first()
            
            if last_invoice and last_invoice.invoice_number:
                last_num = int(last_invoice.invoice_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
                
            org_prefix = self.organization.name[:3].upper()
            self.invoice_number = f"INV-{org_prefix}-{date_part}-{str(new_num).zfill(5)}"
        
        # Calculate totals
        self.balance_due = self.total_amount - self.amount_paid
        
        # Update status based on payments
        if self.amount_paid >= self.total_amount:
            self.status = 'paid'
            if not self.paid_date:
                from django.utils import timezone
                self.paid_date = timezone.now().date()
        elif self.amount_paid > 0:
            self.status = 'partially_paid'
        elif self.due_date and self.due_date < timezone.now().date():
            self.status = 'overdue'
        
        super().save(*args, **kwargs)


class PaymentPlan(models.Model):
    """Installment plans for payments"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='payment_plans'
    )
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='payment_plans'
    )
    
    # Plan Details
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    balance = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Schedule
    start_date = models.DateField()
    end_date = models.DateField()
    number_of_installments = models.PositiveIntegerField()
    installment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('overdue', 'Overdue'),
            ('cancelled', 'Cancelled'),
        ],
        default='active'
    )
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment Plan'
        verbose_name_plural = 'Payment Plans'
    
    def __str__(self):
        return f"{self.name} - {self.customer}"