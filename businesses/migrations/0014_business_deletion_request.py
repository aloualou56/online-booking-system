# Generated migration for BusinessDeletionRequest model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('businesses', '0013_notificationcontact'),
    ]

    operations = [
        migrations.CreateModel(
            name='BusinessDeletionRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField(blank=True, help_text='Optional reason provided by the owner', verbose_name='Reason for Deletion')),
                ('status', models.CharField(choices=[('pending', 'Pending Approval'), ('approved', 'Approved - Deactivated'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled by Owner')], default='pending', max_length=20, verbose_name='Status')),
                ('requested_at', models.DateTimeField(auto_now_add=True, verbose_name='Requested At')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='Reviewed At')),
                ('admin_notes', models.TextField(blank=True, verbose_name='Admin Notes')),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deletion_requests', to='businesses.business', verbose_name='Business')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='business_deletion_requests', to=settings.AUTH_USER_MODEL, verbose_name='Owner')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_business_deletions', to=settings.AUTH_USER_MODEL, verbose_name='Reviewed By')),
            ],
            options={
                'verbose_name': 'Business Deletion Request',
                'verbose_name_plural': 'Business Deletion Requests',
                'ordering': ['-requested_at'],
            },
        ),
    ]
