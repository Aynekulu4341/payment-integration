# Generated by Django 5.1.7 on 2025-04-26 08:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0008_alter_campaign_created_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='target_amount',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AddField(
            model_name='campaign',
            name='target_currency',
            field=models.CharField(choices=[('usd', 'USD'), ('birr', 'Birr')], default='birr', max_length=10),
        ),
    ]
