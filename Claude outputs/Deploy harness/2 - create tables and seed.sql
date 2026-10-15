/*
    2 - create tables and seed.sql

    Deploying the ops harness into a new Fabric warehouse.

    Three scripts, run in order:
        1  check schemas
        2  create tables and seed them    <-- this script
        3  insert a dummy graph and run it

    Then run create_harness_trimmed.sql, which creates the 2 functions and 38
    procedures. It has to go after this script, because two of its objects are
    inline table valued functions, and an inline TVF binds the tables it reads at
    create time rather than deferring them the way a procedure does. Create
    ops.GetGraphExecutionStatus or ops.GetCurrentGraphExecutionId before
    ops.CSPExecutionGraph exists and the create fails outright.

    WHAT THIS CREATES

    23 tables, all in ops. Ten of them are also in create_harness_trimmed.sql and are
    repeated here so this one script stands alone. The other thirteen the harness
    reads and writes but never creates, which is why a brand new warehouse needs them
    spelled out.

        Graph definition          Execution state              Counters and lookups
        CSPScheduleGraph          CSPExecutionGraph            CSPNextExecutionId
        CSPScheduledItem          CSPExecutionGraphNode        CSPNextAdHocGraphId
        CSPScheduledItemString    CSPExecutionParameters       CSPNextAdHocGraphNodeId
        CSPScheduleGraphNode      CSPExecutionStrings          CSPExecutionStatus
        CSPScheduleGraphSegment   CSPExecutionMasterGraph
        CSPScheduleMasterGraph-   CSPExecutionMasterGraphNode
          NodeList

        Logging                   Metrics                      Export
        CSPLogStream              CspLogStreamMetrics          CspExportTablesList
        CSPLogStreamLive          CspLogStreamMetricMeasure
        CSPLoadLog                CspLogStreamMetricResults

    Four more ops tables need no action. ops.CSPExecGraphPrep builds them itself on
    first use, guarded by object_id, and the shapes it uses are its own:

        CSPExecutionLiveList   CSPExecutionLiveListSetup
        CSPExecutionGraphNodeSetup   CSPExecutionGraphNodesList

    Every create is guarded with IF object_id(...) IS NULL, so running this twice
    adds nothing and destroys nothing. There are no DROP statements anywhere in this
    file by design. If you want a table rebuilt, drop it yourself first.

    WHERE THE COLUMN DEFINITIONS CAME FROM, AND WHICH ONES ARE GUESSES

    Eleven tables are exact. CSPExecutionStatus, CSPNextExecutionId, CSPScheduleGraph,
    CSPScheduledItem, CSPScheduledItemString, CSPScheduleGraphNode and
    CSPScheduleGraphSegment were read from sys.columns on a working warehouse. The
    other four exact ones, plus CSPExecutionGraph, CSPExecutionGraphNode,
    CSPExecutionParameters, CSPLogStream, CSPLogStreamLive, CSPNextAdHocGraphId,
    CSPNextAdHocGraphNodeId and CSPScheduleMasterGraphNodeList, came across with the
    harness as supplied DDL.

    Eight are reconstructed from how the harness uses them, and are marked INFERRED
    where they appear below. Column names and order are taken from explicit INSERT
    column lists or from the position of values in a column-less INSERT, so they are
    firm. Types and widths are read off the procedure parameters that feed them, so
    they are reasonable rather than certain. If you have the originals, prefer them.

    Two things worth knowing about the inferred set:

      1.  ops.CspLogStreamMetrics.CspLogMetricId was an identity column in the source.
          Fabric has no identity, so it is a plain int here and
          ops.InsertCspLogStreamMetric will write NULL into it. Nothing on the graph
          execution path touches this table, so a first run is unaffected, but the
          LC and LT metric procedures need that column populated before they are
          useful.

      2.  ops.CSPExecutionMasterGraph's third column is only ever written positionally
          and is never named anywhere in the harness. CSPMasterGraphStartDateTime is
          my name for it, chosen to match its siblings.

    ONE MORE OBJECT THAT IS NOT HERE

    ops.cspGetFailedLCLTRecordsByGraphId, a table valued function returning at least
    an LCLTFlag column. ops.CspLcTestProcessor calls it in a diagnostic branch. The
    procedure creates without it and only fails if that branch runs.

    WHAT GETS SEEDED

        CSPExecutionStatus        codes 0 to 7. ops.CSPSetGraphExecutionStatus checks
                                  every code against this table and throws 51000 if it
                                  is absent, which happens at the end of every run
        CSPNextExecutionId        one row. ops.CSPStartNewGraphExecution increments the
                                  row in place, so an empty table yields nothing and
                                  the execution id comes back NULL
        CSPNextAdHocGraphId       one row, and the same for CSPNextAdHocGraphNodeId.
                                  Both are incremented in place by the ad hoc graph
                                  procedures. They start at a large negative number
                                  because ops.CSPExecuteSingleItem complains once the
                                  counter climbs above minus one million
        CSPExecutionParameters    the LOGSTREAM and TARGETSCHEMA rows

    Every seed is guarded by IF NOT EXISTS, so none of them fire twice.

    CURRENT_TIMESTAMP is used rather than GETDATE(), which a Fabric warehouse does not
    support. It takes no parentheses, and the datetime it returns converts implicitly
    into the datetime2 columns.
*/

