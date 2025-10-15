from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock
from freezegun import freeze_time

from app.referral.models import (
    ReferralConfig, UserReferralProfile, Referral, 
    ReferralEarning, ReferralMilestone
)
from app.referral.services import ReferralService
from app.referral.tests.factories import (
    UserFactory, ReferralConfigFactory, UserReferralProfileFactory,
    ReferralFactory, ReferralMilestoneFactory, ReferralEarningFactory
)

User = get_user_model()


class ReferralServiceTestCase(TestCase):
    """Test cases for ReferralService class."""

    def setUp(self):
        """Set up test data."""
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.user3 = UserFactory()
        self.user4 = UserFactory()
        
        self.config = ReferralConfigFactory(
            max_levels=3,
            level_1_percentage=Decimal('5.0'),
            level_2_percentage=Decimal('3.0'),
            level_3_percentage=Decimal('1.0'),
            is_active=True
        )

    def test_create_referral_chain_with_valid_referrer(self):
        """Test creating referral chain with valid referrer code."""
        # Create referrer profile
        referrer_profile = UserReferralProfileFactory(user=self.user1)
        
        # Create referral chain
        result = ReferralService.create_referral_chain(
            self.user2, 
            referrer_profile.referral_code
        )
        
        self.assertTrue(result)
        
        # Check UserReferralProfile was created
        profile = UserReferralProfile.objects.get(user=self.user2)
        self.assertEqual(profile.referred_by, self.user1)
        self.assertIsNotNone(profile.referral_code)
        
        # Check Referral objects were created
        referrals = Referral.objects.filter(user=self.user2)
        self.assertEqual(referrals.count(), 3)  # 3 levels
        
        # Check level 1 referral
        level1 = referrals.get(level=1)
        self.assertEqual(level1.referrer, self.user1)
        self.assertEqual(level1.referred_user, self.user2)
        
        # Check level 2 referral (user1's referrer if exists)
        level2 = referrals.get(level=2)
        if level2.referrer:
            self.assertNotEqual(level2.referrer, self.user1)

    def test_create_referral_chain_without_referrer(self):
        """Test creating referral chain without referrer code."""
        result = ReferralService.create_referral_chain(self.user2)
        
        self.assertTrue(result)
        
        # Check UserReferralProfile was created
        profile = UserReferralProfile.objects.get(user=self.user2)
        self.assertIsNone(profile.referred_by)
        self.assertIsNotNone(profile.referral_code)
        
        # Check no Referral objects were created
        referrals = Referral.objects.filter(user=self.user2)
        self.assertEqual(referrals.count(), 0)

    def test_create_referral_chain_with_invalid_referrer(self):
        """Test creating referral chain with invalid referrer code."""
        result = ReferralService.create_referral_chain(self.user2, "INVALID_CODE")
        
        self.assertTrue(result)
        
        # Check UserReferralProfile was created
        profile = UserReferralProfile.objects.get(user=self.user2)
        self.assertIsNone(profile.referred_by)
        self.assertIsNotNone(profile.referral_code)
        
        # Check no Referral objects were created
        referrals = Referral.objects.filter(user=self.user2)
        self.assertEqual(referrals.count(), 0)

    def test_create_referral_chain_multi_level(self):
        """Test creating multi-level referral chain."""
        # Create chain: user1 -> user2 -> user3 -> user4
        profile1 = UserReferralProfileFactory(user=self.user1)
        profile2 = UserReferralProfileFactory(user=self.user2, referred_by=self.user1)
        profile3 = UserReferralProfileFactory(user=self.user3, referred_by=self.user2)
        
        # Create referral objects
        ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        ReferralFactory(user=self.user2, referred_user=self.user3, level=1, referrer=self.user1)
        ReferralFactory(user=self.user1, referred_user=self.user3, level=2, referrer=None)
        
        # Now add user4 to the chain
        result = ReferralService.create_referral_chain(
            self.user4, 
            profile3.referral_code
        )
        
        self.assertTrue(result)
        
        # Check Referral objects for user4
        referrals = Referral.objects.filter(user=self.user4)
        self.assertEqual(referrals.count(), 3)
        
        # Level 1: user4 -> user3
        level1 = referrals.get(level=1)
        self.assertEqual(level1.referrer, self.user3)
        
        # Level 2: user4 -> user2
        level2 = referrals.get(level=2)
        self.assertEqual(level2.referrer, self.user2)
        
        # Level 3: user4 -> user1
        level3 = referrals.get(level=3)
        self.assertEqual(level3.referrer, self.user1)

    @patch('app.referral.services.ReferralConfig.get_active_config')
    def test_process_investment_referral_bonus_success(self, mock_get_config):
        """Test processing investment referral bonus successfully."""
        mock_get_config.return_value = self.config
        
        # Create referral chain
        profile1 = UserReferralProfileFactory(user=self.user1)
        profile2 = UserReferralProfileFactory(user=self.user2, referred_by=self.user1)
        
        referral1 = ReferralFactory(
            user=self.user1, 
            referred_user=self.user2, 
            level=1, 
            referrer=None
        )
        
        # Mock investment object
        investment = MagicMock()
        investment.amount = Decimal('1000.00')
        investment.currency = 'INR'
        investment.id = 123
        
        # Mock wallet crediting
        with patch.object(ReferralEarning, 'credit_to_wallet') as mock_credit:
            mock_credit.return_value = True
            
            result = ReferralService.process_investment_referral_bonus(investment)
            
            self.assertTrue(result)
            
            # Check ReferralEarning was created
            earning = ReferralEarning.objects.get(referral=referral1)
            self.assertEqual(earning.amount, Decimal('50.00'))  # 5% of 1000
            self.assertEqual(earning.currency, 'INR')
            self.assertEqual(earning.level, 1)
            self.assertEqual(earning.investment_id, 123)
            
            # Check credit_to_wallet was called
            mock_credit.assert_called_once()

    @patch('app.referral.services.ReferralConfig.get_active_config')
    def test_process_investment_referral_bonus_no_config(self, mock_get_config):
        """Test processing investment referral bonus with no active config."""
        mock_get_config.return_value = None
        
        investment = MagicMock()
        investment.amount = Decimal('1000.00')
        investment.currency = 'INR'
        
        result = ReferralService.process_investment_referral_bonus(investment)
        
        self.assertFalse(result)

    @patch('app.referral.services.ReferralConfig.get_active_config')
    def test_process_investment_referral_bonus_multi_level(self, mock_get_config):
        """Test processing investment referral bonus for multi-level referrals."""
        mock_get_config.return_value = self.config
        
        # Create multi-level referral chain
        profile1 = UserReferralProfileFactory(user=self.user1)
        profile2 = UserReferralProfileFactory(user=self.user2, referred_by=self.user1)
        profile3 = UserReferralProfileFactory(user=self.user3, referred_by=self.user2)
        
        # Create referral objects
        referral1 = ReferralFactory(
            user=self.user1, 
            referred_user=self.user3, 
            level=2, 
            referrer=None
        )
        referral2 = ReferralFactory(
            user=self.user2, 
            referred_user=self.user3, 
            level=1, 
            referrer=self.user1
        )
        
        # Mock investment object
        investment = MagicMock()
        investment.amount = Decimal('1000.00')
        investment.currency = 'USDT'
        investment.id = 456
        
        # Mock wallet crediting
        with patch.object(ReferralEarning, 'credit_to_wallet') as mock_credit:
            mock_credit.return_value = True
            
            result = ReferralService.process_investment_referral_bonus(investment)
            
            self.assertTrue(result)
            
            # Check ReferralEarning objects were created for both levels
            earnings = ReferralEarning.objects.filter(investment_id=456)
            self.assertEqual(earnings.count(), 2)
            
            # Level 1 earning (3%)
            level1_earning = earnings.get(level=1)
            self.assertEqual(level1_earning.amount, Decimal('30.00'))
            self.assertEqual(level1_earning.currency, 'USDT')
            
            # Level 2 earning (1%)
            level2_earning = earnings.get(level=2)
            self.assertEqual(level2_earning.amount, Decimal('10.00'))
            self.assertEqual(level2_earning.currency, 'USDT')

    def test_check_milestones_success(self):
        """Test checking and triggering milestones successfully."""
        # Create user profile with stats
        profile = UserReferralProfileFactory(
            user=self.user1,
            total_referrals=15,
            total_earnings_inr=Decimal('500.00'),
            total_earnings_usdt=Decimal('100.00')
        )
        
        # Create milestones
        milestone1 = ReferralMilestoneFactory(
            name="10 Referrals",
            condition_type="total_referrals",
            condition_value=10,
            bonus_amount=Decimal('50.00'),
            currency="INR",
            is_active=True
        )
        
        milestone2 = ReferralMilestoneFactory(
            name="500 INR Earnings",
            condition_type="total_earnings",
            condition_value=Decimal('500.00'),
            bonus_amount=Decimal('25.00'),
            currency="USDT",
            is_active=True
        )
        
        # Mock wallet crediting
        with patch.object(ReferralService, '_credit_milestone_bonus') as mock_credit:
            mock_credit.return_value = True
            
            triggered_milestones = ReferralService.check_milestones(self.user1)
            
            # Check both milestones were triggered
            self.assertEqual(len(triggered_milestones), 2)
            self.assertIn(milestone1, triggered_milestones)
            self.assertIn(milestone2, triggered_milestones)
            
            # Check _credit_milestone_bonus was called twice
            self.assertEqual(mock_credit.call_count, 2)

    def test_check_milestones_no_eligible(self):
        """Test checking milestones when none are eligible."""
        # Create user profile with low stats
        profile = UserReferralProfileFactory(
            user=self.user1,
            total_referrals=5,
            total_earnings_inr=Decimal('100.00')
        )
        
        # Create milestone with high requirement
        milestone = ReferralMilestoneFactory(
            name="High Requirement",
            condition_type="total_referrals",
            condition_value=20,
            bonus_amount=Decimal('100.00'),
            currency="INR",
            is_active=True
        )
        
        triggered_milestones = ReferralService.check_milestones(self.user1)
        
        # Check no milestones were triggered
        self.assertEqual(len(triggered_milestones), 0)

    def test_check_milestones_already_credited(self):
        """Test checking milestones that were already credited."""
        # Create user profile
        profile = UserReferralProfileFactory(
            user=self.user1,
            total_referrals=15
        )
        
        # Create milestone
        milestone = ReferralMilestoneFactory(
            name="15 Referrals",
            condition_type="total_referrals",
            condition_value=15,
            bonus_amount=Decimal('50.00'),
            currency="INR",
            is_active=True
        )
        
        # Create existing earning for this milestone
        ReferralEarningFactory(
            referral=None,
            investment=None,
            level=0,
            amount=milestone.bonus_amount,
            currency=milestone.currency,
            transaction_type="milestone_bonus",
            reference_id=milestone.id,
            status="credited"
        )
        
        triggered_milestones = ReferralService.check_milestones(self.user1)
        
        # Check no milestones were triggered (already credited)
        self.assertEqual(len(triggered_milestones), 0)

    @patch('app.wallet.models.INRWallet.objects.get_or_create')
    @patch('app.wallet.models.WalletTransaction.objects.create')
    def test_credit_milestone_bonus_inr(self, mock_create_transaction, mock_get_wallet):
        """Test crediting milestone bonus to INR wallet."""
        # Mock wallet
        mock_wallet = MagicMock()
        mock_get_wallet.return_value = (mock_wallet, True)
        
        # Create milestone
        milestone = ReferralMilestoneFactory(
            name="Test Milestone",
            condition_type="total_referrals",
            condition_value=10,
            bonus_amount=Decimal('100.00'),
            currency="INR",
            is_active=True
        )
        
        # Mock transaction creation
        mock_transaction = MagicMock()
        mock_create_transaction.return_value = mock_transaction
        
        result = ReferralService._credit_milestone_bonus(self.user1, milestone)
        
        self.assertTrue(result)
        
        # Check wallet balance was updated
        mock_wallet.balance.__iadd__.assert_called_once_with(Decimal('100.00'))
        mock_wallet.save.assert_called_once()
        
        # Check transaction was created
        mock_create_transaction.assert_called_once()
        call_args = mock_create_transaction.call_args
        self.assertEqual(call_args[1]['transaction_type'], 'milestone_bonus')
        self.assertEqual(call_args[1]['amount'], Decimal('100.00'))
        self.assertEqual(call_args[1]['currency'], 'INR')
        self.assertEqual(call_args[1]['reference_id'], milestone.id)

    @patch('app.wallet.models.USDTWallet.objects.get_or_create')
    @patch('app.wallet.models.WalletTransaction.objects.create')
    def test_credit_milestone_bonus_usdt(self, mock_create_transaction, mock_get_wallet):
        """Test crediting milestone bonus to USDT wallet."""
        # Mock wallet
        mock_wallet = MagicMock()
        mock_get_wallet.return_value = (mock_wallet, True)
        
        # Create milestone
        milestone = ReferralMilestoneFactory(
            name="Test Milestone",
            condition_type="total_referrals",
            condition_value=10,
            bonus_amount=Decimal('50.00'),
            currency="USDT",
            is_active=True
        )
        
        # Mock transaction creation
        mock_transaction = MagicMock()
        mock_create_transaction.return_value = mock_transaction
        
        result = ReferralService._credit_milestone_bonus(self.user1, milestone)
        
        self.assertTrue(result)
        
        # Check wallet balance was updated
        mock_wallet.balance.__iadd__.assert_called_once_with(Decimal('50.00'))
        mock_wallet.save.assert_called_once()
        
        # Check transaction was created
        mock_create_transaction.assert_called_once()
        call_args = mock_create_transaction.call_args
        self.assertEqual(call_args[1]['currency'], 'USDT')

    def test_get_user_referral_tree(self):
        """Test getting user referral tree structure."""
        # Create referral chain
        profile1 = UserReferralProfileFactory(user=self.user1)
        profile2 = UserReferralProfileFactory(user=self.user2, referred_by=self.user1)
        profile3 = UserReferralProfileFactory(user=self.user3, referred_by=self.user2)
        
        # Create referral objects
        ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        ReferralFactory(user=self.user2, referred_user=self.user3, level=1, referrer=self.user1)
        ReferralFactory(user=self.user1, referred_user=self.user3, level=2, referrer=None)
        
        tree = ReferralService.get_user_referral_tree(self.user1, max_levels=3)
        
        # Check tree structure
        self.assertIn('direct_referrals', tree)
        self.assertIn('sub_referrals', tree)
        self.assertIn('total_referrals', tree)
        self.assertIn('total_earnings', tree)
        
        # Check direct referrals
        direct_refs = tree['direct_referrals']
        self.assertEqual(len(direct_refs), 1)
        self.assertEqual(direct_refs[0]['user_id'], self.user2.id)
        self.assertEqual(direct_refs[0]['level'], 1)
        
        # Check sub-referrals
        sub_refs = tree['sub_referrals']
        self.assertEqual(len(sub_refs), 1)
        self.assertEqual(sub_refs[0]['user_id'], self.user3.id)
        self.assertEqual(sub_refs[0]['level'], 2)

    def test_get_referral_earnings(self):
        """Test getting referral earnings with filters."""
        # Create user profile
        profile = UserReferralProfileFactory(user=self.user1)
        
        # Create referral earnings
        earning1 = ReferralEarningFactory(
            referral__user=self.user1,
            referral__referred_user=self.user2,
            level=1,
            amount=Decimal('50.00'),
            currency='INR',
            created_at=timezone.now()
        )
        
        earning2 = ReferralEarningFactory(
            referral__user=self.user1,
            referral__referred_user=self.user3,
            level=2,
            amount=Decimal('30.00'),
            currency='USDT',
            created_at=timezone.now()
        )
        
        # Test without filters
        earnings = ReferralService.get_referral_earnings(self.user1)
        self.assertEqual(len(earnings), 2)
        
        # Test with currency filter
        inr_earnings = ReferralService.get_referral_earnings(
            self.user1, 
            {'currency': 'INR'}
        )
        self.assertEqual(len(inr_earnings), 1)
        self.assertEqual(inr_earnings[0]['currency'], 'INR')
        
        # Test with level filter
        level1_earnings = ReferralService.get_referral_earnings(
            self.user1, 
            {'level': 1}
        )
        self.assertEqual(len(level1_earnings), 1)
        self.assertEqual(level1_earnings[0]['level'], 1)

    def test_get_referrer_for_user(self):
        """Test getting referrer for a user."""
        # Create referral profile
        profile = UserReferralProfileFactory(
            user=self.user2, 
            referred_by=self.user1
        )
        
        referrer = ReferralService._get_referrer_for_user(self.user2)
        self.assertEqual(referrer, self.user1)

    def test_get_referrer_for_user_no_referrer(self):
        """Test getting referrer for user with no referrer."""
        # Create referral profile without referrer
        profile = UserReferralProfileFactory(
            user=self.user1, 
            referred_by=None
        )
        
        referrer = ReferralService._get_referrer_for_user(self.user1)
        self.assertIsNone(referrer)



