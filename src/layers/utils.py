import os


def _table():
    import boto3
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def get_order(user_id, order_id):
    from boto3.dynamodb.conditions import Key

    response = _table().query(
        KeyConditionExpression=Key("userId").eq(user_id) & Key("orderId").eq(order_id)
    )
    items = response.get("Items", [])
    if not items:
        raise LookupError(f"Order {order_id} was not found")
    return items[0]["data"]