-- ==============================================================================================
-- ==============================================================================================
--  TABLES
-- ==============================================================================================
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
--  GRAPH DEFINITION
--  What a graph is made of. Script 3 writes into the first five of these.
-- ----------------------------------------------------------------------------------------------

IF object_id('[ops].[CSPScheduleGraph]') IS NULL
    CREATE TABLE [ops].[CSPScheduleGraph] (
        [CSPScheduleGraphId] INT NULL,
        [CSPScheduleGraphTypeId] INT NULL,
        [CSPScheduleGraphName] VARCHAR (50) NULL,
        [CSPScheduleGraphDescription] VARCHAR (255) NULL,
        [RecordInsertDateTime] DATETIME2 (6) NULL,
        [RecordUpdateDateTime] DATETIME2 (6) NULL,
        [CSPClientId] INT NULL );
GO

IF object_id('[ops].[CSPScheduledItem]') IS NULL
    CREATE TABLE [ops].[CSPScheduledItem] (
        [CSPScheduledItemId] INT NULL,
        [CSPScheduledItemTypeId] INT NULL,
        [CSPScheduledItemName] VARCHAR (100) NULL,
        [CSPScheduledItemDescription] VARCHAR (255) NULL,
        [RecordInsertDateTime] DATETIME2 (6) NULL,
        [RecordUpdateDateTime] DATETIME2 (6) NULL,
        [CSPClientId] INT NULL,
        [ScheduledItemReference] BIGINT NULL,
        [CspScriptClassCode] INT NULL );
GO

IF object_id('[ops].[CSPScheduledItemString]') IS NULL
    CREATE TABLE [ops].[CSPScheduledItemString] (
        [CSPScheduledItemId] INT NULL,
        [CSPScheduledItemString] VARCHAR (MAX) NULL,
        [CSPMajorVersion] INT NULL,
        [CSPMinorVersion] INT NULL,
        [CSPScheduledItemCurrentFlag] BIT NULL,
        [RecordInsertDateTime] DATETIME2 (6) NULL,
        [RecordUpdateDateTime] DATETIME2 (6) NULL,
        [CSPClientId] INT NULL );
GO

IF object_id('[ops].[CSPScheduleGraphNode]') IS NULL
    CREATE TABLE [ops].[CSPScheduleGraphNode] (
        [CSPScheduleGraphNodeId] INT NULL,
        [CSPScheduleGraphNodeName] VARCHAR (50) NULL,
        [CSPScheduleGraphNodeDescription] VARCHAR (255) NULL,
        [CSPScheduledItemId] INT NULL,
        [RecordInsertDateTime] DATETIME2 (6) NULL,
        [RecordUpdateDateTime] DATETIME2 (6) NULL,
        [CSPClientId] INT NULL );
