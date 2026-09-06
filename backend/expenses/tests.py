from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from social import services as social_services
from social.models import SharedAccountMember
from wallet.models import Account, AccountCategory, AccountOwnerType
from . import services
from .models import ExpenseEntry, ExpenseShare, ExpenseSplitType, Settlement, SettlementStatus

User = get_user_model()


def make_user(email):
    return User.objects.create_user(username=email.split('@')[0], email=email, password='StrongPass123!')


def make_group(creator, *members, name='Trip Fund'):
    account = social_services.create_shared_group_account(creator=creator, name=name, occasion_name='Goa Trip')
    for m in members:
        SharedAccountMember.objects.create(account=account, user=m)
    return account


class LogExpenseServiceTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice@example.com')
        self.bob = make_user('bob@example.com')
        self.carol = make_user('carol@example.com')
        self.account = make_group(self.alice, self.bob, self.carol)

    def test_equal_split_divides_evenly(self):
        entry = services.log_expense(
            account=self.account, created_by=self.alice, paid_by_id=self.alice.id,
            description='Dinner', amount=Decimal('300.00'), category='food',
            split_type=ExpenseSplitType.EQUAL, expense_date='2026-08-01', note='',
            participant_ids=[self.alice.id, self.bob.id, self.carol.id],
        )
        shares = {s.user_id: s.share_amount for s in entry.shares.all()}
        self.assertEqual(sum(shares.values()), Decimal('300.00'))
        self.assertEqual(shares[self.alice.id], Decimal('100.00'))
        self.assertEqual(shares[self.bob.id], Decimal('100.00'))
        self.assertEqual(shares[self.carol.id], Decimal('100.00'))

    def test_equal_split_distributes_rounding_remainder(self):
        entry = services.log_expense(
            account=self.account, created_by=self.alice, paid_by_id=self.alice.id,
            description='Snacks', amount=Decimal('100.00'), category='food',
            split_type=ExpenseSplitType.EQUAL, expense_date='2026-08-01', note='',
            participant_ids=[self.alice.id, self.bob.id, self.carol.id],
        )
        shares = {s.user_id: s.share_amount for s in entry.shares.all()}
        self.assertEqual(sum(shares.values()), Decimal('100.00'))
        # 100/3 = 33.33 with 0.01 remainder distributed to one participant
        values = sorted(shares.values())
        self.assertEqual(values, [Decimal('33.33'), Decimal('33.33'), Decimal('33.34')])

    def test_exact_split_must_sum_to_total(self):
        with self.assertRaises(ValidationError):
            services.log_expense(
                account=self.account, created_by=self.alice, paid_by_id=self.alice.id,
                description='Cab', amount=Decimal('200.00'), category='travel',
                split_type=ExpenseSplitType.EXACT, expense_date='2026-08-01', note='',
                participant_ids=[self.alice.id, self.bob.id],
                exact_shares={self.alice.id: Decimal('50.00'), self.bob.id: Decimal('100.00')},
            )
        self.assertEqual(ExpenseEntry.objects.count(), 0)

    def test_exact_split_accepts_matching_total(self):
        entry = services.log_expense(
            account=self.account, created_by=self.alice, paid_by_id=self.alice.id,
            description='Cab', amount=Decimal('200.00'), category='travel',
            split_type=ExpenseSplitType.EXACT, expense_date='2026-08-01', note='',
            participant_ids=[self.alice.id, self.bob.id],
            exact_shares={self.alice.id: Decimal('50.00'), self.bob.id: Decimal('150.00')},
        )
        self.assertEqual(entry.shares.count(), 2)

    def test_non_member_cannot_be_payer(self):
        outsider = make_user('dave@example.com')
        with self.assertRaises(ValidationError):
            services.log_expense(
                account=self.account, created_by=self.alice, paid_by_id=outsider.id,
                description='X', amount=Decimal('10.00'), category='other',
                split_type=ExpenseSplitType.EQUAL, expense_date='2026-08-01', note='',
                participant_ids=[self.alice.id, outsider.id],
            )

    def test_participants_must_be_members(self):
        outsider = make_user('dave@example.com')
        with self.assertRaises(ValidationError):
            services.log_expense(
                account=self.account, created_by=self.alice, paid_by_id=self.alice.id,
                description='X', amount=Decimal('10.00'), category='other',
                split_type=ExpenseSplitType.EQUAL, expense_date='2026-08-01', note='',
                participant_ids=[self.alice.id, outsider.id],
            )

    def test_delete_expense_only_by_payer_or_logger(self):
        entry = services.log_expense(
            account=self.account, created_by=self.alice, paid_by_id=self.bob.id,
            description='Snacks', amount=Decimal('50.00'), category='food',
            split_type=ExpenseSplitType.EQUAL, expense_date='2026-08-01', note='',
            participant_ids=[self.bob.id, self.carol.id],
        )
        with self.assertRaises(ValidationError):
            services.delete_expense(expense=entry, requesting_user=self.carol)
        services.delete_expense(expense=entry, requesting_user=self.bob)  # payer may delete
        self.assertEqual(ExpenseEntry.objects.count(), 0)


