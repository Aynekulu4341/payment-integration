# Generated by Django 5.1.7 on 2025-05-01 16:39

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0010_remove_transaction_completed_transaction_currency_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='transaction',
            name='currency',
        ),
        migrations.RemoveField(
            model_name='transaction',
            name='status',
        ),
        migrations.RemoveField(
            model_name='transaction',
            name='updated_at',
        ),
        migrations.AddField(
            model_name='transaction',
            name='completed',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='campaign',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name='campaign',
            name='target_amount',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='campaign',
            name='target_currency',
            field=models.CharField(choices=[('usd', 'USD'), ('birr', 'Birr')], default='birr', max_length=10),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='campaign',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='payments.campaign'),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='payment_method',
            field=models.CharField(choices=[('paypal', 'PayPal'), ('telebirr', 'Telebirr')], max_length=20),
        ),
    ]
