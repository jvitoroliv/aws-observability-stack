"""
turn_on_off_lambda.py

Lambda function definitions
"""

import json
import os
import requests

# Entry point for Lambda invocation. Keep handler thin — delegate to service layer.
def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))

    log_event = event['awslogs']['data']
    print("Log event: " + json.dumps(log_event, indent=2))
    
    # Send a signal to Prometheus
    # Configuration via environment variables — see Terraform Lambda resource for source
    pushgateway_url = os.environ.get('pushgateway.dev.fintech.example.com')
    metric_name = 'cloudwatch_logs_metric'
    job_name = 'lambda_log_processor'

    response = requests.post(f'{pushgateway_url}/metrics/job/{job_name}', data=f'{metric_name} 1\n')
    print('Response from Pushgateway:', response.text)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Done')
    }
