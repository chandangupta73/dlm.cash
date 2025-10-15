import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from freezegun import freeze_time
from .factories import (
    UserFactory, ReferralConfigFactory, ReferralMilestoneFactory,
    UserReferralProfileFactory, ReferralFactory, ReferralEarningFactory
)

User = get_user_model()


@pytest.fixture(autouse=True)
def disable_signals():
    """Disable signals during testing to prevent automatic profile creation."""
    from django.db.models.signals import post_save
    from app.referral.signals import create_user_referral_profile
    
    # Disconnect the signal
    post_save.disconnect(create_user_referral_profile, sender=User)
    
    yield
    
    # Reconnect the signal
    post_save.connect(create_user_referral_profile, sender=User)


@pytest.fixture
def user():
    """Create a test user."""
    return UserFactory()


@pytest.fixture
def referrer_user():
    """Create a user who will be a referrer."""
    return UserFactory()


@pytest.fixture
def referred_user():
    """Create a user who will be referred."""
    return UserFactory()


@pytest.fixture
def referral_config():
    """Create a referral configuration."""
    return ReferralConfigFactory(
        max_levels=3,
        level_1_percentage=Decimal('5.00'),
        level_2_percentage=Decimal('3.00'),
        level_3_percentage=Decimal('1.00')
    )


@pytest.fixture
def referral_profile(user):
    """Create a referral profile for a user."""
    return UserReferralProfileFactory(user=user)


@pytest.fixture
def referrer_profile(referrer_user):
    """Create a referral profile for the referrer."""
    return UserReferralProfileFactory(user=referrer_user)


@pytest.fixture
def referred_profile(referred_user):
    """Create a referral profile for the referred user."""
    return UserReferralProfileFactory(user=referred_user)


@pytest.fixture
def referral_relationship(referrer_profile, referred_profile):
    """Create a referral relationship."""
    return ReferralFactory(
        user=referrer_profile.user,
        referred_user=referred_profile.user,
        level=1
    )


@pytest.fixture
def multi_level_referrals(referrer_profile, referred_profile):
    """Create a multi-level referral chain."""
    # Level 1: referrer -> referred
    level1 = ReferralFactory(
        user=referrer_profile.user,
        referred_user=referred_profile.user,
        level=1
    )
    
    # Level 2: upline -> referrer (if upline exists)
    # This would be created by the referral service
    
    return [level1]


@pytest.fixture
def milestone_inr():
    """Create an INR milestone."""
    return ReferralMilestoneFactory(
        name="First 10 Referrals",
        condition_type="total_referrals",
        condition_value=Decimal('10.00'),
        bonus_amount=Decimal('100.00'),
        currency="INR"
    )


@pytest.fixture
def milestone_usdt():
    """Create a USDT milestone."""
    return ReferralMilestoneFactory(
        name="100 USDT Earnings",
        condition_type="total_earnings",
        condition_value=Decimal('100.00'),
        bonus_amount=Decimal('50.00'),
        currency="USDT"
    )


@pytest.fixture
def investment_mock():
    """Mock investment object for testing."""
    class MockInvestment:
        def __init__(self, user, amount, currency):
            self.id = "test-investment-id"
            self.user = user
            self.amount = amount
            self.currency = currency
            self.created_at = timezone.now()
    
    return MockInvestment


@pytest.fixture
@freeze_time("2024-01-15 10:00:00")
def frozen_time():
    """Freeze time for consistent testing."""
    return timezone.now()


@pytest.fixture
def sample_users():
    """Create multiple users for testing referral chains."""
    users = []
    for i in range(5):
        user = UserFactory()
        users.append(user)
    return users


@pytest.fixture
def referral_chain(sample_users):
    """Create a referral chain with multiple levels."""
    # Create referral profiles for all users
    profiles = []
    for user in sample_users:
        profile = UserReferralProfileFactory(user=user)
        profiles.append(profile)
    
    # Create referral relationships
    referrals = []
    
    # Level 1: User 0 refers User 1
    level1 = ReferralFactory(
        user=profiles[0].user,
        referred_user=profiles[1].user,
        level=1
    )
    referrals.append(level1)
    
    # Level 2: User 1 refers User 2
    level2 = ReferralFactory(
        user=profiles[1].user,
        referred_user=profiles[2].user,
        level=1
    )
    referrals.append(level2)
    
    # Level 3: User 2 refers User 3
    level3 = ReferralFactory(
        user=profiles[2].user,
        referred_user=profiles[3].user,
        level=1
    )
    referrals.append(level3)
    
    return {
        'users': sample_users,
        'profiles': profiles,
        'referrals': referrals
    }
