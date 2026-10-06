"""
Decorators for cross-business integration and security.
"""
from functools import wraps
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse


def cross_business_api(view_func):
    """
    Decorator to make API views compatible with cross-business integration.
    Automatically handles CORS, CSRF, and iframe embedding.
    """
    @wraps(view_func)
    @xframe_options_exempt  # Allow embedding in iframes
    def wrapper(request, *args, **kwargs):
        # Handle preflight OPTIONS requests
        if request.method == 'OPTIONS':
            response = JsonResponse({})
            response['Access-Control-Allow-Origin'] = request.META.get('HTTP_ORIGIN', '*')
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Accept, Content-Type, Authorization, X-Requested-With, X-CSRFToken'
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Max-Age'] = '86400'
            return response

        # Call the original view
        response = view_func(request, *args, **kwargs)

        # Add CORS headers to the response
        origin = request.META.get('HTTP_ORIGIN')
        if origin:
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Credentials'] = 'true'

        return response

    return wrapper


def cross_business_view(view_func):
    """
    Decorator to make regular views compatible with cross-business embedding.
    Removes X-Frame-Options to allow iframe embedding.
    """
    @wraps(view_func)
    @xframe_options_exempt
    def wrapper(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)

        # Ensure the response can be embedded
        if hasattr(response, '__setitem__'):
            # Remove any X-Frame-Options that might block embedding
            if 'X-Frame-Options' in response:
                del response['X-Frame-Options']

        return response

    return wrapper