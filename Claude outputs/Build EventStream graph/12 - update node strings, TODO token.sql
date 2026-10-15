/*
    12 - update node strings, TODO token.sql

    Re-issues node SQL through ops.CSPUpdateScheduledItemString, so each change is
    versioned rather than replaced. The procedure flags the current row off, writes a
    new one with CSPMinorVersion incremented, and keeps the old text to look back at.

    ONE CHANGE, FOR THE NODES BELOW 7210

    ##TODO## in a comment becomes TODO, because ## is how the harness marks a parameter.
    Left alone, ops.CSPSubstituteParams would look up a parameter called TODO, fail to
    match, log a critical error, and ops.CSPExecGraphFinalise would count the node as
    failed. Nothing else in any string is touched.

    4 statement(s), for node(s) 7110, 7120, 7130, 7190.

    These four sit below 7210, so the datetime cast you applied by hand is already in
    them. The strings here carry that same cast, so if your edit matched the form you
    gave me it re-issues identical text for that part. Worth a glance at the first one
    before you run the rest.

    Script 05 already carries every change applied here, so a fresh install from 05
    does not need this script. Run it only against a warehouse carrying an earlier
    version of these strings.
*/

-- ==============================================================================================
--  7110  Source 07 - Quotes Abandoned - Motor Quotes
--  notebook cell 14
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7110, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  7120  Source 27 - CC Motor Quote - Abandoned
--  notebook cell 15
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7120, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  7130  Source 08 - Document Uploads - Motor Quotes
--  notebook cell 16
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7130, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  7190  Source 14 - Home Quotes Call Centre Events
--  notebook cell 22
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7190, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
*/'
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
WHERE   CSPScheduledItemId IN (7110, 7120, 7130, 7190)
ORDER BY CSPScheduledItemId, CSPMajorVersion, CSPMinorVersion;
--  expect 4 row(s) flagged 1, plus the superseded rows flagged 0
GO

--  Nothing should come back from either of these.

SELECT  CSPScheduledItemId
FROM    ops.CSPScheduledItemString
WHERE   CSPScheduledItemCurrentFlag = 1
        AND (CSPScheduledItemString LIKE '%DATEDIFF(minute, 0,%'
             OR CSPScheduledItemString LIKE '%##%');
--  expect no rows
GO
