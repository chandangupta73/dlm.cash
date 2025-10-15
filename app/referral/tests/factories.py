import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from decimal import Decimal
import uuid

from ..models import (
    Referral, ReferralEarning, ReferralMilestone, 
    UserReferralProfile, ReferralConfig
)

User = get_user_model()


class UserFactory(DjangoModelFactory):
    """Factory for creating test users."""
    
    class Meta:
        model = User
    
    id = factory.LazyFunction(uuid.uuid4)
    email = factory.Sequence(lambda n: f'user{n}@example.com')
    username = factory.Sequence(lambda n: f'user{n}')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    is_active = True
    is_staff = False
    is_superuser = False


class ReferralConfigFactory(DjangoModelFactory):
    """Factory for creating referral configurations."""
    
    class Meta:
        model = ReferralConfig
    
    id = factory.LazyFunction(uuid.uuid4)
    max_levels = 3
    level_1_percentage = Decimal('5.00')
    level_2_percentage = Decimal('3.00')
    level_3_percentage = Decimal('1.00')
    is_active = True


class UserReferralProfileFactory(DjangoModelFactory):
    """Factory for creating user referral profiles."""
    
    class Meta:
        model = UserReferralProfile
    
    id = factory.LazyFunction(uuid.uuid4)
    user = None  # Will be set manually in tests
    referral_code = factory.Sequence(lambda n: f'REF{n:08d}')
    referred_by = None
    total_referrals = 0
    total_earnings = Decimal('0.000000')
    total_earnings_inr = Decimal('0.00')
    total_earnings_usdt = Decimal('0.000000')
    last_earning_date = None
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to handle existing profiles created by signals."""
        user = kwargs.get('user')
        if user and hasattr(user, 'referral_profile') and user.referral_profile:
            # Profile already exists, return it
            return user.referral_profile
        
        # Create new profile
        return super()._create(model_class, *args, **kwargs)


class ReferralFactory(DjangoModelFactory):
    """Factory for creating referral relationships."""
    
    class Meta:
        model = Referral
    
    id = factory.LazyFunction(uuid.uuid4)
    user = None  # Will be set manually in tests
    referred_user = None  # Will be set manually in tests
    level = 1
    referrer = None
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to handle missing required fields."""
        if not kwargs.get('user'):
            kwargs['user'] = UserFactory()
        if not kwargs.get('referred_user'):
            kwargs['referred_user'] = UserFactory()
        
        return super()._create(model_class, *args, **kwargs)


class ReferralMilestoneFactory(DjangoModelFactory):
    """Factory for creating referral milestones."""
    
    class Meta:
        model = ReferralMilestone
    
    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f'Milestone {n}')
    description = factory.Faker('text', max_nb_chars=200)
    condition_type = 'total_referrals'
    condition_value = Decimal('10.00')
    bonus_amount = Decimal('100.00')
    currency = 'INR'
    is_active = True


