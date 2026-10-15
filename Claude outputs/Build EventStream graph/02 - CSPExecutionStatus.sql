/*
    02 - CSPExecutionStatus.sql

    Graph 7001, a 38 node linear chain mirroring Fabric notebook
    10 - Build EventStream.

    Seeds the execution status lookup. ops.CSPSetGraphExecutionStatus checks every
    status code against this table and throws 51000 if it is not found, which happens
    at the end of every run. Skip this script if the table is already populated.
    
    The codes are the ones the harness actually sets. Descriptions are mine, so change
    them if your own wording differs. Nothing here is specific to graph 7001.

    CURRENT_TIMESTAMP is used rather than GETDATE(), which a Fabric warehouse does not
    support. It takes no parentheses, and the datetime it returns converts implicitly
    into the datetime2 RecordInsertDateTime and RecordUpdateDateTime columns.

    Run order:
        00  list column names
        01  ops.CSPNextExecutionId
        02  ops.CSPExecutionStatus <-- this script
        03  ops.CSPScheduleGraph
        04  ops.CSPScheduledItem
        05  ops.CSPScheduledItemString
        06  ops.CSPScheduleGraphNode
        07  ops.CSPScheduleGraphSegment
        08  verify

    Then: EXECUTE ops.CSPExecuteGenericGraph @cspgraphid = 7001;
*/

-- ==============================================================================================
--  COLUMN NAMES
-- ==============================================================================================
--
--  Every name below was read from sys.columns on the target warehouse, in the order
--  the table declares them, so the list matches the table exactly:
--      CSPExecutionStatusCode
--      CSPExecutionStatusDescription
--
-- ==============================================================================================

IF NOT EXISTS (SELECT 1 FROM ops.CSPExecutionStatus)
    INSERT INTO ops.CSPExecutionStatus
        (
            CSPExecutionStatusCode,
            CSPExecutionStatusDescription
        )
    VALUES
        (0, 'Not Started'),
        (1, 'Started'),
        (2, 'In Progress'),
        (3, 'Stopped'),
        (4, 'Failed'),
        (5, 'Restarted'),
        (6, 'Abandoned'),
        (7, 'Completed');
GO

SELECT * FROM ops.CSPExecutionStatus ORDER BY CSPExecutionStatusCode;
GO
