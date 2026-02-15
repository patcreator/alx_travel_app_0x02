# listings/views.py
import os
import json
import requests
import uuid
import hmac
import hashlib
from decimal import Decimal
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404, redirect
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.urls import reverse
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from celery import shared_task

from .models import Listing, Booking, Review, Payment
from .serializers import ListingSerializer, BookingSerializer, ReviewSerializer, PaymentSerializer

# -------------------
# API ViewSets
# -------------------
class ListingViewSet(viewsets.ModelViewSet):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer

# -------------------
# Chapa Payment Configuration
# -------------------
CHAPA_SECRET_KEY = os.environ.get('CHAPA_SECRET_KEY')
CHAPA_API_URL = "https://api.chapa.co/v1"
CHAPA_INITIATE_URL = f"{CHAPA_API_URL}/transaction/initialize"
CHAPA_VERIFY_URL = f"{CHAPA_API_URL}/transaction/verify"
CHAPA_WEBHOOK_SECRET = os.environ.get('CHAPA_WEBHOOK_SECRET', '')

def get_chapa_headers():
    """Headers for Chapa API requests"""
    return {
        'Authorization': f'Bearer {CHAPA_SECRET_KEY}',
        'Content-Type': 'application/json'
    }

# -------------------
# Celery Tasks
# -------------------
@shared_task
def send_payment_confirmation_email(booking_id, payment_id):
    """Send payment confirmation email using Celery"""
    try:
        booking = Booking.objects.get(id=booking_id)
        payment = Payment.objects.get(id=payment_id)
        
        subject = f'Payment Confirmed - Booking #{booking.id}'
        
        context = {
            'booking': booking,
            'payment': payment,
            'listing': booking.listing,
            'user': booking.user
        }
        
        html_message = render_to_string('emails/payment_confirmation.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject,
            plain_message,
            'noreply@alxtravel.com',
            [booking.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return f"Email sent to {booking.user.email}"
    except Exception as e:
        return f"Failed to send email: {str(e)}"

# -------------------
# Payment Views
# -------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payment(request):
    """
    Initiate payment with Chapa for a booking
    """
    booking_id = request.data.get('booking_id')
    
    if not booking_id:
        return Response({'error': 'Booking ID is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Check if payment already exists
    if hasattr(booking, 'payment'):
        payment = booking.payment
        if payment.status == 'COMPLETED':
            return Response({'error': 'Booking already paid for'}, status=status.HTTP_400_BAD_REQUEST)
        elif payment.status == 'PENDING':
            # Return existing payment link
            return Response({
                'message': 'Payment already initiated',
                'payment': PaymentSerializer(payment).data,
                'checkout_url': f"https://checkout.chapa.co/checkout/payment/{payment.chapa_tx_ref}"
            }, status=status.HTTP_200_OK)
    else:
        # Create new payment record
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.total_price,
            first_name=request.user.first_name or request.user.username,
            last_name=request.user.last_name or '',
            email=request.user.email,
            phone_number=request.user.profile.phone_number if hasattr(request.user, 'profile') else '',
        )
    
    # Prepare data for Chapa
    tx_ref = str(uuid.uuid4())
    payment.chapa_tx_ref = tx_ref
    payment.save()
    
    callback_url = request.build_absolute_uri(reverse('verify-payment', args=[payment.id]))
    
    chapa_data = {
        "amount": str(payment.amount),
        "currency": payment.currency,
        "email": payment.email,
        "first_name": payment.first_name,
        "last_name": payment.last_name,
        "tx_ref": tx_ref,
        "callback_url": callback_url,
        "return_url": request.build_absolute_uri(reverse('payment-success')),
        "customization": {
            "title": f"Booking #{booking.id} - {booking.listing.title}",
            "description": f"Payment for booking from {booking.check_in_date} to {booking.check_out_date}"
        }
    }
    
    if payment.phone_number:
        chapa_data["phone_number"] = payment.phone_number
    
    try:
        # Make request to Chapa API
        response = requests.post(
            CHAPA_INITIATE_URL,
            json=chapa_data,
            headers=get_chapa_headers(),
            timeout=30
        )
        
        if response.status_code == 200:
            chapa_response = response.json()
            
            # Store the response
            payment.chapa_response = chapa_response
            payment.save()
            
            if chapa_response.get('status') == 'success':
                checkout_url = chapa_response['data']['checkout_url']
                
                return Response({
                    'message': 'Payment initiated successfully',
                    'payment': PaymentSerializer(payment).data,
                    'checkout_url': checkout_url
                }, status=status.HTTP_200_OK)
            else:
                payment.mark_as_failed()
                return Response({'error': chapa_response.get('message', 'Payment initiation failed')}, 
                              status=status.HTTP_400_BAD_REQUEST)
        else:
            payment.mark_as_failed()
            return Response({'error': 'Failed to connect to payment gateway'}, 
                          status=status.HTTP_503_SERVICE_UNAVAILABLE)
                          
    except requests.exceptions.RequestException as e:
        payment.mark_as_failed()
        return Response({'error': f'Payment service error: {str(e)}'}, 
                      status=status.HTTP_503_SERVICE_UNAVAILABLE)

@api_view(['GET'])
def verify_payment(request, payment_id):
    """
    Verify payment status with Chapa
    """
    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if payment.status == 'COMPLETED':
        return Response({
            'message': 'Payment already verified and completed',
            'payment': PaymentSerializer(payment).data
        }, status=status.HTTP_200_OK)
    
    try:
        # Verify with Chapa API
        verify_url = f"{CHAPA_VERIFY_URL}/{payment.chapa_tx_ref}"
        response = requests.get(verify_url, headers=get_chapa_headers(), timeout=30)
        
        if response.status_code == 200:
            verification_data = response.json()
            
            # Store verification response
            payment.verification_response = verification_data
            payment.save()
            
            if verification_data.get('status') == 'success':
                chapa_data = verification_data.get('data', {})
                
                # Check if payment was successful
                if chapa_data.get('status') == 'success':
                    payment.mark_as_completed()
                    
                    # Send confirmation email using Celery
                    send_payment_confirmation_email.delay(payment.booking.id, payment.id)
                    
                    return Response({
                        'message': 'Payment verified successfully',
                        'payment': PaymentSerializer(payment).data
                    }, status=status.HTTP_200_OK)
                else:
                    payment.mark_as_failed()
                    return Response({
                        'error': 'Payment verification failed',
                        'details': chapa_data
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                payment.mark_as_failed()
                return Response({
                    'error': verification_data.get('message', 'Verification failed')
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'error': 'Failed to verify payment with Chapa'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
    except requests.exceptions.RequestException as e:
        return Response({
            'error': f'Verification service error: {str(e)}'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_success(request):
    """
    Handle successful payment return
    """
    return Response({
        'message': 'Payment completed successfully',
        'redirect_url': reverse('my-bookings')
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_status(request, booking_id):
    """
    Get payment status for a booking
    """
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if hasattr(booking, 'payment'):
        payment = booking.payment
        return Response({
            'payment': PaymentSerializer(payment).data
        }, status=status.HTTP_200_OK)
    else:
        return Response({
            'message': 'No payment found for this booking'
        }, status=status.HTTP_404_NOT_FOUND)

@csrf_exempt
@require_http_methods(["POST"])
def chapa_webhook(request):
    """
    Webhook endpoint for Chapa to send payment updates
    """
    # Verify webhook signature
    signature = request.headers.get('x-chapa-signature')
    payload = request.body
    
    if not signature:
        return JsonResponse({'error': 'No signature provided'}, status=400)
    
    # Calculate expected signature
    expected_signature = hmac.new(
        CHAPA_WEBHOOK_SECRET.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        return JsonResponse({'error': 'Invalid signature'}, status=401)
    
    try:
        data = json.loads(payload)
        
        # Extract transaction reference
        tx_ref = data.get('tx_ref')
        if not tx_ref:
            return JsonResponse({'error': 'No transaction reference'}, status=400)
        
        try:
            payment = Payment.objects.get(chapa_tx_ref=tx_ref)
        except Payment.DoesNotExist:
            return JsonResponse({'error': 'Payment not found'}, status=404)
        
        # Update payment based on webhook data
        event = data.get('event')
        
        if event == 'charge.success':
            payment.mark_as_completed()
            # Send confirmation email
            send_payment_confirmation_email.delay(payment.booking.id, payment.id)
        elif event == 'charge.failed':
            payment.mark_as_failed()
        
        return JsonResponse({'status': 'success'}, status=200)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_booking_with_payment(request):
    """
    Create a booking and initiate payment in one step
    """
    serializer = BookingSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        booking = serializer.save(user=request.user)
        
        # Initiate payment
        payment_data = {
            'booking_id': booking.id
        }
        
        # Create a mock request object for initiate_payment
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        payment_request = factory.post('/initiate-payment/', payment_data, format='json')
        payment_request.user = request.user
        
        # Call initiate_payment
        response = initiate_payment(payment_request)
        
        if response.status_code == 200:
            return Response({
                'booking': BookingSerializer(booking).data,
                'payment': response.data
            }, status=status.HTTP_201_CREATED)
        else:
            # Payment initiation failed, but booking was created
            return Response({
                'booking': BookingSerializer(booking).data,
                'warning': 'Booking created but payment initiation failed',
                'error': response.data
            }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)