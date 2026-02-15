# listings/serializers.py
from rest_framework import serializers
from .models import Listing, Booking, Review, Payment

# -------------------
# Listing Serializers
# -------------------
class ListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = '__all__'


# -------------------
# Booking Serializers
# -------------------
class BookingSerializer(serializers.ModelSerializer):
    listing = ListingSerializer(read_only=True)
    listing_title = serializers.ReadOnlyField(source='listing.title')
    
    class Meta:
        model = Booking
        fields = ['id', 'listing', 'listing_title', 'user', 'check_in_date', 
                 'check_out_date', 'guests', 'total_price', 'status', 
                 'created_at', 'updated_at']
        read_only_fields = ['user', 'total_price', 'status']


# -------------------
# Payment Serializers
# -------------------
class PaymentSerializer(serializers.ModelSerializer):
    booking_details = BookingSerializer(source='booking', read_only=True)
    
    class Meta:
        model = Payment
        fields = ['id', 'booking', 'booking_details', 'transaction_reference', 
                 'chapa_tx_ref', 'amount', 'currency', 'status', 'payment_method',
                 'first_name', 'last_name', 'email', 'phone_number', 
                 'created_at', 'updated_at', 'completed_at']
        read_only_fields = ['transaction_reference', 'chapa_tx_ref', 'chapa_response', 
                           'verification_response']


# -------------------
# Review Serializers
# -------------------
class ReviewSerializer(serializers.ModelSerializer):
    booking = BookingSerializer(read_only=True)

    class Meta:
        model = Review
        fields = '__all__'