import json
import os
import time
import boto3

athena = boto3.client("athena")
s3 = boto3.client("s3")

ATHENA_DB = os.getenv("ATHENA_DB_NAME", "healthcare_facility_db")
ATHENA_TABLE = os.getenv("ATHENA_TABLE_NAME", "facilities_raw")
ATHENA_OUTPUT = os.getenv(
    "ATHENA_OUTPUT_LOCATION",
    "s3://medlaunch-data-pipeline-bucket/results/"
)

RESULT_BUCKET = os.getenv("RESULT_BUCKET", "medlaunch-data-pipeline-bucket")
RESULT_PREFIX = os.getenv("RESULT_PREFIX", "lambda-query-results/")

MAX_WAIT_SECONDS = int(os.getenv("MAX_ATHENA_WAIT_SECONDS", "150"))
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "3"))


def lambda_handler(event, context):
    print("Received event:", json.dumps(event))

    for record in event.get("Records", []):
        src_bucket = record["s3"]["bucket"]["name"]
        src_key = record["s3"]["object"]["key"]

        if not src_key.lower().endswith(".json"):
            print("File is not JSON, skipping.")
            continue

        query = f"""
        SELECT
          location.state AS state,
          COUNT(DISTINCT facility_id) AS accredited_facility_count
        FROM {ATHENA_TABLE}
        WHERE cardinality(accreditations) > 0
        GROUP BY location.state
        ORDER BY state;
        """

        resp = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": ATHENA_DB},
            ResultConfiguration={"OutputLocation": ATHENA_OUTPUT},
        )

        qid = resp["QueryExecutionId"]
        print("Athena QueryExecutionId:", qid)

        final_state = _wait_for_athena_query(qid, context)

        if final_state != "SUCCEEDED":
            raise Exception(f"Athena query did not succeed. Final state: {final_state}")

        results = _fetch_athena_results(qid)

        timestamp = int(time.time())
        out_key = f"{RESULT_PREFIX}accredited_facilities_{timestamp}.json"

        summary = {
            "source_file": f"s3://{src_bucket}/{src_key}",
            "athena_query_execution_id": qid,
            "results": results
        }

        s3.put_object(
            Bucket=RESULT_BUCKET,
            Key=out_key,
            Body=json.dumps(summary),
            ContentType="application/json",
        )

        print(f"Wrote summary to s3://{RESULT_BUCKET}/{out_key}")

    return {"status": "OK"}


def _wait_for_athena_query(qid, context):
    start = time.time()

    while True:
        resp = athena.get_query_execution(QueryExecutionId=qid)
        status_info = resp["QueryExecution"]["Status"]
        state = status_info["State"]
        reason = status_info.get("StateChangeReason", "")

        print(f"Current Athena status: {state}")
        if reason:
            print(f"Athena status reason: {reason}")

        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            return state

        if context.get_remaining_time_in_millis() < 10000:
            return "TIMED_OUT"

        if (time.time() - start) > MAX_WAIT_SECONDS:
            return "TIMED_OUT"

        time.sleep(POLL_INTERVAL_SECONDS)


def _fetch_athena_results(qid):
    rows = []
    next_token = None
    first = True
    columns = []

    while True:
        args = {"QueryExecutionId": qid}
        if next_token:
            args["NextToken"] = next_token

        resp = athena.get_query_results(**args)
        data_rows = resp["ResultSet"]["Rows"]

        if first:
            columns = [c["VarCharValue"] for c in data_rows[0]["Data"]]
            data_rows = data_rows[1:]
            first = False

        for r in data_rows:
            values = [c.get("VarCharValue") for c in r["Data"]]
            row = dict(zip(columns, values))
            if "accredited_facility_count" in row:
                row["accredited_facility_count"] = int(row["accredited_facility_count"])
            rows.append(row)

        next_token = resp.get("NextToken")
        if not next_token:
            break

    return rows
