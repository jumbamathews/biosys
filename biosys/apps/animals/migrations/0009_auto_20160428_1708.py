# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-04-28 09:08
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('animals', '0008_auto_20160428_1703'),
    ]

    operations = [
        migrations.AlterField(
            model_name='animalobservation',
            name='reproductive_condition',
            field=models.CharField(blank=True, choices=[('', ''), ('developed', 'developed'), ('undeveloped', 'undeveloped')], default='', max_length=20, verbose_name='Reproductive condition'),
        ),
    ]
