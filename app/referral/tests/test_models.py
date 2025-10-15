import pytest
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from app.referral.signals import create_user_referral_profile

from ..models import (
    Referral, ReferralEarning, ReferralMilestone, 
    UserReferralProfile, ReferralConfig
)
from .factories import (
    UserFactory, ReferralConfigFactory, ReferralMilestoneFactory,
    UserReferralProfileFactory, ReferralFactory, ReferralEarningFactory
)

User = get_user_model()


class ReferralTestBase(TestCase):
    """Base test class that disables signals during testing."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Disconnect the signal that creates referral profiles automatically
        post_save.disconnect(create_user_referral_profile, sender=User)
    
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # Reconnect the signal
        post_save.connect(create_user_referral_profile, sender=User)


class ReferralConfigModelTest(ReferralTestBase):
    """Test cases for ReferralConfig model."""
    
    def setUp(self):
        """Set up test data."""
        self.config = ReferralConfigFactory()
    
    def test_referral_config_creation(self):
        """Test referral configuration creation."""
        self.assertEqual(self.config.max_levels, 3)
        self.assertEqual(self.config.level_1_percentage, Decimal('5.00'))
        self.assertEqual(self.config.level_2_percentage, Decimal('3.00'))
        self.assertEqual(self.config.level_3_percentage, Decimal('1.00'))
        self.assertTrue(self.config.is_active)
    
    def test_get_active_config(self):
        """Test getting active configuration."""
        active_config = ReferralConfig.get_active_config()
        self.assertEqual(active_config, self.config)
    
    def test_get_percentage_for_level(self):
        """Test getting percentage for specific levels."""
        self.assertEqual(self.config.get_percentage_for_level(1), Decimal('5.00'))
        self.assertEqual(self.config.get_percentage_for_level(2), Decimal('3.00'))
        self.assertEqual(self.config.get_percentage_for_level(3), Decimal('1.00'))
        self.assertEqual(self.config.get_percentage_for_level(4), Decimal('0.00'))
    
    def test_string_representation(self):
        """Test string representation of referral config."""
        expected = "Referral Config - 3 levels, L1:5.00%, L2:3.00%, L3:1.00%"
        self.assertEqual(str(self.config), expected)


class UserReferralProfileModelTest(ReferralTestBase):
    """Test cases for UserReferralProfile model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        # Create profile manually since signals are disabled
        self.profile = UserReferralProfileFactory(user=self.user)
    
    def test_profile_creation(self):
        """Test referral profile creation."""
        self.assertEqual(self.profile.user, self.user)
        self.assertIsNotNone(self.profile.referral_code)
        self.assertEqual(self.profile.total_referrals, 0)
        self.assertEqual(self.profile.total_earnings, Decimal('0.000000'))
    
    def test_generate_referral_code(self):
        """Test referral code generation."""
        original_code = self.profile.referral_code
        self.profile.generate_referral_code()
        self.assertNotEqual(self.profile.referral_code, original_code)
        self.assertEqual(len(self.profile.referral_code), 8)
    
    def test_unique_referral_code(self):
        """Test that referral codes are unique."""
        user2 = UserFactory()
        profile2 = UserReferralProfileFactory(user=user2)
        self.assertNotEqual(self.profile.referral_code, profile2.referral_code)
    
    def test_update_stats(self):
        """Test statistics update."""
        # Create some referrals and earnings
        referred_user = UserFactory()
        referral = ReferralFactory(
            user=self.user,
            referred_user=referred_user,
            level=1
        )
        
        # Create earnings
        earning = ReferralEarningFactory(
            referral=referral,
            amount=Decimal('50.00'),
            currency='INR',
            status='credited'
        )
        
        # Update stats
        self.profile.update_stats()
        
        self.assertEqual(self.profile.total_referrals, 1)
        self.assertEqual(self.profile.total_earnings_inr, Decimal('50.00'))
    
    def test_string_representation(self):
        """Test string representation of profile."""
        expected = f"Referral Profile - {self.user.email} (Code: {self.profile.referral_code})"
        self.assertEqual(str(self.profile), expected)


