/*
    Build EventStream graph - setup.sql

    Defines graph 7001, a 38 node linear chain mirroring Fabric notebook
    10 - Build EventStream. Run this, then start the graph with:

        EXECUTE ops.CSPExecuteGenericGraph @cspgraphid = 7001;

    Node ids run from 7010 upwards in steps of 10, so there is room to insert a step
    later without renumbering. Scheduled item ids match node ids one for one, which is
    the convention ops.CSPInsertScheduledItemString uses.

    Cells carried across, in notebook order:
        3 setup cells   notebook cells 1, 3 and 4
        34 build cells  one per EventSourceId
        1 summary cell  notebook cell 47

    Left out:
        cells 8, 26, 36, 39 and 40, whose EventSourceId is deleted and rebuilt by a
          later cell, so their output never survives
        cells 2, 12, 37 and 46, which are ad-hoc checks
        cells 0, 48 and 49, which are pyspark rather than SQL

    The node SQL is the notebook's Spark SQL, carried across unchanged. A warehouse
    cannot parse it, so every build node will fail until the SQL is translated. The
    graph mechanics, sequencing, logging and status handling can all be exercised
    before then.

    Inserts use the harness's own positional column order, taken from the inserts in
    ops.CSPExecuteSingleItem, ops.CSPInsertScheduledItemString and
    ops.CspInsertScheduledGraphSegment, so no column names are guessed at.
*/

-- ==============================================================================================
--  0.  PREREQUISITE SEED DATA
--      Skip this section if these two tables are already populated.
-- ==============================================================================================

--  One row only. ops.CSPStartNewGraphExecution increments it to get the next execution id,
--  and an empty table silently yields execution id 0.
IF NOT EXISTS (SELECT 1 FROM ops.CSPNextExecutionId)
    INSERT INTO ops.CSPNextExecutionId VALUES (0);
GO

--  ops.CSPSetGraphExecutionStatus validates against this and throws 51000 otherwise.
IF NOT EXISTS (SELECT 1 FROM ops.CSPExecutionStatus)
    INSERT INTO ops.CSPExecutionStatus VALUES
        (0, 'Not Started'),
        (1, 'Started'),
        (2, 'In Progress'),
        (3, 'Stopped'),
        (4, 'Failed'),
        (5, 'Restarted'),
        (6, 'Abandoned'),
        (7, 'Completed');
GO

-- ==============================================================================================
--  1.  CLEAR ANY PREVIOUS DEFINITION OF THIS GRAPH
--      Makes the script re-runnable. It touches graph 7001 and nodes 7010 to
--      7380 only.
-- ==============================================================================================

DELETE ops.CSPScheduleGraphSegment WHERE CSPScheduleGraphId = 7001;
DELETE ops.CSPScheduleGraphNode   WHERE CSPScheduleGraphNodeId BETWEEN 7010 AND 7380;
DELETE ops.CSPScheduledItemString WHERE CSPScheduledItemId    BETWEEN 7010 AND 7380;
DELETE ops.CSPScheduledItem       WHERE CSPScheduledItemId    BETWEEN 7010 AND 7380;
DELETE ops.CSPScheduleGraph       WHERE CSPScheduleGraphId = 7001;
GO

-- ==============================================================================================
--  2.  THE GRAPH
--      Positions: CSPScheduleGraphId, graph type, name, description,
--                 RecordInsertDateTime, RecordUpdateDateTime, CSPClientId.
--      Graph type 4 is the value ops.CSPExecuteSingleItem uses for an ad-hoc graph. It is
--      the only example in the harness and nothing on the execution path reads it, so
--      change it if your own type list says otherwise.
-- ==============================================================================================

INSERT INTO ops.CSPScheduleGraph
VALUES (7001, 4, N'Build EventStream', N'Mirror of Fabric notebook 10 - Build EventStream', GETDATE(), NULL, 7);
GO

-- ==============================================================================================
--  3.  SCHEDULED ITEMS, THEIR SQL, AND THE GRAPH NODES
--      ops.CSPScheduledItem       (ItemId, TypeId, Name, Description, Inserted, Updated,
--                                  ClientId, ItemId again, ScriptClassTypeCode)
--                                  TypeId 7 is a SQL node. ScriptClassTypeCode 2 is ETL.
--      ops.CSPScheduledItemString (ItemId, SQL, MajorVersion, MinorVersion, CurrentFlag,
--                                  Inserted, Updated, ClientId)
--                                  CurrentFlag must be 1 or the node cannot find its SQL.
--      ops.CSPScheduleGraphNode   (NodeId, Name, Description, ItemId, Inserted, Updated,
--                                  ClientId)
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
--  7010  Setup - lkp.EventSource
--  notebook cell 1
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7010, 7, N'Setup - lkp.EventSource', N'Create and populate the EventSource lookup', GETDATE(), NULL, 7, 7010, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7010,
N'Create or Replace Table lkp.EventSource
(
    EventSourceId   Int,
    EventSourceDescription  Varchar(255)
)
;
Insert into  lkp.EventSource 
Select 1, ''Genesys Calls - MFQ Data''
union all  
Select 2, ''Google Analytics - MFQ Records''
union all  
Select 3, ''Documents Issued - From Relay''
union all  
Select 4, ''Quote Started - Motor Quotes'' -- why policy code linked? 
union all  
Select 5, ''Payments - MFQ Motor Quotes''
union all  
Select 6, ''Payments - CallCentre Motor Quotes''
union all  
Select 7, ''Quotes Abandoned - Motor Quotes''
union all  
Select 8, ''Document Uploads - Motor Quotes''
union all  
Select 9, ''Quote Retrieval - MFQ Motor Quotes''
union all  
Select 10, ''Quote Completion Steps - MFQ Motor Quotes''
union all  
Select 11, ''Policy Transactions (NewArchive) - All Policies''
union all  
Select 12, ''Policy Transactions (MTA History) - All Policies''
union all  
Select 13, ''Policy Renewal Start - All Policies''  
union all  
Select 14, ''Home Quotes Call Centre Events''  
union all  
Select 15, ''Genesys Calls - All calls''
union all  
Select 16, ''Document Chase from Workflow''
union all  
Select 17, ''Events from Applied Renewals''
union all  
Select 18, ''Home Claims''
union all  
Select 19, ''Motor Claims''
union all  
Select 20, ''Customer Portal Login''
union all  
Select 24, ''CC Motor Quotes - Started''
union all  
Select 27, ''CC Motor Quote - Abandoned''
union all  
Select 33, ''Online Home Quote - Retrieved''
union all  
Select 34, ''Online Home Quote - Started''
union all  
Select 35, ''Online Home Quote - Progressed''
union all  
Select 36, ''Online Home Quote - Payment Status Success / Failure''
union all  
Select 37, ''Home Insurance - Document Upload for Verification''
union all  
Select 38, ''Quote Completion Steps - Online Home Quotes''
union all  
Select 39, ''Travel Quotes''
union all  
Select 40, ''Traval Transactions''
union all  
Select 41, ''Travel Renewals / Cancellations''
union all  
Select 42, ''Van Quote Journeys - Started / Retrieved''
union all  
Select 43, ''Van Payment Journey''

;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7010, N'Setup - lkp.EventSource', N'Create and populate the EventSource lookup', 7010, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7020  Setup - ods.EventStream
--  notebook cell 3
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7020, 7, N'Setup - ods.EventStream', N'Create the EventStream table', GETDATE(), NULL, 7, 7020, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7020,
N'Create or Replace Table ods.EventStream 
(
    EventId     BigInt,
    EventSourceId   Int,
    EventSourceReference    Varchar(128),
    SourceQuoteReference    Varchar(128),
    SourcePolicyReference   Varchar(128),
    SourceCustomerReference Varchar(128),
    SourceSystemId          int,
    PolicyTypeGroup         varchar(50),
    EventDateTime           TIMESTAMP,
    EventDate               Date,
    EventTypeId             int,
    EventDescription        varchar(1024)
)',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7020, N'Setup - ods.EventStream', N'Create the EventStream table', 7020, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7030  Setup - ods.EpisodeEventStream
--  notebook cell 4
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7030, 7, N'Setup - ods.EpisodeEventStream', N'Create the EpisodeEventStream table', GETDATE(), NULL, 7, 7030, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7030,
N'Create or Replace Table ods.EpisodeEventStream 
(
    EventId     BigInt,
    EpisodeReference        varchar(20),
    
    SourceEventReference    Varchar(128),
    SourceQuoteReference    Varchar(128),
    SourcePolicyReference   Varchar(128),
    SourceCustomerReference Varchar(128),

    SourceSystemId          int, /* MFQ HFQ Relay */ 
    PolicyTypeGroup         varchar(50), /* Motor Home Van Travel  */

    EventDate               Date,
    EventDateTime           TIMESTAMP,
    
    CampaignId              int   

    /*
    EventDescription        varchar(1024)
    EventTypeId             int,
    EventSourceId   Int,*/

)',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7030, N'Setup - ods.EpisodeEventStream', N'Create the EpisodeEventStream table', 7030, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7040  Source 01 - Genesys Calls - MFQ Data
--  notebook cell 5
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7040, 7, N'Source 01 - Genesys Calls - MFQ Data', N'Delete and rebuild EventSourceId 1', GETDATE(), NULL, 7, 7040, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7040,
N'Delete from ods.EventStream
Where EventSourceId = 1 
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  Row_Number() over (Partition by 1  Order by CallStartDt, MFQQuoteQueryGuid),
        1, /* Genesys - MFQ Linked records */ 
        ConversationId,
        MFQQuoteQueryGuid,
        null,
        2,
        ''Motor'',
        date_trunc(''MINUTE'', CallStartDt),
        cast(CallStartDt as DATE),
        2,
        EventType
