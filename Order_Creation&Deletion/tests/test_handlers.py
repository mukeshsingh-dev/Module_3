import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def event(body=None, order_id="o-1"):
    return {
        "requestContext": {"authorizer": {"claims": {"sub": "u-1"}}},
        "pathParameters": {"orderId": order_id},
        "body": json.dumps(body or {}),
    }


class FakeTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item, **kwargs):
        key = (Item["userId"], Item["orderId"])
        if "attribute_not_exists" in kwargs.get("ConditionExpression", "") and key in self.items:
            raise RuntimeError("ConditionalCheckFailedException")
        if "attribute_exists" in kwargs.get("ConditionExpression", ""):
            if key not in self.items or self.items[key]["data"].get("status") != "PLACED":
                raise RuntimeError("ConditionalCheckFailedException")
        self.items[key] = Item

    def query(self, **kwargs):
        return {"Items": list(self.items.values())}

    def update_item(self, Key, **kwargs):
        item = self.items[tuple(Key.values())]
        item["data"]["status"] = "CANCELED"
        return {"Attributes": item}


@pytest.fixture
def fake_table(monkeypatch):
    table = FakeTable()
    fake_boto = types.ModuleType("boto3")
    fake_boto.resource = lambda *_: type("DDB", (), {"Table": lambda *_: table})()
    conditions = types.ModuleType("boto3.dynamodb.conditions")
    conditions.Key = lambda name: type("KeyExpr", (), {"eq": lambda self, value: (name, value)})()
    dynamodb = types.ModuleType("boto3.dynamodb")
    dynamodb.conditions = conditions
    monkeypatch.setitem(sys.modules, "boto3", fake_boto)
    monkeypatch.setitem(sys.modules, "boto3.dynamodb", dynamodb)
    monkeypatch.setitem(sys.modules, "boto3.dynamodb.conditions", conditions)
    monkeypatch.setenv("TABLE_NAME", "orders")
    return table


def test_create_list_get_edit_cancel(fake_table, monkeypatch):
    create = load("create_order", "src/api/order/create/create_order.py")
    listing = load("list_orders", "src/api/order/list/list_orders.py")
    edit = load("edit_order", "src/api/order/edit/edit_order.py")
    cancel = load("cancel_order", "src/api/order/cancel/cancel_order.py")
    get = load("get_order", "src/api/order/get/get_order.py")

    monkeypatch.setattr(create, "_table", lambda: fake_table)
    monkeypatch.setattr(listing, "_table", lambda: fake_table)
    monkeypatch.setattr(edit, "_table", lambda: fake_table)
    monkeypatch.setattr(cancel, "_table", lambda: fake_table)
    monkeypatch.setattr(get, "get_order", lambda user, oid: fake_table.items[(user, oid)]["data"])
    monkeypatch.setattr(edit, "get_order", lambda user, oid: fake_table.items[(user, oid)]["data"])

    order_body = {
        "orderId": "o-1", "status": "PLACED", "orderTime": "9999999999",
        "restaurantId": 1, "totalAmount": 19.97, "orderItems": [{"id": 1, "quantity": 1}],
    }
    created = create.add_order(event(order_body))
    assert created["orderId"] == "o-1"
    assert create.add_order(event(order_body)) == created
    assert len(fake_table.items) == 1
    listed = listing.list_orders(event())
    assert len(listed) == 1
    assert listed[0]["orderId"] == created["orderId"]
    assert json.loads(get.lambda_handler(event(), None)["body"])["status"] == "PLACED"
    updated = edit.edit_order(event({"status": "PLACED", "totalAmount": 22.5}))
    assert updated["totalAmount"] == 22.5
    cancelled = cancel.cancel_order(event())
    assert cancelled["status"] == "CANCELED"
