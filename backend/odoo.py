"""Read-only JSON-2 boundary. No create/write/unlink or guessed pricing methods."""

import os, re
import httpx
import keyring

SERVICE = "BarcodeStudio.Odoo"


def configure(url, database, key):
    if not re.fullmatch(r"https://[a-zA-Z0-9][a-zA-Z0-9.-]*\.odoo\.com", url):
        raise ValueError(
            "Use your HTTPS *.odoo.com SaaS address without a trailing slash"
        )
    if not database or len(database) > 100:
        raise ValueError("Database name required")
    if os.name != "nt":
        raise ValueError(
            "Persistent credential setup requires Windows Credential Manager; use backend ODOO_URL, ODOO_DATABASE, ODOO_API_KEY for development"
        )
    from keyring.backends.Windows import WinVaultKeyring

    vault = WinVaultKeyring()
    vault.set_password(SERVICE, "api_key", key)
    vault.set_password(SERVICE, "url", url)
    vault.set_password(SERVICE, "database", database)


def credentials():
    if os.name == "nt":
        from keyring.backends.Windows import WinVaultKeyring

        vault = WinVaultKeyring()
        return tuple(
            vault.get_password(SERVICE, k) for k in ("url", "database", "api_key")
        )
    return tuple(
        os.environ.get(k) for k in ("ODOO_URL", "ODOO_DATABASE", "ODOO_API_KEY")
    )


def disconnect():
    if os.name == "nt":
        from keyring.backends.Windows import WinVaultKeyring

        v = WinVaultKeyring()
        for k in ("url", "database", "api_key"):
            if v.get_password(SERVICE, k):
                v.delete_password(SERVICE, k)


def call(model, method, payload):
    allowed = {
        "product.product": {"search_read", "fields_get"},
        "res.currency": {"search_read"},
        "product.pricelist": {"search_read"},
    }
    if method not in allowed.get(model, set()):
        raise ValueError("Operation is not an approved read-only operation")
    url, db, key = credentials()
    if not all((url, db, key)):
        raise ValueError("Configure Odoo credentials in the backend first")
    if not re.fullmatch(r"https://[a-zA-Z0-9][a-zA-Z0-9.-]*\.odoo\.com", url):
        raise ValueError("Invalid Odoo SaaS URL")
    try:
        with httpx.Client(timeout=20, follow_redirects=False) as c:
            r = c.post(
                f"{url}/json/2/{model}/{method}",
                headers={"Authorization": f"bearer {key}", "X-Odoo-Database": db},
                json=payload,
            )
        if r.status_code != 200:
            raise ValueError(
                f"Odoo returned HTTP {r.status_code}; check API permissions, plan and database /doc"
            )
        return r.json()
    except (httpx.HTTPError, ValueError) as e:
        if isinstance(e, ValueError) and str(e).startswith("Odoo returned"):
            raise
        raise ValueError(
            "Odoo request failed; check network and database configuration"
        ) from None


def products(search, offset=0):
    domain = (
        [
            "|",
            "|",
            ["name", "ilike", search],
            ["barcode", "ilike", search],
            ["default_code", "ilike", search],
        ]
        if search
        else []
    )
    return call(
        "product.product",
        "search_read",
        {
            "domain": domain,
            "fields": [
                "id",
                "display_name",
                "barcode",
                "default_code",
                "lst_price",
                "currency_id",
            ],
            "limit": 100,
            "offset": offset,
            "order": "id",
        },
    )


def pricelist_price(*args, **kwargs):
    raise ValueError(
        "Pricelist calculation is blocked until an authorized public operation is verified against this database /doc; no prices have been guessed"
    )
