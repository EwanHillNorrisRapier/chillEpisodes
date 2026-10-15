/*
    03 - CSPScheduleGraph.sql

    Graph 7001, a 38 node linear chain mirroring Fabric notebook
    10 - Build EventStream.

    Registers graph 7001. ops.CSPStartNewGraphExecution refuses to open an execution
    unless a row exists here for the graph id, and the failure is silent until
    ops.CSPExecGraphPrep throws "Execution Stopped".
    
    Graph type 4 is the value ops.CSPExecuteSingleItem uses for an ad-hoc graph. It is the
    only example in the harness and nothing on the execution path reads it, so change it if
    your own type list says otherwise.

    CURRENT_TIMESTAMP is used rather than GETDATE(), which a Fabric warehouse does not
    support. It takes no parentheses, and the datetime it returns converts implicitly
    into the datetime2 RecordInsertDateTime and RecordUpdateDateTime columns.

    Run order:
        00  list column names
        01  ops.CSPNextExecutionId
        02  ops.CSPExecutionStatus
        03  ops.CSPScheduleGraph <-- this script
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
--      CSPScheduleGraphId
--      CSPScheduleGraphTypeId
--      CSPScheduleGraphName
--      CSPScheduleGraphDescription
--      RecordInsertDateTime
--      RecordUpdateDateTime
--      CSPClientId
--
-- ==============================================================================================

-- ==============================================================================================
--  CLEAR
-- ==============================================================================================

DELETE ops.CSPScheduleGraph WHERE CSPScheduleGraphId = 7001;
GO

-- ==============================================================================================
--  INSERT
-- ==============================================================================================

INSERT INTO ops.CSPScheduleGraph
    (
        CSPScheduleGraphId,
        CSPScheduleGraphTypeId,
        CSPScheduleGraphName,
        CSPScheduleGraphDescription,
        RecordInsertDateTime,
        RecordUpdateDateTime,
        CSPClientId
    )
VALUES
    (7001, 4, 'Build EventStream', 'Mirror of Fabric notebook 10 - Build EventStream', CURRENT_TIMESTAMP, NULL, 7);
GO

SELECT * FROM ops.CSPScheduleGraph WHERE CSPScheduleGraphId = 7001;
GO
