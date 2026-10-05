/*
    Script out the 18 objects the ops harness expects to already exist
    Fabric Warehouse, T-SQL, run from SSMS against the source warehouse

    Run section 0 first. It puts the object list in a session temp table that the
    rest of the script reads, so run everything in one connection.

    Order of play:
        0.  the list, plus what each object actually is
        1.  views, scripted from their definition
        2.  tables, with CREATE TABLE built from the column metadata
        3.  a porting check before you run any of it on your own warehouse
*/


-- ---------------------------------------------------------------------------
-- 0. The list, and what each object turns out to be.
--    Run this first and read the ObjectType column: it tells you which of
--    sections 1 and 2 each object belongs in.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS #wanted;

CREATE TABLE #wanted (SchemaName varchar(128), ObjectName varchar(128));

INSERT INTO #wanted (SchemaName, ObjectName) VALUES
    ('ops','GetGraphExecutionStatus'),
    ('ops','CSPScheduleMasterGraphNodeList'),
    ('ops','GetCurrentGraphExecutionId'),
    ('ops','CSPNextAdHocGraphNodeId'),
    ('ops','CSPNextAdHocGraphId'),
    ('ops','getPartitionsData'),
    ('ops','CSPNextExecutionId'),
    ('ops','getTableNames'),
    ('ops','CurrentParameters'),
    ('ops','cspGetFailedLCLTRecordsByGraphId'),
    ('ops','CSPFrameWorkBackupList'),
    ('ops','CSPExecutionStatus'),
    ('ads','SnapShotLookup'),
    ('ads','AnalysisPeriodLookup'),
    ('ads','AnalysisPeriodType'),
    ('stg','Trans_Base_ToDrop'),
    ('stg','Trans_Base_Temp'),
    ('stg','OMNITRANS_ToDrop');

SELECT  w.SchemaName,
        w.ObjectName,
        COALESCE(o.type_desc, 'NOT FOUND')            AS ObjectType,
        o.create_date,
        o.modify_date,
        (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = o.object_id) AS ColumnCount
FROM    #wanted AS w
LEFT JOIN sys.schemas AS s ON s.name = w.SchemaName
LEFT JOIN sys.objects AS o ON o.schema_id = s.schema_id AND o.name = w.ObjectName
ORDER BY w.SchemaName, w.ObjectName;


-- ---------------------------------------------------------------------------
-- 1. Views. Definition straight out of sys.sql_modules, same as the procedures.
-- ---------------------------------------------------------------------------
SELECT  s.name AS SchemaName,
        o.name AS ObjectName,
        DATALENGTH(m.definition) / 2 AS DefinitionChars,
        m.definition                 AS CreateStatement
FROM    #wanted         AS w
JOIN    sys.schemas     AS s ON s.name = w.SchemaName
JOIN    sys.objects     AS o ON o.schema_id = s.schema_id AND o.name = w.ObjectName
JOIN    sys.sql_modules AS m ON m.object_id = o.object_id
ORDER BY s.name, o.name;

/*  A view definition names the tables underneath it. Read those: if a view sits on
    an ops table the harness creates for itself, you get it for free once the
    procedures have run once. If it sits on something else, that something else
    joins this list.                                                              */


-- ---------------------------------------------------------------------------
-- 2. Tables. There is no built in script-table function in T-SQL, so this
--    assembles the DDL from sys.columns.
-- ---------------------------------------------------------------------------
WITH cols AS
(
    SELECT  s.name AS SchemaName,
            o.name AS ObjectName,
            c.column_id,
            '    ' + QUOTENAME(c.name) + ' ' + UPPER(t.name)
            + CASE
                WHEN t.name IN ('varchar','char','varbinary','binary')
                    THEN '(' + CASE WHEN c.max_length = -1 THEN 'MAX'
                                    ELSE CAST(c.max_length AS varchar(10)) END + ')'
                WHEN t.name IN ('nvarchar','nchar')
                    THEN '(' + CASE WHEN c.max_length = -1 THEN 'MAX'
                                    ELSE CAST(c.max_length / 2 AS varchar(10)) END + ')'
                WHEN t.name IN ('decimal','numeric')
                    THEN '(' + CAST(c.precision AS varchar(10)) + ', ' + CAST(c.scale AS varchar(10)) + ')'
                WHEN t.name IN ('datetime2','time','datetimeoffset')
                    THEN '(' + CAST(c.scale AS varchar(10)) + ')'
                WHEN t.name = 'float'
                    THEN '(' + CAST(c.precision AS varchar(10)) + ')'
                ELSE ''
              END
            + CASE WHEN c.is_nullable = 1 THEN ' NULL' ELSE ' NOT NULL' END AS ColumnDef
    FROM    #wanted     AS w
    JOIN    sys.schemas AS s ON s.name = w.SchemaName
    JOIN    sys.objects AS o ON o.schema_id = s.schema_id AND o.name = w.ObjectName
    JOIN    sys.columns AS c ON c.object_id = o.object_id
    JOIN    sys.types   AS t ON t.user_type_id = c.user_type_id
    WHERE   o.type = 'U'
)
SELECT  SchemaName,
        ObjectName,
        'CREATE TABLE ' + QUOTENAME(SchemaName) + '.' + QUOTENAME(ObjectName)
        + CHAR(13) + CHAR(10) + '(' + CHAR(13) + CHAR(10)
        + STRING_AGG(CAST(ColumnDef AS nvarchar(max)), ',' + CHAR(13) + CHAR(10))
              WITHIN GROUP (ORDER BY column_id)
        + CHAR(13) + CHAR(10) + ');' AS CreateStatement
