"""
Security middleware for adding security headers with automatic cross-business support.
"""
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers with automatic cross-business integration support."""

    def process_response(self, request, response):
        # CORS Headers for automatic cross-business API access
        origin = request.META.get('HTTP_ORIGIN')

        # Automatically allow cross-origin requests for API/widget endpoints or in debug mode
        # In production, be more permissive to ensure cross-business integration works
        if (settings.DEBUG or
            self.is_cross_business_endpoint(request) or
            getattr(settings, 'ENABLE_CROSS_BUSINESS_ACCESS', True)):

            response['Access-Control-Allow-Origin'] = origin or '*'
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Accept, Accept-Language, Content-Language, Content-Type, Authorization, X-Requested-With, X-CSRFToken'
            response['Access-Control-Max-Age'] = '86400'  # 24 hours

        # Handle preflight OPTIONS requests
        if request.method == 'OPTIONS':
            response.status_code = 200
            return response

        # For cross-business integration testing, remove restrictive headers more aggressively
        if getattr(settings, 'ENABLE_CROSS_BUSINESS_ACCESS', True):
            # Always remove X-Frame-Options to allow embedding from any domain
            if 'X-Frame-Options' in response:
                del response['X-Frame-Options']

        # Handle X-Frame-Options and CSP for cross-business endpoints
        if self.is_cross_business_endpoint(request):
            # For cross-business endpoints, remove ALL restrictive headers
            headers_to_remove = ['X-Frame-Options', 'Content-Security-Policy']
            for header in headers_to_remove:
                if header in response:
                    del response[header]

            # Add debug headers to confirm cross-business handling
            response['X-Cross-Business-Enabled'] = 'true'
            response['X-Debug-Path'] = request.path
            response['X-Debug-Host'] = request.get_host()
            return response

        # Content-Security-Policy - only for non-embeddable content
        csp_parts = []

        csp_mappings = [
            ('CSP_DEFAULT_SRC', 'default-src'),
            ('CSP_SCRIPT_SRC', 'script-src'),
            ('CSP_STYLE_SRC', 'style-src'),
            ('CSP_FONT_SRC', 'font-src'),
            ('CSP_IMG_SRC', 'img-src'),
            ('CSP_CONNECT_SRC', 'connect-src'),
        ]

        # Only add frame-ancestors for internal pages, not embeddable ones
        for setting_name, directive in csp_mappings:
            if hasattr(settings, setting_name):
                sources = getattr(settings, setting_name)
                # Filter out wildcard for internal pages for better security
                if directive == 'default-src' and '*' in sources:
                    sources = tuple(src for src in sources if src != '*')
                    sources = sources or ("'self'",)
                csp_parts.append(f"{directive} {' '.join(sources)}")

        if csp_parts:
            response['Content-Security-Policy'] = '; '.join(csp_parts)

        return response

    def is_cross_business_endpoint(self, request):
        """Check if this is an endpoint designed for cross-business integration."""
        path = request.path

        # Automatically allow embedding for multiple URL patterns
        cross_business_patterns = [
            '/b/',            # Business booking URLs (b/business-slug/)
            '/api/',          # All API endpoints
            '/booking/',      # Public booking pages
            '/widget/',       # Widget endpoints
            '/embed/',        # Embed endpoints
        ]

        # Check if path matches any cross-business pattern
        if any(pattern in path for pattern in cross_business_patterns):
            return True

        # Special handling for root domain and subdomain routing
        # If the site uses subdomain routing (business.reserva.gr), handle root paths
        host = request.get_host().lower()
        if not host.startswith('www.') and host != 'reserva.gr' and host != '127.0.0.1' and host != 'localhost':
            # This might be a business subdomain, allow embedding
            return True

        # Handle numeric IDs or other business identifier patterns
        # Pattern like /6/dedi/iran/ or /123/business-name/
        import re
        if re.match(r'^/\d+/', path):
            return True

        # Allow embedding for short paths that might be business URLs
        path_parts = [p for p in path.split('/') if p]
        if len(path_parts) <= 3 and path_parts:
            # This could be a business URL pattern
            return True

        return False
