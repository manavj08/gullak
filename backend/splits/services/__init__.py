"""
splits.services — business logic for the splits app, organized by
responsibility:

  settlement.py  Settlement mathematics: split-type share rounding,
                 pairwise debt netting, global debt simplification, and
                 the "show calculation" explainability trail. The single
                 source of truth for every money computation in this app.
  groups.py      Group membership management.
  expenses.py    Expense creation/deletion (delegates all share math to
                 settlement.py).
  upi.py         UPI id validation/save and payment-info generation.

Everything is re-exported here so the rest of the app (views, permissions,
tests) can keep writing `from . import services; services.create_group(...)`
without needing to know which submodule a given function lives in.
"""
from .expenses import create_expense, delete_expense
from .groups import add_member, create_group, is_member, member_ids, remove_member, update_settlement_mode
from .settlement import (
    custom_shares, equal_shares, explain_expense, explain_group, explain_settlement,
    generate_settlements, mark_settlement_paid, net_pairwise_debts, percentage_shares,
    simplify_global_debts,
)
from .upi import payment_info, save_upi_id, validate_upi_id

__all__ = [
    'create_expense', 'delete_expense',
    'add_member', 'create_group', 'is_member', 'member_ids', 'remove_member', 'update_settlement_mode',
    'custom_shares', 'equal_shares', 'explain_expense', 'explain_group', 'explain_settlement',
    'generate_settlements', 'mark_settlement_paid', 'net_pairwise_debts', 'percentage_shares',
    'simplify_global_debts',
    'payment_info', 'save_upi_id', 'validate_upi_id',
]
