# Copyright (C) 2026 Yerevan Digital Co
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    expiry_alert_enabled = fields.Boolean(
        string="Enable Expiry Alerts",
        groups="stock.group_stock_manager",
    )
    expiry_alert_days = fields.Char(
        string="Alert Days",
        default="30, 15, 7, 3, 1",
        groups="stock.group_stock_manager",
        help="Comma-separated days before expiration. Alerts are created only on exact matching days.",
    )
    expiry_alert_responsible_user_id = fields.Many2one(
        "res.users",
        string="Expiry Alert Responsible User",
        check_company=True,
        domain="[('share', '=', False), ('company_ids', 'in', id)]",
        groups="stock.group_stock_manager",
    )
    expiry_alert_send_email = fields.Boolean(
        string="Send Email Notification",
        groups="stock.group_stock_manager",
    )
    expiry_alert_notify_expired = fields.Boolean(
        string="Notify When Product Expires",
        default=True,
        groups="stock.group_stock_manager",
    )

    @api.constrains("expiry_alert_days")
    def _check_expiry_alert_days(self):
        parser = self.env["stock.expiry.threshold.mixin"]
        for company in self:
            parser._parse_expiry_alert_days(company.expiry_alert_days)

    @api.constrains("expiry_alert_enabled", "expiry_alert_responsible_user_id")
    def _check_expiry_alert_responsible_user(self):
        for company in self:
            if company.expiry_alert_enabled and not company.expiry_alert_responsible_user_id:
                raise ValidationError(
                    _("Select an expiry alert responsible user before enabling expiry alerts.")
                )

    def write(self, vals):
        if "expiry_alert_days" in vals:
            vals = dict(vals)
            vals["expiry_alert_days"] = self.env[
                "stock.expiry.threshold.mixin"
            ]._normalize_expiry_alert_days(vals["expiry_alert_days"])
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        parser = self.env["stock.expiry.threshold.mixin"]
        normalized_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            if "expiry_alert_days" in vals:
                vals["expiry_alert_days"] = parser._normalize_expiry_alert_days(
                    vals["expiry_alert_days"]
                )
            normalized_vals_list.append(vals)
        return super().create(normalized_vals_list)
