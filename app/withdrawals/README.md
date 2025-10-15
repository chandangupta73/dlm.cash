# Withdrawals Module - Part 3

## Overview
The Withdrawals module handles user withdrawal requests, fee calculations, and admin approval workflows for the Investment System.

## Features
- Withdrawal request creation and validation
- Automatic fee calculation
- Admin approval/rejection workflow
- Balance validation and deduction
- Transaction logging and history

## Models
- **WithdrawalRequest**: User withdrawal requests
- **WithdrawalFee**: Fee structure and calculations
- **WithdrawalTransaction**: Withdrawal transaction history

## Withdrawal Process
1. **Request Creation**: User submits withdrawal request
2. **Validation**: System validates amount and balance
3. **Fee Calculation**: Automatic fee deduction
4. **Admin Review**: Admin reviews and processes request
5. **Processing**: Balance deduction and transaction logging
6. **Completion**: Withdrawal marked as completed

## Business Rules
- **Minimum Withdrawal**: ₹100 for INR, $10 for USDT
- **Maximum Withdrawal**: Based on available balance
- **Fee Structure**: Percentage-based fees with minimum amounts
- **KYC Requirement**: KYC must be approved for withdrawals
- **Balance Validation**: Sufficient balance required

## API Endpoints
- `POST /api/v1/withdrawals/` - Create withdrawal request
- `GET /api/v1/withdrawals/` - Get user withdrawals
- `GET /api/v1/withdrawals/{id}/` - Get withdrawal details
- `POST /api/v1/withdrawals/{id}/cancel/` - Cancel withdrawal

## Admin Functions
- Review withdrawal requests
- Approve or reject withdrawals
- Add admin notes
- Process withdrawals
- Monitor withdrawal history

## Fee Calculation
- **INR Withdrawals**: 2% fee (minimum ₹10)
- **USDT Withdrawals**: 1% fee (minimum $1)
- **VIP Users**: Reduced fees based on tier
- **Bulk Withdrawals**: Volume-based discounts

## Security Features
- Balance validation before processing
- Admin approval required
- Transaction logging
- Audit trail maintenance
- KYC verification enforcement

## Testing
- Complete test suite covering all workflows
- Fee calculation tests
- Balance validation tests
- Admin workflow tests
- Edge case handling

## Usage
Users can request withdrawals through the API. Admins must approve all withdrawals. The system automatically calculates fees and validates balances.
