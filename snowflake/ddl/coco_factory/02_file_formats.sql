-- 02_file_formats.sql
-- File format definitions for RAW ingestion

USE DATABASE COCO_FACTORY;
USE SCHEMA RAW;

CREATE OR REPLACE FILE FORMAT CSV_CANONICAL
    TYPE = CSV
    FIELD_DELIMITER = ','
    RECORD_DELIMITER = '\n'
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    TRIM_SPACE = TRUE
    ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE
    NULL_IF = ('', 'NULL', 'null', 'None')
    COMMENT = 'Standard CSV file format with headers skipped';

CREATE OR REPLACE FILE FORMAT CSV_CANONICAL_GZ
    TYPE = CSV
    FIELD_DELIMITER = ','
    RECORD_DELIMITER = '\n'
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    TRIM_SPACE = TRUE
    ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE
    NULL_IF = ('', 'NULL', 'null', 'None')
    COMPRESSION = GZIP
    COMMENT = 'Gzip-compressed CSV file format with headers skipped';
