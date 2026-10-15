/*
    04 - CSPScheduledItem.sql

    Graph 7001, a 38 node linear chain mirroring Fabric notebook
    10 - Build EventStream.

    One row per node, ids 7010 to 7380 in steps of 10.
    CSPScheduledItemTypeId must be 7. That is what ops.CSPGraphExec looks for to route a
    node to ops.CSPExecGraphNodeTypeSQL. Any other value logs "Critical Failure" and the
    loop exits without executing anything.
    
    ScheduledItemReference matters only for type 1 nodes, where ops.CSPExecGraphNodeTypeGraph
    joins it to CSPScheduleGraphId to find the child graph. Harmless on a type 7 node.
    
    ScriptClassTypeCode 2 is ETL, per the Ops/ETL/Lens mapping in ops.CSPInsertScheduledItemString.

    CURRENT_TIMESTAMP is used rather than GETDATE(), which a Fabric warehouse does not
    support. It takes no parentheses, and the datetime it returns converts implicitly
    into the datetime2 RecordInsertDateTime and RecordUpdateDateTime columns.

    Run order:
        00  list column names
        01  ops.CSPNextExecutionId
        02  ops.CSPExecutionStatus
        03  ops.CSPScheduleGraph
        04  ops.CSPScheduledItem <-- this script
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
--      CSPScheduledItemId
--      CSPScheduledItemTypeId
--      CSPScheduledItemName
--      CSPScheduledItemDescription
--      RecordInsertDateTime
--      RecordUpdateDateTime
--      CSPClientId
--      ScheduledItemReference
--      CspScriptClassCode
--
-- ==============================================================================================

-- ==============================================================================================
--  CLEAR
-- ==============================================================================================

DELETE ops.CSPScheduledItem WHERE CSPScheduledItemId BETWEEN 7010 AND 7380;
GO

-- ==============================================================================================
--  INSERT
-- ==============================================================================================

INSERT INTO ops.CSPScheduledItem
    (
        CSPScheduledItemId,
        CSPScheduledItemTypeId,
        CSPScheduledItemName,
        CSPScheduledItemDescription,
        RecordInsertDateTime,
        RecordUpdateDateTime,
        CSPClientId,
        ScheduledItemReference,
        CspScriptClassCode
    )
VALUES
    (7010, 7, 'Setup - lkp.EventSource', 'Create and populate the EventSource lookup', CURRENT_TIMESTAMP, NULL, 7, 7010, 2),   -- notebook cell 1
    (7020, 7, 'Setup - ods.EventStream', 'Create the EventStream table', CURRENT_TIMESTAMP, NULL, 7, 7020, 2),   -- notebook cell 3
    (7030, 7, 'Setup - ods.EpisodeEventStream', 'Create the EpisodeEventStream table', CURRENT_TIMESTAMP, NULL, 7, 7030, 2),   -- notebook cell 4
    (7040, 7, 'Source 01 - Genesys Calls - MFQ Data', 'Delete and rebuild EventSourceId 1', CURRENT_TIMESTAMP, NULL, 7, 7040, 2),   -- notebook cell 5
    (7050, 7, 'Source 02 - Google Analytics - MFQ Records', 'Delete and rebuild EventSourceId 2', CURRENT_TIMESTAMP, NULL, 7, 7050, 2),   -- notebook cell 6
    (7060, 7, 'Source 03 - Documents Issued - From Relay', 'Delete and rebuild EventSourceId 3', CURRENT_TIMESTAMP, NULL, 7, 7060, 2),   -- notebook cell 7
    (7070, 7, 'Source 04 - Quote Started - Motor Quotes', 'Delete and rebuild EventSourceId 4', CURRENT_TIMESTAMP, NULL, 7, 7070, 2),   -- notebook cell 9
    (7080, 7, 'Source 24 - CC Motor Quotes - Started', 'Delete and rebuild EventSourceId 24', CURRENT_TIMESTAMP, NULL, 7, 7080, 2),   -- notebook cell 10
    (7090, 7, 'Source 05 - Payments - MFQ Motor Quotes', 'Delete and rebuild EventSourceId 5', CURRENT_TIMESTAMP, NULL, 7, 7090, 2),   -- notebook cell 11
    (7100, 7, 'Source 06 - Payments - CallCentre Motor Quotes', 'Delete and rebuild EventSourceId 6', CURRENT_TIMESTAMP, NULL, 7, 7100, 2),   -- notebook cell 13
    (7110, 7, 'Source 07 - Quotes Abandoned - Motor Quotes', 'Delete and rebuild EventSourceId 7', CURRENT_TIMESTAMP, NULL, 7, 7110, 2),   -- notebook cell 14
    (7120, 7, 'Source 27 - CC Motor Quote - Abandoned', 'Delete and rebuild EventSourceId 27', CURRENT_TIMESTAMP, NULL, 7, 7120, 2),   -- notebook cell 15
    (7130, 7, 'Source 08 - Document Uploads - Motor Quotes', 'Delete and rebuild EventSourceId 8', CURRENT_TIMESTAMP, NULL, 7, 7130, 2),   -- notebook cell 16
    (7140, 7, 'Source 09 - Quote Retrieval - MFQ Motor Quotes', 'Delete and rebuild EventSourceId 9', CURRENT_TIMESTAMP, NULL, 7, 7140, 2),   -- notebook cell 17
    (7150, 7, 'Source 10 - Quote Completion Steps - MFQ Motor Quotes', 'Delete and rebuild EventSourceId 10', CURRENT_TIMESTAMP, NULL, 7, 7150, 2),   -- notebook cell 18
    (7160, 7, 'Source 11 - Policy Transactions (NewArchive) - All Policies', 'Delete and rebuild EventSourceId 11', CURRENT_TIMESTAMP, NULL, 7, 7160, 2),   -- notebook cell 19
    (7170, 7, 'Source 12 - Policy Transactions (MTA History) - All Policies', 'Delete and rebuild EventSourceId 12', CURRENT_TIMESTAMP, NULL, 7, 7170, 2),   -- notebook cell 20
    (7180, 7, 'Source 13 - Policy Renewal Start - All Policies', 'Delete and rebuild EventSourceId 13', CURRENT_TIMESTAMP, NULL, 7, 7180, 2),   -- notebook cell 21
    (7190, 7, 'Source 14 - Home Quotes Call Centre Events', 'Delete and rebuild EventSourceId 14', CURRENT_TIMESTAMP, NULL, 7, 7190, 2),   -- notebook cell 22
    (7200, 7, 'Source 15 - Genesys Calls - All calls', 'Delete and rebuild EventSourceId 15', CURRENT_TIMESTAMP, NULL, 7, 7200, 2),   -- notebook cell 23
    (7210, 7, 'Source 16 - Document Chase from Workflow', 'Delete and rebuild EventSourceId 16', CURRENT_TIMESTAMP, NULL, 7, 7210, 2),   -- notebook cell 24
    (7220, 7, 'Source 17 - Events from Applied Renewals', 'Delete and rebuild EventSourceId 17', CURRENT_TIMESTAMP, NULL, 7, 7220, 2),   -- notebook cell 25
    (7230, 7, 'Source 18 - Home Claims', 'Delete and rebuild EventSourceId 18', CURRENT_TIMESTAMP, NULL, 7, 7230, 2),   -- notebook cell 27
    (7240, 7, 'Source 19 - Motor Claims', 'Delete and rebuild EventSourceId 19', CURRENT_TIMESTAMP, NULL, 7, 7240, 2),   -- notebook cell 28
    (7250, 7, 'Source 20 - Customer Portal Login', 'Delete and rebuild EventSourceId 20', CURRENT_TIMESTAMP, NULL, 7, 7250, 2),   -- notebook cell 29
    (7260, 7, 'Source 33 - Online Home Quote - Retrieved', 'Delete and rebuild EventSourceId 33', CURRENT_TIMESTAMP, NULL, 7, 7260, 2),   -- notebook cell 30
    (7270, 7, 'Source 34 - Online Home Quote - Started', 'Delete and rebuild EventSourceId 34', CURRENT_TIMESTAMP, NULL, 7, 7270, 2),   -- notebook cell 31
    (7280, 7, 'Source 35 - Online Home Quote - Progressed', 'Delete and rebuild EventSourceId 35', CURRENT_TIMESTAMP, NULL, 7, 7280, 2),   -- notebook cell 32
    (7290, 7, 'Source 36 - Online Home Quote - Payment Status Success / Failure', 'Delete and rebuild EventSourceId 36', CURRENT_TIMESTAMP, NULL, 7, 7290, 2),   -- notebook cell 33
    (7300, 7, 'Source 37 - Home Insurance - Document Upload for Verification', 'Delete and rebuild EventSourceId 37', CURRENT_TIMESTAMP, NULL, 7, 7300, 2),   -- notebook cell 34
    (7310, 7, 'Source 38 - Quote Completion Steps - Online Home Quotes', 'Delete and rebuild EventSourceId 38', CURRENT_TIMESTAMP, NULL, 7, 7310, 2),   -- notebook cell 35
    (7320, 7, 'Source 39 - Travel Quotes', 'Delete and rebuild EventSourceId 39', CURRENT_TIMESTAMP, NULL, 7, 7320, 2),   -- notebook cell 38
    (7330, 7, 'Source 45 - Unknown source', 'Delete and rebuild EventSourceId 45', CURRENT_TIMESTAMP, NULL, 7, 7330, 2),   -- notebook cell 41
    (7340, 7, 'Source 40 - Traval Transactions', 'Delete and rebuild EventSourceId 40', CURRENT_TIMESTAMP, NULL, 7, 7340, 2),   -- notebook cell 42
    (7350, 7, 'Source 41 - Travel Renewals / Cancellations', 'Delete and rebuild EventSourceId 41', CURRENT_TIMESTAMP, NULL, 7, 7350, 2),   -- notebook cell 43
    (7360, 7, 'Source 42 - Van Quote Journeys - Started / Retrieved', 'Delete and rebuild EventSourceId 42', CURRENT_TIMESTAMP, NULL, 7, 7360, 2),   -- notebook cell 44
    (7370, 7, 'Source 43 - Van Payment Journey', 'Delete and rebuild EventSourceId 43', CURRENT_TIMESTAMP, NULL, 7, 7370, 2),   -- notebook cell 45
    (7380, 7, 'Summary - ods.EventStreamSummary', 'Build the EventStream summary table', CURRENT_TIMESTAMP, NULL, 7, 7380, 2);   -- notebook cell 47
GO

SELECT CSPScheduledItemId, CSPScheduledItemTypeId, CSPScheduledItemName
FROM ops.CSPScheduledItem WHERE CSPScheduledItemId BETWEEN 7010 AND 7380 ORDER BY 1;
--  expect 38 rows
GO
