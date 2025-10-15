# Wallet Module - Part 2

## Overview
The Wallet module manages user balances, deposits, and transactions for both INR and USDT currencies in the Investment System.

## Features
- Multi-currency wallet support (INR & USDT)
- Secure balance management
- Deposit processing workflows
- Transaction logging and history
- Multi-chain wallet addresses

## Models
- **INRWallet**: Indian Rupee wallet with balance tracking
- **USDTWallet**: USDT wallet with balance tracking
- **WalletAddress**: Multi-chain wallet addresses
- **WalletTransaction**: Complete transaction history
- **DepositRequest**: Deposit approval workflow

## Wallet Operations
### INR Wallet
- Balance management with atomic operations
- Deposit approval workflow
- Transaction logging
- Balance validation

### USDT Wallet
- USDT balance tracking
- Multi-chain address generation
- Deposit confirmation
- Auto-sweep functionality

## API Endpoints
- `GET /api/v1/wallets/inr/` - Get INR wallet details
- `GET /api/v1/wallets/usdt/` - Get USDT wallet details
- `POST /api/v1/deposit-requests/` - Create deposit request
- `GET /api/v1/wallet-transactions/` - Get transaction history
- `GET /api/v1/wallet-addresses/{chain}/` - Get wallet address

## Admin Functions
- Approve/reject deposit requests
- Monitor wallet balances
- View transaction history
- Manage wallet addresses

## Security Features
- Atomic balance operations
- Concurrency control with `select_for_update`
- Transaction validation
- Balance integrity checks

## Testing
- **49 comprehensive tests** covering all functionality
- Unit tests for models and methods
- Integration tests for wallet operations
- API tests for all endpoints
- E2E tests for complete workflows

## Usage
Users can view balances, request deposits, and track transaction history. Admins can approve deposits and monitor system activity. 