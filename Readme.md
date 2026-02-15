# ALX Travel App

A Django-based backend project for a travel booking platform that allows users to manage listings, bookings, and reviews with integrated payment processing.

## 🚀 Features

### Core Features
- **Listings Management**: Create, read, update, and delete travel listings
- **Booking System**: Handle reservations for listings with date validation
- **Reviews & Ratings**: Allow users to leave feedback on their bookings
- **Database Seeder**: Populate sample data for testing and development

### Payment Integration (Chapa)
- **Payment Initiation**: Secure payment processing with Chapa gateway
- **Payment Verification**: Real-time payment status verification
- **Webhook Support**: Asynchronous payment updates via Chapa webhooks
- **Email Notifications**: Automatic payment confirmation emails via Celery
- **Payment Status Tracking**: Monitor transaction states (PENDING, COMPLETED, FAILED)

## 📋 Prerequisites

- Python 3.8+
- MySQL
- Redis (for Celery)
- Chapa Account (for payment processing)

## 🛠️ Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd alx_travel_app_0x01
