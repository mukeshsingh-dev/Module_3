import json
import os
from decimal import Decimal
from datetime import datetime

try:
    from aws_lambda_powertools import Logger, Metrics
    from aws_lambda_powertools.metrics import MetricUnit
    from aws_lambda_powertools.utilities.idempotency import (
        IdempotencyConfig,
        DynamoDBPersistenceLayer,
        idempotent_function,
    )
    from aws_lambda_powertools.utilities.typing import LambdaContext
except ImportError:  # Local unit-test fallback; production uses the SAM layer.
    class Logger:
        def info(self, message):
            print(json.dumps({"level": "INFO", "message": message, "service": "orders"}, default=str))

        def inject_lambda_context(self, function):
            return function

    class MetricUnit:
        Count = "Count"

    class Metrics:
        def add_metric(self, name, unit, value):
            self.values = getattr(self, "values", []) + [(name, unit, value)]

        def log_metrics(self, function):
            return function

    class IdempotencyConfig:
        def __init__(self, **kwargs):
            pass

        def register_lambda_context(self, context):
            pass

    class DynamoDBPersistenceLayer:
        def __init__(self, **kwargs):
            pass

    def idempotent_function(data_keyword_argument, config, persistence_store):
        cache = {}

        def decorator(function):
            def wrapper(*args, **kwargs):
                event = kwargs.get(data_keyword_argument) or (args[0] if args else {})
                body = json.loads(event.get("body") or "{}")
                key = (event.get("requestContext", {}).get("authorizer", {}).get("claims", {}).get("sub"), body.get("orderId"))
                if key not in cache:
                    cache[key] = function(*args, **kwargs)
                return cache[key]

            return wrapper

        return decorator


logger = Logger()
metrics = Metrics()
orders_table = os.getenv("TABLE_NAME")
idempotency_table = os.getenv("IDEMPOTENCY_TABLE_NAME")
idempotency_config = IdempotencyConfig(event_key_jmespath="powertools_json(body).orderId")
persistence_layer = DynamoDBPersistenceLayer(table_name=idempotency_table)


def _table():
    import boto3
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


@idempotent_function(data_keyword_argument="event", config=idempotency_config, persistence_store=persistence_layer)
def add_order(event: dict):
    logger.info("Adding a new order")
    detail = json.loads(event["body"], parse_float=Decimal)
    logger.info({"operation": "add_order", "order_details": detail})
    user_id = event["requestContext"]["authorizer"]["claims"]["sub"]
    order_id = detail["orderId"]
    total_amount = detail["totalAmount"]
    order_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    data = {
        "orderId": order_id,
        "userId": user_id,
        "restaurantId": detail["restaurantId"],
        "totalAmount": total_amount,
        "orderItems": detail["orderItems"],
        "status": "PLACED",
        "orderTime": order_time,
    }
    _table().put_item(
        Item={"userId": user_id, "orderId": order_id, "data": data},
        ConditionExpression="attribute_not_exists(orderId) AND attribute_not_exists(userId)",
    )
    metrics.add_metric(name="SuccessfulOrder", unit=MetricUnit.Count, value=1)
    metrics.add_metric(name="OrderTotal", unit=MetricUnit.Count, value=total_amount)
    logger.info(f"new Order with ID {order_id} saved")
    detail["status"] = "PLACED"
    return detail


@metrics.log_metrics
def lambda_handler(event, context: LambdaContext):
    idempotency_config.register_lambda_context(context)
    order_detail = add_order(event=event)
    return {"statusCode": 200, "headers": {}, "body": json.dumps(order_detail, default=str)}
