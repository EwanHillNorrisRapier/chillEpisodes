#!/usr/bin/env python
# coding: utf-8

# ## Home Acquisition: count queries converted to Event Stream inserts
#
# DRAFT FOR REVIEW. Nothing here has been applied to
# "03 - Populate Episode Event Stream.py". Once the method is agreed, these cells
# replace the matching count-only cells in the Home Acquisitions section.
#
# Section A: clean conversions, the count query already had everything needed.
# Section B: conversions that need a decision from you before they go in.
# Section C: blocked, the staging table they need does not exist for Home.
#
# The conversion rules applied throughout are listed in the next cell.


# In[ ]:


# ---------------------------------------------------------------------------
# CONVERSION RULES
# ---------------------------------------------------------------------------
#
# 1. The distinct column becomes the source reference.
#    count(distinct QuoteCodeReference) means the grain is one row per quote, so
#    QuoteCodeReference goes into SourceQuoteReference and the insert groups by it.
#    count(distinct PolicyCode) goes into SourcePolicyReference. Genesys rows put
#    ConversationId into EventSourceID, as the Motor A0 insert does.
#
# 2. Every insert needs a timestamp the count query never selected.
#    The column chosen is named in a comment on each cell. Where the choice is
#    open to argument it is called out as a question rather than buried.
#
# 3. Date windows are parameterised.
#    The Home counts hardcode between '2026-07-01' and '2026-07-31'. Motor uses
#    >= '{run_start}' and < '{run_end}'. These drafts use the Motor form. Besides
#    making the notebook re-runnable it fixes a real bug: between '2026-07-01' and
#    '2026-07-31' on a timestamp column drops everything after midnight on 31 July.
#
# 4. EventDescription is 'Home Acquisition - ' plus the Step text from the
#    Reconciliation Request tab, verbatim. That keeps the stream readable and
#    keeps recon lined up with the framework.
#
# 5. Grain follows the reference used: 'Quote', 'Policy' or 'Call'.
#
# 6. SourceSystemId. See the open question at the bottom of this file. These
#    drafts use 2 for HFQ (the Home quoting platform, mirroring 2 for MFQ),
#    1 for CRM XP, Relay and EDW feeds, and 9 for a sale written on the phone,
#    mirroring Motor A4b.
#
# ---------------------------------------------------------------------------


# =============================================================================
# SECTION A: clean conversions
# =============================================================================


# In[ ]:


--HA1
-- was: select count(*) from stg.HA1_HFQ_Quotes
-- timestamp: ts_unix, already built on stg.HA1_HFQ_Quotes
-- the staging cell above this one stays as it is, only the count is replaced

