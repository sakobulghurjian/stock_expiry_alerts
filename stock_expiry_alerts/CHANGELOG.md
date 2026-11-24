# Changelog

## 20.0.1.0.0

- Ported to Odoo 20 Community.
- Convert access lists and the multi-company record rule to Odoo 20 `ir.access`.
- Follow the Odoo 20 rename of `stock.lot.product_uom_id` to `uom_id` and use the new unit rounding API.
- Use Odoo 20 Material Symbols icons on alert buttons.

## 19.0.1.0.0

- Add company-specific expiry alert settings and category threshold overrides.
- Add batched daily internal-stock checks for exact-day and expired-once alerts.
- Add assigned lot activities and optional standard Odoo email notifications.
- Add durable per-expiration-lifecycle event deduplication and read-only history.
- Extend the free expiry dashboard with alert status and next-threshold fields.
- Add focused coverage for all 15 requested notification scenarios.
- Add a narrowly scoped Inventory-manager settings screen without granting
  access to general system settings or unrelated company data.
- Open the manager settings screen as a modal so its audited Save action is
  rendered and invoked instead of merely storing a transient record.
