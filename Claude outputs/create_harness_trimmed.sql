/*
    create_harness_trimmed.sql

    The ops harness with the five procedures removed that depend on objects we cannot
    source, or that only operate on table partitions. Nothing here reaches outside the
    ops schema at create time.

    Removed, and why:
        ops.analysisperiodcalc                   needs ads.SnapShotLookup, ads.AnalysisPeriodLookup, ads.AnalysisPeriodType
        ops.CSPConsolidateTables                 needs the ops.getTableNames function
        ops.CSPFrameWorkBackup                   needs the ops.CSPFrameWorkBackupList table
        ops.CSPMovePartitionsFromSourceToTarget  needs the ops.getPartitionsData function, and table partitioning
        ops.CSPSwapPartitions                    table partitioning, and its only caller was the line above

    Nothing else calls any of the five, so removing them breaks no caller.

    One caveat on what is left. ops.CspLcTestProcessor is kept, but one diagnostic block
    near the end of it still calls ops.cspGetFailedLCLTRecordsByGraphId, which does not
    exist here. The procedure will create without complaint, because T-SQL defers name
    resolution, and will only fail if that branch runs. Comment the block out or supply
    the function.

    ------------------------------------------------------------------------------------
    WHAT THIS SCRIPT DOES NOT CREATE

    It creates 5 tables, 2 functions and 38 procedures. These objects are read or written
    by the procedures but are not created anywhere in this file, so they have to exist
    before the harness will run:

        ops.CSPExecutionGraph                ops.CSPLogStreamMetricMeasure
        ops.CSPExecutionGraphNode            ops.CSPLogStreamMetricResults
        ops.CSPExecutionMasterGraphNode      ops.CSPLogStreamMetrics
        ops.CSPExecutionParameters           ops.CSPScheduledItem
        ops.CSPExecutionStrings              ops.CSPScheduledItemString
        ops.CSPLoadLog                       ops.CSPScheduleGraph
        ops.CSPLogStream                     ops.CSPScheduleGraphNode
        ops.CSPLogStreamLive                 ops.CSPScheduleGraphSegment

        ops.cspGetFailedLCLTRecordsByGraphId  (function, see the caveat above)

    Six more ops tables are referenced but need no action, because the procedures build
    them themselves on the fly:

        ops.ContentFileToBeProcessedList     built by ops.AddContentFileToProcessList
        ops.CspContentFileList               built by ops.CSPAcceptContentFile
        ops.CSPExecutionGraphNodeSetup       built by ops.CSPExecGraphPrep
        ops.CSPExecutionGraphNodesList       built by ops.CSPExecGraphPrep
        ops.CSPExecutionLiveList             built by ops.CSPExecGraphPrep
        ops.CSPExecutionLiveListSetup        built by ops.CSPExecGraphPrep

    Two schemas other than ops have to exist, because procedures write working tables
    into them at run time:

        stg   ops.CSPTableCopy writes stg.CSPx; ops.CSPValidateSourceRecords writes
              stg.cspvsr_x and stg.cspvsr_y
        trk   ops.CSPValidateSourceRecords writes a trk.DQF_<tablename> table per table
              it validates, through dynamic SQL

    System objects used, which need nothing doing: sys.tables, sys.columns, sys.types,
    INFORMATION_SCHEMA.COLUMNS and sp_executesql.

    One thing worth fixing. ops.CSPGraphExec has a SELECT that reads FROM CSPExecutionGraph
    with no schema prefix, where every other reference in the harness says ops.CSPExecutionGraph.
    It will resolve against the caller default schema, so it works for a user whose default
    schema is ops and fails for anyone else.
    ------------------------------------------------------------------------------------

    Run order is tables, then functions, then procedures. Batches are separated with GO
    because CREATE PROCEDURE and CREATE FUNCTION have to start a batch.

    Formatting note: the source was copied out of an SSMS grid, which turned every line
    break into spaces. The line breaks here were reconstructed, so indentation is close to
    the original but not identical to it. The SQL itself is unchanged.
*/


-- ==============================================================================================
--  TABLES
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPExecutionStatus]
-- ----------------------------------------------------------------------------------------------
DROP TABLE IF EXISTS [ops].[CSPExecutionStatus];
GO

CREATE TABLE [ops].[CSPExecutionStatus] (
    [CSPExecutionStatusCode] INT NULL,
    [CSPExecutionStatusDescription] VARCHAR(100) NULL )
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPNextAdHocGraphId]
-- ----------------------------------------------------------------------------------------------
DROP TABLE IF EXISTS [ops].[CSPNextAdHocGraphId];
GO

CREATE TABLE [ops].[CSPNextAdHocGraphId] (
    [CSPGraphId] BIGINT NULL )
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPNextAdHocGraphNodeId]
-- ----------------------------------------------------------------------------------------------
DROP TABLE IF EXISTS [ops].[CSPNextAdHocGraphNodeId];
GO

CREATE TABLE [ops].[CSPNextAdHocGraphNodeId] (
    [CSPScheduleGraphNodeId] BIGINT NULL )
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPNextExecutionId]
-- ----------------------------------------------------------------------------------------------
DROP TABLE IF EXISTS [ops].[CSPNextExecutionId];
GO

CREATE TABLE [ops].[CSPNextExecutionId] (
    [CSPExecutionId] INT NULL )
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPScheduleMasterGraphNodeList]
-- ----------------------------------------------------------------------------------------------
DROP TABLE IF EXISTS [ops].[CSPScheduleMasterGraphNodeList];
GO

CREATE TABLE [ops].[CSPScheduleMasterGraphNodeList] (
    [CSPMasterGraphId] INT NULL,
    [CSPMasterGraphNodeId] INT NULL,
    [CSPMasterGraphNodeTypeId] INT NULL,
    [CSPScheduleGraphId] INT NULL,
    [CSPMasterGraphNodeOrder] INT NULL,
    [RecordInsertDateTime] DATETIME2(6) NULL,
    [RecordUpdateDateTime] DATETIME2(6) NULL,
    [CSPClientId] INT NULL )
;
GO


-- ==============================================================================================
--  FUNCTIONS
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
--  [ops].[GetCurrentGraphExecutionId]
-- ----------------------------------------------------------------------------------------------
DROP FUNCTION IF EXISTS [ops].[GetCurrentGraphExecutionId];
GO

CREATE FUNCTION [ops].[GetCurrentGraphExecutionId] (@cspgraphid INT) RETURNS TABLE
 AS RETURN (SELECT COALESCE (max(CSPExecutionId), 0) AS CSPExecutionId
     FROM ops.CSPExecutionGraph
     WHERE CSPGraphId = @cspgraphid)
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[GetGraphExecutionStatus]
-- ----------------------------------------------------------------------------------------------
DROP FUNCTION IF EXISTS [ops].[GetGraphExecutionStatus];
GO

CREATE FUNCTION [ops].[GetGraphExecutionStatus] (@cspgraphid INT) RETURNS TABLE
 AS RETURN
     SELECT COALESCE (CSPExecutionStatusFlag, 0) AS CSPExecutionStatusFlag
    FROM ops.CSPExecutionGraph
    WHERE CSPGraphId = @cspgraphid
           AND CSPExecutionId = (SELECT max(CSPExecutionId)
                                 FROM ops.CSPExecutionGraph
                                 WHERE CSPGraphId = @cspgraphid)
;
GO


-- ==============================================================================================
--  STORED PROCEDURES
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
--  [ops].[AddContentFileToProcessList]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[AddContentFileToProcessList];
GO

CREATE PROCEDURE [ops].[AddContentFileToProcessList] @ContentFileName VARCHAR (MAX), @ContentFileLocation VARCHAR (MAX)
AS
BEGIN
    IF object_id('ops.ContentFileToBeProcessedList') IS NULL
        CREATE TABLE ops.ContentFileToBeProcessedList (
            LogDateTime DATETIME2 (6),
            ContentFileName VARCHAR (MAX),
            ContentFileLocation VARCHAR (MAX),
            ProcessedFlag BIT );
    INSERT INTO ops.ContentFileToBeProcessedList (LogDateTime, ContentFileName, ContentFileLocation)
    VALUES (getdate(), @ContentFileName, @ContentFileLocation);
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPAcceptContentFile]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPAcceptContentFile];
GO

