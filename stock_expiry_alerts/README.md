# Inventory Expiry Alerts

Inventory Expiry Alerts is a focused Odoo 20 Community addon that creates
activities—and optionally emails—when physically stocked lots or serials reach
configured expiration thresholds. It extends the free `stock_expiry_dashboard`
addon without changing its reporting workflow.

## Configure

Inventory managers configure each active company through **Inventory >
Configuration > Expiry Alerts**. System administrators can also use **Inventory
> Configuration > Settings > Expiry Alerts**; the general Settings integration
is preserved for them.

- enable alerts;
- enter comma-separated exact-day thresholds such as `30, 15, 7, 3, 1`;
- select one responsible internal user;
- optionally enable email and the one-time expired notification.

On a product category, **Expiry Alert Days Override** replaces the company
thresholds for products in that category. Leave it empty to use the company
defaults.

## Behavior

The daily scheduled action processes enabled companies independently. It scans
expiration-dated lots in bounded batches and aggregates current physical
quantity from internal-location quants. Customer, supplier, scrap, inventory,
and historical stock-move quantities do not trigger alerts.

Positive thresholds are exact-day checks: a 7-day threshold alerts at 7 days,
not after that day has passed. The optional expired event applies once when the
local expiration day is reached or passed. A database uniqueness constraint on
company, lot, expiration timestamp, and threshold prevents duplicate events,
activities, and emails even when the cron is rerun. Changing a lot's expiration
timestamp starts a new expiration lifecycle.

The responsible user's timezone defines the local expiration day for that
company. The responsible user receives an activity linked to the lot. When email
is enabled and the user has an email address, Odoo queues a standard template
email. Missing email addresses never prevent the activity.

Inventory users can open **Inventory > Expiry Alert History**. The free dashboard
detail list also shows whether an alert was sent, its latest date, and the next
pending threshold.

## Security

Only Inventory Managers can configure or manually invoke alert processing. The
dedicated manager screen saves an audited whitelist of the five expiry fields
with narrow elevation; it does not grant access to general Odoo Settings or
unrelated company fields.
Inventory users have read-only access to event history, restricted to their
allowed companies. Activities and lot access continue to use Odoo's standard
mail and Inventory permissions. No controller, external service, raw SQL, or
broad stock-data elevation is introduced.

## Installation and update

Install `stock_expiry_dashboard` first, then install `stock_expiry_alerts`. After
deploying a newer version, update the module in a disposable/staged database
before production:

```text
odoo-bin -d <database> -u stock_expiry_alerts --stop-after-init
```

Run focused tests with:

```text
odoo-bin -d <disposable_database> --test-enable \
  --test-tags /stock_expiry_alerts --stop-after-init
```
