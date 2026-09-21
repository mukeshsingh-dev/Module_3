import json
import os
from decimal import Decimal

try:
    from utils import get_order
except ImportError:
    from src.layers.utils import get_order


def _table():
    import boto3
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def edit_order(event):
    user_id = event["requestContext"]["authorizer"]["claims"]["sub"]
    order_id = event["pathParameters"]["orderId"]
    data = json.loads(event.get("body") or "{}", parse_float=Decimal)
    data.update({"userId": user_id, "orderId": order_id})
    _table().put_item(
        Item={"userId": user_id, "orderId": order_id, "data": data},
        ConditionExpression="attribute_exists(orderId) AND attribute_exists(userId) AND #data.#status = :status",
        ExpressionAttributeNames={"#data": "data", "#status": "status"},
        ExpressionAttributeValues={":status": "PLACED"},
    )
    return get_order(user_id, order_id)


def lambda_handler(event, context):
    return {"statusCode": 200, "headers": {}, "body": json.dumps(edit_order(event), default=str)}
