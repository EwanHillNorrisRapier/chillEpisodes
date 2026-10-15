/*
    05 - CSPScheduledItemString.sql

    Graph 7001, a 38 node linear chain mirroring Fabric notebook
    10 - Build EventStream.

    The SQL each node runs, one row per node, carried across from the notebook unchanged.
    CSPScheduledItemCurrentFlag must be 1. ops.CSPExecGraphNodeTypeSQL joins on it, and a
    node whose string is not flagged current throws "Graph Node does not exist in
    CSPScheduleGraphNode table".
    
    The SQL started as Spark SQL in the notebook and has been converted to T-SQL. What
    changed, and nothing else did:
    
        Partition by 1 in a window      dropped, T-SQL rejects a constant there      34
        date_trunc('MINUTE', x)         DATEADD(minute, DATEDIFF(minute, 0, x), 0)   31
        date_trunc('SECOND', x)         the same anchored on 1900-01-01                2
        backtick identifiers            square brackets                              14
        timestamp_seconds(x)            DATEADD(second, CAST(x AS bigint), epoch)      8
        to_timestamp(x, format)         TRY_CONVERT, style 112 or a STUFF rebuild      5
        cast(x as timestamp)            cast(x as datetime2(6))                        4
        Create or Replace Table         DROP TABLE IF EXISTS then CREATE TABLE         3
        TIMESTAMP as a column type      DATETIME2(6), since T-SQL TIMESTAMP is         2
                                        rowversion and would not have errored
        split(PagePath, '?')[0]         CHARINDEX and LEFT                             1
        Create Table ... as select      a DROP TABLE IF EXISTS put in front of it      1
    
    Left alone because they are already valid T-SQL: TRY_CAST, DATEADD and DATEDIFF in
    their three-argument form, CONCAT, CAST as DATE or varchar(n), LEN, TRIM, UPPER,
    LOWER, COALESCE, YEAR, MONTH, CHARINDEX, REPLACE, SUBSTRING, and the comment styles.
    
    One thing is knowingly still Spark: node 7360 compares IsRetrieved = True, which
    T-SQL has no literal for. It needs = 1 or = True once the column type on
    ChillLH.dlk.vanquotejourney is known.
    
    The ## marks a parameter to ops.CSPSubstituteParams, so the ##TODO## notes the
    notebook left in its comments now read TODO. Left as they were, each would be looked
    up in ops.CSPExecutionParameters, fail to match, and log a critical error that
    ops.CSPExecGraphFinalise would count as a failed node.
    
    WHERE THE DATA COMES FROM
    
    The nodes read 37 source objects and create 4 of their own. The 37 are now read
    straight out of the linked lakehouse with three-part names, all lower case, since
    that is how ChillLH stores them:
    
        [ChillLH].[dlk].[hfq_quotedetails]        and 36 more
    
    Nothing is copied, so there is no snapshot to go stale. Six of the 37 were spelled
    two ways by the notebook, and both spellings now resolve to the same lakehouse
    object, so the duplicate-copy problem goes away with them.
    
    The four the nodes build stay two-part, so they land in the running database:
    
        lkp.EventSource   ods.EventStream   ods.EpisodeEventStream   ods.EventStreamSummary
    
    To revise one later, prefer ops.CSPUpdateScheduledItemString, which versions the old
    row out rather than replacing it.

    CURRENT_TIMESTAMP is used rather than GETDATE(), which a Fabric warehouse does not
    support. It takes no parentheses, and the datetime it returns converts implicitly
    into the datetime2 RecordInsertDateTime and RecordUpdateDateTime columns.

    Run order:
        00  list column names
        01  ops.CSPNextExecutionId
        02  ops.CSPExecutionStatus
        03  ops.CSPScheduleGraph
        04  ops.CSPScheduledItem
        05  ops.CSPScheduledItemString <-- this script
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
--      CSPScheduledItemString
--      CSPMajorVersion
--      CSPMinorVersion
--      CSPScheduledItemCurrentFlag
--      RecordInsertDateTime
--      RecordUpdateDateTime
--      CSPClientId
--
-- ==============================================================================================

-- ==============================================================================================
--  CLEAR
-- ==============================================================================================

DELETE ops.CSPScheduledItemString WHERE CSPScheduledItemId BETWEEN 7010 AND 7380;
GO

-- ==============================================================================================
--  INSERT, ONE BATCH PER NODE
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
--  7010  Setup - lkp.EventSource
--  notebook cell 1
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
VALUES (7010,
'DROP TABLE IF EXISTS lkp.EventSource;

CREATE TABLE lkp.EventSource (
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
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7020  Setup - ods.EventStream
--  notebook cell 3
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
VALUES (7020,
'DROP TABLE IF EXISTS ods.EventStream;

CREATE TABLE ods.EventStream (
    EventId     BigInt,
    EventSourceId   Int,
    EventSourceReference    Varchar(128),
    SourceQuoteReference    Varchar(128),
    SourcePolicyReference   Varchar(128),
    SourceCustomerReference Varchar(128),
    SourceSystemId          int,
    PolicyTypeGroup         varchar(50),
    EventDateTime           DATETIME2(6),
    EventDate               Date,
    EventTypeId             int,
    EventDescription        varchar(1024)
)',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7030  Setup - ods.EpisodeEventStream
--  notebook cell 4
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
VALUES (7030,
'DROP TABLE IF EXISTS ods.EpisodeEventStream;

CREATE TABLE ods.EpisodeEventStream (
    EventId     BigInt,
    EpisodeReference        varchar(20),
    
    SourceEventReference    Varchar(128),
    SourceQuoteReference    Varchar(128),
    SourcePolicyReference   Varchar(128),
    SourceCustomerReference Varchar(128),

    SourceSystemId          int, /* MFQ HFQ Relay */ 
    PolicyTypeGroup         varchar(50), /* Motor Home Van Travel  */

    EventDate               Date,
    EventDateTime           DATETIME2(6),
    
    CampaignId              int   

    /*
    EventDescription        varchar(1024)
    EventTypeId             int,
    EventSourceId   Int,*/

)',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7040  Source 01 - Genesys Calls - MFQ Data
--  notebook cell 5
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
VALUES (7040,
'Delete from ods.EventStream
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
select  Row_Number() over (Order by CallStartDt, MFQQuoteQueryGuid),
        1, /* Genesys - MFQ Linked records */ 
        ConversationId,
        MFQQuoteQueryGuid,
        null,
        2,
        ''Motor'',
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), CallStartDt), cast(0 as datetime)),
        cast(CallStartDt as DATE),
        2,
        EventType
