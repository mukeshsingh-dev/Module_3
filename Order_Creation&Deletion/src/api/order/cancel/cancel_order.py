import json
import os
import time


class OrderStatusError(Exception):
    status_code = 400


def _table():
    import boto3
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def cancel_order(event):
    user_id = event["requestContext"]["authorizer"]["claims"]["sub"]
    order_id = event["pathParameters"]["orderId"]
    try:
        response = _table().update_item(
            Key={"userId": user_id, "orderId": order_id},
            UpdateExpression="set #data.#status = :new_status",
            ConditionExpression="(#data.#status = :current_status) AND (#data.orderTime > :minOrderTime)",
            ExpressionAttributeNames={"#data": "data", "#status": "status"},
            ExpressionAttributeValues={":current_status": "PLACED", ":minOrderTime": str(time.time() - 600), ":new_status": "CANCELED"},
            ReturnValues="ALL_NEW",
        )
        return response["Attributes"]["data"]
    except Exception as exc:
        code = getattr(getattr(exc, "response", {}).get("Error", {}), "get", lambda *_: None)("Code")
        if code == "ConditionalCheckFailedException":
            raise OrderStatusError(f"Order {order_id} cannot be cancelled") from exc
        raise


def lambda_handler(event, context):
    try:
        return {"statusCode": 200, "headers": {}, "body": json.dumps(cancel_order(event), default=str)}
    except OrderStatusError as exc:
        return {"statusCode": exc.status_code, "body": str(exc)}
