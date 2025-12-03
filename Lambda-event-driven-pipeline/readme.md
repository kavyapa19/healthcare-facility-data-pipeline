# MedLaunch Event-Driven Data Pipeline (S3 + Athena + Lambda)

This project implements Stage 3 **event-driven analytics pipeline** on AWS to process healthcare facility accreditation data.

When a **new JSON file** is uploaded to S3, an **AWS Lambda** function automatically:

1. Triggers on the S3 event (File uploaded to S3) 
2. Executes an **Athena query** to count **accredited facilities per state**  
3. Stores a **summary JSON result** back into S3  

The pipeline uses:

- **Amazon S3** – raw data and analytics outputs  
- **AWS Glue Data Catalog** – Athena table metadata  
- **Amazon Athena** – serverless SQL over S3  
- **AWS Lambda** – event-driven processing  
- **Amazon CloudWatch Logs** – logging and debugging  

---
## Architecture diagram
![Architecture diagram](assets/eventdriven-pipeline.drawio.png)


## Pipeline Steps

## step1: Data Ingestion & Athena Setup
Upload raw JSON files to S3:

Location: 
```
s3://medlaunch-data-pipeline-bucket/data/
```

Each file contains facility records with fields like:

facility_id

name

location (including state)

accreditations (array)

## Step 2: Create Athena database:
Created from stage 1 (./sql/01_create_database.sql)

## step 3: Create Athena table
Created from stage 1 (./sql/02_create_facilities_raw_table.sql)

## step 4: Athena Query: Accredited Facilities per State

Validation query in Athena
With healthcare_facility_db selected:

```sql
SELECT
  location.state AS state,
  COUNT(DISTINCT facility_id) AS accredited_facility_count
FROM facilities_raw
WHERE cardinality(accreditations) > 0
GROUP BY location.state
ORDER BY state;
```

## Step 5: Event-Driven Processing with Lambda

Lambda Function:
Runtime: Python 3.1

Name (example): Event-Driven-lambda-function

Timeout: 3–5 minutes (to give Athena enough time)

Memory: 128 MB (sufficient for this use case)

Environment Variables:
```
| Key                       | Value                                          |
| ------------------------- | ---------------------------------------------- |
| `ATHENA_DB_NAME`          | `healthcare_facility_db`                       |
| `ATHENA_TABLE_NAME`       | `facilities_raw`                               |
| `ATHENA_OUTPUT_LOCATION`  | `s3://medlaunch-data-pipeline-bucket/results/` |
| `RESULT_BUCKET`           | `medlaunch-data-pipeline-bucket`               |
| `RESULT_PREFIX`           | `lambda-query-results/`                        |
| `MAX_ATHENA_WAIT_SECONDS` | `150` (for example)                            |
| `POLL_INTERVAL_SECONDS`   | `3`                                            |

```

## Step 6: IAM Permissions :

The Lambda execution role needs permissions for:
Athena:
```json
{
  "Effect": "Allow",
  "Action": [
    "athena:StartQueryExecution",
    "athena:GetQueryExecution",
    "athena:GetQueryResults"
  ],
  "Resource": "*"
}
```
Glue:
```json
{
  "Effect": "Allow",
  "Action": [
    "glue:GetDatabase",
    "glue:GetDatabases",
    "glue:GetTable",
    "glue:GetTables",
    "glue:GetPartition",
    "glue:GetPartitions"
  ],
  "Resource": [
    "arn:aws:glue:us-east-1:230232161862:catalog",
    "arn:aws:glue:us-east-1:230232161862:database/healthcare_facility_db",
    "arn:aws:glue:us-east-1:230232161862:table/healthcare_facility_db/facilities_raw"
  ]
}
```
S3:
```json
[
  {
    "Effect": "Allow",
    "Action": [ "s3:GetObject" ],
    "Resource": "arn:aws:s3:::medlaunch-data-pipeline-bucket/data/*"
  },
  {
    "Effect": "Allow",
    "Action": [ "s3:GetBucketLocation", "s3:ListBucket" ],
    "Resource": "arn:aws:s3:::medlaunch-data-pipeline-bucket"
  },
  {
    "Effect": "Allow",
    "Action": [ "s3:GetObject", "s3:PutObject" ],
    "Resource": "arn:aws:s3:::medlaunch-data-pipeline-bucket/results/*"
  },
  {
    "Effect": "Allow",
    "Action": [ "s3:PutObject" ],
    "Resource": "arn:aws:s3:::medlaunch-data-pipeline-bucket/lambda-query-results/*"
  }
]
Cloudwatch:

```json
{
  "Effect": "Allow",
  "Action": [
    "logs:CreateLogGroup",
    "logs:CreateLogStream",
    "logs:PutLogEvents"
  ],
  "Resource": "arn:aws:logs:*:*:*"
}
```
Add the following IAM permissions to Lambda Role

## Step 7: Lambda Trigger Configuration
In the Lambda console → Configuration → Triggers:

Trigger: S3

Bucket: medlaunch-data-pipeline-bucket

Event type: All object create events (or PUT)

Prefix: data/

This ensures:

Any time a *.json file is created under data/, the Lambda function is invoked.


## Step 8: Testing
Prepare a sample json file
```json
{
  "facility_id": "FAC001",
  "name": "Sunrise Medical Center",
  "location": {
    "address": "123 Main St",
    "city": "Los Angeles",
    "state": "CA",
    "zip": "90001"
  },
  "accreditations": [
    {
      "type": "Cardiology",
      "issuer": "American Heart Association",
      "issued_date": "2021-03-15",
      "valid_until": "2025-03-15"
    }
  ]
}
```
Upload the file to:
```text
s3://medlaunch-data-pipeline-bucket/data/alternate-test.json
```
Verify Lambda execution:
Go to CloudWatch Logs → Log groups → /aws/lambda/Event-Driven-lambda-function

Confirm there is a new log stream with messages similar to:

Received event: ...

New file uploaded: s3://medlaunch-data-pipeline-bucket/data/alternate-test.json

Current Athena status: SUCCEEDED

Check summary output in S3:
```text
s3://medlaunch-data-pipeline-bucket/lambda-query-results/accredited_facilities_per_state_<timestamp>.json
```
