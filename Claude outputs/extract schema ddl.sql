/*
    extract schema ddl.sql

    Scripts out every table, view, function and stored procedure in one schema, as
    runnable CREATE statements, one statement per row.

    Point it at the source server that holds the original ops harness. The output is
    meant to replace the reconstructed definitions in the ported copy, where eight
    tables and one function are currently inferred from how the harness uses them
    rather than from the real thing.

    WHAT ENGINE THIS ASSUMES

    SQL Server 2017 or later, or Azure SQL Database. That is what the harness source
    looks like: it uses STRING_AGG with WITHIN GROUP, DROP TABLE IF EXISTS, THROW, and
    ALTER TABLE ... SWITCH PARTITION $PARTITION.Pf_HASH_BY_DATETIME(...), which is the
    SQL Server form of partition switching rather than the Synapse one.

    If the server turns out to be a Synapse dedicated pool or a Fabric warehouse,
    STRING_AGG and parts of the catalogue used below are not available there. Section 7
    is a metadata dump that works anywhere, so fall back to that and say so.

    HOW TO RUN IT

    Read the APPENDIX at the bottom first if you are pulling the whole schema out. The
    SSMS grid is what destroyed the line breaks in the original port, and the appendix
    says how to avoid repeating that.

    Short version: set @SchemaName in section 0, run the whole file once in SSMS to
    review, then run it through sqlcmd with -y 0 to write a .sql file.

    HOW IT IS PUT TOGETHER

    Section 1 builds one temp table, #ddl, holding every statement with a sort key.
    Everything after that reads #ddl, so the heavy work happens once. Temp tables
    survive GO within a connection, so run the file in one go, in one window.

    Sections:
        0  configuration, and an inventory of what is in the schema
        1  build #ddl
        2  tables
        3  indexes, foreign keys and check constraints
        4  views, functions and procedures
        5  anything that did not script, and why
        6  THE EXTRACT: everything in dependency order, ready to pipe to a file
        7  raw column metadata, as a cross-check and as the fallback for Synapse
        8  the two objects this exercise exists to recover

    WHAT IT DOES NOT DO

    Triggers, sequences, synonyms, user defined types, security, extended properties,
    and the partition functions and schemes themselves. Section 5 lists anything in the
    schema it skipped, so nothing goes missing quietly. A CREATE TABLE that lands on a
    partition scheme does carry its ON clause, but the scheme has to exist on the target
    first.

    Collations are emitted per column only where the column differs from the database
    default, which is the SSMS convention and keeps the output readable.
*/


-- ==============================================================================================
--  0.  CONFIGURATION AND INVENTORY
--
--  Set the schema name here. Everything else reads it from #cfg, which survives the GO
--  separators as long as you stay in the same query window.
--
--  QuietMode 1 suppresses the review result sets in sections 2, 3, 4, 5, 7 and 8, so
--  that a sqlcmd run emits only the extract in section 6. Leave it 0 while you are
--  reading the output in SSMS.
-- ==============================================================================================

DROP TABLE IF EXISTS #cfg;

CREATE TABLE #cfg (SchemaName sysname NOT NULL, QuietMode BIT NOT NULL);

INSERT INTO #cfg (SchemaName, QuietMode)
VALUES ('ops', 0);
GO

--  Confirm you are on the right server and database before anything else.