GO

IF object_id('[ops].[CSPScheduleGraphSegment]') IS NULL
    CREATE TABLE [ops].[CSPScheduleGraphSegment] (
        [CSPScheduleGraphId] INT NULL,
        [CSPScheduleGraphSegmentId] INT NULL,
        [CSPScheduleGraphSegmentTypeId] INT NULL,
        [CSPScheduleGraphNodeFrom] INT NULL,
        [CSPScheduleGraphNodeTo] INT NULL,
        [CSPScheduleGraphSegmentName] VARCHAR (255) NULL,
        [CSPScheduleGraphSegmentDescription] VARCHAR (255) NULL,
        [RecordInsertDateTime] DATETIME2 (6) NULL,
        [RecordUpdateDateTime] DATETIME2 (6) NULL,
        [CSPClientId] INT NULL );
GO

IF object_id('[ops].[CSPScheduleMasterGraphNodeList]') IS NULL
    CREATE TABLE [ops].[CSPScheduleMasterGraphNodeList] (
        [CSPMasterGraphId] INT NULL,
        [CSPMasterGraphNodeId] INT NULL,
        [CSPMasterGraphNodeTypeId] INT NULL,
        [CSPScheduleGraphId] INT NULL,
        [CSPMasterGraphNodeOrder] INT NULL,
        [RecordInsertDateTime] DATETIME2 (6) NULL,
        [RecordUpdateDateTime] DATETIME2 (6) NULL,
        [CSPClientId] INT NULL );
GO

-- ----------------------------------------------------------------------------------------------
--  EXECUTION STATE
--  What happened on each run. Written by the harness, not by you.
--
--  CSPExecutionGraph is the one table here whose column ORDER is load bearing.
--  ops.CSPStartNewGraphExecution inserts into it without naming columns, six values
--  positionally, so a reordered table silently writes the wrong values.
-- ----------------------------------------------------------------------------------------------

IF object_id('[ops].[CSPExecutionGraph]') IS NULL
    CREATE TABLE [ops].[CSPExecutionGraph] (
        [CSPExecutionId] INT NULL,
        [CSPContextId] INT NULL,
        [CSPGraphId] INT NULL,
        [CSPGraphStartDateTime] DATETIME2 (0) NULL,
        [CSPGraphEndDateTime] DATETIME2 (0) NULL,
        [CSPExecutionStatusFlag] INT NULL );
GO

IF object_id('[ops].[CSPExecutionGraphNode]') IS NULL
    CREATE TABLE [ops].[CSPExecutionGraphNode] (
        [CSPExecutionId] INT NULL,
        [CSPContextId] INT NULL,
        [CSPGraphId] INT NULL,
        [CSPGraphNodeId] INT NULL,
        [CSPGraphNodeStartDateTime] DATETIME2 (6) NULL,
        [CSPGraphNodeEndDateTime] DATETIME2 (6) NULL,
        [CSPExecutionStatusFlag] INT NULL,
        [CSPRecordsProcessed] INT NULL,
        [CSPClientId] INT NULL );
GO

IF object_id('[ops].[CSPExecutionParameters]') IS NULL
    CREATE TABLE [ops].[CSPExecutionParameters] (
        [CSPParameterLevelCode] INT NULL,
        [CSPContextId] INT NULL,
        [CSPExecutionId] INT NULL,
        [CSPGraphId] INT NULL,
        [CSPGraphNodeId] INT NULL,
        [CSPParmName] VARCHAR (255) NULL,
        [CSPParmValue] VARCHAR (255) NULL,
        [CSPClientId] INT NULL );
GO