from    stg.MFQCallEvents           a 
/* first insert so row_number is as is */',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7040, N'Source 01 - Genesys Calls - MFQ Data', N'Delete and rebuild EventSourceId 1', 7040, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7050  Source 02 - Google Analytics - MFQ Records
--  notebook cell 6
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7050, 7, N'Source 02 - Google Analytics - MFQ Records', N'Delete and rebuild EventSourceId 2', GETDATE(), NULL, 7, 7050, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7050,
N'-- 2. GA clicks

Delete from ods.EventStream
Where EventSourceId = 2 
;
Insert into ods.EventStream
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by WorkDateTime, `MFQ-QuoteQueryGUID1`),
        2, /* GA - MFQ Linked ecords */ 
        ClientID, /* not necessarily unique */ 
        `MFQ-QuoteQueryGUID1` as SourceQuoteReference,
        null,
        2,
        ''Motor'',
        date_trunc(''MINUTE'', WorkDateTime),
        cast(WorkDateTime as DATE),
        2,
        --concat(PagePathGroup, '' - '', PagePath, PageTitle)
        CONCAT( -- changed ED 15/05/26 - to clean EventDescriptions
            PagePathGroup
            , '' - ''
            , CASE 
                WHEN PageTitle = ''ooops | Chill Insurance Ireland'' THEN ''Error''
                ELSE split(PagePath, ''\\?'')[0] 
                END
            )
from    edw.tbl_fact_ga_clicks_GA4  a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
Where   `MFQ-QuoteQueryGUID1` is not null 
and		ClientID not like ''Adwords%'' 
and     PagePathGroup is not null 
/* first insert so row_number is as is */ 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7050, N'Source 02 - Google Analytics - MFQ Records', N'Delete and rebuild EventSourceId 2', 7050, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7060  Source 03 - Documents Issued - From Relay
--  notebook cell 7
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7060, 7, N'Source 03 - Documents Issued - From Relay', N'Delete and rebuild EventSourceId 3', GETDATE(), NULL, 7, 7060, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7060,
N'Delete from ods.EventStream
Where EventSourceId = 3 
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDate, a.PolicyCode),
        3, /* Relay Documents */ 
        EventId, /* not necessarily unique  - Same Document Event goes twice sometimes if two actions happen on same document */ 
        Null,  
        a.PolicyCode,
        PolicyTypeGroup,  
        date_trunc(''MINUTE'', EventDate),
        cast(EventDate as DATE),
        null,
        EventDescription
from    ods.RelayDocumentEvents  a 
join 
        (select PolicyCode, PolicyTypeGroup from edw.tbl_ref_policy 
            Where  PolicyTypeGroup in (''Motor'', ''Home'', ''Van'', ''Other'') 
            Group by PolicyCode, PolicyTypeGroup) b
            on a.PolicyCode = b.PolicyCode 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
Where   EventDescription not like ''Unknown - Saved Document - Cash Receipt No: %'' /* 2026/07/23 Changes - Vijay */ 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7060, N'Source 03 - Documents Issued - From Relay', N'Delete and rebuild EventSourceId 3', 7060, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7070  Source 04 - Quote Started - Motor Quotes
--  notebook cell 9
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7070, 7, N'Source 04 - Quote Started - Motor Quotes', N'Delete and rebuild EventSourceId 4', GETDATE(), NULL, 7, 7070, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7070,
N'Delete from ods.EventStream
Where EventSourceId = 4 
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by QuoteDateTime, SourceSystemQuoteReference),
        4, /* Motor Quotes -- MFQ here -- CC to be added */ 
        SourceSystemQuoteReference, /* One Event to start (may be one more to convert or abandon) */ 
        SourceSystemQuoteReference,  
        null PolicyCode,
        2,
        ''Motor'',  
        date_trunc(''MINUTE'', QuoteDateTime),
        cast(QuoteDateTime as DATE),
        2,
        ''New Business - Quote Started'' 
/*from    ods.MotorCustomerPolicyQuoteLinks  a */
FROM    (select a.QuoteQueryGuid SourceSystemQuoteReference, max(CreatedDateTime) QuoteDateTime
         from   dlk.mfq_quotequery                  a 
         join
                ods.motorcustomerpolicyquotelinks   b 
                    ON QuoteQueryGuid = SourceSystemQuoteReference
         left join /* tbhis is still dodgy? check */ 
                (select QuoteQueryGuid from dlk.mfq_quotequery where RetrieveSessionToken is not null) c 
                    on  a.QuoteQueryGuid = c.QuoteQueryGuid
         Where c.QuoteQueryGuid is null 
         Group by a.QuoteQueryGuid)
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 

;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7070, N'Source 04 - Quote Started - Motor Quotes', N'Delete and rebuild EventSourceId 4', 7070, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7080  Source 24 - CC Motor Quotes - Started
--  notebook cell 10
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7080, 7, N'Source 24 - CC Motor Quotes - Started', N'Delete and rebuild EventSourceId 24', GETDATE(), NULL, 7, 7080, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7080,
N'Delete from ods.EventStream
Where EventSourceId = 24 
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceCustomerReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by StartQuoteDateTime, SourceSystemQuoteReference),
        24, /* Motor Quotes -- CC to be added */ 
        SourceSystemQuoteReference, 
        SourceSystemQuoteReference,  
        PolicyCode,
        Policy_Holder_ID,
        SourceSystemId,
        ''Motor'',  
        date_trunc(''MINUTE'', Date_Calculated),
        cast(Date_Calculated as DATE),
        1,
        Concat(QuoteType, '' - Quote Started - CallCentre'') 
from    ods.MotorCustomerPolicyQuoteLinksdeduped    a 
join    dlk.ext_quotationstorage_policydetails b 
            on  a.SourceSystemQuoteReference = b.Quotation_ID 
            and SourceSystemId = 9
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 

;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7080, N'Source 24 - CC Motor Quotes - Started', N'Delete and rebuild EventSourceId 24', 7080, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7090  Source 05 - Payments - MFQ Motor Quotes
--  notebook cell 11
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7090, 7, N'Source 05 - Payments - MFQ Motor Quotes', N'Delete and rebuild EventSourceId 5', GETDATE(), NULL, 7, 7090, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7090,
N'Delete from ods.EventStream 
Where EventSourceId = 5 
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceCustomerReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by PaymentDate, QuoteQueryGuid),
        5, /* MFQ Payments */ 
        QuoteSummaryGuid, 
        QuoteQueryGuid SourceSystemQuoteReference,  
        null PolicyCode,
        RapierCustomerId,
        2,
        ''Motor'',  
        date_trunc(''MINUTE'', PaymentDate),
        cast(PaymentDate as DATE),
        2,
        Case 
            when PaymentResultType = 1 then ''Payment Successful - Online''
            when PaymentResultType = 2 then ''Payment Failure - Online''
            when PaymentResultType = 3 then ''Payment Abandoned - Online''
        End 
from    (
            select distinct 
                    QuoteSummaryGuid,
                    QuoteQueryGuid,
                    PaymentDate,
                    case 
                        when PaymentType in (0,5) then 1
                        when PaymentType = 4 then 2
                        when PaymentType = 1 then 3
                    end PaymentResultType,
                    b.RapierCustomerId
            FROM    stg.MFQ_Quote_Payments                  a
            join
                    ods.MfqScvLink                          b 
                    on a.QuoteQueryGuid = b.SourceSystemQuoteReference 
        )   a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7090, N'Source 05 - Payments - MFQ Motor Quotes', N'Delete and rebuild EventSourceId 5', 7090, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7100  Source 06 - Payments - CallCentre Motor Quotes
--  notebook cell 13
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7100, 7, N'Source 06 - Payments - CallCentre Motor Quotes', N'Delete and rebuild EventSourceId 6', GETDATE(), NULL, 7, 7100, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7100,
N'Delete from ods.EventStream 
Where EventSourceId = 6 
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by QuoteDateTime, SourceSystemQuoteReference),
        6, /* Call Centre Payments - pick from Sales table */ 
        SourceSystemQuoteReference, /* One Event to start (may be one more to convert or abandon) */ 
        SourceSystemQuoteReference,  
        PolicyCode,
        9,
        ''Motor'',  
        date_trunc(''MINUTE'', QuoteDateTime),
        cast(QuoteDateTime as DATE),
        1,
        ''Payment Successful - Call Centre''
from    (
   		select	SourceSystemQuoteReference, 
				QuoteDateTime,
				PolicyCode
		from	(		
					select	Row_Number() over(Partition by a.PolicyCode, a.Policy_Start_Date Order by QuoteDateTime desc) rno, 
							a.*
					from	ods.motorcustomerpolicyquotelinks	a
					join
							edw.tbl_fact_policy_sales			b 
								on		a.PolicyCode = b.PolicyCode 
								and		ReportingSaleDate between cast(QuoteDateTime as date) and dateadd(day,5,Policy_Start_Date)
					Where	SourceSystemId = 9 
                    and     Channel = ''a) Back Office''
				) x 
		Where	x.rno = 1 
        )   a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7100, N'Source 06 - Payments - CallCentre Motor Quotes', N'Delete and rebuild EventSourceId 6', 7100, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7110  Source 07 - Quotes Abandoned - Motor Quotes
