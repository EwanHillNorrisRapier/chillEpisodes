/*
    1 - check schemas.sql

    Deploying the ops harness into a new Fabric warehouse. Read only, nothing is
    created here.

    Three scripts, and nothing else:
        1  check schemas                     <-- this script
        2  create everything and seed it
        3  insert a dummy graph and run it

    Script 2 is self-contained. It carries the whole of create_harness_trimmed.sql
    inside it, so there is no separate harness file to run. Scripts 1, 2 and 3 in
    order leave the harness deployed and ready to test.

    WHAT THIS CHECKS

    Three schemas have to exist. Only one of them is needed to create the harness,
    the other two are needed the first time certain procedures run, and the failure
    then is a run time error inside dynamic SQL rather than a create time one, which
    is harder to read.

        ops   every one of the 50 harness objects, and all 23 of its tables
        stg   ops.CSPTableCopy writes stg.CSPx
              ops.CSPValidateSourceRecords writes stg.cspvsr_x and stg.cspvsr_y
        trk   ops.CSPValidateSourceRecords builds one trk.DQF_<tablename> table per
              table it validates, through dynamic SQL

    Schemas a graph's own node SQL writes into are a separate matter and are not
    checked here. For the Build EventStream graph those are lkp and ods.

    A note on case. Fabric warehouses are case sensitive, so sys.schemas has to be
    matched on the exact lower case spellings above. A schema called OPS is not the
    schema the harness wants.
*/

-- ==============================================================================================
--  WHERE AM I
-- ==============================================================================================

--  Worth a glance before anything else. Running a deployment against the wrong
--  warehouse is the easiest mistake to make here.

SELECT DB_NAME() AS CurrentDatabase,
       CAST (DATABASEPROPERTYEX(DB_NAME(), 'Collation') AS VARCHAR (128)) AS CurrentCollation;
GO

-- ==============================================================================================
--  THE SCHEMAS
-- ==============================================================================================

SELECT r.SchemaName,
       CASE WHEN s.name IS NULL THEN 'MISSING' ELSE 'present' END AS Status,
       r.RequiredBy
FROM (SELECT 'ops' AS SchemaName,
             'Every harness object. Nothing works without it' AS RequiredBy
      UNION ALL
      SELECT 'stg',
             'ops.CSPTableCopy writes stg.CSPx. ops.CSPValidateSourceRecords writes stg.cspvsr_x and stg.cspvsr_y'
      UNION ALL
      SELECT 'trk',
             'ops.CSPValidateSourceRecords builds a trk.DQF_<tablename> table per table it validates') AS r
     LEFT OUTER JOIN
     sys.schemas AS s
     ON s.name = r.SchemaName
ORDER BY r.SchemaName;

--  Expect three rows, all reading 'present'. Any row reading 'MISSING' needs the
--  matching statement below running.
GO

-- ==============================================================================================
--  CREATE THE MISSING ONES
-- ==============================================================================================

--  Left commented on purpose, so this script stays read only. Uncomment only the
--  ones the query above reported as MISSING.
--
--  CREATE SCHEMA ops;
--  GO
--  CREATE SCHEMA stg;
--  GO
--  CREATE SCHEMA trk;
--  GO

-- ==============================================================================================
--  WHAT IS ALREADY IN ops
-- ==============================================================================================

--  On a genuinely new warehouse this returns nothing. If it returns rows, the
--  harness is being deployed over something, and script 2 will leave those tables
--  alone rather than replacing them, so check this list matches what you expect.

SELECT s.name AS SchemaName,
       o.name AS ObjectName,
       o.type_desc AS ObjectType,
       o.create_date
FROM sys.objects AS o
     INNER JOIN
     sys.schemas AS s
     ON s.schema_id = o.schema_id
WHERE s.name IN ('ops', 'stg', 'trk')
      AND o.type IN ('U', 'V', 'P', 'FN', 'IF', 'TF')
ORDER BY s.name, o.type_desc, o.name;
GO
