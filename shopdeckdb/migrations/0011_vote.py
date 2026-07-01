from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shopdeckdb', '0010_title_demo'),
    ]

    operations = [
        migrations.CreateModel(
            name='Vote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('age', models.IntegerField()),
                ('gender', models.CharField(max_length=10)),
                ('q3', models.CharField(max_length=10)),
                ('q4', models.BooleanField()),
                ('q5', models.BooleanField()),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='shopdeckdb.client3ds')),
                ('voted_title', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='shopdeckdb.title')),
            ],
        ),
    ]
