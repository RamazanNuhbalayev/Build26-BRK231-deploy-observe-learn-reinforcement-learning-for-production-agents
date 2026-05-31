"""Retail Tools – Azure Function App with 6 agentic tools for multi-turn RFT."""
import json
import re
import hashlib
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

try:
    import azure.functions as func
    from azure.functions import AsgiFunctionApp
    HAS_AZ = True
except ImportError:
    HAS_AZ = False

# ---------------------------------------------------------------------------
# In-memory database
# ---------------------------------------------------------------------------
TODAY = datetime(2026, 7, 15)
TODAY_STR = "2026-07-15"

DB = json.loads("""
{
  "today": "2026-07-15",
  "customers": {
    "C001": {
      "id": "C001",
      "name": "Sofia Martinez",
      "email": "sofia.martinez@example.com",
      "loyalty_tier": "platinum"
    },
    "C002": {
      "id": "C002",
      "name": "Ava Chen",
      "email": "ava.chen@example.com",
      "loyalty_tier": "standard"
    },
    "C003": {
      "id": "C003",
      "name": "Yusuf Rossi",
      "email": "yusuf.rossi@example.com",
      "loyalty_tier": "gold"
    },
    "C004": {
      "id": "C004",
      "name": "Emma Kim",
      "email": "emma.kim@example.com",
      "loyalty_tier": "standard"
    },
    "C005": {
      "id": "C005",
      "name": "Noah Brown",
      "email": "noah.brown@example.com",
      "loyalty_tier": "platinum"
    }
  },
  "products": {
    "P001": {
      "id": "P001",
      "name": "Wireless Headphones",
      "category": "electronics",
      "price": 149.99,
      "on_sale": false
    },
    "P002": {
      "id": "P002",
      "name": "Mechanical Keyboard",
      "category": "electronics",
      "price": 129.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P002-BLK",
          "variant": "Black"
        },
        {
          "sku": "P002-WHT",
          "variant": "White"
        },
        {
          "sku": "P002-RGB",
          "variant": "RGB"
        }
      ]
    },
    "P002-BLK": {
      "id": "P002",
      "name": "Mechanical Keyboard",
      "category": "electronics",
      "price": 129.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P002-BLK",
          "variant": "Black"
        },
        {
          "sku": "P002-WHT",
          "variant": "White"
        },
        {
          "sku": "P002-RGB",
          "variant": "RGB"
        }
      ],
      "selected_variant": "Black"
    },
    "P002-WHT": {
      "id": "P002",
      "name": "Mechanical Keyboard",
      "category": "electronics",
      "price": 129.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P002-BLK",
          "variant": "Black"
        },
        {
          "sku": "P002-WHT",
          "variant": "White"
        },
        {
          "sku": "P002-RGB",
          "variant": "RGB"
        }
      ],
      "selected_variant": "White"
    },
    "P002-RGB": {
      "id": "P002",
      "name": "Mechanical Keyboard",
      "category": "electronics",
      "price": 129.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P002-BLK",
          "variant": "Black"
        },
        {
          "sku": "P002-WHT",
          "variant": "White"
        },
        {
          "sku": "P002-RGB",
          "variant": "RGB"
        }
      ],
      "selected_variant": "RGB"
    },
    "P003": {
      "id": "P003",
      "name": "Smart Watch",
      "category": "electronics",
      "price": 299.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P003-S",
          "variant": "Small"
        },
        {
          "sku": "P003-M",
          "variant": "Medium"
        },
        {
          "sku": "P003-L",
          "variant": "Large"
        }
      ]
    },
    "P003-S": {
      "id": "P003",
      "name": "Smart Watch",
      "category": "electronics",
      "price": 299.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P003-S",
          "variant": "Small"
        },
        {
          "sku": "P003-M",
          "variant": "Medium"
        },
        {
          "sku": "P003-L",
          "variant": "Large"
        }
      ],
      "selected_variant": "Small"
    },
    "P003-M": {
      "id": "P003",
      "name": "Smart Watch",
      "category": "electronics",
      "price": 299.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P003-S",
          "variant": "Small"
        },
        {
          "sku": "P003-M",
          "variant": "Medium"
        },
        {
          "sku": "P003-L",
          "variant": "Large"
        }
      ],
      "selected_variant": "Medium"
    },
    "P003-L": {
      "id": "P003",
      "name": "Smart Watch",
      "category": "electronics",
      "price": 299.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P003-S",
          "variant": "Small"
        },
        {
          "sku": "P003-M",
          "variant": "Medium"
        },
        {
          "sku": "P003-L",
          "variant": "Large"
        }
      ],
      "selected_variant": "Large"
    },
    "P004": {
      "id": "P004",
      "name": "Bluetooth Speaker",
      "category": "electronics",
      "price": 79.99,
      "on_sale": false
    },
    "P005": {
      "id": "P005",
      "name": "Electric Kettle",
      "category": "electronics",
      "price": 59.99,
      "on_sale": false
    },
    "P006": {
      "id": "P006",
      "name": "Merino Wool Sweater",
      "category": "apparel",
      "price": 89.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P006-S",
          "variant": "Small"
        },
        {
          "sku": "P006-M",
          "variant": "Medium"
        },
        {
          "sku": "P006-L",
          "variant": "Large"
        },
        {
          "sku": "P006-XL",
          "variant": "XL"
        }
      ]
    },
    "P006-S": {
      "id": "P006",
      "name": "Merino Wool Sweater",
      "category": "apparel",
      "price": 89.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P006-S",
          "variant": "Small"
        },
        {
          "sku": "P006-M",
          "variant": "Medium"
        },
        {
          "sku": "P006-L",
          "variant": "Large"
        },
        {
          "sku": "P006-XL",
          "variant": "XL"
        }
      ],
      "selected_variant": "Small"
    },
    "P006-M": {
      "id": "P006",
      "name": "Merino Wool Sweater",
      "category": "apparel",
      "price": 89.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P006-S",
          "variant": "Small"
        },
        {
          "sku": "P006-M",
          "variant": "Medium"
        },
        {
          "sku": "P006-L",
          "variant": "Large"
        },
        {
          "sku": "P006-XL",
          "variant": "XL"
        }
      ],
      "selected_variant": "Medium"
    },
    "P006-L": {
      "id": "P006",
      "name": "Merino Wool Sweater",
      "category": "apparel",
      "price": 89.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P006-S",
          "variant": "Small"
        },
        {
          "sku": "P006-M",
          "variant": "Medium"
        },
        {
          "sku": "P006-L",
          "variant": "Large"
        },
        {
          "sku": "P006-XL",
          "variant": "XL"
        }
      ],
      "selected_variant": "Large"
    },
    "P006-XL": {
      "id": "P006",
      "name": "Merino Wool Sweater",
      "category": "apparel",
      "price": 89.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P006-S",
          "variant": "Small"
        },
        {
          "sku": "P006-M",
          "variant": "Medium"
        },
        {
          "sku": "P006-L",
          "variant": "Large"
        },
        {
          "sku": "P006-XL",
          "variant": "XL"
        }
      ],
      "selected_variant": "XL"
    },
    "P007": {
      "id": "P007",
      "name": "Trail Hiking Boots",
      "category": "apparel",
      "price": 159.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P007-9",
          "variant": "Size 9"
        },
        {
          "sku": "P007-10",
          "variant": "Size 10"
        },
        {
          "sku": "P007-11",
          "variant": "Size 11"
        }
      ]
    },
    "P007-9": {
      "id": "P007",
      "name": "Trail Hiking Boots",
      "category": "apparel",
      "price": 159.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P007-9",
          "variant": "Size 9"
        },
        {
          "sku": "P007-10",
          "variant": "Size 10"
        },
        {
          "sku": "P007-11",
          "variant": "Size 11"
        }
      ],
      "selected_variant": "Size 9"
    },
    "P007-10": {
      "id": "P007",
      "name": "Trail Hiking Boots",
      "category": "apparel",
      "price": 159.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P007-9",
          "variant": "Size 9"
        },
        {
          "sku": "P007-10",
          "variant": "Size 10"
        },
        {
          "sku": "P007-11",
          "variant": "Size 11"
        }
      ],
      "selected_variant": "Size 10"
    },
    "P007-11": {
      "id": "P007",
      "name": "Trail Hiking Boots",
      "category": "apparel",
      "price": 159.99,
      "on_sale": false,
      "variants": [
        {
          "sku": "P007-9",
          "variant": "Size 9"
        },
        {
          "sku": "P007-10",
          "variant": "Size 10"
        },
        {
          "sku": "P007-11",
          "variant": "Size 11"
        }
      ],
      "selected_variant": "Size 11"
    },
    "P008": {
      "id": "P008",
      "name": "Running Jacket",
      "category": "apparel",
      "price": 119.99,
      "on_sale": false
    },
    "P009": {
      "id": "P009",
      "name": "LED Desk Lamp",
      "category": "electronics",
      "price": 45.99,
      "on_sale": false
    },
    "P010": {
      "id": "P010",
      "name": "Premium Yoga Mat",
      "category": "home",
      "price": 69.99,
      "on_sale": false
    },
    "P011": {
      "id": "P011",
      "name": "Canvas Tote Bag",
      "category": "apparel",
      "price": 34.99,
      "on_sale": false
    },
    "P012": {
      "id": "P012",
      "name": "Face Serum Set",
      "category": "personal_care",
      "price": 89.99,
      "on_sale": false
    },
    "P013": {
      "id": "P013",
      "name": "Urban Sneakers",
      "category": "apparel",
      "price": 64.99,
      "on_sale": true
    },
    "P014": {
      "id": "P014",
      "name": "Stainless Water Bottle",
      "category": "home",
      "price": 24.99,
      "on_sale": true
    },
    "P015": {
      "id": "P015",
      "name": "Hair Styling Kit",
      "category": "personal_care",
      "price": 49.99,
      "on_sale": false
    }
  },
  "orders": {
    "ORD-001": {
      "order_id": "ORD-001",
      "customer_id": "C001",
      "order_date": "2026-06-28",
      "promised_delivery": "2026-07-03",
      "line_items": [
        {
          "item_id": "LI-001",
          "product_id": "P006",
          "sku": "P006-M",
          "name": "Merino Wool Sweater",
          "category": "apparel",
          "qty": 1,
          "unit_price": 89.99,
          "discount_pct": 0,
          "variant": ""
        }
      ],
      "subtotal": 89.99,
      "tax": 7.2,
      "total": 97.19,
      "payment_method": "credit_card",
      "fulfillment": {
        "LI-001": {
          "status": "delivered",
          "ship_date": "2026-07-01",
          "delivery_date": "2026-07-05",
          "promised_delivery_date": "2026-07-03",
          "carrier": "FedEx",
          "tracking": "TRK-ORD-001-LI-001",
          "late_delivery": false
        }
      }
    },
    "ORD-002": {
      "order_id": "ORD-002",
      "customer_id": "C002",
      "order_date": "2026-05-30",
      "promised_delivery": "2026-06-05",
      "line_items": [
        {
          "item_id": "LI-002",
          "product_id": "P001",
          "sku": "P001",
          "name": "Wireless Headphones",
          "category": "electronics",
          "qty": 1,
          "unit_price": 149.99,
          "discount_pct": 0,
          "variant": ""
        }
      ],
      "subtotal": 149.99,
      "tax": 12.0,
      "total": 161.99,
      "payment_method": "credit_card",
      "fulfillment": {
        "LI-002": {
          "status": "delivered",
          "ship_date": "2026-06-03",
          "delivery_date": "2026-06-10",
          "promised_delivery_date": "2026-06-05",
          "carrier": "UPS",
          "tracking": "TRK-ORD-002-LI-002",
          "late_delivery": true
        }
      }
    },
    "ORD-003": {
      "order_id": "ORD-003",
      "customer_id": "C003",
      "order_date": "2026-06-18",
      "promised_delivery": "2026-06-23",
      "line_items": [
        {
          "item_id": "LI-003",
          "product_id": "P002",
          "sku": "P002-BLK",
          "name": "Mechanical Keyboard",
          "category": "electronics",
          "qty": 1,
          "unit_price": 129.99,
          "discount_pct": 0,
          "variant": ""
        },
        {
          "item_id": "LI-004",
          "product_id": "P013",
          "sku": "P013",
          "name": "Urban Sneakers",
          "category": "apparel",
          "qty": 1,
          "unit_price": 64.99,
          "discount_pct": 0,
          "variant": ""
        }
      ],
      "subtotal": 194.98,
      "tax": 15.6,
      "total": 210.58,
      "payment_method": "debit_card",
      "fulfillment": {
        "LI-003": {
          "status": "delivered",
          "ship_date": "2026-06-21",
          "delivery_date": "2026-06-25",
          "promised_delivery_date": "2026-06-23",
          "carrier": "FedEx",
          "tracking": "TRK-ORD-003-LI-003",
          "late_delivery": false
        },
        "LI-004": {
          "status": "delivered",
          "ship_date": "2026-06-21",
          "delivery_date": "2026-06-25",
          "promised_delivery_date": "2026-06-23",
          "carrier": "FedEx",
          "tracking": "TRK-ORD-003-LI-004",
          "late_delivery": false
        }
      }
    },
    "ORD-004": {
      "order_id": "ORD-004",
      "customer_id": "C004",
      "order_date": "2026-06-30",
      "promised_delivery": "2026-07-05",
      "line_items": [
        {
          "item_id": "LI-005",
          "product_id": "P009",
          "sku": "P009",
          "name": "LED Desk Lamp",
          "category": "electronics",
          "qty": 1,
          "unit_price": 45.99,
          "discount_pct": 0,
          "variant": ""
        },
        {
          "item_id": "LI-006",
          "product_id": "P012",
          "sku": "P012",
          "name": "Face Serum Set",
          "category": "personal_care",
          "qty": 1,
          "unit_price": 89.99,
          "discount_pct": 0,
          "variant": ""
        }
      ],
      "subtotal": 135.98,
      "tax": 10.88,
      "total": 146.86,
      "payment_method": "credit_card",
      "fulfillment": {
        "LI-005": {
          "status": "delivered",
          "ship_date": "2026-07-03",
          "delivery_date": "2026-07-08",
          "promised_delivery_date": "2026-07-05",
          "carrier": "USPS",
          "tracking": "TRK-ORD-004-LI-005",
          "late_delivery": true
        },
        "LI-006": {
          "status": "delivered",
          "ship_date": "2026-07-03",
          "delivery_date": "2026-07-08",
          "promised_delivery_date": "2026-07-05",
          "carrier": "USPS",
          "tracking": "TRK-ORD-004-LI-006",
          "late_delivery": true
        }
      }
    },
    "ORD-005": {
      "order_id": "ORD-005",
      "customer_id": "C005",
      "order_date": "2026-05-15",
      "promised_delivery": "2026-05-22",
      "line_items": [
        {
          "item_id": "LI-007",
          "product_id": "P003",
          "sku": "P003-M",
          "name": "Smart Watch",
          "category": "electronics",
          "qty": 1,
          "unit_price": 299.99,
          "discount_pct": 0,
          "variant": ""
        }
      ],
      "subtotal": 299.99,
      "tax": 24.0,
      "total": 323.99,
      "payment_method": "credit_card",
      "fulfillment": {
        "LI-007": {
          "status": "delivered",
          "ship_date": "2026-05-19",
          "delivery_date": "2026-05-26",
          "promised_delivery_date": "2026-05-22",
          "carrier": "FedEx",
          "tracking": "TRK-ORD-005-LI-007",
          "late_delivery": true
        }
      }
    },
    "ORD-006": {
      "order_id": "ORD-006",
      "customer_id": "C002",
      "order_date": "2026-06-20",
      "promised_delivery": "2026-06-25",
      "line_items": [
        {
          "item_id": "LI-008",
          "product_id": "P010",
          "sku": "P010",
          "name": "Premium Yoga Mat",
          "category": "home",
          "qty": 1,
          "unit_price": 69.99,
          "discount_pct": 0,
          "variant": ""
        }
      ],
      "subtotal": 69.99,
      "tax": 5.6,
      "total": 75.59,
      "payment_method": "paypal",
      "fulfillment": {
        "LI-008": {
          "status": "lost",
          "ship_date": "2026-06-22",
          "delivery_date": null,
          "promised_delivery_date": "2026-06-25",
          "carrier": "USPS",
          "tracking": "TRK-ORD-006-LI-008",
          "late_delivery": false
        }
      }
    },
    "ORD-007": {
      "order_id": "ORD-007",
      "customer_id": "C003",
      "order_date": "2026-05-28",
      "promised_delivery": "2026-06-02",
      "line_items": [
        {
          "item_id": "LI-009",
          "product_id": "P008",
          "sku": "P008",
          "name": "Running Jacket",
          "category": "apparel",
          "qty": 1,
          "unit_price": 119.99,
          "discount_pct": 0,
          "variant": ""
        }
      ],
      "subtotal": 119.99,
      "tax": 9.6,
      "total": 129.59,
      "payment_method": "credit_card",
      "fulfillment": {
        "LI-009": {
          "status": "delivered",
          "ship_date": "2026-06-01",
          "delivery_date": "2026-06-05",
          "promised_delivery_date": "2026-06-02",
          "carrier": "FedEx",
          "tracking": "TRK-ORD-007-LI-009",
          "late_delivery": false
        }
      }
    },
    "ORD-008": {
      "order_id": "ORD-008",
      "customer_id": "C001",
      "order_date": "2026-05-10",
      "promised_delivery": "2026-05-18",
      "line_items": [
        {
          "item_id": "LI-010",
          "product_id": "P005",
          "sku": "P005",
          "name": "Electric Kettle",
          "category": "electronics",
          "qty": 1,
          "unit_price": 59.99,
          "discount_pct": 0,
          "variant": ""
        }
      ],
      "subtotal": 59.99,
      "tax": 4.8,
      "total": 64.79,
      "payment_method": "credit_card",
      "fulfillment": {
        "LI-010": {
          "status": "delivered",
          "ship_date": "2026-05-14",
          "delivery_date": "2026-05-21",
          "promised_delivery_date": "2026-05-18",
          "carrier": "UPS",
          "tracking": "TRK-ORD-008-LI-010",
          "late_delivery": false
        }
      }
    },
    "ORD-009": {
      "order_id": "ORD-009",
      "customer_id": "C004",
      "order_date": "2026-07-01",
      "promised_delivery": "2026-07-05",
      "line_items": [
        {
          "item_id": "LI-011",
          "product_id": "P014",
          "sku": "P014",
          "name": "Stainless Water Bottle",
          "category": "home",
          "qty": 1,
          "unit_price": 24.99,
          "discount_pct": 0,
          "variant": ""
        }
      ],
      "subtotal": 24.99,
      "tax": 2.0,
      "total": 26.99,
      "payment_method": "credit_card",
      "fulfillment": {
        "LI-011": {
          "status": "delivered",
          "ship_date": "2026-07-03",
          "delivery_date": "2026-07-05",
          "promised_delivery_date": "2026-07-05",
          "carrier": "FedEx",
          "tracking": "TRK-ORD-009-LI-011",
          "late_delivery": false
        }
      }
    },
    "ORD-010": {
      "order_id": "ORD-010",
      "customer_id": "C005",
      "order_date": "2026-06-25",
      "promised_delivery": "2026-06-30",
      "line_items": [
        {
          "item_id": "LI-012",
          "product_id": "P007",
          "sku": "P007-10",
          "name": "Trail Hiking Boots",
          "category": "apparel",
          "qty": 1,
          "unit_price": 159.99,
          "discount_pct": 0,
          "variant": ""
        },
        {
          "item_id": "LI-013",
          "product_id": "P004",
          "sku": "P004",
          "name": "Bluetooth Speaker",
          "category": "electronics",
          "qty": 1,
          "unit_price": 79.99,
          "discount_pct": 0,
          "variant": ""
        }
      ],
      "subtotal": 239.98,
      "tax": 19.2,
      "total": 259.18,
      "payment_method": "credit_card",
      "fulfillment": {
        "LI-012": {
          "status": "delivered",
          "ship_date": "2026-06-28",
          "delivery_date": "2026-07-03",
          "promised_delivery_date": "2026-06-30",
          "carrier": "FedEx",
          "tracking": "TRK-ORD-010-LI-012",
          "late_delivery": false
        },
        "LI-013": {
          "status": "delivered",
          "ship_date": "2026-06-28",
          "delivery_date": "2026-07-03",
          "promised_delivery_date": "2026-06-30",
          "carrier": "FedEx",
          "tracking": "TRK-ORD-010-LI-013",
          "late_delivery": false
        }
      }
    },
    "ORD-011": {
      "order_id": "ORD-011",
      "customer_id": "C002",
      "order_date": "2026-06-28",
      "promised_delivery": "2026-07-03",
      "line_items": [
        {
          "item_id": "LI-014",
          "product_id": "P015",
          "sku": "P015",
          "name": "Hair Styling Kit",
          "category": "personal_care",
          "qty": 1,
          "unit_price": 49.99,
          "discount_pct": 0,
          "variant": ""
        }
      ],
      "subtotal": 49.99,
      "tax": 4.0,
      "total": 53.99,
      "payment_method": "credit_card",
      "fulfillment": {
        "LI-014": {
          "status": "delivered",
          "ship_date": "2026-07-01",
          "delivery_date": "2026-07-05",
          "promised_delivery_date": "2026-07-03",
          "carrier": "UPS",
          "tracking": "TRK-ORD-011-LI-014",
          "late_delivery": false
        }
      }
    },
    "ORD-012": {
      "order_id": "ORD-012",
      "customer_id": "C003",
      "order_date": "2026-07-14",
      "promised_delivery": "2026-07-19",
      "line_items": [
        {
          "item_id": "LI-015",
          "product_id": "P002",
          "sku": "P002-WHT",
          "name": "Mechanical Keyboard",
          "category": "electronics",
          "qty": 1,
          "unit_price": 129.99,
          "discount_pct": 0,
          "variant": ""
        },
        {
          "item_id": "LI-016",
          "product_id": "P011",
          "sku": "P011",
          "name": "Canvas Tote Bag",
          "category": "apparel",
          "qty": 1,
          "unit_price": 34.99,
          "discount_pct": 0,
          "variant": ""
        }
      ],
      "subtotal": 164.98,
      "tax": 13.2,
      "total": 178.18,
      "payment_method": "credit_card",
      "fulfillment": {
        "LI-015": {
          "status": "processing",
          "ship_date": null,
          "delivery_date": null,
          "promised_delivery_date": "2026-07-19",
          "carrier": null,
          "tracking": "TRK-ORD-012-LI-015",
          "late_delivery": false
        },
        "LI-016": {
          "status": "processing",
          "ship_date": null,
          "delivery_date": null,
          "promised_delivery_date": "2026-07-19",
          "carrier": null,
          "tracking": "TRK-ORD-012-LI-016",
          "late_delivery": false
        }
      }
    }
  },
  "inventory": {
    "P002-BLK": {
      "in_stock": true,
      "quantity": 15
    },
    "P002-WHT": {
      "in_stock": true,
      "quantity": 3
    },
    "P002-RGB": {
      "in_stock": false,
      "quantity": 0,
      "restock_date": "2026-08-01"
    },
    "P003-S": {
      "in_stock": true,
      "quantity": 8
    },
    "P003-M": {
      "in_stock": false,
      "quantity": 0,
      "restock_date": "2026-07-25"
    },
    "P003-L": {
      "in_stock": true,
      "quantity": 2
    },
    "P006-S": {
      "in_stock": true,
      "quantity": 20
    },
    "P006-M": {
      "in_stock": true,
      "quantity": 12
    },
    "P006-L": {
      "in_stock": false,
      "quantity": 0,
      "restock_date": "2026-07-20"
    },
    "P006-XL": {
      "in_stock": true,
      "quantity": 5
    },
    "P007-9": {
      "in_stock": true,
      "quantity": 4
    },
    "P007-10": {
      "in_stock": true,
      "quantity": 6
    },
    "P007-11": {
      "in_stock": false,
      "quantity": 0,
      "restock_date": "2026-08-15"
    }
  }
}""")


