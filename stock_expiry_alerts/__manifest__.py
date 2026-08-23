# Copyright (C) 2026 Yerevan Digital Co
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

{
    "name": "Inventory Expiry Alerts",
    "summary": "Notify responsible users before stocked lots and serials expire",
    "version": "19.0.1.0.0",
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "author": "Yerevan Digital Co",
    "maintainer": "Yerevan Digital Co",
    "website": "https://yerevandigital.com/",
    "support": "info@yerevandigital.com",
    "price": 9.99,
    "currency": "USD",
    "depends": [
        "stock_expiry_dashboard",
        "mail",
    ],
    "data": [
        "security/stock_expiry_alert_security.xml",
        "security/ir.model.access.csv",
        "data/mail_activity_type_data.xml",
        "data/mail_template_data.xml",
        "data/ir_cron_data.xml",
        "views/stock_expiry_alert_settings_views.xml",
        "views/res_config_settings_views.xml",
        "views/product_category_views.xml",
        "views/stock_expiry_alert_event_views.xml",
        "views/stock_expiry_dashboard_views.xml",
    ],
    "images": [
        "static/description/banner.png",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
