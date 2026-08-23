# Copyright (C) 2026 Yerevan Digital Co
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from collections import defaultdict

from odoo import api, fields, models, _


class StockExpiryDashboardLine(models.Model):
    _inherit = "stock.expiry.dashboard.line"

    alert_sent = fields.Boolean(
        compute="_compute_expiry_alert_information",
        compute_sudo=True,
    )
    last_alert_date = fields.Datetime(
        compute="_compute_expiry_alert_information",
        compute_sudo=True,
    )
    next_alert_threshold = fields.Char(
        string="Next Alert Threshold",
        compute="_compute_expiry_alert_information",
        compute_sudo=True,
    )

    @api.depends("lot_id", "company_id", "expiration_date")
    def _compute_expiry_alert_information(self):
        events_by_key = defaultdict(list)
        valid_lines = self.filtered(
            lambda line: line.lot_id and line.company_id and line.expiration_date
        )
        if valid_lines:
            events = self.env["stock.expiry.alert.event"].search(
                [
                    ("lot_id", "in", valid_lines.lot_id.ids),
                    ("company_id", "in", valid_lines.company_id.ids),
                ],
                order="alert_datetime desc, id desc",
            )
            for event in events:
                key = (event.lot_id.id, event.company_id.id, event.expiration_date)
                events_by_key[key].append(event)

        lot_model = self.env["stock.lot"]
        for line in self:
            line.alert_sent = False
            line.last_alert_date = False
            line.next_alert_threshold = False
            if not line.lot_id or not line.company_id or not line.expiration_date:
                continue
            key = (line.lot_id.id, line.company_id.id, line.expiration_date)
            matching_events = events_by_key[key]
            if matching_events:
                line.alert_sent = True
                line.last_alert_date = matching_events[0].alert_datetime
            days_remaining = lot_model._expiry_alert_days_remaining(
                line.lot_id, line.company_id
            )
            if days_remaining <= 0:
                if (
                    line.company_id.expiry_alert_notify_expired
                    and -1 not in {event.threshold_days for event in matching_events}
                ):
                    line.next_alert_threshold = _("Expired")
                continue
            sent_thresholds = {event.threshold_days for event in matching_events}
            pending = [
                threshold
                for threshold in lot_model._expiry_alert_thresholds(
                    line.lot_id, line.company_id
                )
                if threshold <= days_remaining and threshold not in sent_thresholds
            ]
            if pending:
                line.next_alert_threshold = str(max(pending))
