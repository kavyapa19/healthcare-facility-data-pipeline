CREATE EXTERNAL TABLE IF NOT EXISTS healthcare_facility_db.facilities_raw (
  facility_id   string,
  facility_name string,
  location      struct<
                   address:string,
                   city:string,
                   state:string,
                   zip:string
                 >,
  employee_count int,
  services       array<string>,
  labs           array<
                   struct<
                     lab_name:string,
                     certifications:array<string>
                   >
                 >,
  accreditations array<
                   struct<
                     accreditation_body:string,
                     accreditation_id:string,
                     valid_until:string
                   >
                 >
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
  'ignore.malformed.json' = 'true'
)
LOCATION 's3://medlaunch-data-pipeline-bucket/data/'
TBLPROPERTIES ('has_encrypted_data'='false');
