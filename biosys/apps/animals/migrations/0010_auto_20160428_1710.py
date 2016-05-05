# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-04-28 09:10
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('animals', '0009_auto_20160428_1708'),
    ]

    operations = [
        migrations.AlterField(
            model_name='animalobservation',
            name='capture_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='animals.CaptureTypeLookup', verbose_name='Capture Type'),
        ),
        migrations.AlterField(
            model_name='animalobservation',
            name='sex',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='animals.SexLookup', verbose_name='Sex'),
        ),
    ]
