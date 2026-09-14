#!/usr/bin/env python
# coding: utf-8

# ## Extracted from "XX - Episode Reconciliation - Gaps.html"
#
# All 108 code cells from the notebook export, in original order, with the
# step ids parsed out of each cell header.
#
# READ THIS FIRST: none of these cells is an insert. The export contains no
# "insert into" and no reference to ods.EpisodeEventStream anywhere. The cells
# are count queries, staging table builds and investigation notes. They are the
# raw material for inserts, not the inserts themselves. Nothing here has been
# added to "03 - Populate Episode Event Stream.py".
#
# Cell kinds: 67 count queries, 8 staging table builds, 33 other (notes and
# plain selects). 79 distinct step ids are referenced.


# In[ ]:

-- HTML cell 0   kind: count query
-- step ids: none in header
-- header: Motor	Renewal	RO.F2

 select  count(distinct a.PolicyCode) 
 from   (   select  PolicyCode 
            from	stg.motorclaims
            Where	ClaimDate between 20250801 and 20260731
            and	    OwnFaultFlag = 'Y' 
            )                                       a, 
        stg.R0_MotorPoliciesEligibleForRenewals     b 
 Where  a.PolicyCode = b.PolicyCode


# In[ ]:

-- HTML cell 1   kind: count query
-- step ids: R1.E1.F3
-- header: Motor	Renewal	R1.E1.F3

  -- get Renewal emails from XP table
select count(distinct PolicyCode) 
from  
    (
        select  distinct b.PolicyCode
        from    dlk.EXT_XtremePushResults a, stg.R0_MotorPoliciesEligibleForRenewals b 
        where   campaign_name like '%Motor%' 
        and     campaign_name like '%TYR%' 
        and     a.PolicyCode = b.PolicyCode 
        and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
        and     interaction_type = 'sent' 
        and     MessageType  in ( 'EMAIL', 'SMS')
        union
        select  distinct b.PolicyCode 
        from    dlk.EXT_XtremePushResults_Policy a, stg.R0_MotorPoliciesEligibleForRenewals b 
        where   campaign_name like '%Motor%' 
        and     campaign_name like '%TYR%' 
        and     a.PolicyCode = b.PolicyCode 
        and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
        and     interaction_type = 'sent' 
        and     MessageType  in ( 'EMAIL', 'SMS')
    ) x


# In[ ]:

-- HTML cell 2   kind: count query
-- step ids: R3.B1.2
-- header: Motor	Renewal	R3.B1.2

  -- get Renewal emails from XP table
select count(distinct PolicyCode) 
from  
    (
        select  distinct b.PolicyCode
        from    dlk.EXT_XtremePushResults a, stg.R0_MotorPoliciesEligibleForRenewals b 
        where   campaign_name like '%Motor%' 
        and     campaign_name like '%Lapsed%' 
        and     a.PolicyCode = b.PolicyCode 
        and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
        and     interaction_type = 'sent' 
        and     MessageType  in ( 'EMAIL', 'SMS')
        union
        select  distinct b.PolicyCode 
        from    dlk.EXT_XtremePushResults_Policy a, stg.R0_MotorPoliciesEligibleForRenewals b 
        where   campaign_name like '%Motor%' 
        and     campaign_name like '%Lapsed%' 
        and     a.PolicyCode = b.PolicyCode 
        and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
        and     interaction_type = 'sent' 
        and     MessageType  in ( 'EMAIL', 'SMS')
    ) x


# In[ ]:

-- HTML cell 3   kind: count query
-- step ids: R3.B1.2.F1
-- header: Motor	Renewal	R3.B1.2.F1


select  count(distinct a.PolicyCode)
from    dlk.EXT_XtremePushResults_Policy a, stg.R0_MotorPoliciesEligibleForRenewals b 
where   campaign_name like '%Motor%' 
and     campaign_name like '%Lapsed%' 
and     a.PolicyCode = b.PolicyCode 
and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
and     interaction_type = 'sent' 
and     MessageType  in ( 'EMAIL', 'SMS')
and     a.PolicyCode not in 
        (
            select  distinct a.PolicyCode
            from    dlk.EXT_XtremePushResults_Policy a, stg.R0_MotorPoliciesEligibleForRenewals b 
            where   campaign_name like '%Motor%' 
            and     campaign_name like '%Lapsed%' 
            and     a.PolicyCode = b.PolicyCode 
            and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
            and     interaction_type in ('open','click')
            and     MessageType  in ( 'EMAIL', 'SMS')
        )


# In[ ]:

-- HTML cell 4   kind: count query
-- step ids: R3.B1.2.F1
-- header: Motor	Renewal	R3.B1.2.F1


select  count(distinct a.PolicyCode)
from    dlk.EXT_XtremePushResults_Policy a, stg.R0_MotorPoliciesEligibleForRenewals b 
where   campaign_name like '%Motor%' 
and     campaign_name like '%Lapsed%' 
and     a.PolicyCode = b.PolicyCode 
and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
and     interaction_type = 'sent' 
and     MessageType  in ( 'EMAIL', 'SMS')
and     a.PolicyCode not in 
        (
            select  distinct a.PolicyCode
            from    dlk.EXT_XtremePushResults_Policy a, stg.R0_MotorPoliciesEligibleForRenewals b 
            where   campaign_name like '%Motor%' 
            and     campaign_name like '%Lapsed%' 
            and     a.PolicyCode = b.PolicyCode 
            and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
            and     interaction_type in ('open','click')
            and     MessageType  in ( 'EMAIL', 'SMS')
        )
and     a.PolicyCode in 
        (
            select  distinct a.PolicyCode
            from    dlk.EXT_XtremePushResults_Policy a, stg.R0_MotorPoliciesEligibleForRenewals b 
            where   campaign_name like '%Motor%' 
            and     campaign_name like '%Lapsed%' 
            and     a.PolicyCode = b.PolicyCode 
            and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
            and     interaction_type in ('bounce')
            and     MessageType  in ( 'EMAIL', 'SMS')
        )


# In[ ]:

-- HTML cell 5   kind: count query
-- step ids: R3.B1.1
-- header: Motor	Renewal	R3.B1.1

select	count(distinct PolicyCode) 
from	stg.r0_motorpolicieseligibleforrenewals
Where	(	
			TYReportingSaleDate > RenewalDate 
		or 
			TYReportingSaleDate is null 
			) 
and     PolicyOfferNum > 0


# In[ ]:

-- HTML cell 6   kind: count query
-- step ids: R3.B1.3
-- header: Motor	Renewal	R3.B1.3

select	count(distinct PolicyCode) 
from	stg.r0_motorpolicieseligibleforrenewals
Where	(	
			TYReportingSaleDate >= dateadd(day,7,RenewalDate)
		or 
			TYReportingSaleDate is null 
			) 
and     PolicyOfferNum > 0


# In[ ]:

-- HTML cell 7   kind: count query
-- step ids: R3.B1.4
-- header: Motor	Renewal	R3.B1.4

select	count(distinct PolicyCode) 
from	stg.r0_motorpolicieseligibleforrenewals
Where	(	
			TYReportingSaleDate >= dateadd(day,30,RenewalDate)
		or 
			TYReportingSaleDate is null 
			) 
and     PolicyOfferNum > 0


# In[ ]:

-- HTML cell 8   kind: count query
-- step ids: R3.B1.O1
-- header: Motor	Renewal	R3.B1.O1

select	count(distinct PolicyCode) 
from	stg.r0_motorpolicieseligibleforrenewals
Where	(	
			TYReportingSaleDate > RenewalDate
			) 
and     PolicyOfferNum > 0


# In[ ]:

-- HTML cell 9   kind: count query
-- step ids: R3.B1.O3
-- header: Motor	Renewal	R3.B1.O3

select	count(distinct PolicyCode) 
from	stg.r0_motorpolicieseligibleforrenewals
Where	(	
			TYReportingSaleDate is null 
			) 
and     PolicyOfferNum > 0


# In[ ]:

-- HTML cell 10   kind: note or select
-- step ids: R6.F1
-- header: Motor	Renewal	R6.F1

-- Choose the code for duplicate certificates Motor	Renewal	R6.B1.5


# In[ ]:

-- HTML cell 11   kind: count query
-- step ids: HR0
-- header: Home	Renewal	HR0

select count(distinct PolicyCode) from stg.R0_HomePoliciesEligibleForRenewals


# In[ ]:

-- HTML cell 12   kind: note or select
-- step ids: none in header
-- header: worthwhile to know

select	EventType, count(*), count(distinct PolicyCode)
from	dlk.ext_home_qs_policydetails 
Where	TransactionDate between '2026-07-01 11:01:06.000' and '2026-08-01 01:01:06.000'
Group by EventType

/* Even though not sure if this is used in SQL 09 reports */


# In[ ]:

-- HTML cell 13   kind: note or select
-- step ids: HR0.F1
-- header: Home	Renewal	HR0.F1

select	EventType, count(distinct b.PolicyCode)
from	dlk.EXT_Home_QS_ClaimDetails    a, 
        dlk.ext_home_qs_policydetails   b,
        stg.R0_HomePoliciesEligibleForRenewals c 
Where	a.HomeRiskId = upper(b.RiskId)
and		TransactionDate between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000'
and		b.PolicyCode = c.PolicyCode 
-- and     EventType = 'Quotation Provided' 
Group by EventType 
-- use only Quotation Provided for this count -- 681 -- the unique policycodes involved are 681 too


# In[ ]:

-- HTML cell 14   kind: count query
-- step ids: HR2.F1
-- header: Home	Renewal	HR2.F1

select  count(distinct ConversationId) callcount, count(distinct ani) PhoneNumber
from    dlk.genesys_session_summary 
Where   wrapupCode <> 'ININ-WRAP-UP-TIMEOUT'
and     ConversationStartTime between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000'
and     QueueName = 'INBOUND_Home_Renewals'
and     OriginatingDirection = 'inbound'
and     wrapupCodeName in 
                (
                    'UNFAVOURABLE_NCD',
                    'REQUOTED_NOT_SOLD',
                    'UNDECIDED/SHOPPING AROUND',
                    'UNFAVOURABLE_COMPETITOR'
                    )
-- Group by QueueName, wrapupCodeName


# In[ ]:

-- HTML cell 15   kind: count query
-- step ids: HR1.E1
-- header: Home	Renewal	HR1.E1

select	count(distinct a.PolicyCode)
from	dlk.EXT_XtremePushResults_Policy   a, stg.R0_HomePoliciesEligibleForRenewals b 
where	`timestamp` between '2026-06-01 00:00:00.000' and '2026-09-01 00:00:00.000' 
and     a.PolicyCode = b.PolicyCode 
and		campaign_name like '%Home%' 
and		campaign_name like '%Renewals%' 
and     MessageType in ( 'EMAIL', 'SMS')
and     interaction_type = 'sent' 
limit 100


# In[ ]:

-- HTML cell 16   kind: count query
-- step ids: HR1.E1.F1
-- header: Home	Renewal	HR1.E1.F1

select	count(distinct a.PolicyCode)
from	dlk.EXT_XtremePushResults_Policy   a, stg.R0_HomePoliciesEligibleForRenewals b 
where	`timestamp` between '2026-06-01 00:00:00.000' and '2026-09-01 00:00:00.000' 
and     a.PolicyCode = b.PolicyCode 
and		campaign_name like '%Home%' 
and		campaign_name like '%Renewals%' 
and     MessageType in ( 'EMAIL', 'SMS')
and     interaction_type = 'sent' 
and     coalesce(b.TYReportingSaleDate, b.RenewalDate) > b.RenewalDate


# In[ ]:

-- HTML cell 17   kind: count query
-- step ids: HR3.B1
-- header: Home	Renewal	HR3.B1

select	count(distinct a.PolicyCode)
from	dlk.EXT_XtremePushResults    a, stg.R0_HomePoliciesEligibleForRenewals b 
where	`timestamp` between '2026-06-01 00:00:00.000' and '2026-09-01 00:00:00.000' 
and     a.PolicyCode = b.PolicyCode 
and		campaign_name like 'Home - This Year Lapsed%' 
and     MessageType in ( 'EMAIL', 'SMS')
and     interaction_type = 'sent'


# In[ ]:

-- HTML cell 18   kind: note or select
-- step ids: HR4.B2, HR4.B2.F1
-- header: docs asked for HR4.B2
-- header: Home	Renewal	HR4.B2.F1 --  day 1 should be the full chase and then day 7 / 14 / 20 should reduce as people submit docs and get them approved..
-- header: -- these voluems are messed up for some reason -- so redone below on the 08th

select  Campaign, count(distinct a.PolicyCode) 
from    edw.EXP_MyChill_Chase_Daily_Snapshot_Home a, stg.R0_HomePoliciesEligibleForRenewals b 
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-05-01' and '2026-07-31' 
and     PolicyType = 'Renewals' 
and     PolicyTypeGroup = 'Home' 
and     a.PolicyCode = b.PolicyCode 
and case 
        When Comp_DDM_Status				= 'O' then 1 
        When Gap_In_Cov_Ltr_Status			= 'O' then 1 
        When Val_For_Spec_Item_Status		= 'O' then 1 
        When PPS_Num_Status					= 'O' then 1 
        When Identification_Status			= 'O' then 1 
        When Digital_Journey_Status			= 'O' then 1 
        When Finance_Form_Status			= 'O' then 1 
        else 0
    End = 1 
--and Campaign = 'DAY 1'
Group by Campaign
Order by 1


# In[ ]:

-- HTML cell 19   kind: count query
-- step ids: VA6.B1.F1, VA6.B1.5
-- header: docs asked for VA6.B1.F1 VA6.B1.5

select  count(distinct a.PolicyCode) 
from    edw.EXP_MyChill_Chase_Daily_Snapshot_Home a, stg.R0_HomePoliciesEligibleForRenewals b 
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-05-01' and '2026-07-31' 
and     PolicyType = 'Renewals' 
and     PolicyTypeGroup = 'Home' 
and     a.PolicyCode = b.PolicyCode 
and case 
        When Comp_DDM_Status				= 'O' then 1 
        When Gap_In_Cov_Ltr_Status			= 'O' then 1 
        When Val_For_Spec_Item_Status		= 'O' then 1 
        When PPS_Num_Status					= 'O' then 1 
        When Identification_Status			= 'O' then 1 
        When Digital_Journey_Status			= 'O' then 1 
        When Finance_Form_Status			= 'O' then 1 
        else 0
    End = 1 
and Campaign = 'DAY 20'


# In[ ]:

-- HTML cell 20   kind: count query
-- step ids: none in header
--- Starting from 2026/09/08 -- Vijay

/*
    Home	Renewal	HR3.B1.2
*/
select	count(distinct a.PolicyCode)
from	dlk.EXT_XtremePushResults  a, stg.R0_HomePoliciesEligibleForRenewals b 
where	`timestamp` between '2026-06-01 00:00:00.000' and '2026-09-01 00:00:00.000' 
and     a.PolicyCode = b.PolicyCode 
and		campaign_name like '%Home%' 
and		campaign_name like '%Lapsed%' 
and     MessageType in ( 'EMAIL', 'SMS')
and     interaction_type = 'sent' 
-- and     coalesce(b.TYReportingSaleDate, b.RenewalDate) > b.RenewalDate


# In[ ]:

-- HTML cell 21   kind: count query
-- step ids: R3.B1.2.F1
-- header: Motor	Renewal	R3.B1.2.F1


select  count(distinct a.PolicyCode)
from    dlk.EXT_XtremePushResults a, stg.R0_HomePoliciesEligibleForRenewals b 
where   campaign_name like '%Home%' 
and     campaign_name like '%Lapsed%' 
and     a.PolicyCode = b.PolicyCode 
and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
and     interaction_type = 'sent' 
and     MessageType  in ( 'EMAIL', 'SMS')
and     a.PolicyCode not in 
        (
            select  distinct a.PolicyCode
            from    dlk.EXT_XtremePushResults a, stg.R0_HomePoliciesEligibleForRenewals b 
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
            from    dlk.EXT_XtremePushResults a, stg.R0_HomePoliciesEligibleForRenewals b 
            where   campaign_name like '%Home%' 
            and     campaign_name like '%Lapsed%' 
            and     a.PolicyCode = b.PolicyCode 
            and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
            and     interaction_type in ('bounce')
            and     MessageType  in ( 'EMAIL', 'SMS')
        )


# In[ ]:

-- HTML cell 22   kind: count query
-- step ids: HR3.B1.O1
-- header: Home	Renewal	HR3.B1.O1

select	count(distinct a.PolicyCode)
from	dlk.EXT_XtremePushResults  a, stg.R0_HomePoliciesEligibleForRenewals b 
where	`timestamp` between '2026-06-01 00:00:00.000' and '2026-09-01 00:00:00.000' 
and     a.PolicyCode = b.PolicyCode 
and		campaign_name like '%Home%' 
and		campaign_name like '%Lapsed%' 
and     MessageType in ( 'EMAIL', 'SMS')
and     interaction_type = 'sent' 
and     coalesce(b.TYReportingSaleDate, b.RenewalDate) > b.RenewalDate /* renewed after lapsing but before the window closed */


# In[ ]:

-- HTML cell 23   kind: count query
-- step ids: HR3.B1.O3
-- header: Home	Renewal	HR3.B1.O3

select	count(distinct a.PolicyCode)
from	dlk.EXT_XtremePushResults  a, stg.R0_HomePoliciesEligibleForRenewals b 
where	`timestamp` between '2026-06-01 00:00:00.000' and '2026-09-01 00:00:00.000' 
and     a.PolicyCode = b.PolicyCode 
and		campaign_name like '%Home%' 
and		campaign_name like '%Lapsed%' 
and     MessageType in ( 'EMAIL', 'SMS')
and     interaction_type = 'sent' 
and     b.TYReportingSaleDate is null


# In[ ]:

-- HTML cell 24   kind: count query
-- step ids: HR4.B2, HR4.B2.F1
-- header: docs asked for HR4.B2 -- HR4.B2.F1
-- header: Home	Renewal	HR4.B2.F1 --  day 1 should be the full chase and then day 7 / 14 / 20 should reduce as people submit docs and get them approved..
-- header: -- these voluems are messed up for some reason -- so redone below on the 08th - recalculated below for both cells

select  count(distinct a.PolicyCode) 
from    edw.EXP_MyChill_Chase_Daily_Snapshot_Home a, stg.R0_HomePoliciesEligibleForRenewals b 
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-05-01' and '2026-07-31' 
and     PolicyType = 'Renewals' 
and     PolicyTypeGroup = 'Home' 
and     a.PolicyCode = b.PolicyCode 
and case 
        When Comp_DDM_Status				= 'O' then 1 
        When Gap_In_Cov_Ltr_Status			= 'O' then 1 
        When Val_For_Spec_Item_Status		= 'O' then 1 
        When PPS_Num_Status					= 'O' then 1 
        When Identification_Status			= 'O' then 1 
        When Digital_Journey_Status			= 'O' then 1 
        When Finance_Form_Status			= 'O' then 1 
        else 0
    End = 1 
