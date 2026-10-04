/*
    Script out every stored procedure in a schema
    Fabric Warehouse / SQL analytics endpoint, T-SQL, run from SSMS

    Three ways of getting the same thing. Pick the one that suits what you are doing:
        1. inventory with the definition in a grid column
        2. the same, rendered so nothing is truncated
        3. one runnable deployment script for the whole schema

    sp_helptext is not available in Fabric, and it chops at 4000 characters anyway,
    so all three read sys.sql_modules instead.
*/


-- ---------------------------------------------------------------------------
-- 1. Inventory. One row per procedure, definition in the last column.
-- ---------------------------------------------------------------------------
SELECT  s.name                            AS SchemaName,
        p.name                            AS ProcedureName,
        p.create_date                     AS Created,
        p.modify_date                     AS LastModified,
        DATALENGTH(m.definition) / 2      AS DefinitionChars,
        m.definition                      AS CreateStatement
FROM    sys.sql_modules AS m
JOIN    sys.procedures  AS p ON p.object_id = m.object_id
JOIN    sys.schemas     AS s ON s.schema_id = p.schema_id
WHERE   s.name = 'ops'
ORDER   BY p.name;

/*  SSMS truncates the grid at 65,535 characters per cell, and results to text at 8,192.
    Check DefinitionChars against that before trusting what you see. If anything is over,
    use query 2.                                                                        */


-- ---------------------------------------------------------------------------
-- 2. Same list, but each definition comes back as a clickable cell that opens
--    in full in a new query window. Nothing gets truncated.
-- ---------------------------------------------------------------------------
SELECT  s.name AS SchemaName,
        p.name AS ProcedureName,
        CAST('<?query --' + CHAR(13) + CHAR(10)
             + m.definition
             + CHAR(13) + CHAR(10) + '--?>' AS xml) AS CreateStatement
FROM    sys.sql_modules AS m
JOIN    sys.procedures  AS p ON p.object_id = m.object_id
JOIN    sys.schemas     AS s ON s.schema_id = p.schema_id
WHERE   s.name = 'ops'
ORDER   BY p.name;

/*  The cast fails if a procedure body contains the two characters ?> , which is rare
    but happens inside dynamic SQL. If one row errors, fall back to query 1 for that
    procedure and raise the grid limit in Tools, Options, Query Results, SQL Server,
    Results to Grid.                                                                   */


-- ---------------------------------------------------------------------------
-- 3. The whole schema as one deployment script, batch separated, ready to run
--    against another warehouse.
-- ---------------------------------------------------------------------------
SELECT  STRING_AGG(
            CAST(
                'DROP PROCEDURE IF EXISTS ' + QUOTENAME(s.name) + '.' + QUOTENAME(p.name) + ';'
                + CHAR(13) + CHAR(10) + 'GO' + CHAR(13) + CHAR(10)
                + m.definition
                + CHAR(13) + CHAR(10) + 'GO' + CHAR(13) + CHAR(10)
            AS nvarchar(max)),
            CHAR(13) + CHAR(10)
        ) WITHIN GROUP (ORDER BY p.name) AS DeploymentScript
FROM    sys.sql_modules AS m
JOIN    sys.procedures  AS p ON p.object_id = m.object_id
JOIN    sys.schemas     AS s ON s.schema_id = p.schema_id
WHERE   s.name = 'ops';

/*  The CAST to nvarchar(max) matters. Without it STRING_AGG overflows at 8,000 bytes
    and throws rather than truncating quietly.

    Procedure order does not matter here. T-SQL defers name resolution, so a procedure
    that calls another will create even if the one it calls does not exist yet.        */


-- ---------------------------------------------------------------------------
-- Bonus. The signatures on their own, for working out how to call the harness.
-- ---------------------------------------------------------------------------
SELECT  s.name AS SchemaName,
        p.name AS ProcedureName,
        prm.parameter_id,
        prm.name AS ParameterName,
        t.name   AS DataType,
        prm.max_length,
        prm.precision,
        prm.scale,
        prm.is_output,
        prm.has_default_value,
        prm.default_value
FROM    sys.procedures AS p
JOIN    sys.schemas    AS s ON s.schema_id = p.schema_id
LEFT JOIN sys.parameters AS prm ON prm.object_id = p.object_id
LEFT JOIN sys.types      AS t   ON t.user_type_id = prm.user_type_id
WHERE   s.name = 'ops'
ORDER   BY p.name, prm.parameter_id;
