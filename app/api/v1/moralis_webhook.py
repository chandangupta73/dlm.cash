from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json
import logging

from app.services.real_wallet_service import real_wallet_service

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def moralis_usdt_webhook(request):
    """Handle Moralis webhook for USDT deposits."""
    try:
        # Parse webhook data
        webhook_data = json.loads(request.body)
        
        # Log webhook for debugging
        logger.info(f"Moralis webhook received: {webhook_data}")
        
        # Process the webhook
        result = real_wallet_service.process_moralis_webhook(webhook_data)
        
        if result['success']:
            logger.info(f"Webhook processed successfully: {result}")
            return Response({
                'status': 'success',
                'message': 'Webhook processed successfully',
                'data': result
            }, status=status.HTTP_200_OK)
        else:
            logger.error(f"Webhook processing failed: {result['error']}")
            return Response({
                'status': 'error',
                'message': result['error']
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook: {e}")
        return Response({
            'status': 'error',
            'message': 'Invalid JSON payload'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return Response({
            'status': 'error',
            'message': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def moralis_webhook_test(request):
    """Test endpoint for Moralis webhook (for development)."""
    # Sample webhook data for testing
    test_webhook_data = {
        'to': '0x742d35Cc6634C0532925a3b8D404d1deBa4Cb61f',
        'from': '0x1234567890123456789012345678901234567890',
        'value': '1000000',  # 1 USDT in Wei (6 decimals)
        'hash': '0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
        'chain': 'eth'
    }
    
    result = real_wallet_service.process_moralis_webhook(test_webhook_data)
    
    return Response({
        'test_webhook_data': test_webhook_data,
        'result': result
    }, status=status.HTTP_200_OK) 