/*
    3 - dummy graph.sql

    Deploying the ops harness into a new Fabric warehouse.

    Three scripts, and nothing else:
        1  check schemas
        2  create everything and seed it
        3  insert a dummy graph and run it    <-- this script

    Script 2 creates every table, function and procedure the harness needs, and seeds
    the five tables that have to hold rows before a first run. This script calls
    those procedures, so script 2 has to have run.

    WHAT THIS IS FOR

    Graph 9001, three nodes in a line, doing nothing of consequence. It exists to
    prove the harness is wired up before you point it at anything real. A clean run
    exercises, in order:

        ops.CSPExecuteGenericGraph    the entry point
        ops.CSPExecGraphPrep          builds the four run time working tables
        ops.CSPManageGraphExecution   decides whether a new execution may start
        ops.CSPStartNewGraphExecution takes the next execution id, opens the run
        ops.CSPManageMasterGraph      logs that this graph has no master graph
        ops.CSPGraphExec              the node loop, walking the segments
        ops.CSPExecGraphNodeTypeSQL   sets the five parameters, runs each node
        ops.CSPSubstituteParams       replaces the ## tokens in each node's SQL
        ops.CSPStreamLogger           writes to CSPLogStream and CSPLogStreamLive
        ops.CSPExecGraphProgress      marks each node done and picks the next
        ops.CSPExecGraphFinalise      counts the nodes, closes the run
        ops.CSPSetGraphExecutionStatus  looks the final code up in CSPExecutionStatus

    THE NODES

        9010  create ops.CSPHarnessSmokeTest and write the first row
        9020  write a second row
        9030  check both earlier rows are there, then write a third

    Node 9030 is the point of the thing. It throws 51001 if nodes 9010 and 9020 did
    not both run under this execution id, which is what you would see if the segment
    chain were broken or the nodes ran out of order. A throw inside a node is caught
    by ops.CSPExecGraphNodeTypeSQL, logged as a node failure and counted by
    ops.CSPExecGraphFinalise, so the failure shows up in the log rather than as a
    stack trace.

    Each node writes the four substituted parameters into the table as text, so one
    SELECT afterwards tells you both that the chain ran and that parameter
    substitution worked. The tokens used are CONTEXTID, RUNID, GRAPHID and
    GRAPHNODEID, all five of which ops.CSPExecGraphNodeTypeSQL sets per node. The
    fifth, MASTERRUNID, is set too but not used here.

    CONVENTIONS, AND WHY

        CSPScheduledItemTypeId   7. ops.CSPGraphExec routes on this value, and
                                 anything other than 7 logs 'Critical Failure' and
                                 exits the loop without executing a thing
        CSPScheduledItemCurrentFlag  1. ops.CSPExecGraphNodeTypeSQL joins on it. A
                                 string not flagged current reports the node as
                                 missing from CSPScheduleGraphNode, which is a
                                 misleading error for what is actually wrong
        CSPScheduleGraphTypeId   4, matching what ops.CSPExecuteSingleItem uses for
                                 an ad hoc graph. Nothing on the execution path
                                 reads it
        CspScriptClassCode       2, ETL, per the mapping in
                                 ops.CSPInsertScheduledItemString
        CSPClientId              7. Cosmetic, nothing reads it
        node id = item id        the convention ops.CSPInsertScheduledItemString
                                 follows when it creates nodes itself

    A node belongs to a graph only through the segments. There is no graph id on
    CSPScheduleGraphNode, and ops.CSPExecGraphPrep discovers the nodes by reading
    CSPScheduleGraphSegment, so a node in no segment never runs.

    Every insert here is preceded by a DELETE of the same key range, so the script is
    safe to re-run. It touches only ids 9001 and 9010 to 9030.

    CURRENT_TIMESTAMP is used rather than GETDATE(), which a Fabric warehouse does not
    support.
*/

-- ==============================================================================================
--  CLEAR ANYTHING LEFT FROM A PREVIOUS ATTEMPT
-- ==============================================================================================

DELETE ops.CSPScheduleGraphSegment WHERE CSPScheduleGraphId = 9001;
GO
DELETE ops.CSPScheduleGraphNode WHERE CSPScheduleGraphNodeId BETWEEN 9010 AND 9030;
GO
DELETE ops.CSPScheduledItemString WHERE CSPScheduledItemId BETWEEN 9010 AND 9030;
GO
DELETE ops.CSPScheduledItem WHERE CSPScheduledItemId BETWEEN 9010 AND 9030;
GO
DELETE ops.CSPScheduleGraph WHERE CSPScheduleGraphId = 9001;
GO

