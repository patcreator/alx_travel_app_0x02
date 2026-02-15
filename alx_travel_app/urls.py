# listings/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

# Create a router for ViewSets
router = DefaultRouter()
router.register(r'listings', views.ListingViewSet)
router.register(r'bookings', views.BookingViewSet)
router.register(r'reviews', views.ReviewViewSet)

# Custom URL patterns for payment views
payment_urlpatterns = [
    # Payment initiation and verification
    path('initiate-payment/', 
         views.initiate_payment, 
         name='initiate-payment'),
    
    path('verify-payment/<int:payment_id>/', 
         views.verify_payment, 
         name='verify-payment'),
    
    path('payment-success/', 
         views.payment_success, 
         name='payment-success'),
    
    path('payment-status/<int:booking_id>/', 
         views.payment_status, 
         name='payment-status'),
    
    # Combined booking and payment
    path('create-booking-with-payment/', 
         views.create_booking_with_payment, 
         name='create-booking-with-payment'),
    
    # Webhook (no authentication required)
    path('chapa-webhook/', 
         views.chapa_webhook, 
         name='chapa-webhook'),
]

# Combine all URL patterns
urlpatterns = [
    # Include router URLs
    *router.urls,
    
    # Include payment URLs
    *payment_urlpatterns,
]