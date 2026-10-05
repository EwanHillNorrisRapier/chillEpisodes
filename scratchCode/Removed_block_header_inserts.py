#!/usr/bin/env python
# coding: utf-8

# ## Inserts removed from block header steps, 14 September 2026
#
# Each of these sat under a .B1, .B2 or .PC step id. Those ids are headings for a block
# of numbered sub-steps, not events, and each insert here reproduced the volume of one of
# its own sub-steps. They are kept only so the logic is not lost while the sub-step
# inserts are built out.


# In[ ]:

--A3.B1
-- removed block header insert. Sub-steps: A3.B1.1, A3.B1.2
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
    2,
    'Motor',
    date_trunc('MINUTE', a.LastStep5DateTime),
    cast(a.LastStep5DateTime as date),
    'A3.B1',
    'Motor Acquisition - Quote retrieve and re-quote cycles',
    'Quote'
from    stg.A1_MotorAcquisitionQuoteInitiated a  
JOIN 
        stg.A1_MotorAcquisitionQuoteInitiated b
            on a.QuoteQueryGuid = b.RetrieveSessionToken
("")


# In[ ]:

--A5.B1
-- removed block header insert. Sub-steps: A5.B1.1, A5.B1.2, A5.B1.3, A5.B1.4, A5.B1.5
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
    QuoteQueryGuid,
    2,
    'Motor',
    date_trunc('MINUTE', PaymentDate),
    cast(PaymentDate as date),
    'A5.B1',
    'Motor Acquisition - Loan setup with the finance provider',
    'Quote'
from    stg.MFQ_Quote_Payments
Where   PaymentDate >= (select startTime from stg.episodeeventstream_buildconfig) and PaymentDate < (select endTime   from stg.episodeeventstream_buildconfig) 
and     PaymentType in (0,5)
and     FullPaymentFlag is FALSE 
("")


# In[ ]:

--HA5.B1
-- removed block header insert. Sub-steps: HA5.B1.1, HA5.B1.2, HA5.B1.3, HA5.B1.4, HA5.B1.5
--*
--PaymentResponseType,
--PaymentResponseResponseActionResultCode = 'DECLINED' 

-- converted from the count query. The plain count of part payment rows is grouped to QuoteReference, the same grain the sibling HFQ payment steps use, and the loan setup is treated as a completion.

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
    'HA5.B1',
    'Home Acquisition - Payment and loan setup',
    'Quote'
from    stg.HFQ_payments    a
where   a.PaymentResponseResponseTimestamp >= (select startTime from stg.episodeeventstream_buildconfig) and a.PaymentResponseResponseTimestamp < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.isFullPayment = 'false'
Group by a.QuoteReference
;


# In[ ]:

--HM4.B1
-- removed block header insert. Sub-steps: HM4.B1.1, HM4.B1.2, HM4.B1.3, HM4.B1.4, HM4.B1.5, HM4.B1.6
-- converted from the count query. Timestamp from the upload event Timestamp on dlk.MyChill_NewUploadDocumentEvents, using min for the first upload.

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
    b.PolicyCode,
    1,
    'Home',
    date_trunc('MINUTE', min(b.`Timestamp`)),
    cast(min(b.`Timestamp`) as date),
    'HM4.B1',
    'Home MTA - Document intake',
    'Policy'
from    stg.JJulyMTAs a, dlk.MyChill_NewUploadDocumentEvents  b
Where   a.PolicyCode = b.PolicyCode
and     b.`Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and b.`Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
and     b.PolicyCode in
        (
            select  distinct a.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Home'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
        )
Group by b.PolicyCode
;


# In[ ]:

--HR2.B1
-- removed block header insert. Sub-steps: HR2.B1.1, HR2.B1.2, HR2.B1.3
-- converted from the count query. Both staging tables are built first, the source is the HFQ quoting platform so SourceSystemId is 2, and the ts_unix lookback from 2026-05-01 to 2026-08-01 is kept exactly as it is so no build config run window applies.

Create or Replace Table stg.HomeRenewalScvCustomerKeys as
select  distinct scv_customer_key , PolicyCode, ClientCode
from    ods.scv_customer_key  a, (select PolicyCode, left(PolicyCode,6) as ClientCode from stg.R0_HomePoliciesEligibleForRenewals) b
Where   a.SourceSystemReference = b.ClientCode
and     a.SourceSystemId = 1
;

