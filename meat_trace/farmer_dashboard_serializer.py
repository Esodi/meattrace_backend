from rest_framework import serializers
from .models import Animal, Activity
from .serializers import ActivitySerializer

class FarmerDashboardSerializer(serializers.Serializer):
    """
    Serializer for the farmer dashboard, providing a structured and validated
    representation of the data required by the frontend.
    """
    class UserSerializer(serializers.Serializer):
        id = serializers.IntegerField()
        username = serializers.CharField()
        first_name = serializers.CharField()
        last_name = serializers.CharField()
        email = serializers.EmailField()

    class StatisticsSerializer(serializers.Serializer):
        total_animals = serializers.IntegerField()
        active_animals = serializers.IntegerField()
        slaughtered_animals = serializers.IntegerField()
        transferred_animals = serializers.IntegerField()
        pending_transfers = serializers.IntegerField()

    class SummarySerializer(serializers.Serializer):
        animals_registered_this_month = serializers.IntegerField()
        animals_slaughtered_this_month = serializers.IntegerField()

    user = UserSerializer()
    statistics = StatisticsSerializer()
    species_breakdown = serializers.DictField(child=serializers.IntegerField())
    recent_activities = ActivitySerializer(many=True)
    summary = SummarySerializer()