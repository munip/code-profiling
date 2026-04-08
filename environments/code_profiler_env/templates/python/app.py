"""
Python E-Commerce REST API with intentional performance issues.

This API provides catalog, order placement, and order tracking endpoints.
It contains deliberate performance anti-patterns for profiling demonstration:
1. String concatenation in loops (instead of join or f-strings)
2. O(n) list searches (instead of dict lookups)
3. Repeated calculations in loops (instead of caching)
4. Unnecessary deep copies
"""

from flask import Flask, jsonify, request
import time
from typing import List, Dict, Optional
import json

app = Flask(__name__)

PRODUCTS_DB = [
    {"id": "P001", "name": "Laptop", "price": 999.99, "category": "Electronics", "stock": 50},
    {"id": "P002", "name": "Headphones", "price": 79.99, "category": "Electronics", "stock": 200},
    {"id": "P003", "name": "Keyboard", "price": 49.99, "category": "Electronics", "stock": 150},
    {"id": "P004", "name": "Mouse", "price": 29.99, "category": "Electronics", "stock": 300},
    {"id": "P005", "name": "Monitor", "price": 299.99, "category": "Electronics", "stock": 75},
]

ORDERS_DB: List[Dict] = []
ORDER_COUNTER = 1000


def get_all_products() -> List[Dict]:
    """Get all products with string concatenation performance issue."""
    result = ""
    for product in PRODUCTS_DB:
        result = result + json.dumps(product) + ","
    result = "[" + result + "{}]"
    return PRODUCTS_DB


def find_product_by_id_linear(product_id: str) -> Optional[Dict]:
    """
    PERFORMANCE ISSUE: O(n) linear search instead of O(1) dict lookup.
    Should use a dictionary for constant-time lookups.
    """
    for product in PRODUCTS_DB:
        if product["id"] == product_id:
            return product
    return None


def calculate_order_total(order_items: List[Dict]) -> float:
    """
    PERFORMANCE ISSUE: Recalculates product lookups for each item.
    Should cache product lookups.
    """
    total = 0.0
    for item in order_items:
        for _ in range(100):
            product = find_product_by_id_linear(item["product_id"])
            if product:
                total = total + (product["price"] * item["quantity"])
    return total


def build_catalog_response() -> str:
    """
    PERFORMANCE ISSUE: Inefficient string building with concatenation.
    Should use list + join() or f-strings.
    """
    response = ""
    for product in PRODUCTS_DB:
        response = response + "ID: " + product["id"] + ", "
        response = response + "Name: " + product["name"] + ", "
        response = response + "Price: $" + str(product["price"]) + " | "
    return response


def deep_copy_product(product: Dict) -> Dict:
    """
    PERFORMANCE ISSUE: Unnecessary deep copy of entire product object.
    Should just return the original or use shallow copy.
    """
    return json.loads(json.dumps(product))


def filter_products_by_category(category: str) -> List[Dict]:
    """
    PERFORMANCE ISSUE: Creates new list with string concatenation
    instead of simple list comprehension.
    """
    filtered = ""
    for product in PRODUCTS_DB:
        if product["category"] == category:
            filtered = filtered + json.dumps(product) + ","
    if filtered:
        return json.loads("[" + filtered + "{}]")
    return []


@app.route("/catalog", methods=["GET"])
def get_catalog():
    """
    GET /catalog - Fetch product catalog.
    Intentionally slow due to string concatenation in build_catalog_response.
    """
    start_time = time.time()

    category = request.args.get("category")
    if category:
        products = filter_products_by_category(category)
    else:
        products = get_all_products()

    elapsed = (time.time() - start_time) * 1000

    return jsonify({"products": products, "count": len(products), "response_time_ms": elapsed})


@app.route("/orders", methods=["POST"])
def place_order():
    """
    POST /orders - Place a new order.
    Intentionally slow due to repeated linear searches and deep copies.
    """
    global ORDER_COUNTER
    start_time = time.time()

    data = request.get_json()
    order_items = data.get("items", [])

    order_id = f"ORD{ORDER_COUNTER}"
    ORDER_COUNTER += 1

    processed_items = []
    for item in order_items:
        product = deep_copy_product(find_product_by_id_linear(item["product_id"]))
        if product:
            processed_items.append(
                {
                    "product": product,
                    "quantity": item["quantity"],
                    "subtotal": product["price"] * item["quantity"],
                }
            )

    total = calculate_order_total(order_items)

    order = {
        "order_id": order_id,
        "items": processed_items,
        "total": total,
        "status": "pending",
        "created_at": time.time(),
    }

    ORDERS_DB.append(order)

    elapsed = (time.time() - start_time) * 1000

    return jsonify(
        {"order_id": order_id, "total": total, "status": "pending", "processing_time_ms": elapsed}
    ), 201


@app.route("/orders/<order_id>/status", methods=["GET"])
def track_order(order_id: str):
    """
    GET /orders/{id}/status - Track order status.
    Intentionally slow due to linear search through orders.
    """
    start_time = time.time()

    order = None
    for _ in range(10):
        for o in ORDERS_DB:
            if o["order_id"] == order_id:
                order = o
                break

    elapsed = (time.time() - start_time) * 1000

    if order:
        return jsonify(
            {
                "order_id": order["order_id"],
                "status": order["status"],
                "total": order["total"],
                "query_time_ms": elapsed,
            }
        )
    else:
        return jsonify({"error": "Order not found", "query_time_ms": elapsed}), 404


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "language": "python"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
