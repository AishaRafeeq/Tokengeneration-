from django.db import models

class QRSetting(models.Model):
    base_url = models.URLField(default='http://localhost:8000/token/')
    default_expiration_hours = models.IntegerField(default=24)
    default_error_correction = models.CharField(max_length=1, choices=(('L','7%'),('M','15%'),('Q','25%'),('H','30%')), default='M')
