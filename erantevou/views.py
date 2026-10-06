from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.http import JsonResponse
from django.http import Http404
from django.utils.html import escape
from django.templatetags.static import static
from django.db.models import Q
from django.db.models import Count, Max
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.template.response import TemplateResponse
from django.contrib.sites.requests import RequestSite
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
import json
from businesses.models import Business
from bookings.models import Booking
from erantevou.decorators import cross_business_view


def landing(request):
    """Landing page for Reserva platform — customer facing."""
    businesses = (
        Business.objects
        .filter(is_active=True, is_approved=True)
        .prefetch_related('services')
        .order_by('name')
    )
    # Filter out businesses without services
    businesses = [b for b in businesses if b.services.filter(is_active=True).exists()]
    return render(request, 'landing.html', {
        'hide_sidebar': True,
        'businesses': businesses,
    })


def features_view(request):
    """Public features page describing the Reserva platform."""
    return render(request, 'features.html', {
        'hide_sidebar': True,
    })


def business_browser_view(request):
    """Public directory page for browsing all businesses."""
    businesses = (
        Business.objects
        .filter(is_active=True, is_approved=True)
        .prefetch_related('services')
        .order_by('name')
    )
    return render(request, 'businesses/browser.html', {
        'hide_sidebar': True,
        'businesses': businesses,
    })


@cross_business_view
def widget_view(request, business_slug):
    """Embeddable widget/iframe view — minimal layout, no sidebar."""
    from businesses.models import Service, Employee
    business = get_object_or_404(Business, slug=business_slug, is_active=True, is_approved=True)
    services = Service.objects.filter(business=business, is_active=True)
    employees = Employee.objects.filter(business=business, is_active=True).exclude(
        Q(name__iexact='system', title__iexact='automatic assignment') |
        Q(name='Σύστημα', title='Αυτόματη Ανάθεση')
    )
    return render(request, 'widget/embed.html', {
        'business': business,
        'hide_sidebar': True,
        'services': services,
        'employees': employees,
    })


def business_custom_page_view(request, business_slug):
    """Serve optional business-uploaded custom HTML page at /<business-slug>/."""
    business = get_object_or_404(Business, slug=business_slug, is_active=True, is_approved=True)

    if business.public_site_mode == 'external_website':
        if business.external_website_url:
            return redirect(business.external_website_url)
        return redirect('public_booking:booking_page', business_slug=business.slug)

    if business.public_site_mode == 'built_in_site' or (business.public_site_mode == 'booking_page' and business.custom_site_enabled):
        from businesses.models import Service, Employee
        services = Service.objects.filter(business=business, is_active=True)
        employees = Employee.objects.filter(business=business, is_active=True).exclude(
            Q(name__iexact='system', title__iexact='automatic assignment') |
            Q(name='Σύστημα', title='Αυτόματη Ανάθεση')
        )
        return render(request, 'businesses/custom_site.html', {
            'business': business,
            'services': services,
            'employees': employees,
            'widget_url': request.build_absolute_uri(f'/widget/{business.slug}/'),
            'booking_url': request.build_absolute_uri(business.get_booking_url()),
            'hide_sidebar': True,
        })

    if business.public_site_mode == 'custom_html' and business.custom_landing_html:
        pass
    elif business.custom_landing_html and business.public_site_mode == 'booking_page':
        pass
    else:
        return redirect('public_booking:booking_page', business_slug=business.slug)

    try:
        with business.custom_landing_html.open('rb') as file_obj:
            html_text = file_obj.read().decode('utf-8', errors='replace')
    except OSError:
        return redirect('public_booking:booking_page', business_slug=business.slug)

    widget_url = request.build_absolute_uri(f'/widget/{business.slug}/')
    booking_url = request.build_absolute_uri(business.get_booking_url())
    logo_url = request.build_absolute_uri(business.logo.url) if business.logo else ''

    widget_embed = f'''
<section style="margin:32px auto;max-width:1100px;padding:0 16px;">
    <div style="border:1px solid rgba(201,162,39,.18);border-radius:20px;overflow:hidden;box-shadow:0 18px 60px rgba(0,0,0,.12);background:#fff;">
        <iframe src="{escape(widget_url)}" title="Reserva Booking Widget" style="width:100%;min-height:900px;border:0;display:block;background:#fff;"></iframe>
    </div>
    <p style="text-align:center;margin-top:12px;font:600 14px/1.4 Arial,sans-serif;color:#6b7280;">
        Online booking powered by Reserva
    </p>
</section>
'''

    widget_placeholder_present = ('{{RESERVA_WIDGET}}' in html_text) or ('{{RESERVA_WIDGET_IFRAME}}' in html_text)

    replacements = {
        '{{RESERVA_WIDGET}}': widget_embed,
        '{{RESERVA_WIDGET_IFRAME}}': widget_embed,
        '{{RESERVA_BOOKING_URL}}': booking_url,
        '{{RESERVA_WIDGET_URL}}': widget_url,
        '{{RESERVA_BUSINESS_NAME}}': escape(business.name),
        '{{RESERVA_LOGO_URL}}': escape(logo_url),
    }

    for placeholder, value in replacements.items():
        html_text = html_text.replace(placeholder, value)

    if not widget_placeholder_present:
        closing_body = html_text.lower().rfind('</body>')
        if closing_body != -1:
            html_text = html_text[:closing_body] + widget_embed + html_text[closing_body:]
        else:
            html_text += widget_embed

    response = HttpResponse(html_text, content_type='text/html; charset=utf-8')
    response['X-Frame-Options'] = 'ALLOWALL'
    return response


