from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_custom_user_email_verification'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='is_phone_verified',
            field=models.BooleanField(
                default=False,
                help_text='Phone verification status (for professionals with mobile numbers)',
                verbose_name='Phone Verified',
            ),
        ),
        migrations.AddField(
            model_name='customuser',
            name='phone_otp',
            field=models.CharField(blank=True, max_length=6, null=True, verbose_name='Phone OTP'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='phone_otp_expires_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Phone OTP Expiration Time'),
        ),
    ]