from    [ChillLH].[stg].[mfqcallevents]           a 
/* first insert so row_number is as is */',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7050  Source 02 - Google Analytics - MFQ Records
--  notebook cell 6
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
VALUES (7050,
'-- 2. GA clicks

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
select  maxEventId + Row_Number() over (Order by WorkDateTime, [MFQ-QuoteQueryGUID1]),
        2, /* GA - MFQ Linked ecords */ 
        ClientID, /* not necessarily unique */ 
        [MFQ-QuoteQueryGUID1] as SourceQuoteReference,
        null,
        2,
        ''Motor'',
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), WorkDateTime), cast(0 as datetime)),
        cast(WorkDateTime as DATE),
        2,
        --concat(PagePathGroup, '' - '', PagePath, PageTitle)
        CONCAT( -- changed ED 15/05/26 - to clean EventDescriptions
            PagePathGroup
            , '' - ''
            , CASE 
                WHEN PageTitle = ''ooops | Chill Insurance Ireland'' THEN ''Error''
                ELSE CASE WHEN CHARINDEX(''?'', PagePath) > 0 THEN LEFT(PagePath, CHARINDEX(''?'', PagePath) - 1) ELSE PagePath END 
                END
            )
from    [ChillLH].[edw].[tbl_fact_ga_clicks_ga4]  a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
Where   [MFQ-QuoteQueryGUID1] is not null 
and		ClientID not like ''Adwords%'' 
and     PagePathGroup is not null 
/* first insert so row_number is as is */ 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7060  Source 03 - Documents Issued - From Relay
--  notebook cell 7
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
VALUES (7060,
'Delete from ods.EventStream
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
select  maxEventId + Row_Number() over (Order by EventDate, a.PolicyCode),
        3, /* Relay Documents */ 
        EventId, /* not necessarily unique  - Same Document Event goes twice sometimes if two actions happen on same document */ 
        Null,  
        a.PolicyCode,
        PolicyTypeGroup,  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDate), cast(0 as datetime)),
        cast(EventDate as DATE),
        null,
        EventDescription
from    [ChillLH].[ods].[relaydocumentevents]  a 
join 
        (select PolicyCode, PolicyTypeGroup from [ChillLH].[edw].[tbl_ref_policy] 
            Where  PolicyTypeGroup in (''Motor'', ''Home'', ''Van'', ''Other'') 
            Group by PolicyCode, PolicyTypeGroup) b
            on a.PolicyCode = b.PolicyCode 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