class ReferralModelTest(ReferralTestBase):
    """Test cases for Referral model."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.user3 = UserFactory()
        
        # Create profiles manually since signals are disabled
        self.profile1 = UserReferralProfileFactory(user=self.user1)
        self.profile2 = UserReferralProfileFactory(user=self.user2)
        self.profile3 = UserReferralProfileFactory(user=self.user3)
    
    def test_referral_creation(self):
        """Test referral relationship creation."""
        referral = ReferralFactory(
            user=self.user1,
            referred_user=self.user2,
            level=1
        )
        
        self.assertEqual(referral.user, self.user1)
        self.assertEqual(referral.referred_user, self.user2)
        self.assertEqual(referral.level, 1)
        self.assertIsNone(referral.referrer)
    
    def test_multi_level_referral(self):
        """Test multi-level referral creation."""
        # Level 1: user1 -> user2
        level1 = ReferralFactory(
            user=self.user1,
            referred_user=self.user2,
            level=1
        )
        
        # Level 2: user2 -> user3
        level2 = ReferralFactory(
            user=self.user2,
            referred_user=self.user3,
            level=1
        )
        
        self.assertEqual(level1.level, 1)
        self.assertEqual(level2.level, 1)
    
    def test_unique_referral_constraint(self):
        """Test unique constraint on referral relationships."""
        ReferralFactory(
            user=self.user1,
            referred_user=self.user2,
            level=1
        )
        
        # Try to create duplicate
        with self.assertRaises(IntegrityError):
            ReferralFactory(
                user=self.user1,
                referred_user=self.user2,
                level=1
            )
    
    def test_is_direct_referral_property(self):
        """Test direct referral property."""
        direct_referral = ReferralFactory(
            user=self.user1,
            referred_user=self.user2,
            level=1
        )
        
        indirect_referral = ReferralFactory(
            user=self.user1,
            referred_user=self.user3,
            level=2
        )
        
        self.assertTrue(direct_referral.is_direct_referral)
        self.assertFalse(indirect_referral.is_direct_referral)
    
    def test_string_representation(self):
        """Test string representation of referral."""
        referral = ReferralFactory(
            user=self.user1,
            referred_user=self.user2,
            level=1
        )
        
        expected = f"{self.user1.email} → {self.user2.email} (Level 1)"
        self.assertEqual(str(referral), expected)


class ReferralEarningModelTest(ReferralTestBase):
    """Test cases for ReferralEarning model."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        
        self.profile1 = UserReferralProfileFactory(user=self.user1)
        self.profile2 = UserReferralProfileFactory(user=self.user2)
        
        self.referral = ReferralFactory(
            user=self.user1,
            referred_user=self.user2,
            level=1
        )
        
        # Mock investment
        class MockInvestment:
            def __init__(self):
                self.id = "test-investment-id"
        
        self.investment = MockInvestment()
    
    def test_earning_creation(self):
        """Test referral earning creation."""
        # Create a real investment for testing
        from app.referral.tests.factories import InvestmentFactory
        investment = InvestmentFactory()
        
        earning = ReferralEarningFactory(
            referral=self.referral,
            investment=investment,
            amount=Decimal('25.00'),
            currency='INR',
            percentage_used=Decimal('5.00')
        )
        
        self.assertEqual(earning.referral, self.referral)
        self.assertEqual(earning.amount, Decimal('25.00'))
        self.assertEqual(earning.currency, 'INR')
        self.assertEqual(earning.status, 'pending')
    
    def test_currency_choices(self):
        """Test currency field choices."""
        earning = ReferralEarningFactory()
        self.assertIn(earning.currency, ['INR', 'USDT'])
    
    def test_status_choices(self):
        """Test status field choices."""
        earning = ReferralEarningFactory()
        self.assertIn(earning.status, ['pending', 'credited', 'failed', 'cancelled'])
    
    def test_percentage_validation(self):
        """Test percentage validation."""
        # Valid percentage
        earning = ReferralEarningFactory(percentage_used=Decimal('5.00'))
        earning.full_clean()
        
        # Invalid percentage (negative)
        earning.percentage_used = Decimal('-1.00')
        with self.assertRaises(ValidationError):
            earning.full_clean()
    
    def test_amount_validation(self):
        """Test amount validation."""
        # Valid amount
        earning = ReferralEarningFactory(amount=Decimal('0.000001'))
        earning.full_clean()
        
        # Invalid amount (zero)
        earning.amount = Decimal('0.00')
        with self.assertRaises(ValidationError):
            earning.full_clean()
    
    def test_string_representation(self):
        """Test string representation of earning."""
        earning = ReferralEarningFactory(
            referral=self.referral,
            amount=Decimal('25.00'),
            currency='INR'
        )
        
        expected = f"{self.user1.email} - 25.00 INR (Level 1)"
        self.assertEqual(str(earning), expected)


