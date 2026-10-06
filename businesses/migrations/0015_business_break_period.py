from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0014_business_deletion_request'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='break_end_time',
            field=models.TimeField(blank=True, help_text='Προαιρετικό καθημερινό διάλειμμα κατά το οποίο δεν δέχονται ραντεβού.', null=True, verbose_name='Λήξη διαλείμματος'),
        ),
        migrations.AddField(
            model_name='business',
            name='break_start_time',
            field=models.TimeField(blank=True, help_text='Προαιρετικό καθημερινό διάλειμμα κατά το οποίο δεν δέχονται ραντεβού.', null=True, verbose_name='Έναρξη διαλείμματος'),
        ),
    ]
