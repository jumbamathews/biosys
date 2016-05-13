# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-05-13 05:41
from __future__ import unicode_literals

import django.contrib.gis.db.models.fields
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0014_auto_20160506_1142'),
    ]

    operations = [
        migrations.CreateModel(
            name='DataDescriptor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('type', models.CharField(choices=[('project', 'Project'), ('site', 'Site'), ('dataset', 'Dataset'), ('observation', 'Observation'), ('species_observation', 'Species observation')], default='dataset', max_length=100)),
                ('data_package', django.contrib.postgres.fields.jsonb.JSONField()),
            ],
        ),
        migrations.CreateModel(
            name='Observation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', django.contrib.postgres.fields.jsonb.JSONField()),
                ('date_time', models.DateTimeField()),
                ('geometry', django.contrib.gis.db.models.fields.GeometryField(blank=True, null=True, srid=4326)),
                ('data_descriptor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.DataDescriptor')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SiteDataSet',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', django.contrib.postgres.fields.jsonb.JSONField()),
                ('data_descriptor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.DataDescriptor')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.RenameModel(
            old_name='SpeciesObservation',
            new_name='OldSpeciesObservation',
        ),
        migrations.AddField(
            model_name='project',
            name='data',
            field=django.contrib.postgres.fields.jsonb.JSONField(null=True),
        ),
        migrations.AddField(
            model_name='site',
            name='data',
            field=django.contrib.postgres.fields.jsonb.JSONField(null=True),
        ),
        migrations.AddField(
            model_name='sitedataset',
            name='site',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.Site'),
        ),
        migrations.AddField(
            model_name='observation',
            name='site',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.Site'),
        ),
        migrations.AddField(
            model_name='datadescriptor',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.Project'),
        ),
        migrations.AddField(
            model_name='project',
            name='data_descriptor',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='descriptors', related_query_name='descriptor', to='main.DataDescriptor'),
        ),
        migrations.AddField(
            model_name='site',
            name='data_descriptor',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='main.DataDescriptor'),
        ),
    ]
