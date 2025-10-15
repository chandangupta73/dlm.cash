from decimal import Decimal
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.admin.sites import AdminSite
from django.contrib.admin import ModelAdmin
from django.utils import timezone
from unittest.mock import patch, MagicMock
from freezegun import freeze_time

from app.referral.models import (
    ReferralConfig, UserReferralProfile, Referral, 
    ReferralEarning, ReferralMilestone
)
from app.referral.admin import (
    ReferralConfigAdmin, UserReferralProfileAdmin, ReferralAdmin,
    ReferralEarningAdmin, ReferralMilestoneAdmin, get_referral_stats
)
from app.referral.tests.factories import (
    UserFactory, ReferralConfigFactory, UserReferralProfileFactory,
    ReferralFactory, ReferralMilestoneFactory, ReferralEarningFactory
)

User = get_user_model()


class ReferralAdminTestCase(TestCase):
    """Test cases for referral admin interface."""

    def setUp(self):
        """Set up test data."""
        self.site = AdminSite()
        self.factory = RequestFactory()
        
        # Create users
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.user3 = UserFactory()
        self.admin_user = UserFactory(is_staff=True, is_superuser=True)
        
        # Create referral config
        self.config = ReferralConfigFactory(
            max_levels=3,
            level_1_percentage=Decimal('5.0'),
            level_2_percentage=Decimal('3.0'),
            level_3_percentage=Decimal('1.0'),
            is_active=True
        )
        
        # Create referral profiles and referrals
        self.profile1 = UserReferralProfileFactory(user=self.user1)
        self.profile2 = UserReferralProfileFactory(user=self.user2, referred_by=self.user1)
        self.profile3 = UserReferralProfileFactory(user=self.user3, referred_by=self.user2)
        
        self.referral1 = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        self.referral2 = ReferralFactory(user=self.user2, referred_user=self.user3, level=1, referrer=self.user1)

    def test_referral_config_admin_list_display(self):
        """Test ReferralConfigAdmin list_display."""
        admin = ReferralConfigAdmin(ReferralConfig, self.site)
        
        self.assertIn('max_levels', admin.list_display)
        self.assertIn('level_1_percentage', admin.list_display)
        self.assertIn('level_2_percentage', admin.list_display)
        self.assertIn('level_3_percentage', admin.list_display)
        self.assertIn('is_active', admin.list_display)
        self.assertIn('created_at', admin.list_display)

    def test_referral_config_admin_list_filter(self):
        """Test ReferralConfigAdmin list_filter."""
        admin = ReferralConfigAdmin(ReferralConfig, self.site)
        
        self.assertIn('is_active', admin.list_filter)
        self.assertIn('created_at', admin.list_filter)

    def test_referral_config_admin_search_fields(self):
        """Test ReferralConfigAdmin search_fields."""
        admin = ReferralConfigAdmin(ReferralConfig, self.site)
        
        self.assertIn('max_levels', admin.search_fields)

    def test_referral_config_admin_readonly_fields(self):
        """Test ReferralConfigAdmin readonly_fields."""
        admin = ReferralConfigAdmin(ReferralConfig, self.site)
        
        self.assertIn('created_at', admin.readonly_fields)
        self.assertIn('updated_at', admin.readonly_fields)

    def test_user_referral_profile_admin_list_display(self):
        """Test UserReferralProfileAdmin list_display."""
        admin = UserReferralProfileAdmin(UserReferralProfile, self.site)
        
        self.assertIn('user_email', admin.list_display)
        self.assertIn('referral_code', admin.list_display)
        self.assertIn('referred_by_email', admin.list_display)
        self.assertIn('total_referrals', admin.list_display)
        self.assertIn('total_earnings_inr', admin.list_display)
        self.assertIn('total_earnings_usdt', admin.list_display)
        self.assertIn('last_earning_date', admin.list_display)
        self.assertIn('created_at', admin.list_display)

    def test_user_referral_profile_admin_list_filter(self):
        """Test UserReferralProfileAdmin list_filter."""
        admin = UserReferralProfileAdmin(UserReferralProfile, self.site)
        
        self.assertIn('referred_by', admin.list_filter)
        self.assertIn('created_at', admin.list_filter)
        self.assertIn('last_earning_date', admin.list_display)

    def test_user_referral_profile_admin_search_fields(self):
        """Test UserReferralProfileAdmin search_fields."""
        admin = UserReferralProfileAdmin(UserReferralProfile, self.site)
        
        self.assertIn('user__email', admin.search_fields)
        self.assertIn('user__username', admin.search_fields)
        self.assertIn('referral_code', admin.search_fields)

    def test_user_referral_profile_admin_readonly_fields(self):
        """Test UserReferralProfileAdmin readonly_fields."""
        admin = UserReferralProfileAdmin(UserReferralProfile, self.site)
        
        self.assertIn('created_at', admin.readonly_fields)
        self.assertIn('updated_at', admin.readonly_fields)
        self.assertIn('last_earning_date', admin.readonly_fields)

    def test_user_referral_profile_admin_actions(self):
        """Test UserReferralProfileAdmin actions."""
        admin = UserReferralProfileAdmin(UserReferralProfile, self.site)
        
        self.assertIn('regenerate_referral_code', admin.actions)
        self.assertIn('update_stats', admin.actions)

    def test_user_referral_profile_admin_user_email_method(self):
        """Test UserReferralProfileAdmin user_email method."""
        admin = UserReferralProfileAdmin(UserReferralProfile, self.site)
        
        email = admin.user_email(self.profile1)
        self.assertEqual(email, self.user1.email)

    def test_user_referral_profile_admin_referred_by_email_method(self):
        """Test UserReferralProfileAdmin referred_by_email method."""
        admin = UserReferralProfileAdmin(UserReferralProfile, self.site)
        
        # Test with referrer
        email = admin.referred_by_email(self.profile2)
        self.assertEqual(email, self.user1.email)
        
        # Test without referrer
        email = admin.referred_by_email(self.profile1)
        self.assertEqual(email, '-')

    def test_user_referral_profile_admin_regenerate_referral_code_action(self):
        """Test UserReferralProfileAdmin regenerate_referral_code action."""
        admin = UserReferralProfileAdmin(UserReferralProfile, self.site)
        request = self.factory.get('/')
        request.user = self.admin_user
        
        old_code = self.profile1.referral_code
        
        # Call the action
        admin.regenerate_referral_code(request, UserReferralProfile.objects.filter(id=self.profile1.id))
        
        # Check that code was regenerated
        self.profile1.refresh_from_db()
        self.assertNotEqual(old_code, self.profile1.referral_code)

    def test_user_referral_profile_admin_update_stats_action(self):
        """Test UserReferralProfileAdmin update_stats action."""
        admin = UserReferralProfileAdmin(UserReferralProfile, self.site)
        request = self.factory.get('/')
        request.user = self.admin_user
        
        # Create some referral data
        referral = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        earning = ReferralEarningFactory(
            referral=referral,
            level=1,
            amount=Decimal('50.00'),
            currency='INR'
        )
        
        # Call the action
        admin.update_stats(request, UserReferralProfile.objects.filter(id=self.profile1.id))
        
        # Check that stats were updated
        self.profile1.refresh_from_db()
        self.assertEqual(self.profile1.total_referrals, 1)
        self.assertEqual(self.profile1.total_earnings_inr, Decimal('50.00'))

    def test_referral_admin_list_display(self):
        """Test ReferralAdmin list_display."""
        admin = ReferralAdmin(Referral, self.site)
        
        self.assertIn('user_email', admin.list_display)
        self.assertIn('referred_user_email', admin.list_display)
        self.assertIn('level', admin.list_display)
        self.assertIn('referrer_email', admin.list_display)
        self.assertIn('created_at', admin.list_display)

    def test_referral_admin_list_filter(self):
        """Test ReferralAdmin list_filter."""
        admin = ReferralAdmin(Referral, self.site)
        
        self.assertIn('level', admin.list_filter)
        self.assertIn('created_at', admin.list_filter)

    def test_referral_admin_search_fields(self):
        """Test ReferralAdmin search_fields."""
        admin = ReferralAdmin(Referral, self.site)
        
        self.assertIn('user__email', admin.search_fields)
        self.assertIn('referred_user__email', admin.search_fields)
        self.assertIn('referrer__email', admin.search_fields)

    def test_referral_admin_readonly_fields(self):
        """Test ReferralAdmin readonly_fields."""
        admin = ReferralAdmin(Referral, self.site)
        
        self.assertIn('created_at', admin.readonly_fields)
        self.assertIn('updated_at', admin.readonly_fields)

    def test_referral_admin_user_email_method(self):
        """Test ReferralAdmin user_email method."""
        admin = ReferralAdmin(Referral, self.site)
        
        email = admin.user_email(self.referral1)
        self.assertEqual(email, self.user1.email)

    def test_referral_admin_referred_user_email_method(self):
        """Test ReferralAdmin referred_user_email method."""
        admin = ReferralAdmin(Referral, self.site)
        
        email = admin.referred_user_email(self.referral1)
        self.assertEqual(email, self.user2.email)

    def test_referral_admin_referrer_email_method(self):
        """Test ReferralAdmin referrer_email method."""
        admin = ReferralAdmin(Referral, self.site)
        
        # Test with referrer
        email = admin.referrer_email(self.referral2)
        self.assertEqual(email, self.user1.email)
        
        # Test without referrer
        email = admin.referrer_email(self.referral1)
        self.assertEqual(email, '-')

    def test_referral_earning_admin_list_display(self):
        """Test ReferralEarningAdmin list_display."""
        admin = ReferralEarningAdmin(ReferralEarning, self.site)
        
        self.assertIn('referral_user_email', admin.list_display)
        self.assertIn('level', admin.list_display)
        self.assertIn('amount', admin.list_display)
        self.assertIn('currency', admin.list_display)
        self.assertIn('status', admin.list_display)
        self.assertIn('credited_at', admin.list_display)
        self.assertIn('created_at', admin.list_display)

    def test_referral_earning_admin_list_filter(self):
        """Test ReferralEarningAdmin list_filter."""
        admin = ReferralEarningAdmin(ReferralEarning, self.site)
        
        self.assertIn('level', admin.list_filter)
        self.assertIn('currency', admin.list_filter)
        self.assertIn('status', admin.list_filter)
        self.assertIn('created_at', admin.list_filter)

    def test_referral_earning_admin_search_fields(self):
        """Test ReferralEarningAdmin search_fields."""
        admin = ReferralEarningAdmin(ReferralEarning, self.site)
        
        self.assertIn('referral__user__email', admin.search_fields)
        self.assertIn('currency', admin.search_fields)

    def test_referral_earning_admin_readonly_fields(self):
        """Test ReferralEarningAdmin readonly_fields."""
        admin = ReferralEarningAdmin(ReferralEarning, self.site)
        
        self.assertIn('created_at', admin.readonly_fields)
        self.assertIn('updated_at', admin.readonly_fields)
        self.assertIn('credited_at', admin.readonly_fields)

    def test_referral_earning_admin_referral_user_email_method(self):
        """Test ReferralEarningAdmin referral_user_email method."""
        admin = ReferralEarningAdmin(ReferralEarning, self.site)
        
        # Create earning
        earning = ReferralEarningFactory(
            referral=self.referral1,
            level=1,
            amount=Decimal('50.00'),
            currency='INR'
        )
        
        email = admin.referral_user_email(earning)
        self.assertEqual(email, self.user1.email)

    def test_referral_milestone_admin_list_display(self):
        """Test ReferralMilestoneAdmin list_display."""
        admin = ReferralMilestoneAdmin(ReferralMilestone, self.site)
        
        self.assertIn('name', admin.list_display)
        self.assertIn('condition_type', admin.list_display)
        self.assertIn('condition_value', admin.list_display)
        self.assertIn('bonus_amount', admin.list_display)
        self.assertIn('currency', admin.list_display)
        self.assertIn('is_active', admin.list_display)
        self.assertIn('created_at', admin.list_display)

    def test_referral_milestone_admin_list_filter(self):
        """Test ReferralMilestoneAdmin list_filter."""
        admin = ReferralMilestoneAdmin(ReferralMilestone, self.site)
        
        self.assertIn('condition_type', admin.list_filter)
        self.assertIn('currency', admin.list_filter)
        self.assertIn('is_active', admin.list_filter)
        self.assertIn('created_at', admin.list_filter)

    def test_referral_milestone_admin_search_fields(self):
        """Test ReferralMilestoneAdmin search_fields."""
        admin = ReferralMilestoneAdmin(ReferralMilestone, self.site)
        
        self.assertIn('name', admin.search_fields)
        self.assertIn('condition_type', admin.search_fields)

    def test_referral_milestone_admin_readonly_fields(self):
        """Test ReferralMilestoneAdmin readonly_fields."""
        admin = ReferralMilestoneAdmin(ReferralMilestone, self.site)
        
        self.assertIn('created_at', admin.readonly_fields)
        self.assertIn('updated_at', admin.readonly_fields)

    def test_get_referral_stats_function(self):
        """Test get_referral_stats function."""
        # Create some test data
        milestone = ReferralMilestoneFactory(
            name="Test Milestone",
            condition_type="total_referrals",
            condition_value=10,
            bonus_amount=Decimal('50.00'),
            currency="INR",
            is_active=True
        )
        
        stats = get_referral_stats()
        
        # Check that stats contain expected keys
        self.assertIn('total_users', stats)
        self.assertIn('total_referrals', stats)
        self.assertIn('total_earnings', stats)
        self.assertIn('active_milestones', stats)
        
        # Check that values are reasonable
        self.assertIsInstance(stats['total_users'], int)
        self.assertIsInstance(stats['total_referrals'], int)
        self.assertIsInstance(stats['total_earnings'], dict)
        self.assertIsInstance(stats['active_milestones'], int)

    def test_admin_model_registration(self):
        """Test that all models are properly registered in admin."""
        # Check that models are registered
        registered_models = self.site._registry
        
        self.assertIn(ReferralConfig, registered_models)
        self.assertIn(UserReferralProfile, registered_models)
        self.assertIn(Referral, registered_models)
        self.assertIn(ReferralEarning, registered_models)
        self.assertIn(ReferralMilestone, registered_models)

    def test_admin_custom_methods_with_html(self):
        """Test admin custom methods that return HTML."""
        # Test user_email method with HTML link
        admin = UserReferralProfileAdmin(UserReferralProfile, self.site)
        
        email_html = admin.user_email(self.profile1)
        self.assertIn(self.user1.email, email_html)
        self.assertIn('href', email_html)  # Should contain link
        
        # Test referred_by_email method with HTML link
        email_html = admin.referred_by_email(self.profile2)
        self.assertIn(self.user1.email, email_html)
        self.assertIn('href', email_html)  # Should contain link

    def test_admin_actions_permissions(self):
        """Test that admin actions respect permissions."""
        admin = UserReferralProfileAdmin(UserReferralProfile, self.site)
        request = self.factory.get('/')
        request.user = self.user1  # Regular user, not admin
        
        # Try to call admin action
        with self.assertRaises(Exception):
            admin.regenerate_referral_code(request, UserReferralProfile.objects.all())

    def test_admin_list_display_links(self):
        """Test admin list_display_links."""
        # Test ReferralConfigAdmin
        admin = ReferralConfigAdmin(ReferralConfig, self.site)
        self.assertIn('max_levels', admin.list_display_links)
        
        # Test UserReferralProfileAdmin
        admin = UserReferralProfileAdmin(UserReferralProfile, self.site)
        self.assertIn('referral_code', admin.list_display_links)
        
        # Test ReferralAdmin
        admin = ReferralAdmin(Referral, self.site)
        self.assertIn('level', admin.list_display_links)
        
        # Test ReferralEarningAdmin
        admin = ReferralEarningAdmin(ReferralEarning, self.site)
        self.assertIn('amount', admin.list_display_links)
        
        # Test ReferralMilestoneAdmin
        admin = ReferralMilestoneAdmin(ReferralMilestone, self.site)
        self.assertIn('name', admin.list_display_links)

    def test_admin_ordering(self):
        """Test admin ordering."""
        # Test ReferralConfigAdmin
        admin = ReferralConfigAdmin(ReferralConfig, self.site)
        self.assertEqual(admin.ordering, ['-created_at'])
        
        # Test UserReferralProfileAdmin
        admin = UserReferralProfileAdmin(UserReferralProfile, self.site)
        self.assertEqual(admin.ordering, ['-created_at'])
        
        # Test ReferralAdmin
        admin = ReferralAdmin(Referral, self.site)
        self.assertEqual(admin.ordering, ['-created_at'])
        
        # Test ReferralEarningAdmin
        admin = ReferralEarningAdmin(ReferralEarning, self.site)
        self.assertEqual(admin.ordering, ['-created_at'])
        
        # Test ReferralMilestoneAdmin
        admin = ReferralMilestoneAdmin(ReferralMilestone, self.site)
        self.assertEqual(admin.ordering, ['-created_at'])

    def test_admin_date_hierarchy(self):
        """Test admin date_hierarchy."""
        # Test ReferralConfigAdmin
        admin = ReferralConfigAdmin(ReferralConfig, self.site)
        self.assertEqual(admin.date_hierarchy, 'created_at')
        
        # Test UserReferralProfileAdmin
        admin = UserReferralProfileAdmin(UserReferralProfile, self.site)
        self.assertEqual(admin.date_hierarchy, 'created_at')
        
        # Test ReferralAdmin
        admin = ReferralAdmin(Referral, self.site)
        self.assertEqual(admin.date_hierarchy, 'created_at')
        
        # Test ReferralEarningAdmin
        admin = ReferralEarningAdmin(ReferralEarning, self.site)
        self.assertEqual(admin.date_hierarchy, 'created_at')
        
        # Test ReferralMilestoneAdmin
        admin = ReferralMilestoneAdmin(ReferralMilestone, self.site)
        self.assertEqual(admin.date_hierarchy, 'created_at')