Order by 1


# In[ ]:

-- HTML cell 25   kind: count query
-- step ids: HA1.E1
-- header: HA1.E1

select  count(distinct email), count(*)
from	dlk.EXT_XtremePushResults   a 
where	`timestamp` between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
and		campaign_name like 'Home % TYR %' 
and     interaction_type = 'sent' 
and     MessageType in ('SMS', 'EMAIL')


# In[ ]:

-- HTML cell 26   kind: count query
-- step ids: none in header
select count(distinct QuoteCodeReference) from stg.HA1_HFQ_Quotes
limit 10


# In[ ]:

-- HTML cell 27   kind: count query
-- step ids: HA3.F1
-- header: Home	ACQUISITION	HA3.F1

select  count(distinct QuoteCodeReference), count(distinct proposer_email)
from    stg.HA1_HFQ_Quotes
Where   QuoteCodeReference not in 
        (
            select  QuoteCodeReference
            from    dlk.hfq_response_quotes
            where   Quotes_Premium > 0
            and     Quotes_Outcome = 'PremiumReturned'
            and     Quotes_DateCreated between '2026-07-01' and '2026-07-31'
            Group by QuoteCodeReference
        )


# In[ ]:

-- HTML cell 28   kind: count query
-- step ids: HA6
-- header: HA6


select 
		count(distinct PolicyCode)  
		from edw.exp_mychill_chase_daily_snapshot_home a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-07-01' and '2026-07-31' and PolicyType = 'New Business' 
and case 
        when Gap_In_Cov_Ltr_Status = 'O' then 1 
        when Val_For_Spec_Item_Status = 'O' then 1 
        when PPS_Num_Status = 'O' then 1 
        When Identification_Status = 'O' then 1 
        when Finance_Form_Status = 'O' then 1 
        when Digital_Journey_Status = 'O' then 1 
        else 0
    End = 1


# In[ ]:

-- HTML cell 29   kind: count query
-- step ids: HA6.F1
-- header: HA6.F1

select  count(distinct PolicyCode)
From    (
            select  PolicyCode  
                    from edw.exp_mychill_chase_daily_snapshot_home a
            Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-07-01' and '2026-07-31' and PolicyType = 'New Business' 
            and case 
                    when Gap_In_Cov_Ltr_Status = 'O' then 1 
                    when Val_For_Spec_Item_Status = 'O' then 1 
                    when PPS_Num_Status = 'O' then 1 
                    When Identification_Status = 'O' then 1 
                    when Finance_Form_Status = 'O' then 1 
                    when Digital_Journey_Status = 'O' then 1 
                    else 0
                End = 1
            Group by PolicyCode 
            Having count(*) > 1     
        )


# In[ ]:

-- HTML cell 30   kind: count query
-- step ids: HA6.B1.2
-- header: HA6.B1.2

select  count(distinct b.PolicyCode)
from    stg.GlobalPoliciesSold a, dlk.MyChill_NewUploadDocumentEvents  b 
Where   a.PolicyCode = b.PolicyCode
and     ReportingSaleType = 'New Business' 
and     PolicyTypeGroup = 'Home'
and     `Timestamp` > '2026-07-01 00:00:00.000'


# In[ ]:

-- HTML cell 31   kind: count query
-- step ids: HA6.B1.4
-- header: HA6.B1.4

select  count(distinct PolicyCode)
From    (
            select  PolicyCode  
                    from edw.exp_mychill_chase_daily_snapshot_home a
            Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-07-01' and '2026-07-31' and PolicyType = 'New Business' 
            and case 
                    when Gap_In_Cov_Ltr_Status = 'O' then 1 
                    when Val_For_Spec_Item_Status = 'O' then 1 
                    when PPS_Num_Status = 'O' then 1 
                    When Identification_Status = 'O' then 1 
                    when Finance_Form_Status = 'O' then 1 
                    when Digital_Journey_Status = 'O' then 1 
                    else 0
                End = 1
            and    campaign = 'DAY 1'
            Group by PolicyCode 
        )


# In[ ]:

-- HTML cell 32   kind: count query
-- step ids: HA6.B1.5
-- header: HA6.B1.5

select  count(distinct PolicyCode)
From    (
            select  PolicyCode  
                    from edw.exp_mychill_chase_daily_snapshot_home a
            Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-07-01' and '2026-07-31' and PolicyType = 'New Business' 
            and case 
                    when Gap_In_Cov_Ltr_Status = 'O' then 1 
                    when Val_For_Spec_Item_Status = 'O' then 1 
                    when PPS_Num_Status = 'O' then 1 
                    When Identification_Status = 'O' then 1 
                    when Finance_Form_Status = 'O' then 1 
                    when Digital_Journey_Status = 'O' then 1 
                    else 0
                End = 1
            and    campaign <> 'DAY 1'
            Group by PolicyCode 
        )


# In[ ]:

-- HTML cell 33   kind: count query
-- step ids: HA6.B1.5
-- header: HA6.B1.5

SELECT  count(distinct a.PolicyCode)
FROM    stg.GlobalPoliciesSold                   a,
        ods.EventStream                          d 
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime > '2026-07-01 00:00:00.000' 
and     ReportingSaleType = 'New Business' 
and     EventDescription like '%Chase%' 
and     EventDescription like '%Final%'


# In[ ]:

-- HTML cell 34   kind: note or select
-- step ids: HA6.B1.3
-- header: HA6.B1.3

select  isAccepted, count(distinct b.PolicyCode)
from    stg.GlobalPoliciesSold a, dlk.MyChillWorkflow_DocumentStatus  b 
Where   a.PolicyCode = b.PolicyCode
and     ReportingSaleType = 'New Business' 
and     PolicyTypeGroup = 'Home'
and     `Timestamp` > '2026-07-01 00:00:00.000' 
/*and     isAccepted IsRejected */
Group by isAccepted
limit 100
;


# In[ ]:

-- HTML cell 35   kind: count query
-- step ids: HA6.B1.O1
-- header: HA6.B1.O1 -- no doc escalation and then cancellation

SELECT  count(distinct a.PolicyCode)
FROM    stg.GlobalPoliciesSold                   a,
        ods.EventStream                          d 
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime > '2026-07-01 00:00:00.000' 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
        (
            'Insurer Led Cancelation - Emailed Document - Reg canx email template',
            'Insurer Led Cancelation - Sent To Document Processing - Reg canx email template'
        )
and     a.PolicyCode in 
        (SELECT  distinct a.PolicyCode
        FROM    stg.GlobalPoliciesSold                   a,
                ods.EventStream                          d 
        Where   a.PolicyCode = d.SourcePolicyReference
        and     d.EventSourceId = 3 
        and     d.PolicyTypeGroup = 'Home'
        and     EventDateTime > '2026-07-01 00:00:00.000' 
        and     ReportingSaleType = 'New Business' 
        and     EventDescription like '%Chase%' 
        and     EventDescription like '%Final%' )


# In[ ]:

-- HTML cell 36   kind: staging build
-- step ids: none in header
Create or Replace Table stg.JulyPolicyState AS
select	EffectiveDate	,
		PolicyCode	,
		ClientCode,
		PolicyTypeGroup,
		OpenNum,
		CloseNum,
		NewBusGrossNum,
		MTAGrossNum
		MTCGrossNum,
		RenewGrossNum
		ReportingSaleDate	,
		PolicyInceptDate,
		PolicyLapsedDate	,
		PolicyLapsedFlag	,
		PolicyCancelDate	,
		PolicyCancelFlag,
		ReportingSaleType,	
		ReportingSaleCategory	,
		PolicyStatusCode	,
		PolicyStatusDesc	
from	edw.tbl_fact_Policy_Mvt 
where   EffectiveDate = '2026-07-31'
Order by 1


# In[ ]:

-- HTML cell 37   kind: staging build
-- step ids: HM3
-- header: Home	MTA	HM3

Create or Replace table stg.JJulyMTAs as 
SELECT
    na.ar_posting_date	as Workdate
    ,rtrim(na.ar_code)				as PolicyTranCode
    ,na.ar_trans_seq				as PolicyTransSeq
    ,na.ar_client_code				as ClientCode
    ,na.ar_policy_code				as PolicyCode
    ,CASE WHEN na.ar_cli_type = '8' AND na.ar_dtype = 6
            THEN 'Commission Journal'
            ELSE coalesce(pt.PremiumType, 'Unmapped')			
            END												as PremiumType
    ,CASE WHEN na.ar_cli_type = '8' AND na.ar_dtype = 6
            THEN 'MTA'
            ELSE coalesce(pt.PremiumTypeGroup, 'Unmpped')
            END												as PremiumTypeGroup
    ,(na.ar_com_initial_net_prem + na.ar_com_initial_comm)	as CCYGrossPremium
    ,(na.ar_cli_net_premium)								as CCYNetPremium
    ,(CASE WHEN na.ar_cli_type = '8' AND na.ar_dtype = 6
            THEN na.ar_cli_amount ELSE na.ar_com_initial_comm END) as CCYCommission
    ,(CASE WHEN na.ar_cli_type = '8' AND na.ar_dtype = 5
            THEN na.ar_cli_amount ELSE na.ar_cli_fees END)	as CCYFees
    ,na.ar_posting_date
    ,ar_effective_date
    ,na.ar_cli_type
    ,na.ar_com_type
    ,na.ar_return_sub_type
    ,na.ar_com_sta
    ,na.ar_confirmed_prov
    ,na.ar_dtype
    ,na.ar_user
    ,na.ar_addon_ref
    ,na.ar_trans_description as TransactionDescription