class ReferralEarningFactory(DjangoModelFactory):
    """Factory for creating referral earnings."""
    
    class Meta:
        model = ReferralEarning
    
    id = factory.LazyFunction(uuid.uuid4)
    referral = None  # Will be set manually in tests
    investment = None  # Will be set manually in tests
    level = 1
    amount = Decimal('10.00')
    currency = 'INR'
    percentage_used = Decimal('5.00')
    status = 'pending'
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to handle missing required fields."""
        if not kwargs.get('referral'):
            kwargs['referral'] = ReferralFactory()
        if not kwargs.get('investment'):
            kwargs['investment'] = InvestmentFactory()
        
        return super()._create(model_class, *args, **kwargs)


# Specialized factories for different scenarios
class DirectReferralFactory(ReferralFactory):
    """Factory for creating direct referrals (level 1)."""
    level = 1


class IndirectReferralFactory(ReferralFactory):
    """Factory for creating indirect referrals (level 2+)."""
    level = 2


class INRReferralEarningFactory(ReferralEarningFactory):
    """Factory for creating INR referral earnings."""
    currency = 'INR'
    amount = Decimal('50.00')


class USDTReferralEarningFactory(ReferralEarningFactory):
    """Factory for creating USDT referral earnings."""
    currency = 'USDT'
    amount = Decimal('25.000000')


class MilestoneReferralsFactory(ReferralMilestoneFactory):
    """Factory for creating referral count milestones."""
    condition_type = 'total_referrals'
    condition_value = Decimal('5.00')
    bonus_amount = Decimal('50.00')


class MilestoneEarningsFactory(ReferralMilestoneFactory):
    """Factory for creating earnings milestones."""
    condition_type = 'total_earnings'
    condition_value = Decimal('100.00')
    bonus_amount = Decimal('25.00')


# Factory for creating complete referral chains
class ReferralChainFactory:
    """Factory for creating multi-level referral chains."""
    
    @staticmethod
    def create_chain(depth=3, users_per_level=2):
        """
        Create a referral chain with specified depth and users per level.
        
        Args:
            depth: Number of levels in the chain
            users_per_level: Number of users at each level
            
        Returns:
            dict: Dictionary containing the created objects
        """
        chain_data = {
            'users': [],
            'profiles': [],
            'referrals': [],
            'levels': {}
        }
        
        # Create users and profiles for each level
        for level in range(depth):
            level_users = []
            level_profiles = []
            
            for i in range(users_per_level):
                user = UserFactory()
                profile = UserReferralProfileFactory(user=user)
                level_users.append(user)
                level_profiles.append(profile)
            
            chain_data['users'].extend(level_users)
            chain_data['profiles'].extend(level_profiles)
            chain_data['levels'][level] = {
                'users': level_users,
                'profiles': level_profiles
            }
        
        # Create referral relationships
        for level in range(1, depth):
            for i, profile in enumerate(chain_data['levels'][level]['profiles']):
                # Find a referrer from the previous level
                referrer_profile = chain_data['levels'][level-1]['profiles'][i % len(chain_data['levels'][level-1]['profiles'])]
                
                referral = ReferralFactory(
                    user=referrer_profile.user,
                    referred_user=profile.user,
                    level=1  # Direct referral
                )
                
                chain_data['referrals'].append(referral)
        
        return chain_data


# Factory for creating test scenarios
class ReferralTestScenarioFactory:
    """Factory for creating common test scenarios."""
    
    @staticmethod
    def create_basic_scenario():
        """Create a basic referral scenario with 3 users."""
        user1 = UserFactory()
        user2 = UserFactory()
        user3 = UserFactory()
        
        profile1 = UserReferralProfileFactory(user=user1)
        profile2 = UserReferralProfileFactory(user=user2)
        profile3 = UserReferralProfileFactory(user=user3)
        
        # User1 refers User2
        referral1 = ReferralFactory(
            user=user1,
            referred_user=user2,
            level=1
        )
        
        # User2 refers User3
        referral2 = ReferralFactory(
            user=user2,
            referred_user=user3,
            level=1
        )
        
        return {
            'users': [user1, user2, user3],
            'profiles': [profile1, profile2, profile3],
            'referrals': [referral1, referral2]
        }
    
    @staticmethod
    def create_milestone_scenario():
        """Create a scenario with milestones."""
        # Create users
        users = [UserFactory() for _ in range(3)]
        profiles = [UserReferralProfileFactory(user=user) for user in users]
        
        # Create milestones
        milestone1 = MilestoneReferralsFactory(
            name="First 5 Referrals",
            condition_value=Decimal('5.00'),
            bonus_amount=Decimal('100.00'),
            currency='INR'
        )
        
        milestone2 = MilestoneEarningsFactory(
            name="100 INR Earnings",
            condition_value=Decimal('100.00'),
            bonus_amount=Decimal('50.00'),
            currency='INR'
        )
        
        return {
            'users': users,
            'profiles': profiles,
            'milestones': [milestone1, milestone2]
        }


class InvestmentPlanFactory(DjangoModelFactory):
    """Factory for creating investment plans."""
    
    class Meta:
        model = 'investment.InvestmentPlan'
    
    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f'Plan {n}')
    description = factory.Faker('text', max_nb_chars=200)
    min_amount = Decimal('100.00')
    max_amount = Decimal('10000.00')
    roi_rate = Decimal('5.00')
    frequency = 'daily'
    duration_days = 30
    breakdown_window_days = 7
    status = 'active'
    is_active = True


class InvestmentFactory(DjangoModelFactory):
    """Factory for creating investments."""
    
    class Meta:
        model = 'investment.Investment'
    
    id = factory.LazyFunction(uuid.uuid4)
    user = factory.SubFactory(UserFactory)
    plan = factory.SubFactory(InvestmentPlanFactory)
    amount = Decimal('1000.00')
    currency = 'inr'
    status = 'active'
    is_active = True
