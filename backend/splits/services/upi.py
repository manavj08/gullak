"""UPI id validation/save and payment-info generation for the splits app."""
import re

from django.core.exceptions import ValidationError

UPI_ID_RE = re.compile(r'^[\w.\-]{2,256}@[A-Za-z]{2,64}$')


def validate_upi_id(value):
    if not value or not UPI_ID_RE.match(value):
        raise ValidationError({'upi_id': 'Enter a valid UPI ID (e.g. name@bank).'})
    return value


def save_upi_id(*, user, upi_id):
    validate_upi_id(upi_id)
    user.upi_id = upi_id
    user.save(update_fields=['upi_id'])
    return user


def payment_info(*, settlement):
    """UPI payment info for a settlement: link + structured fields.
    QR rendering happens client-side — no image is generated here."""
    payee = settlement.payee
    payee_upi = getattr(payee, 'upi_id', '') or ''
    payee_name = payee.get_full_name() or payee.username
    note = f'Split settlement - {settlement.group.name}'
    info = {
        'payee_upi_id': payee_upi or None,
        'payee_name': payee_name,
        'amount': str(settlement.amount),
        'currency': 'INR',
        'note': note,
        'upi_link': None,
    }
    if payee_upi:
        link = f'upi://pay?pa={payee_upi}&pn={payee_name}&am={settlement.amount}&cu=INR&tn={note}'
        info['upi_link'] = link.replace(' ', '%20')
    return info