FROM dlk.RBSDATA2_NewArchive na
JOIN edw.tbl_ref_Mapping_BAR_Premium_Type pt
        ON pt.ar_cli_type = replace(na.ar_cli_type,' ','-')
        AND pt.ar_com_type = replace(na.ar_com_type,' ','-')
        AND pt.ar_return_sub_type = replace(na.ar_return_sub_type,' ','-')
        AND pt.ar_com_sta = replace(na.ar_com_sta,' ','-')
        AND pt.ar_confirmed_prov = replace(na.ar_confirmed_prov,' ','-')
WHERE	(1=1)
    AND  	(
        (na.ar_com_type In ('X','Y','Z','1','3','5','C','E')
        AND	na.ar_trans_seq = 0 )
        OR 
        (na.ar_cli_type = '1'
        AND	na.ar_new_flag IN (0,4)
        AND na.ar_com_sta=''
        AND na.ar_trans_seq = 0
        and	na.ar_insco = 'ZZZZ')
        OR
        (na.ar_cli_type = '5'
        AND na.ar_return_sub_type='5'
        AND na.ar_trans_seq = 0 
        and na.ar_insco = 'ZZZZ' )
        OR 
        (na.ar_cli_type = '8'
        AND ar_dtype IN (5,6)
        AND na.ar_trans_seq = 0 )
        OR
        (na.ar_insco ='KCI' 
        AND na.ar_addon_ref <> 0 
        AND na.ar_show_on_report = 'Y')
        ) 
    AND NA.ar_posting_date >= 20260701
    AND NA.ar_posting_date <= 20260731
    AND pt.PremiumTypeGroup = 'MTA'
;


# In[ ]:

-- HTML cell 38   kind: note or select
-- step ids: none in header
select  PolicyTypeGroup, PremiumType, count(*)
from    stg.JJulyMTAs a, stg.JulyPolicyState b 
Where a.PolicyCode = b.PolicyCode
Group by PolicyTypeGroup, PremiumType
limit 100


# In[ ]:

-- HTML cell 39   kind: count query
-- step ids: HM3
-- header: Home	MTA	HM3  - Not too sure but need to dig a bit more

select  count(distinct a.PolicyCode)
from    stg.JJulyMTAs a, stg.JulyPolicyState b 
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Home'
-- and     PremiumType = 'Mid Term Adjustment'
and     PolicyStatusDesc not in (
    'Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer'
)


# In[ ]:

-- HTML cell 40   kind: count query
-- step ids: HM2.O1
-- header: Home	MTA	HM2.O1  - Not too sure but need to dig a bit more

select  count(distinct a.PolicyCode)
from    stg.JJulyMTAs a, stg.JulyPolicyState b 
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Home'
-- and     PremiumType = 'Mid Term Adjustment'
and     PolicyStatusDesc in (
     'Cancelled Mid Term' , 'Lapsed for Transfer'
)


# In[ ]:

-- HTML cell 41   kind: count query
-- step ids: HM4.B1
-- header: Home	MTA	HM4.B1  - the base policy list is the one to be confirmed

select  count(distinct b.PolicyCode)
from    stg.JJulyMTAs a, dlk.MyChill_NewUploadDocumentEvents  b 
Where   a.PolicyCode = b.PolicyCode
and     `Timestamp` > '2026-07-01 00:00:00.000' 
and     b.PolicyCode in 
        (
            select  distinct a.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b 
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Home'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
        )


# In[ ]:

-- HTML cell 42   kind: count query
-- step ids: HM4.B1.F1
-- header: Home	MTA	HM4.B1.F1

select  count(distinct a.PolicyCode) 
from    edw.EXP_MyChill_Chase_Daily_Snapshot_Home a 
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-05-01' and '2026-07-31' 
and     PolicyTypeGroup = 'Home' 
and case 
        When Comp_DDM_Status				= 'O' then 1 
        When Gap_In_Cov_Ltr_Status			= 'O' then 1 
        When Val_For_Spec_Item_Status		= 'O' then 1 
        When PPS_Num_Status					= 'O' then 1 
        When Identification_Status			= 'O' then 1 
        When Digital_Journey_Status			= 'O' then 1 
        When Finance_Form_Status			= 'O' then 1 
        else 0
    End = 1 
/*and Campaign = 'DAY 20'*/
and     a.PolicyCode in 
        (
            select  distinct a.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b 
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Home'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
        )


# In[ ]:

-- HTML cell 43   kind: note or select
-- step ids: HM4
-- header: Home	MTA	HM4

select  TransactionDescription, Count(distinct b.PolicyCode), sum(CCYGrossPremium), sum(CCYFees)
from    stg.JJulyMTAs a, stg.JulyPolicyState b 
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Home'
and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
and     ( 
            CCYGrossPremium <> 0 
        or 
            CCYFees <> 0 )
Group by TransactionDescription


# In[ ]:

-- HTML cell 44   kind: count query
-- step ids: HM4
-- header: Home	MTA	HM4

select  Count(distinct b.PolicyCode), sum(CCYGrossPremium), sum(CCYFees)
from    stg.JJulyMTAs a, stg.JulyPolicyState b 
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Home'
and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
and     ( 
            CCYGrossPremium <> 0 
        or 
            CCYFees <> 0 )


# In[ ]:

-- HTML cell 45   kind: note or select
-- step ids: none in header
-- header: data investigation

select  b.PolicyCode, sum(CCYGrossPremium), sum(CCYFees), count(distinct TransactionDescription)
from    stg.JJulyMTAs a, stg.JulyPolicyState b 
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Home'
and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
and     ( 
            CCYGrossPremium <> 0 
        or 
            CCYFees <> 0 )
Group by b.PolicyCode
Having /* count(distinct TransactionDescription) > 1 and */ sum(CCYGrossPremium) + sum(CCYFees) <> 0


# In[ ]:

-- HTML cell 46   kind: note or select
-- step ids: none in header
-- header: FINR20001
-- header: MULC8K007

Select  *
from    stg.JJulyMTAs a, stg.JulyPolicyState b 
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Home'
and     a.PolicyCode = '0YAJ41002'


# In[ ]:

-- HTML cell 47   kind: count query
-- step ids: HM4c
-- header: Home	MTA	HM4c

select  Count(distinct b.PolicyCode), sum(CCYGrossPremium), sum(CCYFees)
from    stg.JJulyMTAs a, stg.JulyPolicyState b 
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Home'
and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
and     ( 
            CCYGrossPremium = 0 
        and 
            CCYFees = 0 )


# In[ ]:

-- HTML cell 48   kind: note or select
-- step ids: none in header
select  EventDescription, count(*), count(distinct SourcePolicyReference) 
from    ods.EventStream
Where   SourcePolicyReference in 
        (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Home'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
        )
and     EventDate between '2026-07-01' and '2026-07-31'
and     EventSourceId = 3 
Group by EventDescription
Order by 2 desc 
/*
    Emailed Document
    Document Transmitted
*/


# In[ ]:

-- HTML cell 49   kind: count query
-- step ids: HM6
-- header: Home	MTA	HM6

select  count(distinct SourcePolicyReference) 
from    ods.EventStream
Where   SourcePolicyReference in 
        (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Home'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
        )
and     EventDate between '2026-07-01' and '2026-07-31'
and     EventSourceId = 3 
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        )


# In[ ]:

-- HTML cell 50   kind: count query
-- step ids: HM4.B1.1
-- header: Home	MTA	HM4.B1.1

SELECT  count(distinct a.PolicyCode)
FROM    (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Home'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
        )                                       a,
        ods.EventStream                          d 
Where   d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000'  
and     EventDescription like '% Body' 
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        )
and     a.PolicyCode = d.SourcePolicyReference


# In[ ]:

-- HTML cell 51   kind: count query
-- step ids: HM4.B1.1
-- header: Home	MTA	HM4.B1.1

select  count(distinct PolicyCode)
From    (
            select  PolicyCode  
                    from edw.exp_mychill_chase_daily_snapshot_home a
            Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-07-01' and '2026-07-31' and PolicyType = 'New Business' 
            and case 
                    when Gap_In_Cov_Ltr_Status = 'O' then 1 
                    when Val_For_Spec_Item_Status = 'O' then 1 
                    when PPS_Num_Status = 'O' then 1 
                    When Identification_Status = 'O' then 1 
                    when Finance_Form_Status = 'O' then 1 
                    when Digital_Journey_Status = 'O' then 1 
                    else 0
                End = 1
            and     PolicyCode in 
            (
                select  b.PolicyCode
                from    stg.JJulyMTAs a, stg.JulyPolicyState b
                Where   a.PolicyCode = b.PolicyCode
                and     PolicyTypeGroup = 'Home'
                and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
            ) 
        )


# In[ ]:

-- HTML cell 52   kind: count query
-- step ids: HM4.B1.2
-- header: Home	MTA	HM4.B1.2

select  count(distinct b.PolicyCode)
from    (
                select  b.PolicyCode
                from    stg.JJulyMTAs a, stg.JulyPolicyState b
                Where   a.PolicyCode = b.PolicyCode
                and     PolicyTypeGroup = 'Home'
                and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
            ) a, 
        dlk.MyChill_NewUploadDocumentEvents  b 
