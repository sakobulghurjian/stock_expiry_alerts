# Copyright (C) 2026 Yerevan Digital Co
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from odoo import fields, models


class StockExpiryAlertEvent(models.Model):
    _name = "stock.expiry.alert.event"
    _description = "Inventory Expiry Alert Event"
    _order = "alert_datetime desc, id desc"
    _check_company_auto = True

    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial Number",
        required=True,
        readonly=True,
        index=True,
        ondelete="cascade",
        check_company=True,
    )
    product_id = fields.Many2one(
        "product.product",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        readonly=True,
        index=True,
        ondelete="cascade",
    )
    responsible_user_id = fields.Many2one(
        "res.users",
        required=True,
        readonly=True,
        ondelete="restrict",
    )
    expiration_date = fields.Datetime(required=True, readonly=True, index=True)
    threshold_days = fields.Integer(
        string="Threshold",
        required=True,
        readonly=True,
        help="Positive values are days-before-expiry thresholds. -1 identifies the one-time expired event.",
    )
    days_remaining = fields.Integer(required=True, readonly=True)
    quantity = fields.Float(readonly=True, digits="Product Unit of Measure")
    alert_datetime = fields.Datetime(default=fields.Datetime.now, required=True, readonly=True)
    activity_id = fields.Many2one("mail.activity", readonly=True, ondelete="set null")
    email_sent = fields.Boolean(readonly=True)
    is_expired = fields.Boolean(compute="_compute_is_expired")

    _event_uniq = models.Constraint(
        "unique(company_id, lot_id, expiration_date, threshold_days)",
        "An expiry alert already exists for this company, lot, expiration date, and threshold.",
    )

    def _compute_is_expired(self):
        for event in self:
            event.is_expired = event.threshold_days == -1

    def action_open_lot(self):
        self.ensure_one()
        self.check_access("read")
        self.lot_id.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "name": self.lot_id.display_name,
            "res_model": "stock.lot",
            "res_id": self.lot_id.id,
            "view_mode": "form",
            "target": "current",
        }

