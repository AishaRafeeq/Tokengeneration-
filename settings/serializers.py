from rest_framework import serializers
from .models import QRSetting

class QRSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = QRSetting
        fields = '__all__'