-- ==============================================================================================
--  THE GRAPH
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
    (9001, 4, 'Harness smoke test', 'Three node dummy graph, proves the harness is wired up correctly', CURRENT_TIMESTAMP, NULL, 7);
GO

-- ==============================================================================================
--  THE ITEMS
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
    (9010, 7, 'Smoke test - create', 'Create ops.CSPHarnessSmokeTest and write the first row', CURRENT_TIMESTAMP, NULL, 7, 9010, 2),
    (9020, 7, 'Smoke test - append', 'Write a second row, proving the chain moved on', CURRENT_TIMESTAMP, NULL, 7, 9020, 2),
    (9030, 7, 'Smoke test - check and finish', 'Throw if the first two rows are absent, then write a third', CURRENT_TIMESTAMP, NULL, 7, 9030, 2);
GO

-- ==============================================================================================
--  THE SQL EACH ITEM RUNS, ONE BATCH PER NODE
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
--  9010  create the table and write the first row
--
--  DROP then CREATE rather than a guard, so a re-run starts from a known state. Note
--  this is a plain CREATE TABLE, not a CREATE TABLE AS SELECT. CTAS has to start its
--  own batch, which it would not be doing here.
-- ----------------------------------------------------------------------------------------------

INSERT INTO ops.CSPScheduledItemString
    (
        CSPScheduledItemId,
        CSPScheduledItemString,
        CSPMajorVersion,
        CSPMinorVersion,
        CSPScheduledItemCurrentFlag,
        RecordInsertDateTime,
        RecordUpdateDateTime,
        CSPClientId
    )
