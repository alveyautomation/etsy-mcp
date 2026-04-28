"""Synthetic fixtures used across the test suite.

All identifiers, names, and SKUs are invented for testing. Any resemblance
to a real Etsy shop is coincidental, this file must never gain real-world
identifiers.
"""

from __future__ import annotations

# Sandbox ShopIDs for the test fixtures only. Pick deliberately unrealistic
# numbers so it's obvious if they ever leak into a real API call by accident.
SANDBOX_SHOP_PRIMARY = 90001
SANDBOX_SHOP_SECONDARY = 90002

SAMPLE_TOKEN_RESPONSE = {
    "access_token": "test-access-token-please-do-not-use-in-production",
    "refresh_token": "test-refresh-token-rotated",
    "expires_in": 3600,
    "token_type": "Bearer",
}

SAMPLE_LISTING = {
    "listing_id": 1234567890,
    "shop_id": SANDBOX_SHOP_PRIMARY,
    "title": "Lorem Ipsum Handmade Widget. Sample Listing",
    "description": "A perfectly cromulent widget for testing purposes.",
    "state": "active",
    "price": {"amount": 2999, "divisor": 100, "currency_code": "USD"},
    "quantity": 12,
    "url": "https://www.etsy.invalid/listing/1234567890",
    "tags": ["lorem", "ipsum", "widget"],
}

SAMPLE_LISTING_SEARCH = {
    "count": 2,
    "results": [
        SAMPLE_LISTING,
        {
            "listing_id": 1234567891,
            "shop_id": SANDBOX_SHOP_PRIMARY,
            "title": "Lorem Ipsum Handmade Widget. Deluxe",
            "state": "active",
            "price": {"amount": 4999, "divisor": 100, "currency_code": "USD"},
            "quantity": 4,
        },
    ],
}

SAMPLE_SHOP = {
    "shop_id": SANDBOX_SHOP_PRIMARY,
    "shop_name": "LoremIpsumStudio",
    "user_id": 7000001,
    "currency_code": "USD",
    "listing_active_count": 87,
    "num_favorers": 314,
    "url": "https://www.etsy.invalid/shop/LoremIpsumStudio",
    "is_vacation": False,
}

SAMPLE_RECEIPT_DETAIL = {
    "receipt_id": 5550001,
    "shop_id": SANDBOX_SHOP_PRIMARY,
    "buyer_user_id": 8000001,
    "status": "completed",
    "grandtotal": {"amount": 5998, "divisor": 100, "currency_code": "USD"},
    "subtotal": {"amount": 5598, "divisor": 100, "currency_code": "USD"},
    "transactions": [
        {
            "transaction_id": 9000001,
            "listing_id": 1234567890,
            "title": "Lorem Ipsum Handmade Widget. Sample Listing",
            "quantity": 1,
            "price": {"amount": 2999, "divisor": 100, "currency_code": "USD"},
        },
        {
            "transaction_id": 9000002,
            "listing_id": 1234567891,
            "title": "Lorem Ipsum Handmade Widget. Deluxe",
            "quantity": 1,
            "price": {"amount": 2599, "divisor": 100, "currency_code": "USD"},
        },
    ],
}

SAMPLE_RECEIPTS_PAGE_1 = {
    "count": 3,
    "results": [
        {
            "receipt_id": 5550001,
            "shop_id": SANDBOX_SHOP_PRIMARY,
            "status": "completed",
            "grandtotal": {"amount": 5998, "divisor": 100, "currency_code": "USD"},
        },
        {
            "receipt_id": 5550002,
            "shop_id": SANDBOX_SHOP_PRIMARY,
            "status": "completed",
            "grandtotal": {"amount": 1250, "divisor": 100, "currency_code": "USD"},
        },
    ],
}

SAMPLE_RECEIPTS_PAGE_2 = {
    "count": 3,
    "results": [
        {
            "receipt_id": 5550003,
            "shop_id": SANDBOX_SHOP_PRIMARY,
            "status": "open",
            "grandtotal": {"amount": 19900, "divisor": 100, "currency_code": "USD"},
        }
    ],
}

SAMPLE_INVENTORY = {
    "products": [
        {
            "product_id": 6000001,
            "sku": "LOREM-WIDGET-RED",
            "property_values": [
                {"property_id": 200, "property_name": "Color", "values": ["Red"]}
            ],
            "offerings": [
                {
                    "offering_id": 6500001,
                    "quantity": 8,
                    "is_enabled": True,
                    "price": {
                        "amount": 2999,
                        "divisor": 100,
                        "currency_code": "USD",
                    },
                }
            ],
        },
        {
            "product_id": 6000002,
            "sku": "LOREM-WIDGET-BLUE",
            "property_values": [
                {"property_id": 200, "property_name": "Color", "values": ["Blue"]}
            ],
            "offerings": [
                {
                    "offering_id": 6500002,
                    "quantity": 4,
                    "is_enabled": True,
                    "price": {
                        "amount": 2999,
                        "divisor": 100,
                        "currency_code": "USD",
                    },
                }
            ],
        },
    ],
}

SAMPLE_ACTIVE_LISTINGS_PAGE_1 = {
    "count": 3,
    "results": [
        {
            "listing_id": 1234567890,
            "shop_id": SANDBOX_SHOP_PRIMARY,
            "title": "Lorem Ipsum Handmade Widget. Sample Listing",
            "state": "active",
            "quantity": 12,
        },
        {
            "listing_id": 1234567891,
            "shop_id": SANDBOX_SHOP_PRIMARY,
            "title": "Lorem Ipsum Handmade Widget. Deluxe",
            "state": "active",
            "quantity": 4,
        },
    ],
}

SAMPLE_ACTIVE_LISTINGS_PAGE_2 = {
    "count": 3,
    "results": [
        {
            "listing_id": 1234567892,
            "shop_id": SANDBOX_SHOP_PRIMARY,
            "title": "Lorem Ipsum Handmade Widget. Mini",
            "state": "active",
            "quantity": 22,
        }
    ],
}
