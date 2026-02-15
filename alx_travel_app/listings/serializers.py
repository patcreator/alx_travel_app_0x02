from rest_framework import serializers
from .models import Listing, Booking, Review

class ListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = '__all__'

class BookingSerializer(serializers.ModelSerializer):
    listing = ListingSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = '__all__'

class ReviewSerializer(serializers.ModelSerializer):
    booking = BookingSerializer(read_only=True)

    class Meta:
        model = Review
        fields = '__all__'
