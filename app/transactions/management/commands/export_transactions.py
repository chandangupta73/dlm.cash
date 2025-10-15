from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import models
from decimal import Decimal
import csv
import os
from datetime import datetime, timedelta

from app.transactions.models import Transaction
from app.transactions.services import TransactionService

User = get_user_model()


class Command(BaseCommand):
    help = 'Export transactions to CSV file with optional filtering'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default=None,
            help='Output file path (default: transactions_YYYYMMDD_HHMMSS.csv)'
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Filter by username'
        )
        parser.add_argument(
            '--type',
            type=str,
            help='Filter by transaction type'
        )
        parser.add_argument(
            '--currency',
            type=str,
            help='Filter by currency (INR or USDT)'
        )
        parser.add_argument(
            '--status',
            type=str,
            help='Filter by transaction status'
        )
        parser.add_argument(
            '--date-from',
            type=str,
            help='Filter from date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--date-to',
            type=str,
            help='Filter to date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--min-amount',
            type=Decimal,
            help='Minimum transaction amount'
        )
        parser.add_argument(
            '--max-amount',
            type=Decimal,
            help='Maximum transaction amount'
        )

    def handle(self, *args, **options):
        try:
            # Build filters
            filters = {}
            
            if options['user']:
                try:
                    user = User.objects.get(username=options['user'])
                    filters['user'] = user
                except User.DoesNotExist:
                    raise CommandError(f"User '{options['user']}' not found")
            
            if options['type']:
                if options['type'] not in [choice[0] for choice in Transaction.TRANSACTION_TYPE_CHOICES]:
                    raise CommandError(f"Invalid transaction type: {options['type']}")
                filters['type'] = options['type']
            
            if options['currency']:
                if options['currency'] not in [choice[0] for choice in Transaction.CURRENCY_CHOICES]:
                    raise CommandError(f"Invalid currency: {options['currency']}")
                filters['currency'] = options['currency']
            
            if options['status']:
                if options['status'] not in [choice[0] for choice in Transaction.STATUS_CHOICES]:
                    raise CommandError(f"Invalid status: {options['status']}")
                filters['status'] = options['status']
            
            if options['date_from']:
                try:
                    filters['date_from'] = datetime.strptime(options['date_from'], '%Y-%m-%d').date()
                except ValueError:
                    raise CommandError("Invalid date format. Use YYYY-MM-DD")
            
            if options['date_to']:
                try:
                    filters['date_to'] = datetime.strptime(options['date_to'], '%Y-%m-%d').date()
                except ValueError:
                    raise CommandError("Invalid date format. Use YYYY-MM-DD")
            
            if options['min_amount']:
                filters['min_amount'] = options['min_amount']
            
            if options['max_amount']:
                filters['max_amount'] = options['max_amount']
            
            # Get output file path
            if options['output']:
                output_path = options['output']
            else:
                timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                output_path = f"transactions_{timestamp}.csv"
            
            # Get transactions with filters
            queryset = Transaction.objects.select_related('user')
            
            if filters.get('user'):
                queryset = queryset.filter(user=filters['user'])
            
            if filters.get('type'):
                queryset = queryset.filter(type=filters['type'])
            
            if filters.get('currency'):
                queryset = queryset.filter(currency=filters['currency'])
            
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            
            if filters.get('date_from'):
                queryset = queryset.filter(created_at__date__gte=filters['date_from'])
            
            if filters.get('date_to'):
                queryset = queryset.filter(created_at__date__lte=filters['date_to'])
            
            if filters.get('min_amount'):
                queryset = queryset.filter(amount__gte=filters['min_amount'])
            
            if filters.get('max_amount'):
                queryset = queryset.filter(amount__lte=filters['max_amount'])
            
            # Export to CSV
            total_transactions = queryset.count()
            
            if total_transactions == 0:
                self.stdout.write(
                    self.style.WARNING('No transactions found matching the specified criteria')
                )
                return
            
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow([
                    'Transaction ID',
                    'Username',
                    'Email',
                    'Type',
                    'Currency',
                    'Amount',
                    'Status',
                    'Reference ID',
                    'Created At',
                    'Updated At'
                ])
                
                # Write data rows
                for transaction in queryset:
                    writer.writerow([
                        str(transaction.id),
                        transaction.user.username,
                        transaction.user.email,
                        transaction.get_type_display(),
                        transaction.get_currency_display(),
                        str(transaction.amount),
                        transaction.get_status_display(),
                        transaction.reference_id or '',
                        transaction.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        transaction.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                    ])
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully exported {total_transactions} transactions to {output_path}'
                )
            )
            
            # Show summary
            total_volume = queryset.aggregate(
                total=Decimal('0') + queryset.aggregate(total=models.Sum('amount'))['total']
            )['total'] or Decimal('0')
            
            self.stdout.write(f'Total volume: {total_volume}')
            
        except Exception as e:
            raise CommandError(f"Export failed: {str(e)}")