--  notebook cell 14
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7110, 7, N'Source 07 - Quotes Abandoned - Motor Quotes', N'Delete and rebuild EventSourceId 7', GETDATE(), NULL, 7, 7110, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7110,
N'Delete from ods.EventStream 
Where EventSourceId = 7
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceCustomerReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDateTime, SourceSystemQuoteReference),
        7, /* Quotes abandoned */ 
        SourceSystemQuoteReference, /* One Event to start (may be one more to convert or abandon) */ 
        SourceSystemQuoteReference,  
        PolicyCode,
        RapierCustomerId,
        2,
        ''Motor'',  
        date_trunc(''MINUTE'', EventDateTime),
        cast(EventDateTime as DATE),
        2,
        ''Quote Abandoned - Online''
from    (
            select  a.SourceSystemQuoteReference,
                    DateAdd(day,7,case when Policy_Start_Date < ''2000-01-01'' then dateadd(year,datediff( year, Policy_Start_Date, QuoteDatetime)+1,Policy_Start_Date) else Policy_Start_Date end ) as EventDateTime,
                    PolicyCode,
                    c.RapierCustomerId 
            from    ods.motorcustomerpolicyquotelinks                                             a 
            left join 
                    (Select QuoteQueryGuid from ods.MFQQuoteToPolicy Where PaymentType in(5,0))   b  
                        on b.QuoteQueryGuid = a.SourceSystemQuoteReference /* check if the  upper / lower case is failing to join here ##TODO## */
            join
                    ods.MfqScvLink                          c 
                    on a.SourceSystemQuoteReference = c.SourceSystemQuoteReference 
            Where   b.QuoteQueryGuid is NULL
            and     a.SourceSystemId = 2 
            and     CURRENT_TIMESTAMP > DateAdd(day,7,Policy_Start_Date)
        )   a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7110, N'Source 07 - Quotes Abandoned - Motor Quotes', N'Delete and rebuild EventSourceId 7', 7110, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7120  Source 27 - CC Motor Quote - Abandoned
--  notebook cell 15
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7120, 7, N'Source 27 - CC Motor Quote - Abandoned', N'Delete and rebuild EventSourceId 27', GETDATE(), NULL, 7, 7120, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7120,
N'Delete from ods.EventStream 
Where EventSourceId = 27
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDateTime, SourceSystemQuoteReference),
        27, /* Quotes abandoned */ 
        SourceSystemQuoteReference, /* One Event to start (may be one more to convert or abandon) */ 
        SourceSystemQuoteReference,  
        PolicyCode,
        9,
        ''Motor'',  
        date_trunc(''MINUTE'', EventDateTime),
        cast(EventDateTime as DATE),
        1,
        ''Quote Abandoned''
from    (
            select  a.SourceSystemQuoteReference,
                    DateAdd(day,7,case when Policy_Start_Date < ''2000-01-01'' then dateadd(year,datediff( year, Policy_Start_Date, QuoteDatetime)+1,Policy_Start_Date) else Policy_Start_Date end ) as EventDateTime,
                    PolicyCode
            from    ods.motorcustomerpolicyquotelinks                                             a 
            left join 
                    (
                    select	SourceSystemQuoteReference
                    from	(		
                                select	Row_Number() over(Partition by a.PolicyCode, a.Policy_Start_Date Order by QuoteDateTime desc) rno, 
                                        a.SourceSystemQuoteReference
                                from	ods.motorcustomerpolicyquotelinks	a
                                join
                                        edw.tbl_fact_policy_sales		b 
                                            on		a.PolicyCode = b.PolicyCode 
                                            and		ReportingSaleDate between cast(QuoteDateTime as date) and Policy_Start_Date  
                            ) x 
                    Where	x.rno = 1 
                    )   b  
                        on b.SourceSystemQuoteReference = a.SourceSystemQuoteReference /* check if the  upper / lower case is failing to join here ##TODO## */
            Where   b.SourceSystemQuoteReference is NULL
            and     a.SourceSystemId = 9 
            and     CURRENT_TIMESTAMP > DateAdd(day,7,Policy_Start_Date)
        )   a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7120, N'Source 27 - CC Motor Quote - Abandoned', N'Delete and rebuild EventSourceId 27', 7120, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7130  Source 08 - Document Uploads - Motor Quotes
--  notebook cell 16
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7130, 7, N'Source 08 - Document Uploads - Motor Quotes', N'Delete and rebuild EventSourceId 8', GETDATE(), NULL, 7, 7130, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7130,
N'Delete from ods.EventStream 
Where EventSourceId = 8
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDateTime, SourceSystemQuoteReference),
        8, /* Document Upload */ 
        SourceSystemQuoteReference, /* One Event to start (may be one more to convert or abandon) */ 
        SourceSystemQuoteReference,  
        PolicyCode,
        SourceSystemId,
        ''Motor'',  
        date_trunc(''MINUTE'', EventDateTime),
        cast(EventDateTime as DATE),
        null,
        EventDescription
from    (
            select  a.*,
                    b.timestamp as EventDateTime,
                    ErrorMEssage,
                    IsUploaded,
                    concat(case when IsUploaded = 1 then ''Document Upload Success'' else ''Document Upload Failure'' end, '' - '', Type, '' - '', case when Type = ''file'' then ''License'' else Title end) EventDescription
            from    ods.motorcustomerpolicyquotelinksdeduped       a,
                    dlk.MyChill_NewUploadDocumentEvents         b       /* dlk for day 1 -- dlt from then on  ##TODO## */ 
            Where   a.PolicyCode = b.PolicyCode 
            )                                                 y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7130, N'Source 08 - Document Uploads - Motor Quotes', N'Delete and rebuild EventSourceId 8', 7130, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7140  Source 09 - Quote Retrieval - MFQ Motor Quotes
--  notebook cell 17
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7140, 7, N'Source 09 - Quote Retrieval - MFQ Motor Quotes', N'Delete and rebuild EventSourceId 9', GETDATE(), NULL, 7, 7140, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7140,
N'/* dont need GA -- we can do from MFQ itself ! */ 
Delete from ods.EventStream
Where EventSourceId = 9 
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceCustomerReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDateTime, SourceSystemQuoteReference),
        9, /* Motor Quotes -- MFQ */ 
        EventId,
        SourceSystemQuoteReference,  
        PolicyCode,
        RapierCustomerId,
        2,
        ''Motor'',  
        date_trunc(''MINUTE'', EventDateTime),
        cast(EventDateTime as DATE),
        2,
        ''Quote Retrieved''
From    (select     RetrieveSessionToken EventId,
                    a.QuoteQueryGuid SourceSystemQuoteReference,  
                    c.PolicyCode,
                    CreatedDateTime EventDateTime,
                    b.RapierCustomerId
            from	dlk.mfq_quotequery		a
            join
                    ods.MfqScvLink                          b 
                    on a.QuoteQueryGuid = b.SourceSystemQuoteReference
            left join 
                    ods.motorcustomerpolicyquotelinks	c	
                        ON  a.QuoteQueryGuid = c.SourceSystemQuoteReference
            Where   RetrieveSessionToken is not null                          
            Group by RetrieveSessionToken,
                    a.QuoteQueryGuid,  
                    c.PolicyCode,
                    CreatedDateTime,
                    b.RapierCustomerId)                          x 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7140, N'Source 09 - Quote Retrieval - MFQ Motor Quotes', N'Delete and rebuild EventSourceId 9', 7140, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7150  Source 10 - Quote Completion Steps - MFQ Motor Quotes
--  notebook cell 18
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7150, 7, N'Source 10 - Quote Completion Steps - MFQ Motor Quotes', N'Delete and rebuild EventSourceId 10', GETDATE(), NULL, 7, 7150, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7150,
N'Delete from ods.EventStream
Where EventSourceId = 10
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceCustomerReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDateTime, SourceSystemQuoteReference),
        10, /* MFQ Motor Quotes -- Steps */ 
        EventId,
        SourceSystemQuoteReference,  
        PolicyCode,
        RapierCustomerId,
        2,
        ''Motor'',  
        date_trunc(''MINUTE'', EventDateTime),
        cast(EventDateTime as DATE),
        2,
        ''New Business - Quote Progressed''
        /*concat(''Step '', cast(StepId as varchar(3)), '' Complete'')*/
From    (
            select      ClientStepId as EventId,
                        QuoteQueryGuid SourceSystemQuoteReference,  
                        PolicyCode,
                        StepId,
                        EventDateTime,
                        RapierCustomerId
            from	stg.MFQ_Steps_Summary                   a
            join
                    ods.MfqScvLink                          b 
                    on a.QuoteQueryGuid = b.SourceSystemQuoteReference
            JOIN
                    ods.motorcustomerpolicyquotelinks	    c	
                        ON  a.QuoteQueryGuid = c.SourceSystemQuoteReference
            )                          x 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7150, N'Source 10 - Quote Completion Steps - MFQ Motor Quotes', N'Delete and rebuild EventSourceId 10', 7150, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7160  Source 11 - Policy Transactions (NewArchive) - All Policies
--  notebook cell 19
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7160, 7, N'Source 11 - Policy Transactions (NewArchive) - All Policies', N'Delete and rebuild EventSourceId 11', GETDATE(), NULL, 7, 7160, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7160,
N'Delete from ods.EventStream
Where EventSourceId = 11
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by ar_posting_date, ar_policy_code),
        11,
        ar_code,
        Null,
        ar_policy_code,
        p.PolicyTypeGroup,
        to_timestamp(concat(cast(ar_posting_date as varchar(8)),''2359''),''yyyyMMddHHmm''),  
        to_timestamp(cast(ar_posting_date as varchar(8)),''yyyyMMdd''),  
        null,
        ar_trans_description
