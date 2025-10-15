# Users Module - Part 1

## Overview
The Users module handles user registration, authentication, and profile management for the Investment System.

## Features
- User registration and login
- JWT authentication
- Password reset and email verification
- User roles and permissions
- Profile management

## Models
- **User**: Core user model with authentication fields
- **UserProfile**: Extended user profile information
- **OTP**: One-time password for verification
- **UserSession**: Track user login sessions

## API Endpoints
- `POST /api/v1/auth/register/` - User registration
- `POST /api/v1/auth/login/` - User login
- `POST /api/v1/auth/refresh/` - Refresh JWT token
- `POST /api/v1/auth/logout/` - User logout
- `POST /api/v1/auth/password-reset/` - Password reset request
- `POST /api/v1/auth/password-reset-confirm/` - Confirm password reset

## Testing
- Complete test suite with 100% coverage
- Unit tests for models and authentication
- API tests for all endpoints
- Integration tests for user workflows

## Usage
Users can register, login, and manage their profiles through the REST API. All endpoints require proper authentication except registration and login.
