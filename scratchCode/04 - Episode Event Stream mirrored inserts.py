#!/usr/bin/env python
# coding: utf-8

# ## 04 - Episode Event Stream, mirrored inserts
#
# Draft inserts for steps that had none, each built from the same step already working for another
# product. Nothing here has been added to "03 - Populate Episode Event Stream.py". Review, then move
# the cells you are happy with across.
#
# 30 inserts, covering the yellow highlighted steps that had an equivalent to copy.
# 14 could not be mirrored and are listed at the end with the reason.
#
# Each cell names the donor step it came from. Date windows follow the donor: where the donor used
# the build config run window it is kept, and where it used a literal window such as 2026-05-01 to
# 2026-08-10 that literal is kept too.


# Home Renewal

# In[ ]:

--HR3.B1.2
-- mirrored from R3.B1.2. The Motor donor was taken because it uses min of the send timestamp for the start of the sequence, the renewals table and the campaign name filter swap to Home, and the literal window of 2026-05-01 to 2026-08-10 is kept exactly as the donor has it.
-- Fabric volume for this step: 1243

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
    x.PolicyCode,
    1,
    'Home',
    date_trunc('MINUTE', min(x.SentTimestamp)),
    cast(min(x.SentTimestamp) as date),
    'HR3.B1.2',
    'Home Renewal - Lapse CRM sequence runs',
    'Policy'
from    (
            select  distinct b.PolicyCode, a.`timestamp` as SentTimestamp
            from    dlk.EXT_XtremePushResults a, stg.R0_HomePoliciesEligibleForRenewals b
            where   campaign_name like '%Home%'
            and     campaign_name like '%Lapsed%'
            and     a.PolicyCode = b.PolicyCode
            and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
            and     interaction_type = 'sent'
            and     MessageType  in ( 'EMAIL', 'SMS')
            union
            select  distinct b.PolicyCode, a.`timestamp` as SentTimestamp
            from    dlk.EXT_XtremePushResults_Policy a, stg.R0_HomePoliciesEligibleForRenewals b
            where   campaign_name like '%Home%'
            and     campaign_name like '%Lapsed%'
            and     a.PolicyCode = b.PolicyCode
            and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
            and     interaction_type = 'sent'
            and     MessageType  in ( 'EMAIL', 'SMS')
        ) x
Group by x.PolicyCode
;

# In[ ]:

--HR3.B1.2.F1
-- mirrored from VR3.B1.2.F1. The Van donor was taken because it carries the bounce clause that makes the policy unreachable, which is the shape the notebook's own Home count query for this step already uses, and the literal window of 2026-05-01 to 2026-08-10 is kept exactly as the donor has it.
-- Fabric volume for this step: 32

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
    date_trunc('MINUTE', max(a.`timestamp`)),
    cast(max(a.`timestamp`) as date),
    'HR3.B1.2.F1',
    'Home Renewal - Unreachable on the lapse sequence',
    'Policy'
from    dlk.EXT_XtremePushResults_Policy a, stg.R0_HomePoliciesEligibleForRenewals b
where   campaign_name like '%Home%'
and     campaign_name like '%Lapsed%'
and     a.PolicyCode = b.PolicyCode
and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
and     interaction_type = 'sent'
and     MessageType  in ( 'EMAIL', 'SMS')
and     a.PolicyCode not in
        (
            select  distinct a.PolicyCode
            from    dlk.EXT_XtremePushResults_Policy a, stg.R0_HomePoliciesEligibleForRenewals b
            where   campaign_name like '%Home%'
            and     campaign_name like '%Lapsed%'
            and     a.PolicyCode = b.PolicyCode
            and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
            and     interaction_type in ('open','click')
            and     MessageType  in ( 'EMAIL', 'SMS')
        )
and     a.PolicyCode in
        (
            select  distinct a.PolicyCode
            from    dlk.EXT_XtremePushResults_Policy a, stg.R0_HomePoliciesEligibleForRenewals b
            where   campaign_name like '%Home%'
            and     campaign_name like '%Lapsed%'
            and     a.PolicyCode = b.PolicyCode
            and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
            and     interaction_type in ('bounce')
            and     MessageType  in ( 'EMAIL', 'SMS')
        )
Group by a.PolicyCode
;

# In[ ]:

--HR4.B2.3
-- mirrored from R4.B2.3. Straight swap of the renewals table and the product literal, with the build config run window, the extra cut off at 2026-09-01 and the isAccepted filter all kept exactly as the donor has them.
-- Fabric volume for this step: 23

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
SELECT  a.PolicyCode,
        1,
        'Home',
        max(date_trunc('MINUTE', `Timestamp`)),
        max(cast(`Timestamp` as date)),
        'HR4.B2.3',
        'Home Renewal - Documents validated',
        'Policy'
from    stg.R0_HomePoliciesEligibleForRenewals a, dlk.MyChillWorkflow_DocumentStatus  b
Where   a.TyPolicyCode = b.PolicyCode
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
and     `Timestamp` < '2026-09-01 00:00:00.000'
and     isAccepted = 'true'
Group by a.PolicyCode
;

# In[ ]:

--HR4.B2.6
-- mirrored from R4.B2.6. Straight swap of the renewals table and the product literal, with the build config run window, the extra cut off at 2026-09-01 and the isAccepted filter all kept exactly as the donor has them.
-- Fabric volume for this step: 46

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
SELECT  a.PolicyCode,
        1,
        'Home',
        max(date_trunc('MINUTE', `Timestamp`)),
        max(cast(`Timestamp` as date)),
        'HR4.B2.6',
        'Home Renewal - Documents received and validated',
        'Policy'
