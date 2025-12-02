CREATE TABLE healthcare_facility_db.facility_accreditation_summary
WITH (
  format = 'PARQUET',
  external_location = 's3://medlaunch-data-pipeline-bucket/results/facility_accreditation_summary/'
) AS
SELECT
  f.facility_id,
  f.facility_name,
  f.employee_count,
  cardinality(f.services) AS number_of_offered_services,
  MIN(CAST(a.valid_until AS date)) AS expiry_date_of_first_accreditation
FROM
  healthcare_facility_db.facilities_raw AS f
CROSS JOIN UNNEST(f.accreditations) AS t(a)
GROUP BY
  f.facility_id,
  f.facility_name,
  f.employee_count,
  cardinality(f.services)
ORDER BY
  f.facility_id;