# ---------------------------------------------------------------------------
# Return windows: tier -> category -> days
# ---------------------------------------------------------------------------
RETURN_WINDOWS = {
    "standard": {"apparel": 30, "home": 30, "electronics": 15, "personal_care": 15},
    "gold":     {"apparel": 45, "home": 45, "electronics": 30, "personal_care": 30},
    "platinum": {"apparel": 60, "home": 60, "electronics": 45, "personal_care": 45},
}


def _get_return_window(tier, category):
    tier_w = RETURN_WINDOWS.get(tier, RETURN_WINDOWS["standard"])
    return tier_w.get(category, 30)


def _is_defective(reason):
    r = reason.lower()
    return any(w in r for w in [
        "defective", "broken", "damaged", "faulty", "malfunction",
        "defect", "cracked", "flicker", "doesn\'t work", "not working",
        "damaged_in_shipping",
    ])


# ---------------------------------------------------------------------------
# Tool 1: get_order_details
# ---------------------------------------------------------------------------
def get_order_details(order_id: str) -> str:
    """Retrieve order details including line items, customer info, and totals."""
    order = DB["orders"].get(order_id)
    if not order:
        return json.dumps({"error": f"Order {order_id} not found"})

    customer = DB["customers"].get(order["customer_id"])
    if not customer:
        return json.dumps({"error": f"Customer not found for order {order_id}"})

    enriched_items = []
    for li in order["line_items"]:
        product = DB["products"].get(li["product_id"])
        on_sale = product.get("on_sale", False) if product else False
        enriched_items.append({
            "item_id": li["item_id"],
            "product_id": li["product_id"],
            "product_name": li.get("name", product["name"] if product else "Unknown"),
            "category": li.get("category", product["category"] if product else "unknown"),
            "sku": li["sku"],
            "quantity": li["qty"],
            "unit_price": li["unit_price"],
            "discount_pct": li["discount_pct"],
            "on_sale": on_sale,
            "variant": li.get("variant", ""),
        })

    return json.dumps({
        "order_id": order.get("order_id", order_id),
        "customer": {
            "id": customer["id"],
            "name": customer["name"],
            "email": customer["email"],
            "loyalty_tier": customer["loyalty_tier"],
        },
        "order_date": order["order_date"],
        "promised_delivery": order.get("promised_delivery"),
        "items": enriched_items,
        "subtotal": order["subtotal"],
        "tax": order["tax"],
        "total": order["total"],
        "payment_method": order["payment_method"],
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool 2: get_fulfillment_status
# ---------------------------------------------------------------------------
def get_fulfillment_status(order_id: str) -> str:
    """Get per-item fulfillment status for an order."""
    order = DB["orders"].get(order_id)
    if not order:
        return json.dumps({"error": f"Order {order_id} not found"})

    fulfillment = order.get("fulfillment", {})
    items = []
    for item_id, ful in fulfillment.items():
        delivery_date = ful.get("delivery_date")
        days_since = None
        if delivery_date:
            days_since = (TODAY - datetime.fromisoformat(delivery_date)).days

        days_late = None
        promised = ful.get("promised_delivery_date")
        if ful.get("late_delivery") and delivery_date and promised:
            days_late = (datetime.fromisoformat(delivery_date) - datetime.fromisoformat(promised)).days

        items.append({
            "item_id": item_id,
            "status": ful["status"],
            "ship_date": ful.get("ship_date"),
            "delivery_date": delivery_date,
            "carrier": ful.get("carrier"),
            "late_delivery": ful.get("late_delivery", False),
            "days_late": days_late,
            "days_since_delivery": days_since,
        })

    return json.dumps({
        "order_id": order_id,
        "today": TODAY_STR,
        "items": items,
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool 3: check_resolution_policy
# ---------------------------------------------------------------------------
def check_resolution_policy(order_id: str, item_id: str, reason: str) -> str:
    """Check what resolution actions are available for an item given the reason."""
    order = DB["orders"].get(order_id)
    if not order:
        return json.dumps({"error": f"Order {order_id} not found"})

    li = next((i for i in order["line_items"] if i["item_id"] == item_id), None)
    if not li:
        return json.dumps({"error": f"Item {item_id} not found in order {order_id}"})

    product = DB["products"].get(li["product_id"])
    customer = DB["customers"].get(order["customer_id"])
    tier = customer["loyalty_tier"] if customer else "standard"

    ful = order.get("fulfillment", {}).get(item_id, {})

    status = ful.get("status", "unknown")
    category = li.get("category", product.get("category", "home") if product else "home")
    on_sale = product.get("on_sale", False) if product else False
    is_late = ful.get("late_delivery", False)
    is_defect = _is_defective(reason)
    is_lost = status == "lost"
    is_processing = status in ("processing", "pending")

    delivery_str = ful.get("delivery_date")
    days_since = None
    if delivery_str:
        days_since = (TODAY - datetime.fromisoformat(delivery_str)).days

    base_window = _get_return_window(tier, category)
    effective_window = base_window + (15 if is_late else 0)
    shipping_credit = 10.0 if is_late else 0.0

    if is_defect or is_lost or is_processing:
        restocking_pct = 0.0
    elif category == "electronics":
        restocking_pct = {"platinum": 0.0, "gold": 7.5}.get(tier, 15.0)
    else:
        restocking_pct = 0.0

    # Lost packages
    if is_lost:
        return json.dumps({
            "eligible": True,
            "eligible_actions": ["refund", "replacement"],
            "return_window_days": None,
            "days_since_delivery": None,
            "restocking_fee_pct": 0.0,
            "shipping_credit": 0.0,
            "special_rules": [
                "Lost package: eligible for full replacement or full refund",
                "No return shipment required",
            ],
        }, indent=2)

    # Pending / processing -> cancellation
    if is_processing:
        return json.dumps({
            "eligible": True,
            "eligible_actions": ["refund"],
            "return_window_days": None,
            "days_since_delivery": None,
            "restocking_fee_pct": 0.0,
            "shipping_credit": 0.0,
            "special_rules": [
                "Order not yet shipped: eligible for cancellation and full refund",
            ],
        }, indent=2)

    # Defective items
    if is_defect:
        if on_sale:
            return json.dumps({
                "eligible": True,
                "eligible_actions": ["store_credit"],
                "return_window_days": effective_window,
                "days_since_delivery": days_since,
                "restocking_fee_pct": 0.0,
                "shipping_credit": shipping_credit,
                "special_rules": [
                    "Defective item: eligible regardless of return window",
                    "Sale item exception: defective sale items -> store credit only (not refund)",
                    "No restocking fee for defective items",
                ],
            }, indent=2)
        return json.dumps({
            "eligible": True,
            "eligible_actions": ["refund", "replacement", "exchange", "store_credit"],
            "return_window_days": effective_window,
            "days_since_delivery": days_since,
            "restocking_fee_pct": 0.0,
            "shipping_credit": shipping_credit,
            "special_rules": [
                "Defective item: eligible regardless of return window or sale status",
                "No restocking fee for defective items",
                "Prepaid return label will be provided",
            ],
        }, indent=2)

    # Sale items (non-defective) -> final sale
    if on_sale:
        return json.dumps({
            "eligible": False,
            "eligible_actions": ["deny"],
            "return_window_days": effective_window,
            "days_since_delivery": days_since,
            "restocking_fee_pct": 0.0,
            "shipping_credit": shipping_credit,
            "special_rules": [
                "Sale/clearance item: final sale - no returns or exchanges unless defective",
            ],
            "denial_reason": "Sale items are final sale and cannot be returned unless defective.",
        }, indent=2)

    # Personal care (non-defective)
    if category == "personal_care":
        r_lower = reason.lower()
        is_sealed = any(w in r_lower for w in ["sealed", "unopened", "never opened"])
        if not is_sealed:
            return json.dumps({
                "eligible": False,
                "eligible_actions": ["deny"],
                "return_window_days": effective_window,
                "days_since_delivery": days_since,
                "restocking_fee_pct": 0.0,
                "shipping_credit": shipping_credit,
                "special_rules": [
                    "Personal care item: not returnable once opened unless defective",
                ],
                "denial_reason": "Opened personal care items cannot be returned unless defective.",
            }, indent=2)

    # Check return window
    if days_since is not None and days_since > effective_window:
        rules = [
            f"Return window expired: {days_since} days since delivery, "
            f"window is {effective_window} days ({tier} tier, {category})",
        ]
        if is_late:
            rules.append(
                f"Late delivery extension already applied: base {base_window} + 15 = {effective_window} days"
            )
            rules.append("$10 shipping credit still applies for late delivery")
        return json.dumps({
            "eligible": False,
            "eligible_actions": ["deny"],
            "return_window_days": effective_window,
            "days_since_delivery": days_since,
            "restocking_fee_pct": 0.0,
            "shipping_credit": shipping_credit,
            "special_rules": rules,
            "denial_reason": (
                f"The {effective_window}-day return window has expired "
                f"({days_since} days since delivery)."
            ),
        }, indent=2)

    # Within window -> eligible
    rules = []
    if is_late:
        rules.append(
            f"Late delivery: window extended from {base_window} to {effective_window} days, "
            f"$10 shipping credit applies"
        )
    if tier != "standard":
        rules.append(f"{tier.title()} tier: {effective_window}-day return window for {category}")
    if category == "electronics" and restocking_pct > 0:
        rules.append(
            f"Electronics restocking fee: {restocking_pct}% applies for non-defective returns"
        )

    days_remaining = (effective_window - days_since) if days_since is not None else None

    return json.dumps({
        "eligible": True,
        "eligible_actions": ["refund", "exchange", "store_credit"],
        "return_window_days": effective_window,
        "days_since_delivery": days_since,
        "days_remaining": days_remaining,
        "restocking_fee_pct": restocking_pct,
        "shipping_credit": shipping_credit,
        "special_rules": rules,
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool 4: check_inventory
# ---------------------------------------------------------------------------
def check_inventory(sku: str) -> str:
    """Check stock availability for a product SKU."""
    inv = DB["inventory"].get(sku)

    if inv is None:
        prefix = sku.rsplit("-", 1)[0] if "-" in sku else sku
        alternatives = {
            k: {"in_stock": v["in_stock"], "quantity": v["quantity"]}
            for k, v in DB["inventory"].items()
            if k.startswith(prefix)
        }
        if alternatives:
            return json.dumps({
                "error": f"SKU {sku} not found in inventory",
                "available_variants": alternatives,
            }, indent=2)
        return json.dumps({"error": f"SKU {sku} not found in inventory"})

    result = {
        "sku": sku,
        "in_stock": inv["in_stock"],
        "quantity": inv["quantity"],
    }
    if not inv["in_stock"]:
        result["restock_date"] = inv.get("restock_date")
        prefix = sku.rsplit("-", 1)[0] if "-" in sku else sku
        result["alternatives"] = [
            {"sku": k, "quantity": v["quantity"]}
            for k, v in DB["inventory"].items()
            if k.startswith(prefix) and k != sku and v["in_stock"]
        ]

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool 5: calculate_resolution
# ---------------------------------------------------------------------------
def calculate_resolution(order_id: str, items: list) -> str:
    """Calculate financial details for a list of item resolutions."""
    order = DB["orders"].get(order_id)
    if not order:
        return json.dumps({"error": f"Order {order_id} not found"})

    if isinstance(items, str):
        try:
            items = json.loads(items)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid items format - expected JSON array"})

    customer = DB["customers"].get(order["customer_id"])
    tier = customer["loyalty_tier"] if customer else "standard"
    fulfillment = order.get("fulfillment", {})

    breakdown = []
    total_refund = 0.0
    total_restocking = 0.0
    total_shipping_credit = 0.0
    warnings = []

    for ai in items:
        item_id = ai.get("item_id")
        action = ai.get("action")
        reason = ai.get("reason", "")

        # Shipping credit
        if action == "shipping_credit":
            ful = fulfillment.get(item_id, {})
            if ful.get("late_delivery"):
                total_shipping_credit += 10.0
                breakdown.append({
                    "item_id": item_id,
                    "action": "shipping_credit",
                    "amount": 10.0,
                    "reason": "Late delivery compensation",
                })
            else:
                warnings.append(f"Shipping credit for {item_id}: delivery was not late")
            continue

        if action == "deny":
            breakdown.append({
                "item_id": item_id, "action": "deny",
                "refund_amount": 0.0, "restocking_fee": 0.0, "net_refund": 0.0,
                "reason": reason,
            })
            continue

        li = next((i for i in order["line_items"] if i["item_id"] == item_id), None)
        if not li:
            warnings.append(f"Item {item_id} not found in order")
            continue

        product = DB["products"].get(li["product_id"])
        category = li.get("category", product.get("category", "home") if product else "home")
        unit_price = li["unit_price"]
        qty = li["qty"]
        item_total = round(unit_price * qty, 2)
        if li.get("discount_pct", 0) > 0:
            item_total = round(item_total * (1 - li["discount_pct"] / 100), 2)

        ful = fulfillment.get(item_id, {})
        is_defect = _is_defective(reason)
        is_lost = ful.get("status") == "lost"
        is_processing = ful.get("status") in ("processing", "pending")

        if action in ("refund", "store_credit"):
            if is_defect or is_lost or is_processing:
                rpct = 0.0
            elif category == "electronics":
                rpct = {"platinum": 0.0, "gold": 7.5}.get(tier, 15.0)
            else:
                rpct = 0.0

            rfee = round(item_total * rpct / 100, 2)
            net = round(item_total - rfee, 2)
            breakdown.append({
                "item_id": item_id, "action": action,
                "refund_amount": item_total, "restocking_fee": rfee,
                "restocking_fee_pct": rpct, "net_refund": net,
            })
            total_refund += net
            total_restocking += rfee

        elif action == "replacement":
            breakdown.append({
                "item_id": item_id, "action": "replacement",
                "refund_amount": item_total, "restocking_fee": 0.0,
                "net_refund": item_total,
                "note": "Replacement item shipped at no cost",
            })
            total_refund += item_total

        elif action == "exchange":
            exchange_sku = ai.get("exchange_sku", li["sku"])
            exchange_product = DB["products"].get(exchange_sku)
            if not exchange_product:
                prefix = exchange_sku.rsplit("-", 1)[0] if "-" in exchange_sku else exchange_sku
                exchange_product = DB["products"].get(prefix)
            exchange_price = exchange_product["price"] if exchange_product else unit_price
            price_diff = round(exchange_price - unit_price, 2)

            entry = {
                "item_id": item_id, "action": "exchange",
                "original_price": unit_price,
                "exchange_sku": exchange_sku,
                "exchange_price": exchange_price,
                "price_difference": price_diff,
                "restocking_fee": 0.0,
            }
            if price_diff > 0:
                entry["customer_owes"] = price_diff
                entry["net_refund"] = 0.0
            elif price_diff < 0:
                entry["customer_credit"] = abs(price_diff)
                entry["net_refund"] = abs(price_diff)
                total_refund += abs(price_diff)
            else:
                entry["net_refund"] = 0.0
            breakdown.append(entry)

    total_resolution = round(total_refund + total_shipping_credit, 2)

    result = {
        "order_id": order_id,
        "breakdown": breakdown,
        "summary": {
            "total_refund": round(total_refund, 2),
            "total_restocking_fees": round(total_restocking, 2),
            "total_shipping_credit": round(total_shipping_credit, 2),
            "total_resolution_amount": total_resolution,
        },
        "refund_method": order["payment_method"],
    }
    if warnings:
        result["warnings"] = warnings
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool 6: submit_resolution
# ---------------------------------------------------------------------------
def submit_resolution(order_id: str, resolution_summary: str) -> str:
    """Submit a finalized resolution. Returns confirmation ID."""
    order = DB["orders"].get(order_id)
    if not order:
        return json.dumps({"error": f"Order {order_id} not found"})

    customer = DB["customers"].get(order["customer_id"])
    cust_name = customer["name"] if customer else "Customer"
    cust_email = customer["email"] if customer else ""

    conf_hash = hashlib.md5(
        f"{order_id}-{resolution_summary}".encode()
    ).hexdigest()[:8].upper()
    confirmation_id = f"RES-{conf_hash}"

    return json.dumps({
        "confirmation_id": confirmation_id,
        "order_id": order_id,
        "status": "submitted",
        "summary": resolution_summary,
        "customer_notification": {
            "to": cust_email,
            "name": cust_name,
            "subject": f"Retail Resolution Confirmation - {confirmation_id}",
        },
        "estimated_processing": "5-7 business days",
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------
TOOL_DISPATCH = {
    "get_order_details": get_order_details,
    "get_fulfillment_status": get_fulfillment_status,
    "check_resolution_policy": check_resolution_policy,
    "check_inventory": check_inventory,
    "calculate_resolution": calculate_resolution,
    "submit_resolution": submit_resolution,
}


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Retail Tools", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/")
async def health():
    return {"status": "ok", "tools": list(TOOL_DISPATCH.keys()), "today": TODAY_STR}


@app.get("/db")
async def get_db():
    """Return the full in-memory database (for the demo console)."""
    return DB


@app.get("/demo")
async def demo_page():
    """Serve the interactive demo console."""
    import os
    demo_path = os.path.join(os.path.dirname(__file__), "demo.html")
    if os.path.exists(demo_path):
        from fastapi.responses import HTMLResponse
        with open(demo_path) as f:
            return HTMLResponse(f.read())
    return JSONResponse(status_code=404, content={"error": "demo.html not found"})


@app.post("/tool/{tool_name}")
async def invoke_tool(tool_name: str, request: Request):
    if tool_name not in TOOL_DISPATCH:
        return JSONResponse(
            status_code=404,
            content={"error": f"Unknown tool: {tool_name}. Available: {list(TOOL_DISPATCH.keys())}"},
        )

    body = await request.json()
    call_id = body.get("call_id", "")
    fc_id = body.get("id", "")
    arguments_raw = body.get("arguments", "{}")

    if isinstance(arguments_raw, str):
        try:
            arguments = json.loads(arguments_raw)
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid JSON in arguments field"},
            )
    else:
        arguments = arguments_raw

    fn = TOOL_DISPATCH[tool_name]
    try:
        output = fn(**arguments)
    except TypeError as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid arguments for {tool_name}: {e}"},
        )

    return {
        "type": "function_call_output",
        "call_id": call_id,
        "id": fc_id,
        "output": output,
    }


# ---------------------------------------------------------------------------
# Azure Functions ASGI wrapper
# ---------------------------------------------------------------------------
if HAS_AZ:
    fastapi_app = AsgiFunctionApp(app=app, http_auth_level=func.AuthLevel.ANONYMOUS)
else:
    fastapi_app = app