FROM    cols
GROUP BY SchemaName, ObjectName
ORDER BY SchemaName, ObjectName;


-- ---------------------------------------------------------------------------
-- 2b. The same thing as one runnable script, all tables together.
-- ---------------------------------------------------------------------------
WITH cols AS
(
    SELECT  s.name AS SchemaName, o.name AS ObjectName, c.column_id,
            '    ' + QUOTENAME(c.name) + ' ' + UPPER(t.name)
            + CASE
                WHEN t.name IN ('varchar','char','varbinary','binary')
                    THEN '(' + CASE WHEN c.max_length = -1 THEN 'MAX' ELSE CAST(c.max_length AS varchar(10)) END + ')'
                WHEN t.name IN ('nvarchar','nchar')
                    THEN '(' + CASE WHEN c.max_length = -1 THEN 'MAX' ELSE CAST(c.max_length / 2 AS varchar(10)) END + ')'
                WHEN t.name IN ('decimal','numeric')
                    THEN '(' + CAST(c.precision AS varchar(10)) + ', ' + CAST(c.scale AS varchar(10)) + ')'
                WHEN t.name IN ('datetime2','time','datetimeoffset')
                    THEN '(' + CAST(c.scale AS varchar(10)) + ')'
                WHEN t.name = 'float' THEN '(' + CAST(c.precision AS varchar(10)) + ')'
                ELSE ''
              END
            + CASE WHEN c.is_nullable = 1 THEN ' NULL' ELSE ' NOT NULL' END AS ColumnDef
    FROM    #wanted AS w
    JOIN    sys.schemas AS s ON s.name = w.SchemaName
    JOIN    sys.objects AS o ON o.schema_id = s.schema_id AND o.name = w.ObjectName
    JOIN    sys.columns AS c ON c.object_id = o.object_id
    JOIN    sys.types   AS t ON t.user_type_id = c.user_type_id
    WHERE   o.type = 'U'
),
ddl AS
(
    SELECT  SchemaName, ObjectName,
            'DROP TABLE IF EXISTS ' + QUOTENAME(SchemaName) + '.' + QUOTENAME(ObjectName) + ';'
            + CHAR(13) + CHAR(10)
            + 'CREATE TABLE ' + QUOTENAME(SchemaName) + '.' + QUOTENAME(ObjectName)
            + CHAR(13) + CHAR(10) + '(' + CHAR(13) + CHAR(10)
            + STRING_AGG(CAST(ColumnDef AS nvarchar(max)), ',' + CHAR(13) + CHAR(10))
                  WITHIN GROUP (ORDER BY column_id)
            + CHAR(13) + CHAR(10) + ');' + CHAR(13) + CHAR(10) AS Stmt
    FROM    cols
    GROUP BY SchemaName, ObjectName
)
SELECT  STRING_AGG(CAST(Stmt AS nvarchar(max)), CHAR(13) + CHAR(10))
            WITHIN GROUP (ORDER BY SchemaName, ObjectName) AS DeploymentScript
FROM    ddl;


-- ---------------------------------------------------------------------------
-- 3. Porting check. Run this before you run the output on your own warehouse.
--    Anything that comes back needs a decision rather than a copy and paste.
-- ---------------------------------------------------------------------------
SELECT  s.name AS SchemaName,
        o.name AS ObjectName,
        c.name AS ColumnName,
        t.name AS DataType,
        c.is_identity,
        c.is_computed,
        c.default_object_id,
        CASE
            WHEN t.name IN ('nvarchar','nchar','ntext','text','image','money','smallmoney',
                            'datetime','smalldatetime','sql_variant','xml','timestamp',
                            'geography','geometry','hierarchyid')
                 THEN 'type may not be supported in a Fabric Warehouse'
            WHEN c.is_identity = 1  THEN 'IDENTITY is not available in a Fabric Warehouse'
            WHEN c.is_computed = 1  THEN 'computed column, check the expression'
            WHEN c.default_object_id <> 0 THEN 'has a DEFAULT constraint, which section 2 does not script'
            ELSE NULL
        END AS Issue
FROM    #wanted     AS w
JOIN    sys.schemas AS s ON s.name = w.SchemaName
JOIN    sys.objects AS o ON o.schema_id = s.schema_id AND o.name = w.ObjectName
JOIN    sys.columns AS c ON c.object_id = o.object_id
JOIN    sys.types   AS t ON t.user_type_id = c.user_type_id
WHERE   o.type = 'U'
AND     (   t.name IN ('nvarchar','nchar','ntext','text','image','money','smallmoney',
                       'datetime','smalldatetime','sql_variant','xml','timestamp',
                       'geography','geometry','hierarchyid')
         OR c.is_identity = 1
         OR c.is_computed = 1
         OR c.default_object_id <> 0 )
ORDER BY s.name, o.name, c.column_id;

/*  Section 2 scripts columns, types and nullability only. It does not script
    primary keys, unique constraints, defaults, indexes or identity, because a
    Fabric Warehouse either does not support them or only accepts them as
    NOT ENFORCED. For three of these, CSPNextAdHocGraphId, CSPNextAdHocGraphNodeId
    and CSPNextExecutionId, the harness reads and then updates a next value row,
    so they need seeding with a starting row once created.                        */
