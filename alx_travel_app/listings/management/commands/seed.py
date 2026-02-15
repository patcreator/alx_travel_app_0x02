from django.core.management.base import BaseCommand
from listings.models import Listing, Booking, Review
from django.contrib.auth import get_user_model
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed database with sample listings, bookings, and reviews'

    def handle(self, *args, **kwargs):
        # Optional: clear old data
        Listing.objects.all().delete()
        Booking.objects.all().delete()
        Review.objects.all().delete()

        users = User.objects.all()
        if not users:
            self.stdout.write(self.style.WARNING('No users found. Please create users first.'))
            return

        # Create listings
        listings = []
        for i in range(10):
            listing = Listing.objects.create(
                title=f"Sample Listing {i+1}",
                description="A beautiful place to stay.",
                location=f"City {i+1}",
                price_per_night=random.randint(50, 300),
                host=random.choice(users)
            )
            listings.append(listing)

        # Create bookings
        bookings = []
        for listing in listings:
            guest = random.choice(users)
            booking = Booking.objects.create(
                listing=listing,
                guest=guest,
                check_in="2026-01-10",
                check_out="2026-01-15",
                status=random.choice(['pending','confirmed','canceled'])
            )
            bookings.append(booking)

        # Create reviews
        for booking in bookings:
            Review.objects.create(
                booking=booking,
                rating=random.randint(1,5),
                comment="Great stay!"
            )

        self.stdout.write(self.style.SUCCESS('Successfully seeded listings, bookings, and reviews!'))
