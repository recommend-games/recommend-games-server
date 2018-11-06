# Generated by Django 2.1.3 on 2018-11-06 11:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('games', '0005_auto_20181023_1141'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='external_link',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='game',
            name='image_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='game',
            name='video_url',
            field=models.URLField(blank=True, null=True),
        ),
    ]
