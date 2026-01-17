from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'payments', views.PaymentViewSet, basename='payment')
router.register(r'invoices', views.InvoiceViewSet, basename='invoice')
router.register(r'payment-plans', views.PaymentPlanViewSet, basename='payment-plan')

urlpatterns = [
    # ==============================================
    # ADD THIS LINE - Template view for payments list
    # ==============================================
    path('list/', views.payments_list_view, name='payments_list'),
    
    # ==============================================
    # API endpoints
    # ==============================================
    path('', include(router.urls)),
    
    # Additional payment endpoints
    path('payments/initiate/mpesa/', views.PaymentViewSet.as_view({'post': 'initiate_mpesa'}), name='initiate_mpesa'),
    path('payments/<uuid:pk>/reverse/', views.PaymentViewSet.as_view({'post': 'reverse'}), name='reverse_payment'),
    path('payments/statistics/', views.PaymentViewSet.as_view({'get': 'statistics'}), name='payment_statistics'),
    path('payments/dashboard/', views.PaymentViewSet.as_view({'get': 'dashboard'}), name='payment_dashboard'),
    path('payments/create/', views.PaymentViewSet.as_view({'get': 'create'}), name='payments_create'),
    # Invoice endpoints
    path('invoices/<uuid:pk>/send/', views.InvoiceViewSet.as_view({'post': 'send'}), name='send_invoice'),
    path('invoices/<uuid:pk>/record-payment/', views.InvoiceViewSet.as_view({'post': 'record_payment'}), name='record_invoice_payment'),
    path('invoices/overdue/', views.InvoiceViewSet.as_view({'get': 'overdue'}), name='overdue_invoices'),
    
    path('list/', views.payments_list_view, name='payments_list'),
    # ADD THIS SINGLE LINE:
    path('invoices/list/', views.payments_list_view, name='invoices_list'),  # Same view, different name
    path('invoices/create/', views.InvoiceViewSet.as_view({'get': 'create'}), name='invoices_create'),# Payment plan endpoints
    path('payment-plans/<uuid:pk>/record-installment/', views.PaymentPlanViewSet.as_view({'post': 'record_installment'}), name='record_installment'),
]