# Legal / GDPR pages
def privacy_view(request):
    """Privacy policy page."""
    return render(request, 'legal/privacy.html', {'hide_sidebar': True})


def terms_view(request):
    """Terms of service page."""
    return render(request, 'legal/terms.html', {'hide_sidebar': True})


def contact_view(request):
    """Contact page."""
    return render(request, 'legal/contact.html', {'hide_sidebar': True})


def about_view(request):
    """About us page."""
    return render(request, 'legal/about.html', {'hide_sidebar': True})


def robots_txt_view(request):
    """Robots.txt with sitemap declaration for search engines."""
    sitemap_url = request.build_absolute_uri('/sitemap.xml')
    content = (
        'User-agent: *\n'
        'Allow: /\n\n'
        'Disallow: /admin/\n'
        'Disallow: /superadmin/\n\n'
        f'Sitemap: {sitemap_url}\n'
    )
    return HttpResponse(content, content_type='text/plain; charset=utf-8')


def favicon_ico_redirect_view(request):
    """Canonical favicon endpoint for crawlers that request /favicon.ico."""
    return redirect('/static/favicon.svg?v=20260404', permanent=True)


def pwa_manifest_view(request):
    """Web app manifest for installable PWA support."""
    manifest = {
        'id': '/',
        'name': 'Reserva',
        'short_name': 'Reserva',
        'description': 'Online booking platform for businesses and customers.',
        'lang': 'el',
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'orientation': 'portrait-primary',
        'background_color': '#ffffff',
        'theme_color': '#c9a227',
        'icons': [
            {
                'src': static('img/pwa-192.png'),
                'sizes': '192x192',
                'type': 'image/png',
                'purpose': 'any maskable',
            },
            {
                'src': static('img/pwa-512.png'),
                'sizes': '512x512',
                'type': 'image/png',
                'purpose': 'any maskable',
            },
        ],
    }
    return HttpResponse(
        json.dumps(manifest),
        content_type='application/manifest+json; charset=utf-8',
    )


def pwa_offline_view(request):
    """Offline fallback page for PWA navigation requests."""
    return render(request, 'offline.html', {'hide_sidebar': True})