SELECT @@SERVERNAME AS ServerName,
       DB_NAME() AS DatabaseName,
       CAST (SERVERPROPERTY('ProductVersion') AS VARCHAR (32)) AS ProductVersion,
       CAST (SERVERPROPERTY('EngineEdition') AS VARCHAR (4)) AS EngineEdition,
       CAST (DATABASEPROPERTYEX(DB_NAME(), 'Collation') AS VARCHAR (128)) AS DatabaseCollation,
       (SELECT SchemaName FROM #cfg) AS SchemaBeingScripted;

--  EngineEdition 3 is Enterprise or Developer, 5 is Azure SQL Database, 6 is a Synapse
--  dedicated pool, 11 is a Fabric warehouse. 6 and 11 mean section 1 will not run.
GO

--  What is actually in the schema. Read this before anything else: the counts here are
--  what section 6 has to account for.

SELECT o.type AS TypeCode,
       o.type_desc AS ObjectType,
       count(*) AS [Count]
FROM sys.objects AS o
     INNER JOIN
     sys.schemas AS s
     ON s.schema_id = o.schema_id
WHERE s.name = (SELECT SchemaName FROM #cfg)
      AND o.is_ms_shipped = 0
GROUP BY o.type, o.type_desc
ORDER BY o.type_desc;
GO

SELECT o.type_desc AS ObjectType,
       o.name AS ObjectName,
       o.create_date,
       o.modify_date
FROM sys.objects AS o
     INNER JOIN
     sys.schemas AS s
     ON s.schema_id = o.schema_id
WHERE s.name = (SELECT SchemaName FROM #cfg)
      AND o.is_ms_shipped = 0
      AND o.type IN ('U', 'V', 'P', 'FN', 'IF', 'TF', 'AF', 'PC')
ORDER BY o.type_desc, o.name;
GO


-- ==============================================================================================
--  1.  BUILD #ddl
--
--  One row per statement. Seq orders the whole extract so it can be run top to bottom:
--      100  tables
--      200  indexes
--      300  check constraints
--      400  foreign keys
--      500  views
--      600  functions
--      700  procedures
--
--  Tables come first, then the things that depend on them. Views, functions and
--  procedures are ordered by name within their group rather than by dependency, which
--  is fine for procedures because T-SQL defers name resolution, and fine for scalar and
--  table valued functions as long as no function references another one. Section 5
--  flags it if one does.
-- ==============================================================================================

DROP TABLE IF EXISTS #ddl;

CREATE TABLE #ddl (
    Seq INT NOT NULL,
    ObjectType VARCHAR (60) NOT NULL,
    SchemaName SYSNAME NOT NULL,
    ObjectName SYSNAME NOT NULL,
    Statement NVARCHAR (MAX) NOT NULL );
GO

-- ----------------------------------------------------------------------------------------------
--  1a.  TABLES
--
--  Columns, computed columns, identity, defaults, non-default collations, then the
--  primary key and any unique constraints, then the ON clause for a partition scheme or
--  a non-default filegroup.
-- ----------------------------------------------------------------------------------------------

DECLARE @Schema AS SYSNAME = (SELECT SchemaName FROM #cfg);
DECLARE @DbCollation AS NVARCHAR (128) = CAST (DATABASEPROPERTYEX(DB_NAME(), 'Collation') AS NVARCHAR (128));

WITH cols
AS (SELECT c.object_id,
           Ord = c.column_id,
           Line = '    ' + QUOTENAME(c.name) + ' '
                  + CASE
                        WHEN c.is_computed = 1
                            THEN 'AS ' + COALESCE (cc.definition, '(NULL)')
                                 + CASE WHEN cc.is_persisted = 1 THEN ' PERSISTED' ELSE '' END
                        ELSE QUOTENAME(ty.name)
                             + CASE
                                   WHEN ty.name IN ('varchar', 'char', 'varbinary', 'binary')
                                       THEN '(' + CASE WHEN c.max_length = -1 THEN 'MAX'
                                                       ELSE CAST (c.max_length AS VARCHAR (10)) END + ')'
                                   WHEN ty.name IN ('nvarchar', 'nchar')
                                       THEN '(' + CASE WHEN c.max_length = -1 THEN 'MAX'
                                                       ELSE CAST (c.max_length / 2 AS VARCHAR (10)) END + ')'
                                   WHEN ty.name IN ('decimal', 'numeric')
                                       THEN '(' + CAST (c.precision AS VARCHAR (10)) + ', '
                                                + CAST (c.scale AS VARCHAR (10)) + ')'
                                   WHEN ty.name IN ('datetime2', 'datetimeoffset', 'time')
                                       THEN '(' + CAST (c.scale AS VARCHAR (10)) + ')'
                                   WHEN ty.name = 'float'
                                       THEN '(' + CAST (c.precision AS VARCHAR (10)) + ')'
                                   ELSE ''
                               END
                             + CASE WHEN c.collation_name IS NOT NULL
                                         AND c.collation_name <> @DbCollation
                                    THEN ' COLLATE ' + c.collation_name
                                    ELSE '' END
                             + CASE WHEN ic.object_id IS NOT NULL
                                    THEN ' IDENTITY(' + CONVERT (VARCHAR (40), ic.seed_value) + ', '
                                                      + CONVERT (VARCHAR (40), ic.increment_value) + ')'
                                    ELSE '' END
                             + CASE WHEN c.is_nullable = 1 THEN ' NULL' ELSE ' NOT NULL' END
                             + CASE WHEN dc.object_id IS NOT NULL
                                    THEN ' CONSTRAINT ' + QUOTENAME(dc.name) + ' DEFAULT ' + dc.definition
                                    ELSE '' END
                    END
    FROM sys.columns AS c
         INNER JOIN sys.tables AS t ON t.object_id = c.object_id
         INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
         INNER JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
         LEFT OUTER JOIN sys.computed_columns AS cc
             ON cc.object_id = c.object_id AND cc.column_id = c.column_id
         LEFT OUTER JOIN sys.identity_columns AS ic
             ON ic.object_id = c.object_id AND ic.column_id = c.column_id
         LEFT OUTER JOIN sys.default_constraints AS dc
             ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id
    WHERE s.name = @Schema
          AND t.is_ms_shipped = 0),
     keycols
AS (SELECT i.object_id,
           i.index_id,
           KeyList = STRING_AGG(CAST (QUOTENAME(kc.name) + CASE WHEN xc.is_descending_key = 1 THEN ' DESC' ELSE ' ASC' END AS NVARCHAR (MAX)), ', ')
                     WITHIN GROUP (ORDER BY xc.key_ordinal)
    FROM sys.indexes AS i
         INNER JOIN sys.index_columns AS xc
             ON xc.object_id = i.object_id AND xc.index_id = i.index_id AND xc.key_ordinal > 0
         INNER JOIN sys.columns AS kc
             ON kc.object_id = xc.object_id AND kc.column_id = xc.column_id
    GROUP BY i.object_id, i.index_id),
     constraints
AS (SELECT i.object_id,
           Ord = 1000000 + i.index_id,
           Line = '    CONSTRAINT ' + QUOTENAME(i.name) + ' '
                  + CASE WHEN i.is_primary_key = 1 THEN 'PRIMARY KEY' ELSE 'UNIQUE' END
                  + CASE WHEN i.type_desc = 'CLUSTERED' THEN ' CLUSTERED' ELSE ' NONCLUSTERED' END
                  + ' (' + k.KeyList + ')'
    FROM sys.indexes AS i
         INNER JOIN sys.tables AS t ON t.object_id = i.object_id
         INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
         INNER JOIN keycols AS k ON k.object_id = i.object_id AND k.index_id = i.index_id
    WHERE s.name = @Schema
          AND t.is_ms_shipped = 0
          AND (i.is_primary_key = 1 OR i.is_unique_constraint = 1)),
     body
AS (SELECT object_id, Ord, Line FROM cols
    UNION ALL
    SELECT object_id, Ord, Line FROM constraints),
     storage
AS (SELECT i.object_id,
           OnClause = CASE
                          WHEN ps.name IS NOT NULL
                              THEN ' ON ' + QUOTENAME(ps.name) + ' (' + QUOTENAME(pc.name) + ')'
                          WHEN fg.name IS NOT NULL AND fg.name <> 'PRIMARY'
                              THEN ' ON ' + QUOTENAME(fg.name)
                          ELSE ''
                      END
    FROM sys.indexes AS i
         LEFT OUTER JOIN sys.partition_schemes AS ps ON ps.data_space_id = i.data_space_id
         LEFT OUTER JOIN sys.filegroups AS fg ON fg.data_space_id = i.data_space_id
         LEFT OUTER JOIN sys.index_columns AS pic
             ON pic.object_id = i.object_id AND pic.index_id = i.index_id AND pic.partition_ordinal > 0
         LEFT OUTER JOIN sys.columns AS pc
             ON pc.object_id = pic.object_id AND pc.column_id = pic.column_id
    WHERE i.index_id IN (0, 1))
INSERT INTO #ddl (Seq, ObjectType, SchemaName, ObjectName, Statement)
SELECT 100,
       'TABLE',
       @Schema,
       t.name,
       'DROP TABLE IF EXISTS ' + QUOTENAME(@Schema) + '.' + QUOTENAME(t.name) + ';' + char(13) + char(10)
       + 'GO' + char(13) + char(10) + char(13) + char(10)
       + 'CREATE TABLE ' + QUOTENAME(@Schema) + '.' + QUOTENAME(t.name) + ' (' + char(13) + char(10)
       + (SELECT STRING_AGG(CAST (b.Line AS NVARCHAR (MAX)), ',' + char(13) + char(10)) WITHIN GROUP (ORDER BY b.Ord)
          FROM body AS b
          WHERE b.object_id = t.object_id)
       + char(13) + char(10) + ')' + COALESCE (st.OnClause, '') + ';' + char(13) + char(10)
       + 'GO'
FROM sys.tables AS t
     INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
     LEFT OUTER JOIN storage AS st ON st.object_id = t.object_id
WHERE s.name = @Schema
      AND t.is_ms_shipped = 0;
GO

-- ----------------------------------------------------------------------------------------------
--  1b.  INDEXES
--
--  Everything that is not already carried by a primary key or unique constraint above.
--  Rowstore indexes keep their key list, included columns, filter and uniqueness.
--  Columnstore indexes are handled separately because they have no key ordering.
-- ----------------------------------------------------------------------------------------------

DECLARE @Schema AS SYSNAME = (SELECT SchemaName FROM #cfg);

WITH keylist
AS (SELECT i.object_id,
           i.index_id,
           Keys = STRING_AGG(CAST (CASE WHEN xc.is_included_column = 0
                                       THEN QUOTENAME(c.name) + CASE WHEN xc.is_descending_key = 1 THEN ' DESC' ELSE ' ASC' END
                                       END AS NVARCHAR (MAX)), ', ')
                  WITHIN GROUP (ORDER BY xc.key_ordinal),
           Included = STRING_AGG(CAST (CASE WHEN xc.is_included_column = 1 THEN QUOTENAME(c.name) END AS NVARCHAR (MAX)), ', ')
                      WITHIN GROUP (ORDER BY xc.index_column_id),
           AllCols = STRING_AGG(CAST (QUOTENAME(c.name) AS NVARCHAR (MAX)), ', ') WITHIN GROUP (ORDER BY xc.index_column_id)
    FROM sys.indexes AS i
         INNER JOIN sys.index_columns AS xc
             ON xc.object_id = i.object_id AND xc.index_id = i.index_id
         INNER JOIN sys.columns AS c
             ON c.object_id = xc.object_id AND c.column_id = xc.column_id
    GROUP BY i.object_id, i.index_id)
INSERT INTO #ddl (Seq, ObjectType, SchemaName, ObjectName, Statement)
SELECT 200,
       'INDEX',
       @Schema,
       t.name + '.' + i.name,
       CASE
           WHEN i.type = 5
               THEN 'CREATE CLUSTERED COLUMNSTORE INDEX ' + QUOTENAME(i.name)
                    + ' ON ' + QUOTENAME(@Schema) + '.' + QUOTENAME(t.name) + ';'
           WHEN i.type = 6
               THEN 'CREATE NONCLUSTERED COLUMNSTORE INDEX ' + QUOTENAME(i.name)
                    + ' ON ' + QUOTENAME(@Schema) + '.' + QUOTENAME(t.name)
                    + ' (' + k.AllCols + ');'
           ELSE 'CREATE ' + CASE WHEN i.is_unique = 1 THEN 'UNIQUE ' ELSE '' END
                + i.type_desc COLLATE DATABASE_DEFAULT + ' INDEX ' + QUOTENAME(i.name)
                + ' ON ' + QUOTENAME(@Schema) + '.' + QUOTENAME(t.name)
                + ' (' + k.Keys + ')'
                + CASE WHEN k.Included IS NOT NULL THEN ' INCLUDE (' + k.Included + ')' ELSE '' END
                + CASE WHEN i.has_filter = 1 THEN ' WHERE ' + i.filter_definition ELSE '' END + ';'
       END + char(13) + char(10) + 'GO'
FROM sys.indexes AS i
     INNER JOIN sys.tables AS t ON t.object_id = i.object_id
     INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
     LEFT OUTER JOIN keylist AS k ON k.object_id = i.object_id AND k.index_id = i.index_id
WHERE s.name = @Schema
      AND t.is_ms_shipped = 0
      AND i.index_id > 0
      AND i.is_primary_key = 0
      AND i.is_unique_constraint = 0
      AND i.type IN (1, 2, 5, 6);
GO

-- ----------------------------------------------------------------------------------------------
--  1c.  CHECK CONSTRAINTS AND FOREIGN KEYS
--
--  Separate ALTER TABLE statements rather than inline, so the tables can all be created
--  first and the references resolved afterwards. WITH CHECK or WITH NOCHECK is carried
--  across, because a constraint that was not trusted on the source should not silently
--  become trusted on the target.
-- ----------------------------------------------------------------------------------------------

DECLARE @Schema AS SYSNAME = (SELECT SchemaName FROM #cfg);

INSERT INTO #ddl (Seq, ObjectType, SchemaName, ObjectName, Statement)
SELECT 300,
       'CHECK',
       @Schema,
       t.name + '.' + cc.name,
       'ALTER TABLE ' + QUOTENAME(@Schema) + '.' + QUOTENAME(t.name)
       + ' WITH ' + CASE WHEN cc.is_not_trusted = 1 THEN 'NOCHECK' ELSE 'CHECK' END
       + ' ADD CONSTRAINT ' + QUOTENAME(cc.name) + ' CHECK ' + cc.definition + ';'
       + char(13) + char(10) + 'GO'
FROM sys.check_constraints AS cc
     INNER JOIN sys.tables AS t ON t.object_id = cc.parent_object_id
     INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
WHERE s.name = @Schema
      AND t.is_ms_shipped = 0;

WITH fkcols
AS (SELECT fkc.constraint_object_id,
           Parent = STRING_AGG(CAST (QUOTENAME(pc.name) AS NVARCHAR (MAX)), ', ') WITHIN GROUP (ORDER BY fkc.constraint_column_id),
           Ref = STRING_AGG(CAST (QUOTENAME(rc.name) AS NVARCHAR (MAX)), ', ') WITHIN GROUP (ORDER BY fkc.constraint_column_id)
    FROM sys.foreign_key_columns AS fkc
         INNER JOIN sys.columns AS pc
             ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id
         INNER JOIN sys.columns AS rc
             ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id
    GROUP BY fkc.constraint_object_id)
INSERT INTO #ddl (Seq, ObjectType, SchemaName, ObjectName, Statement)
SELECT 400,
       'FOREIGN KEY',
       @Schema,
       t.name + '.' + fk.name,
       'ALTER TABLE ' + QUOTENAME(@Schema) + '.' + QUOTENAME(t.name)
       + ' WITH ' + CASE WHEN fk.is_not_trusted = 1 THEN 'NOCHECK' ELSE 'CHECK' END
       + ' ADD CONSTRAINT ' + QUOTENAME(fk.name)
       + ' FOREIGN KEY (' + f.Parent + ')'
       + ' REFERENCES ' + QUOTENAME(rs.name) + '.' + QUOTENAME(rt.name) + ' (' + f.Ref + ')'
       + CASE fk.delete_referential_action WHEN 1 THEN ' ON DELETE CASCADE'
                                           WHEN 2 THEN ' ON DELETE SET NULL'
                                           WHEN 3 THEN ' ON DELETE SET DEFAULT'
                                           ELSE '' END
       + CASE fk.update_referential_action WHEN 1 THEN ' ON UPDATE CASCADE'
                                           WHEN 2 THEN ' ON UPDATE SET NULL'
                                           WHEN 3 THEN ' ON UPDATE SET DEFAULT'
                                           ELSE '' END + ';'
       + char(13) + char(10) + 'GO'
FROM sys.foreign_keys AS fk
     INNER JOIN sys.tables AS t ON t.object_id = fk.parent_object_id
     INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
     INNER JOIN sys.tables AS rt ON rt.object_id = fk.referenced_object_id
     INNER JOIN sys.schemas AS rs ON rs.schema_id = rt.schema_id
     INNER JOIN fkcols AS f ON f.constraint_object_id = fk.object_id
WHERE s.name = @Schema
      AND t.is_ms_shipped = 0;
GO

-- ----------------------------------------------------------------------------------------------
--  1d.  VIEWS, FUNCTIONS AND PROCEDURES
--
--  Straight out of sys.sql_modules, which holds the source exactly as it was submitted,
--  line breaks and comments and all. Nothing is reformatted.
--
--  The CREATE is prefixed with a matching DROP ... IF EXISTS rather than rewritten to
--  CREATE OR ALTER, so the definition itself stays untouched.
--
--  Note that sys.sql_modules.definition is NULL for an encrypted module. Section 5
--  lists any that come back empty.
-- ----------------------------------------------------------------------------------------------

DECLARE @Schema AS SYSNAME = (SELECT SchemaName FROM #cfg);

INSERT INTO #ddl (Seq, ObjectType, SchemaName, ObjectName, Statement)
SELECT CASE o.type WHEN 'V' THEN 500
                   WHEN 'P' THEN 700
                   ELSE 600 END,
       o.type_desc COLLATE DATABASE_DEFAULT,
       @Schema,
       o.name,
       'DROP ' + CASE o.type WHEN 'V' THEN 'VIEW' WHEN 'P' THEN 'PROCEDURE' ELSE 'FUNCTION' END
       + ' IF EXISTS ' + QUOTENAME(@Schema) + '.' + QUOTENAME(o.name) + ';' + char(13) + char(10)
       + 'GO' + char(13) + char(10) + char(13) + char(10)
       + m.definition + char(13) + char(10)
       + 'GO'
FROM sys.sql_modules AS m
     INNER JOIN sys.objects AS o ON o.object_id = m.object_id
     INNER JOIN sys.schemas AS s ON s.schema_id = o.schema_id
WHERE s.name = @Schema
      AND o.is_ms_shipped = 0
      AND o.type IN ('V', 'P', 'FN', 'IF', 'TF')
      AND m.definition IS NOT NULL;
GO


-- ==============================================================================================
--  2.  TABLES
--
--  Review only. One row per table. Click a Statement cell to read it.
-- ==============================================================================================

IF (SELECT QuietMode FROM #cfg) = 0
    SELECT ObjectName,
           DATALENGTH(Statement) / 2 AS [Length],
           Statement
    FROM #ddl
    WHERE Seq = 100
    ORDER BY ObjectName;
GO


-- ==============================================================================================
--  3.  INDEXES, FOREIGN KEYS AND CHECK CONSTRAINTS
--
--  Review only. Often empty on a harness schema, which is itself worth knowing: it means
--  the tables are heaps with no keys, and the reconstructed copy is not missing any.
-- ==============================================================================================

IF (SELECT QuietMode FROM #cfg) = 0
    SELECT ObjectType,
           ObjectName,
           Statement
    FROM #ddl
    WHERE Seq IN (200, 300, 400)
    ORDER BY Seq, ObjectName;
GO


-- ==============================================================================================
--  4.  VIEWS, FUNCTIONS AND PROCEDURES
--
--  Review only. Length is the giveaway for a truncated copy, so note it before you
--  extract and check it again afterwards.
-- ==============================================================================================

IF (SELECT QuietMode FROM #cfg) = 0
    SELECT ObjectType,
           ObjectName,
           DATALENGTH(Statement) / 2 AS [Length],
           Statement
    FROM #ddl
    WHERE Seq IN (500, 600, 700)
    ORDER BY Seq, ObjectName;
GO


-- ==============================================================================================
--  5.  WHAT DID NOT SCRIPT
--
--  Three checks. Anything these return has to be dealt with by hand, and the point of
--  running them is that nothing goes missing without you knowing.
-- ==============================================================================================

IF (SELECT QuietMode FROM #cfg) = 0
BEGIN
    --  5a. Objects in the schema that section 1 does not handle at all.
    SELECT 'not handled by this script' AS Issue,
           o.type_desc AS ObjectType,
           o.name AS ObjectName
    FROM sys.objects AS o
         INNER JOIN sys.schemas AS s ON s.schema_id = o.schema_id
    WHERE s.name = (SELECT SchemaName FROM #cfg)
          AND o.is_ms_shipped = 0
          AND o.type NOT IN ('U', 'V', 'P', 'FN', 'IF', 'TF',
                             'PK', 'UQ', 'F', 'C', 'D')
    UNION ALL
    --  5b. Modules whose definition came back NULL, which means encrypted or no permission.
    SELECT 'definition unreadable, encrypted or no VIEW DEFINITION',
           o.type_desc,
           o.name
    FROM sys.sql_modules AS m
         INNER JOIN sys.objects AS o ON o.object_id = m.object_id
         INNER JOIN sys.schemas AS s ON s.schema_id = o.schema_id
    WHERE s.name = (SELECT SchemaName FROM #cfg)
          AND m.definition IS NULL
    UNION ALL
    --  5c. Objects in the schema that produced no row in #ddl.
    SELECT 'in the schema but not scripted',
           o.type_desc,
           o.name
    FROM sys.objects AS o
         INNER JOIN sys.schemas AS s ON s.schema_id = o.schema_id
    WHERE s.name = (SELECT SchemaName FROM #cfg)
          AND o.is_ms_shipped = 0
          AND o.type IN ('U', 'V', 'P', 'FN', 'IF', 'TF')
          AND NOT EXISTS (SELECT 1 FROM #ddl AS d
                          WHERE d.ObjectName = o.name AND d.Seq IN (100, 500, 600, 700));

    --  5d. What this schema reaches outside itself, and what it reaches that does not
    --      exist. Anything listed has to be dealt with before the extract will run
    --      cleanly on the target, and the Status column is what tells you whether the
    --      schema is self-contained.
    --
    --      This reads sys.sql_expression_dependencies, a catalogue view, rather than
    --      sys.dm_sql_referenced_entities. The DMV raises error 2020 the moment it meets
    --      an entity that references something which does not exist, and this schema has
    --      at least one of those, so the DMV would fail the whole query.
    SELECT COALESCE (dep.referenced_schema_name, '(not schema qualified)') AS ReferencedSchema,
           dep.referenced_entity_name AS ReferencedObject,
           CASE WHEN dep.referenced_id IS NULL THEN 'DOES NOT EXIST' ELSE 'exists' END AS Status,
           count(DISTINCT o.name) AS ReferencedByCount,
           STRING_AGG(CAST (o.name AS NVARCHAR (MAX)), ', ') WITHIN GROUP (ORDER BY o.name) AS ReferencedBy
    FROM sys.sql_expression_dependencies AS dep
         INNER JOIN sys.objects AS o ON o.object_id = dep.referencing_id
         INNER JOIN sys.schemas AS s ON s.schema_id = o.schema_id
    WHERE s.name = (SELECT SchemaName FROM #cfg)
          AND o.is_ms_shipped = 0
          AND dep.referenced_entity_name IS NOT NULL
          AND (dep.referenced_id IS NULL
               OR COALESCE (dep.referenced_schema_name, '') <> (SELECT SchemaName FROM #cfg))
    GROUP BY dep.referenced_schema_name, dep.referenced_entity_name, dep.referenced_id
    ORDER BY Status DESC, ReferencedSchema, ReferencedObject;
END
GO


-- ==============================================================================================
--  6.  THE EXTRACT
--
--  This is the one to pipe to a file. Everything in #ddl, in dependency order, one
--  statement per row, each already carrying its own DROP and its trailing GO.
--
--  Run the file through sqlcmd as the appendix describes and this is the only result
--  set you get, so the output is a runnable .sql file with no editing.
-- ==============================================================================================

SELECT Statement + char(13) + char(10) AS [--]
FROM #ddl
ORDER BY Seq, ObjectName;
GO


-- ==============================================================================================
--  7.  RAW COLUMN METADATA
--
--  A cross-check on section 2, and the fallback if the server turns out to be a Synapse
--  pool or a Fabric warehouse where section 1 will not run. Small enough to copy out of
--  the grid without anything being mangled, because every value is short.
--
--  This is the one to send over first if you want the eight inferred table shapes
--  settled before anything else.
-- ==============================================================================================

IF (SELECT QuietMode FROM #cfg) = 0
    SELECT t.name AS TableName,
           c.column_id AS Position,
           c.name AS ColumnName,
           ty.name AS DataType,
           c.max_length AS MaxLength,
           c.precision AS [Precision],
           c.scale AS Scale,
           c.is_nullable AS IsNullable,
           c.is_identity AS IsIdentity,
           c.is_computed AS IsComputed,
           c.collation_name AS CollationName,
           dc.definition AS DefaultDefinition
    FROM sys.tables AS t
         INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
         INNER JOIN sys.columns AS c ON c.object_id = t.object_id
         INNER JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
         LEFT OUTER JOIN sys.default_constraints AS dc
             ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id
    WHERE s.name = (SELECT SchemaName FROM #cfg)
          AND t.is_ms_shipped = 0
    ORDER BY t.name, c.column_id;
GO


-- ==============================================================================================
--  8.  THE TWO OBJECTS THIS EXERCISE EXISTS TO RECOVER
--
--  The ported harness calls ops.cspGetFailedLCLTRecordsByGraphId but never creates it,
--  and names ops.cspGetMissingLCLTRecordsByGraphId in a log message. Both have been
--  reconstructed or left out in the ported copy. These two queries settle them.
--
--  The second one widens the search to the whole database and every schema, in case
--  they live somewhere other than ops.
-- ==============================================================================================

IF (SELECT QuietMode FROM #cfg) = 0
BEGIN
    SELECT s.name AS SchemaName,
           o.name AS ObjectName,
           o.type_desc AS ObjectType,
           m.definition
    FROM sys.sql_modules AS m
         INNER JOIN sys.objects AS o ON o.object_id = m.object_id
         INNER JOIN sys.schemas AS s ON s.schema_id = o.schema_id
    WHERE o.name IN ('cspGetFailedLCLTRecordsByGraphId',
                     'cspGetMissingLCLTRecordsByGraphId');

    --  Anything in the database whose name looks like it belongs to this family, in case
    --  the spelling differs.
    SELECT s.name AS SchemaName,
           o.name AS ObjectName,
           o.type_desc AS ObjectType
    FROM sys.objects AS o
         INNER JOIN sys.schemas AS s ON s.schema_id = o.schema_id
    WHERE o.name LIKE '%LCLT%'
          OR o.name LIKE '%GetFailed%'
          OR o.name LIKE '%GetMissing%'
    ORDER BY s.name, o.name;
END
GO


/*
    ==============================================================================================
    APPENDIX.  GETTING THE OUTPUT OUT WITHOUT MANGLING IT
    ==============================================================================================

    This matters more than the script. The original port of this harness was copied out
    of an SSMS grid, which turned every line break into a space, and the indentation had
    to be reconstructed by hand afterwards. sys.sql_modules.definition holds the line
    breaks correctly. It is the copy out of the grid that destroys them.

    BEST: sqlcmd straight to a file

        Set QuietMode to 1 in section 0 first, so only section 6 produces output.

        sqlcmd -S yourserver.database.windows.net -d YourDatabase -G ^
               -i "extract schema ddl.sql" -o "ops_schema.sql" ^
               -y 0 -h -1 -W -s ""

            -G   Entra ID authentication. Drop it and add -E for Windows authentication,
                 or -U and -P for SQL authentication
            -y 0 do not truncate long values. Without it you get 256 characters per row
            -h -1 no column headers
            -W   trim trailing spaces
            -s ""  no column separator

        Check the result: the file should start with DROP TABLE IF EXISTS and the line
        count should be in the thousands, not the dozens.

        If any single procedure is over 1 MB, sqlcmd will still clip it. Nothing in this
        harness is close, but section 4 prints the lengths so you can confirm.

    ALSO GOOD: PowerShell

        Invoke-Sqlcmd -ServerInstance yourserver -Database YourDatabase `
                      -InputFile "extract schema ddl.sql" -MaxCharLength 2147483647 |
            Select-Object -ExpandProperty "--" |
            Out-File -FilePath "ops_schema.sql" -Encoding utf8

        -MaxCharLength is the one that matters. The default is 4000 and it truncates
        silently.

    IN SSMS, IF YOU HAVE TO

        Do not copy multiple rows out of the grid. Copying more than one row at a time is
        what flattens the line breaks.

        Instead, in Tools, Options, Query Results, SQL Server, Results to Grid, set
        "Maximum Characters Retrieved" for Non XML data to 2000000 and XML data to
        Unlimited. Then click a single Statement cell, which opens it in its own tab with
        the line breaks intact, and save that tab.

        That is fine for the two functions in section 8. It is tedious for 50 objects,
        which is why sqlcmd is the answer for the full extract.

    THE NATIVE ALTERNATIVE

        If this is a real SQL Server or Azure SQL and you have SSMS pointed at it, the
        Generate Scripts wizard does all of this properly and handles triggers,
        sequences, permissions and dependency ordering, which this script does not.

            Right click the database, Tasks, Generate Scripts, Select specific database
            objects, tick the ops objects, Advanced, set "Script DROP and CREATE" to
            "Script DROP and CREATE", set "Types of data to script" to "Schema only",
            then save to file.

        Use the wizard if it is available. Use this script when it is not, when you want
        one schema only without clicking through a tree, or when you want the output in a
        shape you can diff against the ported copy.

    WHAT TO DO WITH THE RESULT

        Diff it against the ported harness. The eight tables currently marked INFERRED in
        the deployment script are the ones to check first:

            CSPExecutionStrings            CspLogStreamMetrics
            CSPExecutionMasterGraph        CspLogStreamMetricMeasure
            CSPExecutionMasterGraphNode    CspLogStreamMetricResults
            CSPLoadLog                     CspExportTablesList

        Then ops.cspGetFailedLCLTRecordsByGraphId, which is currently a reconstruction.

        Watch for identity columns in particular. CspLogStreamMetrics.CspLogMetricId is
        almost certainly an identity on the source, and Fabric has no identity, so
        whatever comes back has to be replaced with something that assigns the key
        explicitly.
*/
