/*
    06 - CSPScheduleGraphNode.sql

    Graph 7001, a 38 node linear chain mirroring Fabric notebook
    10 - Build EventStream.

    One row per node, pointing each node at its scheduled item.
    Node ids match item ids one for one here, which is the convention
    ops.CSPInsertScheduledItemString uses when it creates nodes itself.
    
    CSPScheduleGraphNodeName is varchar(50) and seven of the source names are longer than
    that, so names are trimmed to 50 at a word boundary here. The full name is kept in
    CSPScheduleGraphNodeDescription, and script 04 carries it untrimmed because
    CSPScheduledItemName is varchar(100). That is why a few node names are shorter than
    their matching item names.
    
    Note there is no graph id on this table. A node belongs to a graph only through the
    segments in script 07.

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
        06  ops.CSPScheduleGraphNode <-- this script
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
--      CSPScheduleGraphNodeId
--      CSPScheduleGraphNodeName
--      CSPScheduleGraphNodeDescription
--      CSPScheduledItemId
--      RecordInsertDateTime
--      RecordUpdateDateTime
--      CSPClientId
--
-- ==============================================================================================

-- ==============================================================================================
--  CLEAR
-- ==============================================================================================

DELETE ops.CSPScheduleGraphNode WHERE CSPScheduleGraphNodeId BETWEEN 7010 AND 7380;
GO

-- ==============================================================================================
--  INSERT
-- ==============================================================================================

INSERT INTO ops.CSPScheduleGraphNode
    (
        CSPScheduleGraphNodeId,
        CSPScheduleGraphNodeName,
        CSPScheduleGraphNodeDescription,
        CSPScheduledItemId,
        RecordInsertDateTime,
        RecordUpdateDateTime,
        CSPClientId
    )
VALUES
    (7010, 'Setup - lkp.EventSource', 'Setup - lkp.EventSource. Create and populate the EventSource lookup', 7010, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 1
    (7020, 'Setup - ods.EventStream', 'Setup - ods.EventStream. Create the EventStream table', 7020, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 3
    (7030, 'Setup - ods.EpisodeEventStream', 'Setup - ods.EpisodeEventStream. Create the EpisodeEventStream table', 7030, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 4
    (7040, 'Source 01 - Genesys Calls - MFQ Data', 'Source 01 - Genesys Calls - MFQ Data. Delete and rebuild EventSourceId 1', 7040, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 5
    (7050, 'Source 02 - Google Analytics - MFQ Records', 'Source 02 - Google Analytics - MFQ Records. Delete and rebuild EventSourceId 2', 7050, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 6
    (7060, 'Source 03 - Documents Issued - From Relay', 'Source 03 - Documents Issued - From Relay. Delete and rebuild EventSourceId 3', 7060, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 7
    (7070, 'Source 04 - Quote Started - Motor Quotes', 'Source 04 - Quote Started - Motor Quotes. Delete and rebuild EventSourceId 4', 7070, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 9
    (7080, 'Source 24 - CC Motor Quotes - Started', 'Source 24 - CC Motor Quotes - Started. Delete and rebuild EventSourceId 24', 7080, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 10
    (7090, 'Source 05 - Payments - MFQ Motor Quotes', 'Source 05 - Payments - MFQ Motor Quotes. Delete and rebuild EventSourceId 5', 7090, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 11
    (7100, 'Source 06 - Payments - CallCentre Motor Quotes', 'Source 06 - Payments - CallCentre Motor Quotes. Delete and rebuild EventSourceId 6', 7100, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 13
    (7110, 'Source 07 - Quotes Abandoned - Motor Quotes', 'Source 07 - Quotes Abandoned - Motor Quotes. Delete and rebuild EventSourceId 7', 7110, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 14
    (7120, 'Source 27 - CC Motor Quote - Abandoned', 'Source 27 - CC Motor Quote - Abandoned. Delete and rebuild EventSourceId 27', 7120, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 15
    (7130, 'Source 08 - Document Uploads - Motor Quotes', 'Source 08 - Document Uploads - Motor Quotes. Delete and rebuild EventSourceId 8', 7130, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 16
    (7140, 'Source 09 - Quote Retrieval - MFQ Motor Quotes', 'Source 09 - Quote Retrieval - MFQ Motor Quotes. Delete and rebuild EventSourceId 9', 7140, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 17
    (7150, 'Source 10 - Quote Completion Steps - MFQ Motor', 'Source 10 - Quote Completion Steps - MFQ Motor Quotes. Delete and rebuild EventSourceId 10', 7150, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 18
    (7160, 'Source 11 - Policy Transactions (NewArchive)', 'Source 11 - Policy Transactions (NewArchive) - All Policies. Delete and rebuild EventSourceId 11', 7160, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 19
    (7170, 'Source 12 - Policy Transactions (MTA History)', 'Source 12 - Policy Transactions (MTA History) - All Policies. Delete and rebuild EventSourceId 12', 7170, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 20
    (7180, 'Source 13 - Policy Renewal Start - All Policies', 'Source 13 - Policy Renewal Start - All Policies. Delete and rebuild EventSourceId 13', 7180, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 21
    (7190, 'Source 14 - Home Quotes Call Centre Events', 'Source 14 - Home Quotes Call Centre Events. Delete and rebuild EventSourceId 14', 7190, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 22
    (7200, 'Source 15 - Genesys Calls - All calls', 'Source 15 - Genesys Calls - All calls. Delete and rebuild EventSourceId 15', 7200, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 23
    (7210, 'Source 16 - Document Chase from Workflow', 'Source 16 - Document Chase from Workflow. Delete and rebuild EventSourceId 16', 7210, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 24
    (7220, 'Source 17 - Events from Applied Renewals', 'Source 17 - Events from Applied Renewals. Delete and rebuild EventSourceId 17', 7220, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 25
    (7230, 'Source 18 - Home Claims', 'Source 18 - Home Claims. Delete and rebuild EventSourceId 18', 7230, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 27
    (7240, 'Source 19 - Motor Claims', 'Source 19 - Motor Claims. Delete and rebuild EventSourceId 19', 7240, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 28
    (7250, 'Source 20 - Customer Portal Login', 'Source 20 - Customer Portal Login. Delete and rebuild EventSourceId 20', 7250, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 29
    (7260, 'Source 33 - Online Home Quote - Retrieved', 'Source 33 - Online Home Quote - Retrieved. Delete and rebuild EventSourceId 33', 7260, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 30
    (7270, 'Source 34 - Online Home Quote - Started', 'Source 34 - Online Home Quote - Started. Delete and rebuild EventSourceId 34', 7270, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 31
    (7280, 'Source 35 - Online Home Quote - Progressed', 'Source 35 - Online Home Quote - Progressed. Delete and rebuild EventSourceId 35', 7280, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 32
    (7290, 'Source 36 - Online Home Quote - Payment Status', 'Source 36 - Online Home Quote - Payment Status Success / Failure. Delete and rebuild EventSourceId 36', 7290, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 33
    (7300, 'Source 37 - Home Insurance - Document Upload', 'Source 37 - Home Insurance - Document Upload for Verification. Delete and rebuild EventSourceId 37', 7300, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 34
    (7310, 'Source 38 - Quote Completion Steps - Online Home', 'Source 38 - Quote Completion Steps - Online Home Quotes. Delete and rebuild EventSourceId 38', 7310, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 35
    (7320, 'Source 39 - Travel Quotes', 'Source 39 - Travel Quotes. Delete and rebuild EventSourceId 39', 7320, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 38
    (7330, 'Source 45 - Unknown source', 'Source 45 - Unknown source. Delete and rebuild EventSourceId 45', 7330, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 41
    (7340, 'Source 40 - Traval Transactions', 'Source 40 - Traval Transactions. Delete and rebuild EventSourceId 40', 7340, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 42
    (7350, 'Source 41 - Travel Renewals / Cancellations', 'Source 41 - Travel Renewals / Cancellations. Delete and rebuild EventSourceId 41', 7350, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 43
    (7360, 'Source 42 - Van Quote Journeys - Started', 'Source 42 - Van Quote Journeys - Started / Retrieved. Delete and rebuild EventSourceId 42', 7360, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 44
    (7370, 'Source 43 - Van Payment Journey', 'Source 43 - Van Payment Journey. Delete and rebuild EventSourceId 43', 7370, CURRENT_TIMESTAMP, NULL, 7),   -- notebook cell 45
    (7380, 'Summary - ods.EventStreamSummary', 'Summary - ods.EventStreamSummary. Build the EventStream summary table', 7380, CURRENT_TIMESTAMP, NULL, 7);   -- notebook cell 47
GO

SELECT CSPScheduleGraphNodeId, CSPScheduledItemId
FROM ops.CSPScheduleGraphNode WHERE CSPScheduleGraphNodeId BETWEEN 7010 AND 7380 ORDER BY 1;
--  expect 38 rows
GO
