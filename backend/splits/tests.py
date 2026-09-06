from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from . import services
from .models import (
    Settlement, SettlementMode, SettlementStatus, SplitExpense, SplitGroup,
    SplitGroupMember, SplitType,
)

User = get_user_model()


def make_user(email, upi_id=''):
    user = User.objects.create_user(username=email.split('@')[0], email=email, password='StrongPass123!')
    if upi_id:
        user.upi_id = upi_id
        user.save(update_fields=['upi_id'])
    return user


def make_group(creator, *members, name='Trip Fund', mode=SettlementMode.GLOBAL):
    group = services.create_group(name=name, created_by=creator, settlement_mode=mode)
    for m in members:
        SplitGroupMember.objects.create(group=group, user=m)
    return group


# ============================================================ model tests ==

class SplitGroupModelTests(TestCase):
    def test_creator_is_added_as_admin_member(self):
        alice = make_user('alice@example.com')
        group = services.create_group(name='Roomies', created_by=alice)
        membership = SplitGroupMember.objects.get(group=group, user=alice)
        self.assertEqual(membership.role, 'admin')


# ========================================================== expense splits =

class ExpenseSplitServiceTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice@example.com')
        self.bob = make_user('bob@example.com')
        self.carol = make_user('carol@example.com')
        self.group = make_group(self.alice, self.bob, self.carol)

    def test_equal_split_divides_evenly(self):
        expense = services.create_expense(
            group=self.group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Dinner', amount=Decimal('300.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id, self.carol.id],
        )
        shares = {s.user_id: s.share_amount for s in expense.shares.all()}
        self.assertEqual(sum(shares.values()), Decimal('300.00'))
        self.assertEqual(shares[self.alice.id], Decimal('100.00'))

    def test_equal_split_distributes_rounding_remainder(self):
        expense = services.create_expense(
            group=self.group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Snacks', amount=Decimal('100.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id, self.carol.id],
        )
        shares = {s.user_id: s.share_amount for s in expense.shares.all()}
        self.assertEqual(sum(shares.values()), Decimal('100.00'))
        self.assertEqual(sorted(shares.values()), [Decimal('33.33'), Decimal('33.33'), Decimal('33.34')])

    def test_custom_split_must_sum_to_total(self):
        with self.assertRaises(ValidationError):
            services.create_expense(
                group=self.group, created_by=self.alice, paid_by_id=self.alice.id,
                description='Cab', amount=Decimal('200.00'), split_type=SplitType.CUSTOM,
                expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id],
                exact_shares={self.alice.id: Decimal('50.00'), self.bob.id: Decimal('100.00')},
            )
        self.assertEqual(SplitExpense.objects.count(), 0)

    def test_custom_split_accepts_matching_total(self):
        expense = services.create_expense(
            group=self.group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Cab', amount=Decimal('200.00'), split_type=SplitType.CUSTOM,
            expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id],
            exact_shares={self.alice.id: Decimal('50.00'), self.bob.id: Decimal('150.00')},
        )
        shares = {s.user_id: s.share_amount for s in expense.shares.all()}
        self.assertEqual(shares[self.bob.id], Decimal('150.00'))

    def test_percentage_split_must_sum_to_100(self):
        with self.assertRaises(ValidationError):
            services.create_expense(
                group=self.group, created_by=self.alice, paid_by_id=self.alice.id,
                description='Groceries', amount=Decimal('90.00'), split_type=SplitType.PERCENTAGE,
                expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id],
                percentages={self.alice.id: Decimal('60'), self.bob.id: Decimal('30')},
            )

    def test_percentage_split_computes_shares_and_handles_rounding(self):
        expense = services.create_expense(
            group=self.group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Rent', amount=Decimal('100.00'), split_type=SplitType.PERCENTAGE,
            expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id, self.carol.id],
            percentages={self.alice.id: Decimal('34'), self.bob.id: Decimal('33'), self.carol.id: Decimal('33')},
        )
        shares = {s.user_id: s.share_amount for s in expense.shares.all()}
        self.assertEqual(sum(shares.values()), Decimal('100.00'))
        self.assertEqual(shares[self.alice.id], Decimal('34.00'))

    def test_non_member_cannot_create_expense(self):
        outsider = make_user('dan@example.com')
        with self.assertRaises(ValidationError):
            services.create_expense(
                group=self.group, created_by=outsider, paid_by_id=self.alice.id,
                description='Dinner', amount=Decimal('90.00'), split_type=SplitType.EQUAL,
                expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id],
            )

    def test_participant_must_be_group_member(self):
        outsider = make_user('dan@example.com')
        with self.assertRaises(ValidationError):
            services.create_expense(
                group=self.group, created_by=self.alice, paid_by_id=self.alice.id,
                description='Dinner', amount=Decimal('90.00'), split_type=SplitType.EQUAL,
                expense_date='2026-08-01', participant_ids=[self.alice.id, outsider.id],
            )


# =================================================================== members

class MembershipServiceTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice@example.com')
        self.bob = make_user('bob@example.com')
        self.group = make_group(self.alice, self.bob)

    def test_member_can_add_new_member(self):
        carol = make_user('carol@example.com')
        services.add_member(group=self.group, user_id=carol.id, requesting_user=self.bob)
        self.assertTrue(SplitGroupMember.objects.filter(group=self.group, user=carol).exists())

    def test_non_member_cannot_add_member(self):
        outsider = make_user('dan@example.com')
        carol = make_user('carol@example.com')
        with self.assertRaises(ValidationError):
            services.add_member(group=self.group, user_id=carol.id, requesting_user=outsider)

    def test_member_can_remove_self(self):
        services.remove_member(group=self.group, user_id=self.bob.id, requesting_user=self.bob)
        self.assertFalse(SplitGroupMember.objects.filter(group=self.group, user=self.bob).exists())

    def test_member_cannot_remove_another_member(self):
        with self.assertRaises(ValidationError):
            services.remove_member(group=self.group, user_id=self.alice.id, requesting_user=self.bob)

    def test_creator_can_remove_other_member(self):
        services.remove_member(group=self.group, user_id=self.bob.id, requesting_user=self.alice)
        self.assertFalse(SplitGroupMember.objects.filter(group=self.group, user=self.bob).exists())

    def test_creator_cannot_be_removed(self):
        with self.assertRaises(ValidationError):
            services.remove_member(group=self.group, user_id=self.alice.id, requesting_user=self.alice)


# ============================================================== settlement =

class SettlementGenerationTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice@example.com', upi_id='alice@okhdfc')
        self.bob = make_user('bob@example.com')
        self.carol = make_user('carol@example.com')

    def test_global_mode_simplifies_debts(self):
        group = make_group(self.alice, self.bob, self.carol, mode=SettlementMode.GLOBAL)
        # Alice pays 300 split equally among all 3 -> Bob and Carol each owe Alice 100.
        services.create_expense(
            group=group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Dinner', amount=Decimal('300.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id, self.carol.id],
        )
        settlements = services.generate_settlements(group=group)
        self.assertEqual(len(settlements), 2)
        total = sum(s.amount for s in settlements)
        self.assertEqual(total, Decimal('200.00'))
        for s in settlements:
            self.assertEqual(s.payee_id, self.alice.id)

    def test_pairwise_mode_keeps_direct_balances(self):
        group = make_group(self.alice, self.bob, self.carol, mode=SettlementMode.PAIRWISE)
        services.create_expense(
            group=group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Dinner', amount=Decimal('300.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id, self.carol.id],
        )
        settlements = services.generate_settlements(group=group)
        self.assertEqual(len(settlements), 2)
        payer_ids = {s.payer_id for s in settlements}
        self.assertEqual(payer_ids, {self.bob.id, self.carol.id})
        for s in settlements:
            self.assertEqual(s.amount, Decimal('100.00'))
            self.assertEqual(s.payee_id, self.alice.id)

    def test_recalculate_clears_stale_pending_settlements(self):
        group = make_group(self.alice, self.bob)
        services.create_expense(
            group=group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Coffee', amount=Decimal('100.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id],
        )
        first = services.generate_settlements(group=group)
        self.assertEqual(len(first), 1)
        # Add another expense reversing the balance and recalculate.
        services.create_expense(
            group=group, created_by=self.bob, paid_by_id=self.bob.id,
            description='Snacks', amount=Decimal('100.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-02', participant_ids=[self.alice.id, self.bob.id],
        )
        second = services.generate_settlements(group=group)
        self.assertEqual(len(second), 0)
        self.assertEqual(Settlement.objects.filter(group=group, status=SettlementStatus.PENDING).count(), 0)

    def test_only_payee_can_mark_settlement_paid(self):
        group = make_group(self.alice, self.bob)
        services.create_expense(
            group=group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Coffee', amount=Decimal('100.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id],
        )
        [settlement] = services.generate_settlements(group=group)
        with self.assertRaises(ValidationError):
            services.mark_settlement_paid(settlement=settlement, requesting_user=self.bob)
        settlement = services.mark_settlement_paid(settlement=settlement, requesting_user=self.alice)
        self.assertEqual(settlement.status, SettlementStatus.PAID)
        self.assertIsNotNone(settlement.paid_at)

    def test_payment_info_includes_upi_link_when_payee_has_upi_id(self):
        group = make_group(self.alice, self.bob)
        services.create_expense(
            group=group, created_by=self.alice, paid_by_id=self.alice.id,
            description='Coffee', amount=Decimal('50.00'), split_type=SplitType.EQUAL,
            expense_date='2026-08-01', participant_ids=[self.alice.id, self.bob.id],
        )
        [settlement] = services.generate_settlements(group=group)
        info = services.payment_info(settlement=settlement)
        self.assertIsNotNone(info['upi_link'])
        self.assertIn('alice@okhdfc', info['upi_link'])


class UpiIdValidationTests(TestCase):
    def test_rejects_invalid_upi_id(self):
        with self.assertRaises(ValidationError):
            services.validate_upi_id('not-a-upi-id')

    def test_accepts_valid_upi_id(self):
        services.validate_upi_id('someone@okhdfc')  # should not raise


