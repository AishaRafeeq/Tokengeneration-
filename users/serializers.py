from rest_framework import serializers
from .models import User, Category


class CategorySerializer(serializers.ModelSerializer):
    """Serialize categories with full details."""
    class Meta:
        model = Category
        fields = ["id", "name", "color"]


class UserSerializer(serializers.ModelSerializer):
    """
    User serializer:
    - Nested categories for read.
    - Accept category IDs for write.
    - Include QR permissions.
    """
    categories = CategorySerializer(many=True, read_only=True)  # read-only nested categories
    category_ids = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        many=True,
        write_only=True,
        required=False
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "categories",      # nested read-only
            "category_ids",   
             "full_name", # write-only
            "can_scan_qr",
            "can_generate_qr",
            "can_view_analytics",
            "can_verify_qr",
            "is_active",
            "is_staff",
            "is_superuser",
            "password",
        ]
        extra_kwargs = {
            "password": {"write_only": True, "required": False},
        }

    def create(self, validated_data):
        categories = validated_data.pop("category_ids", [])
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        if categories:
            user.categories.set(categories)
        return user

    def update(self, instance, validated_data):
        categories = validated_data.pop("category_ids", None)
        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)
        instance.save()
        if categories is not None:
            instance.categories.set(categories)
        return instance
