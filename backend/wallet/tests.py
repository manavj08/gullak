from datetime import datetime, time, timedelta
from decimal import Decimal
import csv
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status

from .models import Account, AccountCategory, Transaction, TransactionType
from . import services

User = get_user_model()


def make_user(email='u@example.com'):
    return User.objects.create_user(username=email.split('@')[0], email=email, password='StrongPass123!')


class GullakAutoCreationTests(TestCase):
    def test_every_new_user_gets_exactly_one_gullak_account(self):
        user = make_user()
        gullak_accounts = Account.objects.filter(user=user, category=AccountCategory.GULLAK)
        self.assertEqual(gullak_accounts.count(), 1)
        self.assertEqual(gullak_accounts.first().unblock_balance, Decimal('0.00'))

    def test_gullak_cannot_be_created_manually_via_serializer(self):
        from .serializers import AccountSerializer
        user = make_user()
        serializer = AccountSerializer(
            data={'name': 'Fake Gullak', 'category': 'gullak', 'account_type': ''},
            context={'request': type('R', (), {'user': user})()},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('category', serializer.errors)

    def test_only_one_gullak_per_user_enforced_at_db_level(self):
        user = make_user()
        with self.assertRaises(Exception):
            Account.objects.create(user=user, name='Second Gullak', category=AccountCategory.GULLAK)


class AccountModelTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_four_non_gullak_categories_have_correct_fields(self):
        daily = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('100.00'), block_balance=Decimal('0.00'),
        )
        self.assertTrue(daily.is_block_capable)

        rev = Account.objects.create(
            user=self.user, name='FD', category=AccountCategory.REVENUE_GENERATION,
            account_type='Fixed Deposit', principal=Decimal('500.00'), current_value=Decimal('520.00'),
        )
        self.assertFalse(rev.is_block_capable)
        self.assertEqual(rev.net_worth_contribution, Decimal('520.00'))

        loan = Account.objects.create(
            user=self.user, name='Credit Card', category=AccountCategory.LOAN_DEBT,
            account_type='Credit Card', credit_limit=Decimal('1000.00'),
            amount_used=Decimal('200.00'), amount_owed=Decimal('200.00'),
        )
        self.assertFalse(loan.is_block_capable)
        self.assertEqual(loan.net_worth_contribution, Decimal('-200.00'))

    def test_decimal_arithmetic_is_exact_no_rounding_drift(self):
        acc = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('100.10'), block_balance=Decimal('0.00'),
        )
        # Repeated small decimal operations should never drift, unlike floats.
        for _ in range(3):
            services.create_transaction(user=self.user, account=acc, type_='expense', amount=Decimal('0.10'))
        acc.refresh_from_db()
        self.assertEqual(acc.unblock_balance, Decimal('99.80'))


class TransactionServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.acc = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('100.00'), block_balance=Decimal('0.00'),
        )
        self.acc2 = Account.objects.create(
            user=self.user, name='Cash', category=AccountCategory.DAILY_TRANSACTION,
            account_type='Cash', unblock_balance=Decimal('0.00'), block_balance=Decimal('0.00'),
        )

    def test_income_increases_unblock(self):
        services.create_transaction(user=self.user, account=self.acc, type_='income', amount=Decimal('5.00'))
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.unblock_balance, Decimal('105.00'))

    def test_expense_decreases_unblock(self):
        services.create_transaction(user=self.user, account=self.acc, type_='expense', amount=Decimal('5.00'))
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.unblock_balance, Decimal('95.00'))

    def test_expense_cannot_exceed_unblock_balance(self):
        with self.assertRaises(ValidationError):
            services.create_transaction(user=self.user, account=self.acc, type_='expense', amount=Decimal('99999.00'))

    def test_cannot_transact_directly_on_gullak(self):
        gullak = services.get_or_create_gullak(self.user)
        with self.assertRaises(ValidationError):
            services.create_transaction(user=self.user, account=gullak, type_='expense', amount=Decimal('5.00'))

    def test_transfer_moves_money_without_creating_or_losing_it(self):
        services.create_transfer(user=self.user, from_account=self.acc, to_account=self.acc2, amount=Decimal('20.00'))
        self.acc.refresh_from_db()
        self.acc2.refresh_from_db()
        self.assertEqual(self.acc.unblock_balance, Decimal('80.00'))
        self.assertEqual(self.acc2.unblock_balance, Decimal('20.00'))
        self.assertEqual(self.acc.unblock_balance + self.acc2.unblock_balance, Decimal('100.00'))

    def test_cannot_transfer_to_or_from_gullak(self):
        gullak = services.get_or_create_gullak(self.user)
        with self.assertRaises(ValidationError):
            services.create_transfer(user=self.user, from_account=self.acc, to_account=gullak, amount=Decimal('5.00'))

    def test_lend_decreases_unblock_borrow_increases(self):
        services.create_transaction(user=self.user, account=self.acc, type_='lend', amount=Decimal('10.00'))
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.unblock_balance, Decimal('90.00'))

        services.create_transaction(user=self.user, account=self.acc, type_='borrow', amount=Decimal('10.00'))
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.unblock_balance, Decimal('100.00'))

    def test_double_submit_with_same_client_request_id_does_not_duplicate(self):
        services.create_transaction(
            user=self.user, account=self.acc, type_='expense', amount=Decimal('1.00'), client_request_id='req-1',
        )
        services.create_transaction(
            user=self.user, account=self.acc, type_='expense', amount=Decimal('1.00'), client_request_id='req-1',
        )
        self.assertEqual(Transaction.objects.filter(client_request_id='req-1').count(), 1)
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.unblock_balance, Decimal('99.00'))  # only deducted once

    def test_settle_lend_does_not_change_balance_history(self):
        txn = services.create_transaction(user=self.user, account=self.acc, type_='lend', amount=Decimal('5.00'))
        self.acc.refresh_from_db()
        balance_after_lend = self.acc.unblock_balance
        txn.settled = True
        txn.save()
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.unblock_balance, balance_after_lend)


class BlockUnblockServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.acc = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('100.00'), block_balance=Decimal('0.00'),
        )
        self.gullak = services.get_or_create_gullak(self.user)

    def test_block_moves_money_from_account_into_gullak(self):
        services.block_funds(user=self.user, account=self.acc, amount=Decimal('30.00'))
        self.acc.refresh_from_db()
        self.gullak.refresh_from_db()
        self.assertEqual(self.acc.unblock_balance, Decimal('70.00'))
        self.assertEqual(self.gullak.unblock_balance, Decimal('30.00'))

    def test_block_creates_linked_transaction_legs(self):
        services.block_funds(user=self.user, account=self.acc, amount=Decimal('30.00'))
        source_leg = Transaction.objects.get(account=self.acc, type=TransactionType.GULLAK_BLOCK)
        gullak_leg = Transaction.objects.get(account=self.gullak, type=TransactionType.GULLAK_BLOCK)
        self.assertEqual(source_leg.transfer_pair_id, gullak_leg.id)
        self.assertEqual(gullak_leg.transfer_pair_id, source_leg.id)

    def test_cannot_block_more_than_unblock_balance(self):
        with self.assertRaises(ValidationError):
            services.block_funds(user=self.user, account=self.acc, amount=Decimal('500.00'))
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.unblock_balance, Decimal('100.00'))  # unchanged

    def test_emergency_unblock_moves_money_back(self):
        services.block_funds(user=self.user, account=self.acc, amount=Decimal('50.00'))
        services.emergency_unblock_funds(user=self.user, account=self.acc, amount=Decimal('20.00'))
        self.acc.refresh_from_db()
        self.gullak.refresh_from_db()
        self.assertEqual(self.acc.unblock_balance, Decimal('70.00'))
        self.assertEqual(self.gullak.unblock_balance, Decimal('30.00'))

    def test_emergency_unblock_within_unallocated_creates_no_pending_deduction(self):
        from goals.models import PendingGoalDeduction
        services.block_funds(user=self.user, account=self.acc, amount=Decimal('50.00'))
        services.emergency_unblock_funds(user=self.user, account=self.acc, amount=Decimal('20.00'))
        self.assertEqual(PendingGoalDeduction.objects.filter(user=self.user, resolved=False).count(), 0)

    def test_emergency_unblock_exceeding_unallocated_auto_deducts_from_goal(self):
        # V2: overage is now deducted automatically (proportionally) rather than left
        # for manual resolution — see goals.tests.AutoApplyDeductionTests for full coverage.
        from goals.models import Goal, PendingGoalDeduction
        from goals import services as goal_services
        services.block_funds(user=self.user, account=self.acc, amount=Decimal('50.00'))
        goal = Goal.objects.create(user=self.user, name='Trip', target_amount=Decimal('1000.00'))
        goal_services.add_funds_to_goal(user=self.user, goal=goal, add_amount=Decimal('40.00'))
        # Gullak = 50, allocated = 40, unallocated = 10. Unblocking 25 exceeds unallocated by 15.
        services.emergency_unblock_funds(user=self.user, account=self.acc, amount=Decimal('25.00'))
        record = PendingGoalDeduction.objects.filter(user=self.user).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.amount, Decimal('15.00'))
        self.assertTrue(record.resolved)  # pre-resolved: auto-applied, informational only
        goal.refresh_from_db()
        self.assertEqual(goal.allocated_amount, Decimal('25.00'))  # 40 - 15, applied automatically


class GullakComputationTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_gullak_total_is_the_gullak_accounts_own_balance(self):
        acc = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('50.00'), block_balance=Decimal('0.00'),
        )
        self.assertEqual(services.compute_gullak_total(self.user), Decimal('0.00'))
        services.block_funds(user=self.user, account=acc, amount=Decimal('20.00'))
        self.assertEqual(services.compute_gullak_total(self.user), Decimal('20.00'))

    def test_net_worth_includes_gullak_and_excludes_double_counting(self):
        acc = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('50.00'), block_balance=Decimal('0.00'),
        )
        services.block_funds(user=self.user, account=acc, amount=Decimal('20.00'))
        # acc now has 30 unblock, Gullak has 20 -> total net worth should be 50, not 70.
        self.assertEqual(services.compute_net_worth(self.user), Decimal('50.00'))


class EmptyStateAPITests(APITestCase):
    def test_new_user_sees_empty_lists_not_errors(self):
        user = make_user()
        self.client.force_authenticate(user)
        resp = self.client.get(reverse('account-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        resp = self.client.get(reverse('gullak_summary'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(resp.data['gullak_total']), Decimal('0.00'))

    def test_new_user_account_list_includes_auto_created_gullak(self):
        user = make_user()
        self.client.force_authenticate(user)
        resp = self.client.get(reverse('account-list'))
        categories = [a['category'] for a in resp.data['results']]
        self.assertIn('gullak', categories)


class TransactionAPIRoutingTests(APITestCase):
    """Regression test: /transactions/create/ and /transactions/transfer/ must not be
    shadowed by the DefaultRouter's /transactions/<pk>/ pattern."""

    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.acc = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('100.00'), block_balance=Decimal('0.00'),
        )
        self.acc2 = Account.objects.create(
            user=self.user, name='Cash', category=AccountCategory.DAILY_TRANSACTION,
            account_type='Cash', unblock_balance=Decimal('0.00'), block_balance=Decimal('0.00'),
        )

    def test_create_transaction_endpoint_allows_post(self):
        resp = self.client.post(reverse('transaction_create'), {
            'account': self.acc.id, 'type': 'expense', 'amount': '5.00', 'category': 'food',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_transfer_endpoint_allows_post(self):
        resp = self.client.post(reverse('transaction_transfer'), {
            'from_account': self.acc.id, 'to_account': self.acc2.id, 'amount': '5.00',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)


class GullakLegExclusionAPITests(APITestCase):
    """Gullak block/unblock legs must not appear in the general transaction list, but must
    appear when explicitly requested (used by the Gullak account's own detail page)."""

    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.acc = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('100.00'), block_balance=Decimal('0.00'),
        )
        services.block_funds(user=self.user, account=self.acc, amount=Decimal('30.00'))
        services.create_transaction(user=self.user, account=self.acc, type_='expense', amount=Decimal('5.00'))

    def test_general_list_excludes_gullak_legs_by_default(self):
        resp = self.client.get(reverse('transaction-list'))
        types = [t['type'] for t in resp.data['results']]
        self.assertNotIn('gullak_block', types)
        self.assertIn('expense', types)

    def test_include_gullak_param_shows_them(self):
        resp = self.client.get(reverse('transaction-list'), {'include_gullak': 'true'})
        types = [t['type'] for t in resp.data['results']]
        self.assertIn('gullak_block', types)


# ================================================================================
# Analytics: Net Worth Over Time & Spend by Category
# ================================================================================

class NetWorthHistoryTests(TestCase):
    def setUp(self):
        self.user = make_user('nwhistory@example.com')
        self.account = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('1000.00'), block_balance=Decimal('0.00'),
        )

    def _backdate(self, txn, day):
        at = timezone.make_aware(datetime.combine(day, time(12, 0)))
        Transaction.objects.filter(pk=txn.pk).update(timestamp=at)

    def test_flat_history_when_no_transactions_exist(self):
        current = services.compute_net_worth(self.user)
        history = services.net_worth_history(self.user, days=5)
        self.assertEqual(len(history), 5)
        self.assertTrue(all(h['net_worth'] == current for h in history))

    def test_oldest_first_ordering_and_date_range(self):
        history = services.net_worth_history(self.user, days=5)
        dates = [h['date'] for h in history]
        self.assertEqual(dates, sorted(dates))
        today = timezone.localdate()
        self.assertEqual(dates[-1], today.isoformat())
        self.assertEqual(dates[0], (today - timedelta(days=4)).isoformat())

    def test_expense_today_raises_reconstructed_past_net_worth(self):
        txn = services.create_transaction(
            user=self.user, account=self.account, type_='expense', amount=Decimal('100.00'),
        )
        current = services.compute_net_worth(self.user)  # 900.00
        history = services.net_worth_history(self.user, days=3)
        by_date = {h['date']: h['net_worth'] for h in history}
        today = timezone.localdate().isoformat()
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        self.assertEqual(by_date[today], current)
        self.assertEqual(by_date[yesterday], current + Decimal('100.00'))

    def test_income_today_lowers_reconstructed_past_net_worth(self):
        txn = services.create_transaction(
            user=self.user, account=self.account, type_='income', amount=Decimal('200.00'),
        )
        current = services.compute_net_worth(self.user)  # 1200.00
        history = services.net_worth_history(self.user, days=3)
        by_date = {h['date']: h['net_worth'] for h in history}
        today = timezone.localdate().isoformat()
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        self.assertEqual(by_date[today], current)
        self.assertEqual(by_date[yesterday], current - Decimal('200.00'))

    def test_backdated_expense_only_affects_dates_before_it(self):
        txn = services.create_transaction(
            user=self.user, account=self.account, type_='expense', amount=Decimal('50.00'),
        )
        self._backdate(txn, timezone.localdate() - timedelta(days=2))
        history = services.net_worth_history(self.user, days=5)
        by_date = {h['date']: h['net_worth'] for h in history}
        current = services.compute_net_worth(self.user)  # 950.00
        today = timezone.localdate()
        # On and after the transaction date: reflects the expense already happened.
        self.assertEqual(by_date[today.isoformat()], current)
        self.assertEqual(by_date[(today - timedelta(days=2)).isoformat()], current)
        # Before the transaction date: expense hadn't happened yet, net worth was higher.
        self.assertEqual(by_date[(today - timedelta(days=3)).isoformat()], current + Decimal('50.00'))
        self.assertEqual(by_date[(today - timedelta(days=4)).isoformat()], current + Decimal('50.00'))

    def test_transfer_between_own_accounts_does_not_change_history(self):
        other = Account.objects.create(
            user=self.user, name='Cash', category=AccountCategory.DAILY_TRANSACTION,
            account_type='Cash', unblock_balance=Decimal('500.00'), block_balance=Decimal('0.00'),
        )
        before = services.compute_net_worth(self.user)
        services.create_transfer(user=self.user, from_account=self.account, to_account=other, amount=Decimal('100.00'))
        after = services.compute_net_worth(self.user)
        self.assertEqual(before, after)  # sanity: transfer doesn't change total
        history = services.net_worth_history(self.user, days=3)
        self.assertTrue(all(h['net_worth'] == after for h in history))

    def test_revenue_generation_and_loan_debt_held_constant(self):
        Account.objects.create(
            user=self.user, name='Mutual Fund', category=AccountCategory.REVENUE_GENERATION,
            account_type='Mutual Fund', principal=Decimal('1000.00'), current_value=Decimal('1200.00'),
        )
        Account.objects.create(
            user=self.user, name='Credit Card', category=AccountCategory.LOAN_DEBT,
            account_type='Credit Card', amount_owed=Decimal('300.00'),
        )
        current = services.compute_net_worth(self.user)  # 1000 (daily) + 1200 (RG) - 300 (loan) = 1900
        self.assertEqual(current, Decimal('1900.00'))
        history = services.net_worth_history(self.user, days=4)
        self.assertTrue(all(h['net_worth'] == current for h in history))

    def test_days_parameter_controls_result_length(self):
        self.assertEqual(len(services.net_worth_history(self.user, days=10)), 10)
        self.assertEqual(len(services.net_worth_history(self.user, days=1)), 1)


class SpendByCategoryTests(TestCase):
    def setUp(self):
        self.user = make_user('spendcat@example.com')
        self.account = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('5000.00'), block_balance=Decimal('0.00'),
        )

    def _backdate(self, txn, day):
        at = timezone.make_aware(datetime.combine(day, time(12, 0)))
        Transaction.objects.filter(pk=txn.pk).update(timestamp=at)

    def test_aggregates_expenses_by_category(self):
        services.create_transaction(
            user=self.user, account=self.account, type_='expense', amount=Decimal('300.00'), category='food',
        )
        services.create_transaction(
            user=self.user, account=self.account, type_='expense', amount=Decimal('200.00'), category='food',
        )
        services.create_transaction(
            user=self.user, account=self.account, type_='expense', amount=Decimal('150.00'), category='transport',
        )
        result = services.spend_by_category(self.user, days=30)
        by_category = {r['category']: r['amount'] for r in result}
        self.assertEqual(by_category['Food'], Decimal('500.00'))
        self.assertEqual(by_category['Transport'], Decimal('150.00'))

    def test_orders_largest_first(self):
        services.create_transaction(
            user=self.user, account=self.account, type_='expense', amount=Decimal('50.00'), category='bills',
        )
        services.create_transaction(
            user=self.user, account=self.account, type_='expense', amount=Decimal('500.00'), category='shopping',
        )
        result = services.spend_by_category(self.user, days=30)
        self.assertEqual(result[0]['category'], 'Shopping')

    def test_categories_with_no_spending_are_omitted(self):
        services.create_transaction(
            user=self.user, account=self.account, type_='expense', amount=Decimal('100.00'), category='food',
        )
        result = services.spend_by_category(self.user, days=30)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['category'], 'Food')

    def test_income_and_lend_are_not_counted_as_spend(self):
        services.create_transaction(
            user=self.user, account=self.account, type_='income', amount=Decimal('1000.00'), category='other',
        )
        services.create_transaction(
            user=self.user, account=self.account, type_='lend', amount=Decimal('200.00'), category='other',
        )
        result = services.spend_by_category(self.user, days=30)
        self.assertEqual(result, [])

    def test_outside_the_day_window_is_excluded(self):
        txn = services.create_transaction(
            user=self.user, account=self.account, type_='expense', amount=Decimal('999.00'), category='food',
        )
        self._backdate(txn, timezone.localdate() - timedelta(days=40))
        result = services.spend_by_category(self.user, days=30)
        self.assertEqual(result, [])


