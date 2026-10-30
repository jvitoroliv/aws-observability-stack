# Cross-Border Payments — Cloud Infrastructure & DevSecOps

**Role:** DevSecOps Engineer
**Stack:** AWS (Organizations, Control Tower, SSO, CloudWatch, Lambda, WAF, GuardDuty), Terraform, Bitbucket Pipelines, Python

---

## What's Here

Cloud infrastructure and DevSecOps work from a licensed financial services company operating in cross-border payments. I worked on the AWS multi-account setup, built the monitoring and alerting stack, owned the CI/CD pipelines, and handled security tooling.

The code in this repo covers the monitoring Lambda functions, pipeline configurations, and infrastructure patterns. Production Terraform modules and application code stay with the company.

## AWS Account Structure

The platform ran on AWS Organizations with Control Tower. The account layout followed the standard separation pattern:

| Account | Purpose |
|---------|---------|
| Management | Organizations root, billing, SCPs |
| Log Archive | CloudTrail, Config, VPC Flow Logs (centralized) |
| Audit | Security Hub, GuardDuty findings aggregation |
| Shared Services | CI/CD tooling, shared ECR, internal DNS |
| Development | Dev workloads |
| Staging | Pre-production, integration testing |
| Production | Customer-facing services |

SCPs enforced guardrails: deny root user actions, restrict region usage, block public S3 buckets, require encryption. IAM Identity Center (SSO) managed access across all accounts with permission sets mapped to AD groups.

## Monitoring Stack

The monitoring setup combined CloudWatch native capabilities with custom Lambda functions for business-level alerting:

```python
# Pattern from the monitoring Lambda
# Checks transaction processing latency against SLA thresholds

def check_transaction_sla(event, context):
    cloudwatch = boto3.client('cloudwatch')

    metrics = cloudwatch.get_metric_statistics(
        Namespace='Platform/Transactions',
        MetricName='ProcessingLatency',
        Period=300,
        Statistics=['Average', 'p99'],
        StartTime=datetime.utcnow() - timedelta(minutes=15),
        EndTime=datetime.utcnow()
    )

    for datapoint in metrics['Datapoints']:
        if datapoint['p99'] > SLA_THRESHOLD_MS:
            trigger_alert(
                severity='critical',
                message=f"Transaction p99 latency {datapoint['p99']}ms exceeds SLA threshold {SLA_THRESHOLD_MS}ms"
            )
```

Three layers:

1. **Infrastructure metrics** from CloudWatch native: CPU, memory, disk, network across all accounts. Cross-account metric aggregation into the monitoring account.
2. **Application metrics** via custom CloudWatch namespaces. Services pushed business metrics (transaction counts, processing times, error rates) through the CloudWatch agent.
3. **Custom Lambda monitors** that ran on a schedule (EventBridge), pulled metrics from CloudWatch, applied business logic, and routed alerts to SNS topics split by severity. Critical went to PagerDuty. Warning went to Slack. Info got logged.

## CI/CD

Bitbucket Pipelines for everything. The setup:

| Pipeline | Trigger | What It Does |
|----------|---------|-------------|
| `infra-plan` | PR opened/updated | `terraform plan` against target account, posts plan as PR comment |
| `infra-apply` | Merge to main | `terraform apply` with approval gate for production |
| `app-build` | PR opened/updated | Build, unit tests, SAST scan, container image build |
| `app-deploy-staging` | Merge to develop | Deploy to staging, run integration tests |
| `app-deploy-prod` | Merge to main + approval | Blue/green deploy to production ECS |
| `security-scan` | Nightly schedule | Dependency audit, container image scan, secrets detection |

OIDC federation for AWS authentication. No long-lived access keys in pipeline variables. Each pipeline step assumed a role scoped to the target account with the minimum permissions needed for that step.

## Security Tooling

| Tool | What It Did |
|------|------------|
| **GuardDuty** | Threat detection across all accounts, findings aggregated in Audit account |
| **Security Hub** | Compliance checks (CIS AWS Foundations, PCI DSS), unified findings dashboard |
| **WAF** | Rate limiting, geo-blocking, managed rule groups on CloudFront and ALB |
| **Config** | Configuration compliance rules, drift detection, remediation automation |
| **CloudTrail** | API audit logging to centralized Log Archive account, with integrity validation |
| **Secrets Manager** | Rotation policies for DB credentials and API keys, cross-account access |

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   AWS Organizations                  │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │Management│  │Log Archive│  │      Audit       │  │
│  │  SCPs    │  │CloudTrail │  │  Security Hub    │  │
│  │  Billing │  │  Config   │  │  GuardDuty       │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │            Shared Services                    │   │
│  │  ECR │ CI/CD │ Internal DNS │ Monitoring      │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │   Dev    │  │ Staging  │  │   Production     │  │
│  │          │  │          │  │  ECS + ALB + WAF  │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Design Decisions

**Control Tower over manual Organizations setup.** Landing zone gave us account factory, guardrail inheritance, and a baseline that would pass an audit on day one. The tradeoff: less flexibility in OU structure and some opinionated defaults around logging that we kept rather than fighting.

**OIDC for CI/CD, no access keys.** Bitbucket Pipelines supported OIDC federation natively. Every pipeline step got short-lived credentials scoped to exactly what that step needed. No rotation schedule, no leaked keys in pipeline variables, no shared credentials between environments.

**Lambda monitors over third-party APM.** The team evaluated Datadog and New Relic. Both exceeded the budget by a factor of 3x on projected data volume. CloudWatch was already collecting everything. The Lambda monitors added the business logic layer on top for about $40/month in compute, compared to $3,000+/month for a SaaS APM at our scale.

**Cross-account metric aggregation.** Monitoring account pulled metrics from all workload accounts. One dashboard, one alert routing config, one on-call schedule. Teams could see their own account metrics but alerting was centralized so nothing fell through the gaps.