Where   a.PolicyCode = b.PolicyCode
and     `Timestamp` between '2026-07-01 00:00:00.000' AND '2026-08-01 00:00:00.000'


# In[ ]:

-- HTML cell 53   kind: count query
-- step ids: HM4.B1.4
-- header: Home	MTA	HM4.B1.4


select  count(distinct PolicyCode)
From    (
            select  PolicyCode  
                    from edw.exp_mychill_chase_daily_snapshot_home a
            Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-07-01' and '2026-07-31'  
            and case 
                    when Gap_In_Cov_Ltr_Status = 'O' then 1 
                    when Val_For_Spec_Item_Status = 'O' then 1 
                    when PPS_Num_Status = 'O' then 1 
                    When Identification_Status = 'O' then 1 
                    when Finance_Form_Status = 'O' then 1 
                    when Digital_Journey_Status = 'O' then 1 
                    else 0
                End = 1
            and Campaign = 'DAY 1'
            and     PolicyCode in 
            (
                select  b.PolicyCode
                from    stg.JJulyMTAs a, stg.JulyPolicyState b
                Where   a.PolicyCode = b.PolicyCode
                and     PolicyTypeGroup = 'Home'
                and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
            ) 
        )


# In[ ]:

-- HTML cell 54   kind: count query
-- step ids: HM4.B1.5
-- header: Home	MTA	HM4.B1.5


select  count(distinct PolicyCode)
From    (
            select  PolicyCode  
                    from edw.exp_mychill_chase_daily_snapshot_home a
            Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-07-01' and '2026-07-31'  
            and case 
                    when Gap_In_Cov_Ltr_Status = 'O' then 1 
                    when Val_For_Spec_Item_Status = 'O' then 1 
                    when PPS_Num_Status = 'O' then 1 
                    When Identification_Status = 'O' then 1 
                    when Finance_Form_Status = 'O' then 1 
                    when Digital_Journey_Status = 'O' then 1 
                    else 0
                End = 1
            and Campaign = 'DAY 20'
            and     PolicyCode in 
            (
                select  b.PolicyCode
                from    stg.JJulyMTAs a, stg.JulyPolicyState b
                Where   a.PolicyCode = b.PolicyCode
                and     PolicyTypeGroup = 'Home'
                and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
            ) 
        )


# In[ ]:

-- HTML cell 55   kind: note or select
-- step ids: HM4.B1.3
-- header: Home	MTA	HM4.B1.3

select  isAccepted, count(distinct b.PolicyCode)
from    (
                select  b.PolicyCode
                from    stg.JJulyMTAs a, stg.JulyPolicyState b
                Where   a.PolicyCode = b.PolicyCode
                and     PolicyTypeGroup = 'Home'
                and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
            )  a, dlk.MyChillWorkflow_DocumentStatus  b 
Where   a.PolicyCode = b.PolicyCode
and     `Timestamp` between '2026-07-01 00:00:00.000' AND '2026-08-01 00:00:00.000' 
/*and     isAccepted IsRejected */
Group by isAccepted
limit 100
;


# In[ ]:

-- HTML cell 56   kind: note or select
-- step ids: HM4.B1.O1
-- header: Home	MTA	HM4.B1.O1

SELECT  EventDescription, count(distinct a.PolicyCode)
FROM    (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Home'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
        )                                       a,
        (select  distinct PolicyCode  
                    from edw.exp_mychill_chase_daily_snapshot_home a
            Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-07-01' and '2026-07-31' 
            and case 
                    when Gap_In_Cov_Ltr_Status = 'O' then 1 
                    when Val_For_Spec_Item_Status = 'O' then 1 
                    when PPS_Num_Status = 'O' then 1 
                    When Identification_Status = 'O' then 1 
                    when Finance_Form_Status = 'O' then 1 
                    when Digital_Journey_Status = 'O' then 1 
                    else 0
                End = 1
                )                                b,
        ods.EventStream                          d 
Where   d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000'  
and     EventDescription like '% CXL %' 

and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        )
and     a.PolicyCode = d.SourcePolicyReference 
and     a.PolicyCode = b.PolicyCode
Group by EventDescription


# In[ ]:

-- HTML cell 57   kind: note or select
-- step ids: HM6.B1.1
-- header: Home	MTA	HM6.B1.1 - build - counts follow in the next cell

SELECT  EventDescription, count(distinct a.PolicyCode)
FROM    (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Home'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
        )                                       a,
        ods.EventStream                          d 
Where   d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000'  
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        )
and     a.PolicyCode = d.SourcePolicyReference 
Group by EventDescription               
Order by 2 desc


# In[ ]:

-- HTML cell 58   kind: note or select
-- step ids: HM6.B1.1
-- header: Home	MTA	HM6.B1.1 - counts follow in the next cell

SELECT  EventDescription, count(distinct a.PolicyCode)
FROM    (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Home'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
        )                                       a,
        ods.EventStream                          d 
Where   d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000'  
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        )
and     a.PolicyCode = d.SourcePolicyReference 
Group by EventDescription               
Order by 2 desc


# In[ ]:

-- HTML cell 59   kind: count query
-- step ids: HM6.B1.1
-- header: Home	MTA	HM6.B1.1 - counts follow in the next cell

SELECT  count(distinct a.PolicyCode)
FROM    (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Home'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
        )                                       a,
        ods.EventStream                          d 
Where   d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000'  
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        )
and     EventDescription in (

        'New Business - Emailed Document - Terms Of Business',
        'New Business - Emailed Document - Cover Letter',
        'New Business - Emailed Document - 04 - Suitability Statement',
        'New Business - Document Transmitted - 04 - Suitability Statement',
        'New Business - Document Transmitted - Terms Of Business',
        'New Business - Document Transmitted - Cover Letter'
)        
and     a.PolicyCode = d.SourcePolicyReference


# In[ ]:

-- HTML cell 60   kind: staging build
-- step ids: HC0
-- header: Home	CANCELLATION	HC0
-- header: -- collecting the client / policy codes
-- header: please note

Create or Replace Table stg.JulyHomeCancellations as 
select  distinct PolicyStatusDesc,  ShortDescription, PolicyCode, ClientCode
from    edw.tbl_fact_policy_mtc 
Where   PolicyTypeGroup = 'Home'
and     EffectiveDate = '2026-07-31'
/* poteential ods based build 
  SELECT
      RTRIM(p.pl_code)                  AS PolicyCode,
      LTRIM(RTRIM(p.pl_status))         AS PolicyStatusCode,
      LTRIM(RTRIM(s.PolicyStatusDesc))  AS PolicyStatusDesc,
      c.ShortDescription,
      TRY_CONVERT(
          date,
          CONVERT(varchar(8), p.pl_cancel_date),
          112
      ) AS PolicyCancelDate
  FROM dlk.RBSDATA2_Policy_Physical p
  INNER JOIN DWH.tbl_ref_PolicyStatus s -- lookup table 
      ON LTRIM(RTRIM(p.pl_status))
       = LTRIM(RTRIM(s.PolicyStatusCode))
  LEFT JOIN DataFramework.ODS.RELAY_ConfigurableCodeListItem c -- lookup table
      ON p.pl_cancel_premium_type = c.Code
     AND c.Category = 32
     AND c.DeletedDate IS NULL
  WHERE s.CancelFlag = 'Y'
  ORDER BY PolicyCode;
  */


# In[ ]:

-- HTML cell 61   kind: note or select
-- step ids: HC0
-- header: Home	CANCELLATION	HC0
-- header: -- the short description is used to populate the various cells under HC*
-- header: please note

select  PolicyStatusDesc,  ShortDescription, count(distinct PolicyCode), count(distinct ClientCode)
from    edw.tbl_fact_policy_mtc 
Where   PolicyTypeGroup = 'Home'
and     EffectiveDate = '2026-07-31'
Group by PolicyStatusDesc,  ShortDescription
Order by 3 desc


# In[ ]:

-- HTML cell 62   kind: note or select
-- step ids: HC1a
-- header: Home	CANCELLATION	HC1a

select  PolicyStatusDesc,  count(distinct PolicyCode)
from    edw.tbl_fact_policy_mtc 
Where   PolicyTypeGroup = 'Home'
and     EffectiveDate = '2026-07-31'
and     (    
            ShortDescription like 'Client%'
        or            
            ShortDescription like 'Customer%'
        )            
Group by PolicyStatusDesc
Order by 2 desc


# In[ ]:

-- HTML cell 63   kind: note or select
-- step ids: HC1b.F1
-- header: Home	CANCELLATION	HC1b.F1

select  *
from    edw.tbl_fact_policy_mtc 
Where   PolicyTypeGroup = 'Home'
and     EffectiveDate = '2026-07-31'
and     ShortDescription like '%NCT%'


# In[ ]:

-- HTML cell 64   kind: count query
-- step ids: HC2
-- header: Home	CANCELLATION	HC2


select  Count(distinct a.PolicyCode)  
from    (select  distinct PolicyCode  
                    from edw.exp_mychill_chase_daily_snapshot_home a
            Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-07-01' and '2026-07-31' 
            and case 
                    when Gap_In_Cov_Ltr_Status = 'O' then 1 
                    when Val_For_Spec_Item_Status = 'O' then 1 
                    when PPS_Num_Status = 'O' then 1 
                    When Identification_Status = 'O' then 1 
                    when Finance_Form_Status = 'O' then 1 
                    when Digital_Journey_Status = 'O' then 1 
                    else 0
                End = 1
                )               a,
        stg.JulyHomeCancellations   b
