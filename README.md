# Pesaflow

Pesaflow is a **comprehensive financial management and payment workflow platform** designed to streamline customer, organization, and payment management for businesses in Kenya and beyond. It integrates **customer management, organizational management, payments (including M-Pesa integration), notifications, and analytics dashboards** into a single, easy-to-use Django-based application.

The platform is built to help businesses **track customers, manage organizations, process payments, generate invoices, configure integrations, and send notifications** efficiently while maintaining modularity for easier scaling and maintenance.

---
## Project Structure

```text
│pesaflow/
├── accounts/
│   ├── migrations/
│   │   └── __init__.py
│   ├── templates/
│   │   └── accounts/
│   │       ├── login.html
│   │       ├── register.html
│   │       ├── profile.html
│   │       ├── change_password.html
│   │       ├── password_reset.html
│   │       └── password_reset_confirm.html
│   ├── __pycache__/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── permissions.py
│   ├── serializers.py
│   ├── tests.py
│   ├── urls.py
│   ├── views.py
│   └── __init__.py
├── customers/
│   ├── migrations/
│   │   └── __init__.py
│   ├── templates/
│   │   └── customers/
│   │       ├── create.html
│   │       ├── detail.html
│   │       ├── edit.html
│   │       ├── groups.html
│   │       ├── import.html
│   │       └── list.html
│   ├── __pycache__/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── permissions.py
│   ├── serializers.py
│   ├── tests.py
│   ├── urls.py
│   ├── views.py
│   └── __init__.py
├── integrations/
│   ├── migrations/
│   │   └── __init__.py
│   ├── templates/
│   │   └── integrations/
│   │       ├── create.html
│   │       ├── detail.html
│   │       ├── list.html
│   │       ├── logs.html
│   │       └── mpesa_config.html
│   ├── __pycache__/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── permissions.py
│   ├── serializers.py
│   ├── tests.py
│   ├── urls.py
│   ├── views.py
│   └── __init__.py
├── notifications/
│   ├── migrations/
│   │   └── __init__.py
│   ├── templates/
│   │   └── notifications/
│   │       ├── sent/
│   │       │   └── list.html
│   │       └── templates/
│   │           ├── create.html
│   │           ├── edit.html
│   │           └── list.html
│   ├── __pycache__/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── permissions.py
│   ├── serializers.py
│   ├── tests.py
│   ├── urls.py
│   ├── views.py
│   └── __init__.py
├── organizations/
│   ├── migrations/
│   │   └── __init__.py
│   ├── templates/
│   │   └── organizations/
│   │       ├── create.html
│   │       ├── detail.html
│   │       ├── edit.html
│   │       ├── list.html
│   │       ├── members.html
│   │       └── settings.html
│   ├── __pycache__/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── permissions.py
│   ├── serializers.py
│   ├── tests.py
│   ├── urls.py
│   ├── views.py
│   └── __init__.py
├── payments/
│   ├── migrations/
│   │   └── __init__.py
│   ├── templates/
│   │   └── payments/
│   │       ├── create.html
│   │       ├── detail.html
│   │       ├── initiate_mpesa.html
│   │       ├── list.html
│   │       ├── invoices/
│   │       │   ├── create.html
│   │       │   ├── detail.html
│   │       │   ├── list.html
│   │       │   └── send.html
│   │       └── plans/
│   │           ├── create.html
│   │           ├── detail.html
│   │           └── list.html
│   ├── __pycache__/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── permissions.py
│   ├── serializers.py
│   ├── tests.py
│   ├── urls.py
│   ├── views.py
│   └── __init__.py
├── pesaflow/
│   ├── __pycache__/
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── __init__.py
├── static/
│   ├── css/
│   │   ├── style.css
│   └── js/
│       └── main.js
├── staticfiles/
├── templates/
│   ├── base/
│   │   ├── base.html
│   │   ├── navbar.html
│   │   ├── sidebar.html
│   │   ├── footer.html
│   │   └── messages.html
│   ├── index.html
│   ├── admin_dashboard.html
│   ├── business_dashboard.html
│   └── customer_dashboard.html
├── .env
├── fix_all_imports.py
├── manage.py
└── requirements.txt

---
## Features
Accounts Management: Registration, login, password reset, profile, and security.

Customer Management: CRUD operations for customers, group management, and data import.

Payments: M-Pesa integration, payment plans, and invoice management with sending capabilities.

Organizations: Manage multiple organizations, members, and organization-specific settings.

Integrations: Configure external integrations, including M-Pesa API, and view logs.

Notifications: Send notifications to users and track sent messages.

Dashboards: Admin, business, and customer dashboards with real-time metrics.

Modular Architecture: Each app is independent, making maintenance and scaling easier.

---
### Installation

Clone the repository:
git clone https://github.com/eKidenge/pesaflow.git
cd pesaflow

Create a virtual environment and activate it:
python -m venv venv
.\venv\Scripts\activate   # Windows
source venv/bin/activate  # Linux / Mac

