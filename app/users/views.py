from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, OTP, BankDetails, USDTDetails
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, 
    UserProfileSerializer, BankDetailsSerializer, USDTDetailsSerializer
)
from django.utils import timezone
from datetime import timedelta
import random
import string


@api_view(['POST'])
@permission_classes([])  # Allow unauthenticated access
def register_user(request):
    """User registration endpoint."""
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            'user': UserProfileSerializer(user).data,
            'message': 'User registered successfully'
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([])  # Allow unauthenticated access
def login_user(request):
    """User login endpoint."""
    serializer = UserLoginSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        user = authenticate(request, username=email, password=password)
        if user:
            from rest_framework_simplejwt.tokens import RefreshToken
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh)
                },
                'user': UserProfileSerializer(user).data
            })
        else:
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Get or update user profile."""
    if request.method == 'GET':
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)
    
    elif request.method == 'PATCH':
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BankDetailsViewSet(viewsets.ModelViewSet):
    """ViewSet for managing bank details."""
    
    serializer_class = BankDetailsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return bank details for the current user."""
        return BankDetails.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Create bank details for the current user."""
        serializer.save(user=self.request.user)
    
    def perform_update(self, serializer):
        """Update bank details for the current user."""
        serializer.save(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Create or update bank details."""
        # Check if bank details already exist
        try:
            bank_details = BankDetails.objects.get(user=request.user)
            # Update existing
            serializer = self.get_serializer(bank_details, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)
        except BankDetails.DoesNotExist:
            # Create new
            return super().create(request, *args, **kwargs) 


class USDTDetailsViewSet(viewsets.ModelViewSet):
    """ViewSet for managing USDT details."""
    
    serializer_class = USDTDetailsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return USDT details for the current user."""
        return USDTDetails.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Create USDT details for the current user."""
        serializer.save(user=self.request.user)
    
    def perform_update(self, serializer):
        """Update USDT details for the current user."""
        serializer.save(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Create or update USDT details."""
        # Check if USDT details already exist
        try:
            usdt_details = USDTDetails.objects.get(user=request.user)
            # Update existing
            serializer = self.get_serializer(usdt_details, data=request.data, partial=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            self.perform_update(serializer)
            return Response(serializer.data)
        except USDTDetails.DoesNotExist:
            # Create new
            serializer = self.get_serializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED) 