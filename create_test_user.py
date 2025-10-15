#!/usr/bin/env python
"""
Script to create a test user for login testing
"""

import os
import django
import sys

# Add the project path
sys.path.append('/Users/Arvin Suvarna/Desktop/investment_part1,2/investment_system')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'investment_system.settings')
django.setup()

from app.users.models import User

def create_test_user():
    """Create a test user with known credentials"""
    email = "testuser@example.com"
    password = "testpass123"
    
    # Check if user already exists
    if User.objects.filter(email=email).exists():
        print(f"User {email} already exists")
        user = User.objects.get(email=email)
    else:
        # Create user
        user = User.objects.create_user(
            email=email,
            username=email,
            password=password,
            first_name="Test",
            last_name="User",
            phone_number="+1234567890"
        )
        print(f"Created user: {email}")
    
    # Also create/check admin user
    admin_email = "admin@example.com"
    admin_password = "admin123"
    
    if User.objects.filter(email=admin_email).exists():
        print(f"Admin user {admin_email} already exists")
        admin_user = User.objects.get(email=admin_email)
        # Update password to ensure it's correct
        admin_user.set_password(admin_password)
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()
        print(f"Updated admin user password")
    else:
        admin_user = User.objects.create_superuser(
            email=admin_email,
            username=admin_email,
            password=admin_password,
            first_name="Admin",
            last_name="User"
        )
        print(f"Created admin user: {admin_email}")
    
    print("\nTest credentials:")
    print(f"Regular user: {email} / {password}")
    print(f"Admin user: {admin_email} / {admin_password}")

if __name__ == "__main__":
    create_test_user()
