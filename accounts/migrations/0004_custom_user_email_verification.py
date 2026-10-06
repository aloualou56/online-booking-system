# Generated migration for CustomUser OTP fields and email verification

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_useremail'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='is_email_verified',
            field=models.BooleanField(default=False, help_text='Email verification status', verbose_name='Email Verified'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='email_otp',
            field=models.CharField(blank=True, max_length=6, null=True, verbose_name='Email OTP'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='email_otp_expires_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='OTP Expiration Time'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='is_deactivated',
            field=models.BooleanField(default=False, help_text='For professionals: account is deactivated but not deleted', verbose_name='Account Deactivated'),
        ),
    ]
