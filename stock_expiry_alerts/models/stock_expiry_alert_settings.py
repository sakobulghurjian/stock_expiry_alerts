# Copyright (C) 2026 Yerevan Digital Co
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class StockExpiryAlertSettings(models.TransientModel):
    """Inventory-manager-safe UI for only the expiry-alert company fields."""

    _name = "stock.expiry.alert.settings"
    _description = "Inventory Expiry Alert Settings"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    expiry_alert_enabled = fields.Boolean(string="Enable Expiry Alerts")
    expiry_alert_days = fields.Char(
        string="Alert Days",
        default="30, 15, 7, 3, 1",
        help="Comma-separated exact days before expiration.",
    )
    expiry_alert_responsible_user_id = fields.Many2one(
        "res.users",
        string="Expiry Alert Responsible User",
        domain="[('share', '=', False), ('company_ids', 'in', company_id)]",
    )
    expiry_alert_send_email = fields.Boolean(string="Send Email Notification")
    expiry_alert_notify_expired = fields.Boolean(
        string="Notify When Product Expires",
        default=True,
    )

    @api.model
    def _check_manager_access(self):
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise AccessError(_("Only inventory managers can configure expiry alerts."))

    @api.model
    def _check_allowed_company(self, company):
        if not company or company not in self.env.companies:
            raise AccessError(_("You cannot configure expiry alerts for this company."))

    @api.model
    def default_get(self, field_names):
        self._check_manager_access()
        values = super().default_get(field_names)
        company = self.env.company
        self._check_allowed_company(company)
        company_values = {
            "company_id": company.id,
            "expiry_alert_enabled": company.expiry_alert_enabled,
            "expiry_alert_days": company.expiry_alert_days,
            "expiry_alert_responsible_user_id": company.expiry_alert_responsible_user_id.id,
            "expiry_alert_send_email": company.expiry_alert_send_email,
            "expiry_alert_notify_expired": company.expiry_alert_notify_expired,
        }
        for field_name, value in company_values.items():
            if field_name in field_names:
                values[field_name] = value
        return values

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager_access()
        normalized_vals_list = []
        parser = self.env["stock.expiry.threshold.mixin"]
        for vals in vals_list:
            vals = dict(vals)
            company = self.env["res.company"].browse(
                vals.get("company_id") or self.env.company.id
            ).exists()
            self._check_allowed_company(company)
            vals["company_id"] = company.id
            if "expiry_alert_days" in vals:
                vals["expiry_alert_days"] = parser._normalize_expiry_alert_days(
                    vals["expiry_alert_days"]
                )
            normalized_vals_list.append(vals)
        records = super().create(normalized_vals_list)
        records._check_configuration()
        return records

    def write(self, vals):
        self._check_manager_access()
        if "company_id" in vals:
            company = self.env["res.company"].browse(vals["company_id"]).exists()
            self._check_allowed_company(company)
        vals = dict(vals)
        if "expiry_alert_days" in vals:
            vals["expiry_alert_days"] = self.env[
                "stock.expiry.threshold.mixin"
            ]._normalize_expiry_alert_days(vals["expiry_alert_days"])
        result = super().write(vals)
        self._check_configuration()
        return result

    def _check_configuration(self):
        parser = self.env["stock.expiry.threshold.mixin"]
        for settings in self:
            settings._check_allowed_company(settings.company_id)
            parser._parse_expiry_alert_days(settings.expiry_alert_days)
            responsible = settings.expiry_alert_responsible_user_id
            if settings.expiry_alert_enabled and not responsible:
                raise ValidationError(
                    _("Select an expiry alert responsible user before enabling expiry alerts.")
                )
            if responsible and (responsible.share or settings.company_id not in responsible.company_ids):
                raise ValidationError(
                    _("The responsible user must be an internal user of the selected company.")
                )

    def action_save(self):
        self.ensure_one()
        self._check_manager_access()
        self._check_allowed_company(self.company_id)
        self._check_configuration()
        values = {
            "expiry_alert_enabled": self.expiry_alert_enabled,
            "expiry_alert_days": self.expiry_alert_days,
            "expiry_alert_responsible_user_id": self.expiry_alert_responsible_user_id.id,
            "expiry_alert_send_email": self.expiry_alert_send_email,
            "expiry_alert_notify_expired": self.expiry_alert_notify_expired,
        }
        # Only this audited whitelist crosses the res.company ACL boundary.
        self.company_id.sudo().write(values)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Expiry Alerts"),
                "message": _("Expiry alert settings were saved for %s.", self.company_id.display_name),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