from    dlk.RBSDATA2_NewArchive a 
JOIN
        ods.Policy              p 
            on a.ar_policy_code = p.PolicyCode
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
Where   ar_cli_type not in (''K'', '''', ''0'', ''2'' , ''C'' , ''E'' ) 
and     ar_posting_date > 19000101
and     ar_trans_description > ''''
and     trim(ar_trans_description) not in (''Transaction Reconciliation'')
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7160, N'Source 11 - Policy Transactions (NewArchive) - All Policies', N'Delete and rebuild EventSourceId 11', 7160, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7170  Source 12 - Policy Transactions (MTA History) - All Policies
--  notebook cell 20
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7170, 7, N'Source 12 - Policy Transactions (MTA History) - All Policies', N'Delete and rebuild EventSourceId 12', GETDATE(), NULL, 7, 7170, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7170,
N'Delete from ods.EventStream
Where EventSourceId = 12
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by  EventDateTime, Hi_pol_code),
        12,
        cast(Hi_trcode as varchar(255)),
        Null,
        cast(Hi_pol_code as varchar(255)),
        b.PolicyTypeGroup,
        EventDateTime /*to_timestamp(cast(Hi_Date * 10000 + Hi_hr * 100 + Hi_min as varchar(12)),''yyyyMMddHHmm'')*/,
        cast(EventDateTime as Date), /*to_timestamp(cast(Hi_Date as varchar(8)),''yyyyMMdd''),  */
        null,
        Hi_note
from    (select Hi_trcode, Hi_pol_code, Hi_note, 
                to_timestamp(cast(case    when trim(Hi_note) in (''Renewal Invited by Insurer'' , ''Policy Lapsed'', ''Policy AutoLapsed'')  
                                    then    Hi_mta_eff_date * 10000 + Hi_mta_eff_time 
                                    else    Hi_Date * 10000 + Hi_hr * 100 + Hi_min end  as varchar(12)),''yyyyMMddHHmm'') as EventDateTime 
        from    dlk.RBSDATA2_MTA_History ) a
JOIN
        ods.Policy                  b
            on  a.Hi_pol_code = b.PolicyCode
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
Where   PolicyTypeGroup not in (''Other'', ''Commercial'')        
and     Hi_note > '''' 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7170, N'Source 12 - Policy Transactions (MTA History) - All Policies', N'Delete and rebuild EventSourceId 12', 7170, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7180  Source 13 - Policy Renewal Start - All Policies
--  notebook cell 21
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7180, 7, N'Source 13 - Policy Renewal Start - All Policies', N'Delete and rebuild EventSourceId 13', GETDATE(), NULL, 7, 7180, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7180,
N'Delete from ods.EventStream
Where EventSourceId = 13
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceCustomerReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by  a.PolicyRenewDateAdj, a.PolicyCode),
        13,
        Case 
            when a.PolicyTypeGroup in (''Home'', ''Motor'', ''Van'') then a.PolicyCode 
            when a.PolicyTypeGroup in (''Travel'') then concat(a.PolicyCode, ''M'') 
            else NULL
        end, /* event source should be a bit more clear */ 
        Null,   
        a.PolicyCode,
        b.ClientCode,
        Case 
            when a.PolicyTypeGroup in (''Home'', ''Motor'', ''Van'') then 1 
            when a.PolicyTypeGroup in (''Travel'') then 5 
            else NULL
        end,              
        a.PolicyTypeGroup,
        dateadd(day, 
               case 
                    when a.PolicyTypeGroup in (''Home'', ''Motor'', ''Van'') then -60
                    when a.PolicyTypeGroup in (''Travel'') then -60
                end, 
            a.PolicyRenewDateAdj),/* 40 days for Home 60 days for the renewal email - motor? */
        dateadd(day,                                                                                                                            
               case 
                    when a.PolicyTypeGroup in (''Home'', ''Motor'', ''Van'') then -60
                    when a.PolicyTypeGroup in (''Travel'') then -60
                end, 
            a.PolicyRenewDateAdj), /* 40 days for Home 60 days for the renewal email - motor? */
        Null,
        ''Policy Renewal Window Started''
from    edw.tbl_fact_policy_sales a 
left join 
        edw.tbl_ref_policy        b 
            on a.PolicyKeyEffDate = b.PolicyKey   
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
Where   a.PolicyRenewDateAdj >= ''2020-01-01''
and     a.PolicyCloseNum = 1 
and     a.EffectiveDate <= ''2026-12-31''
/*and     case 
            when PolicyStatusDesc in (''Lapsed for Transfer'',''Suspended'',''Cancelled'',''Renewal Transfer'',''Cancelled Mid Term'',''Locked'',''Lapsed'',''NB Not Taken Up'',''Temporary'') then 0 
            when PolicyCancelDate < dateadd(day, -60, PolicyRenewDate) then 0 
            else 1 
        end = 1  */           
and     a.PolicyTypeGroup not in (''Other'', ''Commercial'')        
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7180, N'Source 13 - Policy Renewal Start - All Policies', N'Delete and rebuild EventSourceId 13', 7180, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7190  Source 14 - Home Quotes Call Centre Events
--  notebook cell 22
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7190, 7, N'Source 14 - Home Quotes Call Centre Events', N'Delete and rebuild EventSourceId 14', GETDATE(), NULL, 7, 7190, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7190,
N'Delete from ods.EventStream
Where EventSourceId = 14
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by  EventDateTime, a.PolicyCode),
        14,
        EventSourceReference,
        QuoteId,
        a.PolicyCode,
        4,
        ''Home'',
        date_trunc(''MINUTE'', EventDateTime),
        EventDate,
        1,
        case 
                when EventDate > SaleDate then
                         case 
                                when EventDescription = ''New Business - Quotation Provided'' then ''Renewal Confirmation - Quotation Provided''
                                when EventDescription = ''New Business - New Business Policy Accepted'' then ''Renewal Confirmation - Policy Renewal Accepted''
                                Else EventDescription
                         end 
                else     EventDescription
        end as EventDescription                                                                             
from    (
           select   upper(a.PolicyId) EventSourceReference, /* upper lower issues to be resolved in dlk ##TODO## */ 
                    b.QuoteId, 
                    a.PolicyCode,
                    TransactionDate EventDateTime, 
                    cast(TransactionDate as date) EventDate, 
                    concat(a.BusinessProcess, '' - '', a.EventType) EventDescription,
                    coalesce(FirstSaleDate, FirstRenewalDate) SaleDate,
                    FirstRenewalDate /* unused but let us keep it for now */  
            from   dlk.EXT_Home_QS_PolicyDetails   a 
            left join 
                    dlk.EXT_Home_QS_QuoteDetails    b 
                        on  Upper(a.RiskId) = b.HomeRiskId 
                        and a.PolicyNumber = left(b.QuoteReference,17)
            left join 
                     (
                        select PolicyCode, 
                                min(case when PolicyStatusCode = ''N'' then ReportingSaleDate else null end) FirstSaleDate, 
                                min(case when PolicyStatusCode = ''R'' then ReportingSaleDate else null end) FirstRenewalDate 
                        from    edw.tbl_fact_policy_sales 
                        where   PolicyTypeGroup = ''Home''  
                        Group by PolicyCode
                    ) c 
                        on a.PolicyCode = c.PolicyCode 
        )       a 

cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;
/*
Non Full Cycle Manual Rebroke - Quotation Provided
Renewal Transfer - Renewal Transfer Accepted
Renewal Transfer - New Business Referral Submitted
Remove From Full-Cycle - Quotation Provided
Renewal Confirmation - Renewal Referral Submitted
New Business - New Business Referral Submitted
Permanent Mid Term Adjustment - Permanently Adjusted Policy
New Business - Quotation Provided
Unknown - Quotation Provided
Mid-term Cancellation - Quotation Provided
Mid-term Cancellation - New Business Referral Submitted
Mid-term Cancellation - Policy Cancelled
Permanent Mid Term Adjustment - Quotation Provided
Renewal Confirmation - Policy Renewal Accepted
Permanent Mid Term Adjustment - Mid Term Adjustment Referral Submitted
Lapse - Policy Lapsed
New Business - New Business Policy Accepted
Renewal Confirmation - Quotation Provided
Lapse - Quotation Provided

New Business - Quotation Provided
New Business - New Business Policy Accepted

Renewal Confirmation - Quotation Provided
Renewal Confirmation - Policy Renewal Accepted
*/',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7190, N'Source 14 - Home Quotes Call Centre Events', N'Delete and rebuild EventSourceId 14', 7190, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7200  Source 15 - Genesys Calls - All calls
--  notebook cell 23
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7200, 7, N'Source 15 - Genesys Calls - All calls', N'Delete and rebuild EventSourceId 15', GETDATE(), NULL, 7, 7200, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7200,
N'Delete from ods.EventStream
Where EventSourceId = 15 
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by conversationStartTime, conversationid, sessionIndex),
        15, /* Quote Linked Documents */ 
        concat(conversationid, '':'', sessionIndex), /* not necessarily unique  - Same conversation has multiple purposes sometimes */ 
        conversationid,  
        NULL,
        case 
            when lower(CallPurpose) like ''qd_%'' Then null
            when lower(CallPurpose) like ''%van%'' Then ''Van''
            when lower(CallPurpose) like ''%home%'' Then ''Home''
            when lower(CallPurpose) like ''%motor%'' Then ''Motor''
            when lower(CallPurpose) like ''%car%'' and lower(CallPurpose) not like ''%care%'' Then ''Motor''
            when lower(CallPurpose) like ''%car%'' and lower(CallPurpose) not like ''%care%'' Then ''Motor''
            when lower(CallPurpose) like ''%vehicle%''  Then ''Motor''
            else ''Customer''
        end,  
        date_trunc(''MINUTE'', conversationStartTime),
        cast(conversationStartTime as DATE),
        1,
        concat(OriginatingDirection, '' - '', coalesce(CallPurpose,'''')) 