Where   left(a.PolicyCode,6) = b.ClientCode


# In[ ]:

-- HTML cell 65   kind: count query
-- step ids: HC3
-- header: Home	CANCELLATION	HC3


select  Count(distinct a.PolicyCode)  
from    (select  PolicyCode  
                    from edw.exp_mychill_chase_daily_snapshot_home a
            Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-07-01' and '2026-07-31' 
            and case 
                    when Gap_In_Cov_Ltr_Status = 'O' then 1 
                    when Val_For_Spec_Item_Status = 'O' then 1 
                    when PPS_Num_Status = 'O' then 1 
                    When Identification_Status = 'O' then 1 
                    when Finance_Form_Status = 'O' then 1 
                    when Digital_Journey_Status = 'O' then 1 
                    else 0
                End = 1
            and Campaign <> 'DAY 1'  /* first is request and all the next are escalation I think - when we go daily build, we could do that */
                )               a,
        stg.JulyHomeCancellations   b
Where   left(a.PolicyCode,6) = b.ClientCode


# In[ ]:

-- HTML cell 66   kind: count query
-- step ids: HC4
-- header: Home	CANCELLATION	HC4

select  Count(distinct SourcePolicyReference) 
from    ods.eventstream             a,
        stg.JulyHomeCancellations   b 
Where   left(a.SourcePolicyReference,6) = b.ClientCode 
and     a.PolicyTypeGroup = 'Home'
and     a.EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000'
and     a.EventSourceId = 3 
and     a.EventDescription like '%Document Chase%'
and     a.EventDescription like '%Final Notice%'
and     (   a.EventDescription like '%Emailed Document%' 
        or 
            a.EventDescription like '%Document Transmitted%'
        )
-- left(a.SourcePolicyReference,6) = b.PolicyCode


# In[ ]:

-- HTML cell 67   kind: count query
-- step ids: HC5
-- header: Home	CANCELLATION	HC5

select  Count(distinct SourcePolicyReference) 
from    ods.eventstream             a,
        stg.JulyHomeCancellations   b 
Where   left(a.SourcePolicyReference,6) = b.ClientCode 
and     a.PolicyTypeGroup = 'Home'
and     a.EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000'
and     a.EventSourceId = 3 
and     a.EventDescription like '%CXL%'
and     (   a.EventDescription like '%Emailed Document%' 
        or 
            a.EventDescription like '%Document Transmitted%'
        )


# In[ ]:

-- HTML cell 68   kind: note or select
-- step ids: none in header
-- (cell was empty)


# In[ ]:

-- HTML cell 69   kind: staging build
-- step ids: none in header
-- header: Doc Request

Create or Replace table stg.DocRequestCustomers as 
Select  CustomerPhoneNumber, ConversationStartTime, ConversationId
from    stg.A0_genesys_derived_data
Where   ConversationStartTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000'
and     QueueName = 'INBOUND_Documents_Out'
Group by CustomerPhoneNumber, ConversationStartTime, ConversationId


# In[ ]:

-- HTML cell 70   kind: staging build
-- step ids: none in header
-- header: Doc Request

Create or Replace table stg.DocRequestClientCodes as 
Select  CustomerPhoneNumber, a.RapierCustomerId, a.SourceSystemCustomerId as ClientCode, ConversationStartTime, ConversationId
from    pii.customer_data_assembled a, 
        stg.DocRequestCustomers     b
Where   a.CustomerPhone = b.CustomerPhoneNumber
and     a.SourceSystemId = 1 
and     a.SubSourceSystemId = 1 
Group by CustomerPhoneNumber, a.RapierCustomerId, a.SourceSystemCustomerId , ConversationStartTime, ConversationId


# In[ ]:

-- HTML cell 71   kind: note or select
-- step ids: none in header
select * from stg.DocRequestClientCodes limit 10


# In[ ]:

-- HTML cell 72   kind: note or select
-- step ids: HD1
-- header: Home	Doc Request	HD1

SELECT  EventDescription, count(distinct d.SourcePolicyReference), count(*)
FROM    stg.DocRequestClientCodes                a,
        ods.EventStream                          d 
Where   a.clientCode = left(d.SourcePolicyReference,6)
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000' 
and     EventDateTime between ConversationStartTime and dateadd(day,2,ConversationStartTime)
and     (   d.EventDescription like '%Emailed Document%' 
        or 
            d.EventDescription like '%Document Transmitted%'
        ) 
Group by EventDescription
Order by 2 desc ;


# In[ ]:

-- HTML cell 73   kind: note or select
-- step ids: none in header
-- header: Doc Request	-- we are still tracking by an event happening - sometimes a call comes through with no event - so we need to join to a higher level policy client table that we can do later

/* Home	Doc Request	HD1 -- Motor	Doc Request	D1 -- Van	Doc Request	VD1
*/
SELECT  d.PolicyTypeGroup, count(distinct d.SourcePolicyReference), count(distinct ConversationId)
FROM    stg.DocRequestClientCodes                a,
        ods.EventStream                          d 
Where   a.clientCode = left(d.SourcePolicyReference,6)
and     d.EventSourceId = 3 
/*and     d.PolicyTypeGroup = 'Home'*/
and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000' 
Group by d.PolicyTypeGroup
;


# In[ ]:

-- HTML cell 74   kind: note or select
-- step ids: HD1.F1, D1.F1, VD1.F1
-- header: Home	Doc Request	HD1.F1 -- Motor	Doc Request	D1.F1 -- Van	Doc Request	VD1.F1

select  PolicyTypeGroup, count(distinct a.ConversationId)
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
Group by PolicyTypeGroup
;


# In[ ]:

-- HTML cell 75   kind: count query
-- step ids: HD2
-- header: Home	Doc Request	HD2 - we are counting policies and also storing the breakdown for Chill to confirm

SELECT  count(distinct d.SourcePolicyReference)
FROM    stg.DocRequestClientCodes                a,
        ods.EventStream                          d 
Where   a.clientCode = left(d.SourcePolicyReference,6)
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000' 
and     EventDateTime between ConversationStartTime and dateadd(day,2,ConversationStartTime)
and     (   d.EventDescription like '%Emailed Document%' 
        or 
            d.EventDescription like '%Document Transmitted%'
        ) 
;
SELECT  EventDescription, count(distinct d.SourcePolicyReference), count(*)
FROM    stg.DocRequestClientCodes                a,
        ods.EventStream                          d 
Where   a.clientCode = left(d.SourcePolicyReference,6)
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000' 
and     EventDateTime between ConversationStartTime and dateadd(day,2,ConversationStartTime)
and     (   d.EventDescription like '%Emailed Document%' 
        or 
            d.EventDescription like '%Document Transmitted%'
        ) 
Group by EventDescription
Order by 2 desc ;


# In[ ]:

-- HTML cell 76   kind: count query
-- step ids: D2
-- header: Motor Doc Request	D2 - we are counting policies and also storing the breakdown for Chill to confirm

SELECT  count(distinct d.SourcePolicyReference)
FROM    stg.DocRequestClientCodes                a,
        ods.EventStream                          d 
Where   a.clientCode = left(d.SourcePolicyReference,6)
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Motor'
and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000' 
and     EventDateTime between ConversationStartTime and dateadd(day,2,ConversationStartTime)
and     (   d.EventDescription like '%Emailed Document%' 
        or 
            d.EventDescription like '%Document Transmitted%'
        ) 
;
SELECT  EventDescription, count(distinct d.SourcePolicyReference), count(*)
FROM    stg.DocRequestClientCodes                a,
        ods.EventStream                          d 
Where   a.clientCode = left(d.SourcePolicyReference,6)
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Motor'
and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000' 
and     EventDateTime between ConversationStartTime and dateadd(day,2,ConversationStartTime)
and     (   d.EventDescription like '%Emailed Document%' 
        or 
            d.EventDescription like '%Document Transmitted%'
        ) 
Group by EventDescription
Order by 2 desc ;


# In[ ]:

-- HTML cell 77   kind: count query
-- step ids: VD2
-- header: Van Doc Request	VD2 - we are counting policies and also storing the breakdown for Chill to confirm

SELECT  count(distinct d.SourcePolicyReference)
FROM    stg.DocRequestClientCodes                a,
        ods.EventStream                          d 
Where   a.clientCode = left(d.SourcePolicyReference,6)
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Van'
and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000' 
and     EventDateTime between ConversationStartTime and dateadd(day,2,ConversationStartTime)
and     (   d.EventDescription like '%Emailed Document%' 
        or 
            d.EventDescription like '%Document Transmitted%'
        ) 
;
SELECT  EventDescription, count(distinct d.SourcePolicyReference), count(*)
FROM    stg.DocRequestClientCodes                a,
        ods.EventStream                          d 
Where   a.clientCode = left(d.SourcePolicyReference,6)
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Van'
and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000' 
and     EventDateTime between ConversationStartTime and dateadd(day,2,ConversationStartTime)
and     (   d.EventDescription like '%Emailed Document%' 
        or 
            d.EventDescription like '%Document Transmitted%'
        ) 
Group by EventDescription
Order by 2 desc ;


# In[ ]:

-- HTML cell 78   kind: note or select
-- step ids: HD3.F1, D3.F1, VD3.F1
-- header: Home	Doc Request	HD3.F1
-- header: Motor	Doc Request	 D3.F1
-- header: Van 	Doc Request	VD3.F1

