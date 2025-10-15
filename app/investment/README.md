# Investment Module - Part 4

## Overview
The Investment module manages investment plans, ROI calculations, and breakdown requests for the Investment System.

## Features
- Investment plan creation and management
- Automatic ROI calculations and crediting
- User investment tracking
- Breakdown request workflow
- Admin approval system

## Models
- **InvestmentPlan**: ROI plans with different durations and rates
- **Investment**: User investments in plans
- **BreakdownRequest**: User withdrawal requests from investments
- **ROICredit**: Daily/weekly/monthly ROI payments

## Investment Plans
### Plan Types
- **Daily Plans**: ROI credited every day
- **Weekly Plans**: ROI credited every week
- **Monthly Plans**: ROI credited every month

### ROI Structure
- **Daily ROI**: 1.5% - 3.5% per day
- **Weekly ROI**: 10% - 25% per week
- **Monthly ROI**: 40% - 120% per month

## Investment Process
1. **Plan Selection**: User chooses investment plan
2. **Investment Creation**: System creates investment record
3. **ROI Scheduling**: Automatic ROI credit schedule
4. **ROI Crediting**: Daily/weekly/monthly payments
5. **Breakdown Requests**: Users can request withdrawals

## ROI System
### Automatic Crediting
- **Daily Plans**: ROI credited every 24 hours
- **Weekly Plans**: ROI credited every 7 days
- **Monthly Plans**: ROI credited every 30 days

### ROI Calculation
- **Formula**: Investment Amount × Daily Rate × Days
- **Compounding**: ROI added to wallet balance
- **Tracking**: Complete ROI history maintained

## Breakdown Requests
### Process
1. **User Request**: Submit breakdown request
2. **Admin Review**: Admin reviews request
3. **Approval/Rejection**: Admin decision with notes
4. **Processing**: Wallet crediting and status update

### Business Rules
- **Minimum Amount**: ₹100 for breakdown
- **Investment Status**: Must be active
- **ROI Accrued**: Based on investment duration

## API Endpoints
- `GET /api/v1/investment-plans/` - List available plans
- `POST /api/v1/investments/` - Create investment
- `GET /api/v1/investments/` - Get user investments
- `POST /api/v1/breakdown-requests/` - Create breakdown request
- `GET /api/v1/breakdown-requests/` - Get user requests

## Admin Functions
- Create and manage investment plans
- Monitor active investments
- Approve/reject breakdown requests
- View ROI crediting history
- Manage investment statuses

## Celery Tasks
- **Daily ROI Credit**: Processes daily ROI payments
- **Weekly ROI Credit**: Processes weekly ROI payments
- **Monthly ROI Credit**: Processes monthly ROI payments
- **Breakdown Processing**: Handles breakdown approvals

## Testing
- **18 comprehensive tests** covering all functionality
- ROI calculation tests
- Investment workflow tests
- Breakdown request tests
- Celery task tests
- Integration tests

## Usage
Users can invest in plans and earn daily/weekly/monthly ROI. The system automatically credits ROI and allows users to request breakdowns. Admins manage plans and approve breakdown requests.