from    ods.CustomerCallEvents  a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
Where   lower(CallPurpose) not like ''qd_%'' 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7200, N'Source 15 - Genesys Calls - All calls', N'Delete and rebuild EventSourceId 15', 7200, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7210  Source 16 - Document Chase from Workflow
--  notebook cell 24
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7210, 7, N'Source 16 - Document Chase from Workflow', N'Delete and rebuild EventSourceId 16', GETDATE(), NULL, 7, 7210, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7210,
N'Delete from ods.EventStream
Where EventSourceId = 16 
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by `Timestamp`, Attempts),
        16, /* Quote Linked Documents */ 
        concat(rk,a.PolicyCode),
        null,  
        a.PolicyCode,
        PolicyTypeGroup,  
        date_trunc(''MINUTE'', `Timestamp`),
        cast(`Timestamp` as DATE),
        null,
        concat(DiaryTypeID, '' - '', Title, '':- Attempt - '', Attempts, '' - '', case when IsAccepted = 1 then ''Accepted'' when IsRejected = 1 then ''Rejected'' else '''' end) 
from    dlk.MyChillWorkflow_DocumentStatus  a 
left join 
        ods.Policy x  on a.PolicyCode = x.PolicyCode
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z         
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7210, N'Source 16 - Document Chase from Workflow', N'Delete and rebuild EventSourceId 16', 7210, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7220  Source 17 - Events from Applied Renewals
--  notebook cell 25
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7220, 7, N'Source 17 - Events from Applied Renewals', N'Delete and rebuild EventSourceId 17', GETDATE(), NULL, 7, 7220, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7220,
N'Delete from ods.EventStream
Where EventSourceId = 17
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDateTime),
        17, /* Quote Linked Documents */ 
        EventSourceReference, 
        null,  
        PolicyCode,
        PolicyTypeGroup,  
        date_trunc(''MINUTE'', EventDateTime),
        cast(EventDateTime as DATE),
        null,
        EventDescription
from    (
            select a.SessionId EventSourceReference,
                    a.PolicyCodeForRenewal PolicyCode,
                    x.PolicyTypeGroup,  
                    `Timestamp` as EventDateTime,
                    concat(''Renewal - Payment Failure - '', PaymentErrorMessage) as EventDescription
            from    dlk.appliedrenewals_paymentfailedevent  a 
            left join 
                    ods.policy x  on a.PolicyCodeForRenewal = x.PolicyCode
            Where len(PolicyCodeForRenewal) > 6 
            union
            select  a.SessionId,
                    a.PolicyCodeForRenewal,
                    x.PolicyTypeGroup,  
                    `Timestamp`,
                    concat(''Renewal - Payment Success - '', a.PaymentType)
            from    dlk.appliedrenewals_paymentsuccess  a 
            left join 
                    ods.policy x  on a.PolicyCodeForRenewal = x.PolicyCode
            Where len(PolicyCodeForRenewal) > 6 
            ) a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z         
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7220, N'Source 17 - Events from Applied Renewals', N'Delete and rebuild EventSourceId 17', 7220, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7230  Source 18 - Home Claims
--  notebook cell 27
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7230, 7, N'Source 18 - Home Claims', N'Delete and rebuild EventSourceId 18', GETDATE(), NULL, 7, 7230, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7230,
N'/* since quote for cc home is one record per insurer, removing the quotedetails */ 
Delete from ods.EventStream
Where EventSourceId = 18
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDateTime),
        18, /* Quote Linked Documents */ 
        HomeClaimId EventSourceReference, 
        PolicyId,  
        PolicyCode,
        ''Home'',  
        date_trunc(''MINUTE'', EventDateTime),
        cast(EventDateTime as DATE),
        1,
        EventDescription
from    (
            Select  c.PolicyId, 
                    b.HomeClaimId,
                    c.TransactionDate EventDateTime,
                    c.PolicyCode,
                    concat( 
                            case when Settled = ''Yes'' then ''1 - Claim - '' else ''0 - Claim - '' end,
                            HomeClaimType /*,	
                            '' - Amount - '',
                            cast(HomeClaimAmount as varchar(15))*/
                            )	EventDescription
            FROM    dlk.EXT_Home_QS_ClaimDetails		b,
                    dlk.EXT_Home_QS_PolicyDetails		c
            Where   b.HomeRiskId = upper(c.RiskId) /* UPPER should have been implemented in the dlk data ##TODO##*/ 
            Group by c.PolicyId, 
                    b.HomeClaimId,
                    c.TransactionDate,
                    c.PolicyCode,
                    concat( 
                            case when Settled = ''Yes'' then ''1 - Claim - '' else ''0 - Claim - '' end,
                            HomeClaimType    /* -- Remove Claim amount -- Vijay 2026/07/23  
                            '' - Amount - '',
                            cast(HomeClaimAmount as varchar(15))   -- Remove Claim amount -- Vijay 2026/07/23 */ 
                            )	
            ) a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z         
;             

/* Please note that a single home policycode links with hundreds of quote records and so results in multiple claim records -- 1 per quote but 100 per policy
        this needs to be covered in downstream builds
-- if this fails - fix -- refer to previous cell 
*/',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7230, N'Source 18 - Home Claims', N'Delete and rebuild EventSourceId 18', 7230, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7240  Source 19 - Motor Claims
--  notebook cell 28
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7240, 7, N'Source 19 - Motor Claims', N'Delete and rebuild EventSourceId 19', GETDATE(), NULL, 7, 7240, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7240,
N'Delete from ods.EventStream
Where EventSourceId = 19
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDate),
        19, /* Motor Claims */ 
        PolicyCode EventSourceReference, 
        null,  
        PolicyCode,
        ''Motor'',  
        date_trunc(''MINUTE'', EventDate),
        cast(EventDate as DATE),
        null,
        EventDescription
from    (
            select  EventDate,
                    PolicyCode,
                    concat( ''Claim - '',
                            Case 
                                when ClaimType = ''A'' then   ''Accident''
                                when ClaimType = ''D'' then   ''Accidental Damage''
                                when ClaimType = ''F'' then   ''Fire''
                                when ClaimType = ''M'' then   ''Malicious damage as a result of theft''
                                when ClaimType = ''P'' then   ''Personal Accident''
                                when ClaimType = ''E'' then   ''Personal Effects''
                                when ClaimType = ''T'' then   ''Theft''
                                when ClaimType = ''V'' then   ''Vandalism''
                                when ClaimType = ''W'' then   ''Windscreen''
                                when ClaimType = ''B'' then   ''Third Party''
                                when ClaimType = ''O'' then   ''Other''
                                when ClaimType = ''G'' then   ''Fuel Claim''
                                else ''Unknown Claim Code''
                            end  /* ,
                            '' - '',
                            cast(ClaimValue as varchar(30))    -- Remove Claim amount -- Vijay 2026/07/23 */ 
                    ) as EventDescription
            from    stg.MotorClaims 
            ) a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z         
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7240, N'Source 19 - Motor Claims', N'Delete and rebuild EventSourceId 19', 7240, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7250  Source 20 - Customer Portal Login
--  notebook cell 29
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7250, 7, N'Source 20 - Customer Portal Login', N'Delete and rebuild EventSourceId 20', GETDATE(), NULL, 7, 7250, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7250,
N'Delete from ods.EventStream
Where EventSourceId = 20
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceCustomerReference,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDateTime),
        20, /* Login Events */ 
        EventSourceReference, 
        null,  
        null,
        ClientCode,
        ''Customer'',  
        date_trunc(''MINUTE'', EventDateTime),
        cast(EventDateTime as DATE),
        null,
        EventDescription
from    (
            select  concat(SessionId,''-'',Id) EventSourceReference,
                    `Timestamp` EventDateTime,
                    PortfolioCode ClientCode,
                    ''Login Successful'' EventDescription
            from    dlk.AppliedRenewals_SuccessfulLoginEvent
            Where	len(PortfolioCode) = 6
            union all 

            select  concat(SessionId,''-'',Id) EventSourceReference,
                    `Timestamp` EventDateTime,
                    PortfolioCode ClientCode,
                    ''Login Locked'' EventDescription
            from	dlk.AppliedRenewals_FailedLoginEvent 
            Where	len(PortfolioCode) = 6 
            and		isLocked = 1
            union all 

            select  concat(SessionId,''-'',Id) EventSourceReference,
                    `Timestamp` EventDateTime,
                    PortfolioCode ClientCode,
                    ''Login Failed'' EventDescription
            from	dlk.AppliedRenewals_FailedLoginEvent 
            Where	len(PortfolioCode) = 6 
            ) a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z         
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7250, N'Source 20 - Customer Portal Login', N'Delete and rebuild EventSourceId 20', 7250, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7260  Source 33 - Online Home Quote - Retrieved
--  notebook cell 30
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7260, 7, N'Source 33 - Online Home Quote - Retrieved', N'Delete and rebuild EventSourceId 33', GETDATE(), NULL, 7, 7260, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7260,
N'Delete from ods.EventStream 
Where EventSourceId = 33
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDateTime, QuoteReference),
        33, /* Document Upload */ 
        QuoteReference, 
        QuoteReference,  
        null,
        3,
        ''Home'',  
        date_trunc(''MINUTE'', EventDateTime),
        cast(EventDateTime as DATE),
        2,
        ''Quote Retrieved''
from    (
            select  QuoteCodeReference as QuoteReference,
                     timestamp_seconds(try_cast(ts as numeric)) as EventDateTime
            from    dlk.hfq_quotedetails  a 
            Where   RetrieveCount > 0 
            union 
            select  QuoteCodeReference as QuoteReference,
                     timestamp_seconds(try_cast(_ts as numeric)) as EventDateTime
            from    dlk.hfq_quotedetails_snapshot_v2  a 
            Where   RetrieveCount > 0 
            )                                                 y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7260, N'Source 33 - Online Home Quote - Retrieved', N'Delete and rebuild EventSourceId 33', 7260, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7270  Source 34 - Online Home Quote - Started
--  notebook cell 31
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7270, 7, N'Source 34 - Online Home Quote - Started', N'Delete and rebuild EventSourceId 34', GETDATE(), NULL, 7, 7270, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7270,
N'Delete from ods.EventStream 
Where EventSourceId = 34
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDateTime, QuoteReference),
        34, /* Document Upload */ 
        QuoteReference, 
        QuoteReference,  
        null,
        3,
        ''Home'',  
        date_trunc(''MINUTE'', EventDateTime),
        cast(EventDateTime as DATE),
        2,
        ''New Business - Quote Started''
from    (
            select distinct id as QuoteReference,
                    CreatedOn as EventDateTime
            from    dlk.hfq_quotedetails  a
            union 
            select distinct id as QuoteReference,
                    CreatedOn as EventDateTime
            from    dlk.hfq_quotedetails_snapshot_v2  a              

            )                                                 y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7270, N'Source 34 - Online Home Quote - Started', N'Delete and rebuild EventSourceId 34', 7270, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7280  Source 35 - Online Home Quote - Progressed
--  notebook cell 32
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7280, 7, N'Source 35 - Online Home Quote - Progressed', N'Delete and rebuild EventSourceId 35', GETDATE(), NULL, 7, 7280, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7280,
N'Delete from ods.EventStream 
Where EventSourceId = 35
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDateTime, QuoteReference),
        35, /* Document Upload */ 
        QuoteReference, 
        QuoteReference,  
        null,
        3,
        ''Home'',  
        date_trunc(''MINUTE'', EventDateTime),
        cast(EventDateTime as DATE),
        2,
        ''New Business - Quote Progressed''
from    (
            select distinct id as QuoteReference,
                    timestamp_seconds(try_cast(ts as numeric)) as EventDateTime
            from    dlk.hfq_quotedetails  a 
            Where   CreatedOn < timestamp_seconds(try_cast(ts as numeric))
            union 
            select distinct id as QuoteReference,
                    timestamp_seconds(try_cast(_ts as numeric)) as EventDateTime
            from    dlk.hfq_quotedetails_snapshot_v2  a 
            Where   CreatedOn < timestamp_seconds(try_cast(_ts as numeric))
            )                                                 y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7280, N'Source 35 - Online Home Quote - Progressed', N'Delete and rebuild EventSourceId 35', 7280, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7290  Source 36 - Online Home Quote - Payment Status Success / Failure
--  notebook cell 33
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7290, 7, N'Source 36 - Online Home Quote - Payment Status Success / Failure', N'Delete and rebuild EventSourceId 36', GETDATE(), NULL, 7, 7290, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7290,
N'Delete from ods.EventStream 
Where EventSourceId = 36
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDateTime, QuoteReference),
        36, /* Document Upload */ 
        QuoteReference, 
        QuoteReference,  
        PolicyCode,
        3,
        ''Home'',  
        date_trunc(''MINUTE'', EventDateTime),
        cast(EventDateTime as DATE),
        2,
        EventDescription
from    (
            select  a.QuoteReference,
                    b.PolicyCode,
                    action_time_created as EventDateTime,
                    Case when a.Status = ''CAPTURED'' then ''Payment Success'' 
                        when a.Status = ''DECLINED'' then ''Payment Failure''
                    end as EventDescription
            from    dlk.hfq_paymentresponse_response        a,
                    (select QuoteCodeReference, PolicyCode from dlk.hfq_sales)  b
            Where   a.QuoteReference = b.QuoteCodeReference  
            Group by a.QuoteReference,
                    b.PolicyCode,
                    action_time_created,
                    Case when a.Status = ''CAPTURED'' then ''Payment Success'' 
                        when a.Status = ''DECLINED'' then ''Payment Failure''
                    end
            )                                                 y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7290, N'Source 36 - Online Home Quote - Payment Status Success / Failure', N'Delete and rebuild EventSourceId 36', 7290, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7300  Source 37 - Home Insurance - Document Upload for Verification
--  notebook cell 34
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7300, 7, N'Source 37 - Home Insurance - Document Upload for Verification', N'Delete and rebuild EventSourceId 37', GETDATE(), NULL, 7, 7300, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7300,
N'Delete from ods.EventStream 
Where EventSourceId = 37
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDateTime, PolicyCode),
        37, /* Document Upload */ 
        pk, 
        Null,  
        PolicyCode,
        4,
        ''Home'',  
        date_trunc(''MINUTE'', EventDateTime),
        cast(EventDateTime as DATE),
        null,
        EventDescription
from    (
            select  a.PolicyCode,
                    pk,
                    b.`Timestamp` as EventDateTime,
                    concat(case when IsUploaded = 1 then ''Document Upload Success'' else ''Document Upload Failure'' end, '' - '', Type, '' - '', Title) EventDescription
            from    ods.policy                              a,
                    dlk.mychill_newuploaddocumentevents     b       
            Where   a.PolicyCode = b.PolicyCode 
            and     a.PolicyTypeGroup = ''Home''  

            )                                                 y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7300, N'Source 37 - Home Insurance - Document Upload for Verification', N'Delete and rebuild EventSourceId 37', 7300, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7310  Source 38 - Quote Completion Steps - Online Home Quotes
--  notebook cell 35
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7310, 7, N'Source 38 - Quote Completion Steps - Online Home Quotes', N'Delete and rebuild EventSourceId 38', GETDATE(), NULL, 7, 7310, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7310,
N'Delete from ods.EventStream 
Where EventSourceId = 38
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by EventDateTime, QuoteCodeReference),
        38, /* Document Upload */ 
        QuoteCodeReference, 
        QuoteCodeReference,  
        Null PolicyCode,
        3,
        ''Home'',  
        date_trunc(''MINUTE'', EventDateTime),
        cast(EventDateTime as DATE),
        2,
        ''Quote Progressed''
from    (
            select  QuoteCodeReference, 
                    LastStep, 
                    min(timestamp_seconds(try_cast(ts as numeric))) EventDateTime 
            from dlk.HFQ_QuoteDetails 
            Group by QuoteCodeReference, 
                    LastStep
            union 
            select  QuoteCodeReference, 
                    LastStep, 
                    min(timestamp_seconds(try_cast(_ts as numeric))) EventDateTime 
            from dlk.HFQ_QuoteDetails_snapshot_v2
            Group by QuoteCodeReference, 
                    LastStep
            )                                                 y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7310, N'Source 38 - Quote Completion Steps - Online Home Quotes', N'Delete and rebuild EventSourceId 38', 7310, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7320  Source 39 - Travel Quotes
--  notebook cell 38
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7320, 7, N'Source 39 - Travel Quotes', N'Delete and rebuild EventSourceId 39', GETDATE(), NULL, 7, 7320, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7320,
N'Delete from ods.EventStream 
Where EventSourceId = 39
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by travel_quoteDate, Quote_number),
        39, /* Document Upload */ 
        Quote_number, 
        Quote_number,  
        Null PolicyCode,
        8,
        ''Travel'',  
        date_trunc(''MINUTE'', travel_quoteDate),
        cast(travel_quoteDate as DATE),
        null,
        CONCAT(business_type, '' - '', travel_certificatestatus)
        case when travel_certificatestatus in (''Completed Quote'', ''Cancelled'', ''Live'') and business_type = ''New Business'' then ''''
from    (        
                    select  Quote_number,
                            travel_certificatestatus,
                            travel_quoteDate,
                            business_type
                    from    dlk.EXT_Travel_Quotes
                    Where   Quote_number <> 0 
                    UNION
                    select  Quote_number,
                            travel_certificatestatus,
                            travel_quoteDate,
                            business_type
                    from    dlk.EXT_Travel_Quotes_AllQuotesFile
                    Where   Quote_number <> 0 
                    and     Quote_number not in (select Quote_number from dlk.EXT_Travel_Quotes)
                )       y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7320, N'Source 39 - Travel Quotes', N'Delete and rebuild EventSourceId 39', 7320, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7330  Source 45 - Unknown source
--  notebook cell 41
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7330, 7, N'Source 45 - Unknown source', N'Delete and rebuild EventSourceId 45', GETDATE(), NULL, 7, 7330, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7330,
N'/* Quote Abandoned */ 
Delete from ods.EventStream 
Where EventSourceId = 45
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceCustomerReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by travel_quoteDate, Quote_number),
        45, /* Document Upload */ 
        Quote_number, 
        Quote_number,  
        Null PolicyCode,
        Null SourceCustomerReference,
        5,
        ''Travel'',  
        date_trunc(''MINUTE'', travel_quoteDate),
        cast(travel_quoteDate as DATE),
        null,
        EventDescription
