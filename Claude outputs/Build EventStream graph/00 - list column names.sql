/*
    00 - list column names.sql

    Graph 7001, a 38 node linear chain mirroring Fabric notebook
    10 - Build EventStream.

    Read only. Dumps the real column names and order for the seven tables these scripts
    write to, so the column lists in 03, 04, 06 and 07 can be checked before you run them.
    
    Four of those tables are never written with a named INSERT anywhere in the harness, so
    their column names could not be read off the code. Paste the output back and I will
    correct the scripts.

    CURRENT_TIMESTAMP is used rather than GETDATE(), which a Fabric warehouse does not
    support. It takes no parentheses, and the datetime it returns converts implicitly
    into the datetime2 RecordInsertDateTime and RecordUpdateDateTime columns.

    Run order:
        00  list column names <-- this script
        01  ops.CSPNextExecutionId
        02  ops.CSPExecutionStatus
        03  ops.CSPScheduleGraph
        04  ops.CSPScheduledItem
        05  ops.CSPScheduledItemString
        06  ops.CSPScheduleGraphNode
        07  ops.CSPScheduleGraphSegment
        08  verify

    Then: EXECUTE ops.CSPExecuteGenericGraph @cspgraphid = 7001;
*/

-- ==============================================================================================
--  COLUMN NAMES IN ORDER
-- ==============================================================================================

SELECT  t.name                AS TableName,
        c.column_id           AS Position,
        c.name                AS ColumnName,
        ty.name               AS DataType,
        c.max_length          AS MaxLength,
        c.is_nullable         AS IsNullable
FROM    sys.tables AS t
        JOIN sys.schemas AS s  ON s.schema_id = t.schema_id
        JOIN sys.columns AS c  ON c.object_id = t.object_id
        JOIN sys.types   AS ty ON ty.user_type_id = c.user_type_id
WHERE   s.name = 'ops'
        AND t.name IN (
            'CSPNextExecutionId',
            'CSPExecutionStatus',
            'CSPScheduleGraph',
            'CSPScheduledItem',
            'CSPScheduledItemString',
            'CSPScheduleGraphNode',
            'CSPScheduleGraphSegment' )
ORDER BY t.name, c.column_id;
GO

-- ==============================================================================================
--  ANY OF THE SEVEN THAT DO NOT EXIST YET
-- ==============================================================================================

SELECT w.TableName
FROM   (VALUES
           ('CSPNextExecutionId'),
           ('CSPExecutionStatus'),
           ('CSPScheduleGraph'),
           ('CSPScheduledItem'),
           ('CSPScheduledItemString'),
           ('CSPScheduleGraphNode'),
           ('CSPScheduleGraphSegment')) AS w (TableName)
WHERE  NOT EXISTS (SELECT 1
                   FROM   sys.tables AS t
                          JOIN sys.schemas AS s ON s.schema_id = t.schema_id
                   WHERE  s.name = 'ops'
                          AND t.name = w.TableName);
--  expect no rows
GO
