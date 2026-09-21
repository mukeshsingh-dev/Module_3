# Module 3 — Synchronous + Idempotence

Team Trojans: Sai Vineetha Tirumalla, Shivani Naikoti, Mukesh Singh, Ranadhir

Workshop: https://catalog.workshops.aws/serverless-patterns/en-US/module3

Deployed in `us-east-2`, 7/7 integration tests passing.

What This Builds ##

An Orders service using synchronous API Gateway and Lambda invocation.
Operation	Request path	Integration

##
Create order	POST /orders	API Gateway → Lambda → DynamoDB
List orders	GET /orders	API Gateway → Lambda → DynamoDB
Get order	GET /orders/{orderId}	API Gateway → Lambda layer → DynamoDB
Edit order	PUT /orders/{orderId}	API Gateway → Lambda layer → DynamoDB
Cancel order	DELETE /orders/{orderId}	API Gateway → Lambda layer → DynamoDB

##
The service uses:
- DynamoDB for order storage
- A Lambda layer for shared order lookup logic
- Cognito authorization for every API endpoint
- Powertools idempotency for duplicate order requests
- Structured logging with Powertools
- CloudWatch Embedded Metric Format metrics
- 
##
The user ID comes from:
$context.authorizer.claims.sub
This prevents clients from spoofing another user.
Files
- template.yaml — DynamoDB tables, API Gateway, Lambda functions, Lambda layer, IAM policies
- requirements.txt — Python dependencies
- events/event.json — sample Lambda event
- src/api/order/create/create_order.py — create order, idempotency, logging, and metrics
- src/api/order/get/get_order.py — get one order
- src/api/order/list/list_orders.py — list user orders
- src/api/order/edit/edit_order.py — edit an order
- src/api/order/cancel/cancel_order.py — cancel an order
- src/layers/utils.py — shared DynamoDB order lookup
- tests/test_handlers.py — local handler and idempotency test

##
Deploy
Requires the Users or Module 2 stack because the Orders API uses a Cognito User Pool.
Run in AWS CloudShell or another AWS CLI environment:
aws sts get-caller-identity
aws configure get region
Set the deployment variables:
export AWS_REGION="$(aws configure get region)"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export STACK_NAME="ws-serverless-patterns-orders"
Find the Users stack:
USERS_STACK=$(aws cloudformation describe-stacks \
  --query "Stacks[?starts_with(StackName,'ws-serverless-patterns-users')].StackName | [0]" \
  --output text)

##
echo "$USERS_STACK"
Get the Cognito User Pool ID:
export USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name "$USERS_STACK" \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='UserPool'].OutputValue" \
  --output text)

##
echo "$USER_POOL_ID"
Move to the Orders project:
cd ~/aws-serverless-patterns-workshop/module-3/orders
Build and deploy with SAM:
sam build

##
sam deploy \
  --guided \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
  --parameter-overrides UserPool="$USER_POOL_ID"
When prompted, accept the default values.
Get the deployed API endpoint:
export ORDERS_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='OrdersServiceEndpoint'].OutputValue" \
  --output text)

##
echo "$ORDERS_ENDPOINT"
Test
Run the local tests:
python3 -m pip install -q -r tests/requirements.txt
python3 -m pytest -q
Expected result:
1 passed
The local test verifies:
- Create order
- Retry the same order
- Idempotent duplicate prevention
- List orders
- Get order
- Edit order
- Cancel order

##
For the complete workshop integration tests:
python3 -m pytest tests/integration -v
The workshop version should report approximately:
7 passed

##
Structured Logs
The create-order function logs:
Adding a new order
It also logs structured order data:
{
  "operation": "add_order",
  "order_details": {
    "orderId": "example-order",
    "restaurantId": 1,
    "totalAmount": 19.97
  }
}

##
View Lambda log groups:
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/lambda/" \
  --region "$AWS_REGION"

##
Metrics
Powertools publishes metrics to the CloudWatch namespace:
ServerlessWorkshop
Metrics include:
- SuccessfulOrder
- OrderTotal
List the metrics:
aws cloudwatch list-metrics \
  --namespace ServerlessWorkshop \
  --region "$AWS_REGION"

##
Idempotency
Repeated requests using the same user and orderId return the original result and do not create duplicate DynamoDB records.
The idempotency records are stored in:
IdempotencyTable
The table uses DynamoDB TTL to automatically expire old idempotency records.
Deviation From the Workshop
This project uses the AWS-managed Powertools Lambda layer:
arn:aws:lambda:${AWS::Region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:68
The local test environment does not require AWS credentials because the project includes a lightweight fallback for local testing.
The deployed AWS environment uses the real Powertools layer for:
- Idempotency
- Structured logging
- Metrics
- Lambda context injection

##
Clean Up :

cd ~/workshop/ws-serverless-patterns/orders
sam delete --stack-name ws-serverless-patterns-orders
