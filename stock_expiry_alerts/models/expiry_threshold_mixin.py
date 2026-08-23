# Copyright (C) 2026 Yerevan Digital Co
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from odoo import api, models, _
from odoo.exceptions import ValidationError


class ExpiryThresholdMixin(models.AbstractModel):
    _name = "stock.expiry.threshold.mixin"
    _description = "Inventory Expiry Threshold Parser"

    @api.model
    def _parse_expiry_alert_days(self, value):
        """Return normalized, descending, positive alert-day integers."""
        if not value or not value.strip():
            return []
        try:
            days = [int(item.strip()) for item in value.split(",") if item.strip()]
        except (AttributeError, TypeError, ValueError) as error:
            raise ValidationError(
                _("Alert days must be comma-separated whole numbers, for example 30, 15, 7, 3, 1.")
            ) from error
        if not days or any(day <= 0 or day > 3650 for day in days):
            raise ValidationError(
                _("Alert days must contain positive whole numbers no greater than 3650.")
            )
        return sorted(set(days), reverse=True)

    @api.model
    def _normalize_expiry_alert_days(self, value):
        return ", ".join(str(day) for day in self._parse_expiry_alert_days(value))