# ==================================================================== API ==

class SplitsApiTests(APITestCase):
    def setUp(self):
        self.alice = make_user('alice@example.com')
        self.bob = make_user('bob@example.com')
        self.outsider = make_user('dan@example.com')
        self.group = make_group(self.alice, self.bob)

    def auth_as(self, user):
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_create_group_via_api(self):
        self.auth_as(self.alice)
        response = self.client.post('/api/splits/groups/', {
            'name': 'Weekend Trip', 'settlement_mode': 'global', 'member_ids': [self.bob.id],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data['members']), 2)

    def test_non_member_gets_404_on_group_detail(self):
        self.auth_as(self.outsider)
        response = self.client.get(f'/api/splits/groups/{self.group.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_can_view_group_detail(self):
        self.auth_as(self.bob)
        response = self.client.get(f'/api/splits/groups/{self.group.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(f'/api/splits/groups/{self.group.id}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_expense_via_api(self):
        self.auth_as(self.alice)
        response = self.client.post(f'/api/splits/groups/{self.group.id}/expenses/', {
            'description': 'Dinner', 'amount': '100.00', 'paid_by': self.alice.id,
            'split_type': 'equal', 'expense_date': '2026-08-01',
            'participant_ids': [self.alice.id, self.bob.id],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data['shares']), 2)

    def test_non_member_cannot_create_expense_via_api(self):
        self.auth_as(self.outsider)
        response = self.client.post(f'/api/splits/groups/{self.group.id}/expenses/', {
            'description': 'Dinner', 'amount': '100.00', 'paid_by': self.alice.id,
            'split_type': 'equal', 'expense_date': '2026-08-01',
            'participant_ids': [self.alice.id, self.bob.id],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_recalculate_and_mark_paid_flow(self):
        self.auth_as(self.alice)
        self.client.post(f'/api/splits/groups/{self.group.id}/expenses/', {
            'description': 'Coffee', 'amount': '100.00', 'paid_by': self.alice.id,
            'split_type': 'equal', 'expense_date': '2026-08-01',
            'participant_ids': [self.alice.id, self.bob.id],
        }, format='json')
        response = self.client.post(f'/api/splits/groups/{self.group.id}/settlements/recalculate/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        settlement_id = response.data[0]['id']

        # Bob (the payer) cannot mark it paid -- only Alice (the payee) can.
        self.auth_as(self.bob)
        response = self.client.post(f'/api/splits/groups/{self.group.id}/settlements/{settlement_id}/mark-paid/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.auth_as(self.alice)
        response = self.client.post(f'/api/splits/groups/{self.group.id}/settlements/{settlement_id}/mark-paid/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'paid')

    def test_leave_group_via_api(self):
        self.auth_as(self.bob)
        response = self.client.delete(f'/api/splits/groups/{self.group.id}/members/{self.bob.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SplitGroupMember.objects.filter(group=self.group, user=self.bob).exists())

    def test_save_upi_id_via_api(self):
        self.auth_as(self.alice)
        response = self.client.post('/api/splits/upi/save/', {'upi_id': 'alice@okhdfc'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.upi_id, 'alice@okhdfc')

    def test_save_invalid_upi_id_via_api(self):
        self.auth_as(self.alice)
        response = self.client.post('/api/splits/upi/save/', {'upi_id': 'not-valid'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_group_list_includes_pending_settlement_total(self):
        self.auth_as(self.alice)
        self.client.post(f'/api/splits/groups/{self.group.id}/expenses/', {
            'description': 'Coffee', 'amount': '100.00', 'paid_by': self.alice.id,
            'split_type': 'equal', 'expense_date': '2026-08-01',
            'participant_ids': [self.alice.id, self.bob.id],
        }, format='json')
        response = self.client.get('/api/splits/groups/')
        group_data = next(g for g in response.data if g['id'] == self.group.id)
        self.assertEqual(group_data['pending_settlement_total'], '0.00')

        self.client.post(f'/api/splits/groups/{self.group.id}/settlements/recalculate/')
        response = self.client.get('/api/splits/groups/')
        group_data = next(g for g in response.data if g['id'] == self.group.id)
        self.assertEqual(group_data['pending_settlement_total'], '50.00')

    def test_only_creator_can_change_settlement_mode(self):
        self.auth_as(self.bob)
        response = self.client.patch(f'/api/splits/groups/{self.group.id}/', {'settlement_mode': 'pairwise'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.auth_as(self.alice)
        response = self.client.patch(f'/api/splits/groups/{self.group.id}/', {'settlement_mode': 'pairwise'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['settlement_mode'], 'pairwise')

    def test_user_lookup_returns_id_for_existing_username(self):
        self.auth_as(self.alice)
        response = self.client.get('/api/splits/users/lookup/', {'username': self.bob.username})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'found': True, 'id': self.bob.id, 'username': self.bob.username})

    def test_user_lookup_reports_not_found_for_unknown_username(self):
        self.auth_as(self.alice)
        response = self.client.get('/api/splits/users/lookup/', {'username': 'nobody_here'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'found': False})