select PolicyTypeGroup, count(distinct clientCode)
from    (
            SELECT  d.PolicyTypeGroup, a.clientCode, count(distinct cast(ConversationStartTime as date)) calleddates
            FROM    stg.DocRequestClientCodes                a,
                    ods.EventStream                          d 
            Where   a.clientCode = left(d.SourcePolicyReference,6)
            and     d.EventSourceId = 3 
            and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000' 
            Group by d.PolicyTypeGroup, a.clientCode
        ) x 
Where   calleddates > 1 
Group by PolicyTypeGroup
;


# In[ ]:

-- HTML cell 79   kind: note or select
-- step ids: HD3.F2, D3.F2, VD3.F2
-- header: Home	Doc Request	HD3.F2
-- header: Motor	Doc Request	 D3.F2
-- header: Van 	Doc Request	VD3.F2

select PolicyTypeGroup, count(distinct clientCode), count(distinct SourcePolicyReference)
from    (
            SELECT  d.PolicyTypeGroup, a.clientCode, d.SourcePolicyReference, EventDescription,  count(distinct EventDateTime) EventDates
            FROM    stg.DocRequestClientCodes                a,
                    ods.EventStream                          d 
            Where   a.clientCode = left(d.SourcePolicyReference,6)
            and     d.EventSourceId = 3 
            and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000' 
            Group by d.PolicyTypeGroup, a.clientCode, d.SourcePolicyReference, EventDescription
        ) x 
Where   EventDates > 1 
Group by PolicyTypeGroup
;


# In[ ]:

-- HTML cell 80   kind: staging build
-- step ids: none in header
-- header: Claims

Create or Replace table stg.ClaimCustomers as 
Select  CustomerPhoneNumber, ConversationStartTime, ConversationId
from    stg.A0_genesys_derived_data
Where   ConversationStartTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000'
and     QueueName = 'INBOUND_Claims'
Group by CustomerPhoneNumber, ConversationStartTime, ConversationId


# In[ ]:

-- HTML cell 81   kind: staging build
-- step ids: none in header
-- header: Claims

Create or Replace table stg.DocRequestClientCodes as 
Select  CustomerPhoneNumber, a.RapierCustomerId, a.SourceSystemCustomerId as ClientCode, ConversationStartTime, ConversationId
from    pii.customer_data_assembled a, 
        stg.ClaimCustomers     b
Where   a.CustomerPhone = b.CustomerPhoneNumber
and     a.SourceSystemId = 1 
and     a.SubSourceSystemId = 1 
Group by CustomerPhoneNumber, a.RapierCustomerId, a.SourceSystemCustomerId , ConversationStartTime, ConversationId


# In[ ]:

-- HTML cell 82   kind: note or select
-- step ids: none in header
-- header: Claims	-- we are still tracking by an event happening - sometimes a call comes through with no event - so we need to join to a higher level policy client table that we can do later

/* Claims 
    HCL1a	Home claim reported
     CL1a	Home claim reported
    VCL1a	Home claim reported

*/
SELECT  d.PolicyTypeGroup, count(distinct d.SourcePolicyReference), count(distinct ConversationId)
FROM    stg.DocRequestClientCodes                a,
        ods.EventStream                          d 
Where   a.clientCode = left(d.SourcePolicyReference,6)
and     d.EventSourceId = 3 
and     EventDateTime between '2025-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000' 
Group by d.PolicyTypeGroup
;


# In[ ]:

-- HTML cell 83   kind: note or select
-- step ids: HR0.F1
-- header: Home	Renewal	HR0.F1

select	HomeClaimType, count(distinct b.PolicyCode)
from	dlk.EXT_Home_QS_ClaimDetails    a, 
        dlk.ext_home_qs_policydetails   b
Where	a.HomeRiskId = upper(b.RiskId)
and		TransactionDate between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000'
Group by HomeClaimType
order by 2 
-- use only Quotation Provided for this count -- 681 -- the unique policycodes involved are 681 too


# In[ ]:

-- HTML cell 84   kind: note or select
-- step ids: VR3.O1
-- header: Van	Renewal	VR3.O1

select  *
from    stg.VanRenewalsJuly b  
limit 10


# In[ ]:

-- HTML cell 85   kind: count query
-- step ids: VR3.O1
-- header: Van	Renewal	VR3.O1	Policy lapsed

select  count(distinct PolicyCode)
from    stg.VanRenewalsJuly b  
Where   PolicyRetNum is null
and     PolicyOfferNum = 1
;


# In[ ]:

-- HTML cell 86   kind: count query
-- step ids: VR3a, VR4
-- header: Van	Renewal	VR3a
-- header: Van	Renewal	VR4

select  count(distinct TyPolicyCode)
from    stg.VanRenewalsJuly a , dlk.appliedrenewals_paymentsuccess b   
Where   PolicyRetNum = 1 
and     PolicyOfferNum = 1
and     a.TYPolicyCode = b.PolicyCodeForRenewal
;


# In[ ]:

-- HTML cell 87   kind: count query
-- step ids: VR3b
-- header: Van	Renewal	VR3b
-- header: --= Not enough Volume here

select  count(distinct PolicyCode)  , count(*)
from    ods.eventstream a, stg.VanRenewalsJuly b  
Where   a.SourcePolicyReference = b.TyPolicyCode
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
and     EventDescription like '%Receipt%'
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        )


# In[ ]:

-- HTML cell 88   kind: count query
-- step ids: VR4.B2
-- header: Van	Renewal	VR4.B2

select  count(distinct PolicyCode)  , count(*)
from    ods.eventstream a, stg.VanRenewalsJuly b  
Where   a.SourcePolicyReference = b.TyPolicyCode
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
and     EventDescription like '%Body%'
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        )


# In[ ]:

-- HTML cell 89   kind: count query
-- step ids: VR4.B2.F1
-- header: Van	Renewal	VR4.B2.F1

/* docs asked for VA6.B1.F1 VA6.B1.5


 */
select  
		count(distinct PolicyCode) 
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-05-01' and '2026-07-31' 
and PolicyType = 'Renewals' 
and PolicyTypeGroup = 'Van' 
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
-- and Campaign = 'DAY 1'


# In[ ]:

-- HTML cell 90   kind: count query
-- step ids: none in header
-- header: This is not asked for?

select  
		count(distinct PolicyCode) 
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-05-01' and '2026-07-31' 
and PolicyType = 'Renewals' 
and PolicyTypeGroup = 'Van' 
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
and Campaign <> 'DAY 1'


# In[ ]:

-- HTML cell 91   kind: count query
-- step ids: VR5
-- header: Van	Renewal	VR5

select  count(distinct PolicyCode)  , count(*)
from    stg.VanRenewalsJuly b  
Where   PolicyRetNum = 1


# In[ ]:

-- HTML cell 92   kind: note or select
-- step ids: none in header
-- header: Van	Renewal	Documents

select  EventDescription, count(distinct PolicyCode)  , count(*)
from    ods.eventstream a, stg.VanRenewalsJuly b  
Where   a.SourcePolicyReference = b.TyPolicyCode /* new policy */ 
and     PolicyRetNum = 1 
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        ) 
Group by EventDescription 
Order by 2 desc ;
select  EventDescription, count(distinct PolicyCode)  , count(*)
from    ods.eventstream a, stg.VanRenewalsJuly b  
Where   a.SourcePolicyReference = b.PolicyCode      /* current policy */ 
and     PolicyRetNum = 1 
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        ) 
Group by EventDescription 
Order by 2 desc


# In[ ]:

-- HTML cell 93   kind: count query
-- step ids: VR4.B2
-- header: Van	Renewal	VR4.B2

select  count(distinct PolicyCode)
from    (
            select  distinct PolicyCode
            from    ods.eventstream a, stg.VanRenewalsJuly b  
            Where   a.SourcePolicyReference = b.TyPolicyCode
            and     PolicyRetNum = 1 
            and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
            and     EventDescription like '%C&D%'
            and     (   EventDescription like '%Emailed Document%' 
                    or 
                        EventDescription like '%Document Transmitted%'
                    ) 
            union 
            select  distinct PolicyCode
            from    ods.eventstream a, stg.VanRenewalsJuly b  
            Where   a.SourcePolicyReference = b.PolicyCode
            and     PolicyRetNum = 1 
            and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
            and     EventDescription like '%C&D%'
            and     (   EventDescription like '%Emailed Document%' 
                    or 
                        EventDescription like '%Document Transmitted%'
                    ) 
    ) x


# In[ ]:

-- HTML cell 94   kind: count query
-- step ids: VR3.B1.1
-- header: Van	Renewal	VR3.B1.1

select  count(distinct PolicyCode) 
from    stg.VanRenewalsJuly
Where (
            LYPolicyRenewDateAdj < TyReportingSaleDate 
        OR
            TyReportingSaleDate is null )    
and     PolicyOfferNum = 1 
;


# In[ ]:

-- HTML cell 95   kind: count query
-- step ids: VR3.B1.2
-- header: Van	Renewal	VR3.B1.2

  -- get Renewal emails from XP table
select count(distinct PolicyCode) 
from  
    (
        select  distinct b.PolicyCode
        from    dlk.EXT_XtremePushResults a, stg.VanRenewalsJuly b 
        where   campaign_name like '%Van%' 
        and     campaign_name like '%Lapsed%' 
        and     a.PolicyCode = b.PolicyCode 
        and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
        and     interaction_type = 'sent' 
        and     MessageType  in ( 'EMAIL', 'SMS')
        union
        select  distinct b.PolicyCode 
        from    dlk.EXT_XtremePushResults_Policy a, stg.VanRenewalsJuly b 
        where   campaign_name like '%Van%' 
        and     campaign_name like '%Lapsed%' 
        and     a.PolicyCode = b.PolicyCode 
        and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
        and     interaction_type = 'sent' 
        and     MessageType  in ( 'EMAIL', 'SMS')
    ) x


