/*
    01 - CSPNextExecutionId.sql

    Graph 7001, a 38 node linear chain mirroring Fabric notebook
    10 - Build EventStream.

    Seeds the execution id counter with its single row. ops.CSPStartNewGraphExecution
    increments this row to get the next execution id, so an empty table silently
    yields execution id 0. Skip this script if the table already has a row.
    
    Nothing here is specific to graph 7001.

    CURRENT_TIMESTAMP is used rather than GETDATE(), which a Fabric warehouse does not
    support. It takes no parentheses, and the datetime it returns converts implicitly
    into the datetime2 RecordInsertDateTime and RecordUpdateDateTime columns.

    Run order:
        00  list column names
        01  ops.CSPNextExecutionId <-- this script
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
--  COLUMN NAMES
-- ==============================================================================================
--
--  Every name below was read from sys.columns on the target warehouse, in the order
--  the table declares them, so the list matches the table exactly:
--      cspExecutionId
--
-- ==============================================================================================

IF NOT EXISTS (SELECT 1 FROM ops.CSPNextExecutionId)
    INSERT INTO ops.CSPNextExecutionId
        (
            cspExecutionId
        )
    VALUES (0);
GO

SELECT * FROM ops.CSPNextExecutionId;
GO
