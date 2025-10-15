from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import logging

from .models import (
    Referral, ReferralEarning, ReferralMilestone, 
    UserReferralProfile, ReferralConfig
)

logger = logging.getLogger(__name__)
User = get_user_model()


class ReferralService:
    """Service class for handling referral operations."""
    
    @staticmethod
    def create_referral_chain(user: User, referrer_code: str = None) -> bool:
        """
        Create referral chain when a new user signs up.
        
        Args:
            user: The new user being registered
            referrer_code: Referral code of the user who referred them
            
        Returns:
            bool: True if referral chain was created successfully
        """
        try:
            with transaction.atomic():
                # Create or get user referral profile
                profile, created = UserReferralProfile.objects.get_or_create(
                    user=user,
                    defaults={'referral_code': None}
                )
                
                if created:
                    profile.generate_referral_code()
                    profile.save()
                
                # If no referrer code provided, just create the profile
                if not referrer_code:
                    return True
                
                # Find the referrer by code
                try:
                    referrer_profile = UserReferralProfile.objects.get(
                        referral_code=referrer_code
                    )
                    referrer = referrer_profile.user
                except UserReferralProfile.DoesNotExist:
                    logger.warning(f"Invalid referral code: {referrer_code}")
                    return True  # Continue without referral
                
                # Prevent self-referral
                if referrer.id == user.id:
                    logger.warning(f"User {user.email} attempted self-referral")
                    return True
                
                # Set the referred_by field on the user's profile
                profile.referred_by = referrer
                profile.save()
                
                # Get referral configuration
                config = ReferralConfig.get_active_config()
                if not config:
                    logger.error("No active referral configuration found")
                    return False
                
                # Create referral relationships for all levels
                ReferralService._create_multi_level_referrals(
                    user, referrer, config.max_levels
                )
                
                # Update referrer's stats
                referrer_profile.update_stats()
                
                return True
                
        except Exception as e:
            logger.error(f"Error creating referral chain for user {user.email}: {str(e)}")
            return False
    
    @staticmethod
    def _create_multi_level_referrals(
        new_user: User, 
        direct_referrer: User, 
        max_levels: int
    ) -> None:
        """
        Create multi-level referral relationships.
        
        Args:
            new_user: The newly registered user
            direct_referrer: The user who directly referred them
            max_levels: Maximum number of levels to create
        """
        current_referrer = direct_referrer
        level = 1
        
        while level <= max_levels and current_referrer:
            # Create referral relationship
            referral, created = Referral.objects.get_or_create(
                user=current_referrer,
                referred_user=new_user,
                level=level,
                defaults={
                    'referrer': ReferralService._get_referrer_for_user(current_referrer)
                }
            )
            
            if created:
                logger.info(f"Created referral: {current_referrer.email} → {new_user.email} (Level {level})")
            
            # Move up the chain for next level
            current_referrer = ReferralService._get_referrer_for_user(current_referrer)
            level += 1
    
    @staticmethod
    def _get_referrer_for_user(user: User) -> Optional[User]:
        """
        Get the user who referred the given user.
        
        Args:
            user: The user to find referrer for
            
        Returns:
            User or None: The referrer user if exists
        """
        try:
            profile = user.referral_profile
            return profile.referred_by
        except UserReferralProfile.DoesNotExist:
            return None
        except AttributeError:
            # Handle case where referral_profile doesn't exist
            return None
    
    @staticmethod
    def process_investment_referral_bonus(investment) -> bool:
        """
        Process referral bonuses when an investment is made.
        
        Args:
            investment: The investment object that triggered the referral bonus
            
        Returns:
            bool: True if all bonuses were processed successfully
        """
        try:
            with transaction.atomic():
                # Get referral configuration
                config = ReferralConfig.get_active_config()
                if not config:
                    logger.error("No active referral configuration found")
                    return False
                
                # Get the user who made the investment
                investor = investment.user
                
                # Find all referral relationships for this user
                referrals = Referral.objects.filter(
                    referred_user=investor,
                    level__lte=config.max_levels
                ).select_related('user')
                
                if not referrals:
                    logger.info(f"No referrals found for investor {investor.email}")
                    return True
                
                # Process referral bonuses for each level
                success_count = 0
                for referral in referrals:
                    if ReferralService._process_single_referral_bonus(
                        referral, investment, config
                    ):
                        success_count += 1
                
                logger.info(f"Processed {success_count}/{len(referrals)} referral bonuses for investment {investment.id}")
                return success_count == len(referrals)
                
        except Exception as e:
            logger.error(f"Error processing referral bonus for investment {investment.id}: {str(e)}")
            return False
    
    @staticmethod
    def _process_single_referral_bonus(
        referral: Referral, 
        investment, 
        config: ReferralConfig
    ) -> bool:
        """
        Process referral bonus for a single referral relationship.
        
        Args:
            referral: The referral relationship
            investment: The investment that triggered the bonus
            config: The referral configuration
            
        Returns:
            bool: True if bonus was processed successfully
        """
        try:
            # Get percentage for this level
            percentage = config.get_percentage_for_level(referral.level)
            if percentage <= 0:
                return True
            
            # Calculate bonus amount
            investment_amount = investment.amount
            bonus_amount = (investment_amount * percentage) / Decimal('100.00')
            
            # Determine currency
            currency = 'USDT' if investment.currency == 'USDT' else 'INR'
            
            # Create referral earning record
            earning = ReferralEarning.objects.create(
                referral=referral,
                investment=investment,
                level=referral.level,
                amount=bonus_amount,
                currency=currency,
                percentage_used=percentage,
                status='pending'
            )
            
            # Credit bonus to wallet
            if earning.credit_to_wallet():
                logger.info(f"Credited {bonus_amount} {currency} referral bonus to {referral.user.email}")
                
                # Update user's referral stats
                try:
                    profile = referral.user.referral_profile
                    profile.update_stats()
                except UserReferralProfile.DoesNotExist:
                    pass
                
                # Check for milestones
                ReferralService.check_milestones(referral.user)
                
                return True
            else:
                logger.error(f"Failed to credit referral bonus for {referral.user.email}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing referral bonus: {str(e)}")
            return False
    
    @staticmethod
    def check_milestones(user: User) -> List[ReferralMilestone]:
        """
        Check if user has reached any milestones and credit bonuses.
        
        Args:
            user: The user to check milestones for
            
        Returns:
            List[ReferralMilestone]: List of milestones that were triggered
        """
        try:
            # Get user's referral profile
            try:
                profile = user.referral_profile
            except UserReferralProfile.DoesNotExist:
                return []
            
            # Get active milestones
            milestones = ReferralMilestone.objects.filter(is_active=True)
            
            triggered_milestones = []
            
            for milestone in milestones:
                if ReferralService._check_single_milestone(profile, milestone):
                    triggered_milestones.append(milestone)
            
            return triggered_milestones
            
        except Exception as e:
            logger.error(f"Error checking milestones for user {user.email}: {str(e)}")
            return []
    
    @staticmethod
    def _check_single_milestone(
        profile: UserReferralProfile, 
        milestone: ReferralMilestone
    ) -> bool:
        """
        Check if a single milestone has been reached.
        
        Args:
            profile: The user's referral profile
            milestone: The milestone to check
            
        Returns:
            bool: True if milestone was triggered
        """
        try:
            # Check if milestone condition is met
            condition_met = False
            
            if milestone.condition_type == 'total_referrals':
                condition_met = profile.total_referrals >= milestone.condition_value
            elif milestone.condition_type == 'total_earnings':
                if milestone.currency == 'INR':
                    condition_met = profile.total_earnings_inr >= milestone.condition_value
                elif milestone.currency == 'USDT':
                    condition_met = profile.total_earnings_usdt >= milestone.condition_value
            
            if not condition_met:
                return False
            
            # Check if milestone bonus was already given
            from app.wallet.models import WalletTransaction
            
            existing_bonus = WalletTransaction.objects.filter(
                user=profile.user,
                transaction_type='milestone_bonus',
                reference_id=str(milestone.id)
            ).exists()
            
            if existing_bonus:
                return False
            
            # Credit milestone bonus
            if ReferralService._credit_milestone_bonus(profile.user, milestone):
                logger.info(f"Milestone bonus credited: {milestone.name} for {profile.user.email}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking milestone {milestone.name}: {str(e)}")
            return False
    
    @staticmethod
    def _credit_milestone_bonus(user: User, milestone: ReferralMilestone) -> bool:
        """
        Credit milestone bonus to user's wallet.
        
        Args:
            user: The user to credit bonus to
            milestone: The milestone that was reached
            
        Returns:
            bool: True if bonus was credited successfully
        """
        try:
            if milestone.currency == 'INR':
                # Credit to INR wallet
                from app.wallet.models import INRWallet, WalletTransaction
                
                wallet, created = INRWallet.objects.get_or_create(
                    user=user,
                    defaults={'balance': Decimal('0.00'), 'status': 'active', 'is_active': True}
                )
                
                # Store balance before adding
                balance_before = wallet.balance
                
                if wallet.add_balance(milestone.bonus_amount):
                    # Create transaction log
                    WalletTransaction.objects.create(
                        user=user,
                        transaction_type='milestone_bonus',
                        wallet_type='inr',
                        amount=milestone.bonus_amount,
                        balance_before=balance_before,
                        balance_after=wallet.balance,
                        status='completed',
                        reference_id=str(milestone.id),
                        description=f"Milestone bonus: {milestone.name}"
                    )
                    return True
                    
            elif milestone.currency == 'USDT':
                # Credit to USDT wallet
                from app.wallet.models import USDTWallet, WalletTransaction
                
                wallet, created = USDTWallet.objects.get_or_create(
                    user=user,
                    defaults={'balance': Decimal('0.000000'), 'status': 'active', 'is_active': True}
                )
                
                # Store balance before adding
                balance_before = wallet.balance
                
                if wallet.add_balance(milestone.bonus_amount):
                    # Create transaction log
                    WalletTransaction.objects.create(
                        user=user,
                        transaction_type='milestone_bonus',
                        wallet_type='usdt',
                        amount=milestone.bonus_amount,
                        balance_before=balance_before,
                        balance_after=wallet.balance,
                        status='completed',
                        reference_id=str(milestone.id),
                        description=f"Milestone bonus: {milestone.name}"
                    )
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error crediting milestone bonus: {str(e)}")
            return False
    
    @staticmethod
    def get_user_referral_tree(user: User, max_levels: int = 3) -> Dict:
        """
        Get the complete referral tree for a user.
        
        Args:
            user: The user to get referral tree for
            max_levels: Maximum levels to include
            
        Returns:
            Dict: Hierarchical referral tree
        """
        try:
            tree = {
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'referral_code': getattr(user.referral_profile, 'referral_code', None)
                },
                'direct_referrals': [],
                'sub_referrals': [],
                'total_referrals': 0,
                'total_earnings': '0.00'
            }
            
            # Get direct referrals (level 1)
            direct_referrals = Referral.objects.filter(
                user=user,
                level=1
            ).select_related('referred_user')
            
            for referral in direct_referrals:
                referred_user = referral.referred_user
                direct_referral_data = {
                    'id': str(referred_user.id),
                    'user_id': str(referred_user.id),
                    'email': referred_user.email,
                    'join_date': referral.created_at,
                    'level': referral.level,
                    'sub_referrals': []
                }
                
                # Get sub-referrals for this user (level 2)
                if max_levels > 1:
                    sub_referrals = Referral.objects.filter(
                        user=referred_user,
                        level=1
                    ).select_related('referred_user')
                    
                    for sub_ref in sub_referrals:
                        sub_user = sub_ref.referred_user
                        sub_referral_data = {
                            'id': str(sub_user.id),
                            'user_id': str(sub_user.id),
                            'email': sub_user.email,
                            'join_date': sub_ref.created_at,
                            'level': 2
                        }
                        direct_referral_data['sub_referrals'].append(sub_referral_data)
                        # Also add to top-level sub_referrals for backward compatibility
                        tree['sub_referrals'].append(sub_referral_data)
                
                tree['direct_referrals'].append(direct_referral_data)
            
            # Update totals
            tree['total_referrals'] = len(tree['direct_referrals'])
            try:
                profile = user.referral_profile
                tree['total_earnings'] = str(profile.total_earnings)
            except UserReferralProfile.DoesNotExist:
                pass
            
            return tree
            
        except Exception as e:
            logger.error(f"Error getting referral tree for user {user.email}: {str(e)}")
            return {}
    
    @staticmethod
    def get_referral_earnings(user: User, filters: Dict = None) -> List[Dict]:
        """
        Get referral earnings for a user with optional filters.
        
        Args:
            user: The user to get earnings for
            filters: Optional filters (currency, date_range, level)
            
        Returns:
            List[Dict]: List of referral earnings
        """
        try:
            earnings_query = ReferralEarning.objects.filter(
                referral__user=user
            ).select_related('referral', 'investment')
            
            # Apply filters
            if filters:
                if filters.get('currency'):
                    earnings_query = earnings_query.filter(currency=filters['currency'])
                
                if filters.get('level'):
                    earnings_query = earnings_query.filter(level=filters['level'])
                
                if filters.get('date_from'):
                    earnings_query = earnings_query.filter(created_at__gte=filters['date_from'])
                
                if filters.get('date_to'):
                    earnings_query = earnings_query.filter(created_at__lte=filters['date_to'])
                
                if filters.get('status'):
                    earnings_query = earnings_query.filter(status=filters['status'])
            
            earnings = earnings_query.order_by('-created_at')
            
            earnings_data = []
            for earning in earnings:
                earnings_data.append({
                    'id': str(earning.id),
                    'amount': str(earning.amount),
                    'currency': earning.currency,
                    'level': earning.level,
                    'percentage': str(earning.percentage_used),
                    'status': earning.status,
                    'created_at': earning.created_at,
                    'credited_at': earning.credited_at,
                    'investment_id': str(earning.investment.id),
                    'referred_user': earning.referral.referred_user.email
                })
            
            return earnings_data
            
        except Exception as e:
            logger.error(f"Error getting referral earnings for user {user.email}: {str(e)}")
            return []
    
    @staticmethod
    def get_referral_earnings_summary(user: User) -> Dict:
        """
        Get referral earnings summary for a user.
        
        Args:
            user: The user to get summary for
            
        Returns:
            Dict: Summary of referral earnings
        """
        try:
            # Get user's referral profile
            try:
                profile = user.referral_profile
            except UserReferralProfile.DoesNotExist:
                return {
                    'total_earnings': '0.00',
                    'total_earnings_inr': '0.00',
                    'total_earnings_usdt': '0.000000',
                    'total_referrals': 0,
                    'last_earning_date': None
                }
            
            # Get recent earnings
            recent_earnings = ReferralEarning.objects.filter(
                referral__user=user,
                status='credited'
            ).order_by('-created_at')[:5]
            
            summary = {
                'total_earnings': str(profile.total_earnings),
                'total_earnings_inr': str(profile.total_earnings_inr),
                'total_earnings_usdt': str(profile.total_earnings_usdt),
                'total_referrals': profile.total_referrals,
                'last_earning_date': profile.last_earning_date,
                'recent_earnings': []
            }
            
            for earning in recent_earnings:
                summary['recent_earnings'].append({
                    'amount': str(earning.amount),
                    'currency': earning.currency,
                    'level': earning.level,
                    'created_at': earning.created_at
                })
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting referral earnings summary for user {user.email}: {str(e)}")
            return {}


# Export the investment handler for use in investment app
