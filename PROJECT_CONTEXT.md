# 📦 Investment & Wallet Management System — Master Plan

## 🧱 Project Overview:
A full-stack Django-based platform for managing:
- User KYC
- INR/USDT Wallets
- Deposits & Withdrawals
- Investment ROI Plans
- Referral System
- Admin Panel
- Transaction Logs

---

## 📂 PART BREAKDOWN:

### 1. User & KYC:
- Register/Login via OTP
- Upload KYC (PAN, Aadhaar)
- Admin Approval

### 2. Wallets:
- INR & USDT Wallets
- Manual/Auto Deposit
- Live USDT Rate Sync
- Admin Wallet as pool

### 3. Withdrawals:
- Bank Linking
- USDT Withdrawals with 2FA
- Admin approval

### 4. Investment Plans (ROI):
- Plan creation, purchase, expiry
- Daily ROI crediting (via cron)
- Track history

### 5. Referral:
- Direct + Multi-level system
- Referral income credited to wallet
- Milestone bonuses

### 6. Transactions:
- History logs (deposit, ROI, referrals, etc.)
- CSV Export
- Search, filter

### 7. Admin Panel:
- Manage users, KYC, plans
- ROI distribution (manual/auto)
- Wallet overrides
- Announcements

---

## 🧰 Tech Stack:
- Backend: Django / Django REST Framework
- Frontend: React (Optional)
- Database: PostgreSQL
- Wallet APIs: BitGo / NowNodes
- Payments: Razorpay, Binance API
- Deployment: Docker, Gunicorn, Nginx, PostgreSQL

---

## ⚙️ Modules Structure:

Each folder in `app/` represents a feature-based Django app.

- `users/` → Auth, profile, KYC
- `wallet/` → USDT, INR balances
- `investment/` → ROI Plans
- `referral/` → Hierarchy + incomes
- `transactions/` → Logging, filters
- `admin_panel/` → Staff tools, analytics
- `support/` → Tickets, announcements
- `utils/` → Converters, API integrations
- `common/` → Shared models, constants, mixins

---

## ✅ Coding Standards:
- Snake_case for files, CamelCase for classes
- DRY & modular
- Test before merge
- All logic per feature must live inside its app
- No hardcoded config — use `.env`
- Document every model, view, and endpoint

---

## 🔐 Auth:
- Use JWT
- Protect all sensitive routes
- Store wallet addresses securely
- Rate limit sensitive endpoints (OTP, Withdrawals)