from rest_framework import serializers
from .models import Token, QRCode, QRScan, QRSettings, QRTemplate, AuditLog
from .utils import generate_qr_code
from django.utils import timezone
from django.core.files.base import ContentFile


# ----------------------------
# Token Serializer
# ----------------------------
from .models import QRCode
from .utils import generate_qr_code

class TokenSerializer(serializers.ModelSerializer):
    qr_code = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Token
        fields = ["id", "token_id", "category", "category_name", "status", "issued_at", "qr_code"]

    def get_qr_code(self, obj):
        if hasattr(obj, 'qr_code'):
            return {
                "image": obj.qr_code.image.url if obj.qr_code.image else None,
                "payload": obj.qr_code.payload,
            }
        return None

    def create(self, validated_data):
        # Token.save() will auto-generate the QRCode
        return Token.objects.create(**validated_data)


# ----------------------------
# QR Code Serializer
# ----------------------------
from rest_framework import serializers
from .models import QRCode

class QRCodeSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = QRCode
        fields = ["id", "image"]

    def get_image(self, obj):
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url


# ----------------------------
# QR Scan Serializer
# ----------------------------
class QRScanSerializer(serializers.ModelSerializer):
    class Meta:
        model = QRScan
        fields = '__all__'
        read_only_fields = ['scan_time', 'scanned_by', 'ip_address', 'user_agent']


# ----------------------------
# QR Settings Serializer
# ----------------------------
class QRSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = QRSettings
        fields = '__all__'


# ----------------------------
# QR Template Serializer
# ----------------------------
class QRTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = QRTemplate
        fields = '__all__'


# ----------------------------
# Audit Log Serializer
# ----------------------------
class AuditLogSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user',
            'action',
            'ip_address',
            'user_agent',
            'timestamp',
            'extra_data',
        ]
        read_only_fields = ['id', 'user', 'timestamp']

class ScanActivityReportSerializer(serializers.ModelSerializer):
    token_id = serializers.SerializerMethodField()
    token_category = serializers.SerializerMethodField()
    scanner_name = serializers.SerializerMethodField()
    scan_result = serializers.SerializerMethodField()

    class Meta:
        model = QRScan
        fields = [
            "token_id",
            "token_category",
            "scan_time",
            "scanner_name",
            "ip_address",
            "device_type",
            "verification_status",
            "scan_result",
        ]

    def get_token_id(self, obj):
        if obj.qr:
            return obj.qr.token.token_id
        elif hasattr(obj, 'token'):
            return obj.token.token_id
        return "INVALID"

    def get_token_category(self, obj):
        if obj.qr and obj.qr.token.category:
            return obj.qr.token.category.name
        elif hasattr(obj, 'token') and obj.token.category:
            return obj.token.category.name
        return None

    def get_scanner_name(self, obj):
        if obj.scanned_by:
            return obj.scanned_by.get_full_name() or obj.scanned_by.username
        return "Unknown"

    def get_scan_result(self, obj):
        if obj.verification_status == "MANUAL":
            return "MANUAL ENTRY"
        if not obj.qr:
            return "INVALID"
        token = obj.qr.token
        now = timezone.now()
        if token.status == "completed":
            return "ALREADY USED"
        elif obj.qr.expires_at < now:
            return "EXPIRED"
        elif obj.verification_status == "SUCCESS":
            return "VALID"
        else:
            return "INVALID"


# ----------------------------
# Verification Log Serializer
# ----------------------------
class VerificationLogSerializer(serializers.ModelSerializer):
    token_id = serializers.SerializerMethodField()
    token_category = serializers.SerializerMethodField()
    verifier_name = serializers.SerializerMethodField()
    verification_result = serializers.SerializerMethodField()

    class Meta:
        model = QRScan
        fields = [
            "token_id",
            "token_category",
            "scan_time",
            "verifier_name",
            "ip_address",
            "device_type",
            "verification_result",
        ]

    def get_token_id(self, obj):
        return obj.qr.token.token_id if obj.qr else "INVALID"

    def get_token_category(self, obj):
        return obj.qr.token.category.name if obj.qr and obj.qr.token.category else None

    def get_verifier_name(self, obj):
        if obj.scanned_by:
            return obj.scanned_by.get_full_name() or obj.scanned_by.username
        return "Unknown"

    def get_verification_result(self, obj):
        if obj.verification_status == "MANUAL":
            return "MANUAL ENTRY"
        if not obj.qr:
            return "INVALID"
        now = timezone.now()
        if obj.qr.expires_at < now:
            return "EXPIRED"
        elif obj.verification_status == "SUCCESS":
            return "VALID"
        else:
            return "FAILED"