--  INFERRED. Column names and order are exact, taken from the explicit insert list in
--  ops.CSPStoreExecutionString. Types follow that procedure's parameters, with
--  @sqlstr declared VARCHAR (MAX).
IF object_id('[ops].[CSPExecutionStrings]') IS NULL
    CREATE TABLE [ops].[CSPExecutionStrings] (
        [CSPExecutionDateTime] DATETIME2 (6) NULL,
        [CSPExecutionString] VARCHAR (MAX) NULL,
        [CSPContextId] INT NULL,
        [CSPExecutionId] INT NULL,
        [CSPGraphId] INT NULL,
        [CSPGraphNodeId] INT NULL );
GO

--  INFERRED. ops.CSPManageMasterGraph inserts six values positionally, so order here
--  is load bearing. Five of the six names appear elsewhere in the harness. The third
--  never does, and CSPMasterGraphStartDateTime is my name for it.
IF object_id('[ops].[CSPExecutionMasterGraph]') IS NULL
    CREATE TABLE [ops].[CSPExecutionMasterGraph] (
        [CSPMasterGraphId] INT NULL,
        [CSPMasterGraphExecutionId] INT NULL,
        [CSPMasterGraphStartDateTime] DATETIME2 (6) NULL,
        [CSPMasterGraphEndDateTime] DATETIME2 (6) NULL,
        [CSPMasterGraphLastUpdateDateTime] DATETIME2 (6) NULL,
        [CSPMasterExecutionStatusCode] INT NULL );
GO

--  INFERRED. Four values inserted positionally by ops.CSPManageMasterGraph, all four
--  names used by name elsewhere. ops.CSPExecGraphNodeTypeSQL reads this table on every
--  node, so it has to exist even for a graph that belongs to no master graph.
IF object_id('[ops].[CSPExecutionMasterGraphNode]') IS NULL
    CREATE TABLE [ops].[CSPExecutionMasterGraphNode] (
        [CSPMasterGraphId] INT NULL,
        [CSPMasterGraphExecutionId] INT NULL,
        [CSPMasterGraphNodeId] INT NULL,
        [CSPMasterGraphNodeExecutionId] INT NULL );
GO

-- ----------------------------------------------------------------------------------------------
--  COUNTERS AND LOOKUPS
--  The three counter tables hold exactly one row each and are incremented in place.
-- ----------------------------------------------------------------------------------------------

--  Note the lower case c on cspExecutionId. That is how the column is spelled on a
--  working warehouse and how ops.CSPStartNewGraphExecution refers to it. On a case
--  sensitive Fabric warehouse the capitalised spelling will not resolve.
IF object_id('[ops].[CSPNextExecutionId]') IS NULL
    CREATE TABLE [ops].[CSPNextExecutionId] (
        [cspExecutionId] INT NULL );
GO

IF object_id('[ops].[CSPNextAdHocGraphId]') IS NULL
    CREATE TABLE [ops].[CSPNextAdHocGraphId] (
        [CSPGraphId] BIGINT NULL );
GO

IF object_id('[ops].[CSPNextAdHocGraphNodeId]') IS NULL
    CREATE TABLE [ops].[CSPNextAdHocGraphNodeId] (
        [CSPScheduleGraphNodeId] BIGINT NULL );
GO

IF object_id('[ops].[CSPExecutionStatus]') IS NULL
    CREATE TABLE [ops].[CSPExecutionStatus] (
        [CSPExecutionStatusCode] INT NULL,
        [CSPExecutionStatusDescription] VARCHAR (100) NULL );
GO

-- ----------------------------------------------------------------------------------------------
--  LOGGING
--  CSPLogStream is the permanent log. CSPLogStreamLive holds the current run only and
--  is emptied by ops.CSPExecGraphPrep and ops.CSPExecGraphFinalise. Identical shapes.
-- ----------------------------------------------------------------------------------------------

