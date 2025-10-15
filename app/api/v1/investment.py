# Investment API v1
# This module provides the investment endpoints for the v1 API
# The actual implementation is in app.investment.views

from app.investment.views import (
    InvestmentPlanViewSet,
    InvestmentViewSet,
    BreakdownRequestViewSet
)

# Export the viewsets for URL routing
__all__ = [
    'InvestmentPlanViewSet',
    'InvestmentViewSet', 
    'BreakdownRequestViewSet'
]
