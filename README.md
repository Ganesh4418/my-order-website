# Single Product Order Website (Flask)

This project is based on the uploaded `app.py` and configured for one product. It has no delivery-fee field in the SQLite orders table. The total is the product price multiplied by quantity.

## Run on Windows / VS Code

1. Extract the ZIP.
2. Open the `order_website` folder in VS Code.
3. Open Terminal and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

4. Open `http://127.0.0.1:5000`.

If PowerShell blocks virtual-environment activation, run `python -m pip install -r requirements.txt` and then `python app.py` without activating it.

## Customize

Edit `app.py` and the single item in `PRODUCTS`:
- `name`: product name
- `description`: description
- `price`: price in rupees
- `image`: currently `/static/RSDW.jpeg`

Replace `static/RSDW.jpeg` with your own product image (keep the same filename or update the `image` value). Change `My Store` in `templates/base.html` to your site name.

Configure Twilio SMS in your hosting environment using `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, and `VENDOR_SMS_NUMBER`. When configured, the order is saved and an SMS is sent from the business Twilio sender to the vendor. The customer phone is only included as order contact information; it is not the SMS sender. If SMS settings are missing, the order is saved but the vendor SMS is not sent.

## Database

`orders.db` is included as an empty database with no `delivery_fee` column. `app.py` creates the same table if it does not exist. If your old database has a delivery-fee column and you want a clean database, stop the server and back up/delete the old `orders.db` before running again. Keep a backup if you need previous orders.

## Legal note

This sample product is an alcoholic beverage. Use the website only where permitted, comply with local licensing, age-verification, delivery and other applicable requirements, and do not accept orders from ineligible customers. The checkout includes an age/legal eligibility confirmation, but that checkbox is not a substitute for proper verification or legal compliance.

The checkout requires the customer to confirm legal-age/local-law eligibility. This is only an acknowledgment, not identity or age verification.