IF object_id('[ops].[CSPLogStream]') IS NULL
    CREATE TABLE [ops].[CSPLogStream] (
        [CSPLogDateTime] DATETIME2 (6) NULL,
        [CSPExecutionId] INT NULL,
        [CSPContextId] INT NULL,
        [CSPGraphId] INT NULL,
        [CSPGraphNodeId] INT NULL,
        [CSPLogTypeCode] INT NULL,
        [CSPLogStringShort] VARCHAR (50) NULL,
        [CSPLogStringLong] VARCHAR (255) NULL,
        [CSPRecordCount] BIGINT NULL,
        [CSPClientId] INT NULL );
GO

IF object_id('[ops].[CSPLogStreamLive]') IS NULL
    CREATE TABLE [ops].[CSPLogStreamLive] (
        [CSPLogDateTime] DATETIME2 (6) NULL,
        [CSPExecutionId] INT NULL,
        [CSPContextId] INT NULL,
        [CSPGraphId] INT NULL,
        [CSPGraphNodeId] INT NULL,
        [CSPLogTypeCode] INT NULL,
        [CSPLogStringShort] VARCHAR (50) NULL,
        [CSPLogStringLong] VARCHAR (255) NULL,
        [CSPRecordCount] BIGINT NULL,
        [CSPClientId] INT NULL );
GO

--  INFERRED. Names and order from the explicit insert list and the UPDATE SET list in
--  ops.CSPLoadMetaData. Types from that procedure's parameters: @loadfilename
--  varchar(255), the two record counts bigint, @LoadErrorCode int, @LoadErrorMessage
--  varchar(max), @LoadStatusFlag tinyint.
IF object_id('[ops].[CSPLoadLog]') IS NULL
    CREATE TABLE [ops].[CSPLoadLog] (
        [LogDateTime] DATETIME2 (6) NULL,
        [LoadFileName] VARCHAR (255) NULL,
        [LoadStartDateTime] DATETIME2 (6) NULL,
        [LoadEndDateTime] DATETIME2 (6) NULL,
        [LoadReadRecordCount] BIGINT NULL,
        [LoadInsertRecordCount] BIGINT NULL,
        [LoadErrorCode] INT NULL,
        [LoadErrorMessage] VARCHAR (MAX) NULL,
        [LoadStatusFlag] TINYINT NULL,
        [CSPExecutionId] INT NULL );
GO

-- ----------------------------------------------------------------------------------------------
--  METRICS
--  The LC and LT comparison machinery. Note the casing: these three are spelled Csp,
--  not CSP, everywhere the harness refers to them, and on a case sensitive warehouse
--  that distinction is real.
-- ----------------------------------------------------------------------------------------------

--  INFERRED. Names from the insert list in ops.InsertCspLogStreamMetric and the SET
--  list in ops.UpdateCspLogStreamMetric. The two log strings are varchar(255) because
--  that is how both procedures declare their parameters.
--
--  CspLogMetricId is read back as a key but never written, so it was an identity
--  column in the source. Fabric has no identity, so it is a plain int here and
--  ops.InsertCspLogStreamMetric will leave it NULL. Populate it yourself, or add a
--  wrapper that assigns max + 1 the way ops.InsertCspLogStreamMetricMeasure does for
--  its own key, before relying on the LC or LT procedures.
IF object_id('[ops].[CspLogStreamMetrics]') IS NULL
    CREATE TABLE [ops].[CspLogStreamMetrics] (
        [CspLogMetricId] INT NULL,
        [CSPGraphId] INT NULL,
        [CSPGraphNodeId] INT NULL,
        [CSPLogStringShort] VARCHAR (255) NULL,
        [CSPLogStringLong] VARCHAR (255) NULL,
        [InsertDateTime] DATETIME2 (6) NULL,
        [UpdateDateTime] DATETIME2 (6) NULL,
        [CSPClientId] INT NULL );
GO

