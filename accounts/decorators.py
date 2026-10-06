from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def role_required(*roles):
    """Decorator: allows access only to users with specified role(s)."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if request.user.role not in roles:
                messages.error(request, 'Δεν έχετε πρόσβαση σε αυτή τη σελίδα.')
                return redirect('landing')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def professional_required(view_func):
    """Decorator: only approved professionals can access."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        # Super admins may temporarily access a business panel for troubleshooting
        # only when an explicit business access session is active.
        if request.user.role == 'super_admin' and request.session.get('superadmin_business_access_id'):
            return view_func(request, *args, **kwargs)
        if request.user.role != 'professional':
            messages.error(request, 'Πρόσβαση μόνο για επαγγελματίες.')
            return redirect('landing')
        if not request.user.is_approved:
            messages.warning(request, 'Ο λογαριασμός σας δεν έχει εγκριθεί ακόμα.')
            return redirect('accounts:pending_approval')
        return view_func(request, *args, **kwargs)
    return _wrapped


def super_admin_required(view_func):
    """Decorator: only super admins can access."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if request.user.role != 'super_admin':
            messages.error(request, 'Πρόσβαση μόνο για διαχειριστές.')
            return redirect('landing')
        return view_func(request, *args, **kwargs)
    return _wrapped


def customer_required(view_func):
    """Decorator: only customers can access."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if request.user.role != 'customer':
            messages.error(request, 'Πρόσβαση μόνο για πελάτες.')
            return redirect('landing')
        return view_func(request, *args, **kwargs)
    return _wrapped
