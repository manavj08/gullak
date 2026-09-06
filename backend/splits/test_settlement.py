"""
Tests for splits.services.settlement — the settlement mathematics module.

Split into two kinds of tests:
  * Pure-function tests (SplitMathTests, PairwiseNettingTests,
    GlobalSimplificationTests) that call settlement.py directly with plain
    Python values — no database, fast, and the most direct check of the
    rounding rule and netting/simplification algorithms.
  * Integration tests (SettlementIntegrationTests, ShowCalculationTests)
    that exercise the same math through real groups/expenses/settlements,
    confirming the DB-bound wiring (services.generate_settlements,
    services.explain_settlement, etc.) matches the pure functions.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from . import services
from .models import SettlementMode, SettlementStatus, SplitType
from .services import settlement as settlement_service
from .tests import make_group, make_user

User = get_user_model()


# ================================================================================
# Split-type share math (pure functions)
# ================================================================================

class EqualSplitMathTests(TestCase):
    def test_divides_evenly_when_it_divides_evenly(self):
        shares = settlement_service.equal_shares(Decimal('300.00'), [1, 2, 3])
        self.assertEqual(shares, {1: Decimal('100.00'), 2: Decimal('100.00'), 3: Decimal('100.00')})

    def test_100_over_3(self):
        shares = settlement_service.equal_shares(Decimal('100.00'), [1, 2, 3])
        self.assertEqual(sum(shares.values()), Decimal('100.00'))
        self.assertEqual(sorted(shares.values()), [Decimal('33.33'), Decimal('33.33'), Decimal('33.34')])
        # Consistent rule: lowest user id absorbs the extra paisa first.
        self.assertEqual(shares[1], Decimal('33.34'))

    def test_100_over_6(self):
        shares = settlement_service.equal_shares(Decimal('100.00'), [1, 2, 3, 4, 5, 6])
        self.assertEqual(sum(shares.values()), Decimal('100.00'))
        self.assertEqual(sorted(shares.values(), reverse=True), [Decimal('16.67')] * 4 + [Decimal('16.66')] * 2)

    def test_10_over_3(self):
        shares = settlement_service.equal_shares(Decimal('10.00'), [1, 2, 3])
        self.assertEqual(sum(shares.values()), Decimal('10.00'))
        self.assertEqual(sorted(shares.values()), [Decimal('3.33'), Decimal('3.33'), Decimal('3.34')])

    def test_one_paisa_over_3(self):
        shares = settlement_service.equal_shares(Decimal('0.01'), [1, 2, 3])
        self.assertEqual(sum(shares.values()), Decimal('0.01'))
        self.assertEqual(sorted(shares.values()), [Decimal('0.00'), Decimal('0.00'), Decimal('0.01')])
        self.assertEqual(shares[1], Decimal('0.01'))  # lowest id gets the only paisa

    def test_empty_participant_list_returns_empty(self):
        self.assertEqual(settlement_service.equal_shares(Decimal('100.00'), []), {})

    def test_single_participant_gets_everything(self):
        shares = settlement_service.equal_shares(Decimal('47.23'), [9])
        self.assertEqual(shares, {9: Decimal('47.23')})

    def test_remainder_never_exceeds_participant_count(self):
        # Sweep a range of awkward amounts/participant counts and confirm the
        # invariant (sum of shares == total) always holds, regardless of rounding.
        for cents in [1, 7, 99, 100, 101, 12345, 99999]:
            amount = Decimal(cents) * settlement_service.CENT
            for n in range(1, 8):
                participants = list(range(1, n + 1))
                shares = settlement_service.equal_shares(amount, participants)
                self.assertEqual(sum(shares.values()), amount, f'amount={amount} n={n}')
                self.assertEqual(len(shares), n)


class CustomSplitMathTests(TestCase):
    def test_accepts_exact_amounts_summing_to_total(self):
        shares = settlement_service.custom_shares(
            Decimal('200.00'), [1, 2], {1: Decimal('50.00'), 2: Decimal('150.00')},
        )
        self.assertEqual(shares, {1: Decimal('50.00'), 2: Decimal('150.00')})

    def test_rejects_total_mismatch(self):
        with self.assertRaises(ValidationError):
            settlement_service.custom_shares(
                Decimal('200.00'), [1, 2], {1: Decimal('50.00'), 2: Decimal('100.00')},
            )

    def test_rejects_missing_participant(self):
        with self.assertRaises(ValidationError):
            settlement_service.custom_shares(Decimal('200.00'), [1, 2], {1: Decimal('200.00')})

    def test_rejects_negative_share(self):
        with self.assertRaises(ValidationError):
            settlement_service.custom_shares(
                Decimal('200.00'), [1, 2], {1: Decimal('-10.00'), 2: Decimal('210.00')},
            )

    def test_rejects_empty_input(self):
        with self.assertRaises(ValidationError):
            settlement_service.custom_shares(Decimal('200.00'), [1, 2], {})


class PercentageSplitMathTests(TestCase):
    def test_accepts_percentages_summing_to_100(self):
        shares, pcts = settlement_service.percentage_shares(
            Decimal('200.00'), [1, 2], {1: Decimal('25'), 2: Decimal('75')},
        )
        self.assertEqual(shares, {1: Decimal('50.00'), 2: Decimal('150.00')})
        self.assertEqual(pcts, {1: Decimal('25'), 2: Decimal('75')})

    def test_rejects_percentages_not_summing_to_100(self):
        with self.assertRaises(ValidationError):
            settlement_service.percentage_shares(
                Decimal('90.00'), [1, 2], {1: Decimal('60'), 2: Decimal('30')},
            )

    def test_handles_rounding_and_sums_to_total(self):
        # 34/33/33 of ₹100 -> 34.00/33.00/33.00, sums exactly.
        shares, _ = settlement_service.percentage_shares(
            Decimal('100.00'), [1, 2, 3], {1: Decimal('34'), 2: Decimal('33'), 3: Decimal('33')},
        )
        self.assertEqual(sum(shares.values()), Decimal('100.00'))
        self.assertEqual(shares[1], Decimal('34.00'))

    def test_awkward_percentages_still_sum_exactly(self):
        # 33.33/33.33/33.34 of ₹10 - each raw share rounds down, remainder distributed.
        shares, _ = settlement_service.percentage_shares(
            Decimal('10.00'), [1, 2, 3], {1: Decimal('33.33'), 2: Decimal('33.33'), 3: Decimal('33.34')},
        )
        self.assertEqual(sum(shares.values()), Decimal('10.00'))

    def test_rejects_negative_percentage(self):
        with self.assertRaises(ValidationError):
            settlement_service.percentage_shares(
                Decimal('100.00'), [1, 2], {1: Decimal('-10'), 2: Decimal('110')},
            )


# ================================================================================
# Pairwise netting (pure function)
# ================================================================================

class PairwiseNettingTests(TestCase):
    def test_mutual_debts_cancel_to_a_single_net(self):
        # A owes B 500, B owes A 200 -> A owes B 300.
        result = settlement_service.net_pairwise_debts([('A', 'B', Decimal('500')), ('B', 'A', Decimal('200'))])
        self.assertEqual(result, [('A', 'B', Decimal('300'))])

    def test_equal_mutual_debts_fully_cancel(self):
        result = settlement_service.net_pairwise_debts([('A', 'B', Decimal('500')), ('B', 'A', Decimal('500'))])
        self.assertEqual(result, [])

    def test_one_directional_debt_passes_through(self):
        result = settlement_service.net_pairwise_debts([('A', 'B', Decimal('500'))])
        self.assertEqual(result, [('A', 'B', Decimal('500'))])

    def test_multiple_debts_same_direction_accumulate(self):
        result = settlement_service.net_pairwise_debts([
            ('A', 'B', Decimal('100')), ('A', 'B', Decimal('50')),
        ])
        self.assertEqual(result, [('A', 'B', Decimal('150'))])

    def test_independent_pairs_stay_independent(self):
        result = settlement_service.net_pairwise_debts([
            ('A', 'B', Decimal('100')), ('C', 'D', Decimal('50')),
        ])
        self.assertEqual(set(result), {('A', 'B', Decimal('100')), ('C', 'D', Decimal('50'))})

    def test_negative_amount_represents_a_repayment(self):
        # A owed B 300; a repayment of 300 fully cancels it.
        result = settlement_service.net_pairwise_debts([
            ('A', 'B', Decimal('300')), ('A', 'B', Decimal('-300')),
        ])
        self.assertEqual(result, [])

    def test_sub_paisa_residue_is_dropped(self):
        result = settlement_service.net_pairwise_debts([('A', 'B', Decimal('0.001'))])
        self.assertEqual(result, [])

    def test_zero_debt_produces_no_result(self):
        result = settlement_service.net_pairwise_debts([])
        self.assertEqual(result, [])


# ================================================================================
# Global simplification (pure function)
# ================================================================================

class GlobalSimplificationTests(TestCase):
    def test_two_debtors_one_creditor(self):
        # A owes 500, B owes 300, C is owed 800.
        result = settlement_service.simplify_global_debts({
            'A': Decimal('-500'), 'B': Decimal('-300'), 'C': Decimal('800'),
        })
        self.assertEqual(set(result), {('A', 'C', Decimal('500.00')), ('B', 'C', Decimal('300.00'))})

    def test_minimizes_transfer_count_for_a_connected_chain(self):
        # A owes 100, B is net zero (owed 100, owes 100 elsewhere -> nets to
        # -100+100=0... use a case where B is a pure pass-through instead).
        # A owes 100 total; C is owed 100. One transfer, not routed through B.
        result = settlement_service.simplify_global_debts({
            'A': Decimal('-100'), 'B': Decimal('0'), 'C': Decimal('100'),
        })
        self.assertEqual(result, [('A', 'C', Decimal('100.00'))])

    def test_balances_under_one_paisa_are_ignored(self):
        result = settlement_service.simplify_global_debts({'A': Decimal('0.001'), 'B': Decimal('-0.001')})
        self.assertEqual(result, [])

    def test_all_zero_balances_produce_no_settlements(self):
        result = settlement_service.simplify_global_debts({'A': Decimal('0'), 'B': Decimal('0')})
        self.assertEqual(result, [])

    def test_uneven_three_way_split_settles_completely(self):
        # ₹100 dinner paid by A, split equally three ways (33.34/33.33/33.33):
        # A is owed 66.66 net, B and C each owe ~33.33/33.34.
        result = settlement_service.simplify_global_debts({
            'A': Decimal('66.66'), 'B': Decimal('-33.33'), 'C': Decimal('-33.33'),
        })
        total_settled = sum(amount for _, _, amount in result)
        self.assertEqual(total_settled, Decimal('66.66'))

    def test_result_sums_conserve_total_money(self):
        balances = {'A': Decimal('-500'), 'B': Decimal('-300'), 'C': Decimal('-50'), 'D': Decimal('850')}
        result = settlement_service.simplify_global_debts(balances)
        # Every debtor's total outgoing settlement equals their debt.
        outgoing = {}
        for payer, _, amount in result:
            outgoing[payer] = outgoing.get(payer, Decimal('0')) + amount
        self.assertEqual(outgoing.get('A', Decimal('0')), Decimal('500.00'))
        self.assertEqual(outgoing.get('B', Decimal('0')), Decimal('300.00'))
        self.assertEqual(outgoing.get('C', Decimal('0')), Decimal('50.00'))


# ================================================================================
# Integration tests: the pure math wired up through real groups/expenses
# ================================================================================

class SettlementIntegrationTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice2@example.com', upi_id='alice@okhdfc')
        self.bob = make_user('bob2@example.com')
        self.carol = make_user('carol2@example.com')
        self.dan = make_user('dan2@example.com')

    def test_multiple_expenses_accumulate_into_one_settlement(self):
        group = make_group(self.alice, self.bob, mode=SettlementMode.GLOBAL)
        services.create_expense(
            group=group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Coffee', amount=Decimal('100.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id],
        )
        services.create_expense(
            group=group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Snacks', amount=Decimal('50.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-02', participant_ids=[self.alice.id, self.bob.id],
        )
        [settlement] = services.generate_settlements(group=group)
        self.assertEqual(settlement.amount, Decimal('75.00'))  # half of 150 total

    def test_mutual_debts_across_two_expenses_net_down(self):
        group = make_group(self.alice, self.bob, mode=SettlementMode.PAIRWISE)
        # Alice pays 500 total (Bob's share 250), Bob pays 400 total (Alice's share 200).
        services.create_expense(
            group=group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Hotel', amount=Decimal('500.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id],
        )
        services.create_expense(
            group=group, created_by=self.bob, paid_by_id=self.bob.id,
            description='Taxi', amount=Decimal('400.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-02', participant_ids=[self.alice.id, self.bob.id],
        )
        [settlement] = services.generate_settlements(group=group)
        # Bob owed Alice 250, Alice owed Bob 200 -> net Bob owes Alice 50.
        self.assertEqual(settlement.payer_id, self.bob.id)
        self.assertEqual(settlement.payee_id, self.alice.id)
        self.assertEqual(settlement.amount, Decimal('50.00'))

    def test_zero_net_balance_produces_no_settlement(self):
        group = make_group(self.alice, self.bob, mode=SettlementMode.GLOBAL)
        # Alice and Bob each pay for an identical expense -> perfectly even, nothing owed.
        services.create_expense(
            group=group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Round 1', amount=Decimal('100.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id],
        )
        services.create_expense(
            group=group, created_by=self.bob, paid_by_id=self.bob.id,
            description='Round 2', amount=Decimal('100.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-02', participant_ids=[self.alice.id, self.bob.id],
        )
        settlements = services.generate_settlements(group=group)
        self.assertEqual(settlements, [])

    def test_uneven_division_settles_exactly_with_no_leftover(self):
        group = make_group(self.alice, self.bob, self.carol, mode=SettlementMode.GLOBAL)
        services.create_expense(
            group=group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Dinner', amount=Decimal('100.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id, self.carol.id],
        )
        settlements = services.generate_settlements(group=group)
        total = sum(s.amount for s in settlements)
        self.assertEqual(total, Decimal('66.66'))  # Alice's net credit (100 - 33.34)

    def test_four_member_group_global_settlement(self):
        group = make_group(self.alice, self.bob, self.carol, self.dan, mode=SettlementMode.GLOBAL)
        services.create_expense(
            group=group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Groceries', amount=Decimal('400.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01',
            participant_ids=[self.alice.id, self.bob.id, self.carol.id, self.dan.id],
        )
        settlements = services.generate_settlements(group=group)
        self.assertEqual(len(settlements), 3)
        self.assertTrue(all(s.payee_id == self.alice.id for s in settlements))
        self.assertEqual(sum(s.amount for s in settlements), Decimal('300.00'))

    def test_already_paid_settlement_reduces_future_global_balance(self):
        group = make_group(self.alice, self.bob, mode=SettlementMode.GLOBAL)
        services.create_expense(
            group=group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Dinner', amount=Decimal('100.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id],
        )
        [first] = services.generate_settlements(group=group)
        self.assertEqual(first.amount, Decimal('50.00'))
        services.mark_settlement_paid(settlement=first, requesting_user=self.alice)

        # Another identical expense — Bob's total new debt is 50, but he already paid 50.
        services.create_expense(
            group=group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Lunch', amount=Decimal('100.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-02', participant_ids=[self.alice.id, self.bob.id],
        )
        settlements = services.generate_settlements(group=group)
        self.assertEqual(len(settlements), 1)
        self.assertEqual(settlements[0].amount, Decimal('50.00'))
        # The paid settlement is still there as history, alongside the new pending one.
        self.assertEqual(
            {s.status for s in group.settlements.all()},
            {SettlementStatus.PAID, SettlementStatus.PENDING},
        )

    def test_already_paid_settlement_reduces_future_pairwise_balance(self):
        group = make_group(self.alice, self.bob, mode=SettlementMode.PAIRWISE)
        services.create_expense(
            group=group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Dinner', amount=Decimal('100.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id],
        )
        [first] = services.generate_settlements(group=group)
        services.mark_settlement_paid(settlement=first, requesting_user=self.alice)

        services.create_expense(
            group=group, created_by=self.bob, paid_by_id=self.bob.id,
            description='Taxi', amount=Decimal('40.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-02', participant_ids=[self.alice.id, self.bob.id],
        )
        settlements = services.generate_settlements(group=group)
        # Bob already paid his 50; now Alice owes Bob 20 for the taxi.
        self.assertEqual(len(settlements), 1)
        self.assertEqual(settlements[0].payer_id, self.alice.id)
        self.assertEqual(settlements[0].payee_id, self.bob.id)
        self.assertEqual(settlements[0].amount, Decimal('20.00'))


# ================================================================================
# "Show Calculation" explainability
# ================================================================================

class ShowCalculationTests(TestCase):
    def setUp(self):
        self.manav = make_user('manav@example.com')
        self.rahul = make_user('rahul@example.com')
        self.amit = make_user('amit@example.com')

    def test_explain_expense_matches_required_format(self):
        group = make_group(self.manav, self.rahul, self.amit, mode=SettlementMode.PAIRWISE)
        expense = services.create_expense(
            group=group, created_by=self.manav, paid_by_id=self.manav.id,
            description='Dinner', amount=Decimal('900.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.manav.id, self.rahul.id, self.amit.id],
        )
        explanation = settlement_service.explain_expense(expense)
        self.assertEqual(explanation['description'], 'Dinner')
        self.assertEqual(explanation['amount'], '900.00')
        self.assertEqual(explanation['paid_by'], 'manav')
        self.assertEqual(
            {s['user']: s['amount'] for s in explanation['shares']},
            {'manav': '300.00', 'rahul': '300.00', 'amit': '300.00'},
        )
        debts = {d['from']: d['amount'] for d in explanation['debts']}
        self.assertEqual(debts, {'rahul': '300.00', 'amit': '300.00'})
        self.assertTrue(all(d['to'] == 'manav' for d in explanation['debts']))

    def test_explain_expense_excludes_payers_own_share_from_debts(self):
        group = make_group(self.manav, self.rahul, mode=SettlementMode.GLOBAL)
        expense = services.create_expense(
            group=group, created_by=self.manav, paid_by_id=self.manav.id,
            description='Coffee', amount=Decimal('100.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.manav.id, self.rahul.id],
        )
        explanation = settlement_service.explain_expense(expense)
        self.assertEqual(len(explanation['debts']), 1)
        self.assertEqual(explanation['debts'][0]['from'], 'rahul')

    def test_explain_settlement_pairwise_lists_only_relevant_expenses(self):
        group = make_group(self.manav, self.rahul, self.amit, mode=SettlementMode.PAIRWISE)
        services.create_expense(
            group=group, created_by=self.manav, paid_by_id=self.manav.id,
            description='Dinner', amount=Decimal('900.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.manav.id, self.rahul.id, self.amit.id],
        )
        # An expense that doesn't involve Amit at all -- shouldn't appear in
        # the Manav/Amit settlement's calculation.
        services.create_expense(
            group=group, created_by=self.manav, paid_by_id=self.manav.id,
            description='Rahul-only snack', amount=Decimal('50.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-02', participant_ids=[self.manav.id, self.rahul.id],
        )
        settlements = services.generate_settlements(group=group)
        amit_settlement = next(s for s in settlements if s.payer_id == self.amit.id)
        explanation = settlement_service.explain_settlement(amit_settlement)
        self.assertEqual(explanation['mode'], 'pairwise')
        self.assertEqual(len(explanation['expenses']), 1)
        self.assertEqual(explanation['expenses'][0]['description'], 'Dinner')

    def test_explain_settlement_global_includes_full_ledger_and_nets(self):
        group = make_group(self.manav, self.rahul, self.amit, mode=SettlementMode.GLOBAL)
        services.create_expense(
            group=group, created_by=self.manav, paid_by_id=self.manav.id,
            description='Dinner', amount=Decimal('900.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.manav.id, self.rahul.id, self.amit.id],
        )
        [settlement] = [s for s in services.generate_settlements(group=group) if s.payer_id == self.rahul.id]
        explanation = settlement_service.explain_settlement(settlement)
        self.assertEqual(explanation['mode'], 'global')
        self.assertEqual(len(explanation['expenses']), 1)
        self.assertEqual(explanation['payee_net']['net'], '600.00')  # Manav paid 900, owes 300
        self.assertEqual(explanation['payer_net']['net'], '-300.00')  # Rahul paid 0, owes 300

    def test_explain_group_lists_every_expense_oldest_first(self):
        group = make_group(self.manav, self.rahul, mode=SettlementMode.GLOBAL)
        services.create_expense(
            group=group, created_by=self.manav, paid_by_id=self.manav.id,
            description='Later', amount=Decimal('50.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-05', participant_ids=[self.manav.id, self.rahul.id],
        )
        services.create_expense(
            group=group, created_by=self.manav, paid_by_id=self.manav.id,
            description='Earlier', amount=Decimal('30.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.manav.id, self.rahul.id],
        )
        trail = settlement_service.explain_group(group)
        self.assertEqual([e['description'] for e in trail], ['Earlier', 'Later'])


# ================================================================================
# API: Show Calculation endpoint
# ================================================================================

class SettlementCalculationApiTests(APITestCase):
    def setUp(self):
        self.alice = make_user('alice3@example.com')
        self.bob = make_user('bob3@example.com')
        self.outsider = make_user('eve3@example.com')

    def auth_as(self, user):
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_calculation_endpoint_returns_explanation(self):
        group = make_group(self.alice, self.bob, mode=SettlementMode.PAIRWISE)
        self.auth_as(self.alice)
        self.client.post(f'/api/splits/groups/{group.id}/expenses/', {
            'description': 'Dinner', 'amount': '100.00', 'paid_by': self.alice.id,
            'split_type': 'equal', 'expense_date': '2026-08-01',
            'participant_ids': [self.alice.id, self.bob.id],
        }, format='json')
        recalc = self.client.post(f'/api/splits/groups/{group.id}/settlements/recalculate/')
        settlement_id = recalc.data[0]['id']

        response = self.client.get(f'/api/splits/groups/{group.id}/settlements/{settlement_id}/calculation/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['mode'], 'pairwise')
        self.assertEqual(len(response.data['expenses']), 1)
        self.assertEqual(response.data['expenses'][0]['description'], 'Dinner')

    def test_non_member_cannot_view_calculation(self):
        group = make_group(self.alice, self.bob, mode=SettlementMode.GLOBAL)
        self.auth_as(self.alice)
        self.client.post(f'/api/splits/groups/{group.id}/expenses/', {
            'description': 'Coffee', 'amount': '50.00', 'paid_by': self.alice.id,
            'split_type': 'equal', 'expense_date': '2026-08-01',
            'participant_ids': [self.alice.id, self.bob.id],
        }, format='json')
        recalc = self.client.post(f'/api/splits/groups/{group.id}/settlements/recalculate/')
        settlement_id = recalc.data[0]['id']

        self.auth_as(self.outsider)
        response = self.client.get(f'/api/splits/groups/{group.id}/settlements/{settlement_id}/calculation/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