insert INTO
ods.EpisodeEventStream
(
    SourceQuoteReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.QuoteCodeReference,
    2,
    'Home',
    date_trunc('MINUTE', min(a.ts_unix)),
    cast(min(a.ts_unix) as date),
    'HA1',
    'Home Acquisition - Quote initiated ONLINE',
    'Quote'
from    stg.HA1_HFQ_Quotes a
where   a.ts_unix >= '{run_start}' and a.ts_unix < '{run_end}'
Group by a.QuoteCodeReference
;


# In[ ]:


--HA1.E1
-- was: select count(*) from dlk.EXT_XtremePushResults ... campaign_name like 'Home % TYR %'
-- timestamp: `timestamp`
-- mirrors the Motor A1.E1 insert, with the Home campaign filter.
-- The two commented conditions in the original count are left out. Both were
-- flagged as iffy in the notebook, and QuoteQueryGuid > '' is needed here anyway
-- because a row with no reference cannot go into the stream.

insert INTO
ods.EpisodeEventStream
(
    SourceQuoteReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.QuoteQueryGuid,
    1,
    'Home',
    date_trunc('MINUTE', min(a.`timestamp`)),
    cast(min(a.`timestamp`) as date),
    'HA1.E1',
    'Home Acquisition - Service retrieve',
    'Quote'
from    dlk.EXT_XtremePushResults a
where   a.`timestamp` >= '{run_start}' and a.`timestamp` < '{run_end}'
and     a.campaign_name like 'Home % TYR %'
and     a.interaction_type = 'sent'
and     a.MessageType = 'EMAIL'
and     a.QuoteQueryGuid > ''
Group by a.QuoteQueryGuid
;


# In[ ]:


--HA2
-- was: select count(distinct QuoteCodeReference) from dlk.hfq_response_quotes
-- timestamp: Quotes_DateCreated

insert INTO
ods.EpisodeEventStream
(
    SourceQuoteReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.QuoteCodeReference,
    2,
    'Home',
    date_trunc('MINUTE', min(a.Quotes_DateCreated)),
    cast(min(a.Quotes_DateCreated) as date),
    'HA2',
    'Home Acquisition - Quote progressed',
    'Quote'
from    dlk.hfq_response_quotes a
where   a.Quotes_DateCreated >= '{run_start}' and a.Quotes_DateCreated < '{run_end}'
Group by a.QuoteCodeReference
;


# In[ ]:


--HA2.F1
-- was: count(distinct a.QuoteCodeReference), anti-join to stg.hfq_price_requested
-- timestamp: a.ts_unix, the quote start, because the event being recorded is the
-- drop off and there is no later timestamp to hang it on

insert INTO
ods.EpisodeEventStream
(
    SourceQuoteReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.QuoteCodeReference,
    2,
    'Home',
    date_trunc('MINUTE', min(a.ts_unix)),
    cast(min(a.ts_unix) as date),
    'HA2.F1',
    'Home Acquisition - Drop off before completing the details',
    'Quote'
from    stg.HA1_HFQ_Quotes          a
left join stg.hfq_price_requested   b
        on a.QuoteCodeReference = b.QuoteCodeReference
Where   b.QuoteCodeReference is null
and     a.ts_unix >= '{run_start}' and a.ts_unix < '{run_end}'
Group by a.QuoteCodeReference
;


# In[ ]:


--HA3
-- was: count(distinct QuoteCodeReference) where Quotes_Premium > 0 and Quotes_Outcome = 'PremiumReturned'
-- timestamp: Quotes_DateCreated
-- the stg.HA3_HomeAcquisitionQuoteInitiated build in this cell stays as it is

insert INTO
ods.EpisodeEventStream
(
    SourceQuoteReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.QuoteCodeReference,
    2,
    'Home',
    date_trunc('MINUTE', min(a.Quotes_DateCreated)),
    cast(min(a.Quotes_DateCreated) as date),
    'HA3',
    'Home Acquisition - Customer gets a price',
    'Quote'
from    dlk.hfq_response_quotes a
where   a.Quotes_Premium > 0
and     a.Quotes_Outcome = 'PremiumReturned'
and     a.Quotes_DateCreated >= '{run_start}' and a.Quotes_DateCreated < '{run_end}'
Group by a.QuoteCodeReference
;


# In[ ]:


--HA4a
-- was: count(distinct a.QuoteCodeReference), join stg.hfq_payments on SUCCESS
-- timestamp: PaymentResponseResponseTimestamp, the same choice Motor A4a makes
-- max() is used because a quote can have more than one successful payment row and
-- the buy event is the last of them

insert INTO
ods.EpisodeEventStream
(
    SourceQuoteReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.QuoteCodeReference,
    2,
    'Home',
    date_trunc('MINUTE', max(b.PaymentResponseResponseTimestamp)),
    cast(max(b.PaymentResponseResponseTimestamp) as date),
    'HA4a',
    'Home Acquisition - Customer buys ONLINE',
    'Quote'
from    stg.HA1_HFQ_Quotes  a
join    stg.hfq_payments    b
        on a.QuoteCodeReference = b.QuoteReference
Where   b.PaymentResponseResponseActionResultCode = 'SUCCESS'
and     b.PaymentResponseResponseTimestamp >= '{run_start}'
and     b.PaymentResponseResponseTimestamp <  '{run_end}'
Group by a.QuoteCodeReference
;


# In[ ]:


--HA4b
-- was: count(distinct a.PolicyCode) grouped by channel
-- timestamp: ReportingSaleDate
-- mirrors Motor A4b. The group by channel in the count was for eyeballing the
-- split, it is not part of the event, so it is dropped.

insert INTO
ods.EpisodeEventStream
(
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.PolicyCode,
    9,
    'Home',
    date_trunc('MINUTE', min(a.ReportingSaleDate)),
    cast(min(a.ReportingSaleDate) as date),
    'HA4b',
    'Home Acquisition - Agent quotes and converts on the CALL',
    'Policy'
from    stg.GlobalPoliciesSold a
Where   a.ReportingSaleType = 'New Business'
and     a.PolicyTypeGroup = 'Home'
and     a.QuoteQueryGuid is null
Group by a.PolicyCode
;


# In[ ]:


--HA4.F1
-- No count query existed. Direct mirror of Motor A4.F1, which reconciles, and
-- HA4.F1 reconciles too at 23 against 23. Included because it is a one line change
-- of PolicyTypeGroup from the Motor version.

insert INTO
ods.EpisodeEventStream
(
    SourceQuoteReference,
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.QuoteQueryGuid,
    a.PolicyCode,
    9,
    'Home',
    date_trunc('MINUTE', min(a.ReportingSaleDate)),
    cast(min(a.ReportingSaleDate) as date),
    'HA4.F1',
    'Home Acquisition - Web assist: starts online, then calls to complete',
    'Policy'
from    stg.GlobalPoliciesSold a
Where   a.ReportingSaleType = 'New Business'
and     a.PolicyTypeGroup = 'Home'
and     a.QuoteQueryGuid is not null
and     a.Channel = 'b) Web Assist'
Group by a.QuoteQueryGuid, a.PolicyCode
;


# In[ ]:


--HA5
-- was: count(distinct QuoteReference) from stg.HFQ_payments on SUCCESS
-- timestamp: PaymentResponseResponseTimestamp
-- Note this is the same population as HA4a minus the join to stg.HA1_HFQ_Quotes,
-- so HA5 will be at or above HA4a. That matches Fabric, 644 against 637.

insert INTO
ods.EpisodeEventStream
(
    SourceQuoteReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.QuoteReference,
    2,
    'Home',
    date_trunc('MINUTE', max(a.PaymentResponseResponseTimestamp)),
    cast(max(a.PaymentResponseResponseTimestamp) as date),
    'HA5',
    'Home Acquisition - Payment successful',
    'Quote'
from    stg.hfq_payments a
where   a.PaymentResponseResponseActionResultCode = 'SUCCESS'
and     a.PaymentResponseResponseTimestamp >= '{run_start}'
and     a.PaymentResponseResponseTimestamp <  '{run_end}'
Group by a.QuoteReference
;


# In[ ]:


--HA5.F1
-- was: count(distinct QuoteReference) where result code = 'DECLINED'
-- timestamp: PaymentResponseResponseTimestamp
-- min() not max() here, the friction event is the first decline

insert INTO
ods.EpisodeEventStream
(
    SourceQuoteReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.QuoteReference,
    2,
    'Home',
    date_trunc('MINUTE', min(a.PaymentResponseResponseTimestamp)),
    cast(min(a.PaymentResponseResponseTimestamp) as date),
    'HA5.F1',
    'Home Acquisition - Payment attempted with friction',
    'Quote'
from    stg.hfq_payments a
where   a.PaymentResponseResponseActionResultCode = 'DECLINED'
and     a.PaymentResponseResponseTimestamp >= '{run_start}'
and     a.PaymentResponseResponseTimestamp <  '{run_end}'
Group by a.QuoteReference
;


# In[ ]:


--HA5.B1
-- was: count(*) where isFullPayment = 'false'
-- timestamp: PaymentResponseResponseTimestamp
-- the count was count(*) not count(distinct), so it counted payment rows. The
-- event is one loan setup per quote, so this groups to the quote. Expect the
-- insert to land at or below the Fabric figure of 197.

insert INTO
ods.EpisodeEventStream
(
    SourceQuoteReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.QuoteReference,
    2,
    'Home',
    date_trunc('MINUTE', min(a.PaymentResponseResponseTimestamp)),
    cast(min(a.PaymentResponseResponseTimestamp) as date),
    'HA5.B1',
    'Home Acquisition - Payment and loan setup',
    'Quote'
from    stg.hfq_payments a
where   a.PaymentResponseResponseTimestamp >= '{run_start}'
and     a.PaymentResponseResponseTimestamp <  '{run_end}'
and     a.isFullPayment = 'false'
Group by a.QuoteReference
;


# In[ ]:


--HA5.1
-- was: count(distinct a.PolicyCode) against ods.EventStream
-- timestamp: d.EventDateTime from the source stream

insert INTO
ods.EpisodeEventStream
(
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.PolicyCode,
    1,
    'Home',
    date_trunc('MINUTE', min(d.EventDateTime)),
    cast(min(d.EventDateTime) as date),
    'HA5.1',
    'Home Acquisition - Terms of business sent',
    'Policy'
from    stg.GlobalPoliciesSold  a,
        ods.EventStream         d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime >= '{run_start}' and d.EventDateTime < '{run_end}'
and     a.ReportingSaleType = 'New Business'
and     d.EventDescription in
            (
                'New Business - Emailed Document - Terms Of Business',
                'New Business - Document Transmitted - Terms Of Business',
                'New Business - Emailed Document - Chill Terms of Business'
            )
Group by a.PolicyCode
;


# In[ ]:


--HA6
-- was: count(distinct PolicyCode) from edw.exp_mychill_chase_daily_snapshot_home
-- timestamp: the snapshot has no event timestamp, only SaleDate as a dd/mm/yyyy
-- string. The Motor A6 insert selects max(EventDateTime) and max(EventDate) from
-- this table, which do not exist on it. See question 2 at the bottom.
-- This draft uses the parsed SaleDate, which is the only date on the row.

insert INTO
ods.EpisodeEventStream
(
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.PolicyCode,
    1,
    'Home',
    date_trunc('MINUTE', min(try_cast(concat(right(a.SaleDate,4), '-', substring(a.SaleDate,4,2), '-', left(a.SaleDate,2)) as date))),
    min(try_cast(concat(right(a.SaleDate,4), '-', substring(a.SaleDate,4,2), '-', left(a.SaleDate,2)) as date)),
    'HA6',
    'Home Acquisition - Documents requested',
    'Policy'
FROM    edw.exp_mychill_chase_daily_snapshot_home a
Where   coalesce(try_cast(concat(right(a.SaleDate,4), '-', substring(a.SaleDate,4,2), '-', left(a.SaleDate,2)) as date),'1900-01-01') >= '{run_start_date}'
and     coalesce(try_cast(concat(right(a.SaleDate,4), '-', substring(a.SaleDate,4,2), '-', left(a.SaleDate,2)) as date),'1900-01-01') <  '{run_end_date}'
and     a.PolicyType = 'New Business'
and     a.Campaign = 'DAY 1'
and
case
    when a.Gap_In_Cov_Ltr_Status      = 'O' then 1
    when a.Val_For_Spec_Item_Status   = 'O' then 1
    when a.PPS_Num_Status             = 'O' then 1
    when a.Identification_Status      = 'O' then 1
    when a.Finance_Form_Status        = 'O' then 1
    when a.Digital_Journey_Status     = 'O' then 1
    else 0
End = 1
Group by a.PolicyCode
;


# In[ ]:


--HA6.F1
-- No count query existed. Same query as HA6 with Campaign = 'DAY 20', which is
-- how Motor A6.F1 is built. Note that Motor A6.F1 writes EventTypeId 'A6' and the
-- A6 description, so the last chase is indistinguishable from the first in the
-- stream today. See question 3.

insert INTO
ods.EpisodeEventStream
(
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.PolicyCode,
    1,
    'Home',
    date_trunc('MINUTE', min(try_cast(concat(right(a.SaleDate,4), '-', substring(a.SaleDate,4,2), '-', left(a.SaleDate,2)) as date))),
    min(try_cast(concat(right(a.SaleDate,4), '-', substring(a.SaleDate,4,2), '-', left(a.SaleDate,2)) as date)),
    'HA6.F1',
    'Home Acquisition - Number of chases before the customer submits',
    'Policy'
FROM    edw.exp_mychill_chase_daily_snapshot_home a
Where   coalesce(try_cast(concat(right(a.SaleDate,4), '-', substring(a.SaleDate,4,2), '-', left(a.SaleDate,2)) as date),'1900-01-01') >= '{run_start_date}'
and     coalesce(try_cast(concat(right(a.SaleDate,4), '-', substring(a.SaleDate,4,2), '-', left(a.SaleDate,2)) as date),'1900-01-01') <  '{run_end_date}'
and     a.PolicyType = 'New Business'
and     a.Campaign = 'DAY 20'
and
case
    when a.Gap_In_Cov_Ltr_Status      = 'O' then 1
    when a.Val_For_Spec_Item_Status   = 'O' then 1
    when a.PPS_Num_Status             = 'O' then 1
    when a.Identification_Status      = 'O' then 1
    when a.Finance_Form_Status        = 'O' then 1
    when a.Digital_Journey_Status     = 'O' then 1
    else 0
End = 1
Group by a.PolicyCode
;


# In[ ]:


--HA7
-- was: count(distinct PolicyCode) against ods.eventstream
-- timestamp: d.EventDateTime
-- the original count used EventDateTime > '2026-07-01' with no upper bound, so it
-- reached past the month end. Parameterised here with both bounds.

insert INTO
ods.EpisodeEventStream
(
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.PolicyCode,
    1,
    'Home',
    date_trunc('MINUTE', min(d.EventDateTime)),
    cast(min(d.EventDateTime) as date),
    'HA7',
    'Home Acquisition - Policy documents dispatched',
    'Policy'
FROM    stg.GlobalPoliciesSold  a,
        ods.EventStream         d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime >= '{run_start}' and d.EventDateTime < '{run_end}'
and     a.ReportingSaleType = 'New Business'
and     d.EventDescription in
            (
                'New Business - Emailed Document - Terms Of Business',
                'New Business - Document Transmitted - Terms Of Business',
                'New Business - Emailed Document - Chill Terms of Business',
                'New Business - Document Transmitted - Chill Terms of Business',
                'New Business - Emailed Document - 05E Terms Of Business'
            )
Group by a.PolicyCode
;


# In[ ]:


--HA7.B1.2
-- was: count(distinct PolicyCode) against ods.eventstream with the long document
-- name list. The list is kept verbatim.
-- timestamp: d.EventDateTime

insert INTO
ods.EpisodeEventStream
(
    SourcePolicyReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.PolicyCode,
    1,
    'Home',
    date_trunc('MINUTE', min(d.EventDateTime)),
    cast(min(d.EventDateTime) as date),
    'HA7.B1.2',
    'Home Acquisition - Document pack dispatched',
    'Policy'
FROM    stg.globalpoliciessold  a,
        ods.eventstream         d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime >= '{run_start}' and d.EventDateTime < '{run_end}'
and     a.ReportingSaleType = 'New Business'
and     (
            d.EventDescription like 'New Business - Emailed Document - %'
        or  d.EventDescription like 'New Business - Document Transmitted - %'
        )
and (
   d.EventDescription like '%04 - Suitability Statement'
Or d.EventDescription like '%05E Terms Of Business'
Or d.EventDescription like '%205 SOF- Proposal_Placeholder'
Or d.EventDescription like '%300 NB Home Email'
Or d.EventDescription like '%Chill Terms of Business'
Or d.EventDescription like '%Cover Letter'
Or d.EventDescription like '%CV Checklist Link'
Or d.EventDescription like '%CV Cover Letter'
Or d.EventDescription like '%CV Email Body'
Or d.EventDescription like '%CV Suitability Statment.'
Or d.EventDescription like '%Direct Debit Mandate'
Or d.EventDescription like '%Document Checklist Email'
Or d.EventDescription like '%Document Checklist SMS'
Or d.EventDescription like '%Gap In Cover Letter'
Or d.EventDescription like '%Home Cover Letter'
Or d.EventDescription like '%Home LOI_Placeholder'
Or d.EventDescription like '%Home Schedule_Placeholder'
Or d.EventDescription like '%Home SOF / Proposal_Placeholder'
Or d.EventDescription like '%Home Suitability Statement'
Or d.EventDescription like '%Insurance Product Information Document'
Or d.EventDescription like '%InsuranceProductInformationDocument'
Or d.EventDescription like '%Insurer Doc 1_Placeholder'
Or d.EventDescription like '%Insurer Doc 2_Placeholder'
Or d.EventDescription like '%Insurer Doc 3_Placeholder'
Or d.EventDescription like '%Interested Party'
Or d.EventDescription like '%Interested Party - Allied Irish Bank plc(AIB Mortgage Bank)'
Or d.EventDescription like '%Interested Party - Bank of Ireland (2 College Green)(Bank of Ireland)'
Or d.EventDescription like '%Interested Party - Bank of Ireland Mortgage Bank U.C.(College Green)'
Or d.EventDescription like '%Interested Party - Bank of Ireland Mortgages(Dublin - 2 College Green)'
Or d.EventDescription like '%Interested Party - Bank of Ireland(College Green)'
Or d.EventDescription like '%Interested Party - Bankinter SA(Maynooth)'
Or d.EventDescription like '%Interested Party - EBS D.A.C(Artane)'
Or d.EventDescription like '%Interested Party - Haven Mortgages Limited(Head Office)'
Or d.EventDescription like '%Interested Party - Permanent TSB(Dublin - Head Office)'
Or d.EventDescription like '%Interested Party - Permanent TSB(Head Office)'
Or d.EventDescription like '%InterestedParty'
Or d.EventDescription like '%Key Facts'
Or d.EventDescription like '%Premium Breakdown'
Or d.EventDescription like '%PremiumBreakdown'
Or d.EventDescription like '%Quote Breakdown'
Or d.EventDescription like '%Receipt'
Or d.EventDescription like '%Receipt_Template'
Or d.EventDescription like '%Schedule'
Or d.EventDescription like '%Statement Of Fact'
Or d.EventDescription like '%StatementOfFact'
Or d.EventDescription like '%Terms Of Business'
)
Group by a.PolicyCode
;


# =============================================================================
# SECTION B: needs a decision before it goes in
# =============================================================================


# In[ ]:


--HA1.E2
-- was: count(distinct CustomerPhoneNumber) from stg.A0_genesys_derived_data where
--      queueName = 'OUTBOUND_SALES_HOME'
--
-- DECISION NEEDED. The count is per phone number. The event stream has no phone
-- number column, and Motor A0 puts ConversationId in EventSourceID instead. This
-- draft switches the grain to the conversation, which will read slightly higher
-- than the Fabric figure of 5 if a customer was called twice. At these volumes it
-- makes no practical difference, but the rule matters for the Motor equivalents.
--
-- Confirm: conversation grain, or keep phone number grain and add a column?

insert INTO
ods.EpisodeEventStream
(
    EventSourceID,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.ConversationId,
    2,
    'Home',
    date_trunc('MINUTE', min(a.conversationStartTime)),
    cast(min(a.conversationStartTime) as date),
    'HA1.E2',
    'Home Acquisition - Outbound sales callback',
    'Call'
from    stg.A0_genesys_derived_data a,
        (select ConversationId, max(sessionIndex) sessionIndex
         from   stg.A0_genesys_derived_data
         Where  queueName is not null
         Group by ConversationId
        ) b
where   a.ConversationId = b.ConversationId
and     a.sessionIndex = b.sessionIndex
and     a.queueName = 'OUTBOUND_SALES_HOME'
and     a.conversationStartTime >= '{run_start}' and a.conversationStartTime < '{run_end}'
Group by a.ConversationId
;


# In[ ]:


--HA1.F1
-- was: count(*) of stg.HA1_HFQ_Quotes left joined to the Home TYR campaign sends
--      on a.proposer_email = b.email, keeping the misses
--
-- DECISION NEEDED, two points.
-- 1. The count is count(*) on a left join, so a quote that matched nothing is
--    counted once but the join can still fan out. Grouping to the quote fixes it.
-- 2. The recon tab describes HA1.F1 as "Outbound campaigns to quotes that never
--    got a price", source HFQ/CRM XP. The count as written is "quotes that never
--    got a campaign email", which is close to the opposite. Which one is the
--    event? This draft implements the query as written, not the description.

insert INTO
ods.EpisodeEventStream
(
    SourceQuoteReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.QuoteCodeReference,
    2,
    'Home',
    date_trunc('MINUTE', min(a.ts_unix)),
    cast(min(a.ts_unix) as date),
    'HA1.F1',
    'Home Acquisition - Outbound campaigns to quotes that never got a price',
    'Quote'
from    stg.HA1_HFQ_Quotes a
left join
        (select email, QuoteQueryGuid
         from   dlk.EXT_XtremePushResults
         where  `timestamp` >= '{run_start}' and `timestamp` < '{run_end}'
         and    campaign_name like 'Home % TYR %'
         and    interaction_type = 'sent'
         and    MessageType = 'EMAIL'
        ) b
        on a.proposer_email = b.email
where   b.QuoteQueryGuid is null
and     a.ts_unix >= '{run_start}' and a.ts_unix < '{run_end}'
Group by a.QuoteCodeReference
;


# In[ ]:


--HA3.F1
-- No count query existed. Fabric shows 3,531.
--
-- DECISION NEEDED. Motor A3.F1 keys off stg.A3_SL10_QQGUIDS with InsurersQuoted = 'N',
-- and there is no Home equivalent of that table. The nearest Home logic is the
-- inverse of HA3: a quote that reached hfq_response_quotes but never returned a
-- premium. That is what this draft does. Confirm it against the 3,531 before use.

insert INTO
ods.EpisodeEventStream
(
    SourceQuoteReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    a.QuoteCodeReference,
    2,
    'Home',
    date_trunc('MINUTE', min(a.Quotes_DateCreated)),
    cast(min(a.Quotes_DateCreated) as date),
    'HA3.F1',
    'Home Acquisition - No price returned, told to call us',
    'Quote'
from    dlk.hfq_response_quotes a
where   a.Quotes_DateCreated >= '{run_start}' and a.Quotes_DateCreated < '{run_end}'
and     a.QuoteCodeReference not in
            (select QuoteCodeReference
             from   dlk.hfq_response_quotes
             where  Quotes_Premium > 0
             and    Quotes_Outcome = 'PremiumReturned'
             and    Quotes_DateCreated >= '{run_start}' and Quotes_DateCreated < '{run_end}'
            )
Group by a.QuoteCodeReference
;


# =============================================================================
# SECTION C: blocked
# =============================================================================
#
# HA0, straight into the CALL CENTRE
#   The count reads stg.A0_MFQ_genesys_link, which is built from
#   stg.A0_genesys_derived_data_filtered where queueName = 'INBOUND_SALES_MOTOR'.
#   As written the Home count returns the Motor number. A Home version needs three
#   new staging cells: a Home filtered Genesys table on 'INBOUND_SALES_HOME', an
#   HFQ phone number table equivalent to stg.A0_mfq_derived_data, and the link
#   between them. dlk.hfq_quotedetails_snapshot_v2 is only ever read for
#   proposer_email in this notebook, so I do not know which column holds the
#   customer phone number. Tell me the column and I will build all three.
#
# HA0.F1, call wait time or fails to make contact
#   The count reads stg.HA0F1_genesys_inbound_call_duration_summary, which is never
#   created anywhere in the notebook. The Motor table
#   stg.A0F1_genesys_inbound_call_duration_summary exists but is hardcoded to
#   'INBOUND_SALES_MOTOR'. Once the Home queue name is confirmed this is a copy of
#   that cell with the queue swapped, and then the insert is a copy of Motor A0.F1.
#
#
# =============================================================================
# OPEN QUESTIONS
# =============================================================================
#
# 1. SourceSystemId has no consistent rule in the notebook today.
#    stg.GlobalPoliciesSold is written as 2 in some inserts and 9 in others.
#    edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan is written as 1 in some and 4 in
#    others. Is there a lookup table for this? If not, the Home work is a good
#    moment to fix the map, and the Motor inserts should be corrected to match.
#
# 2. Motor A6 and A6.F1 select max(EventDateTime) and max(EventDate) from
#    edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan. Neither column appears anywhere
#    else against that table. If they do not exist, both inserts fail at runtime.
#    Worth running before the Home versions are modelled on them.
#
# 3. Several existing inserts select a non-aggregated column alongside max() with
#    no GROUP BY: Motor A6, A6.F1 and A7 all do this. Spark will reject that. Every
#    draft above carries an explicit Group by, which is the main structural
#    difference from the Motor cells.
#
# 4. Motor A6.F1 writes EventTypeId 'A6' with the A6 description, so the DAY 20
#    chase is stored as if it were the DAY 1 chase. The HA6.F1 draft above writes
#    'HA6.F1'. If you want Home to match Motor exactly for now, say so and I will
#    change it, but it looks like a bug in the Motor cell.
#
# 5. Motor A1.E1 writes QuoteQueryGuid into SourcePolicyReference with Grain
#    'Policy'. A quote guid in a policy column looks wrong. The HA1.E1 draft above
#    uses SourceQuoteReference and Grain 'Quote'.
#
# 6. stg.hfq_payments, stg.hfq_price_requested and stg.hfq_prices are read by the
#    Home cells but created in neither this notebook nor anything I can see. I have
#    assumed they come from notebook 02. Confirm the column names are as used above,
#    in particular QuoteReference, isFullPayment and
#    PaymentResponseResponseTimestamp.
#
# 7. Date parameters. These drafts use {run_start} and {run_end} for timestamps and
#    {run_start_date} and {run_end_date} for date columns, matching the Motor cells.
#    Confirm that is right for the chase snapshot, which holds a dd/mm/yyyy string.
