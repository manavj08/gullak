import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone

from wallet.models import Account, AccountCategory, Transaction
from wallet import services as wallet_services
from goals.models import Goal
from goals import services as goal_services
from streaks import services as streak_services
from social import services as social_services

User = get_user_model()

DEMO_EMAIL = 'demo@gullak.app'
DEMO_PASSWORD = 'Demo@12345'
DEMO2_EMAIL = 'demo2@gullak.app'
DEMO2_USERNAME = 'demo_friend'
DEMO2_PASSWORD = 'Demo@12345'


def _backdate(txn: Transaction, day: date):
    """
    Transaction.timestamp uses auto_now_add, so it can't be set through the
    normal create()/save() path (by design — real transactions should always
    be timestamped 'now'). For demo data only, backdate it via a raw
    QuerySet.update(), which bypasses auto_now_add since it doesn't go
    through Model.save(). This only affects this seed command — the
    Transaction model and the real create-transaction flow are untouched —
    and it's what gives the "Net Worth Over Time" / "Spend by Category"
    demo charts a realistic multi-day shape instead of everything landing
    on the moment the seed command was run.
    """
    at = timezone.make_aware(datetime.combine(day, time(hour=random.randint(8, 21), minute=random.randint(0, 59))))
    Transaction.objects.filter(pk=txn.pk).update(timestamp=at)


