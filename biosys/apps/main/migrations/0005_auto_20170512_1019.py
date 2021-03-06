# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-05-12 02:19
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('main', '0004_auto_20170203_1232'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='dataset',
            options={'ordering': ['name']},
        ),
        migrations.AlterModelOptions(
            name='project',
            options={'ordering': ['title']},
        ),
        migrations.AlterModelOptions(
            name='record',
            options={'ordering': ['id']},
        ),
        migrations.AlterModelOptions(
            name='site',
            options={'ordering': ['code']},
        ),
        migrations.AddField(
            model_name='record',
            name='created',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='record',
            name='last_modified',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='record',
            name='source_info',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='custodians',
            field=models.ManyToManyField(help_text='Users that have write/upload access to the data of this project.',
                                         to=settings.AUTH_USER_MODEL),
        ),
    ]