from    (        
                    select  x.Quote_number,
                            x.travel_quoteDate,
                            concat(case when x.RenewalFlag = 1 then ''Renewal'' else ''New Business'' end, '' - '', ''Quote abandoned'') EventDescription
                    From    (   Select  Quote_number,
                                        travel_quoteDate,
                                        max(RenewalFlag) RenewalFlag
                                From    (   select  Quote_number,
                                                    travel_quoteDate,
                                                    case when business_type = ''New Business'' then 0 else 1 end RenewalFlag
                                            from    dlk.EXT_Travel_Quotes  
                                            Where   Quote_Number <> 0 
                                            AND     travel_certificatestatus IN (''Completed Quote'' , ''Cancelled'',''Incomplete Quote'')
                                            UNION
                                            select  Quote_number,
                                                    travel_quoteDate,
                                                    case when business_type = ''New Business'' then 0 else 1 end RenewalFlag
                                            from    dlk.EXT_Travel_Quotes_AllQuotesFile
                                            Where   Quote_number <> 0 
                                            AND     travel_certificatestatus IN (''Completed Quote'' , ''Cancelled'',''Incomplete Quote'')
                                            UNION 
                                            Select  QuoteId,
                                                    UpdatedDate,
                                                    RenewalFlag
                                            from    dlk.ext_travel_policy_trans  
                                            Where   QuoteId > 0
                                            and     RecordType = ''U'' /* record type U always aligned on the same quote or policy id so we can ignore for now */
                                            )   m 
                                Group BY  Quote_number,
                                        travel_quoteDate                                            
                                        )   x 
                    Left join 
                            dlk.ext_travel_policy y on     x.Quote_number = y.QuoteId
                    Where   y.QuoteId is null 
                    Group by  
                            x.Quote_number,
                            x.travel_quoteDate,
                            concat(case when x.RenewalFlag = 1 then ''Renewal'' else ''New Business'' end, '' - '', ''Quote abandoned'') 
                )       a  
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
; 

