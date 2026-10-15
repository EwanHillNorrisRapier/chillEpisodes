/*
    14 - update node strings, correct source cells.sql

    Re-issues three nodes through ops.CSPUpdateScheduledItemString, so each change is
    versioned rather than replaced. The procedure flags the current row off, writes a
    new one with CSPMinorVersion incremented, and keeps the old text to look back at.

    WHY

    These three were built from the wrong notebook cell. Where two cells delete and
    rebuild the same EventSourceId, I kept the later one, on the rule that a later cell
    overwrites an earlier one. That rule turned out to be wrong for four of the five
    duplicated ids. Node 7320 was corrected in script 13. These are the other three:

        node   EventSourceId   was              now
        7070   4              notebook cell 9  notebook cell 8
        7340   40             notebook cell 42 notebook cell 39
        7350   41             notebook cell 43 notebook cell 40

        7230   18              notebook cell 27  already correct, no update needed

    These are different queries, not edits of the deployed ones, so the whole string is
    replaced. Line counts give a sense of the scale:

        7070   47 lines now
        7340   43 lines now
        7350   43 lines now

    THE CONVERSION APPLIED TO THEM

    The same mechanical changes as every other node, and nothing else: Partition by 1
    dropped from the window, date_trunc('MINUTE', x) to the DATEADD and DATEDIFF form
    with cast(0 as datetime) on both anchors, and external sources pointed at [ChillLH]
    in lower case. ods.EventStream stays two-part.

    No new source objects. All three read tables already on the surfaced list, so
    nothing further needs opening up.

    Script 05 carries the same strings, so a fresh install from 05 does not need this.
*/

-- ==============================================================================================
--  7070  Source 04 - Quote Started - Motor Quotes
--  notebook cell 8, the live one for EventSourceId 4
--  replaces the version built from notebook cell 9
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7070, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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

;'
GO

-- ==============================================================================================
--  7340  Source 40 - Traval Transactions
--  notebook cell 39, the live one for EventSourceId 40
--  replaces the version built from notebook cell 42
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7340, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  7350  Source 41 - Travel Renewals / Cancellations
--  notebook cell 40, the live one for EventSourceId 41
--  replaces the version built from notebook cell 43
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7350, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  CHECK
-- ==============================================================================================

SELECT  CSPScheduledItemId,
        CSPMajorVersion,
        CSPMinorVersion,
        CSPScheduledItemCurrentFlag,
        RecordInsertDateTime,
        len(CSPScheduledItemString) AS SqlLength
FROM    ops.CSPScheduledItemString
WHERE   CSPScheduledItemId IN (7070, 7340, 7350)
ORDER BY CSPScheduledItemId, CSPMajorVersion, CSPMinorVersion;
--  expect 3 rows flagged 1, plus the superseded rows flagged 0
GO

--  Nothing should come back from this one.

SELECT  CSPScheduledItemId
FROM    ops.CSPScheduledItemString
WHERE   CSPScheduledItemCurrentFlag = 1
        AND (CSPScheduledItemString LIKE '%DATEDIFF(minute, 0,%'
             OR CSPScheduledItemString LIKE '%##%'
             OR CSPScheduledItemString LIKE '%date_trunc%');
--  expect no rows
GO
