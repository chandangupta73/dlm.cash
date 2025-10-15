import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from unittest.mock import patch
from datetime import datetime, timedelta
from freezegun import freeze_time

from app.investment.models import InvestmentPlan, Investment
from app.wallet.models import INRWallet, USDTWallet, WalletTransaction
from app.admin_panel.models import AdminActionLog
from app.admin_panel.services import AdminInvestmentService
from app.admin_panel.permissions import log_admin_action

User = get_user_model()


class AdminInvestmentServiceTest(TestCase):
    """Test investment management service layer"""
    
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        self.staff_user = User.objects.create_user(
            username='staff',
            email='staff@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=False
        )
        
        self.regular_user = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123'
        )
        
        self.inr_wallet = INRWallet.objects.create(
            user=self.regular_user,
            balance=Decimal('10000.00')
        )
        
        self.usdt_wallet = USDTWallet.objects.create(
            user=self.regular_user,
            balance=Decimal('1000.00')
        )
        
        self.investment_plan = InvestmentPlan.objects.create(
            name='Test Plan',
            roi_rate=Decimal('12.00'),
            duration_days=30,
            min_amount=Decimal('1000.00'),
            max_amount=Decimal('100000.00'),
            is_active=True
        )
        
        self.investment = Investment.objects.create(
            user=self.regular_user,
            plan=self.investment_plan,
            amount=Decimal('5000.00'),
            currency='INR',
            status='ACTIVE',
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=30)
        )
        
        self.investment_service = AdminInvestmentService()
    
    def test_get_investments_with_filters(self):
        """Test retrieving investments with various filters"""
        # Test no filters
        investments = self.investment_service.get_investments()
        self.assertEqual(len(investments), 1)
        self.assertEqual(investments[0].id, self.investment.id)
        
        # Test status filter
        investments = self.investment_service.get_investments(status='ACTIVE')
        self.assertEqual(len(investments), 1)
        
        investments = self.investment_service.get_investments(status='COMPLETED')
        self.assertEqual(len(investments), 0)
        
        # Test user filter
        investments = self.investment_service.get_investments(user_id=self.regular_user.id)
        self.assertEqual(len(investments), 1)
        
        investments = self.investment_service.get_investments(user_id=99999)
        self.assertEqual(len(investments), 0)
        
        # Test plan filter
        investments = self.investment_service.get_investments(plan_id=self.investment_plan.id)
        self.assertEqual(len(investments), 1)
    
    def test_get_investment_plans(self):
        """Test retrieving investment plans"""
        plans = self.investment_service.get_investment_plans()
        
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].id, self.investment_plan.id)
        self.assertEqual(plans[0].name, 'Test Plan')
    
    def test_create_investment_plan(self):
        """Test creating a new investment plan"""
        plan_data = {
            'name': 'Premium Plan',
            'roi_rate': Decimal('15.00'),
            'duration_days': 60,
            'min_amount': Decimal('5000.00'),
            'max_amount': Decimal('500000.00'),
            'is_active': True
        }
        
        result = self.investment_service.create_investment_plan(
            plan_data=plan_data,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check plan created
        new_plan = InvestmentPlan.objects.get(name='Premium Plan')
        self.assertEqual(new_plan.roi_rate, Decimal('15.00'))
        self.assertEqual(new_plan.duration_days, 60)
        self.assertTrue(new_plan.is_active)
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='INVESTMENT_PLAN_CREATION',
            target_model='InvestmentPlan'
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('Premium Plan', action_log.action_description)
    
    def test_update_investment_plan(self):
        """Test updating an investment plan"""
        update_data = {
            'roi_rate': Decimal('18.00'),
            'duration_days': 45,
            'is_active': False
        }
        
        result = self.investment_service.update_investment_plan(
            plan_id=self.investment_plan.id,
            update_data=update_data,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check plan updated
        self.investment_plan.refresh_from_db()
        self.assertEqual(self.investment_plan.roi_rate, Decimal('18.00'))
        self.assertEqual(self.investment_plan.duration_days, 45)
        self.assertFalse(self.investment_plan.is_active)
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='INVESTMENT_PLAN_UPDATE',
            target_model='InvestmentPlan'
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('Test Plan', action_log.action_description)
    
    def test_delete_investment_plan(self):
        """Test deleting an investment plan"""
        result = self.investment_service.delete_investment_plan(
            plan_id=self.investment_plan.id,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check plan deleted
        self.assertFalse(InvestmentPlan.objects.filter(id=self.investment_plan.id).exists())
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='INVESTMENT_PLAN_DELETION',
            target_model='InvestmentPlan'
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('Test Plan', action_log.action_description)
    
    def test_cancel_investment(self):
        """Test cancelling an investment"""
        result = self.investment_service.cancel_investment(
            investment_id=self.investment.id,
            admin_user=self.admin_user,
            reason='Admin cancellation'
        )
        
        self.assertTrue(result['success'])
        
        # Check investment status updated
        self.investment.refresh_from_db()
        self.assertEqual(self.investment.status, 'CANCELLED')
        self.assertEqual(self.investment.cancellation_reason, 'Admin cancellation')
        
        # Check wallet balance refunded
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('15000.00'))  # 10000 + 5000
        
        # Check refund transaction log created
        transaction = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='investment_refund',
            amount=Decimal('5000.00')
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.description, 'Investment cancelled - refund by admin')
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='INVESTMENT_CANCELLATION',
            target_user=self.regular_user
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('Admin cancellation', action_log.action_description)
    
    def test_trigger_roi_distribution(self):
        """Test manually triggering ROI distribution"""
        with freeze_time('2024-01-15'):
            result = self.investment_service.trigger_roi_distribution(
                admin_user=self.admin_user,
                notes='Manual ROI trigger'
            )
            
            self.assertTrue(result['success'])
            
            # Check ROI transactions created
            roi_transactions = WalletTransaction.objects.filter(
                transaction_type='roi_credit'
            )
            self.assertGreater(roi_transactions.count(), 0)
            
            # Check admin action logged
            action_log = AdminActionLog.objects.filter(
                admin_user=self.admin_user,
                action_type='ROI_TRIGGER',
                action_description__contains='Manual ROI trigger'
            ).first()
            self.assertIsNotNone(action_log)
    
    def test_create_investment_plan_validation_error(self):
        """Test creating investment plan with validation error"""
        invalid_plan_data = {
            'name': '',  # Empty name
            'roi_rate': Decimal('15.00'),
            'duration_days': 60,
            'min_amount': Decimal('5000.00'),
            'max_amount': Decimal('500000.00')
        }
        
        result = self.investment_service.create_investment_plan(
            plan_data=invalid_plan_data,
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('name', result['error'])
    
    def test_update_investment_plan_validation_error(self):
        """Test updating investment plan with validation error"""
        invalid_update_data = {
            'roi_rate': Decimal('-5.00'),  # Negative ROI
            'duration_days': 0  # Zero duration
        }
        
        result = self.investment_service.update_investment_plan(
            plan_id=self.investment_plan.id,
            update_data=invalid_update_data,
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('roi_rate', result['error'])
    
    def test_cancel_nonexistent_investment(self):
        """Test cancelling non-existent investment"""
        result = self.investment_service.cancel_investment(
            investment_id=99999,
            admin_user=self.admin_user,
            reason='Test'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
    
    def test_cancel_already_cancelled_investment(self):
        """Test cancelling already cancelled investment"""
        self.investment.status = 'CANCELLED'
        self.investment.save()
        
        result = self.investment_service.cancel_investment(
            investment_id=self.investment.id,
            admin_user=self.admin_user,
            reason='Test'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('already cancelled', result['error'])
    
    def test_cancel_completed_investment(self):
        """Test cancelling completed investment"""
        self.investment.status = 'COMPLETED'
        self.investment.save()
        
        result = self.investment_service.cancel_investment(
            investment_id=self.investment.id,
            admin_user=self.admin_user,
            reason='Test'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('cannot cancel', result['error'])
    
    def test_update_nonexistent_investment_plan(self):
        """Test updating non-existent investment plan"""
        result = self.investment_service.update_investment_plan(
            plan_id=99999,
            update_data={'roi_rate': Decimal('20.00')},
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
    
    def test_delete_nonexistent_investment_plan(self):
        """Test deleting non-existent investment plan"""
        result = self.investment_service.delete_investment_plan(
            plan_id=99999,
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
    
    def test_delete_investment_plan_with_active_investments(self):
        """Test deleting investment plan with active investments"""
        result = self.investment_service.delete_investment_plan(
            plan_id=self.investment_plan.id,
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('active investments', result['error'])
    
    def test_staff_user_cannot_delete_investment_plan(self):
        """Test staff user cannot delete investment plan"""
        result = self.investment_service.delete_investment_plan(
            plan_id=self.investment_plan.id,
            admin_user=self.staff_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('permission denied', result['error'])
    
    def test_investment_plan_creation_with_notification(self):
        """Test investment plan creation triggers notification"""
        with patch('app.admin_panel.services.send_investment_plan_creation_notification') as mock_notify:
            plan_data = {
                'name': 'Notification Test Plan',
                'roi_rate': Decimal('20.00'),
                'duration_days': 90,
                'min_amount': Decimal('10000.00'),
                'max_amount': Decimal('1000000.00'),
                'is_active': True
            }
            
            result = self.investment_service.create_investment_plan(
                plan_data=plan_data,
                admin_user=self.admin_user
            )
            
            self.assertTrue(result['success'])
            mock_notify.assert_called_once()


class AdminInvestmentAPITest(TestCase):
    """Test investment management API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        self.staff_user = User.objects.create_user(
            username='staff',
            email='staff@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=False
        )
        
        self.regular_user = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123'
        )
        
        self.inr_wallet = INRWallet.objects.create(
            user=self.regular_user,
            balance=Decimal('10000.00')
        )
        
        self.investment_plan = InvestmentPlan.objects.create(
            name='Test Plan',
            roi_rate=Decimal('12.00'),
            duration_days=30,
            min_amount=Decimal('1000.00'),
            max_amount=Decimal('100000.00'),
            is_active=True
        )
        
        self.investment = Investment.objects.create(
            user=self.regular_user,
            plan=self.investment_plan,
            amount=Decimal('5000.00'),
            currency='INR',
            status='ACTIVE',
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=30)
        )
        
        self.client.force_authenticate(user=self.admin_user)
    
    def test_list_investments(self):
        """Test listing investments"""
        url = reverse('admin-investment-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.investment.id)
    
    def test_list_investments_with_filters(self):
        """Test listing investments with filters"""
        url = reverse('admin-investment-list')
        response = self.client.get(url, {
            'status': 'ACTIVE',
            'user_id': self.regular_user.id
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_retrieve_investment(self):
        """Test retrieving a specific investment"""
        url = reverse('admin-investment-detail', kwargs={'pk': self.investment.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.investment.id)
        self.assertEqual(response.data['status'], 'ACTIVE')
    
    def test_list_investment_plans(self):
        """Test listing investment plans"""
        url = reverse('admin-investment-plans')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.investment_plan.id)
    
    def test_create_investment_plan_api(self):
        """Test creating investment plan via API"""
        url = reverse('admin-investment-plans')
        data = {
            'name': 'API Test Plan',
            'roi_rate': '15.00',
            'duration_days': 60,
            'min_amount': '5000.00',
            'max_amount': '500000.00',
            'is_active': True
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'API Test Plan')
        self.assertEqual(response.data['roi_rate'], '15.00')
    
    def test_update_investment_plan_api(self):
        """Test updating investment plan via API"""
        url = reverse('admin-investment-plan-detail', kwargs={'pk': self.investment_plan.id})
        data = {
            'roi_rate': '18.00',
            'duration_days': 45
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['roi_rate'], '18.00')
        self.assertEqual(response.data['duration_days'], 45)
    
    def test_delete_investment_plan_api(self):
        """Test deleting investment plan via API"""
        # First deactivate the plan
        self.investment_plan.is_active = False
        self.investment_plan.save()
        
        url = reverse('admin-investment-plan-detail', kwargs={'pk': self.investment_plan.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_cancel_investment_api(self):
        """Test cancelling investment via API"""
        url = reverse('admin-investment-cancel', kwargs={'pk': self.investment.id})
        data = {'reason': 'API cancellation test'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check investment status updated
        self.investment.refresh_from_db()
        self.assertEqual(self.investment.status, 'CANCELLED')
    
    def test_trigger_roi_api(self):
        """Test triggering ROI via API"""
        url = reverse('admin-investment-trigger-roi')
        data = {'notes': 'API ROI trigger test'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
    
    def test_create_investment_plan_validation_error(self):
        """Test creating investment plan with validation error"""
        url = reverse('admin-investment-plans')
        data = {
            'name': '',  # Empty name
            'roi_rate': '15.00',
            'duration_days': 60
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)
    
    def test_update_investment_plan_validation_error(self):
        """Test updating investment plan with validation error"""
        url = reverse('admin-investment-plan-detail', kwargs={'pk': self.investment_plan.id})
        data = {
            'roi_rate': '-5.00'  # Negative ROI
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('roi_rate', response.data)
    
    def test_cancel_investment_validation_error(self):
        """Test cancelling investment with validation error"""
        url = reverse('admin-investment-cancel', kwargs={'pk': self.investment.id})
        data = {'reason': ''}  # Empty reason
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('reason', response.data)
    
    def test_investment_api_permission_denied_non_admin(self):
        """Test investment API access denied for non-admin users"""
        self.client.force_authenticate(user=self.regular_user)
        
        url = reverse('admin-investment-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_investment_api_permission_denied_staff(self):
        """Test investment API access denied for staff users without permission"""
        self.client.force_authenticate(user=self.staff_user)
        
        url = reverse('admin-investment-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_investment_api_unauthorized(self):
        """Test investment API access denied for unauthenticated users"""
        self.client.force_authenticate(user=None)
        
        url = reverse('admin-investment-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_cancel_nonexistent_investment(self):
        """Test cancelling non-existent investment"""
        url = reverse('admin-investment-cancel', kwargs={'pk': 99999})
        data = {'reason': 'Test'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_cancel_already_cancelled_investment(self):
        """Test cancelling already cancelled investment"""
        self.investment.status = 'CANCELLED'
        self.investment.save()
        
        url = reverse('admin-investment-cancel', kwargs={'pk': self.investment.id})
        data = {'reason': 'Test'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already cancelled', response.data['error'])
    
    def test_delete_investment_plan_with_active_investments(self):
        """Test deleting investment plan with active investments"""
        url = reverse('admin-investment-plan-detail', kwargs={'pk': self.investment_plan.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('active investments', response.data['error'])


class AdminInvestmentIntegrationTest(TestCase):
    """Test investment management integration with other modules"""
    
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        self.regular_user = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123'
        )
        
        self.inr_wallet = INRWallet.objects.create(
            user=self.regular_user,
            balance=Decimal('10000.00')
        )
        
        self.investment_plan = InvestmentPlan.objects.create(
            name='Integration Test Plan',
            roi_rate=Decimal('12.00'),
            duration_days=30,
            min_amount=Decimal('1000.00'),
            max_amount=Decimal('100000.00'),
            is_active=True
        )
        
        self.investment = Investment.objects.create(
            user=self.regular_user,
            plan=self.investment_plan,
            amount=Decimal('5000.00'),
            currency='INR',
            status='ACTIVE',
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=30)
        )
        
        self.investment_service = AdminInvestmentService()
    
    def test_investment_cancellation_updates_wallet_balance(self):
        """Test that investment cancellation correctly updates wallet balance"""
        initial_balance = self.inr_wallet.balance
        
        result = self.investment_service.cancel_investment(
            investment_id=self.investment.id,
            admin_user=self.admin_user,
            reason='Integration test cancellation'
        )
        
        self.assertTrue(result['success'])
        
        # Check wallet balance updated
        self.inr_wallet.refresh_from_db()
        expected_balance = initial_balance + self.investment.amount
        self.assertEqual(self.inr_wallet.balance, expected_balance)
    
    def test_investment_cancellation_creates_transaction_log(self):
        """Test that investment cancellation creates proper transaction log"""
        result = self.investment_service.cancel_investment(
            investment_id=self.investment.id,
            admin_user=self.admin_user,
            reason='Transaction log test'
        )
        
        self.assertTrue(result['success'])
        
        # Check transaction log exists
        transaction = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='investment_refund',
            amount=self.investment.amount
        ).first()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.admin_user, self.admin_user)
    
    def test_investment_cancellation_logs_admin_action(self):
        """Test that investment cancellation creates admin action log"""
        result = self.investment_service.cancel_investment(
            investment_id=self.investment.id,
            admin_user=self.admin_user,
            reason='Admin action log test'
        )
        
        self.assertTrue(result['success'])
        
        # Check admin action log exists
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='INVESTMENT_CANCELLATION',
            target_user=self.regular_user
        ).first()
        
        self.assertIsNotNone(action_log)
        self.assertEqual(action_log.target_model, 'Investment')
        self.assertEqual(action_log.target_id, str(self.investment.id))
    
    def test_investment_plan_creation_logs_admin_action(self):
        """Test that investment plan creation creates admin action log"""
        plan_data = {
            'name': 'Integration Test Plan 2',
            'roi_rate': Decimal('20.00'),
            'duration_days': 90,
            'min_amount': Decimal('10000.00'),
            'max_amount': Decimal('1000000.00'),
            'is_active': True
        }
        
        result = self.investment_service.create_investment_plan(
            plan_data=plan_data,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check admin action log exists
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='INVESTMENT_PLAN_CREATION',
            target_model='InvestmentPlan'
        ).first()
        
        self.assertIsNotNone(action_log)
        self.assertIn('Integration Test Plan 2', action_log.action_description)
    
    def test_investment_plan_update_logs_admin_action(self):
        """Test that investment plan update creates admin action log"""
        update_data = {
            'roi_rate': Decimal('25.00'),
            'duration_days': 120
        }
        
        result = self.investment_service.update_investment_plan(
            plan_id=self.investment_plan.id,
            update_data=update_data,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check admin action log exists
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='INVESTMENT_PLAN_UPDATE',
            target_model='InvestmentPlan'
        ).first()
        
        self.assertIsNotNone(action_log)
        self.assertIn('Integration Test Plan', action_log.action_description)
    
    def test_roi_trigger_logs_admin_action(self):
        """Test that ROI trigger creates admin action log"""
        with freeze_time('2024-01-15'):
            result = self.investment_service.trigger_roi_distribution(
                admin_user=self.admin_user,
                notes='Integration test ROI trigger'
            )
            
            self.assertTrue(result['success'])
            
            # Check admin action log exists
            action_log = AdminActionLog.objects.filter(
                admin_user=self.admin_user,
                action_type='ROI_TRIGGER',
                action_description__contains='Integration test ROI trigger'
            ).first()
            
            self.assertIsNotNone(action_log)
    
    def test_multiple_investment_operations_maintain_consistency(self):
        """Test that multiple investment operations maintain data consistency"""
        # Create another investment
        investment2 = Investment.objects.create(
            user=self.regular_user,
            plan=self.investment_plan,
            amount=Decimal('3000.00'),
            currency='INR',
            status='ACTIVE',
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=30)
        )
        
        initial_balance = self.inr_wallet.balance
        
        # Cancel first investment
        result1 = self.investment_service.cancel_investment(
            investment_id=self.investment.id,
            admin_user=self.admin_user,
            reason='First cancellation'
        )
        self.assertTrue(result1['success'])
        
        # Cancel second investment
        result2 = self.investment_service.cancel_investment(
            investment_id=investment2.id,
            admin_user=self.admin_user,
            reason='Second cancellation'
        )
        self.assertTrue(result2['success'])
        
        # Check final balance
        self.inr_wallet.refresh_from_db()
        expected_balance = initial_balance + self.investment.amount + investment2.amount
        self.assertEqual(self.inr_wallet.balance, expected_balance)
        
        # Check transaction count
        transaction_count = WalletTransaction.objects.filter(
            user=self.regular_user,
            transaction_type='investment_refund'
        ).count()
        self.assertEqual(transaction_count, 2)
    
    def test_investment_plan_changes_affect_new_investments_only(self):
        """Test that investment plan changes only affect new investments"""
        # Update plan ROI
        update_data = {'roi_rate': Decimal('25.00')}
        result = self.investment_service.update_investment_plan(
            plan_id=self.investment_plan.id,
            update_data=update_data,
            admin_user=self.admin_user
        )
        self.assertTrue(result['success'])
        
        # Check existing investment unchanged
        self.investment.refresh_from_db()
        self.assertEqual(self.investment.plan.roi_rate, Decimal('25.00'))
        
        # Create new investment with updated plan
        new_investment = Investment.objects.create(
            user=self.regular_user,
            plan=self.investment_plan,
            amount=Decimal('2000.00'),
            currency='INR',
            status='ACTIVE',
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=30)
        )
        
        # Check new investment uses updated plan
        self.assertEqual(new_investment.plan.roi_rate, Decimal('25.00'))