Create or Replace Table stg.HomeRenewalsDoingHFQ as
select  distinct a.scv_customer_key, a.PolicyCode, b.QuoteCodeReference, ts_unix as QuoteStartDateTime
from    stg.HomeRenewalScvCustomerKeys a, stg.HFQ_Quotes b, ods.scv_customer_key c
Where   a.scv_customer_key = c.scv_customer_key
and     b.QuoteCodeReference = c.SourceSystemReference
and     ts_unix between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000'
and     SourceSystemId = 3
;

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
    2,
    'Home',
    date_trunc('MINUTE', min(a.QuoteStartDateTime)),
    cast(min(a.QuoteStartDateTime) as date),
    'HR2.B1',
    'Home Renewal - Online re-quote for another price',
    'Policy'
from    stg.HomeRenewalsDoingHFQ a
Group by a.PolicyCode
;


# In[ ]:

--HR3.B1
-- removed block header insert. Sub-steps: HR3.B1.1, HR3.B1.2
-- converted from the count query. The staging table is built first because later steps read it, the only timestamp available is RenewalDate, and the original query carries no date window of its own, so no build config run window applies.

Create or Replace Table stg.HR3B1_LapsedThisYearPolicy as
select  distinct b.PolicyCode , b.RenewalDate
from    dlk.rbsdata2_policy_physical a,
        stg.R0_HomePoliciesEligibleForRenewals b
Where   trim(a.pl_code) = trim(b.PolicyCode)  -- trim is important as the source tables have trailing spaces
and     trim(a.pl_status) = 'L'
;

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
    date_trunc('MINUTE', max(a.RenewalDate)),
    cast(max(a.RenewalDate) as date),
    'HR3.B1',
    'Home Renewal - This year lapsed',
    'Policy'
from    stg.HR3B1_LapsedThisYearPolicy a
Group by a.PolicyCode
;


# In[ ]:

--HR4.B2
-- removed block header insert. Sub-steps: HR4.B2.1, HR4.B2.2, HR4.B2.3, HR4.B2.4, HR4.B2.5, HR4.B2.6
-- from XX - Episode Reconciliation - Gaps.html, cell 18 (note or select)
-- header: docs asked for HR4.B2
-- header: Home	Renewal	HR4.B2.F1 --  day 1 should be the full chase and then day 7 / 14 / 20 should reduce as people submit docs and get them approved..
-- header: -- these voluems are messed up for some reason -- so redone below on the 08th
--and Campaign = 'DAY 1'

