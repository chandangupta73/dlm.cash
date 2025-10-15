from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import timedelta

from app.transactions.models import Transaction


class Command(BaseCommand):
    help = 'Cleanup and maintain transaction data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days to keep failed transactions (default: 90)'
        )
        parser.add_argument(
            '--status',
            type=str,
            choices=['FAILED', 'PENDING'],
            default='FAILED',
            help='Status of transactions to cleanup (default: FAILED)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        days = options['days']
        status = options['status']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Find transactions to cleanup
        transactions_to_cleanup = Transaction.objects.filter(
            status=status,
            created_at__lt=cutoff_date
        )
        
        count = transactions_to_cleanup.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(f'No {status.lower()} transactions older than {days} days found')
            )
            return
        
        self.stdout.write(
            f'Found {count} {status.lower()} transactions older than {days} days'
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN - No changes will be made')
            )
            
            # Show sample of transactions that would be cleaned up
            sample_transactions = transactions_to_cleanup[:5]
            for tx in sample_transactions:
                self.stdout.write(
                    f'  - {tx.id}: {tx.type} - {tx.currency} {tx.amount} - {tx.created_at.date()}'
                )
            
            if count > 5:
                self.stdout.write(f'  ... and {count - 5} more')
            
            return
        
        # Perform cleanup
        try:
            with transaction.atomic():
                # Archive or delete old failed transactions
                deleted_count = transactions_to_cleanup.delete()[0]
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully cleaned up {deleted_count} {status.lower()} transactions'
                    )
                )
                
                # Show summary
                remaining_failed = Transaction.objects.filter(status=status).count()
                total_transactions = Transaction.objects.count()
                
                self.stdout.write(f'Remaining {status.lower()} transactions: {remaining_failed}')
                self.stdout.write(f'Total transactions: {total_transactions}')
                
        except Exception as e:
            raise CommandError(f"Cleanup failed: {str(e)}")
        
        # Additional maintenance tasks
        self.stdout.write('\nPerforming additional maintenance...')
        
        # Update transaction statistics
        try:
            # Count transactions by status
            status_counts = {}
            for status_choice, _ in Transaction.STATUS_CHOICES:
                status_counts[status_choice] = Transaction.objects.filter(
                    status=status_choice
                ).count()
            
            self.stdout.write('Current transaction status distribution:')
            for status_name, count in status_counts.items():
                self.stdout.write(f'  {status_name}: {count}')
                
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Could not update statistics: {str(e)}')
            )
        
        self.stdout.write(
            self.style.SUCCESS('Transaction cleanup and maintenance completed successfully')
        )
