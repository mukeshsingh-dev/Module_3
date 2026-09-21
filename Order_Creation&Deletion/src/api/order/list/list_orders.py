import json
import os


def _table():
    import boto3
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def list_orders(event):
    from boto3.dynamodb.conditions import Key
    user_id = event["requestContext"]["authorizer"]["claims"]["sub"]
    response = _table().query(KeyConditionExpression=Key("userId").eq(user_id))
    return [item["data"] for item in response.get("Items", [])]


def lambda_handler(event, context):
    return {"statusCode": 200, "headers": {}, "body": json.dumps({"orders": list_orders(event)}, default=str)}
