from rest_framework import serializers


class CoordSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=300)
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)


class TripPlanRequestSerializer(serializers.Serializer):
    current_location = serializers.CharField(min_length=2, max_length=200)
    pickup_location = serializers.CharField(min_length=2, max_length=200)
    dropoff_location = serializers.CharField(min_length=2, max_length=200)
    current_coord = CoordSerializer(required=False)
    pickup_coord = CoordSerializer(required=False)
    dropoff_coord = CoordSerializer(required=False)
    current_cycle_hours = serializers.FloatField(min_value=0, max_value=70)
    cycle_type = serializers.ChoiceField(choices=["70_8", "60_7"], default="70_8")
    start_time = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        if attrs["pickup_location"].strip().lower() == attrs["dropoff_location"].strip().lower():
            raise serializers.ValidationError({"dropoff_location": "Pickup and dropoff must differ."})
        cycle_max = 70 if attrs.get("cycle_type", "70_8") == "70_8" else 60
        if attrs["current_cycle_hours"] > cycle_max:
            raise serializers.ValidationError({
                "current_cycle_hours": f"Cannot exceed {cycle_max} hours for selected cycle."
            })
        return attrs