# In[ ]:

-- HTML cell 96   kind: count query
-- step ids: VR3.B1.2.F1
-- header: Van	Renewal	VR3.B1.2.F1


select  count(distinct a.PolicyCode)
from    dlk.EXT_XtremePushResults_Policy a, stg.VanRenewalsJuly b 
where   campaign_name like '%Van%' 
and     campaign_name like '%Lapsed%' 
and     a.PolicyCode = b.PolicyCode 
and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
and     interaction_type = 'sent' 
and     MessageType  in ( 'EMAIL', 'SMS')
and     a.PolicyCode not in 
        (
            select  distinct a.PolicyCode
            from    dlk.EXT_XtremePushResults_Policy a, stg.VanRenewalsJuly b 
            where   campaign_name like '%Van%' 
            and     campaign_name like '%Lapsed%' 
            and     a.PolicyCode = b.PolicyCode 
            and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
            and     interaction_type in ('open','click')
            and     MessageType  in ( 'EMAIL', 'SMS')
        )
and     a.PolicyCode in 
        (
            select  distinct a.PolicyCode
            from    dlk.EXT_XtremePushResults_Policy a, stg.VanRenewalsJuly b 
            where   campaign_name like '%Van%' 
            and     campaign_name like '%Lapsed%' 
            and     a.PolicyCode = b.PolicyCode 
            and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
            and     interaction_type in ('bounce')
            and     MessageType  in ( 'EMAIL', 'SMS')
        )


# In[ ]:

-- HTML cell 97   kind: count query
-- step ids: R3.B1.O1
-- header: Van	Renewal	R3.B1.O1

select	count(distinct PolicyCode) 
from	stg.VanRenewalsJuly
Where	(	
			TYReportingSaleDate > LYPolicyRenewDateAdj 
			) 
and     PolicyOfferNum > 0 
and     PolicyRetNum = 1 
and 	PolicyCode IN 
		(
			select  distinct b.PolicyCode
			from    dlk.EXT_XtremePushResults a, stg.VanRenewalsJuly b 
			where   campaign_name like '%Van%' 
			and     campaign_name like '%Lapsed%' 
			and     a.PolicyCode = b.PolicyCode 
			and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
			and     interaction_type = 'sent' 
			and     MessageType  in ( 'EMAIL', 'SMS')
			union
			select  distinct b.PolicyCode 
			from    dlk.EXT_XtremePushResults_Policy a, stg.VanRenewalsJuly b 
			where   campaign_name like '%Van%' 
			and     campaign_name like '%Lapsed%' 
			and     a.PolicyCode = b.PolicyCode 
			and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
			and     interaction_type = 'sent' 
			and     MessageType  in ( 'EMAIL', 'SMS')
		)


# In[ ]:

-- HTML cell 98   kind: count query
-- step ids: R3.B1.O1
-- header: Van	Renewal	R3.B1.O1

select	count(distinct PolicyCode) 
from	stg.VanRenewalsJuly
Where	(	
			TYReportingSaleDate is null 
			) 
and     PolicyOfferNum > 0 
and 	PolicyCode IN 
		(
			select  distinct b.PolicyCode
			from    dlk.EXT_XtremePushResults a, stg.VanRenewalsJuly b 
			where   campaign_name like '%Van%' 
			and     campaign_name like '%Lapsed%' 
			and     a.PolicyCode = b.PolicyCode 
			and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
			and     interaction_type = 'sent' 
			and     MessageType  in ( 'EMAIL', 'SMS')
			union
			select  distinct b.PolicyCode 
			from    dlk.EXT_XtremePushResults_Policy a, stg.VanRenewalsJuly b 
			where   campaign_name like '%Van%' 
			and     campaign_name like '%Lapsed%' 
			and     a.PolicyCode = b.PolicyCode 
			and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
			and     interaction_type = 'sent' 
			and     MessageType  in ( 'EMAIL', 'SMS')
		)


# In[ ]:

-- HTML cell 99   kind: count query
-- step ids: VR4.B2.2
-- header: Van	Renewal	VR4.B2.2

select	count(distinct PolicyCode) 
 from    (
            select  distinct b.PolicyCode
            from    stg.VanRenewalsJuly a, dlk.MyChill_NewUploadDocumentEvents  b 
            Where   a.PolicyCode = b.PolicyCode
            and     `Timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
            UNION
            select  distinct b.PolicyCode
            from    stg.VanRenewalsJuly a, dlk.MyChill_NewUploadDocumentEvents  b 
            Where   a.TyPolicyCode = b.PolicyCode
            and     `Timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
        );


# In[ ]:

-- HTML cell 100   kind: note or select
-- step ids: VR4.B2.4
-- header: Van	Renewal	VR4.B2.4

 select counts, count(distinct PolicyCode) from 
		(select  
				PolicyCode , min(CreateDate) FirstDate, max(CreateDate) LastDate, count(*) counts 
		from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
		Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-05-01' and '2026-07-31' 
		and PolicyType = 'Renewals' 
		and PolicyTypeGroup = 'Van' 
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
		Group by PolicyCode) x 
Group by counts 		
Order by 1 
		-- counting guys who were sent at least once


# In[ ]:

-- HTML cell 101   kind: count query
-- step ids: VR4.B2.3
-- header: Van	Renewal	VR4.B2.3

select	count(distinct PolicyCode) 
 from    (
            select  distinct b.PolicyCode
            from    stg.VanRenewalsJuly a, dlk.MyChillWorkflow_DocumentStatus  b 
            Where   a.PolicyCode = b.PolicyCode
            and     `Timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
            UNION
            select  distinct b.PolicyCode
            from    stg.VanRenewalsJuly a, dlk.MyChillWorkflow_DocumentStatus  b 
            Where   a.TyPolicyCode = b.PolicyCode
            and     `Timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
        );
 /* group by isAccepted too */


# In[ ]:

-- HTML cell 102   kind: count query
-- step ids: VR4.B2.O1
-- header: Van	Renewal	VR4.B2.O1

select  count(distinct b.PolicyCode)
from    ods.eventstream a, stg.VanRenewalsJuly b  
Where   a.SourcePolicyReference = b.TyPolicyCode /* new policy */ 
and     PolicyRetNum = 1 
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
and     EventDescription like '%CXL%'
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        ) 
and     TyPolicyCode  in 
                (select  
                        PolicyCode 
                from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
                Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-05-01' and '2026-07-31' 
                and PolicyType = 'Renewals' 
                and PolicyTypeGroup = 'Van' 
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
                )


# In[ ]:

-- HTML cell 103   kind: note or select
-- step ids: VR6.B1.1
-- header: Van	Renewal	VR6.B1.1

select  EventDescription, count(distinct b.PolicyCode)
from    ods.eventstream a, stg.VanRenewalsJuly b  
Where   a.SourcePolicyReference = b.TyPolicyCode /* new policy */ 
and     PolicyRetNum = 1 
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        ) 
and     EventDescription not like 'Renewal Offer%'
and     EventDescription not like 'Document Chase%'
Group by EventDescription
Order by 2 desc


# In[ ]:

-- HTML cell 104   kind: note or select
-- step ids: VR6.B1.1
-- header: Van	Renewal	VR6.B1.1

select  EventDescription, count(distinct b.PolicyCode)
from    ods.eventstream a, stg.VanRenewalsJuly b  
Where   a.SourcePolicyReference = b.TyPolicyCode /* new policy */ 
and     PolicyRetNum = 1 
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
/*and     EventDescription like '%CXL%'
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        ) */
Group by EventDescription
Order by 2 desc


# In[ ]:

-- HTML cell 105   kind: note or select
-- step ids: none in header
select  OriginatingDirection , 
        case when ANI like '%anonymous%' then 'anonymous' else 'normal' end, 
        count(*) from (
select DISTINCT replace(ani, 'tel:+', '' ) ANI, conversationstarttime , OriginatingDirection 
from dlk.genesys_session_summary 
where conversationstarttime between '2026-07-01 00:00:00.000' 
and '2026-08-01 00:00:00.000' 
and queuename = 'INBOUND_SALES_MOTOR') x group by OriginatingDirection , case when ANI like '%anonymous%' then 'anonymous' else 'normal' end  
ORder by 1


# In[ ]:

-- HTML cell 106   kind: staging build
-- step ids: none in header
Create or Replace Table stg.MarieJulyGenesysReconciliation as 
select DISTINCT replace(ani, 'tel:+', '' ) ANI, conversationstarttime , OriginatingDirection 
from dlk.genesys_session_summary 
where conversationstarttime between '2026-07-01 00:00:00.000' 
and '2026-08-01 00:00:00.000' 
and queuename = 'INBOUND_SALES_MOTOR'


# In[ ]:

-- HTML cell 107   kind: note or select
-- step ids: none in header
select  OriginatingDirection , 
        case when ANI like '%anonymous%' then 'anonymous' else 'normal' end, 
        count(*) 
from    stg.MarieJulyGenesysReconciliation x 
group by OriginatingDirection , case when ANI like '%anonymous%' then 'anonymous' else 'normal' end  
ORder by 1