-- converted from the count query. The Group by Campaign and Order by were dropped as an eyeballing breakdown, the timestamp is the same derived SaleDate expression the notebook uses on this table, and the window from 2026-05-01 to 2026-07-31 is kept exactly as it is so no build config run window applies.

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
    date_trunc('MINUTE', min(coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01'))),
    cast(min(coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01')) as date),
    'HR4.B2',
    'Home Renewal - Documents requested',
    'Policy'
from    edw.EXP_MyChill_Chase_Daily_Snapshot_Home a,
        stg.R0_HomePoliciesEligibleForRenewals b
Where   coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') between '2026-05-01' and '2026-07-31'
and     a.PolicyType = 'Renewals'
and     a.PolicyTypeGroup = 'Home'
and     a.PolicyCode = b.PolicyCode
and case
        When a.Comp_DDM_Status              = 'O' then 1
        When a.Gap_In_Cov_Ltr_Status        = 'O' then 1
        When a.Val_For_Spec_Item_Status     = 'O' then 1
        When a.PPS_Num_Status               = 'O' then 1
        When a.Identification_Status        = 'O' then 1
        When a.Digital_Journey_Status       = 'O' then 1
        When a.Finance_Form_Status          = 'O' then 1
        else 0
    End = 1
Group by a.PolicyCode
;


# In[ ]:

--HR6.B1
-- removed block header insert. Sub-steps: HR6.B1.1, HR6.B1.2, HR6.B1.3, HR6.B1.4, HR6.B1.5
-- converted from the count query. The wrapper count(*) sits over one row per PolicyCode so the insert groups to PolicyCode, and the window from 2026-06-01 to 2026-08-01 is kept exactly as it is so no build config run window applies.

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
    'HR6.B1',
    'Home Renewal - Policy fulfilment',
    'Policy'
FROM    stg.R0_HomePoliciesEligibleForRenewals  a,
        ods.EventStream                          d
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime between '2026-06-01 00:00:00.000' and '2026-08-01 00:00:00.000'
AND     d.EventDescription not like 'Renewal Offer - %'
AND     (
            d.EventDescription like '%Emailed Document%'
        OR
            d.EventDescription like '%Document Transmitted%'
        )
Group by a.PolicyCode
;


# In[ ]:

--R2.B1
-- removed block header insert. Sub-steps: R2.B1.1, R2.B1.2, R2.B1.3, R2.B1.4
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
SELECT  PolicyCode,
        1,
        'Motor',
        max(date_trunc('MINUTE', QuoteStartDatetime)),
        max(cast(QuoteStartDatetime as date)),
        'R2.B1',
        'Motor Renewal - Online re-quote (MFQ) for another price',
        'Policy'
FROM    stg.RenewalsDoingMFQ 
group by PolicyCode
("")


# In[ ]:

--R3.B1
-- removed block header insert. Sub-steps: R3.B1.1, R3.B1.2, R3.B1.3, R3.B1.4
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
SELECT  b.PolicyCode,
        1,
        'Motor',
        max(date_trunc('MINUTE', RenewalStartDate)),
        max(cast(RenewalStartDate as date)),
        'R3.B1',
        'Motor Renewal - Customer renews ONLINE',
        'Policy' 
from    dlk.rbsdata2_policy_physical a, stg.R0_MotorPoliciesEligibleForRenewals b
Where   trim(a.pl_code) = trim(b.PolicyCode)  -- trim is important as the source tables have trailing spaces -- Urska needs to address this 
and     trim(a.pl_status) = 'L' 
Group by b.PolicyCode


# In[ ]:

--VA5.B1
-- removed block header insert. Sub-steps: VA5.B1.1, VA5.B1.2, VA5.B1.3, VA5.B1.4, VA5.B1.5
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
        a.QuoteReference,
        1,
        'Travel',
        max(date_trunc('MINUTE', QuoteStartDateTime)),
        max(cast(QuoteStartDateTime as date)),
        'VA5.B1',
        'Van Acquisition - Payment and loan setup',
        'Quote'
from dlk.VanPaymentJourney
WHERE   QuoteStartDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and QuoteStartDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     PaymentStatus = 'Success'
and     PaymentType = 'Instalments'
Group by a.QuoteReference


# In[ ]:

--VR3.B1
-- removed block header insert. Sub-steps: VR3.B1.1, VR3.B1.2
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
SELECT  UserID,
        1,
        'Van',
        max(date_trunc('MINUTE', `timestamp`)),
        max(cast(`timestamp` as date)),
        'VR3.B1',
        'Van Renewals - This year lapsed',
        'User'
from    dlk.EXT_XtremePushResults a, stg.VanRenewals b 
where campaign_name like '%This Year Lapsed%' and a.PolicyCode = b.PolicyCode 
and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
and     interaction_type = 'sent' 
and     MessageType  in ( 'EMAIL', 'SMS') 
group by UserID


# In[ ]:

--VR4.B2
-- removed block header insert. Sub-steps: VR4.B2.1, VR4.B2.2, VR4.B2.3, VR4.B2.4, VR4.B2.5, VR4.B2.6
-- from XX - Episode Reconciliation - Gaps.html, cell 88 (count query)
-- header: Van	Renewal	VR4.B2

-- converted from the count query. First occurrence of the request document so min of EventDateTime is used, the renewal lookback window of 2026-05-01 to 2026-08-10 is kept exactly as written, and stg.VanRenewalsJuly is left unrenamed.

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
    b.PolicyCode,
    1,
    'Van',
    date_trunc('MINUTE', min(EventDateTime)),
    cast(min(EventDateTime) as date),
    'VR4.B2',
    'Van Renewal - Documents requested',
    'Policy'
from    ods.eventstream a, stg.VanRenewalsJuly b
Where   a.SourcePolicyReference = b.TyPolicyCode
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
and     EventDescription like '%Body%'
and     (   EventDescription like '%Emailed Document%'
        or
            EventDescription like '%Document Transmitted%'
        )
Group by b.PolicyCode
;

