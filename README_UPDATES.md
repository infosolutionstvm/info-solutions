# Info Solutions — update notes

## Safe database upgrade

Start the application normally. At startup it adds only missing quotation fields and performance indexes; it does not delete or rewrite existing customer, quotation, service, or payment records.

## Included changes

- CRM customers can be selected when creating a service ticket or quotation. Name, phone, and saved address are prefilled.
- Creating or editing a quotation saves the customer back to CRM.
- Quotations now have an editable issue date, advance amount, and advance payment method.
- A quotation advance automatically appears in Payments & Collections under the quotation number. Editing it updates that linked advance record without removing any other payment history.
- Printable quotations tolerate malformed historic item data, safely escape customer/item text, and handle a missing date without breaking the preview.
- The sidebar keeps the daily workflow first and groups catalogue, reports, and staff tools under Administration & reports.
- The interface has a consistent navy, teal, and white theme. Database indexes and bounded quotation loading improve common screen responsiveness.
- Database schema initialization now runs once per app session rather than after every navigation click. Product, customer-picker, and staff lists are cached briefly and refreshed immediately after updates.

## Run

1. Install dependencies: `pip install -r requirements.txt`
2. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, then add your existing Supabase/Postgres credentials. The ZIP intentionally does not contain passwords.
3. Run: `streamlit run app.py`

The application will run the schema upgrades automatically on its first launch.
