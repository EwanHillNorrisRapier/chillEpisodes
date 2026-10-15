/*
    11 - update node strings, datetime cast.sql

    Re-issues node SQL through ops.CSPUpdateScheduledItemString, so each change is
    versioned rather than replaced. The procedure flags the current row off, writes a
    new one with CSPMinorVersion incremented, and keeps the old text to look back at.

    TWO CHANGES, FOR THE NODES FROM 7210 UPWARDS

        DATEADD(minute, DATEDIFF(minute, 0, x), 0)
    becomes
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), x), cast(0 as datetime))
    
    because the warehouse will not read the bare 0 as a date. And ##TODO## in a comment
    becomes TODO, because ## marks a parameter to ops.CSPSubstituteParams, so the token
    would be looked up, fail to match, and log a critical error. Node 7230 is the only
    one here carrying that. Nothing else in any string is touched.

    17 statement(s), for node(s) 7210, 7220, 7230, 7240, 7250, 7260, 7270, 7280, 7290, 7300, 7310, 7320, 7330, 7340, 7350, 7360, 7370.

    Node 7380 is not here. It builds ods.EventStreamSummary, has no minute truncation and
    no ## token, so it needs no update.

    Script 05 already carries every change applied here, so a fresh install from 05
    does not need this script. Run it only against a warehouse carrying an earlier
    version of these strings.
*/

-- ==============================================================================================
--  7210  Source 16 - Document Chase from Workflow
--  notebook cell 24
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7210, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  7220  Source 17 - Events from Applied Renewals
--  notebook cell 25
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7220, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  7230  Source 18 - Home Claims
--  notebook cell 27
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7230, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
*/'
GO

-- ==============================================================================================
--  7240  Source 19 - Motor Claims
--  notebook cell 28
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7240, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  7250  Source 20 - Customer Portal Login
--  notebook cell 29
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7250, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  7260  Source 33 - Online Home Quote - Retrieved
--  notebook cell 30
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7260, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  7270  Source 34 - Online Home Quote - Started
--  notebook cell 31
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7270, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  7280  Source 35 - Online Home Quote - Progressed
--  notebook cell 32
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7280, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  7290  Source 36 - Online Home Quote - Payment Status Success / Failure
--  notebook cell 33
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7290, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  7300  Source 37 - Home Insurance - Document Upload for Verification
--  notebook cell 34
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7300, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  7310  Source 38 - Quote Completion Steps - Online Home Quotes
--  notebook cell 35
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7310, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  7320  Source 39 - Travel Quotes
--  notebook cell 38
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7320, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by travel_quoteDate, Quote_number),
        39, /* Document Upload */ 
        Quote_number, 
        Quote_number,  
        Null PolicyCode,
        8,
        ''Travel'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), travel_quoteDate), cast(0 as datetime)),
        cast(travel_quoteDate as DATE),
        null,
        CONCAT(business_type, '' - '', travel_certificatestatus)
        case when travel_certificatestatus in (''Completed Quote'', ''Cancelled'', ''Live'') and business_type = ''New Business'' then ''''
from    (        
                    select  Quote_number,
                            travel_certificatestatus,
                            travel_quoteDate,
                            business_type
                    from    [ChillLH].[dlk].[ext_travel_quotes]
                    Where   Quote_number <> 0 
                    UNION
                    select  Quote_number,
                            travel_certificatestatus,
                            travel_quoteDate,
                            business_type
                    from    [ChillLH].[dlk].[ext_travel_quotes_allquotesfile]
                    Where   Quote_number <> 0 
                    and     Quote_number not in (select Quote_number from [ChillLH].[dlk].[ext_travel_quotes])
                )       y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;'
GO

-- ==============================================================================================
--  7330  Source 45 - Unknown source
--  notebook cell 41
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7330, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
*/'
GO

-- ==============================================================================================
--  7340  Source 40 - Traval Transactions
--  notebook cell 42
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7340, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by PurchaseDate, PolicyId ),
        40, 
        PolicyId, /* some quote are 0 */ 
        QuoteId,  
        PolicyId,
        MapfreCustomerId,
        5,
        ''Travel'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), PurchaseDate), cast(0 as datetime)),
        cast(PurchaseDate as DATE),
        null,
        CONCAT(Channel, '' - '', case when RenewalFlag = 1 then ''Renewal'' else ''New Business'' end, '' - '', ''Purchase'')
from    (        
                    select  QuoteId,
                            PolicyId,
                            MapfreCustomerId,
                            PurchaseDate,
                            [Source] as Channel, 
                            RenewalFlag 
                    from    [ChillLH].[dlk].[ext_travel_policy_trans]
                    Where   VoidFlag = 0  
                    and     RecordType <>''U'' 
                    and     CreatedDate > ''2020-01-01''
                    Group by QuoteId,
                            PolicyId,
                            MapfreCustomerId,
                            PurchaseDate,
                            [Source] , 
                            RenewalFlag                    
                )       y 
cross join 
        (select max(EventId) maxEventId from ods.EventStream) z 
;'
GO

-- ==============================================================================================
--  7350  Source 41 - Travel Renewals / Cancellations
--  notebook cell 43
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7350, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
'Delete from ods.EventStream 
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
select  maxEventId + Row_Number() over (Order by VoidDate, PolicyId),
        41, 
        QuoteId, 
        PolicyId,  
        Null PolicyCode,
        8,
        ''Travel'',  
        DATEADD(minute, DATEDIFF(minute, cast(0 as datetime), VoidDate), cast(0 as datetime)),
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
            from	[ChillLH].[dlk].[ext_travel_policy_trans]
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
;'
GO

-- ==============================================================================================
--  7360  Source 42 - Van Quote Journeys - Started / Retrieved
--  notebook cell 44
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7360, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
;'
GO

-- ==============================================================================================
--  7370  Source 43 - Van Payment Journey
--  notebook cell 45
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7370, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
WHERE   CSPScheduledItemId IN (7210, 7220, 7230, 7240, 7250, 7260, 7270, 7280, 7290, 7300, 7310, 7320, 7330, 7340, 7350, 7360, 7370)
ORDER BY CSPScheduledItemId, CSPMajorVersion, CSPMinorVersion;
--  expect 17 row(s) flagged 1, plus the superseded rows flagged 0
GO

--  Nothing should come back from either of these.

SELECT  CSPScheduledItemId
FROM    ops.CSPScheduledItemString
WHERE   CSPScheduledItemCurrentFlag = 1
        AND (CSPScheduledItemString LIKE '%DATEDIFF(minute, 0,%'
             OR CSPScheduledItemString LIKE '%##%');
--  expect no rows
GO