CREATE proc [ops].[CSPAcceptContentFile] @FileName nvarchar(255), @folderpath nvarchar(255)
AS
BEGIN
  if OBJECT_ID('ops.CspContentFileList') is null
  create table ops.CspContentFileList (
   LogDateTime Datetime2(7),
   ContentFileName nvarchar(255),
   ContentFolderPath nvarchar(255),
   IncomingFileName nvarchar(255),
   HasFileArrived bit )
    declare @sqlstr nvarchar(1000) = 'delete from ops.CspContentFileList ' + 'where ContentFileName = ' + '''' + trim(replace(@FileName, '.txt', '')) + '''' + ';'
 select @sqlstr;
  exec sp_executesql @sqlstr ;
   Set @sqlstr = 'insert into ops.CspContentFileList select distinct getdate(),' + '''' + trim(replace(@FileName, '.txt', '')) + '''' + ',' + '''' + trim(@folderpath) + '''' + ',' + ' case when coalesce(charindex(''\\'',replace(Prop_0,'' '', '''')),0) > 0 then ' + 'substring(prop_0,1,charindex(''\\'',replace(Prop_0,'' '', ''''))-1) ' + ' else replace(Prop_0,'' '', '''') end' + ', 0
          from ops.[' + @FileName + ']' ;
 select @sqlstr;
  exec sp_executesql @sqlstr ;
   End
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CspCloseGraphExecution]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CspCloseGraphExecution];
GO

CREATE PROCEDURE [ops].[CspCloseGraphExecution] @cspexecutionid INT, @cspgraphid INT
AS
BEGIN
    DECLARE @GraphCount AS INT = COALESCE ((SELECT count(*)
                                            FROM ops.CSPExecutionGraph
                                            WHERE CSPExecutionId = @cspexecutionid
                                                   AND @cspgraphid = CSPGraphId
                                                   AND CSPExecutionStatusFlag IN (1, 2, 4)), 0);
    IF (@cspgraphid <> 0)
        BEGIN
            UPDATE ops.CSPExecutionGraph
            SET CSPExecutionStatusFlag = 7
            WHERE CSPExecutionId = @cspexecutionid
                   AND @cspgraphid = CSPGraphId
                   AND CSPExecutionStatusFlag IN (1, 2, 4);
            EXECUTE ops.CSPStreamLogger @cspcontextid = 7, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = 0, @csplogtypecode = 1, @csplogstringshort = 'Close Graph', @csplogstringlong = 'Graph Closed', @csprecordcount = @@ROWCOUNT;
        END
    ELSE BEGIN
            EXECUTE ops.CSPStreamLogger @cspcontextid = 7, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = 0, @csplogtypecode = 1, @csplogstringshort = 'Close Graph', @csplogstringlong = 'Graph Is Not Closed. Invalid Graph & Execution Id Combination', @csprecordcount = @@ROWCOUNT;
        END
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CspDeleteGraph]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CspDeleteGraph];
GO

CREATE PROCEDURE [ops].[CspDeleteGraph] @graphid INT
AS
BEGIN
    DROP TABLE IF EXISTS #Nodelist;
    SELECT CSPScheduleGraphNodeFrom AS CSPScheduleGraphNodeId INTO #Nodelist
    FROM ops.CSPScheduleGraphSegment
    WHERE CSPScheduleGraphId = @graphid
    UNION SELECT CSPScheduleGraphNodeTo
    FROM ops.CSPScheduleGraphSegment
    WHERE CSPScheduleGraphId = @graphid;
    DROP TABLE IF EXISTS #ItemList;
    SELECT CSPScheduledItemId INTO #ItemList
    FROM ops.CSPScheduleGraphNode
    WHERE CSPScheduleGraphNodeId IN (SELECT CSPScheduleGraphNodeId
                                      FROM #Nodelist);
    DELETE ops.CSPScheduleGraph
    WHERE CSPScheduleGraphId = @graphid;
    DELETE ops.CSPScheduleGraphSegment
    WHERE CSPScheduleGraphId = @graphid;
    DELETE ops.CSPScheduleGraphNode
    WHERE CSPScheduleGraphNodeId IN (SELECT CSPScheduleGraphNodeId
                                      FROM #Nodelist
                                      WHERE CSPScheduleGraphNodeId <> 0);
    DELETE ops.CSPScheduledItem
    WHERE CSPScheduledItemId IN (SELECT CSPScheduledItemId
                                  FROM #ItemList
                                  WHERE CSPScheduledItemId <> 0);
    DELETE ops.CSPScheduledItemString
    WHERE CSPScheduledItemId IN (SELECT CSPScheduledItemId
                                  FROM #ItemList
                                  WHERE CSPScheduledItemId <> 0);
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPExecGraphFinalise]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPExecGraphFinalise];
GO

CREATE PROCEDURE [ops].[CSPExecGraphFinalise] @cspexecutionid INT
AS
BEGIN
    DECLARE @successflag AS INT = 0;
    DECLARE @cspgraphid AS INT = 0;
    DECLARE @cspcontextid AS INT = 0;
    DECLARE @cspgraphstatuscode AS INT = 0;
    DECLARE @replyMessage AS VARCHAR (100) = '';
    DECLARE @nodesUnprocessed AS INT = 0;
    DECLARE @nodesTobeprocessed AS INT = 0;
    DECLARE @nodesCompleted AS INT = 0;
    DECLARE @nodesFailed AS INT = 0;
    DECLARE @nodesFailedinLog AS INT = 0;
    DECLARE @debug AS INT = 1;
    DECLARE @logMessage AS NVARCHAR (1024) = '';
    SELECT @cspgraphid = CSPGraphId,
           @cspcontextid = CSPContextId
    FROM ops.CSPExecutionGraph
    WHERE CSPExecutionId = @cspexecutionid;
    SELECT @nodesTobeprocessed = count(*)
    FROM ops.CSPExecutionGraphNodesList
    WHERE CSPExecutionId = @cspexecutionid;
    SELECT @nodesUnprocessed = count(*)
    FROM ops.CSPExecutionGraphNodesList
    WHERE CSPExecutionId = @cspexecutionid
           AND CSPExecutionStatusFlag = 0;
    SELECT @nodesFailed = count(*)
    FROM ops.CSPExecutionGraphNodesList
    WHERE CSPExecutionId = @cspexecutionid
           AND CSPExecutionStatusFlag = 4;
    SELECT @nodesCompleted = count(*)
    FROM ops.CSPExecutionGraphNodesList
    WHERE CSPExecutionId = @cspexecutionid
           AND CSPExecutionStatusFlag = 7;
    SELECT @nodesFailedinLog = count(DISTINCT CSPGraphNodeId)
    FROM ops.CSPLogStreamLive
    WHERE CSPLogTypeCode > 1
           AND CSPExecutionId = @cspexecutionid;
    IF @debug > 0
        BEGIN
            SET @logMessage = 'Nodes To Be Processed = ' + CAST (@nodesTobeprocessed AS VARCHAR (5)) + 'Nodes Not Yet Processed = ' + CAST (@nodesUnprocessed AS VARCHAR (5)) + 'Nodes Failed = ' + CAST (@nodesFailed AS VARCHAR (5)) + 'Nodes Completed = ' + CAST (@nodesCompleted AS VARCHAR (5)) + 'Nodes with Failure Logs = ' + CAST (@nodesFailedinLog AS VARCHAR (5));
            EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = 0, @csplogtypecode = 1, @csplogstringshort = 'Debug - [CSPExecGraphFinalise]', @csplogstringlong = @logMessage;
        END
    IF (@nodesTobeprocessed = @nodesCompleted)
       AND @nodesFailedinLog = 0
        SET @successflag = 1;
    DELETE ops.CSPExecutionLiveList
    WHERE CSPExecutionId = @cspexecutionid;
    DELETE ops.CSPExecutionLiveListSetup
    WHERE CSPExecutionId = @cspexecutionid;
    DELETE ops.CSPExecutionGraphNodesList
    WHERE CSPExecutionId = @cspexecutionid;
    DELETE ops.CSPLogStreamLive
    WHERE CSPExecutionId = @cspexecutionid;
    IF @debug > 0
        SELECT 'Stage 1';
    IF @successflag = 1
        BEGIN
            EXECUTE ops.CSPManageGraphExecution @cspgraphid = @cspgraphid, @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid OUTPUT, @cspgraphstatuscode = @cspgraphstatuscode OUTPUT, @replyMessage = @replyMessage OUTPUT, @CSPExecutionControlFlag = 5;
            IF @debug > 0
                BEGIN
                    SET @logMessage = 'SuccessFlag in Successful Leg = ' + CAST (@successflag AS VARCHAR (5));
                    EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = 0, @csplogtypecode = 1, @csplogstringshort = 'Debug - [CSPExecGraphFinalise]', @csplogstringlong = @logMessage;
                END
        END
    ELSE BEGIN
            IF @nodesFailed > 0
               OR @nodesFailedinLog > 0
                  AND @nodesFailedinLog = 0
                EXECUTE ops.CSPManageGraphExecution @cspgraphid = @cspgraphid, @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid OUTPUT, @cspgraphstatuscode = @cspgraphstatuscode OUTPUT, @replyMessage = @replyMessage OUTPUT, @CSPExecutionControlFlag = 2;
            SET @logMessage = 'SuccessFlag in Failed Leg = ' + CAST (@successflag AS VARCHAR (5));
            EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = 0, @csplogtypecode = 1, @csplogstringshort = 'Debug - [CSPExecGraphFinalise]', @csplogstringlong = @logMessage;
            THROW 51000, 'Graph Execution Failed - Investigate', 1;
        END
    EXECUTE [ops].[CSPManageMasterGraph] @cspgraphid = @cspgraphid, @cspexecutionid = @cspexecutionid, @cspcontextid = @cspcontextid;
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPExecGraphNodeTypeGraph]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPExecGraphNodeTypeGraph];
GO

CREATE PROCEDURE [ops].[CSPExecGraphNodeTypeGraph] @cspexecutionid INT, @cspgraphnodeid INT, @debugflag BIT=0
AS
BEGIN
    DECLARE @sqlstr AS VARCHAR (MAX);
    DECLARE @CSPScheduledItemId AS INT;
    DECLARE @CSPParentGraphId AS INT;
    DECLARE @CspChildGraphId AS INT;
    DECLARE @cspChildExecutionid AS INT;
    DECLARE @cspgraphid AS INT;
    DECLARE @CSPMasterGraphExecutionId AS INT = 0;
    DECLARE @cspcontextid AS INT;
    DECLARE @csplogtypecode AS INT = 3;
    DECLARE @nodeExecutionStatusParentFlag AS INT = 0;
    DECLARE @nodeExecutionStatusChildFlag AS INT = 0;
    DECLARE @nodeExecStartDateTime AS DATETIME2 (0) = getdate();
    DECLARE @nodeExecEndDateTime AS DATETIME2 (0);
    IF @debugflag = 1
        SELECT @cspexecutionid,
               @cspgraphnodeid;
    DECLARE @errorResultStr AS VARCHAR (1024);
    SELECT @cspcontextid = CSPContextId,
           @cspgraphid = CSPGraphId
    FROM ops.CSPExecutionGraph
    WHERE CSPExecutionId = @cspexecutionid;
    SELECT @CSPMasterGraphExecutionId = CSPMasterGraphExecutionId
    FROM ops.CSPExecutionMasterGraphNode
    WHERE CSPMasterGraphNodeExecutionId = @cspexecutionid;
    SELECT @CSPMasterGraphExecutionId = COALESCE (@CSPMasterGraphExecutionId, 0);
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'CONTEXTID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'RUNID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'GRAPHID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'GRAPHNODEID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'MASTERRUNID';
    EXECUTE [ops].[CSPSetExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'CONTEXTID', @cspcontextid;
    EXECUTE [ops].[CSPSetExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'RUNID', @cspexecutionid;
    EXECUTE [ops].[CSPSetExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'GRAPHID', @cspgraphid;
    EXECUTE [ops].[CSPSetExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'GRAPHNODEID', @cspgraphnodeid;
    EXECUTE [ops].[CSPSetExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'MASTERRUNID', @CSPMasterGraphExecutionId;
    EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 1, @csplogstringshort = 'Node Execution - Parameters Added', @csprecordcount = 0;
    DECLARE @CSPGraphNodeStartDateTime AS DATETIME2 (6) = GetDate();
    INSERT INTO ops.CSPExecutionGraphNode (CSPExecutionId, CSPContextId, CSPGraphId, CSPGraphNodeId, CSPGraphNodeStartDateTime, CSPExecutionStatusFlag)
    VALUES (@cspexecutionid, @cspcontextid, @cspgraphid, @cspgraphnodeid, @CSPGraphNodeStartDateTime, 1);
    IF (@cspgraphnodeid <> 0)
        BEGIN TRY
            SELECT @CspChildGraphId = a.CSPScheduleGraphId
            FROM ops.CSPScheduleGraph AS a, ops.CSPScheduledItem AS b, ops.CSPScheduleGraphNode AS c
            WHERE a.CSPScheduleGraphId = b.ScheduledItemReference
                   AND c.CSPScheduleGraphNodeId = @cspgraphnodeid
                   AND c.CSPScheduledItemId = b.CSPScheduledItemId
                   AND b.CSPScheduledItemTypeId = 1;
            IF @debugflag = 1
                SELECT @CspChildGraphId;
            IF (@CspChildGraphId IS NULL)
                BEGIN
                    SET @errorResultStr = 'Graph Node does not exist in CSPScheduleGraphNode table. Please Add';
                    EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 3, @csplogstringshort = 'Node Execution Failure', @csplogstringlong = @errorResultStr;
                    THROW 51001, @errorResultStr, 1;
                END
            EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 1, @csplogstringshort = 'Node Execution - Located Graph', @csprecordcount = @CspChildGraphId;
            BEGIN TRY
                EXECUTE [ops].[CSPExecGraphPrep] @CspChildGraphId, 1;
                SELECT @cspChildExecutionid = CSPExecutionId
                FROM ops.CSPExecutionGraph
                WHERE CSPGraphId = @CspChildGraphId;
                EXECUTE [ops].[CSPGraphExec] @cspChildExecutionid;
                EXECUTE [ops].[CSPExecGraphFinalise] @cspChildExecutionid;
                SET @nodeExecEndDateTime = Getdate();
                SELECT @nodeExecutionStatusParentFlag = count(*)
                FROM ops.CSPLogStream
                WHERE CSPLogTypeCode > 1
                       AND CSPExecutionId = @cspexecutionid
                       AND CSPGraphId = @cspgraphid
                       AND CSPGraphNodeId = @cspgraphnodeid
                       AND CSPLogDateTime BETWEEN @nodeExecStartDateTime AND @nodeExecEndDateTime;
                IF (@nodeExecutionStatusParentFlag = 0)
                   AND (@nodeExecutionStatusChildFlag = 0)
                    BEGIN
                        UPDATE a
                        SET CSPExecutionStatusFlag = 7
                        FROM ops.CSPExecutionGraphNode AS a
                        WHERE a.CSPGraphId = @cspgraphid
                               AND a.CSPGraphNodeId = @cspgraphnodeid
                               AND a.CSPExecutionId = @cspexecutionid
                               AND a.CSPContextId = @cspcontextid
                               AND a.CSPGraphNodeStartDateTime = @CSPGraphNodeStartDateTime;
                        EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 1, @csplogstringshort = 'Node Execution - Graph Executed', @csprecordcount = 0;
                    END
                ELSE BEGIN
                        UPDATE a
                        SET CSPExecutionStatusFlag = 4
                        FROM ops.CSPExecutionGraphNode AS a
                        WHERE a.CSPGraphId = @cspgraphid
                               AND a.CSPGraphNodeId = @cspgraphnodeid
                               AND a.CSPExecutionId = @cspexecutionid
                               AND a.CSPContextId = @cspcontextid
                               AND a.CSPGraphNodeStartDateTime = @CSPGraphNodeStartDateTime;
                        SET @errorResultStr = 'Error Message - ' + Error_message();
                        EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 3, @csplogstringshort = 'Node Execution Failure', @csplogstringlong = @errorResultStr;
                    END
            END TRY
            BEGIN CATCH
                UPDATE a
                SET CSPExecutionStatusFlag = 4
                FROM ops.CSPExecutionGraphNode AS a
                WHERE a.CSPGraphId = @cspgraphid
                       AND a.CSPGraphNodeId = @cspgraphnodeid
                       AND a.CSPExecutionId = @cspexecutionid
                       AND a.CSPContextId = @cspcontextid
                       AND a.CSPGraphNodeStartDateTime = @CSPGraphNodeStartDateTime;
                SET @errorResultStr = 'Error Message - ' + Error_message();
                EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 3, @csplogstringshort = 'Node Execution Failure', @csplogstringlong = @errorResultStr;
            END CATCH
        END TRY
        BEGIN CATCH
            UPDATE a
            SET CSPExecutionStatusFlag = 4
            FROM ops.CSPExecutionGraphNode AS a
            WHERE a.CSPGraphId = @cspgraphid
                   AND a.CSPGraphNodeId = @cspgraphnodeid
                   AND a.CSPExecutionId = @cspexecutionid
                   AND a.CSPContextId = @cspcontextid
                   AND a.CSPGraphNodeStartDateTime = @CSPGraphNodeStartDateTime;
            SET @errorResultStr = 'Error Message - ' + Error_message();
            EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 3, @csplogstringshort = 'Node Execution Failure', @csplogstringlong = @errorResultStr;
        END CATCH
    ELSE BEGIN
            UPDATE a
            SET CSPExecutionStatusFlag = 7
            FROM ops.CSPExecutionGraphNode AS a
            WHERE a.CSPGraphId = @cspgraphid
                   AND a.CSPGraphNodeId = @cspgraphnodeid
                   AND a.CSPExecutionId = @cspexecutionid
                   AND a.CSPContextId = @cspcontextid
                   AND a.CSPGraphNodeStartDateTime = @CSPGraphNodeStartDateTime;
        END
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'CONTEXTID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'RUNID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'GRAPHID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'GRAPHNODEID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'MASTERRUNID';
    UPDATE a
    SET CSPGraphNodeEndDateTime = getdate()
    FROM ops.CSPExecutionGraphNode AS a
    WHERE a.CSPGraphId = @cspgraphid
           AND a.CSPGraphNodeId = @cspgraphnodeid
           AND a.CSPExecutionId = @cspexecutionid
           AND a.CSPContextId = @cspcontextid
           AND a.CSPGraphNodeStartDateTime = @CSPGraphNodeStartDateTime;
    UPDATE ops.CSPExecutionLiveList
    SET CSPExecutionStatusFlag = 1
    WHERE CSPExecutionId = @cspexecutionid
           AND CSPScheduleGraphNode = @cspgraphnodeid;
    EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 1, @csplogstringshort = 'Node Execution - Completed', @csprecordcount = 0;
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPExecGraphNodeTypeSQL]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPExecGraphNodeTypeSQL];
GO

CREATE PROCEDURE [ops].[CSPExecGraphNodeTypeSQL] @cspexecutionid INT, @cspgraphnodeid INT, @debugflag BIT=1
AS
BEGIN
    DECLARE @sqlstr AS NVARCHAR (MAX);
    DECLARE @CSPScheduledItemId AS INT;
    DECLARE @cspgraphid AS INT;
    DECLARE @CSPMasterGraphExecutionId AS INT = 0;
    DECLARE @cspcontextid AS INT;
    DECLARE @csplogtypecode AS INT = 3;
    DECLARE @nodeExecutionStatusFlag AS INT = 0;
    DECLARE @nodeExecStartDateTime AS DATETIME2 (6) = getdate();
    DECLARE @nodeExecEndDateTime AS DATETIME2 (6);
    IF @debugflag = 1
        SELECT @cspexecutionid,
               @cspgraphnodeid;
    DECLARE @errorResultStr AS VARCHAR (1024);
    SELECT @cspcontextid = CSPContextId,
           @cspgraphid = CSPGraphId
    FROM ops.CSPExecutionGraph
    WHERE CSPExecutionId = @cspexecutionid;
    SELECT @CSPMasterGraphExecutionId = CSPMasterGraphExecutionId
    FROM ops.CSPExecutionMasterGraphNode
    WHERE CSPMasterGraphNodeExecutionId = @cspexecutionid;
    SELECT @CSPMasterGraphExecutionId = COALESCE (@CSPMasterGraphExecutionId, 0);
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'CONTEXTID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'RUNID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'GRAPHID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'GRAPHNODEID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'MASTERRUNID';
    EXECUTE [ops].[CSPSetExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'CONTEXTID', @cspcontextid;
    EXECUTE [ops].[CSPSetExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'RUNID', @cspexecutionid;
    EXECUTE [ops].[CSPSetExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'GRAPHID', @cspgraphid;
    EXECUTE [ops].[CSPSetExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'GRAPHNODEID', @cspgraphnodeid;
    EXECUTE [ops].[CSPSetExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'MASTERRUNID', @CSPMasterGraphExecutionId;
    EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 1, @csplogstringshort = 'Node Execution - Parameters Added', @csprecordcount = 0;
    DECLARE @CSPGraphNodeStartDateTime AS DATETIME2 (6) = GetDate();
    INSERT INTO ops.CSPExecutionGraphNode (CSPExecutionId, CSPContextId, CSPGraphId, CSPGraphNodeId, CSPGraphNodeStartDateTime, CSPExecutionStatusFlag)
    VALUES (@cspexecutionid, @cspcontextid, @cspgraphid, @cspgraphnodeid, @CSPGraphNodeStartDateTime, 1);
    IF (@cspgraphnodeid <> 0)
        BEGIN TRY
            SELECT @sqlstr = CSPScheduledItemString
            FROM ops.CSPScheduledItemString AS a, ops.CSPScheduledItem AS b, ops.CSPScheduleGraphNode AS c
            WHERE a.CSPScheduledItemId = b.CSPScheduledItemId
                   AND c.CSPScheduleGraphNodeId = @cspgraphnodeid
                   AND c.CSPScheduledItemId = b.CSPScheduledItemId
                   AND b.CSPScheduledItemTypeId = 7
                   AND a.CSPScheduledItemCurrentFlag = 1;
            IF @debugflag = 1
                SELECT @sqlstr;
            IF (@sqlstr = '')
               OR (@sqlstr IS NULL)
                BEGIN
                    SET @errorResultStr = 'Graph Node does not exist in CSPScheduleGraphNode table. Please Add';
                    EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 3, @csplogstringshort = 'Node Execution Failure', @csplogstringlong = @errorResultStr;
                    THROW 51001, @errorResultStr, 1;
                END
            EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 1, @csplogstringshort = 'Node Execution - Retrieved SQL String', @csprecordcount = 0;
            IF (@sqlstr LIKE '%##%')
                EXECUTE ops.CSPSubstituteParams @sqlstr = @sqlstr, @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @retStr = @sqlstr OUTPUT;
            EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 1, @csplogstringshort = 'Node Execution - Params Substituted', @csprecordcount = 0;
            DECLARE @SQLStrPre AS VARCHAR (1000) = ' Begin Try
               exec [ops].[CSPStreamLogger] @cspcontextid = ' + CAST (@cspcontextid AS VARCHAR (10)) + ' , @cspexecutionid = ' + CAST (@cspexecutionid AS VARCHAR (10)) + ' , @cspgraphid = ' + CAST (@cspgraphid AS VARCHAR (20)) + ' , @cspgraphnodeid = ' + CAST (@cspgraphnodeid AS VARCHAR (20)) + ' , @csplogtypecode = ' + CAST (1 AS VARCHAR (10)) + ' , @csplogstringshort = ''Current Session ID - '', @csplogstringlong = @@SPID, @csprecordcount = @@ROWCOUNT; ';
            DECLARE @SQLStrPost AS VARCHAR (1000) = ' End Try
               Begin Catch
                 declare @errorstring varchar(255) = Error_message();
                exec [ops].[CSPStreamLogger] @cspcontextid = ' + CAST (@cspcontextid AS VARCHAR (10)) + ' , @cspexecutionid = ' + CAST (@cspexecutionid AS VARCHAR (10)) + ' , @cspgraphid = ' + CAST (@cspgraphid AS VARCHAR (20)) + ' , @cspgraphnodeid = ' + CAST (@cspgraphnodeid AS VARCHAR (20)) + ' , @csplogtypecode = ' + CAST (@csplogtypecode AS VARCHAR (10)) + ' , @csplogstringshort = ''Error Executing Node - '', @csplogstringlong = @errorstring, @csprecordcount = @@ROWCOUNT;' + ' Throw 51001, @errorstring, 1 ;' + ' End Catch ';
            SET @sqlstr = @SQLStrPre + @sqlstr + @SQLStrPost;
            EXECUTE [ops].[CSPStoreExecutionString] @sqlstr, @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid;
            EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 1, @csplogstringshort = 'Node Execution - SQL String Stored', @csprecordcount = 0;
            BEGIN TRY
                EXECUTE sp_executesql @sqlstr;
                SET @nodeExecEndDateTime = Getdate();
                SELECT @nodeExecutionStatusFlag = count(*)
                FROM ops.CSPLogStreamLive
                WHERE CSPLogTypeCode > 1
                       AND CSPExecutionId = @cspexecutionid
                       AND CSPGraphId = @cspgraphid
                       AND CSPGraphNodeId = @cspgraphnodeid
                       AND CSPLogDateTime BETWEEN @nodeExecStartDateTime AND @nodeExecEndDateTime;
                IF (@nodeExecutionStatusFlag = 0)
                    BEGIN
                        UPDATE a
                        SET CSPExecutionStatusFlag = 7
                        FROM ops.CSPExecutionGraphNode AS a
                        WHERE a.CSPGraphId = @cspgraphid
                               AND a.CSPGraphNodeId = @cspgraphnodeid
                               AND a.CSPExecutionId = @cspexecutionid
                               AND a.CSPContextId = @cspcontextid
                               AND a.CSPGraphNodeStartDateTime = @CSPGraphNodeStartDateTime;
                        EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 1, @csplogstringshort = 'Node Execution - SQL String Executed', @csprecordcount = 0;
                    END
                ELSE BEGIN
                        UPDATE a
                        SET CSPExecutionStatusFlag = 4
                        FROM ops.CSPExecutionGraphNode AS a
                        WHERE a.CSPGraphId = @cspgraphid
                               AND a.CSPGraphNodeId = @cspgraphnodeid
                               AND a.CSPExecutionId = @cspexecutionid
                               AND a.CSPContextId = @cspcontextid
                               AND a.CSPGraphNodeStartDateTime = @CSPGraphNodeStartDateTime;
                        SET @errorResultStr = 'Error Message - ' + Error_message();
                        EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 3, @csplogstringshort = 'Node Execution Failure', @csplogstringlong = @errorResultStr;
                    END
            END TRY
            BEGIN CATCH
                UPDATE a
                SET CSPExecutionStatusFlag = 4
                FROM ops.CSPExecutionGraphNode AS a
                WHERE a.CSPGraphId = @cspgraphid
                       AND a.CSPGraphNodeId = @cspgraphnodeid
                       AND a.CSPExecutionId = @cspexecutionid
                       AND a.CSPContextId = @cspcontextid
                       AND a.CSPGraphNodeStartDateTime = @CSPGraphNodeStartDateTime;
                SET @errorResultStr = 'Error Message - ' + Error_message();
                EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 3, @csplogstringshort = 'Node Execution Failure', @csplogstringlong = @errorResultStr;
            END CATCH
        END TRY
        BEGIN CATCH
            UPDATE a
            SET CSPExecutionStatusFlag = 4
            FROM ops.CSPExecutionGraphNode AS a
            WHERE a.CSPGraphId = @cspgraphid
                   AND a.CSPGraphNodeId = @cspgraphnodeid
                   AND a.CSPExecutionId = @cspexecutionid
                   AND a.CSPContextId = @cspcontextid
                   AND a.CSPGraphNodeStartDateTime = @CSPGraphNodeStartDateTime;
            SET @errorResultStr = 'Error Message - ' + Error_message();
            EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 3, @csplogstringshort = 'Node Execution Failure', @csplogstringlong = @errorResultStr;
        END CATCH
    ELSE BEGIN
            UPDATE a
            SET CSPExecutionStatusFlag = 7
            FROM ops.CSPExecutionGraphNode AS a
            WHERE a.CSPGraphId = @cspgraphid
                   AND a.CSPGraphNodeId = @cspgraphnodeid
                   AND a.CSPExecutionId = @cspexecutionid
                   AND a.CSPContextId = @cspcontextid
                   AND a.CSPGraphNodeStartDateTime = @CSPGraphNodeStartDateTime;
        END
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'CONTEXTID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'RUNID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'GRAPHID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'GRAPHNODEID';
    EXECUTE [ops].[CSPRemoveExecutionParameters] @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 'MASTERRUNID';
    UPDATE a
    SET CSPGraphNodeEndDateTime = getdate()
    FROM ops.CSPExecutionGraphNode AS a
    WHERE a.CSPGraphId = @cspgraphid
           AND a.CSPGraphNodeId = @cspgraphnodeid
           AND a.CSPExecutionId = @cspexecutionid
           AND a.CSPContextId = @cspcontextid
           AND a.CSPGraphNodeStartDateTime = @CSPGraphNodeStartDateTime;
    UPDATE ops.CSPExecutionLiveList
    SET CSPExecutionStatusFlag = 1
    WHERE CSPExecutionId = @cspexecutionid
           AND CSPScheduleGraphNode = @cspgraphnodeid;
    EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 1, @csplogstringshort = 'Node Execution - Completed', @csprecordcount = 0;
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPExecGraphPrep]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPExecGraphPrep];
GO

CREATE PROCEDURE [ops].[CSPExecGraphPrep] @cspgraphid INT, @cspcontextid INT
AS
BEGIN
    DECLARE @cspgraphstatuscode AS INT = 0;
    DECLARE @cspexecutionid AS INT = 0;
    DECLARE @replyMessage AS VARCHAR (100) = '';
    EXECUTE ops.CSPManageGraphExecution @cspgraphid = @cspgraphid, @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid OUTPUT, @cspgraphstatuscode = @cspgraphstatuscode OUTPUT, @replyMessage = @replyMessage OUTPUT, @CSPExecutionControlFlag = 0;
    EXECUTE [ops].[CSPManageMasterGraph] @cspgraphid = @cspgraphid, @cspexecutionid = @cspexecutionid, @cspcontextid = @cspcontextid;
    IF @cspgraphstatuscode = 7
        BEGIN
            SELECT getdate();
            THROW 51000, 'Graph has not been initiated - Old Graph Completed - Investigate', 1;
        END
    IF @cspgraphstatuscode = 3
        BEGIN
            SELECT getdate();
            THROW 51000, 'Graph has been stopped - Should be restarted or Abandoned', 1;
        END
    IF @cspgraphstatuscode = 2
        BEGIN
            SELECT getdate();
            THROW 51000, 'Graph is Under Progress - No action taken', 1;
        END
    IF @cspgraphstatuscode IN (1, 4, 5)
        BEGIN
            IF object_id('[ops].[CSPExecutionLiveListSetup]') IS NULL
                CREATE TABLE [ops].[CSPExecutionLiveListSetup] (
                    [CSPExecutionId] INT NULL,
                    [rno] INT NULL,
                    [CSPScheduleGraphNodeFrom] INT NULL,
                    [CSPScheduleGraphNodeTo] INT NULL );
            IF object_id('[ops].[CSPExecutionLiveList]') IS NULL
                CREATE TABLE [ops].[CSPExecutionLiveList] (
                    [CSPExecutionId] INT NULL,
                    [rno] INT NULL,
                    [CSPScheduleGraphNode] INT NULL,
                    CSPExecutionStatusFlag INT NULL );
            IF object_id('[ops].[CSPExecutionGraphNodeSetup]') IS NULL
                CREATE TABLE [ops].[CSPExecutionGraphNodeSetup] (
                    [CSPExecutionId] INT NULL,
                    [ContextId] INT NULL,
                    [CSPGraphId] INT NULL,
                    [CSPGraphNodeId] INT NULL,
                    [CSPGraphNodeStartDateTime] DATETIME2 (0) NULL,
                    [CSPGraphNodeEndDateTime] DATETIME2 (0) NULL,
                    [CSPExecutionStatusFlag] INT NULL );
            IF object_id('[ops].[CSPExecutionGraphNodesList]') IS NULL
                CREATE TABLE [ops].[CSPExecutionGraphNodesList] (
                    [CSPExecutionId] INT NULL,
                    [CSPGraphId] INT NULL,
                    [CSPGraphNodeId] INT NULL,
                    [CSPExecutionStatusFlag] INT NULL );
            DELETE ops.CSPExecutionGraphNodesList
            WHERE CSPExecutionId = @cspexecutionid;
            DELETE ops.CSPLogStreamLive
            WHERE CSPExecutionId = @cspexecutionid;
            INSERT INTO ops.CSPExecutionGraphNodesList (CSPExecutionId, CSPGraphId, CSPGraphNodeId, CSPExecutionStatusFlag)
            SELECT @cspexecutionid,
                   @cspgraphid,
                   fromstep,
                   0
            FROM (SELECT DISTINCT CSPScheduleGraphNodeFrom AS fromstep
                    FROM ops.CSPScheduleGraphSegment
                    WHERE CSPScheduleGraphId = @cspgraphid
                    UNION SELECT DISTINCT CSPScheduleGraphNodeTo AS fromstep
                    FROM ops.CSPScheduleGraphSegment
                    WHERE CSPScheduleGraphId = @cspgraphid) AS sa;
            DELETE ops.CSPExecutionLiveListSetup
            WHERE CSPExecutionId = @cspexecutionid;
            DELETE ops.CSPExecutionLiveList
            WHERE CSPExecutionId = @cspexecutionid;
            INSERT INTO ops.CSPExecutionLiveListSetup
            SELECT @cspexecutionid,
                   ROW_NUMBER() OVER (ORDER BY CSPScheduleGraphNodeFrom) AS rno,
                   CSPScheduleGraphNodeFrom,
                   CSPScheduleGraphNodeTo
            FROM ops.CSPScheduleGraphSegment
            WHERE CSPScheduleGraphId = @cspgraphid;
            UPDATE a
            SET CSPExecutionStatusFlag = b.CSPExecutionStatusFlag
            FROM ops.CSPExecutionGraphNodesList AS a, (SELECT CSPGraphId,
                                                                  CSPGraphNodeId,
                                                                  max(CSPExecutionStatusFlag) AS CSPExecutionStatusFlag
                                                         FROM ops.CSPExecutionGraphNode
                                                         WHERE CSPExecutionId = @cspexecutionid
                                                         GROUP BY CSPGraphId, CSPGraphNodeId) AS b
            WHERE a.CSPGraphNodeId = b.CSPGraphNodeId
                   AND a.CSPGraphId = b.CSPGraphId
                   AND a.CSPExecutionId = @cspexecutionid;
            INSERT INTO ops.CSPExecutionLiveList (CSPExecutionId, rno, CSPScheduleGraphNode, CSPExecutionStatusFlag)
            SELECT CSPExecutionId,
                   ROW_NUMBER() OVER (PARTITION BY 1 ORDER BY rno) AS rno,
                   CSPScheduleGraphNodeFrom,
                   0
            FROM (SELECT a.CSPExecutionId,
                             a.CSPScheduleGraphNodeFrom,
                             min(a.rno) AS rno
                    FROM (SELECT a.*
                              FROM ops.CSPExecutionLiveListSetup AS a, ops.CSPExecutionGraphNodesList AS b
                              WHERE CSPExecutionStatusFlag IN (4, 0)
                                     AND a.CSPScheduleGraphNodeFrom = b.CSPGraphNodeId
                                     AND a.CSPExecutionId = b.CSPExecutionId
                                     AND a.CSPExecutionId = @cspexecutionid) AS a
                             LEFT OUTER JOIN (SELECT a.*
                              FROM ops.CSPExecutionLiveListSetup AS a, ops.CSPExecutionGraphNodesList AS b
                              WHERE CSPExecutionStatusFlag IN (4, 0)
                                     AND a.CSPScheduleGraphNodeFrom = b.CSPGraphNodeId
                                     AND a.CSPExecutionId = b.CSPExecutionId
                                     AND a.CSPExecutionId = @cspexecutionid) AS c
                             ON a.CSPScheduleGraphNodeFrom = c.CSPScheduleGraphNodeTo
                                AND a.CSPExecutionId = c.CSPExecutionId
                    WHERE c.CSPScheduleGraphNodeFrom IS NULL
                    GROUP BY a.CSPExecutionId, a.CSPScheduleGraphNodeFrom) AS x;
            IF (@@ROWCOUNT = 0)
                INSERT INTO ops.CSPExecutionLiveList (CSPExecutionId, rno, CSPScheduleGraphNode, CSPExecutionStatusFlag)
                SELECT CSPExecutionId,
                       ROW_NUMBER() OVER (PARTITION BY 1 ORDER BY rno) AS rno,
                       CSPScheduleGraphNodeTo,
                       0
                FROM (SELECT a.CSPExecutionId,
                                 a.CSPScheduleGraphNodeTo,
                                 min(a.rno) AS rno
                        FROM (SELECT a.*
                                  FROM ops.CSPExecutionLiveListSetup AS a, ops.CSPExecutionGraphNodesList AS b
                                  WHERE CSPExecutionStatusFlag IN (4, 0)
                                         AND a.CSPScheduleGraphNodeTo = b.CSPGraphNodeId
                                         AND a.CSPExecutionId = b.CSPExecutionId
                                         AND a.CSPExecutionId = @cspexecutionid) AS a
                                 LEFT OUTER JOIN (SELECT a.*
                                  FROM ops.CSPExecutionLiveListSetup AS a, ops.CSPExecutionGraphNodesList AS b
                                  WHERE CSPExecutionStatusFlag IN (4, 0)
                                         AND a.CSPScheduleGraphNodeFrom = b.CSPGraphNodeId
                                         AND a.CSPExecutionId = b.CSPExecutionId
                                         AND a.CSPExecutionId = @cspexecutionid) AS c
                                 ON a.CSPScheduleGraphNodeFrom = c.CSPScheduleGraphNodeFrom
                                    AND a.CSPExecutionId = c.CSPExecutionId
                        WHERE c.CSPScheduleGraphNodeFrom IS NULL
                        GROUP BY a.CSPExecutionId, a.CSPScheduleGraphNodeTo) AS x;
        END
    ELSE BEGIN
            SELECT getdate();
            THROW 51000, 'Execution Stopped - Refer to Previous Message for Error', 1;
        END
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPExecGraphProgress]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPExecGraphProgress];
GO

CREATE PROCEDURE [ops].[CSPExecGraphProgress] @cspexecutionid INT
AS
BEGIN
    IF (SELECT count(*)
        FROM ops.CSPExecutionLiveList
        WHERE CSPExecutionId = @cspexecutionid
               AND CSPExecutionStatusFlag = 0) = 0
        BEGIN
            DELETE ops.CSPExecutionLiveList
            WHERE CSPExecutionId = @cspexecutionid;
            UPDATE a
            SET CSPExecutionStatusFlag = b.CSPExecutionStatusFlag
            FROM ops.CSPExecutionGraphNodesList AS a, (SELECT CSPGraphNodeId,
                                                                  max(CSPExecutionStatusFlag) AS CSPExecutionStatusFlag
                                                         FROM ops.CSPExecutionGraphNode
                                                         WHERE CSPExecutionId = @cspexecutionid
                                                         GROUP BY CSPGraphNodeId) AS b
            WHERE a.CSPGraphNodeId = b.CSPGraphNodeId
                   AND a.CSPExecutionId = @cspexecutionid;
            INSERT INTO ops.CSPExecutionLiveList (CSPExecutionId, rno, CSPScheduleGraphNode, CSPExecutionStatusFlag)
            SELECT x.CSPExecutionId,
                   row_number() OVER (PARTITION BY 1 ORDER BY x.CSPScheduleGraphNodeTo),
                   x.CSPScheduleGraphNodeTo,
                   0
            FROM (SELECT DISTINCT a.CSPExecutionId,
                                    a.CSPScheduleGraphNodeTo
                    FROM (SELECT a.CSPExecutionId,
                                   b.CSPScheduleGraphNodeTo
                            FROM ops.CSPExecutionGraphNodesList AS a
                                   INNER JOIN ops.CSPExecutionLiveListSetup AS b
                                   ON a.CSPGraphNodeId = b.CSPScheduleGraphNodeFrom
                            WHERE a.CSPExecutionStatusFlag = 7
                                   AND a.CSPExecutionId = b.CSPExecutionId
                                   AND a.CSPExecutionId = @cspexecutionid) AS a
                           LEFT OUTER JOIN (SELECT a.CSPExecutionId,
                                   a.CSPScheduleGraphNodeTo,
                                   b.CSPGraphNodeId
                            FROM ops.CSPExecutionLiveListSetup AS a, ops.CSPExecutionGraphNodesList AS b
                            WHERE CSPScheduleGraphNodeTo IN (SELECT DISTINCT CSPScheduleGraphNodeTo
                                                              FROM ops.CSPExecutionGraphNodesList AS a
                                                                     INNER JOIN ops.CSPExecutionLiveListSetup AS b
                                                                     ON a.CSPGraphNodeId = b.CSPScheduleGraphNodeFrom
                                                              WHERE a.CSPExecutionStatusFlag IN (7)
                                                                     AND a.CSPExecutionId = b.CSPExecutionId
                                                                     AND a.CSPExecutionId = @cspexecutionid)
                                   AND a.CSPScheduleGraphNodeFrom = b.CSPGraphNodeId
                                   AND a.CSPExecutionId = b.CSPExecutionId
                                   AND a.CSPExecutionId = @cspexecutionid
                                   AND CSPExecutionStatusFlag IN (0, 4, 5)) AS b
                           ON a.CSPScheduleGraphNodeTo = b.CSPScheduleGraphNodeTo
                           LEFT OUTER JOIN ops.CSPExecutionGraphNodesList AS c
                           ON a.CSPScheduleGraphNodeTo = c.CSPGraphNodeId
                              AND a.CSPExecutionId = c.CSPExecutionId
                              AND a.CSPExecutionId = @cspexecutionid
                              AND c.CSPExecutionStatusFlag IN (4, 7)
                    WHERE b.CSPGraphNodeId IS NULL
                           AND c.CSPGraphNodeId IS NULL) AS x;
        END
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPExecuteGenericGraph]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPExecuteGenericGraph];
GO

CREATE PROCEDURE [ops].[CSPExecuteGenericGraph] @cspgraphid INT
AS
BEGIN
    DECLARE @cspexecutionid AS INT;
    EXECUTE ops.CSPExecGraphPrep @cspgraphid = @cspgraphid, @cspcontextid = 1;
    SELECT @cspexecutionid = CSPExecutionId
    FROM [ops].[GetCurrentGraphExecutionId](@cspgraphid);
    EXECUTE ops.CSPGraphExec @cspexecutionid = @cspexecutionid;
    EXECUTE ops.CSPExecGraphFinalise @cspexecutionid = @cspexecutionid;
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPExecuteSingleItem]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPExecuteSingleItem];
GO

CREATE PROCEDURE [ops].[CSPExecuteSingleItem] @CSPScheduledItemId INT=NULL, @CSPRestartExecutionId INT=NULL
AS
BEGIN
    DECLARE @debug AS BIT = 1;
    DECLARE @debugflag AS INT = 1;
    IF (@CSPRestartExecutionId IS NULL)
        BEGIN
            DECLARE @ParamSeqNo AS INT = 1;
            DECLARE @logString AS VARCHAR (255) = '';
            DECLARE @logTypeCode AS INT = 1;
            DECLARE @cspgraphid AS INT = NULL;
            DECLARE @cspcontextid AS INT = 8;
            DECLARE @CSPGraphName AS VARCHAR (255) = '';
            DECLARE @cspexecutionid AS INT = 0;
            UPDATE ops.CSPNextAdHocGraphId
            SET CSPGraphId = CSPGraphId + 1,
                   @cspgraphid = CSPGraphId + 1;
            SELECT @cspgraphid = CSPGraphId
            FROM ops.CSPNextAdHocGraphId;
            IF (@cspgraphid > -1000000)
                BEGIN
                    SET @logString = 'AdHoc Graph Ids dropped down to Million. Please cleanup the graphids and start again from max negative';
                    EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = NULL, @cspgraphid = @cspgraphid, @cspgraphnodeid = NULL, @csplogtypecode = 3, @csplogstringshort = 'Execute Single Item String', @csplogstringlong = @logString, @csprecordcount = @@ROWCOUNT;
                    THROW 69998, @logString, 1;
                END
            SET @logString = CASE WHEN @cspgraphid BETWEEN -2147483648 AND -1000000 THEN 'Valid GraphId Allocated' ELSE 'Invalid GraphId' END;
            SET @logTypeCode = CASE WHEN @cspgraphid BETWEEN -2147483648 AND -1000000 THEN 1 ELSE 3 END;
            EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = NULL, @cspgraphid = @cspgraphid, @cspgraphnodeid = NULL, @csplogtypecode = @logTypeCode, @csplogstringshort = 'Execute Single Item String', @csplogstringlong = @logString, @csprecordcount = @@ROWCOUNT;
            IF (@logTypeCode = 1)
                BEGIN
                    SET @CSPGraphName = CAST (@CSPScheduledItemId AS VARCHAR (15)) + ' - ' + +CONVERT (VARCHAR, getdate(), 121);
                    INSERT INTO ops.CSPScheduleGraph
                    VALUES (@cspgraphid, 4, @CSPGraphName, 'Automated - Graph generated for Adhoc execution purposes', GETDATE(), NULL, 5);
                END
            EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = NULL, @cspgraphid = @cspgraphid, @cspgraphnodeid = NULL, @csplogtypecode = 1, @csplogstringshort = 'Execute Single Item String', @csplogstringlong = 'New Graph record inserted into ScheduledGraph table', @csprecordcount = @@ROWCOUNT;
            DECLARE @StartGraphNodeId AS INT = NULL;
            DECLARE @EndGraphNodeId AS INT = 0;
            UPDATE ops.CSPNextAdHocGraphNodeId
            SET CSPScheduleGraphNodeId = CSPScheduleGraphNodeId + 1,
                   @StartGraphNodeId = CSPScheduleGraphNodeId + 1;
            SELECT @StartGraphNodeId = CSPScheduleGraphNodeId
            FROM ops.CSPNextAdHocGraphNodeId;
            IF (@StartGraphNodeId > -1000000)
                BEGIN
                    SET @logString = 'AdHoc GraphNode Ids dropped down to Million. Please cleanup the graphids, graphnodeids and start again from max negative';
                    EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = NULL, @cspgraphid = @cspgraphid, @cspgraphnodeid = @StartGraphNodeId, @csplogtypecode = 3, @csplogstringshort = 'Execute Single Item String', @csplogstringlong = @logString, @csprecordcount = @@ROWCOUNT;
                    THROW 69999, @logString, 1;
                END
            SET @logString = CASE WHEN @StartGraphNodeId BETWEEN -2147483648 AND -1000000 THEN 'Valid GraphNodeId Identified' ELSE 'Invalid GraphNodeId' END;
            SET @logTypeCode = CASE WHEN @StartGraphNodeId BETWEEN -2147483648 AND -1000000 THEN 1 ELSE 3 END;
            EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = NULL, @cspgraphid = @cspgraphid, @cspgraphnodeid = NULL, @csplogtypecode = @logTypeCode, @csplogstringshort = 'Execute Single Item String', @csplogstringlong = @logString, @csprecordcount = @@ROWCOUNT;
            INSERT INTO ops.CSPScheduleGraphNode
            SELECT @StartGraphNodeId,
                   CAST (@CSPScheduledItemId AS VARCHAR (15)) + ' - ' + CONVERT (VARCHAR, getdate(), 121),
                   'ScheduledItemId --> ' + CAST (@CSPScheduledItemId AS VARCHAR (15)),
                   @CSPScheduledItemId,
                   getdate(),
                   NULL,
                   5;
            EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = NULL, @cspgraphid = @cspgraphid, @cspgraphnodeid = NULL, @csplogtypecode = 1, @csplogstringshort = 'Execute Single Item String', @csplogstringlong = 'New GraphNode records inserted into ScheduledGraphNode table', @csprecordcount = @@ROWCOUNT;
            INSERT INTO ops.CSPScheduleGraphSegment
            SELECT @cspgraphid,
                   1,
                   1,
                   @StartGraphNodeId,
                   0,
                   CAST (@CSPScheduledItemId AS VARCHAR (15)) + ' - ' + CONVERT (VARCHAR, getdate(), 121),
                   CAST (@CSPScheduledItemId AS VARCHAR (15)) + ' - ' + CONVERT (VARCHAR, getdate(), 121),
                   GETDATE(),
                   NULL,
                   5;
            SELECT 'Segment',
                   *
            FROM ops.CSPScheduleGraphSegment
            WHERE CSPScheduleGraphId = @cspgraphid;
            SELECT 'Node',
                   *
            FROM ops.CSPScheduleGraphNode
            WHERE CSPScheduleGraphNodeId IN (SELECT CSPScheduleGraphNodeFrom
                                              FROM ops.CSPScheduleGraphSegment
                                              WHERE CSPScheduleGraphId = @cspgraphid
                                              UNION SELECT CSPScheduleGraphNodeTo
                                              FROM ops.CSPScheduleGraphSegment
                                              WHERE CSPScheduleGraphId = @cspgraphid);
            SELECT 'Item',
                   *
            FROM ops.CSPScheduledItem
            WHERE CSPScheduledItemId IN (SELECT CSPScheduledItemId
                                          FROM ops.CSPScheduleGraphNode
                                          WHERE CSPScheduleGraphNodeId IN (SELECT CSPScheduleGraphNodeTo
                                                                            FROM ops.CSPScheduleGraphSegment
                                                                            WHERE CSPScheduleGraphId = @cspgraphid));
            EXECUTE [ops].[CSPExecGraphPrep] @cspgraphid = @cspgraphid, @cspcontextid = @cspcontextid;
            SELECT @cspexecutionid = CSPExecutionId
            FROM ops.CSPExecutionGraph
            WHERE CSPGraphId = @cspgraphid
                   AND CSPExecutionStatusFlag = 1;
            SELECT 'Hi ' + replace(USER, 'diy_', '') + ', NOTE -- current EXECUTION ID is --> ',
                   @cspexecutionid;
            EXECUTE [ops].[CSPGraphExec] @cspexecutionid = @cspexecutionid;
            EXECUTE [ops].[CSPExecGraphFinalise] @cspexecutionid = @cspexecutionid;
        END
    IF (@CSPRestartExecutionId IS NOT NULL)
        BEGIN
            SELECT @cspcontextid = CSPContextId,
                   @cspgraphid = CSPGraphId
            FROM ops.CSPExecutionGraph
            WHERE CSPExecutionId = @CSPRestartExecutionId;
            EXECUTE [ops].[CSPExecGraphPrep] @cspgraphid = @cspgraphid, @cspcontextid = @cspcontextid;
            EXECUTE [ops].[CSPGraphExec] @cspexecutionid = @CSPRestartExecutionId;
            EXECUTE [ops].[CSPExecGraphFinalise] @cspexecutionid = @CSPRestartExecutionId;
            IF (SELECT CSPExecutionStatusFlag
                FROM ops.CSPExecutionGraph
                WHERE CSPExecutionId = @CSPRestartExecutionId) < 7
                THROW 56999, 'Execution has failed. Please investigate', 1;
        END
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPGetNextTempGraphid]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPGetNextTempGraphid];
GO

CREATE PROCEDURE [ops].[CSPGetNextTempGraphid] @cspgraphid INT OUTPUT
AS
BEGIN
    UPDATE ops.CSPNextAdHocGraphId
    SET CSPGraphId = CSPGraphId + 1,
           @cspgraphid = CSPGraphId + 1;
    RETURN @cspgraphid;
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPGetNextTempGraphNodeid]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPGetNextTempGraphNodeid];
GO

CREATE PROCEDURE [ops].[CSPGetNextTempGraphNodeid] @NumberOfNodes INT, @StartGraphNodeId INT OUTPUT, @EndGraphNodeId INT OUTPUT
AS
BEGIN
    UPDATE a
    SET CSPScheduleGraphNodeId = CSPScheduleGraphNodeId + @NumberOfNodes,
           @StartGraphNodeId = CSPScheduleGraphNodeId + 1,
           @EndGraphNodeId = CSPScheduleGraphNodeId + @NumberOfNodes
    FROM ops.CSPNextAdHocGraphNodeId AS a;
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPGraphExec]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPGraphExec];
GO

CREATE PROCEDURE [ops].[CSPGraphExec] @cspexecutionid INT
AS
BEGIN
    DECLARE @exnode AS INT = 0;
    DECLARE @totnodes AS INT = 0;
    DECLARE @exNodeType AS INT = 0;
    DECLARE @cspgraphid AS INT = 0;
    DECLARE @cspcontextid AS INT = 0;
    DECLARE @debugflag AS BIT = 1;
    SELECT @totnodes = TotalNodesToExecute,
           @exnode = GraphNodeToExecute
    FROM (SELECT count(*) AS TotalNodesToExecute
            FROM ops.CSPExecutionLiveList
            WHERE CSPExecutionId = @cspexecutionid
                   AND CSPExecutionStatusFlag = 0) AS a
           LEFT OUTER JOIN (SELECT CSPScheduleGraphNode AS GraphNodeToExecute
            FROM ops.CSPExecutionLiveList
            WHERE rno = (SELECT min(rno)
                          FROM ops.CSPExecutionLiveList
                          WHERE CSPExecutionId = @cspexecutionid
                                 AND CSPExecutionStatusFlag = 0)
                   AND CSPExecutionId = @cspexecutionid
                   AND CSPExecutionStatusFlag = 0) AS b
           ON 1 = 1;
    SELECT @cspgraphid = CSPGraphId,
           @cspcontextid = CSPContextId
    FROM CSPExecutionGraph
    WHERE CSPExecutionId = @cspexecutionid;
    SELECT @exNodeType = a.CSPScheduledItemTypeId
    FROM ops.CSPScheduledItem AS a, ops.CSPScheduleGraphNode AS b
    WHERE b.CSPScheduleGraphNodeId = @exnode
           AND b.CSPScheduledItemId = a.CSPScheduledItemId;
    IF (@exNodeType = 0)
        EXECUTE [ops].CSPStreamLogger @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @exnode, @csplogtypecode = 4, @csplogstringshort = 'Critical Failure', @csplogstringlong = 'CspScheduledItem Record Entry is missing for Node -->', @csprecordcount = @exnode;
    IF (@debugflag = 1)
        SELECT 'Ready to Loop through nodes';
    WHILE (@exnode IS NOT NULL
           AND @exNodeType <> 0)
        BEGIN
            SELECT @exNodeType = a.CSPScheduledItemTypeId
            FROM ops.CSPScheduledItem AS a, ops.CSPScheduleGraphNode AS b
            WHERE b.CSPScheduleGraphNodeId = @exnode
                   AND b.CSPScheduledItemId = a.CSPScheduledItemId;
            IF (@exNodeType = 1)
                EXECUTE [ops].[CSPExecGraphNodeTypeGraph] @cspexecutionid = @cspexecutionid, @cspgraphnodeid = @exnode;
            IF (@exNodeType = 7)
                EXECUTE [ops].[CSPExecGraphNodeTypeSQL] @cspexecutionid = @cspexecutionid, @cspgraphnodeid = @exnode;
            IF (@exNodeType = 0)
                EXECUTE [ops].CSPStreamLogger @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @exnode, @csplogtypecode = 4, @csplogstringshort = 'Critical Failure', @csplogstringlong = 'CspScheduledItem Record Entry is missing for Node -->', @csprecordcount = @exnode;
            EXECUTE [ops].[CSPExecGraphProgress] @cspexecutionid = @cspexecutionid;
            IF (@debugflag = 1)
                SELECT 'out of CSPExecGraphProgress';
            SELECT @totnodes = TotalNodesToExecute,
                   @exnode = GraphNodeToExecute
            FROM (SELECT count(*) AS TotalNodesToExecute
                    FROM ops.CSPExecutionLiveList
                    WHERE CSPExecutionId = @cspexecutionid
                           AND CSPExecutionStatusFlag = 0) AS a
                   LEFT OUTER JOIN (SELECT CSPScheduleGraphNode AS GraphNodeToExecute
                    FROM ops.CSPExecutionLiveList
                    WHERE rno = (SELECT min(rno)
                                  FROM ops.CSPExecutionLiveList
                                  WHERE CSPExecutionId = @cspexecutionid
                                         AND CSPExecutionStatusFlag = 0)
                           AND CSPExecutionId = @cspexecutionid
                           AND CSPExecutionStatusFlag = 0) AS b
                   ON 1 = 1;
        END
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CspInsertScheduledGraphSegment]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CspInsertScheduledGraphSegment];
GO

CREATE PROCEDURE [ops].[CspInsertScheduledGraphSegment] @graphid INT, @GraphNodeFrom INT, @GraphNodeTo INT, @SegmentName VARCHAR (100), @SegmentDescription VARCHAR (100)
AS
BEGIN
    DECLARE @SegmentSeqNo AS INT = 0;
    IF (SELECT count(*)
        FROM ops.CSPScheduleGraphSegment
        WHERE CSPScheduleGraphId = @graphid
               AND @GraphNodeFrom = CSPScheduleGraphNodeFrom
               AND CSPScheduleGraphNodeTo = @GraphNodeTo) > 0
        THROW 61000, 'Segment Exists already', 1;
    IF (SELECT count(*)
        FROM ops.CSPScheduleGraphNode
        WHERE CSPScheduleGraphNodeId IN (@GraphNodeFrom, @GraphNodeTo)) <> 2
        THROW 61000, 'Nodes are missing', 1;
    SELECT @SegmentSeqNo = max(CSPScheduleGraphSegmentId)
    FROM ops.CSPScheduleGraphSegment
    WHERE CSPScheduleGraphId = @graphid;
    IF (@SegmentSeqNo IS NULL)
        SET @SegmentSeqNo = 1;
    INSERT INTO ops.CSPScheduleGraphSegment
    VALUES (@graphid, @SegmentSeqNo, 1, @GraphNodeFrom, @GraphNodeTo, @SegmentName, @SegmentDescription, getdate(), NULL, 7);
    SELECT *
    FROM ops.CSPScheduleGraphSegment
    WHERE CSPScheduleGraphId = @graphid
           AND @GraphNodeFrom = CSPScheduleGraphNodeFrom
           AND CSPScheduleGraphNodeTo = @GraphNodeTo;
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPInsertScheduledItemString]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPInsertScheduledItemString];
GO

CREATE PROCEDURE [ops].[CSPInsertScheduledItemString] @ScheduledItemId INT, @ItemName NVARCHAR (255), @ItemDesc NVARCHAR (255), @SqlString NVARCHAR (MAX)
AS
BEGIN
    DECLARE @CspClientId AS INT = 7;
    DECLARE @ScriptClassTypeCode AS INT = 2;
    DECLARE @ScriptClassType AS NVARCHAR (10) = 'ETL';
    SELECT @ScriptClassTypeCode = CASE WHEN @ScriptClassType = 'Ops' THEN 1 WHEN @ScriptClassType = 'ETL' THEN 2 WHEN @ScriptClassType = 'Lens' THEN 3 ELSE 0 END;
    IF (SELECT COUNT(*)
        FROM ops.CSPScheduledItemString
        WHERE CSPScheduledItemId = @ScheduledItemId
               AND CSPScheduledItemCurrentFlag = 1) = 0
        BEGIN
            SELECT *
            FROM ops.CSPScheduledItemString
            WHERE CSPScheduledItemId = @ScheduledItemId
                   AND CSPScheduledItemCurrentFlag = 1;
            SELECT *
            FROM ops.CSPScheduledItem
            WHERE CSPScheduledItemId = @ScheduledItemId;
            DELETE ops.CSPScheduledItemString
            WHERE CSPScheduledItemId = @ScheduledItemId;
            DELETE ops.CSPScheduledItem
            WHERE CSPScheduledItemId = @ScheduledItemId;
            INSERT INTO ops.CSPScheduledItem
            VALUES (@ScheduledItemId, 7, @ItemName, @ItemDesc, getdate(), NULL, @CspClientId, @ScheduledItemId, @ScriptClassTypeCode);
            INSERT INTO ops.CSPScheduledItemString
            VALUES (@ScheduledItemId, @SqlString, 1, 1, 1, getdate(), NULL, @CspClientId);
            SELECT *
            FROM ops.CSPScheduledItemString
            WHERE CSPScheduledItemId = @ScheduledItemId
                     AND CSPScheduledItemCurrentFlag = 1
            ORDER BY 1;
            SELECT *
            FROM ops.CSPScheduledItem
            WHERE CSPScheduledItemId = @ScheduledItemId;
            IF (SELECT count(*)
                FROM ops.CSPScheduleGraphNode
                WHERE CSPScheduleGraphNodeId = @ScheduledItemId) = 0
                BEGIN
                    INSERT INTO ops.CSPScheduleGraphNode
                    SELECT CSPScheduledItemId,
                           CSPScheduledItemName,
                           CSPScheduledItemDescription,
                           CSPScheduledItemId,
                           getdate(),
                           NULL,
                           7
                    FROM ops.CSPScheduledItem
                    WHERE CSPScheduledItemId IN (@ScheduledItemId);
                END
            ELSE THROW 61000, 'Scheduled Node already populated. Please use Update if you want to update', 1;
        END
    ELSE BEGIN
            THROW 61000, 'Scheduled Item ID already populated. Please use Update if you want to update', 1;
        END
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CspLcTestProcessor]
--  WARNING: one diagnostic block below calls ops.cspGetFailedLCLTRecordsByGraphId,
--  which does not exist. This creates fine but fails if that branch runs.
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CspLcTestProcessor];
GO

CREATE PROCEDURE [ops].[CspLcTestProcessor] @contextid INT=0, @graphid INT=0, @GraphNodeId INT=0, @ExecutionId INT=0
AS
BEGIN
    DECLARE @rowCount AS INT = 0;
    DECLARE @IsDebug AS BIT = 1;
    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'LC Processing Starting', @csprecordcount = 0;
    IF @graphid <> 0
        BEGIN
            DROP TABLE IF EXISTS #CspLogStreamMetricLeftRight;
            SELECT a.*,
                   b.CSPGraphId AS LeftCSPGraphId,
                   b.CSPGraphNodeId AS LeftCSPGraphNodeId,
                   b.CSPLogStringShort AS LeftCSPLogStringShort,
                   b.CSPLogStringLong AS LeftCSPLogStringLong,
                   c.CSPGraphId AS RightCSPGraphId,
                   c.CSPGraphNodeId AS RightCSPGraphNodeId,
                   c.CSPLogStringShort AS RightCSPLogStringShort,
                   c.CSPLogStringLong AS RightCSPLogStringLong INTO #CspLogStreamMetricLeftRight
            FROM ops.CspLogStreamMetricMeasure AS a, ops.CspLogStreamMetrics AS b, ops.CspLogStreamMetrics AS c
            WHERE a.[CspLogMetricIdLeft] = b.CspLogMetricId
                   AND a.[CspLogMetricIdRight] = c.CspLogMetricId
                   AND a.DeleteDateTime IS NULL
                   AND b.CSPGraphId = @graphid
                   AND b.CSPGraphNodeId = CASE WHEN @GraphNodeId BETWEEN 800 AND 899 THEN b.CSPGraphNodeId ELSE @GraphNodeId END;
            EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'Build #CspLogStreamMetricLeftRight', @csprecordcount = @@ROWCOUNT;
            IF @IsDebug = 1
                SELECT *
                FROM #CspLogStreamMetricLeftRight;
            IF (SELECT count(*)
                FROM #CspLogStreamMetricLeftRight) > 0
                BEGIN
                    DROP TABLE IF EXISTS #CspLogStreamMetricLastExecId;
                    SELECT a.CSPGraphId,
                             max(CSPExecutionId) AS CSPExecutionId INTO #CspLogStreamMetricLastExecId
                    FROM (SELECT CSPGraphId
                              FROM (SELECT LeftCSPGraphId AS CSPGraphId
                                        FROM #CspLogStreamMetricLeftRight
                                        UNION SELECT RightCSPGraphId AS CSPGraphId
                                        FROM #CspLogStreamMetricLeftRight) AS x
                              GROUP BY CSPGraphId) AS a, ops.CSPExecutionGraph AS b
                    WHERE a.CSPGraphId = b.CSPGraphId
                             AND b.CSPExecutionStatusFlag IN (1, 4, 7)
                    GROUP BY a.CSPGraphId;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'Build #CspLogStreamMetricLastExecId', @csprecordcount = @@ROWCOUNT;
                    IF @IsDebug = 1
                        SELECT *
                        FROM #CspLogStreamMetricLastExecId;
                    DROP TABLE IF EXISTS #CspLogStreamMetricLastEntry;
                    SELECT a.CSPGraphId,
                             a.CSPGraphNodeId,
                             a.CSPLogStringShort,
                             a.CSPLogStringLong,
                             c.CSPExecutionId,
                             max(b.CSPLogDateTime) AS CSPLogDateTime INTO #CspLogStreamMetricLastEntry
                    FROM (SELECT CSPGraphId,
                                       CSPGraphNodeId,
                                       CSPLogStringShort,
                                       CSPLogStringLong
                              FROM (SELECT LeftCSPGraphId AS CSPGraphId,
                                               LeftCSPGraphNodeId AS CSPGraphNodeId,
                                               LeftCSPLogStringShort AS CSPLogStringShort,
                                               LeftCSPLogStringLong AS CSPLogStringLong
                                        FROM #CspLogStreamMetricLeftRight
                                        UNION SELECT RightCSPGraphId AS CSPGraphId,
                                               RightCSPGraphNodeId AS CSPGraphNodeId,
                                               RightCSPLogStringShort AS CSPLogStringShort,
                                               RightCSPLogStringLong AS CSPLogStringLong
                                        FROM #CspLogStreamMetricLeftRight) AS x
                              GROUP BY CSPGraphId, CSPGraphNodeId, CSPLogStringShort, CSPLogStringLong) AS a, ops.CSPLogStream AS b, #CspLogStreamMetricLastExecId AS c
                    WHERE b.CSPGraphId = c.CSPGraphId
                             AND b.CSPExecutionId = c.CSPExecutionId
                             AND a.CSPGraphId = b.CSPGraphId
                             AND a.CSPGraphNodeId = b.CSPGraphNodeId
                             AND a.CSPLogStringShort = b.CSPLogStringShort
                             AND a.CSPLogStringLong = b.CSPLogStringLong
                    GROUP BY a.CSPGraphId, a.CSPGraphNodeId, a.CSPLogStringShort, a.CSPLogStringLong, c.CSPExecutionId;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'Build #CspLogStreamMetricLastEntry', @csprecordcount = @@ROWCOUNT;
                    IF @IsDebug = 1
                        SELECT *
                        FROM #CspLogStreamMetricLastEntry;
                    DROP TABLE IF EXISTS #CspLogStreamMetricResults;
                    SELECT c.CspLogMetricIdLeft,
                           c.CspLogMetricIdRight,
                           a.CSPGraphId AS LeftCSPGraphId,
                           a.CSPGraphNodeId AS LeftCSPGraphNodeId,
                           a.CSPExecutionId AS LeftCSPExecutionId,
                           COALESCE (a.CSPRecordCount, 0) AS LeftCSPRecordCount,
                           d.CSPGraphId AS RightCSPGraphId,
                           d.CSPGraphNodeId AS RightCSPGraphNodeId,
                           d.CSPExecutionId AS RightCSPExecutionId,
                           COALESCE (d.CSPRecordCount, 0) AS RightCSPRecordCount,
                           c.FailureThreshold,
                           c.MinRecordCount,
                           c.MeasureRunsToCompare,
                           CAST (0 AS INT) AS SuccessFlag INTO #CspLogStreamMetricResults
                    FROM ops.CSPLogStream AS a, #CspLogStreamMetricLastEntry AS b, #CspLogStreamMetricLeftRight AS c, ops.CSPLogStream AS d, #CspLogStreamMetricLastEntry AS e
                    WHERE a.CSPGraphId = b.CSPGraphId
                           AND a.CSPExecutionId = b.CSPExecutionId
                           AND a.CSPLogDateTime = b.CSPLogDateTime
                           AND a.CSPLogStringShort = b.CSPLogStringShort
                           AND a.CSPLogStringLong = b.CSPLogStringLong
                           AND a.CSPGraphId = c.LeftCSPGraphId
                           AND a.CSPGraphNodeId = c.LeftCSPGraphNodeId
                           AND a.CSPLogStringShort = c.LeftCSPLogStringShort
                           AND a.CSPLogStringLong = c.LeftCSPLogStringLong
                           AND d.CSPGraphId = e.CSPGraphId
                           AND d.CSPExecutionId = e.CSPExecutionId
                           AND d.CSPLogDateTime = e.CSPLogDateTime
                           AND d.CSPLogStringShort = e.CSPLogStringShort
                           AND d.CSPLogStringLong = e.CSPLogStringLong
                           AND d.CSPGraphId = c.RightCSPGraphId
                           AND d.CSPGraphNodeId = c.RightCSPGraphNodeId
                           AND d.CSPLogStringShort = c.RightCSPLogStringShort
                           AND d.CSPLogStringLong = c.RightCSPLogStringLong;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'Build #CspLogStreamMetricResults', @csprecordcount = @@ROWCOUNT;
                    IF @IsDebug = 1
                        SELECT *
                        FROM #CspLogStreamMetricResults;
                    UPDATE #CspLogStreamMetricResults
                    SET SuccessFlag = 1
                    WHERE LeftCSPRecordCount IS NULL
                           AND RightCSPRecordCount IS NULL;
                    SET @rowCount = @@ROWCOUNT;
                    IF (@rowCount > 0)
                        EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'Left and Right Metrics are Nulls - Test Ignored', @csprecordcount = @rowCount;
                    UPDATE #CspLogStreamMetricResults
                    SET SuccessFlag = 1
                    WHERE LeftCSPRecordCount = 0
                           AND RightCSPRecordCount = 0
                           AND COALESCE (MinRecordCount, 0) = 0;
                    SET @rowCount = @@ROWCOUNT;
                    IF (@rowCount > 0)
                        EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'Left and Right Metrics are 0 - Test Ignored', @csprecordcount = @rowCount;
                    UPDATE #CspLogStreamMetricResults
                    SET SuccessFlag = -1
                    WHERE RightCSPRecordCount IS NULL
                           AND SuccessFlag = 0;
                    SET @rowCount = @@ROWCOUNT;
                    IF (@rowCount > 0)
                        EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 3, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'Missing Right Metric - Test Failed', @csprecordcount = @rowCount;
                    UPDATE #CspLogStreamMetricResults
                    SET SuccessFlag = -1
                    WHERE LeftCSPRecordCount = 0
                           AND RightCSPRecordCount <> 0
                           AND SuccessFlag = 0;
                    SET @rowCount = @@ROWCOUNT;
                    IF (@rowCount > 0)
                        EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 3, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'Left Metric is 0 but Right Metric GT 0 - Test Failed', @csprecordcount = @rowCount;
                    UPDATE #CspLogStreamMetricResults
                    SET SuccessFlag = -1
                    WHERE LeftCSPRecordCount <> 0
                           AND RightCSPRecordCount = 0
                           AND SuccessFlag = 0;
                    SET @rowCount = @@ROWCOUNT;
                    IF (@rowCount > 0)
                        EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 3, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'Left Metric GT 0 but Right Metric = 0 - Test Failed', @csprecordcount = @rowCount;
                    UPDATE #CspLogStreamMetricResults
                    SET SuccessFlag = CASE WHEN abs(1 - ((1.00 * LeftCSPRecordCount) / (1.00 * RightCSPRecordCount))) > FailureThreshold THEN 0 ELSE 1 END
                    WHERE SuccessFlag = 0
                           AND RightCSPRecordCount > 0;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'Metrics Evaluated', @csprecordcount = @@ROWCOUNT;
                    UPDATE #CspLogStreamMetricResults
                    SET SuccessFlag = 0
                    WHERE LeftCSPRecordCount < COALESCE (MinRecordCount, 0);
                    SET @rowCount = @@ROWCOUNT;
                    IF (@rowCount > 0)
                        EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 3, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'Left Metric Less than requirement minimum volume - Test Failed', @csprecordcount = @rowCount;
                    DECLARE @LcExpectedCount AS INT = 0;
                    DECLARE @LcDerivedCount AS INT = 0;
                    DECLARE @LcResultCount AS INT = 0;
                    SELECT @LcExpectedCount = count(*)
                    FROM ops.CspLogStreamMetricMeasure AS a, ops.CspLogStreamMetrics AS b
                    WHERE a.CspLogMetricIdLeft = b.CspLogMetricId
                           AND b.CSPGraphId = @graphid
                           AND b.CSPGraphNodeId = CASE WHEN @GraphNodeId BETWEEN 800 AND 899 THEN b.CSPGraphNodeId ELSE @GraphNodeId END
                           AND a.CspLogMetricIdRight > 0
                           AND a.DeleteDateTime IS NULL;
                    SELECT @LcDerivedCount = count(*)
                    FROM #CspLogStreamMetricResults;
                    SET @LcResultCount = @LcExpectedCount - @LcDerivedCount;
                    IF (@LcResultCount <> 0)
                        EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 3, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'Left Metrics missing from Comparison. Run cspGetMissingLCLTRecordsByGraphId to find the missing elements in Logstream.', @csprecordcount = @LcResultCount;
                    UPDATE ops.CspLogStreamMetricResults
                    SET LiveRecordFlag = 0
                    WHERE LeftCSPGraphId = @graphid
                           AND LeftCSPExecutionId = @ExecutionId
                           AND LCLTFlag = 'LC';
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'Old LC Results removed from ops.CspLogStreamMetricResults', @csprecordcount = @LcDerivedCount;
                    INSERT INTO ops.CspLogStreamMetricResults (CspMetricLogDateTime, CspLogMetricIdLeft, CspLogMetricIdRight, LeftCSPGraphId, LeftCSPGraphNodeId, LeftCSPExecutionId, LeftCSPRecordCount, RightCSPGraphId, RightCSPGraphNodeId, RightCSPExecutionId, RightCSPRecordCount, FailureThreshold, SuccessFlag, LiveRecordFlag, LCLTFlag)
                    SELECT getdate() AS CspMetricLogDateTime,
                           CspLogMetricIdLeft,
                           CspLogMetricIdRight,
                           LeftCSPGraphId,
                           LeftCSPGraphNodeId,
                           LeftCSPExecutionId,
                           LeftCSPRecordCount,
                           RightCSPGraphId,
                           RightCSPGraphNodeId,
                           RightCSPExecutionId,
                           RightCSPRecordCount,
                           FailureThreshold,
                           SuccessFlag,
                           1,
                           'LC'
                    FROM #CspLogStreamMetricResults;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'LC Results written out to ops.CspLogStreamMetricResults', @csprecordcount = @LcDerivedCount;
                    IF (SELECT count(*)
                        FROM [ops].[cspGetFailedLCLTRecordsByGraphId](@graphid)
                        WHERE LCLTFlag = 'LC') > 0
                        EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 3, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'Metrics Failed Comparison. Run cspGetFailedLCLTRecordsByGraphId to find the failures', @csprecordcount = @LcResultCount;
                END
            ELSE EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'No LC tests configured', @csprecordcount = 0;
        END
    ELSE EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 3, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'Graph ID is 0. Processing Aborted', @csprecordcount = 0;
    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LC', @csplogstringlong = 'LC Processing Complete', @csprecordcount = 0;
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPLoadMetaData]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPLoadMetaData];
GO

CREATE proc [ops].[CSPLoadMetaData] @cspexecutionid int,
  @loadfilename varchar(255),
 @LoadReadRecCount bigint = 0,
 @LoadInsertRecCount bigint = 0,
 @LoadErrorCode int = null,
 @LoadErrorMessage varchar(max) = null,
 @LoadStatusFlag tinyint
as Begin /* LoadStatusFlag - 1 Started - 2 Failed - 3 Abandoned - 4 Restart Requested - 5 Ended Successfully New Universal Status Codes -- rewrite the below to these codes 0 Does not Exist 1 Allocated 2 Executing 3 Stopped 4 Failed 5 Restarted 6 Abandoned 7 Completed */ /* TODO - @CSPExecutionId to be declared and defined here */
   declare @ExistingLoadStatusFlag tinyint = 0 ;
  declare @LatestLoggedDateTime Datetime2(7) ;
 declare @errorMessage nVarchar(255) = 'Load of ' + @loadfilename + ' in Progress. Cannot Start another load';
  declare @readFromFile nVarchar(255) = '' ;
 declare @loadToFile nVarchar(255) = '' ;
   /* Check if an existing load is progressing Fix TODO - If a previous load is progressing, return failure and make the ADF pipeline Fail - If a previous load has failed or completed, accept the Load request to progress */
 select @ExistingLoadStatusFlag = LoadStatusFlag,
   @LatestLoggedDateTime = LatestLoggedDateTime
  from ops.CSPLoadLog a,
   (select LoadFileName, max(LogDateTime) as LatestLoggedDateTime
     from ops.CSPLoadLog
   where LoadFileName = @loadfilename
   group by LoadFileName) b
 where a.LoadFileName = b.LoadFileName
 and a.LogDateTime = b.LatestLoggedDateTime ;
 if @ExistingLoadStatusFlag in (0,3,5) and @LoadStatusFlag in (1) /* no load in progress so start load - old load if any has been abandoned or successfully completed */
   insert into ops.CSPLoadLog (LogDateTime, LoadFileName, LoadStartDateTime, LoadStatusFlag, CSPExecutionId)
      values (Getdate(), @loadfilename, getdate(), 1, @cspexecutionid) ;
    if @ExistingLoadStatusFlag in (1,4) and @LoadStatusFlag in (2,3,5) /* Load in Progress Failed Update Status */
   update ops.CSPLoadLog
    set LoadEndDateTime = Getdate(),
     LoadReadRecordCount = @LoadReadRecCount,
     LoadInsertRecordCount = case when @LoadStatusFlag = 5 then @LoadInsertRecCount else 0 end,
     LoadErrorCode = @LoadErrorCode,
     LoadErrorMessage= @LoadErrorMessage,
      LoadStatusFlag = @LoadStatusFlag
    Where LogDateTime = @LatestLoggedDateTime
   and LoadFileName = @loadfilename
   and LoadStatusFlag = @ExistingLoadStatusFlag ;
   /* To insert into Logstream as well along with loadlog -- 11/10/2022 - V & T -- Start */
   if @LoadStatusFlag = 5 /* Load successful insert to log stream */
  Begin
   Select @readFromFile = CONCAT('Read From ', @loadfilename)
     exec [ops].[CSPStreamLogger] @cspcontextid = 1, @cspexecutionid = @cspexecutionid, @cspgraphid = -1, @cspgraphnodeid = -1,
     @csplogtypecode = 1,
    @csplogstringshort = 'Read From File',
    @csplogstringlong = @readFromFile,
    @csprecordcount = @LoadReadRecCount ;
     Select @loadToFile = CONCAT('Load To ', @loadfilename)
        exec [ops].[CSPStreamLogger] @cspcontextid = 1, @cspexecutionid = @cspexecutionid, @cspgraphid = -1, @cspgraphnodeid = -1,
     @csplogtypecode = 1,
   @csplogstringshort = 'Load To SRC',
    @csplogstringlong = @loadToFile,
   @csprecordcount = @LoadInsertRecCount ;
  End /* To insert into Logstream as well along with loadlog -- 11/10/2022 - V & T -- End */
   if @ExistingLoadStatusFlag in (4) and @LoadStatusFlag in (1) /* Restart to Progress */
   exec [ops].[CSPStreamLogger] @cspcontextid = 1,
     @cspexecutionid = 1,
     @cspgraphid = -1,
     @cspgraphnodeid = -2,
     @csplogtypecode = 1, /* Information */ @csplogstringshort = 'File Load Restart',
     @csplogstringlong = @loadfilename ;
     if @ExistingLoadStatusFlag = 2 and @LoadStatusFlag in (1,4) /* Last Load Failed / Restart Requested usually manually or by the automated Graph - Do NOT ACCEPT a fresh start while old failures are in place */
   update ops.CSPLoadLog
    set LoadStartDateTime = Getdate(),
     LoadStatusFlag = 4
   Where LogDateTime = @LatestLoggedDateTime
   and LoadFileName = @loadfilename
   and LoadStatusFlag = 2 ;
 if @ExistingLoadStatusFlag = 1 and @LoadStatusFlag = 1 /* File Load in Progress - Can't start another one - Fail and Stop Progress */
       Throw 51001, @errorMessage , 1;
  End
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CspLtTestProcessor]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CspLtTestProcessor];
GO

CREATE PROCEDURE [ops].[CspLtTestProcessor] @contextid INT=0, @graphid INT=0, @GraphNodeId INT=0, @ExecutionId INT=0
AS
BEGIN
    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'LT Processing Starting', @csprecordcount = 0;
    IF @graphid <> 0
        BEGIN
            DROP TABLE IF EXISTS #CspLogStreamMetricLeft;
            SELECT a.*,
                   b.CSPGraphId AS LeftCSPGraphId,
                   b.CSPGraphNodeId AS LeftCSPGraphNodeId,
                   b.CSPLogStringShort AS LeftCSPLogStringShort,
                   b.CSPLogStringLong AS LeftCSPLogStringLong INTO #CspLogStreamMetricLeft
            FROM ops.CspLogStreamMetricMeasure AS a, ops.CspLogStreamMetrics AS b
            WHERE a.[CspLogMetricIdLeft] = b.CspLogMetricId
                   AND a.[CspLogMetricIdRight] = 0
                   AND a.DeleteDateTime IS NULL
                   AND b.CSPGraphId = @graphid
                   AND b.CSPGraphNodeId = CASE WHEN @GraphNodeId BETWEEN 800 AND 899 THEN b.CSPGraphNodeId ELSE @GraphNodeId END;
            EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Build #CspLogStreamMetricLeft', @csprecordcount = @@ROWCOUNT;
            IF (SELECT count(*)
                FROM #CspLogStreamMetricLeft) > 0
                BEGIN
                    DROP TABLE IF EXISTS #CspLogStreamMetricLastExecId;
                    SELECT * INTO #CspLogStreamMetricLastExecId
                    FROM (SELECT a.CSPGraphId,
                                   CSPExecutionId,
                                   row_number() OVER (PARTITION BY a.CSPGraphId ORDER BY b.CSPExecutionId DESC) AS ExecutionSeqNo,
                                   MeasureRunsToCompare
                            FROM (SELECT CSPGraphId,
                                             MeasureRunsToCompare
                                    FROM (SELECT LeftCSPGraphId AS CSPGraphId,
                                                       max(MeasureRunsToCompare) AS MeasureRunsToCompare
                                              FROM #CspLogStreamMetricLeft
                                              GROUP BY LeftCSPGraphId) AS x
                                    GROUP BY CSPGraphId, MeasureRunsToCompare) AS a, ops.CSPExecutionGraph AS b
                            WHERE a.CSPGraphId = b.CSPGraphId
                                   AND b.CSPExecutionStatusFlag IN (1, 4, 7)) AS a
                    WHERE ExecutionSeqNo <= MeasureRunsToCompare;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Build #CspLogStreamMetricLastExecId', @csprecordcount = @@ROWCOUNT;
                    DROP TABLE IF EXISTS #CspLogStreamMetricLastEntry;
                    SELECT a.CSPGraphId,
                             a.CSPGraphNodeId,
                             a.CSPLogStringShort,
                             a.CSPLogStringLong,
                             c.CSPExecutionId,
                             c.ExecutionSeqNo,
                             max(b.CSPLogDateTime) AS CSPLogDateTime INTO #CspLogStreamMetricLastEntry
                    FROM (SELECT CSPGraphId,
                                       CSPGraphNodeId,
                                       CSPLogStringShort,
                                       CSPLogStringLong
                              FROM (SELECT LeftCSPGraphId AS CSPGraphId,
                                               LeftCSPGraphNodeId AS CSPGraphNodeId,
                                               LeftCSPLogStringShort AS CSPLogStringShort,
                                               LeftCSPLogStringLong AS CSPLogStringLong
                                        FROM #CspLogStreamMetricLeft) AS x
                              GROUP BY CSPGraphId, CSPGraphNodeId, CSPLogStringShort, CSPLogStringLong) AS a, ops.CSPLogStream AS b, #CspLogStreamMetricLastExecId AS c
                    WHERE b.CSPGraphId = c.CSPGraphId
                             AND b.CSPExecutionId = c.CSPExecutionId
                             AND a.CSPGraphId = b.CSPGraphId
                             AND a.CSPGraphNodeId = b.CSPGraphNodeId
                             AND a.CSPLogStringShort = b.CSPLogStringShort
                             AND a.CSPLogStringLong = b.CSPLogStringLong
                    GROUP BY a.CSPGraphId, a.CSPGraphNodeId, a.CSPLogStringShort, a.CSPLogStringLong, c.CSPExecutionId, c.ExecutionSeqNo;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Build #CspLogStreamMetricLastEntry', @csprecordcount = @@ROWCOUNT;
                    DROP TABLE IF EXISTS #CspLogStreamMetricResultsByExecution;
                    SELECT c.CspLogMetricIdLeft,
                           a.CSPGraphId AS LeftCSPGraphId,
                           a.CSPGraphNodeId AS LeftCSPGraphNodeId,
                           a.CSPExecutionId AS LeftCSPExecutionId,
                           COALESCE (a.CSPRecordCount, 0) AS LeftCSPRecordCount,
                           c.FailureThreshold,
                           b.ExecutionSeqNo,
                           CAST (0 AS INT) AS SuccessFlag INTO #CspLogStreamMetricResultsByExecution
                    FROM ops.CSPLogStream AS a, #CspLogStreamMetricLastEntry AS b, #CspLogStreamMetricLeft AS c
                    WHERE a.CSPGraphId = b.CSPGraphId
                           AND a.CSPExecutionId = b.CSPExecutionId
                           AND a.CSPLogDateTime = b.CSPLogDateTime
                           AND a.CSPLogStringShort = b.CSPLogStringShort
                           AND a.CSPLogStringLong = b.CSPLogStringLong
                           AND a.CSPGraphId = c.LeftCSPGraphId
                           AND a.CSPGraphNodeId = c.LeftCSPGraphNodeId
                           AND a.CSPLogStringShort = c.LeftCSPLogStringShort
                           AND a.CSPLogStringLong = c.LeftCSPLogStringLong;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Build #CspLogStreamMetricResults', @csprecordcount = @@ROWCOUNT;
                    CREATE TABLE #LtValidationRoutineResults (
                        CspLogMetricId INT,
                        ValidationResult INT,
                        ValidationRoutineId INT );
                    DROP TABLE IF EXISTS #ValRtn1_a;
                    SELECT a.CspLogMetricIdLeft,
                             a.ExecutionSeqNo,
                             a.LeftCSPRecordCount - b.LeftCSPRecordCount AS VolDiff INTO #ValRtn1_a
                    FROM #CspLogStreamMetricResultsByExecution AS a, #CspLogStreamMetricResultsByExecution AS b
                    WHERE a.ExecutionSeqNo + 1 = b.ExecutionSeqNo
                             AND a.CspLogMetricIdLeft = b.CspLogMetricIdLeft
                             AND a.ExecutionSeqNo > 1
                    ORDER BY a.ExecutionSeqNo;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Build #ValRtn1_a', @csprecordcount = @@ROWCOUNT;
                    DROP TABLE IF EXISTS #ValRtn1_b;
                    SELECT a.CspLogMetricIdLeft,
                             a.ExecutionSeqNo,
                             a.LeftCSPRecordCount - b.LeftCSPRecordCount AS VolDiff INTO #ValRtn1_b
                    FROM #CspLogStreamMetricResultsByExecution AS a, #CspLogStreamMetricResultsByExecution AS b
                    WHERE a.ExecutionSeqNo + 1 = b.ExecutionSeqNo
                             AND a.CspLogMetricIdLeft = b.CspLogMetricIdLeft
                             AND a.ExecutionSeqNo = 1
                    ORDER BY a.ExecutionSeqNo;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Build #ValRtn1_b', @csprecordcount = @@ROWCOUNT;
                    INSERT INTO #LtValidationRoutineResults
                    SELECT a.CspLogMetricIdLeft,
                           CASE WHEN oldval >= newval THEN 1 ELSE 0 END,
                           1 AS ValidationRoutineId
                    FROM (SELECT CspLogMetricIdLeft,
                                     avg(VolDiff) AS oldval
                            FROM #ValRtn1_a
                            GROUP BY CspLogMetricIdLeft) AS a, (SELECT CspLogMetricIdLeft,
                                                                       VolDiff AS newval
                                                                FROM #ValRtn1_b) AS b
                    WHERE a.CspLogMetricIdLeft = b.CspLogMetricIdLeft;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Insert Local Results into #LtValidationRoutineResults', @csprecordcount = @@ROWCOUNT;
                    DROP TABLE IF EXISTS #ValRtn2_a;
                    SELECT CspLogMetricIdLeft,
                             avg(LeftCSPRecordCount) AS AvgCount,
                             max(LeftCSPRecordCount) AS MaxCount,
                             min(LeftCSPRecordCount) AS MinCount,
                             STDEV(LeftCSPRecordCount) AS StdDevCount INTO #ValRtn2_a
                    FROM #CspLogStreamMetricResultsByExecution
                    WHERE ExecutionSeqNo <> 1
                    GROUP BY CspLogMetricIdLeft;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Build #ValRtn2_a', @csprecordcount = @@ROWCOUNT;
                    DROP TABLE IF EXISTS #ValRtn2_b;
                    SELECT CspLogMetricIdLeft,
                           LeftCSPRecordCount INTO #ValRtn2_b
                    FROM #CspLogStreamMetricResultsByExecution
                    WHERE ExecutionSeqNo = 1;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Build #ValRtn2_b', @csprecordcount = @@ROWCOUNT;
                    INSERT INTO #LtValidationRoutineResults
                    SELECT a.CspLogMetricIdLeft,
                           CASE WHEN LeftCSPRecordCount < AvgCount THEN 1 ELSE 0 END,
                           2
                    FROM #ValRtn2_a AS a, #ValRtn2_b AS b
                    WHERE a.CspLogMetricIdLeft = b.CspLogMetricIdLeft
                           AND b.LeftCSPRecordCount > 0
                    UNION SELECT a.CspLogMetricIdLeft,
                           CASE WHEN LeftCSPRecordCount BETWEEN (AvgCount - (2 * StdDevCount)) AND (AvgCount + (4 * StdDevCount)) THEN 1 ELSE 0 END,
                           2
                    FROM #ValRtn2_a AS a, #ValRtn2_b AS b
                    WHERE a.CspLogMetricIdLeft = b.CspLogMetricIdLeft
                           AND b.LeftCSPRecordCount > 0
                    UNION SELECT a.CspLogMetricIdLeft,
                           CASE WHEN LeftCSPRecordCount BETWEEN MinCount AND MaxCount THEN 1 ELSE 0 END,
                           2
                    FROM #ValRtn2_a AS a, #ValRtn2_b AS b
                    WHERE a.CspLogMetricIdLeft = b.CspLogMetricIdLeft
                           AND b.LeftCSPRecordCount > 0;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Insert Local Results into #LtValidationRoutineResults', @csprecordcount = @@ROWCOUNT;
                    DROP TABLE IF EXISTS #ValRtn3_a;
                    SELECT CspLogMetricIdLeft,
                             avg(LeftCSPRecordCount) AS AvgCount,
                             max(LeftCSPRecordCount) AS MaxCount,
                             min(LeftCSPRecordCount) AS MinCount,
                             STDEV(LeftCSPRecordCount) AS StdDevCount INTO #ValRtn3_a
                    FROM #CspLogStreamMetricResultsByExecution
                    WHERE ExecutionSeqNo BETWEEN 2 AND 7 GROUP BY CspLogMetricIdLeft;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Build #ValRtn3_a', @csprecordcount = @@ROWCOUNT;
                    DROP TABLE IF EXISTS #ValRtn3_b;
                    SELECT CspLogMetricIdLeft,
                             avg(LeftCSPRecordCount) AS AvgCount,
                             max(LeftCSPRecordCount) AS MaxCount,
                             min(LeftCSPRecordCount) AS MinCount,
                             STDEV(LeftCSPRecordCount) AS StdDevCount INTO #ValRtn3_b
                    FROM #CspLogStreamMetricResultsByExecution
                    WHERE ExecutionSeqNo BETWEEN 1 AND 6 GROUP BY CspLogMetricIdLeft;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Build #ValRtn3_b', @csprecordcount = @@ROWCOUNT;
                    INSERT INTO #LtValidationRoutineResults
                    SELECT a.CspLogMetricIdLeft,
                           CASE WHEN abs(1 - (a.AvgCount / b.AvgCount)) < 0.05 THEN 1 ELSE 0 END,
                           3
                    FROM #ValRtn3_a AS a, #ValRtn3_b AS b
                    WHERE a.CspLogMetricIdLeft = b.CspLogMetricIdLeft
                           AND b.AvgCount > 0
                    UNION SELECT a.CspLogMetricIdLeft,
                           CASE WHEN abs(1 - (a.MinCount / b.MinCount)) < 0.05 THEN 1 ELSE 0 END,
                           3
                    FROM #ValRtn3_a AS a, #ValRtn3_b AS b
                    WHERE a.CspLogMetricIdLeft = b.CspLogMetricIdLeft
                           AND b.MinCount > 0
                    UNION SELECT a.CspLogMetricIdLeft,
                           CASE WHEN abs(1 - (a.MaxCount / b.MaxCount)) < 0.05 THEN 1 ELSE 0 END,
                           3
                    FROM #ValRtn3_a AS a, #ValRtn3_b AS b
                    WHERE a.CspLogMetricIdLeft = b.CspLogMetricIdLeft
                           AND b.MaxCount > 0;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Insert Local Results into #LtValidationRoutineResults', @csprecordcount = @@ROWCOUNT;
                    DROP TABLE IF EXISTS #ValRtn4_a;
                    SELECT CspLogMetricIdLeft,
                             sum(LeftCSPRecordCount) AS SumCount INTO #ValRtn4_a
                    FROM #CspLogStreamMetricResultsByExecution
                    WHERE ExecutionSeqNo <> 1
                    GROUP BY CspLogMetricIdLeft;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Build #ValRtn4_a', @csprecordcount = @@ROWCOUNT;
                    DROP TABLE IF EXISTS #ValRtn4_b;
                    SELECT CspLogMetricIdLeft,
                             sum(LeftCSPRecordCount) AS SumCount INTO #ValRtn4_b
                    FROM #CspLogStreamMetricResultsByExecution
                    WHERE ExecutionSeqNo = 1
                    GROUP BY CspLogMetricIdLeft;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Build #ValRtn4_b', @csprecordcount = @@ROWCOUNT;
                    INSERT INTO #LtValidationRoutineResults
                    SELECT a.CspLogMetricIdLeft,
                           CASE WHEN a.SumCount = b.SumCount
                                     AND a.SumCount = 0 THEN 1 ELSE 0 END,
                           4
                    FROM #ValRtn4_a AS a, #ValRtn4_b AS b
                    WHERE a.CspLogMetricIdLeft = b.CspLogMetricIdLeft;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Insert Local Results into #LtValidationRoutineResults', @csprecordcount = @@ROWCOUNT;
                    DECLARE @AlwaysZeroMetrics AS INT = 0;
                    SELECT @AlwaysZeroMetrics = count(*)
                    FROM #LtValidationRoutineResults
                    WHERE ValidationRoutineId = 4
                           AND ValidationResult = 1;
                    IF (@AlwaysZeroMetrics > 0)
                        EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT - Warning', @csplogstringlong = 'Few metrics are always zero. Should these be verified?', @csprecordcount = @AlwaysZeroMetrics;
                    INSERT INTO #LtValidationRoutineResults
                    SELECT CspLogMetricIdLeft,
                             1,
                             5
                    FROM #CspLogStreamMetricResultsByExecution
                    GROUP BY CspLogMetricIdLeft
                    HAVING max(ExecutionSeqNo) <= 6;
                    DECLARE @NewMetrics AS INT = 0;
                    SELECT @NewMetrics = count(*)
                    FROM #LtValidationRoutineResults
                    WHERE ValidationRoutineId = 5
                           AND ValidationResult = 1;
                    IF (@NewMetrics > 0)
                        EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT - Warning', @csplogstringlong = 'New metrics present. Should these be verified manually?', @csprecordcount = @NewMetrics;
                    DROP TABLE IF EXISTS #RegDiffBase;
                    SELECT a.CspLogMetricIdLeft,
                           b.LeftCSPRecordCount,
                           b.ExecutionSeqNo,
                           b.LeftCSPRecordCount - a.LeftCSPRecordCount AS RegDiff INTO #RegDiffBase
                    FROM #CspLogStreamMetricResultsByExecution AS a, #CspLogStreamMetricResultsByExecution AS b
                    WHERE a.ExecutionSeqNo = b.ExecutionSeqNo + 1
                           AND a.CspLogMetricIdLeft = b.CspLogMetricIdLeft;
                    INSERT INTO #LtValidationRoutineResults
                    SELECT a.CspLogMetricIdLeft,
                           CASE WHEN a.RegDiff BETWEEN b.MinRegDiff AND b.MaxRegDiff THEN 1 ELSE 0 END AS SuccessFlag,
                           6
                    FROM (SELECT *
                            FROM #RegDiffBase
                            WHERE ExecutionSeqNo = 1) AS a, (SELECT CspLogMetricIdLeft,
                                                                       max(RegDiff) AS MaxRegDiff,
                                                                       min(RegDiff) AS MinRegDiff
                                                              FROM #RegDiffBase
                                                              WHERE ExecutionSeqNo > 1
                                                              GROUP BY CspLogMetricIdLeft) AS b
                    WHERE a.CspLogMetricIdLeft = b.CspLogMetricIdLeft;
                    DROP TABLE IF EXISTS #LtValidationRoutineResultsSummary;
                    SELECT CspLogMetricId,
                             max(ValidationResult) AS maxResult,
                             sum(ValidationResult) AS sumResult INTO #LtValidationRoutineResultsSummary
                    FROM #LtValidationRoutineResults
                    GROUP BY CspLogMetricId;
                    DROP TABLE IF EXISTS #CspLogStreamMetricResults;
                    SELECT CspLogMetricIdLeft,
                             LeftCSPGraphId,
                             LeftCSPGraphNodeId,
                             LeftCSPExecutionId,
                             LeftCSPRecordCount,
                             FailureThreshold,
                             CAST (0 AS INT) AS SuccessFlag INTO #CspLogStreamMetricResults
                    FROM #CspLogStreamMetricResultsByExecution
                    WHERE LeftCSPExecutionId = @ExecutionId
                    GROUP BY CspLogMetricIdLeft, LeftCSPGraphId, LeftCSPGraphNodeId, LeftCSPExecutionId, LeftCSPRecordCount, FailureThreshold;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Build #CspLogStreamMetricResults', @csprecordcount = @@ROWCOUNT;
                    UPDATE a
                    SET SuccessFlag = maxResult
                    FROM #CspLogStreamMetricResults AS a, #LtValidationRoutineResultsSummary AS b
                    WHERE a.CspLogMetricIdLeft = b.CspLogMetricId;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Metric Results Updated', @csprecordcount = @@ROWCOUNT;
                    DECLARE @LtResultCount AS INT = 0;
                    SELECT @LtResultCount = count(*)
                    FROM #CspLogStreamMetricResults
                    WHERE SuccessFlag < 1;
                    IF (@LtResultCount > 0)
                        EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 3, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Failed LT Tests Left Metric - Test Failed', @csprecordcount = @LtResultCount;
                    DECLARE @LtExpectedCount AS INT = 0;
                    DECLARE @LtDerivedCount AS INT = 0;
                    SET @LtResultCount = 0;
                    SELECT @LtExpectedCount = count(DISTINCT CspLogMetricId)
                    FROM ops.CspLogStreamMetricMeasure AS a, ops.CspLogStreamMetrics AS b
                    WHERE a.CspLogMetricIdLeft = b.CspLogMetricId
                           AND b.CSPGraphId = @graphid
                           AND b.CSPGraphNodeId = CASE WHEN @GraphNodeId BETWEEN 800 AND 899 THEN b.CSPGraphNodeId ELSE @GraphNodeId END
                           AND a.CspLogMetricIdRight = 0
                           AND a.DeleteDateTime IS NULL;
                    SELECT @LtDerivedCount = count(DISTINCT CspLogMetricIdLeft)
                    FROM #CspLogStreamMetricResults;
                    SET @LtResultCount = @LtExpectedCount - @LtDerivedCount;
                    IF (@LtResultCount <> 0)
                        EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 3, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'LT (Left) Metrics missing in Logstream for this current execution', @csprecordcount = @LtResultCount;
                    UPDATE ops.CspLogStreamMetricResults
                    SET LiveRecordFlag = 0
                    WHERE LeftCSPGraphId = @graphid
                           AND LeftCSPGraphNodeId = CASE WHEN @GraphNodeId BETWEEN 800 AND 899 THEN LeftCSPGraphNodeId ELSE @GraphNodeId END
                           AND LeftCSPExecutionId = @ExecutionId
                           AND LCLTFlag = 'LT';
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Old LT Results removed from ops.CspLogStreamMetricResults', @csprecordcount = @@ROWCOUNT;
                    INSERT INTO ops.CspLogStreamMetricResults (CspMetricLogDateTime, CspLogMetricIdLeft, CspLogMetricIdRight, LeftCSPGraphId, LeftCSPGraphNodeId, LeftCSPExecutionId, LeftCSPRecordCount, RightCSPGraphId, RightCSPGraphNodeId, RightCSPExecutionId, RightCSPRecordCount, FailureThreshold, SuccessFlag, LiveRecordFlag, LCLTFlag)
                    SELECT getdate() AS CspMetricLogDateTime,
                           CspLogMetricIdLeft,
                           0,
                           LeftCSPGraphId,
                           LeftCSPGraphNodeId,
                           LeftCSPExecutionId,
                           LeftCSPRecordCount,
                           0,
                           0,
                           0,
                           0,
                           FailureThreshold,
                           SuccessFlag,
                           1,
                           'LT'
                    FROM #CspLogStreamMetricResults
                    WHERE LeftCSPExecutionId = @ExecutionId;
                    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'LT Results written out to ops.CspLogStreamMetricResults', @csprecordcount = @@ROWCOUNT;
                END
            ELSE EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'No LT Tests Configured', @csprecordcount = 0;
        END
    ELSE EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 3, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'Graph ID is 0. Processing Aborted', @csprecordcount = 0;
    EXECUTE ops.CSPStreamLogger @cspcontextid = @contextid, @cspexecutionid = @ExecutionId, @cspgraphid = @graphid, @cspgraphnodeid = @GraphNodeId, @csplogtypecode = 1, @csplogstringshort = 'LogStream - LT', @csplogstringlong = 'LT Processing Complete', @csprecordcount = 0;
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPManageGraphExecution]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPManageGraphExecution];
GO

CREATE PROCEDURE [ops].[CSPManageGraphExecution] @cspgraphid INT, @cspcontextid INT, @CSPExecutionControlFlag INT=0, @cspexecutionid INT OUTPUT, @cspgraphstatuscode INT OUTPUT, @replyMessage VARCHAR (100) OUTPUT
AS
BEGIN
    DECLARE @graphStatusFlag AS INT = 0;
    DECLARE @retval AS INT = 0;
    SELECT @cspgraphstatuscode = CSPExecutionStatusFlag
    FROM ops.GetGraphExecutionStatus(@cspgraphid);
    IF (@CSPExecutionControlFlag = 0)
       AND (@cspgraphstatuscode IN (0, 6, 7))
        BEGIN
            EXECUTE ops.CSPStartNewGraphExecution @cspgraphid, @cspcontextid, @retval OUTPUT;
            IF @retval = 0
                SET @replyMessage = 'Starting a new Execution Failed';
        END
    ELSE BEGIN
            IF @cspgraphstatuscode <> 6
                BEGIN
                    SELECT @graphStatusFlag = CASE WHEN @CSPExecutionControlFlag = 1 THEN 3 WHEN @CSPExecutionControlFlag = 2 THEN 4 WHEN @CSPExecutionControlFlag = 3 THEN 5 WHEN @CSPExecutionControlFlag = 4 THEN 6 WHEN @CSPExecutionControlFlag = 5 THEN 7 ELSE 0 END;
                    IF @graphStatusFlag > 0
                        BEGIN
                            EXECUTE ops.CSPSetGraphExecutionStatus @cspgraphid, @graphStatusFlag, @retval OUTPUT;
                            IF @retval = 0
                                SET @replyMessage = 'Modifying Execution Failed';
                            IF @retval = 1
                                BEGIN
                                    IF @CSPExecutionControlFlag = 1
                                        SET @replyMessage = 'Stopping Execution Successful';
                                    IF @CSPExecutionControlFlag = 2
                                        SET @replyMessage = 'Execution Marked as Failed';
                                    IF @CSPExecutionControlFlag = 3
                                        SET @replyMessage = 'Restarting Execution Successful';
                                    IF @CSPExecutionControlFlag = 4
                                        SET @replyMessage = 'Abandoning Execution Successful';
                                    IF @CSPExecutionControlFlag = 5
                                        SET @replyMessage = 'Completing Execution Successfully';
                                END
                            IF @CSPExecutionControlFlag = 3
                                UPDATE ops.CSPExecutionGraphNode
                                SET CSPExecutionStatusFlag = 5
                                WHERE CSPExecutionStatusFlag = 4
                                       AND CSPExecutionId = @cspexecutionid;
                        END
                    ELSE SET @replyMessage = 'No restart options Provided. Graph Currently Executing.';
                END
            ELSE SET @replyMessage = 'Graph Abandoned already.';
        END
    SELECT @cspgraphstatuscode = CSPExecutionStatusFlag
    FROM ops.GetGraphExecutionStatus(@cspgraphid);
    SELECT @cspexecutionid = CSPExecutionId
    FROM ops.GetCurrentGraphExecutionId(@cspgraphid);
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPManageMasterGraph]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPManageMasterGraph];
GO

CREATE PROCEDURE [ops].[CSPManageMasterGraph] @cspcontextid INT, @cspgraphid INT, @cspexecutionid INT
AS
BEGIN
    DECLARE @graphPosition AS INT = 0;
    DECLARE @cspgraphstatuscode AS INT = 0;
    DECLARE @logString AS VARCHAR (1024) = '';
    DECLARE @masterGraphId AS INT = 0;
    DECLARE @masterGraphStartPostion AS INT = 0;
    DECLARE @masterGraphEndPostion AS INT = 0;
    SELECT @cspgraphstatuscode = CSPExecutionStatusFlag
    FROM ops.GetGraphExecutionStatus(@cspgraphid);
    SELECT @graphPosition = COALESCE (CSPMasterGraphNodeOrder, 0)
    FROM ops.CSPScheduleMasterGraphNodeList
    WHERE CSPScheduleGraphId = @cspgraphid;
    IF (@graphPosition > 0)
        BEGIN
            SELECT @masterGraphId = CSPMasterGraphId
            FROM ops.CSPScheduleMasterGraphNodeList
            WHERE CSPScheduleGraphId = @cspgraphid;
            SET @logString = 'Graph is Part of MasterGraph --> ' + CAST (@masterGraphId AS VARCHAR (4));
            EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = 0, @csplogtypecode = 1, @csplogstringshort = 'MasterGraph', @csplogstringlong = @logString, @csprecordcount = 0;
            SELECT @masterGraphStartPostion = min(CSPMasterGraphNodeOrder),
                   @masterGraphEndPostion = max(CSPMasterGraphNodeOrder)
            FROM ops.CSPScheduleMasterGraphNodeList
            WHERE CSPMasterGraphId = @masterGraphId;
            IF (@graphPosition = @masterGraphStartPostion)
                BEGIN
                    IF @cspgraphstatuscode = 7
                        UPDATE ops.CSPExecutionMasterGraph
                        SET CSPMasterGraphLastUpdateDateTime = getdate()
                        WHERE CSPMasterExecutionStatusCode NOT IN (6, 7)
                               AND CSPMasterGraphId = @masterGraphId;
                    IF @cspgraphstatuscode = 1
                        BEGIN
                            INSERT INTO ops.CSPExecutionMasterGraph
                            SELECT @masterGraphId,
                                   max(CSPMasterGraphExecutionId) + 1,
                                   getdate(),
                                   NULL,
                                   NULL,
                                   1
                            FROM ops.CSPExecutionMasterGraph
                            WHERE (SELECT count(*)
                                    FROM ops.CSPExecutionMasterGraph
                                    WHERE CSPMasterExecutionStatusCode NOT IN (6, 7)
                                           AND CSPMasterGraphId = @masterGraphId) = 0;
                            UPDATE ops.CSPExecutionMasterGraph
                            SET CSPMasterGraphLastUpdateDateTime = getdate()
                            WHERE CSPMasterExecutionStatusCode NOT IN (6, 7)
                                   AND CSPMasterGraphId = @masterGraphId;
                        END
                END
            IF (@graphPosition = @masterGraphEndPostion)
                BEGIN
                    IF @cspgraphstatuscode = 7
                        UPDATE ops.CSPExecutionMasterGraph
                        SET CSPMasterExecutionStatusCode = 7,
                               CSPMasterGraphEndDateTime = getdate(),
                               CSPMasterGraphLastUpdateDateTime = getdate()
                        WHERE CSPMasterExecutionStatusCode NOT IN (6, 7)
                               AND CSPMasterGraphId = @masterGraphId;
                    IF @cspgraphstatuscode = 1
                        UPDATE ops.CSPExecutionMasterGraph
                        SET CSPMasterGraphLastUpdateDateTime = getdate()
                        WHERE CSPMasterExecutionStatusCode NOT IN (6, 7)
                               AND CSPMasterGraphId = @masterGraphId;
                END
            IF (@graphPosition > @masterGraphStartPostion)
               AND (@graphPosition < @masterGraphEndPostion)
                BEGIN
                    UPDATE ops.CSPExecutionMasterGraph
                    SET CSPMasterGraphLastUpdateDateTime = getdate()
                    WHERE CSPMasterExecutionStatusCode NOT IN (6, 7)
                           AND CSPMasterGraphId = @masterGraphId;
                END
            SET @logString = 'MasterGraph ' + CAST (@masterGraphId AS VARCHAR (5)) + ' Execution State Updated';
            EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = 0, @csplogtypecode = 1, @csplogstringshort = 'MasterGraph', @csplogstringlong = @logString, @csprecordcount = 0;
            WITH nodeid
            AS (SELECT CSPMasterGraphNodeId
                  FROM ops.CSPScheduleMasterGraphNodeList
                  WHERE CSPMasterGraphId = @masterGraphId
                         AND CSPScheduleGraphId = @cspgraphid),
                 masterid
            AS (SELECT CSPMasterGraphExecutionId,
                         CSPMasterGraphId
                  FROM ops.CSPExecutionMasterGraph
                  WHERE CSPMasterExecutionStatusCode < 6
                         AND CSPMasterGraphId = @masterGraphId)
            INSERT INTO ops.CSPExecutionMasterGraphNode
            SELECT CSPMasterGraphId,
                   CSPMasterGraphExecutionId,
                   CSPMasterGraphNodeId,
                   @cspexecutionid
            FROM masterid AS a, nodeid AS b
            WHERE @cspexecutionid NOT IN (SELECT CSPMasterGraphNodeExecutionId
                                           FROM ops.CSPExecutionMasterGraphNode);
        END
    ELSE BEGIN
            EXECUTE [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = 0, @csplogtypecode = 1, @csplogstringshort = 'MasterGraph', @csplogstringlong = 'Graph is Not Part of MasterGraph', @csprecordcount = 0;
        END
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPRemoveExecutionParameters]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPRemoveExecutionParameters];
GO

CREATE PROCEDURE [ops].[CSPRemoveExecutionParameters] @cspcontextid INT=NULL, @cspexecutionid INT=NULL, @cspgraphid INT=NULL, @cspgraphnodeid INT=NULL, @CSPParmName VARCHAR (255)
AS
BEGIN
    DECLARE @logstr AS VARCHAR (1024) = '';
    SELECT @logstr = @CSPParmName + ' = ' + [CSPParmValue]
    FROM ops.CSPExecutionParameters
    WHERE COALESCE (@cspcontextid, 0) = COALESCE ([CSPContextId], 0)
           AND COALESCE (@cspexecutionid, 0) = COALESCE ([CSPExecutionId], 0)
           AND @cspgraphid = [CSPGraphId]
           AND COALESCE (@cspgraphnodeid, 0) = COALESCE ([CSPGraphNodeId], 0)
           AND @CSPParmName = [CSPParmName];
    IF (SELECT count(*)
        FROM ops.CSPExecutionParameters
        WHERE COALESCE (@cspcontextid, 0) = COALESCE ([CSPContextId], 0)
               AND COALESCE (@cspexecutionid, 0) = COALESCE ([CSPExecutionId], 0)
               AND @cspgraphid = [CSPGraphId]
               AND COALESCE (@cspgraphnodeid, 0) = COALESCE ([CSPGraphNodeId], 0)
               AND @CSPParmName = [CSPParmName]) = 1
        BEGIN
            DELETE ops.CSPExecutionParameters
            WHERE COALESCE (@cspcontextid, 0) = COALESCE ([CSPContextId], 0)
                   AND COALESCE (@cspexecutionid, 0) = COALESCE ([CSPExecutionId], 0)
                   AND @cspgraphid = [CSPGraphId]
                   AND COALESCE (@cspgraphnodeid, 0) = COALESCE ([CSPGraphNodeId], 0)
                   AND @CSPParmName = [CSPParmName];
            EXECUTE ops.CSPStreamLogger @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 1, @csplogstringshort = 'Parameter Deleted', @csplogstringlong = @logstr, @csprecordcount = @@ROWCOUNT;
        END
    ELSE BEGIN
            EXECUTE ops.CSPStreamLogger @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 1, @csplogstringshort = 'Parameter Deletion Failed', @csplogstringlong = @logstr, @csprecordcount = 0;
        END
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPSetExecutionParameters]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPSetExecutionParameters];
GO

CREATE PROCEDURE [ops].[CSPSetExecutionParameters] @cspcontextid INT=NULL, @cspexecutionid INT=NULL, @cspgraphid INT=NULL, @cspgraphnodeid INT=NULL, @CSPParmName VARCHAR (255), @CSPParmValue VARCHAR (255)
AS
BEGIN
    DECLARE @isValidParm AS BIT = 0;
    DECLARE @ParmLevel AS INT = 0;
    DECLARE @logstr AS VARCHAR (1024) = @CSPParmName + ' = ' + @CSPParmValue;
    IF @cspgraphnodeid IS NULL
       AND @cspgraphid IS NULL
       AND @cspexecutionid IS NULL
       AND @cspcontextid IS NULL
        BEGIN
            SET @isValidParm = 1;
            SET @ParmLevel = 0;
        END
    IF @cspgraphnodeid IS NOT NULL
       AND @cspgraphid IS NULL
       AND @cspexecutionid IS NULL
       AND @cspcontextid IS NULL
        BEGIN
            SET @isValidParm = 1;
            SET @ParmLevel = 1;
        END
    IF @cspgraphnodeid IS NULL
       AND @cspgraphid IS NOT NULL
       AND @cspexecutionid IS NULL
       AND @cspcontextid IS NULL
        BEGIN
            SET @isValidParm = 1;
            SET @ParmLevel = 2;
        END
    IF @cspgraphnodeid IS NULL
       AND @cspgraphid IS NULL
       AND @cspexecutionid IS NOT NULL
       AND @cspcontextid IS NULL
        BEGIN
            SET @isValidParm = 1;
            SET @ParmLevel = 3;
        END
    IF @cspgraphnodeid IS NULL
       AND @cspgraphid IS NULL
       AND @cspexecutionid IS NULL
       AND @cspcontextid IS NOT NULL
        BEGIN
            SET @isValidParm = 1;
            SET @ParmLevel = 4;
        END
    IF @cspgraphnodeid IS NOT NULL
       AND @cspgraphid IS NOT NULL
       AND @cspexecutionid IS NOT NULL
       AND @cspcontextid IS NOT NULL
        BEGIN
            SET @isValidParm = 1;
            SET @ParmLevel = 5;
        END
    IF @cspgraphnodeid IS NULL
       AND @cspgraphid IS NOT NULL
       AND @cspexecutionid IS NOT NULL
        BEGIN
            SET @isValidParm = 1;
            SET @ParmLevel = 6;
        END
    IF @cspgraphnodeid IS NOT NULL
       AND @cspgraphid IS NOT NULL
       AND @cspexecutionid IS NULL
        BEGIN
            SET @isValidParm = 1;
            SET @ParmLevel = 7;
        END
    IF COALESCE (@CSPParmName, '') = ''
       AND len(@CSPParmName) < 255
        BEGIN
            SET @isValidParm = 0;
            SET @ParmLevel = 0;
        END
    IF len(@CSPParmValue) < 255
        BEGIN
            SET @isValidParm = 1;
        END
    IF @isValidParm > 0
        BEGIN
            INSERT INTO ops.CSPExecutionParameters ([CSPParameterLevelCode], [CSPContextId], [CSPExecutionId], [CSPGraphId], [CSPGraphNodeId], [CSPParmName], [CSPParmValue])
            VALUES (@ParmLevel, @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, @CSPParmName, @CSPParmValue);
            EXECUTE ops.CSPStreamLogger @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 1, @csplogstringshort = 'Parameter Added', @csplogstringlong = @logstr, @csprecordcount = @@ROWCOUNT;
        END
    ELSE BEGIN
            EXECUTE ops.CSPStreamLogger @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 1, @csplogstringshort = 'Parameter Add Failed', @csplogstringlong = @logstr, @csprecordcount = 0;
        END
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CspSetExportTable]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CspSetExportTable];
GO

CREATE proc [ops].[CspSetExportTable] ( @schemaname varchar(10) ,
  @tablename varchar(255) ,
  @ContainerName Varchar(255) = 'exports',
   @FolderName varchar(255) = 'PowerBI',
  @FileName varchar(255) = '',
  @zippedFlag int = 1,
  @delimiterChar varchar(1) = '|',
  @cspexecutionid int = 0 )
AS
BEGIN
 declare @schemaid int = 0;
 declare @errMsg int = 0;
 declare @sqlstr nvarchar(1024) = '' ;
   declare @fileNamelocal nvarchar(1024) = '' ;
   declare @fileNameSuffix nvarchar(1024) = '' ;
   declare @logStrFailure nvarchar(1024) = @schemaname + '.' + @tablename + ' export setup failed' ;
   declare @logStrSuccess nvarchar(1024) = @schemaname + '.' + @tablename + ' export setup successful' ;
     declare @logstr nvarchar(1024) = '';
     /* if called from within a graph collect all graph variables else assign constants */
 declare @cspgraphid
as int = 0;
 declare @cspcontextid as tinyint = 6;
 declare @cspgraphnodeid as int = 0;
   if @cspexecutionid > 0
   Begin -- Get Graph Vars
   select @cspcontextid = CSPContextId,
     @cspgraphid = CSPGraphId
   from ops.CSPExecutionGraph
    where CSPExecutionId = @cspexecutionid ;
   select @cspgraphnodeid = CSPGraphNodeId
    from ops.CSPExecutionGraphNode
    where CSPExecutionId = @cspexecutionid
   and CSPExecutionStatusFlag = 1 ;
  End /* not planned - triggerable / schedulable - To decide if that has to be implemented in ADF or SQL */
 set @logstr = ''
 if @zippedFlag not in (1, 0)
 Begin
  set @zippedFlag = 1 /* default is to zip from now onwards */
     set @logstr += 'Output file is Zipped - Gzip default as of now' /* For future - set this to a code and supply an enumerated list of values - 0 - not zipped, 1 - gzip, 2 - zipdeflate etc - optimal zipping is always suggested */
 End
  if len(coalesce(@delimiterChar,'')) = 0
 Begin
  Set @delimiterChar = ','
    set @logstr += 'Output file has comma (,) as the delimiter as of now'
  End
   if len(coalesce(@delimiterChar,'')) = 1
 Begin
  set @logstr += 'Output file has the delimiter set to --> ' + @delimiterChar + ' as of now'
  End
   if len(coalesce(@delimiterChar,'')) > 1
 Begin
  Set @delimiterChar = ','
    set @logstr += 'Invalid delimiter supplied. Code correction needed for multi char delimiter. Output file has comma (,) as the delimiter as of now.'
  End
   exec [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid,
  @cspexecutionid = @cspexecutionid,
  @cspgraphid = @cspgraphid,
  @cspgraphnodeid = @cspgraphnodeid,
  @csplogtypecode = 1, /* Success */ @csplogstringshort = 'Export Table Setup',
  @csplogstringlong = @logstr
   Set @logstr = '' /* validate if table exists */
 select @schemaid = schema_id from sys.schemas where name in (@schemaname) ;
 if @schemaid = 0
   Begin
    exec [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid,
    @cspexecutionid = @cspexecutionid,
    @cspgraphid = @cspgraphid,
    @cspgraphnodeid = @cspgraphnodeid,
    @csplogtypecode = 3, /* ERROR */ @csplogstringshort = 'Export Table Setup',
    @csplogstringlong = @logStrFailure
    print @logStrFailure ;
    set @errMsg = 'Schema --> ' + @schemaname + 'does not exist' ;
   Throw 51001, @errMsg , 1
   End
 Else /* schema is found */
  Begin
    if(select name from sys.tables where @schemaid = schema_id and name in (@tablename)) > ''
     Set @sqlstr = 'select top 1 1 from ' + @schemaname + '.' + @tablename ;
  End /* If table Exists - Check if it have more than 0 records */
 if (@sqlstr > '')
   Begin /* execution of that @sqlstr will return if there are any records in the table if empty table we can stop .. but empty tables are acceptable to be included for export */ /* Construct FileName if not provided - with a datestring suffix - parameterising is not implemented but simple to add if called from a graph with a parameter added in for that graph - with a manual call no additional parameters are applied */
   select @fileNamelocal = case when @FileName > '' then @FileName else @tablename end + '_' + convert(varchar(8),getdate(),112) + '.txt' ;
   /* assign fixed values */
      insert into ops.CspExportTablesList ( LogDateTime ,
     ExportSchemaName ,
     ExportTableName ,
     ExportContainerName ,
     ExportFolderName ,
     ExportFileName ,
     ExportStatusCode ,
     ExportCompressionFlag ,
     ExportDelimiter )
   Values ( getdate() /*LogDateTime */,
     @schemaname /* ExportSchemaName */,
     @tablename /*ExportTableName */,
      @ContainerName /*ExportContainerName */,
      @FolderName /*ExportFolderName , */,
      @fileNamelocal /*ExportFileName */,
      0 /*ExportStatusCode */,
      @zippedFlag /*ExportCompressionFlag */,
      @delimiterChar /*ExportDelimiter */ ) ; /* same table can be exported to multiple locations so no vlaidation is done on pre-existing tablenames */
   if (@@ROWCOUNT = 1)
    Begin
     exec [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid,
      @cspexecutionid = @cspexecutionid,
      @cspgraphid = @cspgraphid,
      @cspgraphnodeid = @cspgraphnodeid,
      @csplogtypecode = 1, /* Success */ @csplogstringshort = 'Export Table Setup',
      @csplogstringlong = @logStrSuccess
      print @logStrSuccess
     End
   Else Begin
     exec [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid,
      @cspexecutionid = @cspexecutionid,
      @cspgraphid = @cspgraphid,
      @cspgraphnodeid = @cspgraphnodeid,
      @csplogtypecode = 3, /* ERROR */ @csplogstringshort = 'Export Table Setup',
      @csplogstringlong = @logStrFailure
      print @logStrFailure ; End
   End
 Else Begin
   exec [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid,
    @cspexecutionid = @cspexecutionid,
    @cspgraphid = @cspgraphid,
    @cspgraphnodeid = @cspgraphnodeid,
    @csplogtypecode = 3, /* ERROR */ @csplogstringshort = 'Export Table Setup',
    @csplogstringlong = @logStrFailure
    print @logStrFailure ;
  ;
   End /* Exit */
End
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPSetGraphExecutionStatus]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPSetGraphExecutionStatus];
GO

CREATE PROCEDURE [ops].[CSPSetGraphExecutionStatus] @cspgraphid INT, @CSPExecutionStatus INT, @retval BIT OUTPUT
AS
BEGIN
    DECLARE @debug AS BIT = 1;
    DECLARE @errorStr AS VARCHAR (255);
    SET @retval = 0;
    DECLARE @ExecutionId AS INT;
    SELECT @ExecutionId = CSPExecutionId
    FROM ops.GetCurrentGraphExecutionId(@cspgraphid);
    IF (@debug = 1)
        SELECT 'CSPExecutionStatus --> ',
               @CSPExecutionStatus;
    IF (SELECT 1
        FROM ops.CSPExecutionStatus
        WHERE CSPExecutionStatusCode = @CSPExecutionStatus) = 1
        BEGIN
            UPDATE ops.CSPExecutionGraph
            SET CSPExecutionStatusFlag = @CSPExecutionStatus,
                   CSPGraphEndDateTime = getdate()
            WHERE CSPGraphId = @cspgraphid
                   AND CSPExecutionId = @ExecutionId;
            IF (@@ROWCOUNT > 0)
                SET @retval = 1;
        END
    ELSE BEGIN
            SET @errorStr = 'Graph Status update failed - Invalid Status Code' + @CSPExecutionStatus;
            THROW 51000, @errorStr, 1;
        END
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPStartNewGraphExecution]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPStartNewGraphExecution];
GO

CREATE PROCEDURE [ops].[CSPStartNewGraphExecution] @cspgraphid INT, @cspcontextid INT, @retval BIT OUTPUT
AS
BEGIN
    DECLARE @NewExecutionId AS INT = 0;
    SET @retval = 0;
    IF ((SELECT CSPExecutionStatusFlag
         FROM ops.GetGraphExecutionStatus(@cspgraphid)) IS NULL
        OR (SELECT CSPExecutionStatusFlag
            FROM ops.GetGraphExecutionStatus(@cspgraphid)) IN (0, 6, 7))
       AND (SELECT 1
            FROM ops.CSPScheduleGraph
            WHERE @cspgraphid = CSPScheduleGraphId) = 1
        BEGIN
            BEGIN TRANSACTION;
            UPDATE ops.CSPNextExecutionId
            SET CSPExecutionId = CSPExecutionId + 1;
            SELECT @NewExecutionId = CSPExecutionId
            FROM ops.CSPNextExecutionId;
            INSERT INTO ops.CSPExecutionGraph
            VALUES (@NewExecutionId, @cspcontextid, @cspgraphid, getdate(), NULL, 1);
            COMMIT TRANSACTION;
            SELECT 'New Execution Id',
                   @NewExecutionId;
            IF (@@ROWCOUNT > 0)
                SET @retval = 1;
        END
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CspStopProcessing]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CspStopProcessing];
GO

CREATE PROCEDURE [ops].[CspStopProcessing] @cspcontextid INT, @cspexecutionid INT, @cspgraphid INT, @cspgraphnodeid INT, @CspStopMessage VARCHAR (255)
AS
BEGIN
    EXECUTE ops.CSPStreamLogger @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid, 4, 'Critical Error - Stop', @CspStopMessage, 0;
    THROW 51001, @CspStopMessage, 1;
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPStoreExecutionString]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPStoreExecutionString];
GO

CREATE PROCEDURE [ops].[CSPStoreExecutionString] @sqlstr VARCHAR (MAX), @cspcontextid INT, @cspexecutionid INT, @cspgraphid INT, @cspgraphnodeid INT
AS
BEGIN
    INSERT INTO ops.CSPExecutionStrings ([CSPExecutionDateTime], [CSPExecutionString], [CSPContextId], [CSPExecutionId], [CSPGraphId], [CSPGraphNodeId])
    VALUES (GETDATE(), @sqlstr, @cspcontextid, @cspexecutionid, @cspgraphid, @cspgraphnodeid);
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPStreamLogger]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPStreamLogger];
GO

CREATE PROCEDURE [ops].[CSPStreamLogger] @cspcontextid INT, @cspexecutionid INT, @cspgraphid INT, @cspgraphnodeid INT, @csplogtypecode INT=1, @csplogstringshort VARCHAR (50), @csplogstringlong VARCHAR (255)='', @csprecordcount BIGINT=NULL
AS
BEGIN
    INSERT INTO ops.CSPLogStream (CSPLogDateTime, CSPExecutionId, CSPContextId, CSPGraphId, CSPGraphNodeId, CSPLogTypeCode, CSPLogStringShort, CSPLogStringLong, CSPRecordCount)
    VALUES (getdate(), @cspexecutionid, @cspcontextid, @cspgraphid, @cspgraphnodeid, @csplogtypecode, @csplogstringshort, @csplogstringlong, @csprecordcount);
    INSERT INTO ops.CSPLogStreamLive (CSPLogDateTime, CSPExecutionId, CSPContextId, CSPGraphId, CSPGraphNodeId, CSPLogTypeCode, CSPLogStringShort, CSPLogStringLong, CSPRecordCount)
    VALUES (getdate(), @cspexecutionid, @cspcontextid, @cspgraphid, @cspgraphnodeid, @csplogtypecode, @csplogstringshort, @csplogstringlong, @csprecordcount);
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPSubstituteParams]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPSubstituteParams];
GO

CREATE PROCEDURE [ops].[CSPSubstituteParams] @cspcontextid INT, @cspexecutionid INT, @cspgraphid INT, @cspgraphnodeid INT, @sqlstr NVARCHAR (MAX), @retStr NVARCHAR (MAX) OUTPUT
AS
BEGIN
    DECLARE @startpos AS INT, @endpos AS INT, @CSPParmValue AS NVARCHAR (255);
    SET @startpos = 1;
    SET @endpos = 0;
    SET @CSPParmValue = '';
    DECLARE @errorstring1 AS VARCHAR (50) = 'Parameters Substitution Failed';
    DECLARE @errorstring2 AS VARCHAR (255) = '';
    WHILE (@sqlstr LIKE '%##%##%')
        BEGIN
            SELECT @startpos = charindex('##', @sqlstr, @startpos);
            SELECT @endpos = charindex('##', @sqlstr, @startpos + 2);
            SELECT @CSPParmValue = CSPParmValue
            FROM ops.CSPExecutionParameters
            WHERE CSPParmName = SUBSTRING(@sqlstr, @startpos + 2, @endpos - @startpos - 2)
                   AND COALESCE ([CSPContextId], @cspcontextid) = @cspcontextid
                   AND COALESCE ([CSPExecutionId], @cspexecutionid) = @cspexecutionid
                   AND COALESCE ([CSPGraphId], @cspgraphid) = @cspgraphid
                   AND COALESCE ([CSPGraphNodeId], @cspgraphnodeid) = @cspgraphnodeid;
            IF @@ROWCOUNT <> 1
                BEGIN
                    SET @errorstring2 = SUBSTRING(@sqlstr, @startpos + 2, @endpos - @startpos - 2) + ' - Lookup Failed from ops.CurrentParameters table';
                    EXECUTE ops.CSPStreamLogger @cspcontextid = NULL, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid, @csplogtypecode = 4, @csplogstringshort = @errorstring1, @csplogstringlong = @errorstring2, @csprecordcount = 1;
                END
            SELECT @sqlstr = replace(@sqlstr, SUBSTRING(@sqlstr, @startpos, @endpos - @startpos + 2), @CSPParmValue);
            SET @CSPParmValue = '';
        END
    SET @retStr = @sqlstr;
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPTableCopy]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPTableCopy];
GO

CREATE PROC [ops].[CSPTableCopy] @cspcontextid tinyint,
    @cspexecutionid int,
    @cspgraphid int,
    @cspgraphnodeid int
AS
BEGIN
              declare @SourceSchema varchar(5) = '';
            declare @TargetSchema varchar(5) = '';
                          declare @logMessage varchar(255) = '';
                          declare @srcColumn nvarchar(max) = ''
            declare @tgtColumn nvarchar(max) = ''
            declare @sqlstr nvarchar(max) = ''
            declare @fieldCount int = 0
             declare @tableCount int = 0
             declare @logstr nvarchar(255) = ''
             declare @tablename varchar(255) = ''
             declare @recordCount bigint = 0 ;
                          declare @debugflag bit = 0 /* Read @SourceSchema and @TargetSchema from Parameter Table */
              Select @SourceSchema = [CSPParmValue]
             FROM [ops].[CSPExecutionParameters]
            where [CSPContextId] = @cspcontextid
            and [CSPGraphId] = @cspgraphid
             and [CSPParmName] = 'SOURCESCHEMA' ;
            Select @TargetSchema = [CSPParmValue]
             FROM [ops].[CSPExecutionParameters]
            where [CSPContextId] = @cspcontextid
            and [CSPGraphId] = @cspgraphid
             and [CSPParmName] = 'TARGETSCHEMA' ;
            drop table if exists #CSPCommonTableList ;
            select a.TABLE_NAME,
                     '[' + a.COLUMN_NAME + ']' COLUMN_NAME,
                    a.IS_NULLABLE as tgtNullable,
                    b.IS_NULLABLE as srcNullable,
                    a.DATA_TYPE,
                    a.NUMERIC_PRECISION as tgtNumericPrecision,
                    b.NUMERIC_PRECISION as srcNumericPrecision,
                    a.NUMERIC_SCALE as tgtNumericScale,
                    b.NUMERIC_SCALE as srcNumericScale,
                    a.CHARACTER_MAXIMUM_LENGTH as tgtCharMaxLength,
                    b.CHARACTER_MAXIMUM_LENGTH as srcCharMaxLength,
                    case when a.DATA_TYPE like '%char%'
            then 1 when a.DATA_TYPE in ('tinyint', 'smallint', 'int', 'bigint')
                                                                     then 2 when a.DATA_TYPE in ('decimal')
           then 3 when a.DATA_TYPE in ('float')
             then 4 when a.DATA_TYPE like ('%date%')
          then 5 when a.DATA_TYPE = 'bit'
                  then 6 else 0 /* bit blob etc - not validated now - future todo */
                    end dataTypeGroupId into #CSPCommonTableList
             from (
                        select TABLE_NAME, COLUMN_NAME, IS_NULLABLE, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE
                        FROM INFORMATION_SCHEMA.COLUMNS
                         WHERE TABLE_SCHEMA = @TargetSchema ) a,
                    (
                        select TABLE_NAME, COLUMN_NAME, IS_NULLABLE, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE
                        FROM INFORMATION_SCHEMA.COLUMNS
                         WHERE TABLE_SCHEMA = @SourceSchema ) b
            where a.TABLE_NAME = b.TABLE_NAME
            and a.COLUMN_NAME = b.COLUMN_NAME ;
              if @debugflag =1
                 select * from #CSPCommonTableList
                 order by 1,2 ;
            drop table if exists #CSPCommonTableColumnList
             select b.TableSeqNo,
                     a.*,
                    row_number() over (partition by a.TABLE_NAME, dataTypeGroupId
                                              order by a.COLUMN_NAME) as ColDataTypeSeqNo,
                    row_number() over (partition by a.TABLE_NAME
                                            order by a.COLUMN_NAME) as ColSeqNo into #CSPCommonTableColumnList
            FROM #CSPCommonTableList a,
                    (select row_number() over (order by TABLE_NAME) TableSeqNo, TABLE_NAME
from (select distinct TABLE_NAME from #CSPCommonTableList) x) as b
            where a.TABLE_NAME = b.TABLE_NAME
            and a.dataTypeGroupId in (2 ,3, 4, 5)
                          if @debugflag =1
                 select * from #CSPCommonTableColumnList
                order by 1,2 drop table if exists #CSPColumnTransformationList
            Create table #CSPColumnTransformationList (
                   TableName nvarchar(255),
                SrcColumnStr nvarchar(1024),
                tgtColumnStr nvarchar(max),
                ColSeqNumber int )
             select @tableCount = max(TableSeqNo) from #CSPCommonTableColumnList
             while (@tableCount > 0)
            Begin
                                  select distinct @tablename = TABLE_NAME from #CSPCommonTableColumnList where TableSeqNo = @tableCount ;
                select @fieldCount = max(ColSeqNo) from #CSPCommonTableColumnList where TableSeqNo = @tableCount;
                while (@fieldCount > 0)
                    Begin
                        insert into #CSPColumnTransformationList (TableName, SrcColumnStr, tgtColumnStr, ColSeqNumber)
                          select TABLE_NAME, COLUMN_NAME, ' case when len(' + COLUMN_NAME + ') = 0 then null else convert(numeric, ' + COLUMN_NAME + ') end' , @fieldCount
                        from #CSPCommonTableColumnList
                         where TableSeqNo = @tableCount
                         and ColSeqNo = @fieldCount
                         and dataTypeGroupId in (2) /* Columns which need to be replaced with a transformation are considered here -- refer to @replaceColCount */ ;
                        /* vijay - fix below to correct the loss of precision in float and decimal columns - 22/10/2021 */
                        insert into #CSPColumnTransformationList (TableName, SrcColumnStr, tgtColumnStr, ColSeqNumber)
                          select TABLE_NAME, COLUMN_NAME, ' case when len(' + COLUMN_NAME + ') = 0 then null else convert(float, ' + COLUMN_NAME + ') end' , @fieldCount
                        from #CSPCommonTableColumnList
                         where TableSeqNo = @tableCount
                         and ColSeqNo = @fieldCount
                         and dataTypeGroupId in (3,4) /* Columns which need to be replaced with a transformation are considered here -- refer to @replaceColCount */ ;
                        /* vijay - fix below to correct the loss of precision in float and decimal columns - 22/10/2021 */
                        insert into #CSPColumnTransformationList (TableName, SrcColumnStr, tgtColumnStr, ColSeqNumber)
                          select TABLE_NAME, COLUMN_NAME, ' case when len(' + COLUMN_NAME + ') = 0 then null
                                                                 when len(' + COLUMN_NAME + ') > 19 then substring(' + COLUMN_NAME + ' ,1,19)
                                                                when len(' + COLUMN_NAME + ') = 10 and SUBSTRING(' + COLUMN_NAME + ',5,1) in (''-'',''/'') then concat(left (' + COLUMN_NAME + ',4),''-'',substring(' + COLUMN_NAME + ',6,2),''-'',right(' + COLUMN_NAME + ',2), '' 00:00:00'')
                                                                when len(' + COLUMN_NAME + ') = 10 and SUBSTRING(' + COLUMN_NAME + ',3,1) in (''-'',''/'') then concat(right(' + COLUMN_NAME + ',4),''-'',substring(' + COLUMN_NAME + ',4,2),''-'',left(' + COLUMN_NAME + ',2), '' 00:00:00'')
                                                                when len(' + COLUMN_NAME + ') between 11 and 18 and SUBSTRING(' + COLUMN_NAME + ',5,1) in (''-'',''/'') then concat(left(' + COLUMN_NAME + ',4),''-'',substring(' + COLUMN_NAME + ',6,2),''-'',substring(' + COLUMN_NAME + ',9,2), substring(' + COLUMN_NAME + ',11, len(' + COLUMN_NAME + ')-10))
                                                                when len(' + COLUMN_NAME + ') between 11 and 18 and SUBSTRING(' + COLUMN_NAME + ',3,1) in (''-'',''/'') then concat(right(left(' + COLUMN_NAME + ',10),4),''-'',substring(' + COLUMN_NAME + ',4,2),''-'',left(' + COLUMN_NAME + ',2), substring(' + COLUMN_NAME + ',11, len(' + COLUMN_NAME + ')-10))
                                                                 else ' + COLUMN_NAME + ' end' , @fieldCount
                        from #CSPCommonTableColumnList
                         where TableSeqNo = @tableCount
                         and ColSeqNo = @fieldCount
                         and dataTypeGroupId in (5) /* Datetime columns with higher precision than 3 truncated to 3 */ ;
                        if @debugflag = 1
                             select * , @fieldCount from #CSPColumnTransformationList
                            order by ColSeqNumber ;
                           set @fieldCount -= 1
                     End /* Column Data Transformation - End */
                                  set @tableCount -= 1
                                   End
             if @debugflag =1
                 select * from #CSPColumnTransformationList
                order by 1,2 /* TODO validate schemas */
             if (@SourceSchema> '') and (@TargetSchema > '') and (@SourceSchema <> @TargetSchema) /* TODO validate schemas */
             Begin
                                          declare @ColumnsListStr nvarchar(max) = ''
                       declare @tableSeqNo int = 0 /*declare @tableName nvarchar(255) = ''*/
                    drop table if exists stg.CSPx
                     select name, row_number() over (partition by 1 order by name) as rno into stg.CSPx
                    from sys.tables a
                    where schema_name(schema_id) = @TargetSchema
                    and a.name in (select distinct TABLE_NAME from #CSPCommonTableList )
                                           select @tableSeqNo = coalesce(max(rno),0) from stg.CSPx
                    while (@tableSeqNo > 0)
                        Begin
                            select @tablename = name from stg.CSPx where rno = @tableSeqNo;
                              /* ====== MINIMAL CHANGE: replace FOR XML PATH concat with STRING_AGG ====== */
                            SELECT @ColumnsListStr = STRING_AGG('[' + b.name + ']', ', ') WITHIN GROUP (ORDER BY b.column_id)
                            FROM sys.tables a
                            JOIN sys.columns b ON a.object_id = b.object_id
                            JOIN sys.types c ON c.system_type_id = b.system_type_id
                            WHERE schema_name(a.schema_id) = @TargetSchema
                              AND a.name = @tablename
                                   AND c.name NOT IN ('sysname')
                               AND a.type = 'U';
                              /* was:
                               select @ColumnsListStr = ( ... for xml path('') )
                               Set @ColumnsListStr = left(@ColumnsListStr, len(@ColumnsListStr) - 2) */
                                                      if ( select name
                                  from sys.tables
                                  where schema_name(schema_id) = @SourceSchema
                                 and name = @tablename ) > ''
                                   Begin -- Truncation is ok - should we filter the reason to truncate...? Set @SqlStr = 'truncate table ' + @TargetSchema + '.[' + @tableName + '] ;'
                                        Set @logMessage = 'Truncating table ' + @TargetSchema + '.[' + @tablename + '] ;'
                                        exec [ops].[CSPStoreExecutionString] @sqlstr, @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid ;
                                        exec sp_executesql @sqlstr;
                                          exec [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid,
                                                     @cspexecutionid = @cspexecutionid,
                                                     @cspgraphid = @cspgraphid,
                                                     @cspgraphnodeid = @cspgraphnodeid,
                                                    @csplogtypecode = 1,
                                                     @csplogstringshort = 'Target truncated',
                                                     @csplogstringlong = @logMessage,
                                                     @csprecordcount = @@ROWCOUNT ;
                                                                                                            declare @replaceColCount int = 0
                                          declare @targetColStr nvarchar(max) = @ColumnsListStr;
                                        select @replaceColCount = Coalesce(max(ColSeqNumber),0) from #CSPColumnTransformationList where TableName = @tablename
                                        While (@replaceColCount > 0)
                                        Begin
                                                select @targetColStr = replace(@targetColStr, SrcColumnStr, tgtColumnStr)
                                                from #CSPColumnTransformationList
                                                 where ColSeqNumber = @replaceColCount
                                                and TableName = @tablename ;
                                                  Set @replaceColCount -= 1 ;
                                        End
                                          select @targetColStr
                                         Set @sqlstr = 'insert into ' + @TargetSchema + '.[' + @tablename + '] ( ' + @ColumnsListStr + ' ) Select ' + @targetColStr + ' From ' + @SourceSchema + '.[' + @tablename + '] ;'
                                                                                  Set @logMessage = 'insert into ' + @TargetSchema + '.[' + @tablename + '] From ' + @SourceSchema + '.[' + @tablename + ']'
                                         exec [ops].[CSPStoreExecutionString] @sqlstr, @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid ;
                                        select @sqlstr;
                                        exec sp_executesql @sqlstr;
                                                                                  exec [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid,
                                                     @cspexecutionid = @cspexecutionid,
                                                     @cspgraphid = @cspgraphid,
                                                     @cspgraphnodeid = @cspgraphnodeid,
                                                    @csplogtypecode = 1,
                                                     @csplogstringshort = 'Target Insert',
                                                     @csplogstringlong = @logMessage,
                                                     @csprecordcount = @@ROWCOUNT ;
                                End
                            Else Begin
                                    Set @logMessage = 'Target Table Present but Missing in Source Schema --> ' + @SourceSchema + '.[' + @tablename + ']';
                                    exec [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid,
                                                 @cspexecutionid = @cspexecutionid,
                                                 @cspgraphid = @cspgraphid,
                                                 @cspgraphnodeid = @cspgraphnodeid,
                                                @csplogtypecode = 1,
                                                 @csplogstringshort = 'Table Copy - Missing',
                                                 @csplogstringlong = @logMessage,
                                                 @csprecordcount = 0 ;
                                End
                            Set @tableSeqNo = @tableSeqNo - 1 /* and then exec that */
                        End
               End
 End
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPTruncateTable]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPTruncateTable];
GO

Create proc [ops].[CSPTruncateTable] @tblname varchar(255),
 @schemaname varchar(5),
 @cspexecutionid int
AS
BEGIN
 declare @sqlstr nvarchar(1024) = '';
 declare @logstr nvarchar(1024) = '';
    declare @cspcontextid tinyint;
 declare @cspgraphid int;
 declare @cspgraphnodeid int = 0;
   select @cspgraphid = CSPGraphId,
    @cspcontextid = CSPContextId
   from ops.CSPExecutionGraph
  where CSPExecutionId = @cspexecutionid ;
 Begin Try
      Set @tblname =
case when charindex('.', @tblname)>0
then left(@tblname, charindex('.', @tblname) -1) else @tblname end ;
  if (select 1 from sys.tables where name in (@tblname) and SCHEMA_NAME(schema_id) = @schemaname) = 1
   Begin
    Set @sqlstr = 'Drop table ' + @schemaname + '.[' + @tblname + ']';
    Set @logstr = @schemaname + '.[' + @tblname + ']' + ' Dropped Successfully'
          exec sp_executesql @sqlstr;
   End
  Else Begin
    Set @logstr = @schemaname + '.[' + @tblname + ']' + ' does not exist. Will be created by Load Process.'
   End
    exec [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid,
     @cspexecutionid = @cspexecutionid ,
     @cspgraphid = @cspgraphid,
     @cspgraphnodeid = @cspgraphnodeid,
    @csplogtypecode = 1,
     @csplogstringshort = 'Blob to Src Load',
     @csplogstringlong = @logstr,
     @csprecordcount = 0
   End Try
    Begin Catch
      set @logstr = 'Error Message - ' + Error_message();
    ;
    exec [ops].[CSPStreamLogger] @cspcontextid = @cspcontextid,
       @cspexecutionid = @cspexecutionid ,
       @cspgraphid = @cspgraphid,
       @cspgraphnodeid = @cspgraphnodeid,
      @csplogtypecode = 3, /* ERROR */ @csplogstringshort = 'Drop table Failure',
      @csplogstringlong = @logstr ;
        End Catch
     End
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPUpdateScheduledItemString]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPUpdateScheduledItemString];
GO

CREATE PROCEDURE [ops].[CSPUpdateScheduledItemString] @CSPScheduledItemId INT, @incrMajorMinorVersion NVARCHAR (10), @CSPScheduledItemString NVARCHAR (MAX)
AS
BEGIN
    DECLARE @majorVersion AS INT = 0;
    DECLARE @minorVersion AS INT = 0;
    IF (@incrMajorMinorVersion NOT IN ('Major', 'Minor'))
        BEGIN
            SELECT 'Invalid Version Option - ',
                   @incrMajorMinorVersion;
            THROW 59999, 'Invalid Version Option - Should be Minor or Major', 1;
        END
    IF (@CSPScheduledItemString = '')
        BEGIN
            SELECT 'Empty SQL String',
                   @CSPScheduledItemString;
            THROW 59999, 'Empty SQL String', 1;
        END
    IF (SELECT 1
        FROM ops.CSPScheduledItemString
        WHERE CSPScheduledItemId = @CSPScheduledItemId
               AND CSPScheduledItemCurrentFlag = 1) = 1
        BEGIN
            SELECT @majorVersion = CSPMajorVersion,
                   @minorVersion = CSPMinorVersion
            FROM ops.CSPScheduledItemString
            WHERE CSPScheduledItemId = @CSPScheduledItemId
                   AND CSPScheduledItemCurrentFlag = 1;
            UPDATE ops.CSPScheduledItemString
            SET CSPScheduledItemCurrentFlag = 0,
                   RecordUpdateDateTime = GETDATE()
            WHERE CSPScheduledItemId = @CSPScheduledItemId
                   AND CSPScheduledItemCurrentFlag = 1;
            INSERT INTO ops.CSPScheduledItemString (CSPScheduledItemId, CSPScheduledItemString, CSPMajorVersion, CSPMinorVersion, CSPScheduledItemCurrentFlag, RecordInsertDateTime, RecordUpdateDateTime, CSPClientId)
            SELECT @CSPScheduledItemId,
                   @CSPScheduledItemString,
                   CASE WHEN @incrMajorMinorVersion = 'Major' THEN @majorVersion + 1 ELSE @majorVersion END,
                   CASE WHEN @incrMajorMinorVersion = 'Major' THEN 0 WHEN @incrMajorMinorVersion = 'Minor' THEN @minorVersion + 1 ELSE @minorVersion END,
                   1 AS CSPScheduledItemCurrentFlag,
                   GETDATE(),
                   NULL,
                   7;
        END
    ELSE BEGIN
            SELECT 'Invalid ScheduledItemID ',
                   @CSPScheduledItemId,
                   ' -- Does NOT EXIST';
            THROW 59999, 'review CSPScheduledItemId', 1;
        END
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[CSPValidateSourceRecords]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[CSPValidateSourceRecords];
GO

CREATE proc [ops].[CSPValidateSourceRecords] @cspcontextid tinyint,
 @cspexecutionid int,
 @cspgraphid int,
 @cspgraphnodeid int
as Begin /* TODO List 1. ExecutionId not yet allocated Programmatically */
          declare @SourceSchema varchar(5);
   declare @TargetSchema varchar(5);
        /* Read @SourceSchema and @TargetSchema from Parameter Table */
     Select @SourceSchema = trim([CSPParmValue])
    FROM [ops].[CSPExecutionParameters]
   where [CSPContextId] = @cspcontextid
   and [CSPGraphId] = @cspgraphid
    and [CSPParmName] = 'SOURCESCHEMA' ;
   Select @TargetSchema = trim([CSPParmValue])
    FROM [ops].[CSPExecutionParameters]
   where [CSPContextId] = @cspcontextid
   and [CSPGraphId] = @cspgraphid
    and [CSPParmName] = 'TARGETSCHEMA' ;
        Select @SourceSchema, @TargetSchema /* TODO - check if schema exists else fail right away */
     drop table if exists stg.cspvsr_x ;
   select a.TABLE_NAME,
     a.COLUMN_NAME,
     a.IS_NULLABLE as tgtNullable,
     b.IS_NULLABLE as srcNullable,
     a.DATA_TYPE,
     a.NUMERIC_PRECISION as tgtNumericPrecision,
     b.NUMERIC_PRECISION as srcNumericPrecision,
     a.NUMERIC_SCALE as tgtNumericScale,
     b.NUMERIC_SCALE as srcNumericScale,
     a.CHARACTER_MAXIMUM_LENGTH as tgtCharMaxLength,
     b.CHARACTER_MAXIMUM_LENGTH as srcCharMaxLength,
     case when a.DATA_TYPE like '%char%'
  then 1 when a.DATA_TYPE in ('tinyint', 'smallint', 'int', 'bigint')
                  then 2 when a.DATA_TYPE in ('decimal')
  then 3 when a.DATA_TYPE in ('float')
  then 4 when a.DATA_TYPE = 'datetime2'
  then 5 /* datetime2 is handled first */
         when a.DATA_TYPE like ('%date%')
 then 6 else 0 /* bit blob etc - not validated now - future todo */
     end dataTypeGroupId into stg.cspvsr_x
    from (
      select TABLE_NAME, COLUMN_NAME, IS_NULLABLE, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE
      FROM INFORMATION_SCHEMA.COLUMNS
       WHERE TABLE_SCHEMA = @TargetSchema ) a,
     (
      select TABLE_NAME, COLUMN_NAME, IS_NULLABLE, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE
      FROM INFORMATION_SCHEMA.COLUMNS
       WHERE TABLE_SCHEMA = @SourceSchema ) b
   where a.TABLE_NAME = b.TABLE_NAME
   and a.COLUMN_NAME = b.COLUMN_NAME ;
   drop table if exists stg.cspvsr_y
    select b.TableSeqNo,
      a.*,
     row_number() over (partition by a.TABLE_NAME, dataTypeGroupId
            order by a.COLUMN_NAME) as ColDataTypeSeqNo,
     row_number() over (partition by a.TABLE_NAME
           order by a.COLUMN_NAME) as ColSeqNo into stg.cspvsr_y
   FROM stg.cspvsr_x a,
     (select row_number() over (order by TABLE_NAME) TableSeqNo, TABLE_NAME
from (select distinct TABLE_NAME from stg.cspvsr_x) x) as b
   where a.TABLE_NAME = b.TABLE_NAME
       declare @a nvarchar(max) = ''
   declare @b nvarchar(max) = ''
   declare @c nvarchar(max) = ''
   declare @sqlstr nvarchar(max) = ''
   declare @fieldCount int = 0
    declare @tableCount int = 0
    declare @logstr nvarchar(255) = ''
    declare @tablename varchar(255) = ''
    declare @recordCount bigint = 0 ;
     select @tableCount = max(TableSeqNo) from stg.cspvsr_y
    while (@tableCount > 0)
   Begin
          select distinct @tablename = TABLE_NAME from stg.cspvsr_y where TableSeqNo = @tableCount ;
    set @logstr = @tablename + ' - Exception processing commencing'
    exec ops.CSPStreamLogger @cspcontextid = @cspcontextid,
       @cspexecutionid = @cspexecutionid,
       @cspgraphid = @cspgraphid,
       @cspgraphnodeid = @cspgraphnodeid,
       @csplogtypecode = 1,
       @csplogstringshort = 'DQ Issues - Exceptions ' ,
       @csplogstringlong = @logstr,
       @csprecordcount = 0 /* no records processed yet */ ;
    /* failed records storage */
    select @sqlstr = 'if object_id(''trk.[DQF_' + @tablename + ']'') is null select a.*, cast(null as BigInt) as LoadRunId, cast(null as datetime2(0)) as LoadRunDate, cast(null as BigInt) as UpdateRunId, cast(null as datetime2(0)) as UpdateRunDate, getdate() Deleted_Date , '+ str(@cspexecutionid) + ' as CSPExecutionId into trk.[DQF_' + @tablename + '] from ' + @SourceSchema + '.[' + @tablename + '] a where 1 = 0 ' ;
    exec sp_executesql @sqlstr /* records validation - Start */
    set @sqlstr = ''
    select distinct @a = ' insert into trk.[DQF_' + @tablename + '] select a.*,
cast(null as BigInt) as LoadRunId, cast(null as datetime2(0)) as LoadRunDate, cast(null as BigInt) as UpdateRunId, cast(null as datetime2(0)) as UpdateRunDate, getdate() , ' + str(@cspexecutionid) + ' from ' + @SourceSchema + '.[' + @tablename + '] a Where case ';
      set @b = '' ;
    select distinct @c = ' else 0 end >= 1 ' ;
    select @fieldCount = max(ColSeqNo) from stg.cspvsr_y where TableSeqNo = @tableCount;
    while (@fieldCount > 0)
     Begin /* simple checks */
      select distinct @b += ' when len([' + COLUMN_NAME + ']) > ' + cast(Case when tgtCharMaxLength = -1 then '99999' else tgtCharMaxLength end as varchar(5))+ ' then 1 ' from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 1
       select distinct @b += ' when isnumeric([' + COLUMN_NAME + ']) = 0 and len([' + COLUMN_NAME + ']) > 0 then 1 ' from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId in (2 ,3, 4) /* datetime with more than 3 precision and 7 at most */
      select distinct @b += ' when isdate(substring([' + COLUMN_NAME + '],1,23)) = 0 and len([' + COLUMN_NAME + ']) between 24 and 28 then 1 ' from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 5
      select distinct @b += ' when try_convert(datetime2,[' + COLUMN_NAME + ']) is null and [' + COLUMN_NAME + '] is not null and len([' + COLUMN_NAME + ']) between 19 and 28 then 1 ' from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 5 /* datetime with 3 precision at most */
      select distinct @b += ' when isdate([' + COLUMN_NAME + ']) = 0 and len([' + COLUMN_NAME + ']) between 19 and 23 then 1 ' from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 6 /* datetime with more than 3 precision and 7 at most */
      select distinct @b += ' when isdate(substring([' + COLUMN_NAME + '],1,23)) = 0 and len([' + COLUMN_NAME + ']) between 24 and 28 then 1 ' from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 6 /* datetime with more than 3 precision and 7 at most */
      select distinct @b += ' when isdate(substring([' + COLUMN_NAME + '],1,23)) = 0 and len([' + COLUMN_NAME + ']) between 24 and 28 then 1 ' from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 6 /* 10 char date with dd/mm/yyyy or dd-mm-yyyy format */
      select distinct @b += ' when SUBSTRING([' + COLUMN_NAME + '],3,1) in (''-'',''/'') and isdate(concat(right([' + COLUMN_NAME + '],4),''-'',substring([' + COLUMN_NAME + '],4,2),''-'',LEFT([' + COLUMN_NAME + '],2))) = 0 and len([' + COLUMN_NAME + ']) = 10 then 1 ' from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId in (5,6) /* 10 char date with dd/mm/yyyy or dd-mm-yyyy format */
      select distinct @b += ' when SUBSTRING([' + COLUMN_NAME + '],5,1) in (''-'',''/'') and isdate(concat(right([' + COLUMN_NAME + '],4),''-'',substring([' + COLUMN_NAME + '],6,2),''-'',LEFT([' + COLUMN_NAME + '],2))) = 0 and len([' + COLUMN_NAME + ']) = 10 then 1 ' from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId in (5,6) /* 10 char date with dd/mm/yyyy or dd-mm-yyyy format */
       select distinct @b += ' when SUBSTRING([' + COLUMN_NAME + '],5,1) in (''-'',''/'') and isdate(concat(left([' + COLUMN_NAME + '],4),''-'',substring([' + COLUMN_NAME + '],6,2),''-'',RIGHT(LEFT([' + COLUMN_NAME + '],10),2))) = 0 and len([' + COLUMN_NAME + ']) = 10 then 1 ' from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId in (5,6) /* boundary checks for all int types */
                select distinct @b += ' when isnumeric([' + COLUMN_NAME + ']) = 0 and len([' + COLUMN_NAME + ']) > 0 then ' + CAST(ColSeqNo as varchar(5))
       from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 2 and DATA_TYPE = 'Tinyint'
      select distinct @b += ' when isnumeric([' + COLUMN_NAME + ']) = 1 and convert(numeric,[' + COLUMN_NAME + ']) not between 0 and 255 then ' + CAST(ColSeqNo as varchar(5))
       from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 2 and DATA_TYPE = 'Tinyint'
        select distinct @b += ' when isnumeric([' + COLUMN_NAME + ']) = 0 and len([' + COLUMN_NAME + ']) > 0 then ' + CAST(ColSeqNo as varchar(5))
       from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 2 and DATA_TYPE = 'smallint'
      select distinct @b += ' when isnumeric([' + COLUMN_NAME + ']) = 1 and convert(numeric, [' + COLUMN_NAME + ']) not between -32768 and 32767 then ' + CAST(ColSeqNo as varchar(5))
       from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 2 and DATA_TYPE = 'smallint'
        select distinct @b += ' when isnumeric([' + COLUMN_NAME + ']) = 0 and len([' + COLUMN_NAME + ']) > 0 then ' + CAST(ColSeqNo as varchar(5))
       from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 2 and DATA_TYPE = 'int'
      select distinct @b += ' when isnumeric([' + COLUMN_NAME + ']) = 1 and convert(numeric, [' + COLUMN_NAME + ']) not between -2147483648 and 2147483647 then ' + CAST(ColSeqNo as varchar(5))
       from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 2 and DATA_TYPE = 'int'
        select distinct @b += ' when isnumeric([' + COLUMN_NAME + ']) = 0 and len([' + COLUMN_NAME + ']) > 0 then ' + CAST(ColSeqNo as varchar(5))
       from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 2 and DATA_TYPE = 'BigInt'
      select distinct @b += ' when isnumeric([' + COLUMN_NAME + ']) = 1 and convert(numeric, [' + COLUMN_NAME + ']) not between -9223372036854775808 and 9223372036854775807 then ' + CAST(ColSeqNo as varchar(5))
       from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 2 and DATA_TYPE = 'BigInt' /* boundary checks for Decimal */
        select distinct @b += ' when isnumeric([' + COLUMN_NAME + ']) = 0 and len([' + COLUMN_NAME + ']) > 0 then ' + CAST(ColSeqNo as varchar(5))
       from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 2 and DATA_TYPE = 'decimal'
      select distinct @b += ' when isnumeric([' + COLUMN_NAME + ']) = 1 and and convert(numeric, [' + COLUMN_NAME + ']) not between -' + replicate('9',(tgtNumericPrecision - tgtNumericScale)) + '.' + replicate('9',(tgtNumericScale)) + ' and ' + replicate('9',(tgtNumericPrecision - tgtNumericScale)) + '.' + replicate('9',(tgtNumericScale)) + ' then ' + CAST(ColSeqNo as varchar(5))
       from stg.cspvsr_y where TableSeqNo = @tableCount and ColSeqNo = @fieldCount and dataTypeGroupId = 2 and DATA_TYPE = 'decimal'
        set @fieldCount -= 1
      End /* records validation - End */ /* Copy records out to trk */
     set @logstr = @tablename + ' - Exception records identified'
    select @sqlstr = @a + ' ' + @b + ' ' + @c
           exec [ops].[CSPStoreExecutionString] @sqlstr, @cspcontextid = @cspcontextid, @cspexecutionid = @cspexecutionid, @cspgraphid = @cspgraphid, @cspgraphnodeid = @cspgraphnodeid ;
          exec sp_executesql @sqlstr
    set @recordCount = @@rowcount
      if (@recordCount > 0 )
      Begin
      exec ops.CSPStreamLogger @cspcontextid = @cspcontextid,
         @cspexecutionid = @cspexecutionid,
         @cspgraphid = @cspgraphid,
         @cspgraphnodeid = @cspgraphnodeid,
         @csplogtypecode = 1,
         @csplogstringshort = 'DQ Issues - Exceptions ' ,
         @csplogstringlong = @logstr,
         @csprecordcount = @recordCount /* records removal - Start */
      set @sqlstr = ''
            select distinct @a = ' delete from ' + @SourceSchema + '.' + TABLE_NAME + ' Where case ' from stg.cspvsr_y where TableSeqNo = @tableCount /* @b and @c are the same from prev step */ /* records removal - End */
        Begin Try /* Delete records from src */
         set @logstr = @tablename + ' - Exception records removed'
        select @sqlstr = @a + ' ' + @b + ' ' + @c
               exec sp_executesql @sqlstr
        exec ops.CSPStreamLogger @cspcontextid = @cspcontextid,
           @cspexecutionid = @cspexecutionid,
           @cspgraphid = @cspgraphid,
           @cspgraphnodeid = @cspgraphnodeid,
           @csplogtypecode = 1,
           @csplogstringshort = 'DQ Issues - Exceptions ' ,
           @csplogstringlong = @logstr,
           @csprecordcount = @@rowcount ;
      End Try
      Begin Catch
        set @logstr = @tablename + ' - Exception record processing failed'
        exec ops.CSPStreamLogger @cspcontextid = @cspcontextid,
           @cspexecutionid = @cspexecutionid,
           @cspgraphid = @cspgraphid,
           @cspgraphnodeid = @cspgraphnodeid,
           @csplogtypecode = 3,
           @csplogstringshort = 'DQ Issues - Exceptions ' ,
           @csplogstringlong = @logstr,
           @csprecordcount = @@rowcount ;
        Throw 59999, @logstr, 1 ;
      End Catch
     End
    Else Begin
      set @logstr = @tablename + ' - Exception record processing found no issues'
      exec ops.CSPStreamLogger @cspcontextid = @cspcontextid,
         @cspexecutionid = @cspexecutionid,
         @cspgraphid = @cspgraphid,
         @cspgraphnodeid = @cspgraphnodeid,
         @csplogtypecode = 1,
         @csplogstringshort = 'DQ Issues - Exceptions ' ,
         @csplogstringlong = @logstr,
         @csprecordcount = 0 /* no records failed */ ;
     End
      set @tableCount -= 1
       End
 End
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[DeleteCspLogStreamMetricMeasure]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[DeleteCspLogStreamMetricMeasure];
GO

CREATE PROCEDURE [ops].[DeleteCspLogStreamMetricMeasure] @CspLogMetricIdLeft INT=0, @CspLogMetricIdRight INT=0
AS
BEGIN
    DECLARE @ResultStr AS VARCHAR (255);
    IF (@CspLogMetricIdLeft = 0)
        BEGIN
            PRINT 'Left Metric ID is not valid - 0 is NOT acceptable';
            THROW 51001, 'Delete Abandoned', 1;
        END
    IF (SELECT count(*)
        FROM [ops].[CspLogStreamMetricMeasure]
        WHERE CspLogMetricIdLeft = @CspLogMetricIdLeft
               AND DeleteDateTime IS NULL) = 0
        BEGIN
            PRINT 'Left Metric ID does NOT exist in CspLogStreamMetricMeasure';
            THROW 51001, 'Delete Abandoned', 1;
        END
    IF (@CspLogMetricIdRight <> 0)
       AND ((SELECT count(*)
             FROM [ops].[CspLogStreamMetricMeasure]
             WHERE CspLogMetricIdRight = @CspLogMetricIdRight
                    AND DeleteDateTime IS NULL) = 0)
        BEGIN
            PRINT 'Right Metric ID does NOT exist in CspLogStreamMetricMeasure';
            THROW 51001, 'Delete Abandoned', 1;
        END
    UPDATE ops.[CspLogStreamMetricMeasure]
    SET DeleteDateTime = getdate()
    WHERE CspLogMetricIdLeft = @CspLogMetricIdLeft
           AND CspLogMetricIdRight = @CspLogMetricIdRight
           AND DeleteDateTime IS NULL;
    SET @ResultStr = CAST (@@ROWCOUNT AS VARCHAR (10)) + ' Record(s) Deleted';
    PRINT @ResultStr;
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[InsertCspLogStreamMetric]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[InsertCspLogStreamMetric];
GO

CREATE PROCEDURE [ops].[InsertCspLogStreamMetric] @cspgraphid INT=0, @cspgraphnodeid INT=0, @csplogstringshort VARCHAR (255)='', @csplogstringlong VARCHAR (255)=''
AS
BEGIN
    DECLARE @CspLogMetricId AS INT = 0;
    IF (@cspgraphid = 0)
        BEGIN
            PRINT 'GraphId is not valid - 0 is NOT acceptable';
            THROW 51001, 'Insert Abandoned', 1;
        END
    IF (@cspgraphnodeid = 0)
        BEGIN
            PRINT 'GraphNodeId is not valid - 0 is NOT acceptable';
            THROW 51001, 'Insert Abandoned', 1;
        END
    IF (@csplogstringshort = '')
        BEGIN
            PRINT 'Empty Short String is NOT acceptable';
            THROW 51001, 'Insert Abandoned', 1;
        END
    IF (@csplogstringlong = '')
        BEGIN
            PRINT 'Empty Short String is NOT acceptable';
            THROW 51001, 'Insert Abandoned', 1;
        END
    SELECT @CspLogMetricId = max(a.CspLogMetricId)
    FROM ops.CspLogStreamMetrics AS a
    WHERE @cspgraphid = CSPGraphId
           AND @cspgraphnodeid = CSPGraphNodeId
           AND @csplogstringshort = CSPLogStringShort
           AND @csplogstringlong = CSPLogStringLong;
    IF (@CspLogMetricId) <> 0
        BEGIN
            PRINT 'LogStream Metric Id Exists --> ' + CAST (@CspLogMetricId AS VARCHAR (10));
            THROW 51001, 'Insert Abandoned', 1;
        END
    ELSE BEGIN
            INSERT INTO ops.CspLogStreamMetrics (CSPGraphId, CSPGraphNodeId, CSPLogStringShort, CSPLogStringLong, InsertDateTime, UpdateDateTime, CSPClientId)
            VALUES (@cspgraphid, @cspgraphnodeid, @csplogstringshort, @csplogstringlong, GetDate(), NULL, 5);
            PRINT 'LogStream Metric Id Added';
        END
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[InsertCspLogStreamMetricMeasure]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[InsertCspLogStreamMetricMeasure];
GO

CREATE PROCEDURE [ops].[InsertCspLogStreamMetricMeasure] @CspLogMetricIdLeft INT=0, @CspLogMetricIdRight INT=0, @FailureThreshold DECIMAL (7, 2)=NULL, @MeasureRunsToCompare INT=NULL, @MinRecordCount INT=NULL
AS
BEGIN
    DECLARE @LcLtMode AS VARCHAR (2) = 'LC';
    DECLARE @ResultStr AS VARCHAR (255) = '';
    DECLARE @localFailureThreshold AS DECIMAL (7, 2) = NULL;
    DECLARE @localMeasureRunsToCompare AS INT = NULL;
    DECLARE @localMinRecordCount AS INT = NULL;
    DECLARE @recCount AS INT = 0;
    DECLARE @maxCspMetricMeasureID AS BIGINT = 0;
    SELECT @localFailureThreshold = FailureThreshold,
           @localMeasureRunsToCompare = MeasureRunsToCompare,
           @localMinRecordCount = MinRecordCount
    FROM ops.[CspLogStreamMetricMeasure]
    WHERE @CspLogMetricIdLeft = CspLogMetricIdLeft
           AND @CspLogMetricIdRight = CspLogMetricIdRight
           AND DeleteDateTime IS NULL;
    SET @recCount = @@ROWCOUNT;
    IF (@CspLogMetricIdLeft = 0)
        BEGIN
            PRINT 'Left Metric ID is not valid - 0 is NOT acceptable';
            THROW 51001, 'Insert Abandoned', 1;
        END
    IF (SELECT count(*)
        FROM [ops].[CspLogStreamMetrics]
        WHERE [CspLogMetricId] = @CspLogMetricIdLeft) = 0
        BEGIN
            PRINT 'Left Metric ID does NOT exist in CspLogStreamMetrics';
            THROW 51001, 'Insert Abandoned', 1;
        END
    IF (@CspLogMetricIdRight <> 0)
       AND ((SELECT count(*)
             FROM [ops].[CspLogStreamMetrics]
             WHERE [CspLogMetricId] = @CspLogMetricIdRight) = 0)
        BEGIN
            PRINT 'Right Metric ID does NOT exist in CspLogStreamMetrics';
            THROW 51001, 'Insert Abandoned', 1;
        END
    IF (@FailureThreshold NOT BETWEEN 0 AND 1) BEGIN
            PRINT 'FailureThreshold expected to be between 0 and 1 (0% - Exact Value to 100% - All data lost). Other numbers not acceptable';
            THROW 51001, 'Insert Abandoned', 1;
        END
    IF (@MinRecordCount < 0)
        BEGIN
            PRINT 'Minimum number of records should be a positive integer equal to or greater than 0. If not needed please do not supply the parameter';
            THROW 51001, 'Insert Abandoned', 1;
        END
    IF ((@CspLogMetricIdRight = 0)
        AND (@MeasureRunsToCompare <= 0)
        OR (@MeasureRunsToCompare > 90))
        BEGIN
            PRINT '@MeasureRunsToCompare expected to be between 1 and 90 (1 to 90 previous executions). Other numbers not acceptable';
            THROW 51001, 'Insert Abandoned', 1;
        END
    IF (@CspLogMetricIdRight = 0)
        BEGIN
            PRINT 'LT mode chosen for Left Id - If not intended, use DeleteCspLogStreamMetricMeasure with LeftID as only parameter';
            SET @LcLtMode = 'LT';
        END
    IF (@CspLogMetricIdRight <> 0)
        BEGIN
            PRINT 'LC mode chosen';
            SET @MeasureRunsToCompare = 0;
        END
    SELECT COALESCE (@FailureThreshold, 0) AS FailureThreshold,
           COALESCE (@localFailureThreshold, 0) AS localFailureThreshold,
           COALESCE (@MeasureRunsToCompare, 0) AS MeasureRunsToCompare,
           COALESCE (@localMeasureRunsToCompare, 0) AS localMeasureRunsToCompare,
           COALESCE (@MinRecordCount, 0) AS MinRecordCount,
           COALESCE (@localMinRecordCount, 0) AS localMinRecordCount;
    IF (@recCount > 0)
        BEGIN
            IF (COALESCE (@FailureThreshold, 0) <> COALESCE (@localFailureThreshold, 0)
                OR COALESCE (@MeasureRunsToCompare, 0) <> COALESCE (@localMeasureRunsToCompare, 0)
                OR COALESCE (@MinRecordCount, 0) <> COALESCE (@localMinRecordCount, 0))
                BEGIN
                    UPDATE ops.[CspLogStreamMetricMeasure]
                    SET FailureThreshold = CASE WHEN COALESCE (@localFailureThreshold, 0) <> COALESCE (@FailureThreshold, 0) THEN @FailureThreshold ELSE @localFailureThreshold END,
                           MeasureRunsToCompare = CASE WHEN @CspLogMetricIdRight = 0
                                                            AND COALESCE (@localMeasureRunsToCompare, 0) <> COALESCE (@MeasureRunsToCompare, 0) THEN @MeasureRunsToCompare ELSE @localMeasureRunsToCompare END,
                           MinRecordCount = CASE WHEN COALESCE (@localMinRecordCount, 0) <> COALESCE (@MinRecordCount, 0) THEN @MinRecordCount ELSE @localMinRecordCount END
                    WHERE CspLogMetricIdLeft = @CspLogMetricIdLeft
                           AND CspLogMetricIdRight = @CspLogMetricIdRight;
                END
            ELSE PRINT 'Metric Measure Record already in place. Explicitly delete the previous entry using [ops].[DeleteCspLogStreamMetricMeasure] and add again';
        END
    ELSE BEGIN
            SELECT @maxCspMetricMeasureID = 1 + COALESCE (max(CspMetricMeasureID), 0)
            FROM ops.[CspLogStreamMetricMeasure];
            INSERT INTO ops.[CspLogStreamMetricMeasure] (CspMetricMeasureID, CspLogMetricIdLeft, CspLogMetricIdRight, FailureThreshold, MeasureRunsToCompare, MinRecordCount, InsertDateTime, DeleteDateTime)
            VALUES (@maxCspMetricMeasureID, @CspLogMetricIdLeft, @CspLogMetricIdRight, COALESCE (@FailureThreshold, 0.05), CASE WHEN @LcLtMode = 'LT' THEN COALESCE (@MeasureRunsToCompare, 7) ELSE 1 END, @MinRecordCount, Getdate(), NULL);
            SET @ResultStr = @LcLtMode + ' Record Inserted';
            PRINT @ResultStr;
        END
END
;
GO

-- ----------------------------------------------------------------------------------------------
--  [ops].[UpdateCspLogStreamMetric]
-- ----------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS [ops].[UpdateCspLogStreamMetric];
GO

CREATE PROCEDURE [ops].[UpdateCspLogStreamMetric] @CspLogMetricId INT=0, @cspgraphid INT=0, @cspgraphnodeid INT=0, @csplogstringshort VARCHAR (255)='', @csplogstringlong VARCHAR (255)=''
AS
BEGIN
    IF (@CspLogMetricId = 0)
        BEGIN
            PRINT 'Metric ID is not valid - 0 is NOT acceptable';
            THROW 51001, 'Update Abandoned', 1;
        END
    IF (@cspgraphid = 0)
        BEGIN
            PRINT 'GraphId is not valid - 0 is NOT acceptable';
            THROW 51001, 'Update Abandoned', 1;
        END
    IF (@cspgraphnodeid = 0)
        BEGIN
            PRINT 'GraphNodeId is not valid - 0 is NOT acceptable';
            THROW 51001, 'Update Abandoned', 1;
        END
    IF (@csplogstringshort = '')
        BEGIN
            PRINT 'Empty Short String is NOT acceptable';
            THROW 51001, 'Update Abandoned', 1;
        END
    IF (@csplogstringlong = '')
        BEGIN
            PRINT 'Empty Short String is NOT acceptable';
            THROW 51001, 'Update Abandoned', 1;
        END
    IF (SELECT count(*)
        FROM ops.CspLogStreamMetrics
        WHERE @CspLogMetricId = CspLogMetricId) = 0
        BEGIN
            PRINT 'LogStream Metric Id Does Not Exist --> ' + CAST (@CspLogMetricId AS VARCHAR (10));
            THROW 51001, 'Update Abandoned', 1;
        END
    ELSE BEGIN
            UPDATE ops.CspLogStreamMetrics
            SET CSPGraphId = @cspgraphid,
                   CSPGraphNodeId = @cspgraphnodeid,
                   CSPLogStringShort = @csplogstringshort,
                   CSPLogStringLong = @csplogstringlong,
                   UpdateDateTime = Getdate()
            WHERE @CspLogMetricId = CspLogMetricId;
            PRINT 'LogStream Metric Id Updated';
        END
END
;
GO
