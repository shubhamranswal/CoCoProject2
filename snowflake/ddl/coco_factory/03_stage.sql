-- 03_stage.sql
-- Internal stage definition for loading the canonical dataset files

USE DATABASE COCO_FACTORY;
USE SCHEMA RAW;

CREATE STAGE IF NOT EXISTS FACTORY_STAGE
    FILE_FORMAT = CSV_CANONICAL
    COMMENT = 'Internal stage holding canonical manufacturing CSV and CSV.GZ source files';
