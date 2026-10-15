/*
    08 - verify.sql

    Graph 7001, a 38 node linear chain mirroring Fabric notebook
    10 - Build EventStream.

    Read only. Confirms the five scripts above landed before you start the run.

    CURRENT_TIMESTAMP is used rather than GETDATE(), which a Fabric warehouse does not
    support. It takes no parentheses, and the datetime it returns converts implicitly
    into the datetime2 RecordInsertDateTime and RecordUpdateDateTime columns.

    Run order:
        00  list column names
        01  ops.CSPNextExecutionId
        02  ops.CSPExecutionStatus
        03  ops.CSPScheduleGraph
        04  ops.CSPScheduledItem
        05  ops.CSPScheduledItemString
        06  ops.CSPScheduleGraphNode
        07  ops.CSPScheduleGraphSegment
        08  verify <-- this script

    Then: EXECUTE ops.CSPExecuteGenericGraph @cspgraphid = 7001;
*/

-- ==============================================================================================
--  COUNTS
-- ==============================================================================================

SELECT 'graph'    AS Item, count(*) AS [Rows] FROM ops.CSPScheduleGraph        WHERE CSPScheduleGraphId = 7001
UNION ALL SELECT 'items',    count(*) FROM ops.CSPScheduledItem        WHERE CSPScheduledItemId BETWEEN 7010 AND 7380
UNION ALL SELECT 'strings',  count(*) FROM ops.CSPScheduledItemString  WHERE CSPScheduledItemId BETWEEN 7010 AND 7380 AND CSPScheduledItemCurrentFlag = 1
UNION ALL SELECT 'nodes',    count(*) FROM ops.CSPScheduleGraphNode    WHERE CSPScheduleGraphNodeId BETWEEN 7010 AND 7380
UNION ALL SELECT 'segments', count(*) FROM ops.CSPScheduleGraphSegment WHERE CSPScheduleGraphId = 7001;
--  expect 1 / 38 / 38 / 38 / 37
GO

-- ==============================================================================================
--  EVERY NODE RESOLVES TO A TYPE 7 ITEM WITH A CURRENT SQL STRING
-- ==============================================================================================

--  This is the join ops.CSPExecGraphNodeTypeSQL uses. Any row returned here is a node
--  that will fail to find its SQL at run time.

SELECT c.CSPScheduleGraphNodeId
FROM ops.CSPScheduleGraphNode AS c
       LEFT OUTER JOIN ops.CSPScheduledItem AS b
       ON c.CSPScheduledItemId = b.CSPScheduledItemId AND b.CSPScheduledItemTypeId = 7
       LEFT OUTER JOIN ops.CSPScheduledItemString AS a
       ON a.CSPScheduledItemId = b.CSPScheduledItemId AND a.CSPScheduledItemCurrentFlag = 1
WHERE c.CSPScheduleGraphNodeId BETWEEN 7010 AND 7380
       AND (b.CSPScheduledItemId IS NULL OR a.CSPScheduledItemId IS NULL);
--  expect no rows
GO

-- ==============================================================================================
--  RUN IT
-- ==============================================================================================

--  EXECUTE ops.CSPExecuteGenericGraph @cspgraphid = 7001;
