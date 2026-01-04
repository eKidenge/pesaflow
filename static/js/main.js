// Main JavaScript file

$(document).ready(function() {
    // Initialize tooltips
    $('[data-bs-toggle="tooltip"]').tooltip();
    
    // Initialize popovers
    $('[data-bs-toggle="popover"]').popover();
    
    // Auto-dismiss alerts after 5 seconds
    $('.alert').not('.alert-permanent').delay(5000).fadeOut(300);
    
    // Confirm delete actions
    $('.confirm-delete').on('click', function(e) {
        if (!confirm('Are you sure you want to delete this item?')) {
            e.preventDefault();
            return false;
        }
    });
    
    // DataTables initialization
    if ($.fn.DataTable) {
        $('.datatable').DataTable({
            pageLength: 25,
            responsive: true,
            language: {
                search: "_INPUT_",
                searchPlaceholder: "Search...",
                lengthMenu: "_MENU_ records per page",
                info: "Showing _START_ to _END_ of _TOTAL_ entries",
                infoEmpty: "Showing 0 to 0 of 0 entries",
                infoFiltered: "(filtered from _MAX_ total entries)"
            }
        });
    }
    
    // Form validation
    $('.needs-validation').on('submit', function(e) {
        if (!this.checkValidity()) {
            e.preventDefault();
            e.stopPropagation();
        }
        $(this).addClass('was-validated');
    });
    
    // Copy to clipboard
    $('.copy-to-clipboard').on('click', function() {
        const text = $(this).data('text');
        navigator.clipboard.writeText(text).then(function() {
            alert('Copied to clipboard!');
        });
    });
    
    // Toggle password visibility
    $('.toggle-password').on('click', function() {
        const input = $(this).siblings('input');
        const icon = $(this).find('i');
        const type = input.attr('type') === 'password' ? 'text' : 'password';
        input.attr('type', type);
        icon.toggleClass('fa-eye fa-eye-slash');
    });
    
    // Load more items (infinite scroll)
    let page = 1;
    let loading = false;
    
    $(window).scroll(function() {
        if ($(window).scrollTop() + $(window).height() >= $(document).height() - 100) {
            if (!loading && $('.load-more').length) {
                loading = true;
                page++;
                loadMoreItems(page);
            }
        }
    });
    
    function loadMoreItems(pageNum) {
        const url = $('.load-more').data('url') + '?page=' + pageNum;
        
        $.ajax({
            url: url,
            type: 'GET',
            beforeSend: function() {
                $('.load-more').html('<i class="fas fa-spinner fa-spin"></i> Loading...');
            },
            success: function(data) {
                if (data.html) {
                    $('.items-container').append(data.html);
                    
                    if (data.has_next) {
                        $('.load-more').html('Load More');
                    } else {
                        $('.load-more').remove();
                    }
                } else {
                    $('.load-more').remove();
                }
                loading = false;
            },
            error: function() {
                $('.load-more').html('Error loading more items');
                setTimeout(function() {
                    $('.load-more').html('Load More');
                    loading = false;
                }, 2000);
            }
        });
    }
    
    // Real-time updates (WebSocket simulation)
    if (typeof io !== 'undefined') {
        const socket = io();
        
        socket.on('new_payment', function(data) {
            showToast('New Payment', data.message, 'success');
            updateDashboardStats();
        });
        
        socket.on('payment_failed', function(data) {
            showToast('Payment Failed', data.message, 'error');
        });
        
        socket.on('new_notification', function(data) {
            showToast('New Notification', data.message, 'info');
            updateNotificationBadge();
        });
    }
    
    // Toast notification
    function showToast(title, message, type) {
        const toast = `
            <div class="toast align-items-center text-bg-${type} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        <strong>${title}:</strong> ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;
        
        $('.toast-container').append(toast);
        $('.toast').last().toast('show');
        
        setTimeout(function() {
            $('.toast').first().remove();
        }, 5000);
    }
    
    // Update dashboard stats
    function updateDashboardStats() {
        $.ajax({
            url: '/api/v1/dashboard/stats/',
            type: 'GET',
            success: function(data) {
                // Update stats cards
                $('.total-customers').text(data.total_customers);
                $('.total-revenue').text('KES ' + data.total_revenue.toLocaleString());
                $('.success-rate').text(data.success_rate + '%');
                $('.pending-invoices').text(data.pending_invoices);
            }
        });
    }
    
    // Update notification badge
    function updateNotificationBadge() {
        $.ajax({
            url: '/api/v1/notifications/unread-count/',
            type: 'GET',
            success: function(data) {
                const badge = $('.notification-badge');
                if (data.count > 0) {
                    badge.text(data.count).show();
                } else {
                    badge.hide();
                }
            }
        });
    }
    
    // Initialize date pickers
    if ($.fn.datepicker) {
        $('.datepicker').datepicker({
            format: 'yyyy-mm-dd',
            autoclose: true,
            todayHighlight: true
        });
    }
    
    // Initialize select2
    if ($.fn.select2) {
        $('.select2').select2({
            theme: 'bootstrap-5'
        });
    }
    
    // Format currency inputs
    $('.currency-input').on('input', function() {
        let value = $(this).val().replace(/[^\d.]/g, '');
        if (value) {
            value = parseFloat(value).toLocaleString('en-KE', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
            $(this).val(value);
        }
    });
});

// Format phone numbers
function formatPhoneNumber(phone) {
    phone = phone.replace(/\D/g, '');
    if (phone.startsWith('254')) {
        phone = phone.replace(/^254/, '0');
    }
    return phone.replace(/(\d{3})(\d{3})(\d{3})/, '$1 $2 $3');
}

// Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-KE', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Format currency
function formatCurrency(amount, currency = 'KES') {
    return currency + ' ' + parseFloat(amount).toLocaleString('en-KE', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Export data
function exportData(url, format = 'csv') {
    window.location.href = url + '?format=' + format;
}