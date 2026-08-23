# Copyright (C) 2026 Yerevan Digital Co
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from datetime import datetime, time, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestStockExpiryAlerts(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.responsible = cls.env.user
        cls.responsible.tz = "UTC"
        cls.company.write({
            "expiry_alert_enabled": True,
            "expiry_alert_days": "30, 15, 7, 3, 1",
            "expiry_alert_responsible_user_id": cls.responsible.id,
            "expiry_alert_send_email": False,
            "expiry_alert_notify_expired": True,
        })
        cls.location = cls.env["stock.location"].create({
            "name": "Expiry Alerts Test Shelf",
            "usage": "internal",
            "location_id": cls.env.ref("stock.stock_location_stock").id,
            "company_id": cls.company.id,
        })
        cls.category = cls.env["product.category"].create({
            "name": "Expiry Alerts Test Category",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Expiry Alerts Test Product",
            "is_storable": True,
            "tracking": "lot",
            "use_expiration_date": True,
            "categ_id": cls.category.id,
        })
        cls.Lot = cls.env["stock.lot"]
        cls.Event = cls.env["stock.expiry.alert.event"]
        cls.activity_type = cls.env.ref(
            "stock_expiry_alerts.mail_activity_type_inventory_expiry"
        )

    def _expiration(self, offset):
        return datetime.combine(fields.Date.today() + timedelta(days=offset), time(12))

    def _create_lot(
        self,
        name,
        offset=None,
        quantity=1.0,
        product=None,
        company=None,
        location=None,
    ):
        product = product or self.product
        company = company or self.company
        location = location or self.location
        values = {
            "name": name,
            "product_id": product.id,
            "company_id": company.id,
        }
        if offset is not None:
            values["expiration_date"] = self._expiration(offset)
        lot = self.Lot.with_company(company).create(values)
        if offset is None:
            lot.expiration_date = False
        if quantity:
            self.env["stock.quant"].with_company(company)._update_available_quantity(
                product, location, quantity, lot_id=lot
            )
        return lot

    def _run(self):
        return self.Lot._cron_check_inventory_expiry_alerts()

    def _events(self, lot):
        return self.Event.search([("lot_id", "=", lot.id)])

    def _activities(self, lot):
        return self.env["mail.activity"].search([
            ("res_model", "=", "stock.lot"),
            ("res_id", "=", lot.id),
            ("activity_type_id", "=", self.activity_type.id),
        ])

    def test_01_thirty_day_alert_is_generated(self):
        lot = self._create_lot("ALERT-30", 30, 5)
        self._run()
        self.assertEqual(self._events(lot).threshold_days, 30)
        self.assertEqual(len(self._activities(lot)), 1)

    def test_02_seven_day_alert_is_generated(self):
        lot = self._create_lot("ALERT-7", 7, 2)
        self._run()
        self.assertEqual(self._events(lot).threshold_days, 7)

    def test_03_no_alert_outside_thresholds(self):
        lot = self._create_lot("ALERT-8", 8, 2)
        self._run()
        self.assertFalse(self._events(lot))

    def test_04_duplicate_alert_is_not_generated(self):
        lot = self._create_lot("ALERT-DEDUPE", 15, 2)
        self._run()
        self._run()
        self.assertEqual(len(self._events(lot)), 1)
        self.assertEqual(len(self._activities(lot)), 1)

    def test_05_zero_stock_lot_is_ignored(self):
        lot = self._create_lot("ALERT-ZERO", 7, 0)
        self._run()
        self.assertFalse(self._events(lot))

    def test_06_lot_without_expiration_is_ignored(self):
        lot = self._create_lot("ALERT-NO-DATE", None, 2)
        self._run()
        self.assertFalse(self._events(lot))

    def test_07_expired_notification_is_generated_once(self):
        lot = self._create_lot("ALERT-EXPIRED", -5, 2)
        self._run()
        self._run()
        self.assertEqual(len(self._events(lot)), 1)
        self.assertEqual(self._events(lot).threshold_days, -1)
        self.assertEqual(len(self._activities(lot)), 1)

    def test_08_activity_is_assigned_to_responsible_user(self):
        lot = self._create_lot("ALERT-ASSIGNEE", 3, 2)
        self._run()
        self.assertEqual(self._activities(lot).user_id, self.responsible)

    def test_09_email_is_queued_when_enabled(self):
        self.company.expiry_alert_send_email = True
        self.responsible.email = "expiry-responsible@example.com"
        lot = self._create_lot("ALERT-EMAIL", 1, 2)
        before = self.env["mail.mail"].search_count([])
        self._run()
        self.assertTrue(self._events(lot).email_sent)
        self.assertEqual(self.env["mail.mail"].search_count([]), before + 1)

    def test_10_email_is_not_queued_when_disabled(self):
        self.company.expiry_alert_send_email = False
        lot = self._create_lot("ALERT-NO-EMAIL", 1, 2)
        before = self.env["mail.mail"].search_count([])
        self._run()
        self.assertFalse(self._events(lot).email_sent)
        self.assertEqual(self.env["mail.mail"].search_count([]), before)

    def test_11_category_thresholds_override_global_thresholds(self):
        self.category.expiry_alert_days = "14, 7"
        category_lot = self._create_lot("ALERT-CATEGORY-14", 14, 2)
        excluded_global_lot = self._create_lot("ALERT-CATEGORY-30", 30, 2)
        self._run()
        self.assertEqual(self._events(category_lot).threshold_days, 14)
        self.assertFalse(self._events(excluded_global_lot))

    def test_12_global_thresholds_apply_without_category_override(self):
        self.category.expiry_alert_days = False
        lot = self._create_lot("ALERT-GLOBAL", 15, 2)
        self._run()
        self.assertEqual(self._events(lot).threshold_days, 15)

    def test_13_multi_company_configuration_is_isolated(self):
        other_company = self.env["res.company"].create({"name": "Expiry Alert Other Co"})
        self.responsible.company_ids = [Command.link(other_company.id)]
        other_company.write({
            "expiry_alert_enabled": False,
            "expiry_alert_days": "7",
            "expiry_alert_responsible_user_id": self.responsible.id,
        })
        other_warehouse = self.env["stock.warehouse"].create({
            "name": "Expiry Alert Other Warehouse",
            "code": "EAOT",
            "company_id": other_company.id,
        })
        lot = self._create_lot(
            "ALERT-OTHER-COMPANY",
            7,
            2,
            company=other_company,
            location=other_warehouse.lot_stock_id,
        )
        self._run()
        self.assertFalse(self._events(lot))
        other_company.expiry_alert_enabled = True
        self._run()
        self.assertEqual(self._events(lot).company_id, other_company)

    def test_14_multiple_lots_are_handled_independently(self):
        first = self._create_lot("ALERT-MULTI-1", 7, 2)
        second = self._create_lot("ALERT-MULTI-2", 7, 3)
        self._run()
        self.assertEqual(len(self._events(first)), 1)
        self.assertEqual(len(self._events(second)), 1)

    def test_15_rerunning_cron_does_not_duplicate_activity_or_email(self):
        self.company.expiry_alert_send_email = True
        self.responsible.email = "expiry-rerun@example.com"
        lot = self._create_lot("ALERT-RERUN", 3, 2)
        before = self.env["mail.mail"].search_count([])
        self._run()
        self._run()
        self.assertEqual(len(self._events(lot)), 1)
        self.assertEqual(len(self._activities(lot)), 1)
        self.assertEqual(self.env["mail.mail"].search_count([]), before + 1)

    def test_16_inventory_user_cannot_invoke_cron(self):
        user = new_test_user(
            self.env,
            login="expiry-alert-stock-user",
            groups="base.group_user,stock.group_stock_user",
            company_id=self.company.id,
        )
        with self.assertRaises(AccessError):
            self.Lot.with_user(user)._cron_check_inventory_expiry_alerts()

    def test_17_inventory_user_can_read_derived_dashboard_alert_status(self):
        lot = self._create_lot("ALERT-DASHBOARD-USER", 7, 2)
        self._run()
        user = new_test_user(
            self.env,
            login="expiry-alert-dashboard-user",
            groups="base.group_user,stock.group_stock_user",
            company_id=self.company.id,
        )
        line = self.env["stock.expiry.dashboard.line"].with_user(user).search([
            ("lot_id", "=", lot.id),
        ], limit=1)
        self.assertTrue(line)
        self.assertTrue(line.alert_sent)
        self.assertTrue(line.last_alert_date)

    def test_18_stock_manager_can_open_read_and_save_dedicated_settings(self):
        manager = new_test_user(
            self.env,
            login="expiry-alert-settings-manager",
            groups="base.group_user,stock.group_stock_manager",
            company_id=self.company.id,
        )
        Settings = self.env["stock.expiry.alert.settings"].with_user(manager).with_company(
            self.company
        )
        defaults = Settings.default_get([
            "company_id",
            "expiry_alert_enabled",
            "expiry_alert_days",
            "expiry_alert_responsible_user_id",
            "expiry_alert_send_email",
            "expiry_alert_notify_expired",
        ])
        self.assertEqual(defaults["company_id"], self.company.id)
        self.assertEqual(defaults["expiry_alert_days"], "30, 15, 7, 3, 1")
        view = Settings.get_view(
            view_id=self.env.ref(
                "stock_expiry_alerts.view_stock_expiry_alert_settings_form"
            ).id,
            view_type="form",
        )
        self.assertIn("expiry_alert_responsible_user_id", view["arch"])
        self.assertIn('name="action_save"', view["arch"])
        self.assertIn("<footer>", view["arch"])
        action_definition = self.env["ir.actions.actions"].with_user(manager)._for_xml_id(
            "stock_expiry_alerts.action_stock_expiry_alert_settings"
        )
        self.assertEqual(action_definition["res_model"], "stock.expiry.alert.settings")
        self.assertEqual(action_definition["target"], "new")
        menu = self.env.ref(
            "stock_expiry_alerts.menu_stock_expiry_alert_settings"
        ).with_user(manager)
        menu.check_access("read")
        self.assertIn(self.env.ref("stock.group_stock_manager"), menu.group_ids)
        settings = Settings.create({
            "company_id": self.company.id,
            "expiry_alert_enabled": True,
            "expiry_alert_days": "7, 30, 7, 1",
            "expiry_alert_responsible_user_id": manager.id,
            "expiry_alert_send_email": True,
            "expiry_alert_notify_expired": False,
        })
        action = settings.action_save()
        self.company.invalidate_recordset()
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(self.company.expiry_alert_days, "30, 7, 1")
        self.assertEqual(self.company.expiry_alert_responsible_user_id, manager)
        self.assertTrue(self.company.expiry_alert_send_email)
        self.assertFalse(self.company.expiry_alert_notify_expired)

    def test_19_dedicated_settings_do_not_grant_general_settings_or_company_write(self):
        manager = new_test_user(
            self.env,
            login="expiry-alert-scoped-settings-manager",
            groups="base.group_user,stock.group_stock_manager",
            company_id=self.company.id,
        )
        with self.assertRaises(AccessError):
            self.env["res.config.settings"].with_user(manager).create({})
        with self.assertRaises(AccessError):
            self.company.with_user(manager).write({"name": "Unauthorized Rename"})

        other_company = self.env["res.company"].create({
            "name": "Expiry Alert Unauthorized Company",
        })
        with self.assertRaises(AccessError):
            self.env["stock.expiry.alert.settings"].with_user(manager).create({
                "company_id": other_company.id,
                "expiry_alert_enabled": False,
                "expiry_alert_days": "7",
            })

    def test_20_stock_user_cannot_access_dedicated_settings(self):
        user = new_test_user(
            self.env,
            login="expiry-alert-settings-stock-user",
            groups="base.group_user,stock.group_stock_user",
            company_id=self.company.id,
        )
        with self.assertRaises(AccessError):
            self.env["stock.expiry.alert.settings"].with_user(user).create({
                "company_id": self.company.id,
                "expiry_alert_enabled": False,
                "expiry_alert_days": "7",
            })
