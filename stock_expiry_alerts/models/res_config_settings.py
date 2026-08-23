# Copyright (C) 2026 Yerevan Digital Co
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    expiry_alert_enabled = fields.Boolean(
        related="company_id.expiry_alert_enabled",
        readonly=False,
    )
    expiry_alert_days = fields.Char(
        related="company_id.expiry_alert_days",
        readonly=False,
    )
    expiry_alert_responsible_user_id = fields.Many2one(
        related="company_id.expiry_alert_responsible_user_id",
        readonly=False,
        domain="[('share', '=', False), ('company_ids', 'in', company_id)]",
    )
    expiry_alert_send_email = fields.Boolean(
        related="company_id.expiry_alert_send_email",
        readonly=False,
    )
    expiry_alert_notify_expired = fields.Boolean(
        related="company_id.expiry_alert_notify_expired",
        readonly=False,
    )