--  INFERRED. Names and order from the explicit insert list in
--  ops.InsertCspLogStreamMetricMeasure. CspMetricMeasureID is bigint because the local
--  variable that computes it is. FailureThreshold is decimal(7,2) from the parameter.
IF object_id('[ops].[CspLogStreamMetricMeasure]') IS NULL
    CREATE TABLE [ops].[CspLogStreamMetricMeasure] (
        [CspMetricMeasureID] BIGINT NULL,
        [CspLogMetricIdLeft] INT NULL,
        [CspLogMetricIdRight] INT NULL,
        [FailureThreshold] DECIMAL (7, 2) NULL,
        [MeasureRunsToCompare] INT NULL,
        [MinRecordCount] INT NULL,
        [InsertDateTime] DATETIME2 (6) NULL,
        [DeleteDateTime] DATETIME2 (6) NULL );
GO

--  INFERRED. Names and order from the explicit insert lists in ops.CspLcTestProcessor
--  and ops.CspLtTestProcessor, which agree with one another. The record counts are
--  bigint to match ops.CSPLogStream.CSPRecordCount, which is where they come from.
--  LCLTFlag only ever holds 'LC' or 'LT'.
IF object_id('[ops].[CspLogStreamMetricResults]') IS NULL
    CREATE TABLE [ops].[CspLogStreamMetricResults] (
        [CspMetricLogDateTime] DATETIME2 (6) NULL,
        [CspLogMetricIdLeft] INT NULL,
        [CspLogMetricIdRight] INT NULL,
        [LeftCSPGraphId] INT NULL,
        [LeftCSPGraphNodeId] INT NULL,
        [LeftCSPExecutionId] INT NULL,
        [LeftCSPRecordCount] BIGINT NULL,
        [RightCSPGraphId] INT NULL,
        [RightCSPGraphNodeId] INT NULL,
        [RightCSPExecutionId] INT NULL,
        [RightCSPRecordCount] BIGINT NULL,
        [FailureThreshold] DECIMAL (7, 2) NULL,
        [SuccessFlag] INT NULL,
        [LiveRecordFlag] INT NULL,
        [LCLTFlag] VARCHAR (2) NULL );
GO

-- ----------------------------------------------------------------------------------------------
--  EXPORT
-- ----------------------------------------------------------------------------------------------

--  INFERRED. Names and order from the one explicit insert list in
--  ops.CspSetExportTable. Types from that procedure's parameters, except
--  ExportFileName, which is built into an nvarchar(1024) local before being inserted.
IF object_id('[ops].[CspExportTablesList]') IS NULL
    CREATE TABLE [ops].[CspExportTablesList] (
        [LogDateTime] DATETIME2 (6) NULL,
        [ExportSchemaName] VARCHAR (10) NULL,
        [ExportTableName] VARCHAR (255) NULL,
        [ExportContainerName] VARCHAR (255) NULL,
        [ExportFolderName] VARCHAR (255) NULL,
        [ExportFileName] VARCHAR (1024) NULL,
        [ExportStatusCode] INT NULL,
        [ExportCompressionFlag] INT NULL,
        [ExportDelimiter] VARCHAR (1) NULL );
GO

-- ==============================================================================================
-- ==============================================================================================
--  SEED DATA
-- ==============================================================================================
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
--  ops.CSPExecutionStatus
--
--  ops.CSPSetGraphExecutionStatus looks every status code up here and throws 51000 if
--  it is not found. That happens at the end of every run, so a missing row is not a
--  subtle failure. The codes are the ones the harness actually sets. The wording is
--  mine, so change it if your own status list reads differently.
-- ----------------------------------------------------------------------------------------------

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

-- ----------------------------------------------------------------------------------------------
--  ops.CSPNextExecutionId
--
--  One row, incremented in place by ops.CSPStartNewGraphExecution. On an empty table
--  the UPDATE matches nothing, the SELECT that follows returns nothing, and the run
--  proceeds with a NULL execution id, which is awkward to diagnose from the logs.
-- ----------------------------------------------------------------------------------------------

IF NOT EXISTS (SELECT 1 FROM ops.CSPNextExecutionId)
    INSERT INTO ops.CSPNextExecutionId
        (
            cspExecutionId
        )
    VALUES (0);