/*
New Business - Web - Quote Initiated
New Business - Call Centre - Quote Initiated

Renewal - Web - Quote Initiated
Renewal - Call Centre - Quote Initiated
*/',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7330, N'Source 45 - Unknown source', N'Delete and rebuild EventSourceId 45', 7330, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7340  Source 40 - Traval Transactions
--  notebook cell 42
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7340, 7, N'Source 40 - Traval Transactions', N'Delete and rebuild EventSourceId 40', GETDATE(), NULL, 7, 7340, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7340,
N'Delete from ods.EventStream 
Where EventSourceId = 40
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceCustomerReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by PurchaseDate, PolicyId ),
        40, 
        PolicyId, /* some quote are 0 */ 
        QuoteId,  
        PolicyId,
        MapfreCustomerId,
        5,
        ''Travel'',  
        date_trunc(''MINUTE'', PurchaseDate),
        cast(PurchaseDate as DATE),
        null,
        CONCAT(Channel, '' - '', case when RenewalFlag = 1 then ''Renewal'' else ''New Business'' end, '' - '', ''Purchase'')
from    (        
                    select  QuoteId,
                            PolicyId,
                            MapfreCustomerId,
                            PurchaseDate,
                            `Source` as Channel, 
                            RenewalFlag 
                    from    dlk.EXT_Travel_Policy_Trans
                    Where   VoidFlag = 0  
                    and     RecordType <>''U'' 
                    and     CreatedDate > ''2020-01-01''
                    Group by QuoteId,
                            PolicyId,
                            MapfreCustomerId,
                            PurchaseDate,
                            `Source` , 
                            RenewalFlag                    
                )       y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7340, N'Source 40 - Traval Transactions', N'Delete and rebuild EventSourceId 40', 7340, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7350  Source 41 - Travel Renewals / Cancellations
--  notebook cell 43
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7350, 7, N'Source 41 - Travel Renewals / Cancellations', N'Delete and rebuild EventSourceId 41', GETDATE(), NULL, 7, 7350, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7350,
N'Delete from ods.EventStream 
Where EventSourceId = 41
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by VoidDate, PolicyId),
        41, 
        QuoteId, 
        PolicyId,  
        Null PolicyCode,
        8,
        ''Travel'',  
        date_trunc(''MINUTE'', VoidDate),
        cast(VoidDate as DATE),
        null,
        CONCAT(Channel, '' - '', case when RenewalFlag = 1 then ''Renewal'' else ''New Business'' end, '' - '', ''Cancelled'')
from    (   
            select	QuoteId,
                    PolicyId,
                    MapfreCustomerId,
                    VoidDate,
                    Source as Channel, 
                    RenewalFlag 
            from	dlk.EXT_Travel_Policy_Trans
            Where   VoidFlag = 1   
            Group by 
                    QuoteId,
                    PolicyId,
                    MapfreCustomerId, 
                    VoidDate,
                    Source, 
                    RenewalFlag 
                )       y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7350, N'Source 41 - Travel Renewals / Cancellations', N'Delete and rebuild EventSourceId 41', 7350, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7360  Source 42 - Van Quote Journeys - Started / Retrieved
--  notebook cell 44
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7360, 7, N'Source 42 - Van Quote Journeys - Started / Retrieved', N'Delete and rebuild EventSourceId 42', GETDATE(), NULL, 7, 7360, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7360,
N'Delete from ods.EventStream 
Where EventSourceId = 42
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by QuoteStartDateTime, QuoteReference),
        42, 
        SessionId, 
        QuoteReference ,  
        Null PolicyCode,
        7,
        ''Van'',  
        date_trunc(''MINUTE'', QuoteStartDateTime),
        cast(QuoteStartDateTime as DATE),
        null,
        case 
            when QSno = 1 then ''New Business - Quote Started'' 
            when QSno > 1 and IsRetrieved = True then ''Quote Retrieved'' 
            Else ''Quote - Progressed''
        end             
from    (   
            select  *,
                    row_number() over (partition by QuoteReference Order by QuoteStartDateTime) as QSno
            from    (
                    select	QuoteReference,
                            max(SessionId) SessionId,
                            date_trunc(''SECOND'',try_cast(QuoteStartDateTime  as timestamp)) QuoteStartDateTime,
                            max(IsRetrieved) IsRetrieved
                    from	dlk.vanquotejourney 
                    Group by QuoteReference,
                            date_trunc(''SECOND'',try_cast(QuoteStartDateTime  as timestamp))
                    Order by QuoteStartDateTime
                    ) x 

                )       y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7360, N'Source 42 - Van Quote Journeys - Started / Retrieved', N'Delete and rebuild EventSourceId 42', 7360, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7370  Source 43 - Van Payment Journey
--  notebook cell 45
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7370, 7, N'Source 43 - Van Payment Journey', N'Delete and rebuild EventSourceId 43', GETDATE(), NULL, 7, 7370, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7370,
N'Delete from ods.EventStream 
Where EventSourceId = 43
;
Insert into ods.EventStream 
(
    EventId,
    EventSourceId,
    EventSourceReference,
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription
)
select  maxEventId + Row_Number() over (Partition by 1  Order by QuoteStartDateTime, QuoteReference),
        43, 
        SessionId, 
        QuoteReference ,  
        Null PolicyCode,
        7,
        ''Van'',  
        date_trunc(''MINUTE'', QuoteStartDateTime),
        cast(QuoteStartDateTime as DATE),
        null,
        concat(''Payment - '', PaymentStatus) 
from    (   
            select	QuoteReference, 
                    try_cast(QuoteStartDateTime as timestamp) QuoteStartDateTime, 
                    PaymentStatus, 
                    SessionId
            from	dlk.vanpaymentjourney 
            Where	PaymentType is not NULL
            and     try_cast(QuoteStartDateTime as timestamp) is not null 
                )       y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7370, N'Source 43 - Van Payment Journey', N'Delete and rebuild EventSourceId 43', 7370, GETDATE(), NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7380  Summary - ods.EventStreamSummary
--  notebook cell 47
-- ----------------------------------------------------------------------------------------------
INSERT INTO ops.CSPScheduledItem
VALUES (7380, 7, N'Summary - ods.EventStreamSummary', N'Build the EventStream summary table', GETDATE(), NULL, 7, 7380, 2);

INSERT INTO ops.CSPScheduledItemString
VALUES (7380,
N'Create Table ods.EventStreamSummary as 
select  EventSourceId, 
        SourceSystemId,
        PolicyTypeGroup,
        Year(EventDate) EventYear,
        Month(EventDate) EventMonth,
        count(*) as RecordCount,
        count(Distinct SourceQuoteReference) QuoteCount,
        count(Distinct SourcePolicyReference) PolicyCount,
        count(Distinct SourceCustomerReference) CustCount
From    ods.EventStream 
Group by EventSourceId, 
        SourceSystemId,
        PolicyTypeGroup,
        Year(EventDate),
        Month(EventDate);',
        1, 1, 1, GETDATE(), NULL, 7);

INSERT INTO ops.CSPScheduleGraphNode
VALUES (7380, N'Summary - ods.EventStreamSummary', N'Build the EventStream summary table', 7380, GETDATE(), NULL, 7);
GO

-- ==============================================================================================
--  4.  SEGMENTS
--      A linear chain. Every build cell reads max(EventId) from ods.EventStream to continue
--      the key sequence, so the steps cannot be run in parallel without colliding.
--      Positions: GraphId, SegmentId, segment type, NodeFrom, NodeTo, name, description,
--                 Inserted, Updated, ClientId.
-- ==============================================================================================