Where   EventDescription not like ''Unknown - Saved Document - Cash Receipt No: %'' /* 2026/07/23 Changes - Vijay */ 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7070  Source 04 - Quote Started - Motor Quotes
--  notebook cell 8, the live one for EventSourceId 4
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
VALUES (7070,
'Delete from ods.EventStream
Where EventSourceId = 4 
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
select  maxEventId + Row_Number() over (Order by QuoteDateTime, SourceSystemQuoteReference),
        4, /* Motor Quotes -- MFQ here -- CC to be added */ 
        SourceSystemQuoteReference, /* One Event to start (may be one more to convert or abandon) */ 
        SourceSystemQuoteReference,  
        null PolicyCode,
        RapierCustomerId,  -- pull Rapier customer id! 
        2,
        ''Motor'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), QuoteDateTime), cast(0 as datetime)),
        cast(QuoteDateTime as DATE),
        2,
        ''New Business - Quote Started - Online'' 
/*from    [ChillLH].[ods].[motorcustomerpolicyquotelinks]  a */
FROM    (select a.QuoteQueryGuid SourceSystemQuoteReference, b.RapierCustomerId, max(CreatedDateTime) QuoteDateTime
         from   [ChillLH].[dlk].[mfq_quotequery]                  a 
         /*join
                [ChillLH].[ods].[motorcustomerpolicyquotelinks]   b 
                    ON QuoteQueryGuid = SourceSystemQuoteReference BOTs not excluded */
        join    [ChillLH].[ods].[mfqscvlink]                      b 
                    on a.QuoteQueryGuid = b.SourceSystemQuoteReference
        left join 
                (select QuoteQueryGuid from [ChillLH].[dlk].[mfq_quotequery] where RetrieveSessionToken is not null) c 
                    on  a.QuoteQueryGuid = c.QuoteQueryGuid
         Where c.QuoteQueryGuid is null 
         Group by a.QuoteQueryGuid, b.RapierCustomerId)
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 

;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7080  Source 24 - CC Motor Quotes - Started
--  notebook cell 10
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
VALUES (7080,
'Delete from ods.EventStream
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
select  maxEventId + Row_Number() over (Order by StartQuoteDateTime, SourceSystemQuoteReference),
        24, /* Motor Quotes -- CC to be added */ 
        SourceSystemQuoteReference, 
        SourceSystemQuoteReference,  
        PolicyCode,
        Policy_Holder_ID,
        SourceSystemId,
        ''Motor'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), Date_Calculated), cast(0 as datetime)),
        cast(Date_Calculated as DATE),
        1,
        Concat(QuoteType, '' - Quote Started - CallCentre'') 
from    [ChillLH].[ods].[motorcustomerpolicyquotelinksdeduped]    a 
join    [ChillLH].[dlk].[ext_quotationstorage_policydetails] b 
            on  a.SourceSystemQuoteReference = b.Quotation_ID 
            and SourceSystemId = 9
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 

;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7090  Source 05 - Payments - MFQ Motor Quotes
--  notebook cell 11
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
VALUES (7090,
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by PaymentDate, QuoteQueryGuid),
        5, /* MFQ Payments */ 
        QuoteSummaryGuid, 
        QuoteQueryGuid SourceSystemQuoteReference,  
        null PolicyCode,
        RapierCustomerId,
        2,
        ''Motor'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), PaymentDate), cast(0 as datetime)),
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
            FROM    [ChillLH].[stg].[mfq_quote_payments]                  a
            join
                    [ChillLH].[ods].[mfqscvlink]                          b 
                    on a.QuoteQueryGuid = b.SourceSystemQuoteReference 
        )   a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7100  Source 06 - Payments - CallCentre Motor Quotes
--  notebook cell 13
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
VALUES (7100,
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by QuoteDateTime, SourceSystemQuoteReference),
        6, /* Call Centre Payments - pick from Sales table */ 
        SourceSystemQuoteReference, /* One Event to start (may be one more to convert or abandon) */ 
        SourceSystemQuoteReference,  
        PolicyCode,
        9,
        ''Motor'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), QuoteDateTime), cast(0 as datetime)),
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
					from	[ChillLH].[ods].[motorcustomerpolicyquotelinks]	a
					join
							[ChillLH].[edw].[tbl_fact_policy_sales]			b 
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
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7110  Source 07 - Quotes Abandoned - Motor Quotes
--  notebook cell 14
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
VALUES (7110,
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by EventDateTime, SourceSystemQuoteReference),
        7, /* Quotes abandoned */ 
        SourceSystemQuoteReference, /* One Event to start (may be one more to convert or abandon) */ 
        SourceSystemQuoteReference,  
        PolicyCode,
        RapierCustomerId,
        2,
        ''Motor'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDateTime), cast(0 as datetime)),
        cast(EventDateTime as DATE),
        2,
        ''Quote Abandoned - Online''
from    (
            select  a.SourceSystemQuoteReference,
                    DateAdd(day,7,case when Policy_Start_Date < ''2000-01-01'' then dateadd(year,datediff( year, Policy_Start_Date, QuoteDatetime)+1,Policy_Start_Date) else Policy_Start_Date end ) as EventDateTime,
                    PolicyCode,
                    c.RapierCustomerId 
            from    [ChillLH].[ods].[motorcustomerpolicyquotelinks]                                             a 
            left join 
                    (Select QuoteQueryGuid from [ChillLH].[ods].[mfqquotetopolicy] Where PaymentType in(5,0))   b  
                        on b.QuoteQueryGuid = a.SourceSystemQuoteReference /* check if the  upper / lower case is failing to join here TODO */
            join
                    [ChillLH].[ods].[mfqscvlink]                          c 
                    on a.SourceSystemQuoteReference = c.SourceSystemQuoteReference 
            Where   b.QuoteQueryGuid is NULL
            and     a.SourceSystemId = 2 
            and     CURRENT_TIMESTAMP > DateAdd(day,7,Policy_Start_Date)
        )   a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7120  Source 27 - CC Motor Quote - Abandoned
--  notebook cell 15
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
VALUES (7120,
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by EventDateTime, SourceSystemQuoteReference),
        27, /* Quotes abandoned */ 
        SourceSystemQuoteReference, /* One Event to start (may be one more to convert or abandon) */ 
        SourceSystemQuoteReference,  
        PolicyCode,
        9,
        ''Motor'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDateTime), cast(0 as datetime)),
        cast(EventDateTime as DATE),
        1,
        ''Quote Abandoned''
from    (
            select  a.SourceSystemQuoteReference,
                    DateAdd(day,7,case when Policy_Start_Date < ''2000-01-01'' then dateadd(year,datediff( year, Policy_Start_Date, QuoteDatetime)+1,Policy_Start_Date) else Policy_Start_Date end ) as EventDateTime,
                    PolicyCode
            from    [ChillLH].[ods].[motorcustomerpolicyquotelinks]                                             a 
            left join 
                    (
                    select	SourceSystemQuoteReference
                    from	(		
                                select	Row_Number() over(Partition by a.PolicyCode, a.Policy_Start_Date Order by QuoteDateTime desc) rno, 
                                        a.SourceSystemQuoteReference
                                from	[ChillLH].[ods].[motorcustomerpolicyquotelinks]	a
                                join
                                        [ChillLH].[edw].[tbl_fact_policy_sales]		b 
                                            on		a.PolicyCode = b.PolicyCode 
                                            and		ReportingSaleDate between cast(QuoteDateTime as date) and Policy_Start_Date  
                            ) x 
                    Where	x.rno = 1 
                    )   b  
                        on b.SourceSystemQuoteReference = a.SourceSystemQuoteReference /* check if the  upper / lower case is failing to join here TODO */
            Where   b.SourceSystemQuoteReference is NULL
            and     a.SourceSystemId = 9 
            and     CURRENT_TIMESTAMP > DateAdd(day,7,Policy_Start_Date)
        )   a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7130  Source 08 - Document Uploads - Motor Quotes
--  notebook cell 16
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
VALUES (7130,
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by EventDateTime, SourceSystemQuoteReference),
        8, /* Document Upload */ 
        SourceSystemQuoteReference, /* One Event to start (may be one more to convert or abandon) */ 
        SourceSystemQuoteReference,  
        PolicyCode,
        SourceSystemId,
        ''Motor'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDateTime), cast(0 as datetime)),
        cast(EventDateTime as DATE),
        null,
        EventDescription
from    (
            select  a.*,
                    b.timestamp as EventDateTime,
                    ErrorMEssage,
                    IsUploaded,
                    concat(case when IsUploaded = 1 then ''Document Upload Success'' else ''Document Upload Failure'' end, '' - '', Type, '' - '', case when Type = ''file'' then ''License'' else Title end) EventDescription
            from    [ChillLH].[ods].[motorcustomerpolicyquotelinksdeduped]       a,
                    [ChillLH].[dlk].[mychill_newuploaddocumentevents]         b       /* dlk for day 1 -- dlt from then on  TODO */ 
            Where   a.PolicyCode = b.PolicyCode 
            )                                                 y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7140  Source 09 - Quote Retrieval - MFQ Motor Quotes
--  notebook cell 17
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
VALUES (7140,
'/* dont need GA -- we can do from MFQ itself ! */ 
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
select  maxEventId + Row_Number() over (Order by EventDateTime, SourceSystemQuoteReference),
        9, /* Motor Quotes -- MFQ */ 
        EventId,
        SourceSystemQuoteReference,  
        PolicyCode,
        RapierCustomerId,
        2,
        ''Motor'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDateTime), cast(0 as datetime)),
        cast(EventDateTime as DATE),
        2,
        ''Quote Retrieved''
From    (select     RetrieveSessionToken EventId,
                    a.QuoteQueryGuid SourceSystemQuoteReference,  
                    c.PolicyCode,
                    CreatedDateTime EventDateTime,
                    b.RapierCustomerId
            from	[ChillLH].[dlk].[mfq_quotequery]		a
            join
                    [ChillLH].[ods].[mfqscvlink]                          b 
                    on a.QuoteQueryGuid = b.SourceSystemQuoteReference
            left join 
                    [ChillLH].[ods].[motorcustomerpolicyquotelinks]	c	
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
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7150  Source 10 - Quote Completion Steps - MFQ Motor Quotes
--  notebook cell 18
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
VALUES (7150,
'Delete from ods.EventStream
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
select  maxEventId + Row_Number() over (Order by EventDateTime, SourceSystemQuoteReference),
        10, /* MFQ Motor Quotes -- Steps */ 
        EventId,
        SourceSystemQuoteReference,  
        PolicyCode,
        RapierCustomerId,
        2,
        ''Motor'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDateTime), cast(0 as datetime)),
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
            from	[ChillLH].[stg].[mfq_steps_summary]                   a
            join
                    [ChillLH].[ods].[mfqscvlink]                          b 
                    on a.QuoteQueryGuid = b.SourceSystemQuoteReference
            JOIN
                    [ChillLH].[ods].[motorcustomerpolicyquotelinks]	    c	
                        ON  a.QuoteQueryGuid = c.SourceSystemQuoteReference
            )                          x 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7160  Source 11 - Policy Transactions (NewArchive) - All Policies
--  notebook cell 19
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
VALUES (7160,
'Delete from ods.EventStream
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
select  maxEventId + Row_Number() over (Order by ar_posting_date, ar_policy_code),
        11,
        ar_code,
        Null,
        ar_policy_code,
        p.PolicyTypeGroup,
        TRY_CONVERT(datetime2(6), STUFF(STUFF(STUFF(STUFF(concat(cast(ar_posting_date as varchar(8)),''2359''), 11, 0, '':''), 9, 0, '' ''), 7, 0, ''-''), 5, 0, ''-'')),  
        TRY_CONVERT(datetime2(6), cast(ar_posting_date as varchar(8)), 112),  
        null,
        ar_trans_description
from    [ChillLH].[dlk].[rbsdata2_newarchive] a 
JOIN
        [ChillLH].[ods].[policy]              p 
            on a.ar_policy_code = p.PolicyCode
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
Where   ar_cli_type not in (''K'', '''', ''0'', ''2'' , ''C'' , ''E'' ) 
and     ar_posting_date > 19000101
and     ar_trans_description > ''''
and     trim(ar_trans_description) not in (''Transaction Reconciliation'')
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7170  Source 12 - Policy Transactions (MTA History) - All Policies
--  notebook cell 20
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
VALUES (7170,
'Delete from ods.EventStream
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
select  maxEventId + Row_Number() over (Order by  EventDateTime, Hi_pol_code),
        12,
        cast(Hi_trcode as varchar(255)),
        Null,
        cast(Hi_pol_code as varchar(255)),
        b.PolicyTypeGroup,
        EventDateTime /*TRY_CONVERT(datetime2(6), STUFF(STUFF(STUFF(STUFF(cast(Hi_Date * 10000 + Hi_hr * 100 + Hi_min as varchar(12)), 11, 0, '':''), 9, 0, '' ''), 7, 0, ''-''), 5, 0, ''-''))*/,
        cast(EventDateTime as Date), /*TRY_CONVERT(datetime2(6), cast(Hi_Date as varchar(8)), 112),  */
        null,
        Hi_note
from    (select Hi_trcode, Hi_pol_code, Hi_note, 
                TRY_CONVERT(datetime2(6), STUFF(STUFF(STUFF(STUFF(cast(case    when trim(Hi_note) in (''Renewal Invited by Insurer'' , ''Policy Lapsed'', ''Policy AutoLapsed'')  
                                    then    Hi_mta_eff_date * 10000 + Hi_mta_eff_time 
                                    else    Hi_Date * 10000 + Hi_hr * 100 + Hi_min end  as varchar(12)), 11, 0, '':''), 9, 0, '' ''), 7, 0, ''-''), 5, 0, ''-'')) as EventDateTime 
        from    [ChillLH].[dlk].[rbsdata2_mta_history] ) a
JOIN
        [ChillLH].[ods].[policy]                  b
            on  a.Hi_pol_code = b.PolicyCode
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
Where   PolicyTypeGroup not in (''Other'', ''Commercial'')        
and     Hi_note > '''' 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7180  Source 13 - Policy Renewal Start - All Policies
--  notebook cell 21
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
VALUES (7180,
'Delete from ods.EventStream
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
select  maxEventId + Row_Number() over (Order by  a.PolicyRenewDateAdj, a.PolicyCode),
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
from    [ChillLH].[edw].[tbl_fact_policy_sales] a 
left join 
        [ChillLH].[edw].[tbl_ref_policy]        b 
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
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7190  Source 14 - Home Quotes Call Centre Events
--  notebook cell 22
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
VALUES (7190,
'Delete from ods.EventStream
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
select  maxEventId + Row_Number() over (Order by  EventDateTime, a.PolicyCode),
        14,
        EventSourceReference,
        QuoteId,
        a.PolicyCode,
        4,
        ''Home'',
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDateTime), cast(0 as datetime)),
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
           select   upper(a.PolicyId) EventSourceReference, /* upper lower issues to be resolved in dlk TODO */ 
                    b.QuoteId, 
                    a.PolicyCode,
                    TransactionDate EventDateTime, 
                    cast(TransactionDate as date) EventDate, 
                    concat(a.BusinessProcess, '' - '', a.EventType) EventDescription,
                    coalesce(FirstSaleDate, FirstRenewalDate) SaleDate,
                    FirstRenewalDate /* unused but let us keep it for now */  
            from   [ChillLH].[dlk].[ext_home_qs_policydetails]   a 
            left join 
                    [ChillLH].[dlk].[ext_home_qs_quotedetails]    b 
                        on  Upper(a.RiskId) = b.HomeRiskId 
                        and a.PolicyNumber = left(b.QuoteReference,17)
            left join 
                     (
                        select PolicyCode, 
                                min(case when PolicyStatusCode = ''N'' then ReportingSaleDate else null end) FirstSaleDate, 
                                min(case when PolicyStatusCode = ''R'' then ReportingSaleDate else null end) FirstRenewalDate 
                        from    [ChillLH].[edw].[tbl_fact_policy_sales] 
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
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7200  Source 15 - Genesys Calls - All calls
--  notebook cell 23
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
VALUES (7200,
'Delete from ods.EventStream
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
select  maxEventId + Row_Number() over (Order by conversationStartTime, conversationid, sessionIndex),
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
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), conversationStartTime), cast(0 as datetime)),
        cast(conversationStartTime as DATE),
        1,
        concat(OriginatingDirection, '' - '', coalesce(CallPurpose,'''')) 
from    [ChillLH].[ods].[customercallevents]  a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
Where   lower(CallPurpose) not like ''qd_%'' 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7210  Source 16 - Document Chase from Workflow
--  notebook cell 24
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
VALUES (7210,
'Delete from ods.EventStream
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
select  maxEventId + Row_Number() over (Order by [Timestamp], Attempts),
        16, /* Quote Linked Documents */ 
        concat(rk,a.PolicyCode),
        null,  
        a.PolicyCode,
        PolicyTypeGroup,  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), [Timestamp]), cast(0 as datetime)),
        cast([Timestamp] as DATE),
        null,
        concat(DiaryTypeID, '' - '', Title, '':- Attempt - '', Attempts, '' - '', case when IsAccepted = 1 then ''Accepted'' when IsRejected = 1 then ''Rejected'' else '''' end) 
from    [ChillLH].[dlk].[mychillworkflow_documentstatus]  a 
left join 
        [ChillLH].[ods].[policy] x  on a.PolicyCode = x.PolicyCode
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z         
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7220  Source 17 - Events from Applied Renewals
--  notebook cell 25
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
VALUES (7220,
'Delete from ods.EventStream
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
select  maxEventId + Row_Number() over (Order by EventDateTime),
        17, /* Quote Linked Documents */ 
        EventSourceReference, 
        null,  
        PolicyCode,
        PolicyTypeGroup,  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDateTime), cast(0 as datetime)),
        cast(EventDateTime as DATE),
        null,
        EventDescription
from    (
            select a.SessionId EventSourceReference,
                    a.PolicyCodeForRenewal PolicyCode,
                    x.PolicyTypeGroup,  
                    [Timestamp] as EventDateTime,
                    concat(''Renewal - Payment Failure - '', PaymentErrorMessage) as EventDescription
            from    [ChillLH].[dlk].[appliedrenewals_paymentfailedevent]  a 
            left join 
                    [ChillLH].[ods].[policy] x  on a.PolicyCodeForRenewal = x.PolicyCode
            Where len(PolicyCodeForRenewal) > 6 
            union
            select  a.SessionId,
                    a.PolicyCodeForRenewal,
                    x.PolicyTypeGroup,  
                    [Timestamp],
                    concat(''Renewal - Payment Success - '', a.PaymentType)
            from    [ChillLH].[dlk].[appliedrenewals_paymentsuccess]  a 
            left join 
                    [ChillLH].[ods].[policy] x  on a.PolicyCodeForRenewal = x.PolicyCode
            Where len(PolicyCodeForRenewal) > 6 
            ) a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z         
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7230  Source 18 - Home Claims
--  notebook cell 27
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
VALUES (7230,
'/* since quote for cc home is one record per insurer, removing the quotedetails */ 
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
select  maxEventId + Row_Number() over (Order by EventDateTime),
        18, /* Quote Linked Documents */ 
        HomeClaimId EventSourceReference, 
        PolicyId,  
        PolicyCode,
        ''Home'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDateTime), cast(0 as datetime)),
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
            FROM    [ChillLH].[dlk].[ext_home_qs_claimdetails]		b,
                    [ChillLH].[dlk].[ext_home_qs_policydetails]		c
            Where   b.HomeRiskId = upper(c.RiskId) /* UPPER should have been implemented in the dlk data TODO*/ 
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
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7240  Source 19 - Motor Claims
--  notebook cell 28
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
VALUES (7240,
'Delete from ods.EventStream
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
select  maxEventId + Row_Number() over (Order by EventDate),
        19, /* Motor Claims */ 
        PolicyCode EventSourceReference, 
        null,  
        PolicyCode,
        ''Motor'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDate), cast(0 as datetime)),
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
            from    [ChillLH].[stg].[motorclaims] 
            ) a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z         
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7250  Source 20 - Customer Portal Login
--  notebook cell 29
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
VALUES (7250,
'Delete from ods.EventStream
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
select  maxEventId + Row_Number() over (Order by EventDateTime),
        20, /* Login Events */ 
        EventSourceReference, 
        null,  
        null,
        ClientCode,
        ''Customer'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDateTime), cast(0 as datetime)),
        cast(EventDateTime as DATE),
        null,
        EventDescription
from    (
            select  concat(SessionId,''-'',Id) EventSourceReference,
                    [Timestamp] EventDateTime,
                    PortfolioCode ClientCode,
                    ''Login Successful'' EventDescription
            from    [ChillLH].[dlk].[appliedrenewals_successfulloginevent]
            Where	len(PortfolioCode) = 6
            union all 

            select  concat(SessionId,''-'',Id) EventSourceReference,
                    [Timestamp] EventDateTime,
                    PortfolioCode ClientCode,
                    ''Login Locked'' EventDescription
            from	[ChillLH].[dlk].[appliedrenewals_failedloginevent] 
            Where	len(PortfolioCode) = 6 
            and		isLocked = 1
            union all 

            select  concat(SessionId,''-'',Id) EventSourceReference,
                    [Timestamp] EventDateTime,
                    PortfolioCode ClientCode,
                    ''Login Failed'' EventDescription
            from	[ChillLH].[dlk].[appliedrenewals_failedloginevent] 
            Where	len(PortfolioCode) = 6 
            ) a 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z         
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7260  Source 33 - Online Home Quote - Retrieved
--  notebook cell 30
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
VALUES (7260,
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by EventDateTime, QuoteReference),
        33, /* Document Upload */ 
        QuoteReference, 
        QuoteReference,  
        null,
        3,
        ''Home'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDateTime), cast(0 as datetime)),
        cast(EventDateTime as DATE),
        2,
        ''Quote Retrieved''
from    (
            select  QuoteCodeReference as QuoteReference,
                     DATEADD(second, CAST(try_cast(ts as numeric) AS bigint), ''1970-01-01'') as EventDateTime
            from    [ChillLH].[dlk].[hfq_quotedetails]  a 
            Where   RetrieveCount > 0 
            union 
            select  QuoteCodeReference as QuoteReference,
                     DATEADD(second, CAST(try_cast(_ts as numeric) AS bigint), ''1970-01-01'') as EventDateTime
            from    [ChillLH].[dlk].[hfq_quotedetails_snapshot_v2]  a 
            Where   RetrieveCount > 0 
            )                                                 y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7270  Source 34 - Online Home Quote - Started
--  notebook cell 31
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
VALUES (7270,
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by EventDateTime, QuoteReference),
        34, /* Document Upload */ 
        QuoteReference, 
        QuoteReference,  
        null,
        3,
        ''Home'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDateTime), cast(0 as datetime)),
        cast(EventDateTime as DATE),
        2,
        ''New Business - Quote Started''
from    (
            select distinct id as QuoteReference,
                    CreatedOn as EventDateTime
            from    [ChillLH].[dlk].[hfq_quotedetails]  a
            union 
            select distinct id as QuoteReference,
                    CreatedOn as EventDateTime
            from    [ChillLH].[dlk].[hfq_quotedetails_snapshot_v2]  a              

            )                                                 y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7280  Source 35 - Online Home Quote - Progressed
--  notebook cell 32
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
VALUES (7280,
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by EventDateTime, QuoteReference),
        35, /* Document Upload */ 
        QuoteReference, 
        QuoteReference,  
        null,
        3,
        ''Home'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDateTime), cast(0 as datetime)),
        cast(EventDateTime as DATE),
        2,
        ''New Business - Quote Progressed''
from    (
            select distinct id as QuoteReference,
                    DATEADD(second, CAST(try_cast(ts as numeric) AS bigint), ''1970-01-01'') as EventDateTime
            from    [ChillLH].[dlk].[hfq_quotedetails]  a 
            Where   CreatedOn < DATEADD(second, CAST(try_cast(ts as numeric) AS bigint), ''1970-01-01'')
            union 
            select distinct id as QuoteReference,
                    DATEADD(second, CAST(try_cast(_ts as numeric) AS bigint), ''1970-01-01'') as EventDateTime
            from    [ChillLH].[dlk].[hfq_quotedetails_snapshot_v2]  a 
            Where   CreatedOn < DATEADD(second, CAST(try_cast(_ts as numeric) AS bigint), ''1970-01-01'')
            )                                                 y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7290  Source 36 - Online Home Quote - Payment Status Success / Failure
--  notebook cell 33
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
VALUES (7290,
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by EventDateTime, QuoteReference),
        36, /* Document Upload */ 
        QuoteReference, 
        QuoteReference,  
        PolicyCode,
        3,
        ''Home'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDateTime), cast(0 as datetime)),
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
            from    [ChillLH].[dlk].[hfq_paymentresponse_response]        a,
                    (select QuoteCodeReference, PolicyCode from [ChillLH].[dlk].[hfq_sales])  b
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
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7300  Source 37 - Home Insurance - Document Upload for Verification
--  notebook cell 34
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
VALUES (7300,
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by EventDateTime, PolicyCode),
        37, /* Document Upload */ 
        pk, 
        Null,  
        PolicyCode,
        4,
        ''Home'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDateTime), cast(0 as datetime)),
        cast(EventDateTime as DATE),
        null,
        EventDescription
from    (
            select  a.PolicyCode,
                    pk,
                    b.[Timestamp] as EventDateTime,
                    concat(case when IsUploaded = 1 then ''Document Upload Success'' else ''Document Upload Failure'' end, '' - '', Type, '' - '', Title) EventDescription
            from    [ChillLH].[ods].[policy]                              a,
                    [ChillLH].[dlk].[mychill_newuploaddocumentevents]     b       
            Where   a.PolicyCode = b.PolicyCode 
            and     a.PolicyTypeGroup = ''Home''  

            )                                                 y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7310  Source 38 - Quote Completion Steps - Online Home Quotes
--  notebook cell 35
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
VALUES (7310,
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by EventDateTime, QuoteCodeReference),
        38, /* Document Upload */ 
        QuoteCodeReference, 
        QuoteCodeReference,  
        Null PolicyCode,
        3,
        ''Home'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDateTime), cast(0 as datetime)),
        cast(EventDateTime as DATE),
        2,
        ''Quote Progressed''
from    (
            select  QuoteCodeReference, 
                    LastStep, 
                    min(DATEADD(second, CAST(try_cast(ts as numeric) AS bigint), ''1970-01-01'')) EventDateTime 
            from [ChillLH].[dlk].[hfq_quotedetails] 
            Group by QuoteCodeReference, 
                    LastStep
            union 
            select  QuoteCodeReference, 
                    LastStep, 
                    min(DATEADD(second, CAST(try_cast(_ts as numeric) AS bigint), ''1970-01-01'')) EventDateTime 
            from [ChillLH].[dlk].[hfq_quotedetails_snapshot_v2]
            Group by QuoteCodeReference, 
                    LastStep
            )                                                 y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7320  Source 39 - Travel Quotes
--  supplied from Fabric, supersedes notebook cell 38
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
VALUES (7320,
'/* Quote Initiated */ 
Delete from ods.EventStream 
Where EventSourceId = 39
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
select  maxEventId + Row_Number() over (Order by travel_quoteDate, Quote_number),
        39, /* Document Upload */ 
        Quote_number, 
        Quote_number,  
        PolicyId PolicyCode,
        SourceCustomerReference,
        SourceSystemId,
        ''Travel'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), travel_quoteDate), cast(0 as datetime)),
        cast(travel_quoteDate as DATE),
        null,
        EventDescription
from    (        
                    select  x.Quote_number,
                            x.travel_quoteDate,
                            y.PolicyId,
                            x.SourceSystemId,
                            concat(''M'', y.MapfreCustomerId) as SourceCustomerReference,
                            concat(case when x.RenewalFlag = 1 then ''Renewal'' else ''New Business'' end, '' - '', coalesce(y.Source, ''Web'') , '' - '', ''Quote Initiated'') EventDescription
                    From    (   Select  Quote_number,
                                        travel_quoteDate,
                                        min(SourceSystemId) SourceSystemId,
                                        max(RenewalFlag) RenewalFlag
                                From    (   select  Quote_number,
                                                    travel_quoteDate,
                                                    8 as SourceSystemId,
                                                    case when business_type = ''New Business'' then 0 else 1 end RenewalFlag
                                            from    [ChillLH].[dlk].[ext_travel_quotes]  
                                            Where   Quote_Number <> 0 
                                            AND     travel_certificatestatus IN (''Completed Quote'' , ''Cancelled'', ''Live'', ''Incomplete Quote'')
                                            UNION
                                            select  Quote_number,
                                                    travel_quoteDate,
                                                    8 as SourceSystemId,
                                                    case when business_type = ''New Business'' then 0 else 1 end RenewalFlag
                                            from    [ChillLH].[dlk].[ext_travel_quotes_allquotesfile]
                                            Where   Quote_number <> 0 
                                            AND     travel_certificatestatus IN (''Completed Quote'' , ''Cancelled'', ''Live'', ''Incomplete Quote'')
                                            UNION 
                                            Select  QuoteId,
                                                    CreatedDate,
                                                    5 as SourceSystemId,
                                                    RenewalFlag
                                            from    [ChillLH].[dlk].[ext_travel_policy] 
                                            Where   QuoteId > 0
                                            UNION 
                                            Select  QuoteId,
                                                    CreatedDate,
                                                    5 as SourceSystemId,
                                                    RenewalFlag
                                            from    [ChillLH].[dlk].[ext_travel_policy_trans]  
                                            Where   QuoteId > 0
                                            and     RecordType = ''N'' /* record type U always aligned on the same quote or policy id so we can ignore for now */
                                            )   m 
                                Group BY  Quote_number,
                                        travel_quoteDate                                            
                                        )   x 
                                Left join 
                                        [ChillLH].[dlk].[ext_travel_policy] y on     x.Quote_number = y.QuoteId

                    Group by  
                            x.Quote_number,
                            x.travel_quoteDate,
                            y.PolicyId,
                            x.SourceSystemId,
                            concat(''M'', y.MapfreCustomerId),
                            concat(case when x.RenewalFlag = 1 then ''Renewal'' else ''New Business'' end, '' - '', coalesce(y.Source, ''Web'') , '' - '', ''Quote Initiated'') 
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
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7330  Source 45 - Unknown source
--  notebook cell 41
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
VALUES (7330,
'/* Quote Abandoned */ 
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
select  maxEventId + Row_Number() over (Order by travel_quoteDate, Quote_number),
        45, /* Document Upload */ 
        Quote_number, 
        Quote_number,  
        Null PolicyCode,
        Null SourceCustomerReference,
        5,
        ''Travel'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), travel_quoteDate), cast(0 as datetime)),
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
                                            from    [ChillLH].[dlk].[ext_travel_quotes]  
                                            Where   Quote_Number <> 0 
                                            AND     travel_certificatestatus IN (''Completed Quote'' , ''Cancelled'',''Incomplete Quote'')
                                            UNION
                                            select  Quote_number,
                                                    travel_quoteDate,
                                                    case when business_type = ''New Business'' then 0 else 1 end RenewalFlag
                                            from    [ChillLH].[dlk].[ext_travel_quotes_allquotesfile]
                                            Where   Quote_number <> 0 
                                            AND     travel_certificatestatus IN (''Completed Quote'' , ''Cancelled'',''Incomplete Quote'')
                                            UNION 
                                            Select  QuoteId,
                                                    UpdatedDate,
                                                    RenewalFlag
                                            from    [ChillLH].[dlk].[ext_travel_policy_trans]  
                                            Where   QuoteId > 0
                                            and     RecordType = ''U'' /* record type U always aligned on the same quote or policy id so we can ignore for now */
                                            )   m 
                                Group BY  Quote_number,
                                        travel_quoteDate                                            
                                        )   x 
                    Left join 
                            [ChillLH].[dlk].[ext_travel_policy] y on     x.Quote_number = y.QuoteId
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
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7340  Source 40 - Traval Transactions
--  notebook cell 39, the live one for EventSourceId 40
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
VALUES (7340,
'Delete from ods.EventStream 
Where EventSourceId = 40 /* build 40 here -- Policy Purchased - Renewal and New Bus */ 
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
select  maxEventId + Row_Number() over (Order by PurchaseDate, QuoteId),
        40,   
        QuoteId, 
        QuoteId,  
        PolicyId PolicyCode,
        SourceCustomerReference,
        5,
        ''Travel'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), PurchaseDate), cast(0 as datetime)),
        cast(PurchaseDate as DATE),
        null,
        EventDescription
from    (        
            select  QuoteId,
                    PurchaseDate,
                    PolicyId,
                    concat(''M'', MapfreCustomerId) as SourceCustomerReference,
                    concat(case when RenewalFlag = 1 then ''Renewal'' else ''New Business'' end, '' - '', coalesce(Source, ''Web'') , '' - '', ''Policy purchased'') EventDescription
            from    [ChillLH].[dlk].[ext_travel_policy] 
            Where   QuoteId > 0
            and     RecordType = ''N''
                )       a  
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7350  Source 41 - Travel Renewals / Cancellations
--  notebook cell 40, the live one for EventSourceId 41
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
VALUES (7350,
'Delete from ods.EventStream 
Where EventSourceId = 41 /* build 41 here -- Policy Cancelled */ 
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
select  maxEventId + Row_Number() over (Order by EventDate, QuoteId),
        41,   
        QuoteId, 
        QuoteId,  
        PolicyId PolicyCode,
        SourceCustomerReference,
        5,
        ''Travel'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), EventDate), cast(0 as datetime)),
        cast(EventDate as DATE),
        null,
        EventDescription
from    (        
            select  QuoteId,
                    coalesce(VoidDate,UpdatedDate) EventDate,
                    PolicyId,
                    concat(''M'', MapfreCustomerId) as SourceCustomerReference,
                    concat(case when RenewalFlag = 1 then ''Renewal'' else ''New Business'' end, '' - '', coalesce(Source, ''Web'') , '' - '', ''Policy Cancelled'') EventDescription
            from    [ChillLH].[dlk].[ext_travel_policy_trans] 
            Where   QuoteId > 0
            and     RecordType = ''C''
                )       a  
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7360  Source 42 - Van Quote Journeys - Started / Retrieved
--  notebook cell 44
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
VALUES (7360,
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by QuoteStartDateTime, QuoteReference),
        42, 
        SessionId, 
        QuoteReference ,  
        Null PolicyCode,
        7,
        ''Van'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), QuoteStartDateTime), cast(0 as datetime)),
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
                            DATEADD(second, DATEDIFF(second, ''1900-01-01'', try_cast(QuoteStartDateTime  as datetime2(6))), ''1900-01-01'') QuoteStartDateTime,
                            max(IsRetrieved) IsRetrieved
                    from	[ChillLH].[dlk].[vanquotejourney] 
                    Group by QuoteReference,
                            DATEADD(second, DATEDIFF(second, ''1900-01-01'', try_cast(QuoteStartDateTime  as datetime2(6))), ''1900-01-01'')
                    Order by QuoteStartDateTime
                    ) x 

                )       y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7370  Source 43 - Van Payment Journey
--  notebook cell 45
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
VALUES (7370,
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by QuoteStartDateTime, QuoteReference),
        43, 
        SessionId, 
        QuoteReference ,  
        Null PolicyCode,
        7,
        ''Van'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), QuoteStartDateTime), cast(0 as datetime)),
        cast(QuoteStartDateTime as DATE),
        null,
        concat(''Payment - '', PaymentStatus) 
from    (   
            select	QuoteReference, 
                    try_cast(QuoteStartDateTime as datetime2(6)) QuoteStartDateTime, 
                    PaymentStatus, 
                    SessionId
            from	[ChillLH].[dlk].[vanpaymentjourney] 
            Where	PaymentType is not NULL
            and     try_cast(QuoteStartDateTime as datetime2(6)) is not null 
                )       y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;',
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

-- ----------------------------------------------------------------------------------------------
--  7380  Summary - ods.EventStreamSummary
--  notebook cell 47
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
VALUES (7380,
'DROP TABLE IF EXISTS ods.EventStreamSummary;

Create Table ods.EventStreamSummary as 
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
        1, 1, 1, CURRENT_TIMESTAMP, NULL, 7);
GO

SELECT CSPScheduledItemId, CSPScheduledItemCurrentFlag, len(CSPScheduledItemString) AS SqlLength
FROM ops.CSPScheduledItemString WHERE CSPScheduledItemId BETWEEN 7010 AND 7380 ORDER BY 1;
--  expect 38 rows, all flagged 1
GO