GO

-- ----------------------------------------------------------------------------------------------
--  ops.CSPNextAdHocGraphId and ops.CSPNextAdHocGraphNodeId
--
--  Same pattern, one row each, incremented in place by ops.CSPGetNextTempGraphid and
--  ops.CSPGetNextTempGraphNodeid. Ad hoc graphs take negative ids so they cannot
--  collide with scheduled ones, and ops.CSPExecuteSingleItem logs a cleanup warning
--  once the counter has climbed past minus one million. Starting at minus two billion
--  leaves plenty of room.
--
--  Neither is touched by ops.CSPExecuteGenericGraph. They matter only if you use
--  ops.CSPExecuteSingleItem or ops.CSPInsertScheduledItemString.
-- ----------------------------------------------------------------------------------------------

IF NOT EXISTS (SELECT 1 FROM ops.CSPNextAdHocGraphId)
    INSERT INTO ops.CSPNextAdHocGraphId
        (
            CSPGraphId
        )
    VALUES (-2000000000);
GO

IF NOT EXISTS (SELECT 1 FROM ops.CSPNextAdHocGraphNodeId)
    INSERT INTO ops.CSPNextAdHocGraphNodeId
        (
            CSPScheduleGraphNodeId
        )
    VALUES (-2000000000);
GO

-- ----------------------------------------------------------------------------------------------
--  ops.CSPExecutionParameters
--
--  Two rows, both as supplied with the harness.
--
--  LOGSTREAM is a ready made call to the stream logger that a node's SQL can paste in
--  by writing ##LOGSTREAM##. The four ## tokens inside it are substituted in turn.
--
--  TARGETSCHEMA resolves to src and is scoped to graph -1 and context 1. A NULL in any
--  scope column is a wildcard, and ops.CSPSubstituteParams insists on exactly one
--  matching row, so widening the scope of either row risks breaking both.
--
--  One thing to watch. The parameter names inside the LOGSTREAM value read
--  @CSPContextId, @CSPexecutionId, @CSPgraphid and @CSPgraphnodeid, while
--  ops.CSPStreamLogger declares its parameters in lower case. That is harmless on a
--  case insensitive server and will not bind on a case sensitive Fabric warehouse.
--  The value is left exactly as supplied here rather than quietly corrected. If a node
--  that uses ##LOGSTREAM## fails to bind, this is why, and the fix is to lower case
--  those four names.
-- ----------------------------------------------------------------------------------------------

IF NOT EXISTS (SELECT 1 FROM ops.CSPExecutionParameters WHERE CSPParmName = 'LOGSTREAM')
    INSERT INTO ops.CSPExecutionParameters
        (
            CSPParmName,
            CSPParmValue
        )
    VALUES ('LOGSTREAM', 'exec [ops].[CSPStreamLogger] @CSPContextId = ##CONTEXTID##, @CSPexecutionId = ##RUNID##, @CSPgraphid = ##GRAPHID##, @CSPgraphnodeid = ##GRAPHNODEID##, ');
GO

IF NOT EXISTS (SELECT 1 FROM ops.CSPExecutionParameters WHERE CSPParmName = 'TARGETSCHEMA')
    INSERT INTO ops.CSPExecutionParameters
        (
            CSPParameterLevelCode,
            CSPContextId,
            CSPExecutionId,
            CSPGraphId,
            CSPGraphNodeId,
            CSPParmName,
            CSPParmValue,
            CSPClientId
        )
    VALUES (NULL, 1, NULL, -1, NULL, 'TARGETSCHEMA', 'src', 1);
GO

-- ==============================================================================================
-- ==============================================================================================
--  VERIFY
-- ==============================================================================================
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
--  ALL 23 TABLES PRESENT
-- ----------------------------------------------------------------------------------------------

SELECT r.TableName,
       CASE WHEN o.object_id IS NULL THEN 'MISSING' ELSE 'present' END AS Status
