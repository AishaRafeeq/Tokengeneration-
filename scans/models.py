from django.db import models
from tokens.models import Token
from users.models import User

class Scan(models.Model):
    token = models.ForeignKey(Token, on_delete=models.CASCADE)
    scanned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    scanned_at = models.DateTimeField(auto_now_add=True)