class AnalyticsApiTests(APITestCase):
    def setUp(self):
        self.user = make_user('analyticsapi@example.com')
        self.client.force_authenticate(self.user)
        self.account = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('1000.00'), block_balance=Decimal('0.00'),
        )

    def test_net_worth_history_endpoint(self):
        response = self.client.get(reverse('net_worth_history'), {'days': 7})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 7)
        self.assertIn('date', response.data[0])
        self.assertIn('net_worth', response.data[0])

    def test_spend_by_category_endpoint(self):
        services.create_transaction(
            user=self.user, account=self.account, type_='expense', amount=Decimal('250.00'), category='food',
        )
        response = self.client.get(reverse('spend_by_category'), {'days': 30})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [{'category': 'Food', 'amount': Decimal('250.00')}])

    def test_days_param_is_clamped_to_a_sane_range(self):
        response = self.client.get(reverse('net_worth_history'), {'days': 99999})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data), 365)

    def test_invalid_days_param_falls_back_to_default(self):
        response = self.client.get(reverse('net_worth_history'), {'days': 'not-a-number'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 30)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        response = self.client.get(reverse('net_worth_history'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_analytics_only_reflects_the_requesting_users_data(self):
        other = make_user('otheruser@example.com')
        Account.objects.create(
            user=other, name='Other UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('99999.00'), block_balance=Decimal('0.00'),
        )
        response = self.client.get(reverse('net_worth_history'), {'days': 1})
        self.assertEqual(response.data[0]['net_worth'], Decimal('1000.00'))


# ================================================================================
# Transaction CSV Export
# ================================================================================

class TransactionExportTests(APITestCase):
    def setUp(self):
        self.user = make_user('csvexport@example.com')
        self.client.force_authenticate(self.user)
        self.account = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('5000.00'), block_balance=Decimal('0.00'),
        )

    def _rows(self, response):
        content = response.content.decode('utf-8')
        return list(csv.reader(content.splitlines()))

    def test_returns_csv_content_type_and_attachment_header(self):
        response = self.client.get(reverse('transaction_export'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="gullak_transactions_', response['Content-Disposition'])

    def test_header_row_matches_required_columns(self):
        response = self.client.get(reverse('transaction_export'))
        rows = self._rows(response)
        self.assertEqual(rows[0], ['Date', 'Type', 'Category', 'Amount', 'Account', 'Description'])

    def test_exports_transaction_data_correctly(self):
        services.create_transaction(
            user=self.user, account=self.account, type_='expense', amount=Decimal('250.00'),
            category='food', note='Lunch',
        )
        response = self.client.get(reverse('transaction_export'))
        rows = self._rows(response)
        self.assertEqual(len(rows), 2)  # header + 1 transaction
        date, type_, category, amount, account_name, note = rows[1]
        self.assertEqual(type_, 'Expense')
        self.assertEqual(category, 'Food')
        self.assertEqual(amount, '250.00')
        self.assertEqual(account_name, 'UPI')
        self.assertEqual(note, 'Lunch')

    def test_excludes_gullak_legs_by_default(self):
        gullak = services.get_or_create_gullak(self.user)
        services.block_funds(user=self.user, account=self.account, amount=Decimal('100.00'))
        response = self.client.get(reverse('transaction_export'))
        rows = self._rows(response)
        types = [r[1] for r in rows[1:]]
        self.assertNotIn('Gullak Block', types)

    def test_include_gullak_param_includes_gullak_legs(self):
        services.block_funds(user=self.user, account=self.account, amount=Decimal('100.00'))
        response = self.client.get(reverse('transaction_export'), {'include_gullak': 'true'})
        rows = self._rows(response)
        self.assertGreater(len(rows), 1)

    def test_type_filter_is_respected(self):
        services.create_transaction(
            user=self.user, account=self.account, type_='expense', amount=Decimal('100.00'), category='food',
        )
        services.create_transaction(
            user=self.user, account=self.account, type_='income', amount=Decimal('500.00'), category='other',
        )
        response = self.client.get(reverse('transaction_export'), {'type': 'income'})
        rows = self._rows(response)
        self.assertEqual(len(rows), 2)  # header + 1 income row
        self.assertEqual(rows[1][1], 'Income')

    def test_only_exports_the_requesting_users_own_transactions(self):
        other = make_user('otherexport@example.com')
        other_account = Account.objects.create(
            user=other, name='Other', category=AccountCategory.DAILY_TRANSACTION,
            account_type='Cash', unblock_balance=Decimal('1000.00'), block_balance=Decimal('0.00'),
        )
        services.create_transaction(
            user=other, account=other_account, type_='expense', amount=Decimal('999.00'), category='food',
        )
        response = self.client.get(reverse('transaction_export'))
        rows = self._rows(response)
        self.assertEqual(len(rows), 1)  # header only, nothing from the other user

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        response = self.client.get(reverse('transaction_export'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_export_still_returns_header_row(self):
        response = self.client.get(reverse('transaction_export'))
        rows = self._rows(response)
        self.assertEqual(len(rows), 1)