FROM (SELECT 'CSPExecutionGraph' AS TableName
      UNION ALL SELECT 'CSPExecutionGraphNode'
      UNION ALL SELECT 'CSPExecutionMasterGraph'
      UNION ALL SELECT 'CSPExecutionMasterGraphNode'
      UNION ALL SELECT 'CSPExecutionParameters'
      UNION ALL SELECT 'CSPExecutionStatus'
      UNION ALL SELECT 'CSPExecutionStrings'
      UNION ALL SELECT 'CSPLoadLog'
      UNION ALL SELECT 'CSPLogStream'
      UNION ALL SELECT 'CSPLogStreamLive'
      UNION ALL SELECT 'CSPNextAdHocGraphId'
      UNION ALL SELECT 'CSPNextAdHocGraphNodeId'
      UNION ALL SELECT 'CSPNextExecutionId'
      UNION ALL SELECT 'CSPScheduleGraph'
      UNION ALL SELECT 'CSPScheduleGraphNode'
      UNION ALL SELECT 'CSPScheduleGraphSegment'
      UNION ALL SELECT 'CSPScheduleMasterGraphNodeList'
      UNION ALL SELECT 'CSPScheduledItem'
      UNION ALL SELECT 'CSPScheduledItemString'
      UNION ALL SELECT 'CspExportTablesList'
      UNION ALL SELECT 'CspLogStreamMetricMeasure'
      UNION ALL SELECT 'CspLogStreamMetricResults'
      UNION ALL SELECT 'CspLogStreamMetrics') AS r
     LEFT OUTER JOIN
     sys.schemas AS s
     ON s.name = 'ops'
     LEFT OUTER JOIN
     sys.objects AS o
     ON o.schema_id = s.schema_id AND o.name = r.TableName AND o.type = 'U'
ORDER BY r.TableName;

--  expect 23 rows, every one reading 'present'
GO

-- ----------------------------------------------------------------------------------------------
--  SEED ROWS LANDED
-- ----------------------------------------------------------------------------------------------

SELECT 'ops.CSPExecutionStatus' AS TableName, count(*) AS [Rows], '8' AS Expected FROM ops.CSPExecutionStatus
UNION ALL SELECT 'ops.CSPNextExecutionId',      count(*), '1' FROM ops.CSPNextExecutionId
UNION ALL SELECT 'ops.CSPNextAdHocGraphId',     count(*), '1' FROM ops.CSPNextAdHocGraphId
UNION ALL SELECT 'ops.CSPNextAdHocGraphNodeId', count(*), '1' FROM ops.CSPNextAdHocGraphNodeId
UNION ALL SELECT 'ops.CSPExecutionParameters',  count(*), '2 or more' FROM ops.CSPExecutionParameters;
GO

-- ----------------------------------------------------------------------------------------------
--  CSPExecutionGraph COLUMN ORDER
--
--  The only shape in this file that will corrupt data rather than error if it is wrong,
--  because ops.CSPStartNewGraphExecution inserts into it positionally.
-- ----------------------------------------------------------------------------------------------

SELECT c.column_id AS Position,
       c.name AS ColumnName
FROM sys.columns AS c
     INNER JOIN sys.objects AS o ON o.object_id = c.object_id
     INNER JOIN sys.schemas AS s ON s.schema_id = o.schema_id
WHERE s.name = 'ops'
      AND o.name = 'CSPExecutionGraph'
ORDER BY c.column_id;

--  expect, in this order: CSPExecutionId, CSPContextId, CSPGraphId,
--  CSPGraphStartDateTime, CSPGraphEndDateTime, CSPExecutionStatusFlag
GO

-- ----------------------------------------------------------------------------------------------
--  NEXT
-- ----------------------------------------------------------------------------------------------

--  1.  Run create_harness_trimmed.sql. It creates 2 functions and 38 procedures.
--  2.  Run script 3 to insert and execute the dummy graph.
