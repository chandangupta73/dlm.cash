# KYC Module - Part 1

## Overview
The KYC (Know Your Customer) module handles identity verification and compliance for users in the Investment System.

## Features
- Document upload and verification
- Admin approval/rejection workflow
- Offline KYC processing
- Video KYC support
- Verification status tracking

## Models
- **KYCDocument**: User identity documents
- **KYCVerificationLog**: Audit trail of verification actions
- **OfflineKYCRequest**: Manual KYC processing
- **VideoKYC**: Video verification sessions

## KYC Process
1. **Document Submission**: Users upload required documents
2. **Admin Review**: Admins review submitted documents
3. **Verification**: Documents are verified for authenticity
4. **Approval/Rejection**: Final decision with feedback
5. **Status Update**: User KYC status is updated

## API Endpoints
- `POST /api/v1/kyc/documents/` - Submit KYC documents
- `GET /api/v1/kyc/status/` - Check KYC status
- `POST /api/v1/kyc/offline-request/` - Request offline KYC
- `POST /api/v1/kyc/video-session/` - Schedule video KYC

## Admin Actions
- Review submitted documents
- Approve or reject KYC applications
- Add verification notes
- Track verification history

## Testing
- Complete test suite covering all workflows
- Document validation tests
- Admin workflow tests
- Edge case handling

## Compliance
- Follows regulatory requirements
- Maintains audit trails
- Secure document storage
- Privacy protection measures