VALUES (9010,
'DROP TABLE IF EXISTS ops.CSPHarnessSmokeTest;

CREATE TABLE ops.CSPHarnessSmokeTest (
    RunId        VARCHAR (20) NULL,
    GraphId      VARCHAR (20) NULL,
    NodeId       VARCHAR (20) NULL,
    ContextId    VARCHAR (20) NULL,
    StepName     VARCHAR (20) NULL,
    StepDateTime DATETIME2 (6) NULL
);

INSERT INTO ops.CSPHarnessSmokeTest (RunId, GraphId, NodeId, ContextId, StepName, StepDateTime)
SELECT ''##RUNID##'', ''##GRAPHID##'', ''##GRAPHNODEID##'', ''##CONTEXTID##'', ''create'', CURRENT_TIMESTAMP;
',
1, 0, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  9020  write a second row
-- ----------------------------------------------------------------------------------------------

INSERT INTO ops.CSPScheduledItemString
    (
        CSPScheduledItemId,
        CSPScheduledItemString,
        CSPMajorVersion,
        CSPMinorVersion,
        CSPScheduledItemCurrentFlag,
        RecordInsertDateTime,
        RecordUpdateDateTime,
        CSPClientId
    )
VALUES (9020,
'INSERT INTO ops.CSPHarnessSmokeTest (RunId, GraphId, NodeId, ContextId, StepName, StepDateTime)
SELECT ''##RUNID##'', ''##GRAPHID##'', ''##GRAPHNODEID##'', ''##CONTEXTID##'', ''append'', CURRENT_TIMESTAMP;
',
1, 0, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  9030  check the first two ran, then write a third row
--
--  The semicolon in front of THROW is deliberate. T-SQL wants the statement before a
--  THROW terminated, and this one opens a block.
-- ----------------------------------------------------------------------------------------------

INSERT INTO ops.CSPScheduledItemString
    (
        CSPScheduledItemId,
        CSPScheduledItemString,
        CSPMajorVersion,
        CSPMinorVersion,
        CSPScheduledItemCurrentFlag,
        RecordInsertDateTime,
        RecordUpdateDateTime,
        CSPClientId
    )
VALUES (9030,
'IF (SELECT count(*) FROM ops.CSPHarnessSmokeTest WHERE RunId = ''##RUNID##'') <> 2
BEGIN
    ;THROW 51001, ''Smoke test - nodes 9010 and 9020 did not both run under this execution id'', 1;
END

INSERT INTO ops.CSPHarnessSmokeTest (RunId, GraphId, NodeId, ContextId, StepName, StepDateTime)
SELECT ''##RUNID##'', ''##GRAPHID##'', ''##GRAPHNODEID##'', ''##CONTEXTID##'', ''finish'', CURRENT_TIMESTAMP;
',
1, 0, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ==============================================================================================
--  THE NODES
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
    (9010, 'Smoke test - create', 'Create ops.CSPHarnessSmokeTest and write the first row', 9010, CURRENT_TIMESTAMP, NULL, 7),
    (9020, 'Smoke test - append', 'Write a second row, proving the chain moved on', 9020, CURRENT_TIMESTAMP, NULL, 7),
    (9030, 'Smoke test - check and finish', 'Throw if the first two rows are absent, then write a third', 9030, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ==============================================================================================
--  THE SEGMENTS
--
--  Two edges, 9010 to 9020 to 9030. This is also what tells ops.CSPExecGraphPrep that
--  the three nodes belong to graph 9001 at all.
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
    (9001, 1, 1, 9010, 9020, '9010 to 9020', 'Smoke test - create  ->  Smoke test - append', CURRENT_TIMESTAMP, NULL, 7),
    (9001, 2, 1, 9020, 9030, '9020 to 9030', 'Smoke test - append  ->  Smoke test - check and finish', CURRENT_TIMESTAMP, NULL, 7);
GO

-- ==============================================================================================
--  VERIFY BEFORE RUNNING
-- ==============================================================================================

SELECT 'graph' AS Item, count(*) AS [Rows], '1' AS Expected FROM ops.CSPScheduleGraph WHERE CSPScheduleGraphId = 9001
UNION ALL SELECT 'items',    count(*), '3' FROM ops.CSPScheduledItem        WHERE CSPScheduledItemId BETWEEN 9010 AND 9030
UNION ALL SELECT 'strings',  count(*), '3' FROM ops.CSPScheduledItemString  WHERE CSPScheduledItemId BETWEEN 9010 AND 9030 AND CSPScheduledItemCurrentFlag = 1
UNION ALL SELECT 'nodes',    count(*), '3' FROM ops.CSPScheduleGraphNode    WHERE CSPScheduleGraphNodeId BETWEEN 9010 AND 9030
UNION ALL SELECT 'segments', count(*), '2' FROM ops.CSPScheduleGraphSegment WHERE CSPScheduleGraphId = 9001;
GO

--  This is the join ops.CSPExecGraphNodeTypeSQL uses. Any row it returns is a node
--  that will not find its SQL at run time.

SELECT c.CSPScheduleGraphNodeId
FROM ops.CSPScheduleGraphNode AS c
     LEFT OUTER JOIN
     ops.CSPScheduledItem AS b
     ON c.CSPScheduledItemId = b.CSPScheduledItemId AND b.CSPScheduledItemTypeId = 7
     LEFT OUTER JOIN
     ops.CSPScheduledItemString AS a
     ON a.CSPScheduledItemId = b.CSPScheduledItemId AND a.CSPScheduledItemCurrentFlag = 1
WHERE c.CSPScheduleGraphNodeId BETWEEN 9010 AND 9030
      AND (b.CSPScheduledItemId IS NULL OR a.CSPScheduledItemId IS NULL);

--  expect no rows
GO

-- ==============================================================================================
--  RUN IT
-- ==============================================================================================

EXECUTE ops.CSPExecuteGenericGraph @cspgraphid = 9001;
GO

-- ==============================================================================================
--  WHAT HAPPENED
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
--  Did the nodes run, in order, with their parameters substituted
--
--  Expect three rows reading create, append, finish. RunId, GraphId and ContextId
--  should be the same on all three, NodeId should read 9010, 9020, 9030. A ## left
--  anywhere in those columns means substitution did not happen.
-- ----------------------------------------------------------------------------------------------

SELECT StepName,
       RunId,
       GraphId,
       NodeId,
       ContextId,
       StepDateTime
FROM ops.CSPHarnessSmokeTest
ORDER BY StepDateTime;
GO

-- ----------------------------------------------------------------------------------------------
--  How the harness recorded the run
--
--  CSPExecutionStatusFlag 7 on the graph row is a clean finish. 4 is a failure.
-- ----------------------------------------------------------------------------------------------

SELECT CSPExecutionId,
       CSPContextId,
       CSPGraphId,
       CSPGraphStartDateTime,
       CSPGraphEndDateTime,
       CSPExecutionStatusFlag
FROM ops.CSPExecutionGraph
WHERE CSPGraphId = 9001
ORDER BY CSPExecutionId DESC;
GO

SELECT CSPExecutionId,
       CSPGraphNodeId,
       CSPGraphNodeStartDateTime,
       CSPGraphNodeEndDateTime,
       CSPExecutionStatusFlag,
       CSPRecordsProcessed
FROM ops.CSPExecutionGraphNode
WHERE CSPGraphId = 9001
ORDER BY CSPExecutionId DESC, CSPGraphNodeId;
GO

-- ----------------------------------------------------------------------------------------------
--  The log
--
--  CSPLogTypeCode 1 is information, anything above it is a problem.
-- ----------------------------------------------------------------------------------------------

SELECT CSPLogDateTime,
       CSPExecutionId,
       CSPGraphNodeId,
       CSPLogTypeCode,
       CSPLogStringShort,
       CSPLogStringLong,
       CSPRecordCount
FROM ops.CSPLogStream
WHERE CSPGraphId = 9001
ORDER BY CSPLogDateTime;
GO

--  Anything this returns is worth reading before trusting the deployment.

SELECT CSPLogDateTime,
       CSPExecutionId,
       CSPGraphNodeId,
       CSPLogTypeCode,
       CSPLogStringShort,
       CSPLogStringLong
FROM ops.CSPLogStream
WHERE CSPGraphId = 9001
      AND CSPLogTypeCode > 1
ORDER BY CSPLogDateTime;

--  expect no rows
GO

-- ==============================================================================================
--  RUNNING IT AGAIN
-- ==============================================================================================

--  ops.CSPStartNewGraphExecution will only open a new execution when the last one for
--  the graph finished, was abandoned, or never existed, so a completed run can simply
--  be repeated by executing the procedure again. A run left at status 2, in progress,
--  or 4, failed, blocks the next one and ops.CSPExecGraphPrep throws rather than
--  starting. Clear it with ops.CSPManageGraphExecution and the control flag that
--  suits. Its last three parameters are OUTPUT, so they need variables:
--
--      DECLARE @executionId INT = 0;
--      DECLARE @statusCode INT = 0;
--      DECLARE @reply VARCHAR (100) = '';
--      EXECUTE ops.CSPManageGraphExecution
--              @cspgraphid = 9001,
--              @cspcontextid = 1,
--              @CSPExecutionControlFlag = 4,
--              @cspexecutionid = @executionId OUTPUT,
--              @cspgraphstatuscode = @statusCode OUTPUT,
--              @replyMessage = @reply OUTPUT;
--      SELECT @reply AS ReplyMessage, @statusCode AS StatusBefore;
--
--  The control flag maps to a status: 1 stops, 2 marks failed, 3 restarts,
--  4 abandons, 5 completes. 4 is the one that unblocks a stuck run.

-- ==============================================================================================
--  TEARDOWN
-- ==============================================================================================

--  Left commented. Run it once you are satisfied, to take the dummy graph back out.
--  It leaves the execution and log history in place, so drop those rows too if you
--  want the warehouse completely clean.
--
--  DELETE ops.CSPScheduleGraphSegment WHERE CSPScheduleGraphId = 9001;
--  DELETE ops.CSPScheduleGraphNode    WHERE CSPScheduleGraphNodeId BETWEEN 9010 AND 9030;
--  DELETE ops.CSPScheduledItemString  WHERE CSPScheduledItemId BETWEEN 9010 AND 9030;
--  DELETE ops.CSPScheduledItem        WHERE CSPScheduledItemId BETWEEN 9010 AND 9030;
--  DELETE ops.CSPScheduleGraph        WHERE CSPScheduleGraphId = 9001;
--  DROP TABLE IF EXISTS ops.CSPHarnessSmokeTest;
--
--  DELETE ops.CSPExecutionGraphNode   WHERE CSPGraphId = 9001;
--  DELETE ops.CSPExecutionGraph       WHERE CSPGraphId = 9001;
--  DELETE ops.CSPLogStream            WHERE CSPGraphId = 9001;
--  DELETE ops.CSPExecutionParameters  WHERE CSPGraphId = 9001;