INSERT INTO ops.CSPScheduleGraphSegment
VALUES
    (7001, 1, 1, 7010, 7020, N'7010 to 7020', N'Setup - lkp.EventSource  ->  Setup - ods.EventStream', GETDATE(), NULL, 7),
    (7001, 2, 1, 7020, 7030, N'7020 to 7030', N'Setup - ods.EventStream  ->  Setup - ods.EpisodeEventStream', GETDATE(), NULL, 7),
    (7001, 3, 1, 7030, 7040, N'7030 to 7040', N'Setup - ods.EpisodeEventStream  ->  Source 01 - Genesys Calls - MFQ Data', GETDATE(), NULL, 7),
    (7001, 4, 1, 7040, 7050, N'7040 to 7050', N'Source 01 - Genesys Calls - MFQ Data  ->  Source 02 - Google Analytics - MFQ Records', GETDATE(), NULL, 7),
    (7001, 5, 1, 7050, 7060, N'7050 to 7060', N'Source 02 - Google Analytics - MFQ Records  ->  Source 03 - Documents Issued - From Relay', GETDATE(), NULL, 7),
    (7001, 6, 1, 7060, 7070, N'7060 to 7070', N'Source 03 - Documents Issued - From Relay  ->  Source 04 - Quote Started - Motor Quotes', GETDATE(), NULL, 7),
    (7001, 7, 1, 7070, 7080, N'7070 to 7080', N'Source 04 - Quote Started - Motor Quotes  ->  Source 24 - CC Motor Quotes - Started', GETDATE(), NULL, 7),
    (7001, 8, 1, 7080, 7090, N'7080 to 7090', N'Source 24 - CC Motor Quotes - Started  ->  Source 05 - Payments - MFQ Motor Quotes', GETDATE(), NULL, 7),
    (7001, 9, 1, 7090, 7100, N'7090 to 7100', N'Source 05 - Payments - MFQ Motor Quotes  ->  Source 06 - Payments - CallCentre Motor Quotes', GETDATE(), NULL, 7),
    (7001, 10, 1, 7100, 7110, N'7100 to 7110', N'Source 06 - Payments - CallCentre Motor Quotes  ->  Source 07 - Quotes Abandoned - Motor Quotes', GETDATE(), NULL, 7),
    (7001, 11, 1, 7110, 7120, N'7110 to 7120', N'Source 07 - Quotes Abandoned - Motor Quotes  ->  Source 27 - CC Motor Quote - Abandoned', GETDATE(), NULL, 7),
    (7001, 12, 1, 7120, 7130, N'7120 to 7130', N'Source 27 - CC Motor Quote - Abandoned  ->  Source 08 - Document Uploads - Motor Quotes', GETDATE(), NULL, 7),
    (7001, 13, 1, 7130, 7140, N'7130 to 7140', N'Source 08 - Document Uploads - Motor Quotes  ->  Source 09 - Quote Retrieval - MFQ Motor Quotes', GETDATE(), NULL, 7),
    (7001, 14, 1, 7140, 7150, N'7140 to 7150', N'Source 09 - Quote Retrieval - MFQ Motor Quotes  ->  Source 10 - Quote Completion Steps - MFQ Motor Quotes', GETDATE(), NULL, 7),
    (7001, 15, 1, 7150, 7160, N'7150 to 7160', N'Source 10 - Quote Completion Steps - MFQ Motor Quotes  ->  Source 11 - Policy Transactions (NewArchive) - All Policies', GETDATE(), NULL, 7),
    (7001, 16, 1, 7160, 7170, N'7160 to 7170', N'Source 11 - Policy Transactions (NewArchive) - All Policies  ->  Source 12 - Policy Transactions (MTA History) - All Policies', GETDATE(), NULL, 7),
    (7001, 17, 1, 7170, 7180, N'7170 to 7180', N'Source 12 - Policy Transactions (MTA History) - All Policies  ->  Source 13 - Policy Renewal Start - All Policies', GETDATE(), NULL, 7),
    (7001, 18, 1, 7180, 7190, N'7180 to 7190', N'Source 13 - Policy Renewal Start - All Policies  ->  Source 14 - Home Quotes Call Centre Events', GETDATE(), NULL, 7),
    (7001, 19, 1, 7190, 7200, N'7190 to 7200', N'Source 14 - Home Quotes Call Centre Events  ->  Source 15 - Genesys Calls - All calls', GETDATE(), NULL, 7),
    (7001, 20, 1, 7200, 7210, N'7200 to 7210', N'Source 15 - Genesys Calls - All calls  ->  Source 16 - Document Chase from Workflow', GETDATE(), NULL, 7),
    (7001, 21, 1, 7210, 7220, N'7210 to 7220', N'Source 16 - Document Chase from Workflow  ->  Source 17 - Events from Applied Renewals', GETDATE(), NULL, 7),
    (7001, 22, 1, 7220, 7230, N'7220 to 7230', N'Source 17 - Events from Applied Renewals  ->  Source 18 - Home Claims', GETDATE(), NULL, 7),
    (7001, 23, 1, 7230, 7240, N'7230 to 7240', N'Source 18 - Home Claims  ->  Source 19 - Motor Claims', GETDATE(), NULL, 7),
    (7001, 24, 1, 7240, 7250, N'7240 to 7250', N'Source 19 - Motor Claims  ->  Source 20 - Customer Portal Login', GETDATE(), NULL, 7),
    (7001, 25, 1, 7250, 7260, N'7250 to 7260', N'Source 20 - Customer Portal Login  ->  Source 33 - Online Home Quote - Retrieved', GETDATE(), NULL, 7),
    (7001, 26, 1, 7260, 7270, N'7260 to 7270', N'Source 33 - Online Home Quote - Retrieved  ->  Source 34 - Online Home Quote - Started', GETDATE(), NULL, 7),
    (7001, 27, 1, 7270, 7280, N'7270 to 7280', N'Source 34 - Online Home Quote - Started  ->  Source 35 - Online Home Quote - Progressed', GETDATE(), NULL, 7),
    (7001, 28, 1, 7280, 7290, N'7280 to 7290', N'Source 35 - Online Home Quote - Progressed  ->  Source 36 - Online Home Quote - Payment Status Success / Failure', GETDATE(), NULL, 7),
    (7001, 29, 1, 7290, 7300, N'7290 to 7300', N'Source 36 - Online Home Quote - Payment Status Success / Failure  ->  Source 37 - Home Insurance - Document Upload for Verification', GETDATE(), NULL, 7),
    (7001, 30, 1, 7300, 7310, N'7300 to 7310', N'Source 37 - Home Insurance - Document Upload for Verification  ->  Source 38 - Quote Completion Steps - Online Home Quotes', GETDATE(), NULL, 7),
    (7001, 31, 1, 7310, 7320, N'7310 to 7320', N'Source 38 - Quote Completion Steps - Online Home Quotes  ->  Source 39 - Travel Quotes', GETDATE(), NULL, 7),
    (7001, 32, 1, 7320, 7330, N'7320 to 7330', N'Source 39 - Travel Quotes  ->  Source 45 - Unknown source', GETDATE(), NULL, 7),
    (7001, 33, 1, 7330, 7340, N'7330 to 7340', N'Source 45 - Unknown source  ->  Source 40 - Traval Transactions', GETDATE(), NULL, 7),
    (7001, 34, 1, 7340, 7350, N'7340 to 7350', N'Source 40 - Traval Transactions  ->  Source 41 - Travel Renewals / Cancellations', GETDATE(), NULL, 7),
    (7001, 35, 1, 7350, 7360, N'7350 to 7360', N'Source 41 - Travel Renewals / Cancellations  ->  Source 42 - Van Quote Journeys - Started / Retrieved', GETDATE(), NULL, 7),
    (7001, 36, 1, 7360, 7370, N'7360 to 7370', N'Source 42 - Van Quote Journeys - Started / Retrieved  ->  Source 43 - Van Payment Journey', GETDATE(), NULL, 7),
    (7001, 37, 1, 7370, 7380, N'7370 to 7380', N'Source 43 - Van Payment Journey  ->  Summary - ods.EventStreamSummary', GETDATE(), NULL, 7);
GO

-- ==============================================================================================
--  5.  CHECK BEFORE RUNNING
-- ==============================================================================================

SELECT 'graph'    AS Item, count(*) AS [Rows] FROM ops.CSPScheduleGraph       WHERE CSPScheduleGraphId = 7001
UNION ALL SELECT 'nodes',    count(*) FROM ops.CSPScheduleGraphNode   WHERE CSPScheduleGraphNodeId BETWEEN 7010 AND 7380
UNION ALL SELECT 'items',    count(*) FROM ops.CSPScheduledItem       WHERE CSPScheduledItemId BETWEEN 7010 AND 7380
UNION ALL SELECT 'strings',  count(*) FROM ops.CSPScheduledItemString WHERE CSPScheduledItemId BETWEEN 7010 AND 7380 AND CSPScheduledItemCurrentFlag = 1
UNION ALL SELECT 'segments', count(*) FROM ops.CSPScheduleGraphSegment WHERE CSPScheduleGraphId = 7001;
--  expect 38 nodes, 38 items, 38 strings and 37 segments
GO

-- ==============================================================================================
--  6.  RUN IT
-- ==============================================================================================

--  EXECUTE ops.CSPExecuteGenericGraph @cspgraphid = 7001;
