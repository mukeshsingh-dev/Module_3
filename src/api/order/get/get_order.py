import json

try:
    from utils import get_order
except ImportError:
    from src.layers.utils import get_order


def lambda_handler(event, context):
    user_id = event["requestContext"]["authorizer"]["claims"]["sub"]
    order_id = event["pathParameters"]["orderId"]
    return {"statusCode": 200, "headers": {}, "body": json.dumps(get_order(user_id, order_id), default=str)}
