# Copyright (C) 2026 Yerevan Digital Co
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

import logging
from datetime import datetime, time, timedelta

import pytz
from markupsafe import Markup, escape
from psycopg2 import IntegrityError

from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from odoo.tools.float_utils import float_compare


_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    _inherit = "stock.lot"

    _EXPIRY_ALERT_BATCH_SIZE = 500

    @api.model
    def _expiry_alert_check_access(self):
        if not self.env.is_superuser() and not self.env.user.has_group(
            "stock.group_stock_manager"
        ):
            raise AccessError(_("Only inventory managers can run expiry alerts."))

    @api.model
    def _expiry_alert_timezone(self, company):
        return pytz.timezone(company.expiry_alert_responsible_user_id.tz or "UTC")

    @api.model
    def _expiry_alert_today(self, company):
        return fields.Date.context_today(
            self.with_context(
                tz=company.expiry_alert_responsible_user_id.tz or "UTC"
            )
        )

    @api.model
    def _expiry_alert_upper_bound(self, company, maximum_days):
        timezone = self._expiry_alert_timezone(company)
        next_day = self._expiry_alert_today(company) + timedelta(days=maximum_days + 1)
        local_boundary = timezone.localize(datetime.combine(next_day, time.min))
        return local_boundary.astimezone(pytz.UTC).replace(tzinfo=None)

    @api.model
    def _expiry_alert_thresholds(self, lot, company):
        value = lot.product_id.categ_id.expiry_alert_days or company.expiry_alert_days
        return self.env["stock.expiry.threshold.mixin"]._parse_expiry_alert_days(value)

    @api.model
    def _expiry_alert_maximum_days(self, company):
        parser = self.env["stock.expiry.threshold.mixin"]
        maximum = max(parser._parse_expiry_alert_days(company.expiry_alert_days), default=0)
        category_values = self.env["product.category"].search([
            ("expiry_alert_days", "!=", False),
        ]).mapped("expiry_alert_days")
        for value in category_values:
            maximum = max(maximum, max(parser._parse_expiry_alert_days(value), default=0))
        return maximum

    @api.model
    def _expiry_alert_days_remaining(self, lot, company):
        timezone_lot = lot.with_context(
            tz=company.expiry_alert_responsible_user_id.tz or "UTC"
        )
        expiration_day = fields.Datetime.context_timestamp(
            timezone_lot, lot.expiration_date
        ).date()
        return (expiration_day - self._expiry_alert_today(company)).days

    @api.model
    def _expiry_alert_activity_note(self, lot, company, quantity, days_remaining):
        expiration = fields.Datetime.context_timestamp(
            lot.with_context(tz=company.expiry_alert_responsible_user_id.tz or "UTC"),
            lot.expiration_date,
        )
        return Markup(
            "<p><strong>{title}</strong></p>"
            "<ul><li>{product_label}: {product}</li>"
            "<li>{lot_label}: {lot}</li>"
            "<li>{quantity_label}: {quantity}</li>"
            "<li>{expiration_label}: {expiration}</li>"
            "<li>{days_label}: {days}</li>"
            "<li>{company_label}: {company}</li></ul>"
        ).format(
            title=escape(_("Inventory Expired") if days_remaining <= 0 else _("Inventory Expiry Alert")),
            product_label=escape(_("Product")),
            product=escape(lot.product_id.display_name),
            lot_label=escape(_("Lot/Serial")),
            lot=escape(lot.display_name),
            quantity_label=escape(_("Available Quantity")),
            quantity=escape(lot.product_uom_id._compute_quantity(quantity, lot.product_uom_id)),
            expiration_label=escape(_("Expiration Date")),
            expiration=escape(fields.Datetime.to_string(expiration)),
            days_label=escape(_("Days Remaining")),
            days=escape(days_remaining),
            company_label=escape(_("Company")),
            company=escape(company.display_name),
        )

    @api.model
    def _expiry_alert_create_event(self, lot, company, quantity, days_remaining, threshold):
        event_domain = [
            ("company_id", "=", company.id),
            ("lot_id", "=", lot.id),
            ("expiration_date", "=", lot.expiration_date),
            ("threshold_days", "=", threshold),
        ]
        if self.env["stock.expiry.alert.event"].search_count(event_domain, limit=1):
            return self.env["stock.expiry.alert.event"]
        values = {
            "lot_id": lot.id,
            "product_id": lot.product_id.id,
            "company_id": company.id,
            "responsible_user_id": company.expiry_alert_responsible_user_id.id,
            "expiration_date": lot.expiration_date,
            "threshold_days": threshold,
            "days_remaining": days_remaining,
            "quantity": quantity,
        }
        try:
            with self.env.cr.savepoint():
                # The caller has already passed the manager/superuser gate. The
                # narrow elevation lets a manager-triggered run append immutable
                # history while stock users retain read-only access to it.
                event = self.env["stock.expiry.alert.event"].sudo().create(values)
                return event.with_env(self.env)
        except IntegrityError:
            _logger.info(
                "Expiry event already exists for company %s, lot %s, threshold %s",
                company.id,
                lot.id,
                threshold,
            )
            return self.env["stock.expiry.alert.event"]

    @api.model
    def _expiry_alert_notify(self, lot, company, quantity, days_remaining, threshold):
        event = self._expiry_alert_create_event(
            lot, company, quantity, days_remaining, threshold
        )
        if not event:
            return event

        expired = threshold == -1
        summary = _("Inventory Expired — %s", lot.display_name) if expired else _(
            "Inventory Expiry Alert — %s expires in %s days",
            lot.display_name,
            days_remaining,
        )
        activity = lot.activity_schedule(
            "stock_expiry_alerts.mail_activity_type_inventory_expiry",
            date_deadline=self._expiry_alert_today(company),
            summary=summary,
            note=self._expiry_alert_activity_note(
                lot, company, quantity, days_remaining
            ),
            user_id=company.expiry_alert_responsible_user_id.id,
        )
        event.sudo().activity_id = activity

        responsible = company.expiry_alert_responsible_user_id
        if company.expiry_alert_send_email and responsible.email:
            mail_id = self.env.ref(
                "stock_expiry_alerts.mail_template_inventory_expiry_alert"
            ).send_mail(event.id, force_send=False)
            event.sudo().email_sent = bool(mail_id)
        elif company.expiry_alert_send_email:
            _logger.warning(
                "Expiry email skipped for company %s because responsible user %s has no email",
                company.display_name,
                responsible.display_name,
            )
        return event

    @api.model
    def _expiry_alert_process_company(self, company):
        maximum_days = self._expiry_alert_maximum_days(company)
        upper_bound = self._expiry_alert_upper_bound(company, maximum_days)
        last_lot_id = 0
        events = self.env["stock.expiry.alert.event"]
        while True:
            lots = self.with_company(company).with_context(active_test=False).search(
                [
                    ("id", ">", last_lot_id),
                    ("company_id", "in", [False, company.id]),
                    ("expiration_date", "!=", False),
                    ("expiration_date", "<", upper_bound),
                    ("product_id.use_expiration_date", "=", True),
                ],
                order="id",
                limit=self._EXPIRY_ALERT_BATCH_SIZE,
            )
            if not lots:
                break
            last_lot_id = lots[-1].id
            quantity_rows = self.env["stock.quant"].with_company(company)._read_group(
                [
                    ("company_id", "=", company.id),
                    ("lot_id", "in", lots.ids),
                    ("location_id.usage", "=", "internal"),
                ],
                groupby=["lot_id"],
                aggregates=["quantity:sum"],
            )
            quantities = {lot.id: quantity for lot, quantity in quantity_rows}
            for lot in lots:
                quantity = quantities.get(lot.id, 0.0)
                if float_compare(
                    quantity,
                    0.0,
                    precision_rounding=lot.product_uom_id.rounding,
                ) <= 0:
                    continue
                days_remaining = self._expiry_alert_days_remaining(lot, company)
                if days_remaining <= 0:
                    threshold = -1 if company.expiry_alert_notify_expired else None
                else:
                    thresholds = self._expiry_alert_thresholds(lot, company)
                    threshold = days_remaining if days_remaining in thresholds else None
                if threshold is not None:
                    events |= self._expiry_alert_notify(
                        lot, company, quantity, days_remaining, threshold
                    )
        return events

    @api.model
    def _cron_check_inventory_expiry_alerts(self):
        """Create exact-day and one-time expired alerts for enabled companies."""
        self._expiry_alert_check_access()
        companies = self.env["res.company"].search([
            ("expiry_alert_enabled", "=", True),
            ("expiry_alert_responsible_user_id", "!=", False),
        ])
        events = self.env["stock.expiry.alert.event"]
        for company in companies:
            events |= self._expiry_alert_process_company(company)
        return events