class Command(BaseCommand):
    help = "Seeds the database with demo users and realistic fictional financial data, including a V2 shared account."

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete existing demo users first.')

    @db_transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            User.objects.filter(email__in=[DEMO_EMAIL, DEMO2_EMAIL]).delete()

        if User.objects.filter(email=DEMO_EMAIL).exists():
            self.stdout.write(self.style.WARNING(f'Demo user {DEMO_EMAIL} already exists. Use --reset to recreate.'))
            return

        user = User.objects.create_user(
            username='demo_student', email=DEMO_EMAIL, phone='+919812345678', password=DEMO_PASSWORD,
        )
        user.set_mpin('1234')
        user.save()
        # Gullak account was auto-created by the post_save signal — no need to create it here.

        # V2: a second demo user, used to demonstrate the shared-account invite/accept flow
        # and the aggregate-only visibility rule out of the box.
        friend = User.objects.create_user(
            username=DEMO2_USERNAME, email=DEMO2_EMAIL, phone='+919812345679', password=DEMO2_PASSWORD,
        )
        friend.set_mpin('1234')
        friend.save()

        upi = Account.objects.create(
            user=user, name='PhonePe UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('4500.00'), block_balance=Decimal('0.00'),
        )
        cash = Account.objects.create(
            user=user, name='Cash Wallet', category=AccountCategory.DAILY_TRANSACTION,
            account_type='Cash', unblock_balance=Decimal('800.00'), block_balance=Decimal('0.00'),
        )
        savings = Account.objects.create(
            user=user, name='SBI Savings', category=AccountCategory.SAVINGS,
            account_type='Savings Account', unblock_balance=Decimal('15000.00'), block_balance=Decimal('0.00'),
        )
        Account.objects.create(
            user=user, name='ICICI Mutual Fund', category=AccountCategory.REVENUE_GENERATION,
            account_type='Mutual Fund', principal=Decimal('20000.00'), current_value=Decimal('22100.00'),
        )
        Account.objects.create(
            user=user, name='HDFC Credit Card', category=AccountCategory.LOAN_DEBT,
            account_type='Credit Card', credit_limit=Decimal('50000.00'),
            amount_used=Decimal('8500.00'), amount_owed=Decimal('8500.00'),
            due_date=date.today() + timedelta(days=12),
        )

        # Block some money into Gullak from savings + UPI
        wallet_services.block_funds(user=user, account=savings, amount=Decimal('3000.00'))
        wallet_services.block_funds(user=user, account=upi, amount=Decimal('500.00'))

        # Realistic transaction history over the last 14 days
        categories = ['food', 'transport', 'bills', 'shopping', 'other']
        notes = {
            'food': ['Campus canteen', 'Zomato order', 'Chai and snacks'],
            'transport': ['Auto fare', 'Metro recharge', 'Petrol'],
            'bills': ['Mobile recharge', 'Electricity bill', 'Wifi bill'],
            'shopping': ['Amazon order', 'Stationery', 'Clothes'],
            'other': ['Movie tickets', 'Gift', 'Miscellaneous'],
        }
        today = date.today()
        for i in range(14, 0, -1):
            day = today - timedelta(days=i)
            if random.random() < 0.85:  # most days have activity
                cat = random.choice(categories)
                amount = Decimal(random.randint(30, 150))  # ₹30 - ₹150
                account = random.choice([upi, cash])
                account.refresh_from_db()
                if amount > account.unblock_balance:
                    account = upi
                    account.refresh_from_db()
                if amount > account.unblock_balance:
                    streak_services.record_check_in(user=user, local_date=day, is_manual=True)
                    continue
                txn = wallet_services.create_transaction(
                    user=user, account=account, type_='expense', amount=amount,
                    category=cat, note=random.choice(notes[cat]),
                )
                _backdate(txn, day)
                streak_services.record_check_in(user=user, local_date=day, had_transaction=True)
            else:
                streak_services.record_check_in(user=user, local_date=day, is_manual=True)

        # A couple of income entries
        allowance_txn = wallet_services.create_transaction(
            user=user, account=savings, type_='income', amount=Decimal('10000.00'),
            category='other', note='Monthly allowance',
        )
        _backdate(allowance_txn, today - timedelta(days=12))
        borrow_txn = wallet_services.create_transaction(
            user=user, account=upi, type_='borrow', amount=Decimal('500.00'),
            category='other', note='Borrowed from roommate',
        )
        _backdate(borrow_txn, today - timedelta(days=6))

        # Goals
        goal1 = Goal.objects.create(user=user, name='New Laptop', target_amount=Decimal('60000.00'),
                                     deadline=today + timedelta(days=180))
        goal_services.add_funds_to_goal(user=user, goal=goal1, add_amount=Decimal('2000.00'))

        goal2 = Goal.objects.create(user=user, name='Goa Trip', target_amount=Decimal('15000.00'),
                                     deadline=today + timedelta(days=90))
        goal_services.add_funds_to_goal(user=user, goal=goal2, add_amount=Decimal('1000.00'))

        streak_services.record_check_in(user=user, local_date=today, had_transaction=False, is_manual=True)

        # ---- V2: give the friend a spendable account of their own, then demo the ----
        # ---- shared-account flow: create, invite, accept, contribute, and a common goal. ----
        friend_upi = Account.objects.create(
            user=friend, name='GPay UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('6000.00'), block_balance=Decimal('0.00'),
        )

        shared_account = social_services.create_shared_group_account(
            creator=user, name='Goa Trip Squad', occasion_name='Goa Trip Fund',
            occasion_date=today + timedelta(days=75), reminder_enabled=True,
        )
        invite = social_services.send_invite(inviter=user, invited_username=DEMO2_USERNAME, account=shared_account)
        social_services.respond_to_invite(user=friend, invite=invite, accept=True)

        wallet_services.contribute_to_shared_account(
            user=user, from_account=savings, shared_account=shared_account, amount=Decimal('4000.00'),
        )
        wallet_services.contribute_to_shared_account(
            user=friend, from_account=friend_upi, shared_account=shared_account, amount=Decimal('2500.00'),
        )

        common_goal = Goal.objects.create(
            user=user, name='Goa Trip (shared)', target_amount=Decimal('20000.00'),
            deadline=today + timedelta(days=75), funding_shared_account_id=shared_account.id,
        )
        goal_services.add_funds_to_goal(user=user, goal=common_goal, add_amount=Decimal('5000.00'))

        self.stdout.write(self.style.SUCCESS(
            f'Demo data created.\n'
            f'  User 1 — Email: {DEMO_EMAIL}  Password: {DEMO_PASSWORD}  MPIN: 1234\n'
            f'  User 2 — Email: {DEMO2_EMAIL}  Password: {DEMO2_PASSWORD}  MPIN: 1234  (username: {DEMO2_USERNAME})\n'
            f'  Shared group account "Goa Trip Squad" already set up between them — '
            f'log in as either to see it under Shared accounts.'
        ))