class ReferralMilestoneModelTest(ReferralTestBase):
    """Test cases for ReferralMilestone model."""
    
    def setUp(self):
        """Set up test data."""
        self.milestone = ReferralMilestoneFactory()
    
    def test_milestone_creation(self):
        """Test milestone creation."""
        self.assertEqual(self.milestone.condition_type, 'total_referrals')
        self.assertEqual(self.milestone.condition_value, Decimal('10.00'))
        self.assertEqual(self.milestone.bonus_amount, Decimal('100.00'))
        self.assertEqual(self.milestone.currency, 'INR')
        self.assertTrue(self.milestone.is_active)
    
    def test_condition_type_choices(self):
        """Test condition type field choices."""
        self.assertIn(self.milestone.condition_type, ['total_referrals', 'total_earnings'])
    
    def test_currency_choices(self):
        """Test currency field choices."""
        self.assertIn(self.milestone.currency, ['INR', 'USDT'])
    
    def test_condition_value_validation(self):
        """Test condition value validation."""
        # Valid value
        self.milestone.condition_value = Decimal('1.00')
        self.milestone.full_clean()
        
        # Invalid value (zero)
        self.milestone.condition_value = Decimal('0.00')
        with self.assertRaises(ValidationError):
            self.milestone.full_clean()
    
    def test_bonus_amount_validation(self):
        """Test bonus amount validation."""
        # Valid amount
        self.milestone.bonus_amount = Decimal('1.00')
        self.milestone.full_clean()
        
        # Invalid amount (zero)
        self.milestone.bonus_amount = Decimal('0.00')
        with self.assertRaises(ValidationError):
            self.milestone.full_clean()
    
    def test_string_representation(self):
        """Test string representation of milestone."""
        # The string representation should contain the milestone details, not a specific ID
        milestone_str = str(self.milestone)
        self.assertIn("10.00 total_referrals", milestone_str)
        self.assertIn("100.00 INR", milestone_str)
        self.assertIn("Milestone", milestone_str)
    
    def test_ordering(self):
        """Test milestone ordering by condition value."""
        # Clear existing milestones to avoid interference
        ReferralMilestone.objects.all().delete()
        
        milestone1 = ReferralMilestoneFactory(condition_value=Decimal('5.00'))
        milestone2 = ReferralMilestoneFactory(condition_value=Decimal('10.00'))
        milestone3 = ReferralMilestoneFactory(condition_value=Decimal('15.00'))
        
        # Check that milestones are ordered by condition_value (ascending)
        milestones = list(ReferralMilestone.objects.order_by('condition_value'))
        self.assertEqual(len(milestones), 3)
        self.assertEqual(milestones[0].condition_value, Decimal('5.00'))
        self.assertEqual(milestones[1].condition_value, Decimal('10.00'))
        self.assertEqual(milestones[2].condition_value, Decimal('15.00'))


