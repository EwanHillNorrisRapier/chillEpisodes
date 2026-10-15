/*
    13 - update node string 7320, correct source cell.sql

    Re-issues node 7320 through ops.CSPUpdateScheduledItemString, so the change is
    versioned rather than replaced. The procedure flags the current row off, writes a
    new one with CSPMinorVersion incremented, and keeps the old text to look back at.

    WHY

    Node 7320 was built from the wrong cell. The notebook has two cells that delete and
    rebuild EventSourceId 39, and I kept the later one on the rule that a later cell
    overwrites an earlier one. For 39 that rule gives the wrong answer: the earlier cell
    is the live one, and the version here is the code as it now stands in Fabric.

    WHAT IS DIFFERENT FROM WHAT IS DEPLOYED

    A different query, not an edit of the old one. The shape of the change:

        SourcePolicyReference     was a literal Null, now PolicyId from ext_travel_policy
        SourceCustomerReference   new, concat(M, MapfreCustomerId)
        SourceSystemId            new, 8 for the quote files and 5 for the policy files
        EventDescription          was business_type and certificate status, now
                                  Renewal or New Business, the source, and Quote Initiated
        sources                   was 2 tables, now 4, unioned then grouped

    THE CONVERSION APPLIED TO IT

    The same three mechanical changes as every other node, and nothing else:

        Partition by 1 dropped from the window
        date_trunc('MINUTE', travel_quoteDate) to the DATEADD and DATEDIFF form, with
            cast(0 as datetime) on both anchors
        the four dlk sources pointed at [ChillLH], lower case

    ods.EventStream stays two-part, so the delete and the insert land in this database.

    Script 05 carries the same string, so a fresh install from 05 does not need this.
*/

-- ==============================================================================================
--  7320  Source 39 - Travel Quotes
--  supplied from Fabric, supersedes notebook cell 38
-- ==============================================================================================
exec [ops].[CSPUpdateScheduledItemString]
@CSPScheduledItemId = 7320, @incrMajorMinorVersion = 'Minor', @CSPScheduledItemString = 
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
WHERE   CSPScheduledItemId = 7320
ORDER BY CSPMajorVersion, CSPMinorVersion;
--  expect one row flagged 1, plus the superseded rows flagged 0
GO

--  The new text should mention SourceCustomerReference and all four travel sources.

SELECT  CASE WHEN CSPScheduledItemString LIKE '%MapfreCustomerId%' THEN 1 ELSE 0 END AS HasCustomerRef,
        CASE WHEN CSPScheduledItemString LIKE '%ext_travel_policy_trans%' THEN 1 ELSE 0 END AS HasPolicyTrans,
        CASE WHEN CSPScheduledItemString LIKE '%DATEDIFF(minute, 0,%' THEN 1 ELSE 0 END AS HasBareZero,
        CASE WHEN CSPScheduledItemString LIKE '%##%' THEN 1 ELSE 0 END                      AS HasHashToken
FROM    ops.CSPScheduledItemString
WHERE   CSPScheduledItemId = 7320
        AND CSPScheduledItemCurrentFlag = 1;
--  expect 1, 1, 0, 0
GO