from    stg.R0_HomePoliciesEligibleForRenewals a, dlk.MyChillWorkflow_DocumentStatus  b
Where   a.TyPolicyCode = b.PolicyCode
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
and     `Timestamp` < '2026-09-01 00:00:00.000'
and     isAccepted = 'true'
Group by a.PolicyCode
;

# In[ ]:

--HR4.B2.F1
-- mirrored from VR4.B2.F1. The chase snapshot swaps to the Home table with PolicyTypeGroup set to Home, the open document status list is cut back to the seven statuses the notebook's own Home chase queries read because the Motor and Van vehicle statuses are not on the Home table, and the literal window of 2026-05-01 to 2026-07-31 is kept exactly as the donor has it.
-- Fabric volume for this step: 481

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
    date_trunc('MINUTE', max(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
    cast(max(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01')) as date),
    'HR4.B2.F1',
    'Home Renewal - Chases before the customer submits, and documents never submitted',
    'Policy'
from    edw.EXP_MyChill_Chase_Daily_Snapshot_Home a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-05-01' and '2026-07-31'
and PolicyType = 'Renewals'
and PolicyTypeGroup = 'Home'
and case
        When Comp_DDM_Status                = 'O' then 1
        When Gap_In_Cov_Ltr_Status          = 'O' then 1
        When Val_For_Spec_Item_Status       = 'O' then 1
        When PPS_Num_Status                 = 'O' then 1
        When Identification_Status          = 'O' then 1
        When Digital_Journey_Status         = 'O' then 1
        When Finance_Form_Status            = 'O' then 1
        else 0
    End = 1
Group by a.PolicyCode
;

# In[ ]:

--HR5
-- mirrored from R5. Straight swap of the renewals table and the product literals, with the donor's a.EventDateTime qualified as d.EventDateTime because the timestamp comes from ods.EventStream and not from the renewals table, the suitability statement list left verbatim, and the literal window of 2026-05-01 to 2026-08-01 kept as the donor has it.
-- Fabric volume for this step: 5192

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
SELECT  a.PolicyCode,
        1,
        'Home',
        max(date_trunc('MINUTE', d.EventDateTime)),
        max(cast(d.EventDateTime as date)),
        'HR5',
        'Home Renewal - Renewal processed, policy continued',
        'Policy'
from    stg.R0_HomePoliciesEligibleForRenewals   a,
        ods.EventStream                          d
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000'
and     EventDescription IN
    (
        'Renewal Confirmation - Emailed Document - Suitability Statement',
        'Renewal Transfer - Emailed Document - Motor Suitability Statement',
        'New Business - Emailed Document - Suitability Statement',
        'Renewal Confirmation - Document Transmitted - Suitability Statement',
        'Renewal Transfer - Document Transmitted - Motor Suitability Statement',
        'New Business - Document Transmitted - Suitability Statement',
        'New Business - Document Transmitted - Motor Suitability Statement'
    )
Group by a.PolicyCode
;

# In[ ]:

--HR6
-- mirrored from R6. Straight swap of the renewals table and the product literals, with the donor's a.EventDateTime qualified as d.EventDateTime, the missing comma before the last description in the list added, the certificate descriptions left verbatim as the donor has them, and the literal window of 2026-05-01 to 2026-08-01 kept as written.
-- Fabric volume for this step: 4980

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
SELECT  a.PolicyCode,
        1,
        'Home',
        max(date_trunc('MINUTE', d.EventDateTime)),
        max(cast(d.EventDateTime as date)),
        'HR6',
        'Home Renewal - Renewal documents dispatched',
        'Policy'
from    stg.R0_HomePoliciesEligibleForRenewals   a,
        ods.EventStream                          d
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000'
and     EventDescription IN
    (
        'Renewal Confirmation - Document Transmitted - RNL Cert Issue Letter',
        'Renewal Confirmation - Document Transmitted - Certificate',
        'Renewal Transfer - Document Transmitted - RNL Cert Issue Letter',
        'Renewal Transfer - Document Transmitted - Certificate',
        'New Business - Document Transmitted - NB Cert Issue Letter',
        'New Business - Document Transmitted - Certificate',
        'Renewal Confirmation - Emailed Document - Certificate',
        'Renewal Transfer - Emailed Document - Certificate',
        'Renewal Transfer - Printed Document - RNL Cert Issue Letter'
    )
Group by a.PolicyCode
;

# In[ ]:

--HR6.B1.1
-- mirrored from VR6.B1.1. Straight swap of stg.VanRenewalsJuly for the Home renewals table and of the product literal, with no PolicyTypeGroup filter added to ods.EventStream because the donor carries none and the join to TyPolicyCode already confines the rows to Home renewals, and the literal window of 2026-05-01 to 2026-08-10 kept exactly as written.
-- Fabric volume for this step: 4980

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
    date_trunc('MINUTE', max(EventDateTime)),
    cast(max(EventDateTime) as date),
    'HR6.B1.1',
    'Home Renewal - Policy documents dispatched',
    'Policy'
from    ods.eventstream a, stg.R0_HomePoliciesEligibleForRenewals b
Where   a.SourcePolicyReference = b.TyPolicyCode /* new policy */
and     PolicyRetNum = 1
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
and     (   EventDescription like '%Emailed Document%'
        or
            EventDescription like '%Document Transmitted%'
        )
and     EventDescription not like 'Renewal Offer%'
and     EventDescription not like 'Document Chase%'
Group by b.PolicyCode
;

# In[ ]:

--HR6.B1.5
-- mirrored from R6.B1.5. Straight swap of the renewals table and the product literals, with the Duplicate Certificate filter and the literal window of 2026-05-01 to 2026-08-01 kept exactly as the donor has them.
-- Fabric volume for this step: 0

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
SELECT  a.PolicyCode,
        1,
        'Home',
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDateTime as date)),
        'HR6.B1.5',
        'Home Renewal - Replacement requested',
        'Policy'
from    stg.R0_HomePoliciesEligibleForRenewals   a,
        ods.EventStream                          d
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000'
and     EventDescription like 'Duplicate Certificate%'
Group by a.PolicyCode
;


# Motor Acquisition

# In[ ]:

--A6.B1.4
-- mirrored from HA6.B1.4. straight swap of the chase snapshot to edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan with PolicyTypeGroup Motor added, keeping the donor's subquery, its six document status columns and the DAY 1 campaign filter.
-- Fabric volume for this step: 9662

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
        x.PolicyCode,
        1,
        'Motor',
        date_trunc('MINUTE', max(x.SaleDateTime)),
        cast(max(x.SaleDateTime) as date),
        'A6.B1.4',
        'Motor Acquisition - Chase, first reminder',
        'Policy'
From    (
            select  PolicyCode,
                    max(coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01')) SaleDateTime
            from    edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan   a
            Where   coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
            and     a.PolicyType = 'New Business'
            and     a.PolicyTypeGroup = 'Motor'
            and     case
                when Gap_In_Cov_Ltr_Status = 'O' then 1
                when Val_For_Spec_Item_Status = 'O' then 1
                when PPS_Num_Status = 'O' then 1
                When Identification_Status = 'O' then 1
                when Finance_Form_Status = 'O' then 1
                when Digital_Journey_Status = 'O' then 1
                else 0
            End = 1
            and     a.campaign = 'DAY 1'
            Group by PolicyCode
        )   x
Group by x.PolicyCode
;

# In[ ]:

--A6.B1.F1
-- mirrored from VA6.B1.F1. same chase snapshot table with PolicyTypeGroup switched to Motor, and the donor's literal 2026-05-01 to 2026-07-31 chase window and its PolicyType Renewals filter are both kept exactly as written.
-- Fabric volume for this step: 1178

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
    PolicyCode,
    1,
    'Motor',
    date_trunc('MINUTE', min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
    cast(min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01')) as date),
    'A6.B1.F1',
    'Motor Acquisition - Documents never submitted, policy at risk. Bites A5a customers hardest',
    'Policy'
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-05-01' and '2026-07-31'
and PolicyType = 'Renewals'
and PolicyTypeGroup = 'Motor'
and case
        when Sign_Prop_Status				= 'O' then 1
        when Sign_Stat_Of_Fact_Status		= 'O' then 1
        when Comp_Fin_Agree_Status			= 'O' then 1
        when Comp_DDM_Status				= 'O' then 1
        when Proof_Of_NCB_Status			= 'O' then 1
        when Trans_Proof_Of_NCB_Status		= 'O' then 1
        when Ltr_Of_Driv_Exp_Status			= 'O' then 1
        when Prop_Driv_Lic_Status			= 'O' then 1
        when Nam_Driv_Lic_Status			= 'O' then 1
        when Gap_In_Cov_Ltr_Status			= 'O' then 1
        when `2ndCar_Cert_Status`			= 'O' then 1
        when Doc_Ltr_Status					= 'O' then 1
        when Engineers_Rpt_Status			= 'O' then 1
        when NCT_Status						= 'O' then 1
        when Veh_Lic_Cert_Status			= 'O' then 1
        when Irish_Reg_Status				= 'O' then 1
        when Main_Driver_Dec_Status			= 'O' then 1
        when Soc_Dom_Pleas_Dec_Status		= 'O' then 1
        when Comp_Car_Exper_Status			= 'O' then 1
        when DD_Conf_Ltr_Status				= 'O' then 1
        when Comp_Fin_Mand_Status			= 'O' then 1
        when Val_For_Spec_Item_Status		= 'O' then 1
        when Dri_Lic_Num_Status				= 'O' then 1
        when Comp_Lost_Cert_Dec_Status		= 'O' then 1
        when Orig_Cert_Status				= 'O' then 1
        when Cancel_Req_Status				= 'O' then 1
        when PPS_Num_Status					= 'O' then 1
        when Afford_State_Status			= 'O' then 1
        when Identification_Status			= 'O' then 1
        when Digital_Journey_Status			= 'O' then 1
        when Finance_Form_Status			= 'O' then 1
        else 0
    End = 1
Group by PolicyCode
;


# Motor Cancellation

# In[ ]:

--C1a.F1
-- mirrored from HC1a.F1. both source tables are shared, so only the PolicyTypeGroup literal moves to Motor, and the donor's literal 2026-07-31 effective date and NCT short description filter are kept.
-- Fabric volume for this step: 353

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
    'Motor',
    date_trunc('MINUTE', max(b.PolicyCancelDate)),
    cast(max(b.PolicyCancelDate) as date),
    'C1a.F1',
    'Motor Cancellation - Call wait time, or fails to make contact',
    'Policy'
from    edw.tbl_fact_policy_mtc a,
        stg.JulyPolicyState     b
Where   a.PolicyCode = b.PolicyCode
and     a.PolicyTypeGroup = 'Motor'
and     a.EffectiveDate = '2026-07-31'
and     a.ShortDescription like '%NCT%'
Group by a.PolicyCode
;


# Motor Doc Request

# In[ ]:

--D1.F1
-- mirrored from HD1.F1. Straight product swap of the ods.EventStream PolicyTypeGroup filter to Motor, keeping the literal 2026-07-01 to 2026-08-10 window and the donor's three product IN list in the inner query, and noting that stg.DocRequestClientCodes is read by nine queries but is no longer built anywhere in the notebook.
-- Fabric volume for this step: 245

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
    'Motor',
    date_trunc('MINUTE', min(a.conversationStartTime)),
    cast(min(a.conversationStartTime) as date),
    'D1.F1',
    'Motor Doc Request - Call wait time, or fails to make contact',
    'Call'
from    stg.A0_genesys_derived_data                     a,
        (SELECT  distinct ConversationId, d.PolicyTypeGroup
        FROM    stg.DocRequestClientCodes                a,
                ods.EventStream                          d
        Where   a.clientCode = left(d.SourcePolicyReference,6)
        and     d.EventSourceId = 3
        and     d.PolicyTypeGroup in ( 'Home', 'Van', 'Motor')
        and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000') b
Where   a.ConversationId = b.ConversationId
and     abandoned = 1
and     b.PolicyTypeGroup = 'Motor'
Group by a.ConversationId
;


# Motor MTA

# In[ ]:

--M3
-- mirrored from HM3. Straight swap of the PolicyTypeGroup literal on the stg.JJulyMTAs to stg.JulyPolicyState join, with the timestamp still taken from ReportingSaleDate because stg.JJulyMTAs only carries the integer posting date.
-- Fabric volume for this step: 5271

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
    'Motor',
    date_trunc('MINUTE', min(b.ReportingSaleDate)),
    cast(min(b.ReportingSaleDate) as date),
    'M3',
    'Motor MTA - Customer accepts',
    'Policy'
from    stg.JJulyMTAs a, stg.JulyPolicyState b
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Motor'
and     PolicyStatusDesc not in (
    'Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer'
)
Group by a.PolicyCode
;

# In[ ]:

--M4
-- mirrored from HM4. Straight swap of the PolicyTypeGroup literal to Motor, keeping the donor's CCYGrossPremium and CCYFees test and the ReportingSaleDate timestamp, both of which the same shared tables carry for Motor.
-- Fabric volume for this step: 892

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
    'Motor',
    date_trunc('MINUTE', min(b.ReportingSaleDate)),
    cast(min(b.ReportingSaleDate) as date),
    'M4',
    'Motor MTA - Money due on the change',
    'Policy'
from    stg.JJulyMTAs a, stg.JulyPolicyState b
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Motor'
and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
and     (
            CCYGrossPremium <> 0
        or
            CCYFees <> 0 )
Group by b.PolicyCode
;

# In[ ]:

--M6
-- mirrored from HM6. Straight swap of the PolicyTypeGroup literal to Motor in the stg.JJulyMTAs subquery, keeping the buildconfig window, the EventSourceId 3 document filters and the max EventDateTime for the last reissue.
-- Fabric volume for this step: 4006

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
    SourcePolicyReference,
    1,
    'Motor',
    date_trunc('MINUTE', max(EventDateTime)),
    cast(max(EventDateTime) as date),
    'M6',
    'Motor MTA - Cert and disc sent',
    'Policy'
from    ods.EventStream
Where   SourcePolicyReference in
        (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Motor'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
        )
and     EventDate >= (select startTime from stg.episodeeventstream_buildconfig) and EventDate < (select endTime   from stg.episodeeventstream_buildconfig)
and     EventSourceId = 3
and     (   EventDescription like '%Emailed Document%'
        or
            EventDescription like '%Document Transmitted%'
        )
Group by SourcePolicyReference
;


# Motor Renewal

# In[ ]:

--R1.E1
-- mirrored from HR1.E1. Straight swap of the renewals table to stg.R0_MotorPoliciesEligibleForRenewals, which only needs PolicyCode, with the campaign filter moved to Motor and the literal window of 2026-06-01 to 2026-09-01 kept exactly as the donor has it.
-- Fabric volume for this step: 12493

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
    'Motor',
    date_trunc('MINUTE', min(a.`timestamp`)),
    cast(min(a.`timestamp`) as date),
    'R1.E1',
    'Motor Renewal - Renewal campaigns: CRM',
    'Policy'
from    dlk.EXT_XtremePushResults_Policy   a,
        stg.R0_MotorPoliciesEligibleForRenewals b
where   a.`timestamp` between '2026-06-01 00:00:00.000' and '2026-09-01 00:00:00.000'
and     a.PolicyCode = b.PolicyCode
and     a.campaign_name like '%Motor%'
and     a.campaign_name like '%Renewals%'
and     a.MessageType in ( 'EMAIL', 'SMS')
and     a.interaction_type = 'sent'
Group by a.PolicyCode
;

# In[ ]:

--R4.B2.4
-- mirrored from VR4.B2.4. The chase snapshot table is shared between Motor and Van so only the PolicyTypeGroup filter and the product literal change, and the chase window of 2026-05-01 to 2026-07-31 is kept exactly as written.
-- Fabric volume for this step: 9662

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
    x.PolicyCode,
    1,
    'Motor',
    date_trunc('MINUTE', min(x.FirstDate)),
    cast(min(x.FirstDate) as date),
    'R4.B2.4',
    'Motor Renewal - Chase, first reminder',
    'Policy'
from    (
        select  PolicyCode , min(CreateDate) FirstDate
        from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
        Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-05-01' and '2026-07-31'
        and PolicyType = 'Renewals'
        and PolicyTypeGroup = 'Motor'
        and case
                when Sign_Prop_Status               = 'O' then 1
                when Sign_Stat_Of_Fact_Status       = 'O' then 1
                when Comp_Fin_Agree_Status          = 'O' then 1
                when Comp_DDM_Status                = 'O' then 1
                when Proof_Of_NCB_Status            = 'O' then 1
                when Trans_Proof_Of_NCB_Status      = 'O' then 1
                when Ltr_Of_Driv_Exp_Status         = 'O' then 1
                when Prop_Driv_Lic_Status           = 'O' then 1
                when Nam_Driv_Lic_Status            = 'O' then 1
                when Gap_In_Cov_Ltr_Status          = 'O' then 1
                when `2ndCar_Cert_Status`           = 'O' then 1
                when Doc_Ltr_Status                 = 'O' then 1
                when Engineers_Rpt_Status           = 'O' then 1
                when NCT_Status                     = 'O' then 1
                when Veh_Lic_Cert_Status            = 'O' then 1
                when Irish_Reg_Status               = 'O' then 1
                when Main_Driver_Dec_Status         = 'O' then 1
                when Soc_Dom_Pleas_Dec_Status       = 'O' then 1
                when Comp_Car_Exper_Status          = 'O' then 1
                when DD_Conf_Ltr_Status             = 'O' then 1
                when Comp_Fin_Mand_Status           = 'O' then 1
                when Val_For_Spec_Item_Status       = 'O' then 1
                when Dri_Lic_Num_Status             = 'O' then 1
                when Comp_Lost_Cert_Dec_Status      = 'O' then 1
                when Orig_Cert_Status               = 'O' then 1
                when Cancel_Req_Status              = 'O' then 1
                when PPS_Num_Status                 = 'O' then 1
                when Afford_State_Status            = 'O' then 1
                when Identification_Status          = 'O' then 1
                when Digital_Journey_Status         = 'O' then 1
                when Finance_Form_Status            = 'O' then 1
                else 0
            End = 1
        Group by PolicyCode
        ) x
Group by x.PolicyCode
;

# In[ ]:

--R4.B2.F1
-- mirrored from VR4.B2.F1. The chase snapshot table is shared between Motor and Van so only the PolicyTypeGroup filter and the product literal change, and the chase window of 2026-05-01 to 2026-07-31 is kept exactly as written.
-- Fabric volume for this step: 9662

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
    'Motor',
    date_trunc('MINUTE', max(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
    cast(max(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01')) as date),
    'R4.B2.F1',
    'Motor Renewal - Chases before the customer submits, and documents never submitted',
    'Policy'
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-05-01' and '2026-07-31'
and PolicyType = 'Renewals'
and PolicyTypeGroup = 'Motor'
and case
        when Sign_Prop_Status               = 'O' then 1
        when Sign_Stat_Of_Fact_Status       = 'O' then 1
        when Comp_Fin_Agree_Status          = 'O' then 1
        when Comp_DDM_Status                = 'O' then 1
        when Proof_Of_NCB_Status            = 'O' then 1
        when Trans_Proof_Of_NCB_Status      = 'O' then 1
        when Ltr_Of_Driv_Exp_Status         = 'O' then 1
        when Prop_Driv_Lic_Status           = 'O' then 1
        when Nam_Driv_Lic_Status            = 'O' then 1
        when Gap_In_Cov_Ltr_Status          = 'O' then 1
        when `2ndCar_Cert_Status`           = 'O' then 1
        when Doc_Ltr_Status                 = 'O' then 1
        when Engineers_Rpt_Status           = 'O' then 1
        when NCT_Status                     = 'O' then 1
        when Veh_Lic_Cert_Status            = 'O' then 1
        when Irish_Reg_Status               = 'O' then 1
        when Main_Driver_Dec_Status         = 'O' then 1
        when Soc_Dom_Pleas_Dec_Status       = 'O' then 1
        when Comp_Car_Exper_Status          = 'O' then 1
        when DD_Conf_Ltr_Status             = 'O' then 1
        when Comp_Fin_Mand_Status           = 'O' then 1
        when Val_For_Spec_Item_Status       = 'O' then 1
        when Dri_Lic_Num_Status             = 'O' then 1
        when Comp_Lost_Cert_Dec_Status      = 'O' then 1
        when Orig_Cert_Status               = 'O' then 1
        when Cancel_Req_Status              = 'O' then 1
        when PPS_Num_Status                 = 'O' then 1
        when Afford_State_Status            = 'O' then 1
        when Identification_Status          = 'O' then 1
        when Digital_Journey_Status         = 'O' then 1
        when Finance_Form_Status            = 'O' then 1
        else 0
    End = 1
Group by a.PolicyCode
;

# In[ ]:

--R6.F1
-- mirrored from HR6.F1. Straight swap of the renewals table and the two product literals, since the donor only needs PolicyCode and TyPolicyCode, and the literal window of 2026-06-01 to 2026-08-01 is kept exactly as the donor has it.
-- Fabric volume for this step: 118

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
    'Motor',
    date_trunc('MINUTE', min(d.EventDateTime)),
    cast(min(d.EventDateTime) as date),
    'R6.F1',
    'Motor Renewal - Non-arrival, and time taken to receive',
    'Policy'
FROM    stg.R0_MotorPoliciesEligibleForRenewals  a,
        ods.EventStream                          d
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Motor'
and     d.EventDateTime between '2026-06-01 00:00:00.000' and '2026-08-01 00:00:00.000'
and     d.EventDescription like '%Suitability%'
and     d.EventDescription not like 'Renewal Offer - %'
AND     (
            d.EventDescription like '%Emailed Document%'
        OR
            d.EventDescription like '%Document Transmitted%'
        )
Group by a.PolicyCode
;


# Van Acquisition

# In[ ]:

--VA6
-- mirrored from A6. the Motor donor already reads the shared MotorVan chase snapshot so only PolicyTypeGroup moves to Van, and the 2ndCar_Cert_Status column is quoted with backticks the way the other Van query on that table writes it.
-- Fabric volume for this step: 534

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
        'Van',
        max(date_trunc('MINUTE', coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
        max(cast(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') as date)),
        'VA6',
        'Van Acquisition - Documents requested',
        'Policy'
FROM    edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between (select startTime from stg.episodeeventstream_buildconfig) and (select endTime   from stg.episodeeventstream_buildconfig) and PolicyType = 'New Business' and PolicyTypeGroup = 'Van' and
case
	when Sign_Prop_Status				= 'O' then 1
	when Sign_Stat_Of_Fact_Status		= 'O' then 1
	when Comp_Fin_Agree_Status			= 'O' then 1
	when Comp_DDM_Status				= 'O' then 1
	when Proof_Of_NCB_Status			= 'O' then 1
	when Trans_Proof_Of_NCB_Status		= 'O' then 1
	when Ltr_Of_Driv_Exp_Status			= 'O' then 1
	when Prop_Driv_Lic_Status			= 'O' then 1
	when Nam_Driv_Lic_Status			= 'O' then 1
	when Gap_In_Cov_Ltr_Status			= 'O' then 1
	when `2ndCar_Cert_Status`			= 'O' then 1
	when Doc_Ltr_Status					= 'O' then 1
	when Engineers_Rpt_Status			= 'O' then 1
	when NCT_Status						= 'O' then 1
	when Veh_Lic_Cert_Status			= 'O' then 1
	when Irish_Reg_Status				= 'O' then 1
	when Main_Driver_Dec_Status			= 'O' then 1
	when Soc_Dom_Pleas_Dec_Status		= 'O' then 1
	when Comp_Car_Exper_Status			= 'O' then 1
	when DD_Conf_Ltr_Status				= 'O' then 1
	when Comp_Fin_Mand_Status			= 'O' then 1
	when Val_For_Spec_Item_Status		= 'O' then 1
	when Dri_Lic_Num_Status				= 'O' then 1
	when Comp_Lost_Cert_Dec_Status		= 'O' then 1
	when Orig_Cert_Status				= 'O' then 1
	when Cancel_Req_Status				= 'O' then 1
	when PPS_Num_Status					= 'O' then 1
	when Afford_State_Status			= 'O' then 1
	when Identification_Status			= 'O' then 1
	when Digital_Journey_Status			= 'O' then 1
	when Finance_Form_Status			= 'O' then 1
	else 0
End = 1 
and Campaign = 'DAY 1'
Group by a.PolicyCode
;

# In[ ]:

--VA6.B1.2
-- mirrored from HA6.B1.2. the policies sold table becomes stg.VanSales and the donor's PolicyTypeGroup filter is dropped because stg.VanSales is already restricted to Van and does not project that column.
-- Fabric volume for this step: 266

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
        date_trunc('MINUTE', min(`Timestamp`)),
        cast(min(`Timestamp`) as date),
        'VA6.B1.2',
        'Van Acquisition - Customer submits documents',
        'Policy'
from    stg.VanSales                            a,
        dlk.MyChill_NewUploadDocumentEvents     b
Where   a.PolicyCode = b.PolicyCode
and     a.ReportingSaleType = 'New Business'
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
Group by b.PolicyCode
;

# In[ ]:

--VA6.B1.4
-- mirrored from HA6.B1.4. straight swap of the chase snapshot to edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan with PolicyTypeGroup Van added, keeping the donor's subquery, its six document status columns and the DAY 1 campaign filter.
-- Fabric volume for this step: 474

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
        x.PolicyCode,
        1,
        'Van',
        date_trunc('MINUTE', max(x.SaleDateTime)),
        cast(max(x.SaleDateTime) as date),
        'VA6.B1.4',
        'Van Acquisition - Chase, first reminder',
        'Policy'
From    (
            select  PolicyCode,
                    max(coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01')) SaleDateTime
            from    edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan   a
            Where   coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
            and     a.PolicyType = 'New Business'
            and     a.PolicyTypeGroup = 'Van'
            and     case
                when Gap_In_Cov_Ltr_Status = 'O' then 1
                when Val_For_Spec_Item_Status = 'O' then 1
                when PPS_Num_Status = 'O' then 1
                When Identification_Status = 'O' then 1
                when Finance_Form_Status = 'O' then 1
                when Digital_Journey_Status = 'O' then 1
                else 0
            End = 1
            and     a.campaign = 'DAY 1'
            Group by PolicyCode
        )   x
Group by x.PolicyCode
;

# In[ ]:

--VA7
-- mirrored from A7. the Motor donor is used rather than the Home one because the target step is the certificate and disc dispatch, so the policies sold table becomes stg.VanSales and ods.EventStream is read at PolicyTypeGroup Van with the donor's certificate description list unchanged.
-- Fabric volume for this step: 421

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
SELECT  a.PolicyCode,
        1,
        'Van',
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDate as date)),
        'VA7',
        'Van Acquisition - Cert and disc sent',
        'Policy'
FROM    stg.VanSales                             a,
        ods.EventStream                          d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Van'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     ReportingSaleType = 'New Business'
and     EventDescription in
            (
                'New Business - Document Transmission Confirmed - Certificate',
                'New Business - Document Posted Confirmation - Certificate',
                'New Business - Document Transmitted - Certificate'
            )

Group by a.PolicyCode
;


# Van Doc Request

# In[ ]:

--VD1.F1
-- mirrored from HD1.F1. Straight product swap of the ods.EventStream PolicyTypeGroup filter to Van, keeping the literal 2026-07-01 to 2026-08-10 window exactly as the donor has it, and noting that stg.DocRequestClientCodes is referenced by nine queries but has no build left in the notebook.
-- Fabric volume for this step: 46

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
    'Van',
    date_trunc('MINUTE', min(a.conversationStartTime)),
    cast(min(a.conversationStartTime) as date),
    'VD1.F1',
    'Van Doc Request - Call wait time, or fails to make contact',
    'Call'
from    stg.A0_genesys_derived_data                     a,
        (SELECT  distinct ConversationId, d.PolicyTypeGroup
        FROM    stg.DocRequestClientCodes                a,
                ods.EventStream                          d
        Where   a.clientCode = left(d.SourcePolicyReference,6)
        and     d.EventSourceId = 3
        and     d.PolicyTypeGroup in ( 'Home', 'Van', 'Motor')
        and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000') b
Where   a.ConversationId = b.ConversationId
and     abandoned = 1
and     b.PolicyTypeGroup = 'Van'
Group by a.ConversationId
;

# In[ ]:

--VD3.F1
-- mirrored from HD3.F1. Straight product swap of the outer PolicyTypeGroup filter to Van, keeping the customer client code grain, the calleddates greater than one test and the literal 2026-07-01 to 2026-08-10 window, and noting that stg.DocRequestClientCodes is no longer built anywhere in the notebook.
-- Fabric volume for this step: 29

insert INTO
ods.EpisodeEventStream
(
    SourceCustomerReference,
    SourceSystemId,
    PolicyTypeGroup,
    EventDateTime,
    EventDate,
    EventTypeId,
    EventDescription,
    Grain
)
SELECT
    x.clientCode,
    1,
    'Van',
    date_trunc('MINUTE', max(x.LastCallTime)),
    cast(max(x.LastCallTime) as date),
    'VD3.F1',
    'Van Doc Request - Non-arrival, and the customer rings again',
    'Customer'
from    (
            SELECT  d.PolicyTypeGroup, a.clientCode, count(distinct cast(ConversationStartTime as date)) calleddates, max(ConversationStartTime) LastCallTime
            FROM    stg.DocRequestClientCodes                a,
                    ods.EventStream                          d
            Where   a.clientCode = left(d.SourcePolicyReference,6)
            and     d.EventSourceId = 3
            and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000'
            Group by d.PolicyTypeGroup, a.clientCode
        ) x
Where   x.calleddates > 1
and     x.PolicyTypeGroup = 'Van'
Group by x.clientCode
;


# Van Renewal

# In[ ]:

--VR3.B1.O3
-- mirrored from HR3.B1.O3. The Home donor was used because it only needs PolicyCode and TYReportingSaleDate, both of which the Van renewals table carries, the campaign filter moves to the Van lapse campaign and the literal window of 2026-06-01 to 2026-09-01 is kept exactly as written.
-- Fabric volume for this step: 161

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
    'Van',
    date_trunc('MINUTE', max(a.`timestamp`)),
    cast(max(a.`timestamp`) as date),
    'VR3.B1.O3',
    'Van Renewal - Lost',
    'Policy'
from    dlk.EXT_XtremePushResults  a,
        stg.VanRenewalsJuly b
where   a.`timestamp` between '2026-06-01 00:00:00.000' and '2026-09-01 00:00:00.000'
and     a.PolicyCode = b.PolicyCode
and     a.campaign_name like '%Van%'
and     a.campaign_name like '%Lapsed%'
and     a.MessageType in ( 'EMAIL', 'SMS')
and     a.interaction_type = 'sent'
and     b.TYReportingSaleDate is null
Group by a.PolicyCode
;

# In[ ]:

--VR4
-- mirrored from HR4. Straight swap of the renewals table to stg.VanRenewalsJuly and of the product literal, since TyPolicyCode, TYReportingSaleDate and PolicyRetNum are all carried by the Van renewals table.
-- Fabric volume for this step: 590

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
    a.TyPolicyCode,
    1,
    'Van',
    date_trunc('MINUTE', max(a.TYReportingSaleDate)),
    cast(max(a.TYReportingSaleDate) as date),
    'VR4',
    'Van Renewal - Payment taken',
    'Policy'
from    stg.VanRenewalsJuly a
Where   a.PolicyRetNum = 1
Group by a.TyPolicyCode
;

# In[ ]:

--VR4.B2.5
-- mirrored from HR4.B2.5. Straight swap of the renewals table to stg.VanRenewalsJuly and of the product literal, with the donor's literal window of 2026-06-01 to 2026-09-01 and its lack of a PolicyTypeGroup filter on ods.EventStream both kept as they are.
-- Fabric volume for this step: 583

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
    'Van',
    date_trunc('MINUTE', max(d.EventDateTime)),
    cast(max(d.EventDateTime) as date),
    'VR4.B2.5',
    'Van Renewal - Chase, escalation',
    'Policy'
FROM    stg.VanRenewalsJuly                         a,
        ods.EventStream                             d
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.EventDateTime > '2026-06-01 00:00:00.000'
and     d.EventDateTime < '2026-09-01 00:00:00.000'
and     d.EventDescription like '%Chase%'
and     d.EventDescription like '%Final%'
Group by a.PolicyCode
;

# In[ ]:

--VR4.B2.6
-- mirrored from R4.B2.6. Straight swap of the renewals table to stg.VanRenewalsJuly and of the product literal, with the build config run window and the extra cut off at 2026-09-01 both kept exactly as the donor has them.
-- Fabric volume for this step: 5

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
SELECT  a.PolicyCode,
        1,
        'Van',
        max(date_trunc('MINUTE', `Timestamp`)),
        max(cast(`Timestamp` as date)),
        'VR4.B2.6',
        'Van Renewal - Documents received and validated',
        'Policy'
from    stg.VanRenewalsJuly a, dlk.MyChillWorkflow_DocumentStatus  b
Where   a.TyPolicyCode = b.PolicyCode
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
and     `Timestamp` < '2026-09-01 00:00:00.000'
and     isAccepted = 'true'
Group by a.PolicyCode
;


# Not mirrored

# In[ ]:

-- These steps had an equivalent in another product, but it could not be swapped across.

-- HA4.F1       Home Acquisition, donor A4.F1: the donor identifies the web assist customer by a.QuoteQueryGuid being not null and writes that MFQ quote guid as the SourceQuoteReference, and Home quotes are raised on HFQ so there is no MFQ guid to key the step on.
-- HA7.B1.1     Home Acquisition, donor A7.B1.1: both donors filter ods.EventStream on a motor certificate or disc dispatch description, namely 'New Business - Document Transmitted - Certificate' and 'New Business - Printed Document - CD Issue Letter CV', and a home policy issues no certificate or disc so the logic has no meaning for Home.
-- HM1          Home MTA, donor M1: The donor keys on the vehicle only Genesys queue names INBOUND_VehicleChange and friends and splits Motor from Van using stg.VM0_van_phone_numbers, and neither the queue list nor a phone number table has any Home counterpart.
-- HM1.F1       Home MTA, donor M1.F1: The donor builds stg.AbandonedMTACalls from the same vehicle only Genesys queue names and then excludes the Van phone numbers in stg.VM0_van_phone_numbers, so there is no Home equivalent to key on.
-- HR3b.F1      Home Renewal, donor R3b.F1: The donor reads stg.R3bF1_genesys_inbound_call_duration_summary and stg.R0_genesys_derived_data, and neither table has a Home counterpart in the notebook or in the source table map.
-- HR4.B2.4     Home Renewal, donor VR4.B2.4: The donor takes the first reminder from min of CreateDate on the chase snapshot and no Home query in the notebook ever reads CreateDate from edw.exp_mychill_chase_daily_snapshot_home, so the column cannot be assumed to exist.
-- R3.O1        Motor Renewal, donor VR3.O1: The Van donor keys on PolicyRetNum, PolicyOfferNum and LYPolicyRenewDateAdj, none of which stg.R0_MotorPoliciesEligibleForRenewals carries, and the Home donor reads stg.HR3B1_LapsedThisYearPolicy, which has no Motor counterpart.
-- R4           Motor Renewal, donor HR4: The donor keys on TYReportingSaleDate and PolicyRetNum, and stg.R0_MotorPoliciesEligibleForRenewals projects neither of them.
-- R6.B1.1      Motor Renewal, donor VR6.B1.1: The donor filters on PolicyRetNum from the Van renewals table and stg.R0_MotorPoliciesEligibleForRenewals does not carry that column.
-- TR1.E1       Travel Renewal, donor HR1.E1: Both donors join XtremePush to a policies eligible for renewal staging table and Travel has no such table, only quote and policy feeds, so there is nothing to join the campaign sends to.
-- TR4          Travel Renewal, donor HR4: The donor reads a policies eligible for renewal table for TyPolicyCode, TYReportingSaleDate and PolicyRetNum, and Travel has no renewals table carrying any of those.
-- VR2          Van Renewal, donor HR2: Both donors build the lookback window from RenewalDate and the Van renewals table does not carry a RenewalDate column.
-- VR3.B1.O1    Van Renewal, donor HR3.B1.O1: Both donors compare the sale date against RenewalDate and the Van renewals table does not carry a RenewalDate column.
-- VR3b.F1      Van Renewal, donor R3b.F1: The donor joins stg.R3bF1_genesys_inbound_call_duration_summary to stg.R0_genesys_derived_data, the Motor renewals Genesys pair, and Van has no renewals equivalent because its only Genesys tables cover the INBOUND_SALES_VAN acquisition queue.