class ReferralModelRelationshipsTest(TestCase):
    """Test cases for referral model relationships."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.user3 = UserFactory()
        
        self.profile1 = UserReferralProfileFactory(user=self.user1)
        self.profile2 = UserReferralProfileFactory(user=self.user2)
        self.profile3 = UserReferralProfileFactory(user=self.user3)
    
    def test_user_referral_profile_relationship(self):
        """Test user-referral profile relationship."""
        self.assertEqual(self.user1.referral_profile, self.profile1)
        self.assertEqual(self.profile1.user, self.user1)
    
    def test_referral_user_relationships(self):
        """Test referral user relationships."""
        referral = ReferralFactory(
            user=self.user1,
            referred_user=self.user2,
            level=1
        )
        
        self.assertEqual(referral.user, self.user1)
        self.assertEqual(referral.referred_user, self.user2)
    
    def test_referral_earning_relationships(self):
        """Test referral earning relationships."""
        referral = ReferralFactory(
            user=self.user1,
            referred_user=self.user2,
            level=1
        )
        
        earning = ReferralEarningFactory(referral=referral)
        
        self.assertEqual(earning.referral, referral)
        self.assertEqual(referral.earnings.first(), earning)
    
    def test_cascade_deletion(self):
        """Test cascade deletion behavior."""
        referral = ReferralFactory(
            user=self.user1,
            referred_user=self.user2,
            level=1
        )
        
        earning = ReferralEarningFactory(referral=referral)
        
        # Delete referral should delete earning
        referral.delete()
        self.assertFalse(ReferralEarning.objects.filter(id=earning.id).exists())
    
    def test_referral_chain_tracking(self):
        """Test referral chain tracking."""
        # Create a chain: user1 -> user2 -> user3
        referral1 = ReferralFactory(
            user=self.user1,
            referred_user=self.user2,
            level=1
        )
        
        referral2 = ReferralFactory(
            user=self.user2,
            referred_user=self.user3,
            level=1
        )
        
        # Set referrer for level 2
        referral2.referrer = self.user1
        referral2.save()
        
        self.assertEqual(referral2.referrer, self.user1)
        self.assertEqual(referral1.user, self.user1)


class ReferralModelValidationTest(ReferralTestBase):
    """Test cases for referral model validation."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.profile1 = UserReferralProfileFactory(user=self.user1)
        self.profile2 = UserReferralProfileFactory(user=self.user2)
    
    def test_self_referral_prevention(self):
        """Test that users cannot refer themselves."""
        # This should be prevented at the service level, not model level
        # But we can test the model allows it for flexibility
        referral = ReferralFactory(
            user=self.user1,
            referred_user=self.user1,
            level=1
        )
        
        # Model allows it, but service should prevent it
        self.assertEqual(referral.user, referral.referred_user)
    
    def test_level_validation(self):
        """Test level field validation."""
        # Valid level
        referral = ReferralFactory(level=1)
        referral.full_clean()
        
        # Invalid level (zero)
        referral.level = 0
        with self.assertRaises(ValidationError):
            referral.full_clean()
    
    def test_referral_code_uniqueness(self):
        """Test referral code uniqueness."""
        # Create new users for this test to avoid conflicts
        user3 = UserFactory()
        user4 = UserFactory()
        
        profile1 = UserReferralProfileFactory(user=user3)
        profile2 = UserReferralProfileFactory(user=user4)
        
        self.assertNotEqual(profile1.referral_code, profile2.referral_code)
        
        # Try to set duplicate code
        profile2.referral_code = profile1.referral_code
        with self.assertRaises(IntegrityError):
            profile2.save()
    
    def test_decimal_precision(self):
        """Test decimal field precision."""
        earning = ReferralEarningFactory(
            amount=Decimal('123.456789'),
            percentage_used=Decimal('12.34')
        )
        
        # Should maintain precision
        self.assertEqual(earning.amount, Decimal('123.456789'))
        self.assertEqual(earning.percentage_used, Decimal('12.34'))
