from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from businesses.models import Business


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return [
            'landing',
            'features',
            'business_browser',
            'about',
            'contact',
            'privacy',
            'terms',
        ]

    def location(self, item):
        return reverse(item)


class BusinessPublicPageSitemap(Sitemap):
    priority = 0.7
    changefreq = 'daily'

    def items(self):
        return Business.objects.filter(is_active=True, is_approved=True)

    def location(self, obj):
        return reverse('business_custom_page', kwargs={'business_slug': obj.slug})

    def lastmod(self, obj):
        return obj.updated_at


class BusinessBookingPageSitemap(Sitemap):
    priority = 0.9
    changefreq = 'daily'

    def items(self):
        return Business.objects.filter(is_active=True, is_approved=True)

    def location(self, obj):
        return obj.get_booking_url()

    def lastmod(self, obj):
        return obj.updated_at