class SettlementGenerationTests(TestCase):
    """
    Scenario: Alice pays 300 for dinner, split equally among Alice/Bob/Carol (100 each).
    Bob pays 90 for a cab, split equally between Bob/Carol (45 each).

    Net: Alice +200 (paid 300, owes 100), Bob +45 (paid 90, owes 100+45=145 -> net -55... )
    Computed precisely by the service; asserted below via total amounts owed.
    """
    def setUp(self):
        self.alice = make_user('alice@example.com')
        self.bob = make_user('bob@example.com')
        self.carol = make_user('carol@example.com')
        self.account = make_group(self.alice, self.bob, self.carol)

        services.log_expense(
            account=self.account, created_by=self.alice, paid_by_id=self.alice.id,
            description='Dinner', amount=Decimal('300.00'), category='food',
            split_type=ExpenseSplitType.EQUAL, expense_date='2026-08-01', note='',
            participant_ids=[self.alice.id, self.bob.id, self.carol.id],
        )
        services.log_expense(
            account=self.account, created_by=self.bob, paid_by_id=self.bob.id,
            description='Cab', amount=Decimal('90.00'), category='travel',
            split_type=ExpenseSplitType.EQUAL, expense_date='2026-08-02', note='',
            participant_ids=[self.bob.id, self.carol.id],
        )

    def test_net_balances_are_conserved(self):
        balances = services._net_balances(self.account)
        self.assertEqual(sum(balances.values()), Decimal('0.00'))

    def test_generated_settlements_zero_out_balances(self):
        settlements = services.generate_settlements(account=self.account)
        self.assertGreater(len(settlements), 0)
        # Every settlement should be pending and belong to the account
        for s in settlements:
            self.assertEqual(s.status, SettlementStatus.PENDING)
            self.assertEqual(s.account_id, self.account.id)
            self.assertNotEqual(s.payer_id, s.payee_id)

        # Applying all settlements (as if paid) should bring every balance to zero.
        balances = services._net_balances(self.account)
        for s in settlements:
            balances[s.payer_id] += s.amount
            balances[s.payee_id] -= s.amount
        for uid, bal in balances.items():
            self.assertAlmostEqual(float(bal), 0.0, places=2)

    def test_regenerating_settlements_replaces_pending_ones(self):
        first = services.generate_settlements(account=self.account)
        first_ids = {s.id for s in first}
        second = services.generate_settlements(account=self.account)
        second_ids = {s.id for s in second}
        self.assertTrue(first_ids.isdisjoint(second_ids))
        self.assertEqual(Settlement.objects.filter(account=self.account, status=SettlementStatus.PENDING).count(), len(second))

    def test_mark_paid_only_by_payee(self):
        settlements = services.generate_settlements(account=self.account)
        s = settlements[0]
        with self.assertRaises(ValidationError):
            services.mark_settlement_paid(settlement=s, requesting_user=s.payer)
        updated = services.mark_settlement_paid(settlement=s, requesting_user=s.payee)
        self.assertEqual(updated.status, SettlementStatus.PAID)
        self.assertIsNotNone(updated.paid_at)

    def test_paid_settlement_excluded_from_next_generation(self):
        settlements = services.generate_settlements(account=self.account)
        s = settlements[0]
        services.mark_settlement_paid(settlement=s, requesting_user=s.payee)
        regenerated = services.generate_settlements(account=self.account)
        # The paid amount should no longer reappear as an identical pending settlement
        for r in regenerated:
            self.assertFalse(r.payer_id == s.payer_id and r.payee_id == s.payee_id and r.amount == s.amount)


