# Copyright (C) 2026 Yerevan Digital Co
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from odoo import api, fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    expiry_alert_days = fields.Char(
        string="Expiry Alert Days Override",
        groups="stock.group_stock_manager",
        help="Optional comma-separated alert days. When set, these replace the company defaults for this category.",
    )

    @api.constrains("expiry_alert_days")
    def _check_expiry_alert_days(self):
        parser = self.env["stock.expiry.threshold.mixin"]
        for category in self.filtered("expiry_alert_days"):
            parser._parse_expiry_alert_days(category.expiry_alert_days)

    def write(self, vals):
        if vals.get("expiry_alert_days"):
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
            if vals.get("expiry_alert_days"):
                vals["expiry_alert_days"] = parser._normalize_expiry_alert_days(
                    vals["expiry_alert_days"]
                )
            normalized_vals_list.append(vals)
        return super().create(normalized_vals_list)
