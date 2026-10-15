/*
    07 - CSPScheduleGraphSegment.sql

    Graph 7001, a 38 node linear chain mirroring Fabric notebook
    10 - Build EventStream.

    The edges. 37 segments wiring the 38 nodes into one chain, 7010 through to 7380.
    This table is what ops.CSPExecGraphPrep reads to discover the nodes, so a node that
    appears in no segment never runs.
    
    It has to be a chain rather than a fan-out. Every build cell does
        cross join (select max(EventId) from ods.EventStream)
    to continue the key sequence, so two nodes running at once would collide.
    
    Segment ids are numbered 1 upwards here. ops.CspInsertScheduledGraphSegment would give
    every segment id 1, since it reads max() without incrementing, but nothing on the
    execution path reads the column either way.

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
        07  ops.CSPScheduleGraphSegment <-- this script
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
--      CSPScheduleGraphSegmentId
--      CSPScheduleGraphSegmentTypeId
--      CSPScheduleGraphNodeFrom
--      CSPScheduleGraphNodeTo
--      CSPScheduleGraphSegmentName
--      CSPScheduleGraphSegmentDescription
--      RecordInsertDateTime
--      RecordUpdateDateTime
--      CSPClientId
--
-- ==============================================================================================

-- ==============================================================================================
--  CLEAR
-- ==============================================================================================

DELETE ops.CSPScheduleGraphSegment WHERE CSPScheduleGraphId = 7001;
GO

-- ==============================================================================================
--  INSERT
-- ==============================================================================================

INSERT INTO ops.CSPScheduleGraphSegment
    (
        CSPScheduleGraphId,
        CSPScheduleGraphSegmentId,
        CSPScheduleGraphSegmentTypeId,
        CSPScheduleGraphNodeFrom,
        CSPScheduleGraphNodeTo,
        CSPScheduleGraphSegmentName,
        CSPScheduleGraphSegmentDescription,
        RecordInsertDateTime,
        RecordUpdateDateTime,
        CSPClientId
    )
VALUES
    (7001, 1, 1, 7010, 7020, '7010 to 7020', 'Setup - lkp.EventSource  ->  Setup - ods.EventStream', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 2, 1, 7020, 7030, '7020 to 7030', 'Setup - ods.EventStream  ->  Setup - ods.EpisodeEventStream', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 3, 1, 7030, 7040, '7030 to 7040', 'Setup - ods.EpisodeEventStream  ->  Source 01 - Genesys Calls - MFQ Data', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 4, 1, 7040, 7050, '7040 to 7050', 'Source 01 - Genesys Calls - MFQ Data  ->  Source 02 - Google Analytics - MFQ Records', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 5, 1, 7050, 7060, '7050 to 7060', 'Source 02 - Google Analytics - MFQ Records  ->  Source 03 - Documents Issued - From Relay', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 6, 1, 7060, 7070, '7060 to 7070', 'Source 03 - Documents Issued - From Relay  ->  Source 04 - Quote Started - Motor Quotes', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 7, 1, 7070, 7080, '7070 to 7080', 'Source 04 - Quote Started - Motor Quotes  ->  Source 24 - CC Motor Quotes - Started', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 8, 1, 7080, 7090, '7080 to 7090', 'Source 24 - CC Motor Quotes - Started  ->  Source 05 - Payments - MFQ Motor Quotes', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 9, 1, 7090, 7100, '7090 to 7100', 'Source 05 - Payments - MFQ Motor Quotes  ->  Source 06 - Payments - CallCentre Motor Quotes', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 10, 1, 7100, 7110, '7100 to 7110', 'Source 06 - Payments - CallCentre Motor Quotes  ->  Source 07 - Quotes Abandoned - Motor Quotes', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 11, 1, 7110, 7120, '7110 to 7120', 'Source 07 - Quotes Abandoned - Motor Quotes  ->  Source 27 - CC Motor Quote - Abandoned', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 12, 1, 7120, 7130, '7120 to 7130', 'Source 27 - CC Motor Quote - Abandoned  ->  Source 08 - Document Uploads - Motor Quotes', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 13, 1, 7130, 7140, '7130 to 7140', 'Source 08 - Document Uploads - Motor Quotes  ->  Source 09 - Quote Retrieval - MFQ Motor Quotes', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 14, 1, 7140, 7150, '7140 to 7150', 'Source 09 - Quote Retrieval - MFQ Motor Quotes  ->  Source 10 - Quote Completion Steps - MFQ Motor Quotes', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 15, 1, 7150, 7160, '7150 to 7160', 'Source 10 - Quote Completion Steps - MFQ Motor Quotes  ->  Source 11 - Policy Transactions (NewArchive) - All Policies', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 16, 1, 7160, 7170, '7160 to 7170', 'Source 11 - Policy Transactions (NewArchive) - All Policies  ->  Source 12 - Policy Transactions (MTA History) - All Policies', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 17, 1, 7170, 7180, '7170 to 7180', 'Source 12 - Policy Transactions (MTA History) - All Policies  ->  Source 13 - Policy Renewal Start - All Policies', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 18, 1, 7180, 7190, '7180 to 7190', 'Source 13 - Policy Renewal Start - All Policies  ->  Source 14 - Home Quotes Call Centre Events', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 19, 1, 7190, 7200, '7190 to 7200', 'Source 14 - Home Quotes Call Centre Events  ->  Source 15 - Genesys Calls - All calls', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 20, 1, 7200, 7210, '7200 to 7210', 'Source 15 - Genesys Calls - All calls  ->  Source 16 - Document Chase from Workflow', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 21, 1, 7210, 7220, '7210 to 7220', 'Source 16 - Document Chase from Workflow  ->  Source 17 - Events from Applied Renewals', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 22, 1, 7220, 7230, '7220 to 7230', 'Source 17 - Events from Applied Renewals  ->  Source 18 - Home Claims', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 23, 1, 7230, 7240, '7230 to 7240', 'Source 18 - Home Claims  ->  Source 19 - Motor Claims', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 24, 1, 7240, 7250, '7240 to 7250', 'Source 19 - Motor Claims  ->  Source 20 - Customer Portal Login', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 25, 1, 7250, 7260, '7250 to 7260', 'Source 20 - Customer Portal Login  ->  Source 33 - Online Home Quote - Retrieved', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 26, 1, 7260, 7270, '7260 to 7270', 'Source 33 - Online Home Quote - Retrieved  ->  Source 34 - Online Home Quote - Started', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 27, 1, 7270, 7280, '7270 to 7280', 'Source 34 - Online Home Quote - Started  ->  Source 35 - Online Home Quote - Progressed', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 28, 1, 7280, 7290, '7280 to 7290', 'Source 35 - Online Home Quote - Progressed  ->  Source 36 - Online Home Quote - Payment Status Success / Failure', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 29, 1, 7290, 7300, '7290 to 7300', 'Source 36 - Online Home Quote - Payment Status Success / Failure  ->  Source 37 - Home Insurance - Document Upload for Verification', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 30, 1, 7300, 7310, '7300 to 7310', 'Source 37 - Home Insurance - Document Upload for Verification  ->  Source 38 - Quote Completion Steps - Online Home Quotes', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 31, 1, 7310, 7320, '7310 to 7320', 'Source 38 - Quote Completion Steps - Online Home Quotes  ->  Source 39 - Travel Quotes', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 32, 1, 7320, 7330, '7320 to 7330', 'Source 39 - Travel Quotes  ->  Source 45 - Unknown source', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 33, 1, 7330, 7340, '7330 to 7340', 'Source 45 - Unknown source  ->  Source 40 - Traval Transactions', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 34, 1, 7340, 7350, '7340 to 7350', 'Source 40 - Traval Transactions  ->  Source 41 - Travel Renewals / Cancellations', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 35, 1, 7350, 7360, '7350 to 7360', 'Source 41 - Travel Renewals / Cancellations  ->  Source 42 - Van Quote Journeys - Started / Retrieved', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 36, 1, 7360, 7370, '7360 to 7370', 'Source 42 - Van Quote Journeys - Started / Retrieved  ->  Source 43 - Van Payment Journey', CURRENT_TIMESTAMP, NULL, 7),
    (7001, 37, 1, 7370, 7380, '7370 to 7380', 'Source 43 - Van Payment Journey  ->  Summary - ods.EventStreamSummary', CURRENT_TIMESTAMP, NULL, 7);
GO

SELECT CSPScheduleGraphNodeFrom, CSPScheduleGraphNodeTo
FROM ops.CSPScheduleGraphSegment WHERE CSPScheduleGraphId = 7001 ORDER BY CSPScheduleGraphNodeFrom;
--  expect 37 rows, 7010 -> ... -> 7380
GO