class ExpenseApiTests(APITestCase):
    def setUp(self):
        self.alice = make_user('alice@example.com')
        self.bob = make_user('bob@example.com')
        self.outsider = make_user('dave@example.com')
        self.account = make_group(self.alice, self.bob)

    def auth(self, user):
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_log_expense_via_api(self):
        self.auth(self.alice)
        resp = self.client.post(
            f'/api/expenses/groups/{self.account.id}/expenses/',
            {
                'paid_by': self.alice.id, 'description': 'Groceries', 'amount': '80.00',
                'category': 'food', 'split_type': 'equal', 'expense_date': '2026-08-01',
                'participant_ids': [self.alice.id, self.bob.id],
            }, format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data['shares']), 2)

    def test_non_member_gets_404_not_403(self):
        self.auth(self.outsider)
        resp = self.client.get(f'/api/expenses/groups/{self.account.id}/expenses/')
        self.assertEqual(resp.status_code, 404)

    def test_generate_and_list_settlements(self):
        self.auth(self.alice)
        self.client.post(
            f'/api/expenses/groups/{self.account.id}/expenses/',
            {
                'paid_by': self.alice.id, 'description': 'Groceries', 'amount': '80.00',
                'category': 'food', 'split_type': 'equal', 'expense_date': '2026-08-01',
                'participant_ids': [self.alice.id, self.bob.id],
            }, format='json',
        )
        gen = self.client.post(f'/api/expenses/groups/{self.account.id}/settlements/generate/')
        self.assertEqual(gen.status_code, 201, gen.data)
        self.assertEqual(len(gen.data), 1)
        self.assertEqual(gen.data[0]['payer']['id'], self.bob.id)
        self.assertEqual(gen.data[0]['payee']['id'], self.alice.id)
        self.assertEqual(gen.data[0]['amount'], '40.00')

        listing = self.client.get(f'/api/expenses/groups/{self.account.id}/settlements/')
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.data), 1)

    def test_mark_settlement_paid_via_api_requires_payee(self):
        self.auth(self.alice)
        self.client.post(
            f'/api/expenses/groups/{self.account.id}/expenses/',
            {
                'paid_by': self.alice.id, 'description': 'Groceries', 'amount': '80.00',
                'category': 'food', 'split_type': 'equal', 'expense_date': '2026-08-01',
                'participant_ids': [self.alice.id, self.bob.id],
            }, format='json',
        )
        gen = self.client.post(f'/api/expenses/groups/{self.account.id}/settlements/generate/')
        settlement_id = gen.data[0]['id']

        # Bob is the payer, not the payee — should be rejected.
        self.auth(self.bob)
        bad = self.client.post(f'/api/expenses/groups/{self.account.id}/settlements/{settlement_id}/mark-paid/')
        self.assertEqual(bad.status_code, 400)

        # Alice is the payee — allowed.
        self.auth(self.alice)
        good = self.client.post(f'/api/expenses/groups/{self.account.id}/settlements/{settlement_id}/mark-paid/')
        self.assertEqual(good.status_code, 200)
        self.assertEqual(good.data['status'], 'paid')

    def test_upi_link_uses_payee_upi_id(self):
        self.alice.upi_id = 'alice@okhdfcbank'
        self.alice.save()
        self.auth(self.alice)
        self.client.post(
            f'/api/expenses/groups/{self.account.id}/expenses/',
            {
                'paid_by': self.alice.id, 'description': 'Groceries', 'amount': '80.00',
                'category': 'food', 'split_type': 'equal', 'expense_date': '2026-08-01',
                'participant_ids': [self.alice.id, self.bob.id],
            }, format='json',
        )
        gen = self.client.post(f'/api/expenses/groups/{self.account.id}/settlements/generate/')
        self.assertIn('upi://pay?pa=alice@okhdfcbank', gen.data[0]['upi_link'])

    def test_upi_link_none_without_upi_id(self):
        self.auth(self.alice)
        self.client.post(
            f'/api/expenses/groups/{self.account.id}/expenses/',
            {
                'paid_by': self.alice.id, 'description': 'Groceries', 'amount': '80.00',
                'category': 'food', 'split_type': 'equal', 'expense_date': '2026-08-01',
                'participant_ids': [self.alice.id, self.bob.id],
            }, format='json',
        )
        gen = self.client.post(f'/api/expenses/groups/{self.account.id}/settlements/generate/')
        self.assertIsNone(gen.data[0]['upi_link'])

    def test_delete_expense_via_api(self):
        self.auth(self.alice)
        create = self.client.post(
            f'/api/expenses/groups/{self.account.id}/expenses/',
            {
                'paid_by': self.alice.id, 'description': 'Groceries', 'amount': '80.00',
                'category': 'food', 'split_type': 'equal', 'expense_date': '2026-08-01',
                'participant_ids': [self.alice.id, self.bob.id],
            }, format='json',
        )
        expense_id = create.data['id']
        resp = self.client.delete(f'/api/expenses/groups/{self.account.id}/expenses/{expense_id}/')
        self.assertEqual(resp.status_code, 204)

    def test_shared_pair_account_rejected(self):
        pair = social_services.create_shared_pair_account(creator=self.alice, name='Us')
        SharedAccountMember.objects.create(account=pair, user=self.bob)
        self.auth(self.alice)
        resp = self.client.get(f'/api/expenses/groups/{pair.id}/expenses/')
        self.assertEqual(resp.status_code, 404)
