from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from . import views as core_views
from bookings import views as booking_views
from .sitemaps import StaticViewSitemap, BusinessPublicPageSitemap, BusinessBookingPageSitemap


sitemaps = {
    'static': StaticViewSitemap,
    'business-public': BusinessPublicPageSitemap,
    'business-booking': BusinessBookingPageSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/live-bookings-state/', core_views.live_bookings_state, name='live_bookings_state'),
    path('manifest.webmanifest', core_views.pwa_manifest_view, name='pwa_manifest'),
    path('sw.js', core_views.pwa_service_worker_view, name='pwa_service_worker'),
    path('offline/', core_views.pwa_offline_view, name='pwa_offline'),
    path('favicon.ico', core_views.favicon_ico_redirect_view, name='favicon_ico'),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('business/', include('businesses.urls', namespace='businesses')),
    path('bookings/', include('bookings.urls', namespace='bookings')),
    path('payments/', include('payments.urls', namespace='payments')),
    path('reviews/', include('reviews.urls', namespace='reviews')),
    path('reports/', include('reports.urls', namespace='reports')),
    path('notifications/', include('notifications.urls', namespace='notifications')),

    # Public booking page: booking.erantevou.gr/<slug>
    path('b/<slug:business_slug>/', include('bookings.public_urls', namespace='public_booking')),

    # Widget / iframe embed endpoint
    path('widget/<slug:business_slug>/', core_views.widget_view, name='widget'),

    # Short guest booking URL used in compact SMS.
    path('g/<str:guest_code>/', booking_views.guest_short_link, name='guest_short_link'),

    # Super Admin panel
    path('superadmin/', include('accounts.admin_urls', namespace='superadmin')),

    # Legal / GDPR pages
    path('privacy/', core_views.privacy_view, name='privacy'),
    path('terms/', core_views.terms_view, name='terms'),
    path('contact/', core_views.contact_view, name='contact'),
    path('about/', core_views.about_view, name='about'),
    path('features/', core_views.features_view, name='features'),
    path('businesses/', core_views.business_browser_view, name='business_browser'),
    path('robots.txt', core_views.robots_txt_view, name='robots_txt'),
    path('sitemap.xml', core_views.sitemap_xml_view, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

    path('', core_views.landing, name='landing'),
    path('<slug:business_slug>/', core_views.business_custom_page_view, name='business_custom_page'),
]

# Custom error handlers (used when DEBUG=False)
handler404 = 'erantevou.views.handler404'
handler500 = 'erantevou.views.handler500'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