def pwa_service_worker_view(request):
    """Root-scoped service worker for caching shell and offline fallback."""
    cache_name = 'reserva-pwa-v5'
    offline_url = reverse('pwa_offline')
    core_urls = [
    '/',
    offline_url,
        reverse('pwa_manifest'),
    static('css/style.css') + '?v=20260426-1',
    static('css/business-panel.css') + '?v=20260426-1',
        static('img/pwa-192.png'),
        static('img/pwa-512.png'),
    static('favicon.svg'),
    ]

    urls_js = ',\n  '.join([f"'{u}'" for u in core_urls])
    sw_body = f"""
const CACHE_NAME = '{cache_name}';
const OFFLINE_URL = '{offline_url}';
const CORE_ASSETS = [
    {urls_js}
];

self.addEventListener('install', (event) => {{
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) =>
            Promise.all(
                CORE_ASSETS.map((url) =>
                    fetch(url, {{ cache: 'no-store' }})
                        .then((resp) => {{
                            if (!resp || !resp.ok) return null;
                            return cache.put(url, resp.clone());
                        }})
                        .catch(() => null)
                )
            )
        )
    );
    self.skipWaiting();
}});

self.addEventListener('activate', (event) => {{
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(
            keys
                .filter((key) => key !== CACHE_NAME)
                .map((key) => caches.delete(key))
        ))
    );
    self.clients.claim();
}});

self.addEventListener('fetch', (event) => {{
    if (event.request.method !== 'GET') return;

    const req = event.request;
    const url = new URL(req.url);

    if (req.mode === 'navigate') {{
        event.respondWith(
            fetch(req)
                .then((resp) => {{
                    if (resp && resp.status === 200) {{
                        const copy = resp.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
                    }}
                    return resp;
                }})
                .catch(() => caches.match(req).then((cached) => cached || caches.match(OFFLINE_URL)))
        );
        return;
    }}

    if (url.origin === self.location.origin) {{
        event.respondWith(
            caches.match(req).then((cached) => {{
                if (cached) return cached;
                return fetch(req).then((resp) => {{
                    if (resp && resp.status === 200 && resp.type === 'basic') {{
                        const copy = resp.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
                    }}
                    return resp;
                }});
            }})
        );
    }}
}});
""".strip()

    response = HttpResponse(sw_body, content_type='application/javascript; charset=utf-8')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response


def sitemap_xml_view(request, sitemaps, section=None, template_name='sitemap.xml', content_type='application/xml'):
    """Sitemap endpoint that always uses request host instead of Site model domain."""
    req_protocol = request.scheme
    req_site = RequestSite(request)

    if section is not None:
        if section not in sitemaps:
            raise Http404(f"No sitemap available for section: {section!r}")
        maps = [sitemaps[section]]
    else:
        maps = sitemaps.values()

    page = request.GET.get('p', 1)
    urls = []

    for site in maps:
        try:
            if callable(site):
                site = site()
            urls.extend(site.get_urls(page=page, site=req_site, protocol=req_protocol))
        except EmptyPage:
            raise Http404(f'Page {page} empty')
        except PageNotAnInteger:
            raise Http404(f"No page '{page}'")

    response = TemplateResponse(
        request,
        template_name,
        {'urlset': urls},
        content_type=content_type,
    )
    response.headers['X-Robots-Tag'] = 'noindex, noodp, noarchive'
    return response


@login_required
def live_bookings_state(request):
    """Return a lightweight booking state marker used by panel auto-refresh polling."""
    user = request.user

    if user.role == 'customer':
        queryset = Booking.objects.filter(customer=user)
    elif user.role == 'professional':
        try:
            business = user.business
        except ObjectDoesNotExist:
            business = None
        queryset = Booking.objects.filter(business=business) if business else Booking.objects.none()
    elif user.role == 'employee':
        from businesses.models import Employee
        employee = Employee.objects.filter(user=user, is_active=True).first()
        queryset = Booking.objects.filter(employee=employee) if employee else Booking.objects.none()
    elif user.role == 'super_admin':
        troubleshooting_business_id = request.session.get('superadmin_business_access_id')
        if troubleshooting_business_id:
            queryset = Booking.objects.filter(business_id=troubleshooting_business_id)
        else:
            queryset = Booking.objects.all()
    else:
        queryset = Booking.objects.none()

    summary = queryset.aggregate(
        total=Count('id'),
        latest_id=Max('id'),
        latest_created=Max('created_at'),
        latest_updated=Max('updated_at'),
    )

    latest_created = summary['latest_created'].isoformat() if summary['latest_created'] else ''
    latest_updated = summary['latest_updated'].isoformat() if summary['latest_updated'] else ''
    marker = f"{summary['total']}|{summary['latest_id'] or 0}|{latest_created}|{latest_updated}"

    return JsonResponse({
        'marker': marker,
        'count': summary['total'] or 0,
    })


# Custom error handlers
def handler404(request, exception=None):
    """Custom 404 page."""
    return render(request, '404.html', {'hide_sidebar': True}, status=404)


def handler500(request):
    """Custom 500 page."""
    return render(request, '500.html', {'hide_sidebar': True}, status=500)
