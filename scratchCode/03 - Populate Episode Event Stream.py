#!/usr/bin/env python
# coding: utf-8

# ## 03 - Populate Episode Event Stream
# 
# null

# In[ ]:


-- reate the event stream table
Create or Replace Table ods.EpisodeEventStream 
(
    EventId                    BIGINT,
    EventSourceId              INT,
    EventSourceReference       VARCHAR(128),
    SourceQuoteReference       VARCHAR(128),
    SourcePolicyReference      VARCHAR(128),
    SourceCustomerReference    VARCHAR(128),
    SourceSystemId             INT,
    PolicyTypeGroup            VARCHAR(50),
    EventDateTime              Timestamp,
    EventDate                  DATE,
    EventTypeId                VARCHAR(10),
    EventDescription           VARCHAR(1024),
    Grain                      VARCHAR(50)
);


# In[ ]:


--Add start and end date variables here
-- The run window and the snapshot date for this build. Every query in the notebook reads its dates
-- from here rather than carrying a literal.
Create or Replace Table stg.episodeeventstream_buildconfig
(
    startTime       timestamp,
    endTime         timestamp,
    effectiveDate   timestamp
)
;

insert into stg.episodeeventstream_buildconfig
values
(
    '2026-07-01', '2026-08-01', '2026-07-31'
)
;

# Derived Data

# In[ ]:


Create or Replace Table stg.A0_genesys_derived_data as 
select  conversationId, 
        case 
            when originatingDirection = 'inbound' then replace(ani,'tel:+353', '0') 
            when originatingDirection = 'outbound' then replace(dnis,'tel:+353', '0') 
            else null 
        end as CustomerPhoneNumber,
        originatingDirection,          
        conversationStartTime,
        conversationEndTime,
        sessionCount,
        sessionIndex,
        sessionDuration,
        sessionStartTime,
        sessionEndTime,
        queueName,
        purpose,
        transferToId,
        agentAnswered, 
        alertNoAnswer, 
        abandoned, 
        totalAcdWaitDuration, 
        totalAgentAlertDuration, 
        totalAgentHoldDuration, 
        totalAgentTalkDuration
from    dlk.genesys_session_summary
Where	conversationStartTime >= (select startTime from stg.episodeeventstream_buildconfig) and conversationStartTime < (select endTime   from stg.episodeeventstream_buildconfig) 
("")


# In[ ]:


Create or Replace Table stg.A0_genesys_derived_data_filtered as 
select	a.ConversationId, CustomerPhoneNumber,a.sessionIndex,A.conversationStartTime
from	stg.A0_genesys_derived_data	a,
		(select	ConversationId, max(sessionIndex) sessionIndex
		from	stg.A0_genesys_derived_data
		Where	queueName is not null 
		and		originatingDirection = 'inbound'
		Group by ConversationId
		)	b 
where	a.ConversationId = b.ConversationId
and		a.sessionIndex = b.sessionIndex
and		queueName = 'INBOUND_SALES_MOTOR'
("")


# In[ ]:


Create or Replace table stg.A1_MotorAcquisitionQuoteInitiated as 
select  QuoteQueryGuid, 
        max(RetrieveSessionToken) RetrieveSessionToken,
        min(case when StepId = 1 then CreatedDateTime else null end) Step1DateTime,
        max(case when StepId in (2,3,4,5) then StepId else null end) Step2To5,
        min(case when StepId in (2,3,4) then CreatedDateTime else null end) FirstStep2to4DateTime,
        min(case when StepId = 5 then CreatedDateTime else null end) FirstStep5DateTime,
        max(case when StepId = 5 then CreatedDateTime else null end) LastStep5DateTime, 
        max(BrokerId) BrokerId
from    dlk.mfq_quotequery 
Where   CreatedDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and CreatedDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
Group by QuoteQueryGuid
("")


# In[ ]:


Create or Replace Table stg.A0_mfq_derived_data as 
SELECT distinct
    contactmobile,
    QuoteQueryGuid
from
    dlk.mfq_quotequery
Where   CreatedDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and CreatedDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
("")


# In[ ]:


Create or Replace table stg.A0_MFQ_genesys_link as 
select  ConversationId,SessionIndex, min(QuoteQueryGuid) ChillSourceQuoteReference
from    stg.A0_genesys_derived_data_filtered a left join stg.A0_mfq_derived_data b
        on a.CustomerPhoneNumber = b.contactmobile
where   b.contactmobile is null
Group by ConversationId,SessionIndex
("")


# In[ ]:


Create or Replace Table stg.A0F1_genesys_inbound_call_duration_summary as 
select	a.ConversationId, min(conversationStartTime) as conversationStartTime, 
            sum(agentAnswered) as agentAnswered, sum(alertNoAnswer) alertNoAnswer, sum(abandoned) abandoned, 
            sum(totalAcdWaitDuration) CallWaitTime, sum(totalAgentAlertDuration) CallRingTime, sum(totalAgentHoldDuration) CallHoldTime, sum(totalAgentTalkDuration) CallSpokenTime
from	stg.A0_genesys_derived_data	a
where	a.queueName = 'INBOUND_SALES_MOTOR'  
Group by ConversationId
("")


# In[ ]:


Create or Replace table stg.AX_MFQ_genesys_link as 
select  ConversationId,SessionIndex, min(QuoteQueryGuid) ChillSourceQuoteReference
from    stg.A0_genesys_derived_data_filtered a,stg.A0_mfq_derived_data b
Where   replace(a.CustomerPhoneNumber,'tel:+353','0') = replace(b.contactmobile,'tel:+353','0')
Group by ConversationId,SessionIndex
("")


# In[ ]:


Create or Replace Table stg.MFQInsurersQuoted as 
 WITH base AS (
      SELECT
          qq.QuoteQueryId,
          qq.QuoteQueryGuid,
          qq.CreatedDateTime,
          qq.CoverCode,
          qq.NCDClaimedBonusProtectionType,
          qq.ServiceCallId,
          qr.QuoteResponseId,
          qs.QuoteSummaryId,
          qs.SchemeName,
          qs.Premium,
          qs.Insurer,
          ROW_NUMBER() OVER (
              PARTITION BY qq.QuoteQueryGuid,
                           qq.NCDClaimedBonusProtectionType,
                           qq.CoverCode,
                           COALESCE(qq.ServiceCallId, '0')
              ORDER BY qq.CreatedDateTime DESC, qq.QuoteQueryId DESC
          ) AS latest_service_call_rn
      FROM dlk.MFQ_QuoteQuery qq
      JOIN dlk.MFQ_QuoteResponses qr
        ON qr.RiskID = qq.QuoteQueryId
      JOIN dlk.MFQ_QuoteSummary qs
        ON qs.QuoteResponseId = qr.QuoteResponseId
      JOIN stg.A1_MotorAcquisitionQuoteInitiated z
        ON qq.QuoteQueryGuid = z.QuoteQueryGuid /* focus on this month's guids */ 
      WHERE qr.TransactionID <> '00000000-0000-0000-0000-000000000000'
  ),
  latest_call AS (
      SELECT *
      FROM base
      WHERE latest_service_call_rn = 1
  ),
  lowest_per_insurer AS (
      SELECT *,
          ROW_NUMBER() OVER (
              PARTITION BY QuoteQueryGuid,
                           NCDClaimedBonusProtectionType,
                           CoverCode,
                           COALESCE(ServiceCallId, '0'),
                           Insurer
              ORDER BY Premium
          ) AS insurer_min_premium_rn
      FROM latest_call
      WHERE Premium IS NOT NULL
        AND Premium > 0
        AND SchemeName IS NOT NULL
  ),
  ranked AS (
      SELECT *,
          ROW_NUMBER() OVER (
              PARTITION BY QuoteQueryGuid,
                           NCDClaimedBonusProtectionType,
                           CoverCode,
                           COALESCE(ServiceCallId, '0')
              ORDER BY Premium
          ) AS insurer_rank
      FROM lowest_per_insurer
      WHERE insurer_min_premium_rn = 1
  ),
  rank1 AS (
      SELECT
          QuoteQueryGuid,
          MAX(CASE WHEN insurer_rank = 1 AND CoverCode = '01' AND NCDClaimedBonusProtectionType = 'S' THEN Premium END)
  AS Rank1PremComp,
          MAX(CASE WHEN insurer_rank = 1 AND CoverCode = '02' AND NCDClaimedBonusProtectionType = 'S' THEN Premium END)
  AS Rank1PremTPFT,
          MAX(CASE WHEN insurer_rank = 1 AND CoverCode = '01' AND NCDClaimedBonusProtectionType = 'F' THEN Premium END)
  AS Rank1PremCompNCB,
          MAX(CASE WHEN insurer_rank = 1 AND CoverCode = '02' AND NCDClaimedBonusProtectionType = 'F' THEN Premium END)
  AS Rank1PremTPFTNCB
      FROM ranked
      GROUP BY QuoteQueryGuid
  )
  SELECT
      QuoteQueryGuid,
      CASE
          WHEN COALESCE(Rank1PremComp, 0) <> 0
            OR COALESCE(Rank1PremTPFT, 0) <> 0
            OR COALESCE(Rank1PremCompNCB, 0) <> 0
            OR COALESCE(Rank1PremTPFTNCB, 0) <> 0
          THEN 'Y'
          ELSE 'N'
      END AS InsurersQuoted
  FROM rank1
;


# In[ ]:


Create or Replace Table stg.GlobalPoliciesSold as 
select  PolicyCode, s.Channel, s.ReportingSaleType, s.PolicyTypeGroup, QuoteQueryGuid, HEQReference, ReportingSaleDate 
from    edw.tbl_fact_policy_sales    s 
WHERE   s.EffectiveDate = (select effectiveDate from stg.episodeeventstream_buildconfig)
  AND   s.ReportingSaleCategory = 'Cat A1: Active Sale'
  AND   s.OrgID = 1
  AND   s.SaleCount = 1
("")


# In[ ]:


Create or Replace Table stg.R0_MotorPoliciesEligibleForRenewals as 
select  PolicyCode, LyPolicyRenewDateAdj as RenewalDate, TyPolicyCode , TyPolicyRenewDateAdj
from    edw.tbl_fact_policy_renewals    a 
Where   a. LyPolicyTypeGroup = 'Motor' 
and     a.LYPolicyRenewDateAdj >= (select startTime from stg.episodeeventstream_buildconfig) and a.LYPolicyRenewDateAdj < (select endTime   from stg.episodeeventstream_buildconfig) 
and     PolicyOfferNum = 1 
Group by   PolicyCode, LyPolicyRenewDateAdj, TyPolicyCode  , TyPolicyRenewDateAdj

Create or Replace Table stg.R0_VanPoliciesEligibleForRenewals as 
select  PolicyCode, LyPolicyRenewDateAdj as RenewalDate, TyPolicyCode , TyPolicyRenewDateAdj
from    edw.tbl_fact_policy_renewals    a 
Where   a. LyPolicyTypeGroup = 'Van' 
and     a.LYPolicyRenewDateAdj >= (select startTime from stg.episodeeventstream_buildconfig) and a.LYPolicyRenewDateAdj < (select endTime   from stg.episodeeventstream_buildconfig) 
and     PolicyOfferNum = 1 
Group by   PolicyCode, LyPolicyRenewDateAdj, TyPolicyCode  , TyPolicyRenewDateAdj

Create or Replace Table stg.R0_HomePoliciesEligibleForRenewals as 
select  PolicyCode, LyPolicyRenewDateAdj as RenewalDate, TyPolicyCode , TyPolicyRenewDateAdj
from    edw.tbl_fact_policy_renewals    a 
Where   a. LyPolicyTypeGroup = 'Home' 
and     a.LYPolicyRenewDateAdj >= (select startTime from stg.episodeeventstream_buildconfig) and a.LYPolicyRenewDateAdj < (select endTime   from stg.episodeeventstream_buildconfig) 
and     PolicyOfferNum = 1 
Group by   PolicyCode, LyPolicyRenewDateAdj, TyPolicyCode  , TyPolicyRenewDateAdj
("")


# In[ ]:


create or Replace table stg.CDAPurchasePolicyList as 
select  trim(PolicyNumber) PolicyCode , max(UTCDateUpdated) SentDate
from    dlk.SQL07CDA_Messages
where	RenderedMessage like 'Hi, thanks for choosing us, we really appreciate it.%be sending out your welcome pack shortly. Thanks, Chill Insurance.' 
and		UTCDateAdded >= (select startTime from stg.episodeeventstream_buildconfig) and UTCDateAdded < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ProviderResponse = 'Delivered'
Group by trim(PolicyNumber)
("")


# In[ ]:


Create or Replace Table stg.R1_Motor_Renewals_EmailOffered as 
select  SourcePolicyReference, min(EventDateTime) OfferedDateTime
from    ods.EventStream                             a, 
        stg.R0_MotorPoliciesEligibleForRenewals     b 
Where   EventDescription like 'Renewal Offer - Emailed Document %'
and     a.PolicyTypeGroup = 'Motor'
and     a.SourcePolicyReference = b.PolicyCode 
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000' 
Group by SourcePolicyReference
("")


# In[ ]:


Create or Replace Table stg.MotorRenewalsOnline as 
select  distinct PolicyCode, SalesSource,RenewalStartDate
from   (select  PolicyCode, 1 SalesSource,RenewalStartDate
        from    (
                    select  left(PolicyCode,6) as ClientCode, dateadd(day, -60, RenewalDate) RenewalStartDate, PolicyCode, dateadd(day, 40, RenewalDate) RenewalEndDate
                    from stg.R0_MotorPoliciesEligibleForRenewals 
                )   a,
                dlk.AppliedRenewals_PaymentSuccess b 
        Where   PolicyCode = PolicyCodeForRenewal
        and     b.`Timestamp` > a.RenewalStartDate
        and     b.`Timestamp` < a.RenewalEndDate
        union all 
        select  PolicyCodeForRenewal, 2 ,RenewalStartDate
        from    (
                    select  left(PolicyCode,6) as ClientCode, dateadd(day, -60, RenewalDate) RenewalStartDate, PolicyCode, dateadd(day, 40, RenewalDate) RenewalEndDate
                    from stg.R0_MotorPoliciesEligibleForRenewals 
                )   a,
                dlk.AppliedRenewals_PaymentSuccess b 
        Where   ClientCode = left(PolicyCodeForRenewal,6)
        and     PolicyCode <> PolicyCodeForRenewal
        and     b.`Timestamp` > a.RenewalStartDate
        and     b.`Timestamp` < a.RenewalEndDate
        union all
        select  PolicyCode, 3 , a.PaymentDate
        from    stg.MFQ_Quote_Payments a, stg.RenewalsDoingMFQ  b 
        Where   a.QuotequeryGuId = b.MFQQuotequeryGuId and PaymentType in (0,5)
        ) x
;


# In[ ]:


Create or Replace Table stg.R0_genesys_derived_data as 
select  conversationId, 
        case 
            when originatingDirection = 'inbound' then replace(ani,'tel:+353', '0') 
            when originatingDirection = 'outbound' then replace(dnis,'tel:+353', '0') 
            else null 
        end as CustomerPhoneNumber,
        originatingDirection,          
        conversationStartTime,
        conversationEndTime,
        sessionCount,
        sessionIndex,
        sessionDuration,
        sessionStartTime,
        sessionEndTime,
        queueName,
        purpose,
        transferToId,
        agentAnswered, 
        alertNoAnswer, 
        abandoned, 
        totalAcdWaitDuration, 
        totalAgentAlertDuration, 
        totalAgentHoldDuration, 
        totalAgentTalkDuration
from    dlk.genesys_session_summary
Where	conversationStartTime >= (select startTime from stg.episodeeventstream_buildconfig) and conversationStartTime < (select endTime   from stg.episodeeventstream_buildconfig) 
("")


# In[ ]:


create or Replace table stg.R2B1_3_base as 
select a.* from stg.R2B1_1_Base a, stg.MFQInsurersQuoted   b  Where a.MFQQuoteQueryGuid = b.QuoteQueryGuid and InsurersQuoted = 'Y' ;


# In[ ]:


Create or Replace Table stg.R2B1_4_F1_MFQPrices as 
select  a.*, Rank1PremComp
from    stg.R2B1_3_base     a,
        edw.tbl_fact_mfq    b  
Where   a.MFQQuoteQueryGuid = b.QuoteQueryGuid 
("")

# In[ ]:

Create or Replace Table stg.VR0_VanPoliciesEligibleForRenewals as 
select  PolicyCode, LyPolicyRenewDateAdj as RenewalDate, TyPolicyCode , TyPolicyRenewDateAdj
from    edw.tbl_fact_policy_renewals    a 
Where   a. LyPolicyTypeGroup = 'Van' 
and     a.LYPolicyRenewDateAdj >= (select startTime from stg.episodeeventstream_buildconfig) and a.LYPolicyRenewDateAdj < (select endTime   from stg.episodeeventstream_buildconfig) 
and     PolicyOfferNum = 1 
Group by   PolicyCode, LyPolicyRenewDateAdj, TyPolicyCode  , TyPolicyRenewDateAdj


Create or Replace Table stg.MotorMTAPolicies as 
select  distinct SourcePolicyReference
from    ods.EventStream Where EventSourceId = 3 and EventDescription like 'Permanent%' and PolicyTypeGroup = 'Motor' 
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)

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
    AND NA.ar_posting_date >= cast(date_format((select startTime from stg.episodeeventstream_buildconfig), 'yyyyMMdd') as int)
    AND NA.ar_posting_date < cast(date_format((select endTime   from stg.episodeeventstream_buildconfig), 'yyyyMMdd') as int)
    AND pt.PremiumTypeGroup = 'MTA'
;

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
where   EffectiveDate = (select effectiveDate from stg.episodeeventstream_buildconfig)
Order by 1 


# Derived Data - staging tables moved out of the step cells

# In[ ]:


-- stg.R3B1_LapsedThisYearPolicy. Read by step R3.O1 and any step downstream of it.
Create or Replace Table stg.R3B1_LapsedThisYearPolicy as
select  distinct b.PolicyCode , b.RenewalDate
from    dlk.rbsdata2_policy_physical a,
        stg.R0_MotorPoliciesEligibleForRenewals b
Where   trim(a.pl_code) = trim(b.PolicyCode)  -- trim is important as the source tables have trailing spaces
and     trim(a.pl_status) = 'L'
;


# In[ ]:


-- stg.HA1_HFQ_Quotes. Read by step HA1 and any step downstream of it.
Create Or Replace Table stg.HA1_HFQ_Quotes as
SELECT  *
FROM    (SELECT  *,
                CAST(from_unixtime(_ts) AS TIMESTAMP) as ts_unix,
                ROW_NUMBER() OVER(PARTITION BY QuoteCodeReference, RetrieveCount order by _ts desc) AS RN,
                COUNT(*)     OVER (PARTITION BY QuoteCodeReference, RetrieveCount) AS MaxRN
        FROM    dlk.HFQ_QuoteDetails_Snapshot_v2) a
where   RN = 1
and     ts_unix >= (select startTime from stg.episodeeventstream_buildconfig) and ts_unix < (select endTime   from stg.episodeeventstream_buildconfig)
;


# In[ ]:


-- stg.HA0_genesys_derived_data_filtered. Read by step HA0 and any step downstream of it.
Create or Replace Table stg.HA0_genesys_derived_data_filtered as
select	a.ConversationId, a.CustomerPhoneNumber, a.sessionIndex, a.conversationStartTime
from	stg.A0_genesys_derived_data	a,
        (select	ConversationId, max(sessionIndex) sessionIndex
        from	stg.A0_genesys_derived_data
        Where	queueName is not null
        and		originatingDirection = 'inbound'
        Group by ConversationId
        )	b
where	a.ConversationId = b.ConversationId
and		a.sessionIndex = b.sessionIndex
and		a.queueName = 'INBOUND_SALES_HOME'
;


# In[ ]:


-- stg.HA0F1_genesys_inbound_call_duration_summary. Read by step HA0.F1 and any step downstream of it.
Create or Replace Table stg.HA0F1_genesys_inbound_call_duration_summary as
select	a.ConversationId, min(a.conversationStartTime) as conversationStartTime,
        sum(a.agentAnswered) as agentAnswered, sum(a.alertNoAnswer) alertNoAnswer, sum(a.abandoned) abandoned,
        sum(a.totalAcdWaitDuration) CallWaitTime, sum(a.totalAgentAlertDuration) CallRingTime,
        sum(a.totalAgentHoldDuration) CallHoldTime, sum(a.totalAgentTalkDuration) CallSpokenTime
from	stg.A0_genesys_derived_data	a
where	a.queueName = 'INBOUND_SALES_HOME'
Group by a.ConversationId
;


# In[ ]:


-- stg.HR1a_Home_Renewals_EmailOffered. Read by step HR1a and any step downstream of it.
Create or Replace Table stg.HR1a_Home_Renewals_EmailOffered as
select  SourcePolicyReference, min(EventDateTime) OfferedDateTime
from    ods.EventStream                             a,
        stg.R0_HomePoliciesEligibleForRenewals     b
Where   EventDescription like 'Renewal Offer - Emailed Document %'
and     a.PolicyTypeGroup = 'Home'
and     a.SourcePolicyReference = b.PolicyCode
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
Group by SourcePolicyReference
;


# In[ ]:


-- stg.HR1b_Home_Renewals_PostOffered. Read by step HR1b and any step downstream of it.
Create or Replace Table stg.HR1b_Home_Renewals_PostOffered as
select  SourcePolicyReference, min(EventDateTime) OfferedDateTime
from    ods.EventStream a, stg.R0_HomePoliciesEligibleForRenewals b
Where   EventDescription like 'Renewal Offer - Document Transmitted %'
and     a.PolicyTypeGroup = 'Home'
and     a.SourcePolicyReference = b.PolicyCode
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
Group by SourcePolicyReference
;


# In[ ]:


-- stg.HomeRenewalScvCustomerKeys. Read by step HR2.B1 and any step downstream of it.
Create or Replace Table stg.HomeRenewalScvCustomerKeys as
select  distinct scv_customer_key , PolicyCode, ClientCode
from    ods.scv_customer_key  a, (select PolicyCode, left(PolicyCode,6) as ClientCode from stg.R0_HomePoliciesEligibleForRenewals) b
Where   a.SourceSystemReference = b.ClientCode
and     a.SourceSystemId = 1
;


# In[ ]:


-- stg.HomeRenewalsDoingHFQ. Read by step HR2.B1 and any step downstream of it.
Create or Replace Table stg.HomeRenewalsDoingHFQ as
select  distinct a.scv_customer_key, a.PolicyCode, b.QuoteCodeReference, ts_unix as QuoteStartDateTime
from    stg.HomeRenewalScvCustomerKeys a, stg.HFQ_Quotes b, ods.scv_customer_key c
Where   a.scv_customer_key = c.scv_customer_key
and     b.QuoteCodeReference = c.SourceSystemReference
and     ts_unix between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
and     SourceSystemId = 3
;


# In[ ]:


-- stg.HR3B1_LapsedThisYearPolicy. Read by step HR3.B1 and any step downstream of it.
Create or Replace Table stg.HR3B1_LapsedThisYearPolicy as
select  distinct b.PolicyCode , b.RenewalDate
from    dlk.rbsdata2_policy_physical a,
        stg.R0_HomePoliciesEligibleForRenewals b
Where   trim(a.pl_code) = trim(b.PolicyCode)  -- trim is important as the source tables have trailing spaces
and     trim(a.pl_status) = 'L'
;


# In[ ]:


-- stg.HR4_HomeRenewalsOnlinePayments. Read by step HR4a and any step downstream of it.
Create or Replace Table stg.HR4_HomeRenewalsOnlinePayments as
select  ClientCode, PolicyCode, max(`Timestamp`) PaymentDateTime
from    (
            select  left(PolicyCode,6) as ClientCode, dateadd(day, -60, RenewalDate) RenewalStartDate, PolicyCode, dateadd(day, 40, RenewalDate) RenewalEndDate
            from stg.R0_HomePoliciesEligibleForRenewals
        )   a,
        dlk.AppliedRenewals_PaymentSuccess b
Where   a.ClientCode = b.PortfolioCode
and     b.`Timestamp` > a.RenewalStartDate
and     b.`Timestamp` < a.RenewalEndDate
Group by ClientCode, PolicyCode
;


# In[ ]:


-- stg.HR2B1_1_Base. Read by step HR2.B1.1 and any step downstream of it.
Create or Replace Table stg.HR2B1_1_Base as
SELECT  distinct b.PolicyCode, b.QuoteCodeReference, b.QuoteStartDatetime , RenEURPremOffer, TYEURGrossPremium, PolicyRetNum
FROM    stg.HomeRenewalsDoingHFQ                b,
        stg.R0_HomePoliciesEligibleForRenewals  c,
        edw.tbl_fact_policy_renewals d
Where   b.PolicyCode = c.PolicyCode
and     b.policycode = d.policycode
and     b.QuoteStartDateTime > add_months((select startTime from stg.episodeeventstream_buildconfig), -1)
;


# In[ ]:


-- stg.AbandonedHomeMTACalls. Read by step HM1.F1 and any step downstream of it.
Create or Replace Table stg.AbandonedHomeMTACalls as 
select distinct ConversationId
from 
(select	a.ConversationId, min(conversationStartTime) as conversationStartTime, 
            sum(agentAnswered) as agentAnswered, sum(alertNoAnswer) alertNoAnswer, sum(abandoned) abandoned, 
            sum(totalAcdWaitDuration) CallWaitTime, sum(totalAgentAlertDuration) CallRingTime, sum(totalAgentHoldDuration) CallHoldTime, sum(totalAgentTalkDuration) CallSpokenTime
from	stg.A0_genesys_derived_data	a
where	a.queueName in ('INBOUND_HomeChangeOther',
'INBOUND_HomeChangeBuildCost')
and abandoned = 1 and totalAcdWaitDuration > 0 
Group by ConversationId) x
;


# In[ ]:


-- stg.JulyHomeCancellations. Read by step HC1a and any step downstream of it.
Create or Replace Table stg.JulyHomeCancellations as
select  distinct PolicyStatusDesc,  ShortDescription, PolicyCode, ClientCode
from    edw.tbl_fact_policy_mtc
Where   PolicyTypeGroup = 'Home'
and     EffectiveDate = (select effectiveDate from stg.episodeeventstream_buildconfig)
;


# In[ ]:


-- stg.JulyMotorCancellations. Read by step HC1a and any step downstream of it.
Create or Replace Table stg.JulyMotorCancellations as
select  distinct PolicyStatusDesc,  ShortDescription, PolicyCode, ClientCode
from    edw.tbl_fact_policy_mtc
Where   PolicyTypeGroup = 'Motor'
and     EffectiveDate = (select effectiveDate from stg.episodeeventstream_buildconfig)
;


# In[ ]:


-- stg.JulyVanCancellations. Read by step HC1a and any step downstream of it.
Create or Replace Table stg.JulyVanCancellations as
select  distinct PolicyStatusDesc,  ShortDescription, PolicyCode, ClientCode
from    edw.tbl_fact_policy_mtc
Where   PolicyTypeGroup = 'Van'
and     EffectiveDate = (select effectiveDate from stg.episodeeventstream_buildconfig)
;


# In[ ]:


-- stg.AbandonedMTACalls. Read by step M1.F1 and any step downstream of it.
Create or Replace Table stg.AbandonedMTACalls as 
select distinct ConversationId
from 
(select	a.ConversationId, min(conversationStartTime) as conversationStartTime, 
            sum(agentAnswered) as agentAnswered, sum(alertNoAnswer) alertNoAnswer, sum(abandoned) abandoned, 
            sum(totalAcdWaitDuration) CallWaitTime, sum(totalAgentAlertDuration) CallRingTime, sum(totalAgentHoldDuration) CallHoldTime, sum(totalAgentTalkDuration) CallSpokenTime
from	stg.A0_genesys_derived_data	a
where	a.queueName in ('INBOUND_VehicleChangeAddress',
'INBOUND_VehicleChangeOther',
'INBOUND_VehicleChange_Perm',
'INBOUND_VehicleChange_Temp',
'INBOUND_VehicleUpdateLicence',
'INBOUND_Vehicle_Add_Driver')
and abandoned = 1 and totalAcdWaitDuration > 0 
Group by ConversationId) x
;


# In[ ]:


-- stg.MotorEscalated20days. Read by step C4 and any step downstream of it.
Create or replace table stg.MotorEscalated20days as 
select  
		distinct PolicyCode 
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig) 
and PolicyType = 'New Business' 
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
and Campaign = 'DAY 20'
;


# In[ ]:


-- stg.VanRenewals. Read by step VR1a and any step downstream of it.
Create or Replace Table stg.VanRenewals as 
select  PolicyCode, TYPolicyCode, LYPolicyRenewDateAdj, LYEURGrossPremium, LYEURCommission,	LYEURFees, RenEURPremInvite,	RenEURPremAlternative, RenEURFee, PolicyOfferNum, PolicyRetNum, TYReportingSaleType,	TYReportingSaleCategory,	TYReportingSaleDate,
TYEURGrossPremium,	TYEURCommission,	TYEURFees, Channel, RenewalsPortal,	SuccessfulLoginCount,FailedLoginCount, SuccessfulPaymentCount, FailedPaymentCount, DiaryPaymentTypeTY, PolicyCodeRevisedAtOffer
from    edw.tbl_fact_policy_renewals
where   RenewalMonth = '2026-07-31' 
and     LYPolicyTypeGroup = 'Van' 
Group by PolicyCode, TYPolicyCode, LYPolicyRenewDateAdj, LYEURGrossPremium, LYEURCommission,	LYEURFees, RenEURPremInvite,	RenEURPremAlternative, RenEURFee, PolicyOfferNum, PolicyRetNum, TYReportingSaleType,	TYReportingSaleCategory,	TYReportingSaleDate,
TYEURGrossPremium,	TYEURCommission,	TYEURFees, Channel, RenewalsPortal,	SuccessfulLoginCount,FailedLoginCount, SuccessfulPaymentCount, FailedPaymentCount, DiaryPaymentTypeTY, PolicyCodeRevisedAtOffer
;


# In[ ]:


-- stg.Van_genesys_inbound_call_duration_summary. Read by step VA0.F1 and any step downstream of it.
Create or Replace Table stg.Van_genesys_inbound_call_duration_summary as 
select	a.ConversationId, min(conversationStartTime) as conversationStartTime, 
            sum(agentAnswered) as agentAnswered, sum(alertNoAnswer) alertNoAnswer, sum(abandoned) abandoned, 
            sum(totalAcdWaitDuration) CallWaitTime, sum(totalAgentAlertDuration) CallRingTime, sum(totalAgentHoldDuration) CallHoldTime, sum(totalAgentTalkDuration) CallSpokenTime
from	stg.A0_genesys_derived_data	a
where	a.queueName = 'INBOUND_SALES_VAN'  
Group by ConversationId
;


# In[ ]:


-- stg.Van_genesys_derived_data_filtered. Read by step VA0 and any step downstream of it.
Create or Replace Table stg.Van_genesys_derived_data_filtered as 
select	a.ConversationId, CustomerPhoneNumber,a.sessionIndex,A.conversationStartTime
from	stg.A0_genesys_derived_data	a, /* built in Motor acq - but do not use across notebooks or structure the deps */ 
		(select	ConversationId, max(sessionIndex) sessionIndex
		from	stg.A0_genesys_derived_data
		Where	queueName is not null 
		and		originatingDirection = 'inbound'
		Group by ConversationId
		)	b 
where	a.ConversationId = b.ConversationId
and		a.sessionIndex = b.sessionIndex
and		queueName = 'INBOUND_SALES_VAN'
;


# In[ ]:


-- stg.VanSales. Read by step VA5 and any step downstream of it.
Create or Replace Table stg.VanSales as 
select  PolicyCode, PolicyStatusDesc, Channel, FinanceFlag, RenewalTransferFlag, EURGrossPremium, EURFees, ReportingSaleCategory, ReportingSaleType, ReportingSalesDate
from    edw.tbl_fact_policy_sales 
where   EffectiveDate = (select effectiveDate from stg.episodeeventstream_buildconfig) 
and     PolicyTypeGroup = 'Van' 
and     ReportingSaleCategory = 'Cat A1: Active Sale'
and     PolicyCloseNum = 1 
Group by PolicyCode, PolicyStatusDesc, Channel, FinanceFlag, RenewalTransferFlag, EURGrossPremium, EURFees , ReportingSaleCategory, ReportingSaleType, ReportingSalesDate
;


# In[ ]:


-- stg.TravelQuotes. Read by step TA1p and any step downstream of it.
Create or Replace table stg.TravelQuotes as
select	quote_number, 'Q' as SourceType , travel_certificatestatus, travel_purchaseDate, case when business_type = 'Renewal' then 1 else 0 end RenewalFlag
FROM dlk.EXT_Travel_Quotes 
    WHERE Travel_QuoteDate >= (select startTime from stg.episodeeventstream_buildconfig) and Travel_QuoteDate < (select endTime   from stg.episodeeventstream_buildconfig) 
	     AND rtrim(ltrim(travel_certificatestatus)) IN ('Completed Quote','Incomplete Quote','Cancelled')   and len(email)>0
Group by quote_number, travel_certificatestatus, travel_purchaseDate, case when business_type = 'Renewal' then 1 else 0 end 
union all 
select p.QuoteId, 'P' , RecordType , p.PurchaseDate, RenewalFlag
FROM dlk.EXT_Travel_policy p
	left join dlk.EXT_Travel_Quotes  q on p.QuoteId = q.quote_number 
WHERE p.PurchaseDate >= (select startTime from stg.episodeeventstream_buildconfig) and p.PurchaseDate < (select endTime   from stg.episodeeventstream_buildconfig)	
and	  q.quote_number is null 	
Group by p.QuoteId , RecordType ,p.PurchaseDate, RenewalFlag
union all 
select p.QuoteId, 'P' , q.travel_certificatestatus , p.PurchaseDate, RenewalFlag
FROM dlk.EXT_Travel_policy p
	join dlk.EXT_Travel_Quotes  q on p.QuoteId = q.quote_number 
WHERE p.PurchaseDate >= (select startTime from stg.episodeeventstream_buildconfig) and p.PurchaseDate < (select endTime   from stg.episodeeventstream_buildconfig)	
Group by p.QuoteId ,q.travel_certificatestatus , p.PurchaseDate, RenewalFlag
;



# Derived Data - SCV base and call staging, from Gaps II

# In[ ]:


-- stg.SCVBase_01. Part of the SCV build, from Gaps II.
-- SCV Build
CREATE or Replace table stg.SCVBase_01 as 
select	SourceSystemReference, SCV_Customer_Key, ChillSourceCustomerKey, ChillSourceAddressKey, SourceSystemId 
from	ods.scv_customer_key 
where	SourceSystemId = 1
;


# In[ ]:


-- stg.SCVBase_02. Part of the SCV build, from Gaps II.
CREATE or Replace table stg.SCVBase_02 as 
select	QuoteQueryGuid, a.SourceSystemReference, a.SCV_Customer_Key, a.ChillSourceCustomerKey, a.ChillSourceAddressKey, a.SourceSystemId, c.PRN as AdditionalDriverFlag
from	ods.scv_customer_key				a,
		dlk.mfq_quotequery					b,
		dlk.mfq_quotedrivers				c
where	a.SourceSystemId = 2 
and		a.SourceSystemReference = c.QuoteDriverId
and		b.QuoteQueryId = c.QuoteQueryId
Group by QuoteQueryGuid, a.SourceSystemReference, a.SCV_Customer_Key, a.ChillSourceCustomerKey, a.ChillSourceAddressKey, a.SourceSystemId, c.PRN
;


# In[ ]:


-- stg.SCVBase_03. Part of the SCV build, from Gaps II.
CREATE or Replace table stg.SCVBase_03 as 
select	b.QuoteCodeReference, a.SourceSystemReference, a.SCV_Customer_Key, a.ChillSourceCustomerKey, a.ChillSourceAddressKey, a.SourceSystemId,
		case when a.SourceSystemReference like '%:JOINT' then 1 else 0 end as JointCustomerFlag 
from	ods.scv_customer_key				a,
		dlk.hfq_quotedetails				b
where	a.SourceSystemId = 3 
and		replace(a.SourceSystemReference, ':JOINT', '') = b.QuoteCodeReference
Group by b.QuoteCodeReference, a.SourceSystemReference, a.SCV_Customer_Key, a.ChillSourceCustomerKey, a.ChillSourceAddressKey, a.SourceSystemId
;


# In[ ]:


-- stg.SCVBase_04. Part of the SCV build, from Gaps II.
CREATE or Replace table stg.SCVBase_04 as 
select	c.PolicyCode, a.SourceSystemReference, a.SCV_Customer_Key, a.ChillSourceCustomerKey, a.ChillSourceAddressKey, a.SourceSystemId 
from	ods.scv_customer_key				a,
		dlk.ext_home_qs_policyholderdetails	b,
		dlk.ext_home_qs_policydetails		c
where	a.SourceSystemId = 4 
and		a.SourceSystemReference = b.PolicyHolderId
and		b.PolicyId = c.PolicyId
;


# In[ ]:


-- stg.SCVBase_05. Part of the SCV build, from Gaps II.
CREATE or Replace table stg.SCVBase_05 as 
select	QuoteId, PolicyId, a.SourceSystemReference, a.SCV_Customer_Key, a.ChillSourceCustomerKey, a.ChillSourceAddressKey, a.SourceSystemId
from	ods.scv_customer_key				a,
		dlk.ext_travel_policy				b 
where	a.SourceSystemId = 5 
and		a.SourceSystemReference = b.MapfreCustomerId
Group by QuoteId, PolicyId, a.SourceSystemReference, a.SCV_Customer_Key, a.ChillSourceCustomerKey, a.ChillSourceAddressKey, a.SourceSystemId
;


# In[ ]:


-- stg.SCVBase_06. Part of the SCV build, from Gaps II.
CREATE or Replace table stg.SCVBase_06 as 
select	PK_ContactID, a.SourceSystemReference, a.SCV_Customer_Key, a.ChillSourceCustomerKey, a.ChillSourceAddressKey, a.SourceSystemId, case when a.SourceSystemReference like '%:JOINT' then 1 else 0 end as JointCustomerFlag 
from	ods.scv_customer_key				a,
		dlk.life_tblcontacts				b 
where	a.SourceSystemId = 6 
and		replace(a.SourceSystemReference, ':JOINT', '') = b.PK_ContactID
Group by PK_ContactID, a.SourceSystemReference, a.SCV_Customer_Key, a.ChillSourceCustomerKey, a.ChillSourceAddressKey, a.SourceSystemId, case when a.SourceSystemReference like '%:JOINT' then 1 else 0 end
;


# In[ ]:


-- stg.SCVBase_07. Part of the SCV build, from Gaps II.
CREATE or Replace table stg.SCVBase_07 as 
select	RowKey, a.SourceSystemReference, a.SCV_Customer_Key, a.ChillSourceCustomerKey, a.ChillSourceAddressKey, a.SourceSystemId 
from	ods.scv_customer_key				a,
		dlk.vanquotedetails					b
where	a.SourceSystemId = 7 
and		a.SourceSystemReference = b.RowKey
Group by RowKey, a.SourceSystemReference, a.SCV_Customer_Key, a.ChillSourceCustomerKey, a.ChillSourceAddressKey, a.SourceSystemId
;


# In[ ]:


-- stg.SCVBase_08. Part of the SCV build, from Gaps II.
CREATE or Replace table stg.SCVBase_08 as 
select	quote_number, a.SourceSystemReference, a.SCV_Customer_Key, a.ChillSourceCustomerKey, a.ChillSourceAddressKey, a.SourceSystemId , user_id as email
from	ods.scv_customer_key				a,
		dlk.ext_travel_quotes				b
where	a.SourceSystemId = 8 
and		a.SourceSystemReference = b.quote_number
Group by quote_number, a.SourceSystemReference, a.SCV_Customer_Key, a.ChillSourceCustomerKey, a.ChillSourceAddressKey, a.SourceSystemId, user_id
;


# In[ ]:


-- stg.SCVBase_09. Part of the SCV build, from Gaps II.
CREATE or Replace table stg.SCVBase_09 as 
select	Policy_Code, a.SourceSystemReference, a.SCV_Customer_Key, a.ChillSourceCustomerKey, a.ChillSourceAddressKey, a.SourceSystemId 
from	ods.scv_customer_key					a,
		dlk.ext_quotationstorage_policydetails	b
where	a.SourceSystemId = 9 
and		replace(a.SourceSystemReference, ':1', '') = b.Quotation_ID
Group by Policy_Code, a.SourceSystemReference, a.SCV_Customer_Key, a.ChillSourceCustomerKey, a.ChillSourceAddressKey, a.SourceSystemId
;


# In[ ]:


-- ods.SCVBase. Part of the SCV build, from Gaps II.
CREATE or Replace table ods.SCVBase as 
select SCV_Customer_Key, ChillSourceCustomerKey, ChillSourceAddressKey, SourceSystemId, SourceSystemReference, cast(SourceSystemReference as varchar(225)) as ClientCode,cast(null as varchar(225)) as PolicyCode, cast(null  as varchar(225)) as QuoteReference, cast(1 as VARCHAR(10)) AdditionalCustomerFlag  
from stg.SCVBase_01 union
select SCV_Customer_Key, ChillSourceCustomerKey, ChillSourceAddressKey, SourceSystemId, SourceSystemReference, cast(SourceSystemReference as varchar(225)) as ClientCode,cast(null as varchar(225)) as PolicyCode, QuoteQueryGuid as QuoteReference, AdditionalDriverFlag   
from stg.SCVBase_02 union
select SCV_Customer_Key, ChillSourceCustomerKey, ChillSourceAddressKey, SourceSystemId, SourceSystemReference, cast(SourceSystemReference as varchar(225)) as ClientCode,cast(null as varchar(225)) as PolicyCode, QuoteCodeReference, 1    
from stg.SCVBase_03 union
select SCV_Customer_Key, ChillSourceCustomerKey, ChillSourceAddressKey, SourceSystemId, SourceSystemReference, null as ClientCode, PolicyCode, SourceSystemReference as QuoteReference, 1    
from stg.SCVBase_04 union
select SCV_Customer_Key, ChillSourceCustomerKey, ChillSourceAddressKey, SourceSystemId, SourceSystemReference, cast(SourceSystemReference as varchar(225)) as ClientCode, CAST(PolicyId as varchar(225)) as PolicyCode, CAST(QuoteId as varchar(225)) as QuoteReference, CAST(1 AS VARCHAR(10))   
from stg.SCVBase_05 union
select SCV_Customer_Key, ChillSourceCustomerKey, ChillSourceAddressKey, SourceSystemId, SourceSystemReference, cast(PK_ContactID as varchar(225)) as ClientCode,cast(null as varchar(225)) as PolicyCode, cast(null  as varchar(225)) as QuoteReference, CAST(1 + JointCustomerFlag AS VARCHAR(10))   
from stg.SCVBase_06 union
select SCV_Customer_Key, ChillSourceCustomerKey, ChillSourceAddressKey, SourceSystemId, SourceSystemReference, cast(SourceSystemReference as varchar(225)) as ClientCode,cast(null as varchar(225)) as PolicyCode, RowKey as QuoteReference, CAST(1 AS VARCHAR(10))  
from stg.SCVBase_07 union
select SCV_Customer_Key, ChillSourceCustomerKey, ChillSourceAddressKey, SourceSystemId, SourceSystemReference, email as ClientCode,cast(null as varchar(225)) as PolicyCode, cast(quote_number as varchar(225)) as QuoteReference, CAST(1 AS VARCHAR(10)) 
from stg.SCVBase_08 union
select SCV_Customer_Key, ChillSourceCustomerKey, ChillSourceAddressKey, SourceSystemId, SourceSystemReference, left(PolicyCode,6) as ClientCode, cast(Policy_Code as varchar(225)), left(SourceSystemReference, 36) as QuoteReference, CAST(1 AS VARCHAR(10))  
from stg.SCVBase_09
;


# In[ ]:


-- stg.RelayCustomers. Part of the SCV build, from Gaps II.
Create or Replace Table stg.RelayCustomers as 
select	SCV_Customer_Key, ChillSourceCustomerKey, ClientCode
from	ods.scvbase			a 
Where	a.SourceSystemId = 1 
and		len(a.ClientCode) = 6
Group by SCV_Customer_Key, ChillSourceCustomerKey, ClientCode
;


# In[ ]:


-- ods.ScvEadmLink. Part of the SCV build, from Gaps II.
Create or Replace Table ods.ScvEadmLink as 
select	case when b.SCV_Customer_Key < 10000000000000 then coalesce(b.SCV_Customer_Key, a.SCV_Customer_Key) else a.SCV_Customer_Key end as SCV_Customer_Key_Final,
        a.*
from	ods.scvbase			a 
left join 
        stg.RelayCustomers  b 
            on  b.ClientCode = left(a.PolicyCode,6)
            and	a.SourceSystemId in (4,9)
            and	len(a.PolicyCode) = 9
;


# In[ ]:


-- stg.Claims_genesys_derived_data_filtered. Part of inbound claims calls, read by the claim reported steps.
Create or Replace Table stg.Claims_genesys_derived_data_filtered as 
select	a.ConversationId, CustomerPhoneNumber,a.sessionIndex,A.conversationStartTime
from	stg.A0_genesys_derived_data	a
where	queueName = 'INBOUND_Claims'
;


# In[ ]:


-- stg.Van_PhoneNumbers. Part of Van policy phone numbers, read by VCL1a and VD.V1.
Create or Replace Table stg.Van_PhoneNumbers as 
select	PolicyCode, ClientCode, CustomerPhone, RapierCustomerId
FROM	pii.customer_data_assembled a,
        (
            select	ClientCode, PolicyCode
            from	edw.tbl_fact_policy_mvt
            Where	PolicyTypeGroup = 'Van' 
            and		EffectiveDate = (select effectiveDate from stg.episodeeventstream_buildconfig) 
            and		OpenNum = 1 
            Group by ClientCode, PolicyCode
        )   b
Where	SourceSystemCustomerId = ClientCode
and     SourceSystemId = 1 			
;


# In[ ]:


# In[ ]:


-- stg.Home_PhoneNumbers. Part of Home policy phone numbers, built like stg.Van_PhoneNumbers and read by HCL1a.
Create or Replace Table stg.Home_PhoneNumbers as
select	PolicyCode, ClientCode, CustomerPhone, RapierCustomerId
FROM	pii.customer_data_assembled a,
        (
            select	ClientCode, PolicyCode
            from	edw.tbl_fact_policy_mvt
            Where	PolicyTypeGroup = 'Home'
            and		EffectiveDate = (select effectiveDate from stg.episodeeventstream_buildconfig)
            and		OpenNum = 1
            Group by ClientCode, PolicyCode
        )   b
Where	SourceSystemCustomerId = ClientCode
and     SourceSystemId = 1
;


# In[ ]:


-- stg.Motor_PhoneNumbers. Part of Motor policy phone numbers, built like stg.Van_PhoneNumbers and read by CL1a and D.V1.
Create or Replace Table stg.Motor_PhoneNumbers as
select	PolicyCode, ClientCode, CustomerPhone, RapierCustomerId
FROM	pii.customer_data_assembled a,
        (
            select	ClientCode, PolicyCode
            from	edw.tbl_fact_policy_mvt
            Where	PolicyTypeGroup = 'Motor'
            and		EffectiveDate = (select effectiveDate from stg.episodeeventstream_buildconfig)
            and		OpenNum = 1
            Group by ClientCode, PolicyCode
        )   b
Where	SourceSystemCustomerId = ClientCode
and     SourceSystemId = 1
;


-- stg.DocRequest_genesys_derived_data_filtered. Part of inbound documents out calls, read by VD.V1.
Create or Replace Table stg.DocRequest_genesys_derived_data_filtered as 
select	a.ConversationId, CustomerPhoneNumber,a.sessionIndex,A.conversationStartTime
from	stg.A0_genesys_derived_data	a
where	queueName = 'INBOUND_Documents_Out'
;


# Motor Acquisitions

# In[ ]:


--A1

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
    date_trunc('MINUTE', Step1DateTime),
    cast(Step1DateTime as date),
    'A1',
    'Motor Acquisition - Quote Initiated',
    'Quote'
FROM
    stg.A1_MotorAcquisitionQuoteInitiated


# In[ ]:


--A1.E1

--no service grid data, assume same s A1

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
    date_trunc('MINUTE', Step1DateTime),
    cast(Step1DateTime as date),
    'A1.E1',
    'Motor Acquisition - Service retrieve',
    'Quote'
FROM
    stg.A1_MotorAcquisitionQuoteInitiated


# In[ ]:


--A0

insert INTO
ods.EpisodeEventStream
(        
    EventSourceID,
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
    ConversationId,
    ChillSourceQuoteReference,
    2,
    'Motor',
    date_trunc('MINUTE', conversationStartTime),
    cast(conversationStartTime as date),
    'A0',
    'Motor Acquisition - straight into call centre',
    'Quote'
FROM
    stg.A0_MFQ_genesys_link
("")


# In[ ]:


--A0.F1

insert INTO
ods.EpisodeEventStream
(        
    EventSourceID,
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
    ConversationId,
    null,
    2,
    'Motor',
    date_trunc('MINUTE', conversationStartTime),
    cast(conversationStartTime as date),
    'A0.F1',
    'Motor Acquisition - Call wait time, or fails to make contact',
    'GenesysCall'
FROM
    stg.A0F1_genesys_inbound_call_duration_summary
where   abandoned = 1 
and     CallWaitTime > 0
("")


# In[ ]:


--A2

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
    date_trunc('MINUTE', FirstStep5DateTime),
    cast(FirstStep5DateTime as date),
    'A2',
    'Motor Acquisition - Customer details complete',
    'Quote'
from    stg.A1_MotorAcquisitionQuoteInitiated   
where   FirstStep5DateTime >= (select startTime from stg.episodeeventstream_buildconfig) and FirstStep5DateTime < (select endTime   from stg.episodeeventstream_buildconfig) 


# In[ ]:


--A2.F1

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
    date_trunc('MINUTE', FirstStep2to4DateTime),
    cast(FirstStep2to4DateTime as date),
    'A2.F1',
    'Motor Acquisition - Customer details complete',
    'Quote'
from    stg.A1_MotorAcquisitionQuoteInitiated   
where   FirstStep5DateTime is null 


# In[ ]:


--A2.E1

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
        a.QuoteQueryGuid,
        1,
        'Motor',
        date_trunc('MINUTE', `timestamp`),
        cast(`timestamp` as date),
        'A2.E1',
        'Motor Acquisition - This year retrieve (TYR)',
        'Quote'
from    dlk.EXT_XtremePushResults
where	`timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
and		campaign_name like 'Motor % TYR %' 
and     interaction_type = 'sent' 
and     MessageType = 'EMAIL'
and     QuoteQueryGuid > ''


# In[ ]:


--A3

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
    date_trunc('MINUTE', Step1DateTime),
    cast(Step1DateTime as date),
    'A3',
    'Motor Acquisition - Customer gets a price',
    'Quote'
-- A3 query-- we need to copy the SL10 quote query guids as the scraperflag is quite complex than defined in the framework / chill's explanations in the past /* teams message sent to Nikita for check */
from    stg.MFQInsurersQuoted a
join 
        stg.A1_MotorAcquisitionQuoteInitiated b  
            ON  a.QuoteQueryGuid = b.QuoteQueryGuid 
JOIN 
        stg.A3_SL10_QQGUIDS     z
            ON  a.QuoteQueryGuid = z.QuoteQueryGuid 
left join         
        (select QuoteId, ABPAction from dlk.MFQ_MON_Session Where IsKnownBot = TRUE or case when ABPAction = '' then null else ABPAction end is not null  and `$ExtractDateTime` >= (select startTime from stg.episodeeventstream_buildconfig) and `$ExtractDateTime` < (select endTime   from stg.episodeeventstream_buildconfig) ) c  
            ON  a.QuoteQueryGuid = c.QuoteId 
where   a.InsurersQuoted = 'Y' 
and     z.Tot_All_First = 1 /* source filter to be applied */
and     z.InsurersQuoted = 'Y' /* source filter to be applied */
and     c.QuoteId is null 
and     RetrieveSessionToken is null 
and     Step1DateTime is not null
;


# In[ ]:


--A3.F1

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
    date_trunc('MINUTE', FirstStep5DateTime),
    cast(FirstStep5DateTime as date),
    'A3.F1',
    'Motor Acquisition - No price returned, told to call us',
    'Quote'
from    stg.A1_MotorAcquisitionQuoteInitiated a  
JOIN 
        stg.A3_SL10_QQGUIDS                   b   
            ON  a.QuoteQueryGuid = b.QuoteQueryGuid         
Where   b.Tot_All_First = 1 /* source filter to be applied */
and     b.InsurersQuoted = 'N' /* source filter to be applied */
and     FirstStep5DateTime is not NULL
("")


# In[ ]:


--A3.B1
-- BLOCK HEADER. A3.B1 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from A3.B1.1, A3.B1.2.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

# In[ ]:


--A3.E1
-- converted from the count query. One row per customer phone number on the outbound motor sales queue, with the timestamp taken from conversationStartTime on stg.A0_genesys_derived_data, which is already restricted to the build config window.

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
    a.CustomerPhoneNumber,
    2,
    'Motor',
    date_trunc('MINUTE', min(a.conversationStartTime)),
    cast(min(a.conversationStartTime) as date),
    'A3.E1',
    'Motor Acquisition - Outbound sales callback',
    'Customer'
from    stg.A0_genesys_derived_data a,
        (select ConversationId, max(sessionIndex) sessionIndex
        from    stg.A0_genesys_derived_data
        Where   queueName is not null
        and     originatingDirection = 'inbound'
        Group by ConversationId
        )   b
where   a.ConversationId = b.ConversationId
and     a.sessionIndex = b.sessionIndex
and     a.queueName = 'OUTBOUND_SALES_MOTOR'
Group by a.CustomerPhoneNumber
;

# In[ ]:


--A4a

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
    'Motor',
    date_trunc('MINUTE', PaymentDate),
    cast(PaymentDate as date),
    'A4a',
    'Motor Acquisition - Customer buys ONLINE',
    'Quote'
-- A3 query-- we need to copy the SL10 quote query guids as the scraperflag is quite complex than defined in the framework / chill's explanations in the past /* teams message sent to Nikita for check */
from    stg.GlobalPoliciesSold      a,
        (select QuoteQueryGuid, max(PaymentDate) PaymentDate
        from    stg.MFQ_Quote_Payments 
        where   PaymentStatus like '%|Success, code: 00%' 
        and     PaymentDate >= (select startTime from stg.episodeeventstream_buildconfig) and PaymentDate < (select endTime   from stg.episodeeventstream_buildconfig) 
        and     PaymentType in (0,5)
        Group by QuoteQueryGuid) b 
Where   a.QuoteQueryGuid = b.QuoteQueryGuid
;


# In[ ]:


--A4b

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
    date_trunc('MINUTE', ReportingSaleDate),
    cast(ReportingSaleDate as date),
    'A4b',
    'Motor Acquisition - Agent quotes and converts on the CALL',
    'Policy'
from    stg.GlobalPoliciesSold      a
Where   a.ReportingSaleType = 'New Business' 
and     a.PolicyTypeGroup = 'Motor'
and     a.QuoteQueryGuid is null 



# In[ ]:


--A4.F1

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
    1,
    'Motor',
    date_trunc('MINUTE', ReportingSaleDate),
    cast(ReportingSaleDate as date),
    'A4.F1',
    'Motor Acquisition - Web assist: starts online, then calls to complete',
    'Policy' /* can be quote or policy! */
from    stg.GlobalPoliciesSold      a
Where   a.ReportingSaleType = 'New Business' 
and     a.PolicyTypeGroup = 'Motor'
and     a.QuoteQueryGuid is not null 
and     a.Channel = 'b) Web Assist'
("")


# In[ ]:


--A4b.O1


# In[ ]:


--A5a

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
    date_trunc('MINUTE', PaymentDate),
    cast(PaymentDate as date),
    'A5a',
    'Motor Acquisition - Payment attempted ONLINE',
    'Payment Attempt'
from    stg.MFQ_Quote_Payments  a
where   PaymentDate >= (select startTime from stg.episodeeventstream_buildconfig) and PaymentDate < (select endTime   from stg.episodeeventstream_buildconfig) 
("")


# In[ ]:


--A5.F1

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
    date_trunc('MINUTE', PaymentDate),
    cast(PaymentDate as date),
    'A5.F1',
    'Motor Acquisition - Payment failed',
    'Quote'
from    stg.MFQ_Quote_Payments  a
where   PaymentDate >= (select startTime from stg.episodeeventstream_buildconfig) and PaymentDate < (select endTime   from stg.episodeeventstream_buildconfig) 
and     PaymentType not in (0,5)
("")


# In[ ]:


--A5.B1
-- BLOCK HEADER. A5.B1 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from A5.B1.1, A5.B1.2, A5.B1.3, A5.B1.4, A5.B1.5.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

# In[ ]:


--A5.1

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
        a.QuoteQueryGuid,
        1,
        'Motor',
        date_trunc('MINUTE', `timestamp`),
        cast(`timestamp` as date),
        'A5.1',
        'Motor Acquisition - Service retrieve',
        'Policy'
from    dlk.EXT_XtremePushResults
where	`timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
and		campaign_name = 'Online Motor Bind Confirmation' and interaction_type = 'sent' 
("")


# In[ ]:


--A6

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
        max(date_trunc('MINUTE', coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
        max(cast(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') as date)),
        'A6',
        'Motor Acquisition - Documents requested',
        'Policy'
FROM    edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between (select startTime from stg.episodeeventstream_buildconfig) and (select endTime   from stg.episodeeventstream_buildconfig) and PolicyType = 'New Business' and PolicyTypeGroup = 'Motor' and 
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
	when [2ndCar_Cert_Status]			= 'O' then 1 
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


# In[ ]:


--A6.F1

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
        max(date_trunc('MINUTE', coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
        max(cast(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') as date)),
        'A6.F1',
        'Motor Acquisition - Chases before the customer submits, and documents never submitted',
        'Policy'
FROM    edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between (select startTime from stg.episodeeventstream_buildconfig) and (select endTime   from stg.episodeeventstream_buildconfig) and PolicyType = 'New Business' and PolicyTypeGroup = 'Motor' and 
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
	when [2ndCar_Cert_Status]			= 'O' then 1 
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
and Campaign = 'DAY 20'
Group by a.PolicyCode


# In[ ]:


--A6.B1


# In[ ]:


--A6.B1.F1
-- mirrored from VA6.B1.F1. same chase snapshot table with PolicyTypeGroup switched to Motor, and the donor's literal 2026-05-01 to 2026-07-31 chase window and its PolicyType Renewals filter are both kept exactly as written.

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
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-07-31'
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

# In[ ]:


--A7
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
        'Motor',
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDate as date)),
        'A7',
        'Motor Acquisition - Documents requested',
        'Policy'
FROM    stg.GlobalPoliciesSold                   a,
        ods.EventStream                          d 
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Motor'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
            ( 
                'New Business - Document Transmission Confirmed - Certificate',
                'New Business - Document Posted Confirmation - Certificate',
                'New Business - Document Transmitted - Certificate'
            )   

Group by a.PolicyCode
("")


# In[ ]:


--A7.F1

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
        'A7.F1',
        'Motor Acquisition - Non-arrival, and time taken to receive',
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
            and Campaign = 'DAY 20'
            Group by PolicyCode
        )   x
Group by x.PolicyCode
;


# In[ ]:


--A7.B1


# In[ ]:


--A3.B1.1

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
    QuoteQueryGuid,
    2,
    'Motor',
    date_trunc('MINUTE', Step1DateTime),
    cast(Step1DateTime as date),
    'A3.B1.1',
    'Motor Acquisition - Quote retrieved or iterated',
    'Quote'
from	stg.a1_motoracquisitionquoteinitiated a, 
        stg.a1_motoracquisitionquoteinitiated b 
Where	a.QuoteQueryGuid = b.RetrieveSessionToken

# In[ ]:


--A3.B1.2


# In[ ]:


--A3.B1.O1


# In[ ]:


--A6.B1.1

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
        'A6.B1.1',
        'Motor Acquisition - Document request issued',
        'Policy'
From    (
            select  PolicyCode,
                    max(coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01')) SaleDateTime
            from    edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan   a
            Where   coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
            and     a.PolicyType = 'New Business'
            and     a.PolicyTypeGroup = 'Motor'
            Group by PolicyCode
        )   x
Group by x.PolicyCode
;


# In[ ]:


--A6.B1.2

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
        date_trunc('MINUTE', `timestamp`),
        cast(`timestamp` as date),
        'A6.B1.2',
        'Motor Acquisition - Customer submits documents',
        'Policy'
from    stg.GlobalPoliciesSold a, dlk.MyChill_NewUploadDocumentEvents  b 
Where   a.PolicyCode = b.PolicyCode
and     ReportingSaleType = 'New Business' 
and     PolicyTypeGroup = 'Motor'
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
("")


# In[ ]:


--A6.B1.4
-- mirrored from HA6.B1.4. straight swap of the chase snapshot to edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan with PolicyTypeGroup Motor added, keeping the donor's subquery, its six document status columns and the DAY 1 campaign filter.

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


--A6.B1.5

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
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDate as date)),
        'A6.B1.5',
        'Motor Acquisition - Documents requested',
        'Policy'
FROM    stg.GlobalPoliciesSold                   a,
        ods.EventStream                          d 
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Motor'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ReportingSaleType = 'New Business' 
and     EventDescription like '%Chase%' 
and     EventDescription like '%Final%' 

Group by a.PolicyCode
("")


# In[ ]:


--A6.B1.3

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
        date_trunc('MINUTE', `timestamp`),
        cast(`timestamp` as date),
        'A6.B1.3',
        'Motor Acquisition - Documents validated',
        'Policy'
from    stg.GlobalPoliciesSold a, dlk.MyChillWorkflow_DocumentStatus  b 
Where   a.PolicyCode = b.PolicyCode
and     ReportingSaleType = 'New Business' 
and     PolicyTypeGroup = 'Motor'
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
--and     isAccepted = 'true'
("")


# In[ ]:


--A6.B1.O1
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
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDate as date)),
        'A6.B1.O1',
        'Motor Acquisition - Documents requested',
        'Policy'
FROM    stg.GlobalPoliciesSold                   a,
        ods.EventStream                          d 
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Motor'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
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
        and     d.PolicyTypeGroup = 'Motor'
        and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
        and     ReportingSaleType = 'New Business' 
        and     EventDescription like '%Chase%' 
        and     EventDescription like '%Final%' )

Group by a.PolicyCode
("")


# In[ ]:


--A6.B1.6

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
        date_trunc('MINUTE', `timestamp`),
        cast(`timestamp` as date),
        'A6.B1.6',
        'Motor Acquisition - Documents received and validated',
        'Policy'
from    stg.GlobalPoliciesSold a, dlk.MyChillWorkflow_DocumentStatus  b 
Where   a.PolicyCode = b.PolicyCode
and     ReportingSaleType = 'New Business' 
and     PolicyTypeGroup = 'Motor'
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
and     isAccepted = 'true'


# In[ ]:


--A7.B1.1
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
        'Motor',
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDate as date)),
        'A7.B1.1',
        'Motor Acquisition - Documents requested',
        'Policy'
FROM    stg.GlobalPoliciesSold                   a,
        ods.EventStream                          d 
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Motor'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ReportingSaleType = 'New Business' 
and     EventDescription IN 
            ( 
                'New Business - Document Transmitted - Certificate' /* as confirmed by 2003 / 2004 / 2014 only this exists --Document Transmitted */
            )   

Group by a.PolicyCode
("")


# In[ ]:


--A7.B1.2

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
        'Motor',
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDate as date)),
        'A7.B1.2',
        'Motor Acquisition - Documents requested',
        'Policy'
FROM    stg.GlobalPoliciesSold                   a,
        ods.EventStream                          d 
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Motor'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ReportingSaleType = 'New Business' 
and     EventDescription in (
            'New Business - Document Transmitted - Terms Of Business',
            'New Business - Emailed Document - Terms Of Business'
            )

Group by a.PolicyCode
("")


# In[ ]:


--A7.B1.3
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
        'Motor',
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDate as date)),
        'A7.B1.3',
        'Motor Acquisition - Documents requested',
        'Policy'
FROM    stg.GlobalPoliciesSold                   a,
        ods.EventStream                          d 
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Motor'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ReportingSaleType = 'New Business' 
and     EventDescription in (
            'New Business - Document Transmitted - Terms Of Business',
            'New Business - Emailed Document - Terms Of Business'
            )

Group by a.PolicyCode
("")


# In[ ]:


--A7.B1.4

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
        'A7.B1.4',
        'Motor Acquisition - Document request issued',
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
            Group by PolicyCode
        )   x
Group by x.PolicyCode
;


# In[ ]:


--A7.B1.5
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
        'Motor',
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDate as date)),
        'A7.B1.5',
        'Motor Acquisition - Documents requested',
        'Policy'
FROM    stg.GlobalPoliciesSold                   a,
        ods.EventStream                          d 
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Motor'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ReportingSaleType = 'New Business' 
and     EventDescription in (
            'Duplicate Certificate - Document Transmitted - Certificate'
            )

Group by a.PolicyCode
("")


# Motor Renewals

# In[ ]:


--RO.F1

-- converted from the count query. The renewal held letter is taken from the Relay feed, with
-- min(EventDateTime) as the first time the hold went out, and the build config run window added
-- because the pasted query carried no window of its own.
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
    a.SourcePolicyReference,
    1,
    'Motor',
    date_trunc('MINUTE', min(a.EventDateTime)),
    cast(min(a.EventDateTime) as date),
    'RO.F1',
    'Motor Renewal - Not sent - no terms from Insurer',
    'Policy'
from    ods.eventstream     a
where   a.PolicyTypeGroup = 'Motor'
and     a.EventSourceId = 3
and     a.EventDescription like 'Renewal Offer % Held %'
and     a.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and a.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
Group by a.SourcePolicyReference
;

--R0.B1

-- converted from the count query. NOTE this is the same query as RO.F1 above, so the two steps will
-- write one event each for the same policies. Confirm they are meant to be separate before loading both.
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
    a.SourcePolicyReference,
    1,
    'Motor',
    date_trunc('MINUTE', min(a.EventDateTime)),
    cast(min(a.EventDateTime) as date),
    'R0.B1',
    'Motor Renewal - Renewal held letter',
    'Policy'
from    ods.eventstream     a
where   a.PolicyTypeGroup = 'Motor'
and     a.EventSourceId = 3
and     a.EventDescription like 'Renewal Offer % Held %'
and     a.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and a.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
Group by a.SourcePolicyReference
;

--RO.F2
-- converted from the count query. ClaimDate is an integer in yyyymmdd form so it is cast to a date for the
-- timestamp, the derived table was flattened to reach it, and the twelve month claims window is kept as it was.

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
    date_trunc('MINUTE', max(to_date(cast(a.ClaimDate as string), 'yyyyMMdd'))),
    cast(max(to_date(cast(a.ClaimDate as string), 'yyyyMMdd')) as date),
    'RO.F2',
    'Motor Renewal - Declared claims not recorded',
    'Policy'
from    stg.motorclaims                             a,
        stg.R0_MotorPoliciesEligibleForRenewals     b
Where   a.PolicyCode = b.PolicyCode
and     a.ClaimDate between 20250801 and 20260731
and     a.OwnFaultFlag = 'Y'
Group by b.PolicyCode
;

# In[ ]:


--R1a

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
SELECT  a.SourcePolicyReference,
        1,
        'Motor',
        max(date_trunc('MINUTE', OfferedDateTime)),
        max(cast(OfferedDateTime as date)),
        'R1a',
        'Motor Renewal - Renewal invitation sent by EMAIL',
        'Policy'
FROM    stg.R1_Motor_Renewals_EmailOffered

Group by a.SourcePolicyReference
("")


# In[ ]:


--R1b
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
SELECT  a.SourcePolicyReference,
        1,
        'Motor',
        max(date_trunc('MINUTE', OfferedDateTime)),
        max(cast(OfferedDateTime as date)),
        'R1b',
        'Motor Renewal - Renewal invitation sent by EMAIL',
        'Policy'
FROM    stg.R1_Motor_Renewals_PostOffered
Group by a.SourcePolicyReference
("")


# In[ ]:


--R1.B2

-- converted from the count query. LYPolicyRenewDateAdj is the only date on the cohort so it supplies the
-- timestamp, and its July window is a renewal month cohort filter rather than the run window, so it is
-- kept as the literal the query had.
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
    date_trunc('MINUTE', min(a.LYPolicyRenewDateAdj)),
    cast(min(a.LYPolicyRenewDateAdj) as date),
    'R1.B2',
    'Motor Renewal - Alternative offer sent',
    'Policy'
from    edw.tbl_fact_policy_renewals    a
Where   a.LYPolicyTypeGroup = 'Motor'
and     a.LYPolicyRenewDateAdj between '2026-07-01' and '2026-07-31'
and     a.PolicyOfferNum = 1
and     a.RenEURPremInvite <> a.RenEURPremOffer
Group by a.PolicyCode
;

--R1.E1
-- mirrored from HR1.E1. Straight swap of the renewals table to stg.R0_MotorPoliciesEligibleForRenewals, which only needs PolicyCode, with the campaign filter moved to Motor and the literal window of 2026-06-01 to 2026-09-01 kept exactly as the donor has it.

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
where   a.`timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and add_months((select endTime   from stg.episodeeventstream_buildconfig),  1)
and     a.PolicyCode = b.PolicyCode
and     a.campaign_name like '%Motor%'
and     a.campaign_name like '%Renewals%'
and     a.MessageType in ( 'EMAIL', 'SMS')
and     a.interaction_type = 'sent'
Group by a.PolicyCode
;

# In[ ]:

--R1.E1.F3
-- from XX - Episode Reconciliation - Gaps.html, cell 1 (count query)
-- header: Motor	Renewal	R1.E1.F3
  -- get Renewal emails from XP table

-- converted from the count query. Timestamp is the first XtremePush `timestamp` for the policy, the campaign window of 2026-05-01 to 2026-08-10 has been kept exactly as it was, and note that stg.R0_MotorPoliciesEligibleForRenewals is built in the notebook with LyPolicyTypeGroup = 'Home', which has been left as it is.

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
    date_trunc('MINUTE', min(x.SentTimestamp)),
    cast(min(x.SentTimestamp) as date),
    'R1.E1.F3',
    'Motor Renewal - Renewal customer in an acquisition campaign audience',
    'Policy'
from    (
            select  distinct b.PolicyCode, a.`timestamp` as SentTimestamp
            from    dlk.EXT_XtremePushResults a, stg.R0_MotorPoliciesEligibleForRenewals b
            where   campaign_name like '%Motor%'
            and     campaign_name like '%TYR%'
            and     a.PolicyCode = b.PolicyCode
            and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
            and     interaction_type = 'sent'
            and     MessageType  in ( 'EMAIL', 'SMS')
            union
            select  distinct b.PolicyCode, a.`timestamp` as SentTimestamp
            from    dlk.EXT_XtremePushResults_Policy a, stg.R0_MotorPoliciesEligibleForRenewals b
            where   campaign_name like '%Motor%'
            and     campaign_name like '%TYR%'
            and     a.PolicyCode = b.PolicyCode
            and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
            and     interaction_type = 'sent'
            and     MessageType  in ( 'EMAIL', 'SMS')
        ) x
Group by x.PolicyCode
;

# In[ ]:


--R2
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
        'Motor',
        max(date_trunc('MINUTE', 'Timestamp')),
        max(cast('Timestamp' as date)),
        'R2',
        'Motor Renewal - Customer logs in to portal',
        'Policy'
FROM    (
            select  left(PolicyCode,6) as ClientCode, dateadd(day, -60, RenewalDate) RenewalStartDate, PolicyCode, dateadd(day, 40, RenewalDate) RenewalEndDate
            from stg.R0_MotorPoliciesEligibleForRenewals 
        )   a,
        dlk.appliedrenewals_successfulloginevent b 
Where   a.ClientCode = b.PortfolioCode 
and     b.`Timestamp` > a.RenewalStartDate
and     b.`Timestamp` < a.RenewalEndDate
group by a.PolicyCode


# In[ ]:


--R2.F1
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
        'Motor',
        max(date_trunc('MINUTE', 'Timestamp')),
        max(cast('Timestamp' as date)),
        'R2.F1',
        'Motor Renewal - Failed login',
        'Policy'
FROM    (
            select  left(PolicyCode,6) as ClientCode, dateadd(day, -60, RenewalDate) RenewalStartDate, PolicyCode, dateadd(day, 40, RenewalDate) RenewalEndDate
            from stg.R0_MotorPoliciesEligibleForRenewals 
        )   a,
        dlk.appliedrenewals_failedloginevent b 
Where   a.ClientCode = b.PortfolioCode 
and     b.`Timestamp` > a.RenewalStartDate
and     b.`Timestamp` < a.RenewalEndDate
group by a.PolicyCode
("")


# In[ ]:


--R2.B1
-- BLOCK HEADER. R2.B1 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from R2.B1.1, R2.B1.2, R2.B1.3, R2.B1.4.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

# In[ ]:


--R2.B1.F1
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
        'R2.B1.F1',
        'Motor Renewal - New quote does not beat the renewal price, or the quote is abandoned',
        'Policy'
FROM    stg.RenewalsDoingMFQ  a 
left join 
        (
            select  PolicyCode
            from    stg.MFQ_Quote_Payments a, stg.RenewalsDoingMFQ  b 
            Where   a.QuotequeryGuId = b.MFQQuotequeryGuId 
            and     PaymentType in (0,5)
            and     PaymentDate  between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and add_months((select endTime   from stg.episodeeventstream_buildconfig),  1) 
            Group by PolicyCode
        ) b 
        on b.PolicyCode = a.PolicyCode
where b.PolicyCode is null  
group by a.PolicyCode
("")


# In[ ]:


--R2.E1

-- converted from the count query. The distinct TyPolicyCode is the grain so it goes into
-- SourcePolicyReference, and TyPolicyRenewDateAdj on the eligible for renewals table supplies the
-- timestamp because it is always populated, unlike the sale date. RenewalMonth is a cohort filter and
-- stays as the literal it was.
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
    'Motor',
    date_trunc('MINUTE', min(a.TyPolicyRenewDateAdj)),
    cast(min(a.TyPolicyRenewDateAdj) as date),
    'R2.E1',
    'Motor Renewal - In-flight price improvement: promo code, or the agent reduces the fee',
    'Policy'
from    stg.R0_MotorPoliciesEligibleForRenewals     a,
        edw.tbl_fact_policy_renewals                b
Where   a.PolicyCode = b.PolicyCode
and     b.RenewalMonth = '2026-07-31'
and     b.RenEurFee <> b.TYEURFees
Group by a.TyPolicyCode
;

# In[ ]:


--R3a
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
        max(date_trunc('MINUTE', RenewalStartDate)),
        max(cast(RenewalStartDate as date)),
        'R3a',
        'Motor Renewal - Customer renews ONLINE',
        'Policy'
FROM    stg.MotorRenewalsOnline
group by PolicyCode
("")


# In[ ]:


--R3b
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
SELECT  ar_policy_code,
        1,
        'Motor',
        max(date_trunc('MINUTE', RenewalStartDate)),
        max(cast(RenewalStartDate as date)),
        'R3b',
        'Motor Renewal - Customer renews ONLINE',
        'Policy' 
from    dlk.rbsdata2_newarchive a, edw.tbl_ref_Mapping_BAR_Premium_Type b 
Where   replace(a.ar_cli_type, ' ', '-')        = b.ar_cli_type 
and     replace(a.ar_com_type, ' ', '-')        = b.ar_com_type
and     replace(a.ar_return_sub_type, ' ', '-') = b.ar_return_sub_type 
and     replace(a.ar_com_sta, ' ', '-')         = b.ar_com_sta
and     replace(a.ar_confirmed_prov, ' ', '-')  = b.ar_confirmed_prov
and     PremiumTypeGroup = 'Renewals'
and     a.ar_posting_date between 20260501 and 20260830 
and     a.ar_pol_type = 'M1' 
Group by ar_policy_code  


# In[ ]:


--R3c
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
SELECT  TyPolicyCode,
        1,
        'Motor',
        max(date_trunc('MINUTE', RenewalStartDate)),
        max(cast(RenewalStartDate as date)),
        'R3c',
        'Motor Renewal - Customer renews ONLINE',
        'Policy' 
from    edw.tbl_fact_policy_renewals 
where   RenewalMonth = '2026-07-31' 
and     channel = 'a) IB' 
and     PolicyRetNum = 1 
and     PolicyOfferNum = 1 
and		LYPolicyTypeGroup = 'Motor' 
Group by TyPolicyCode


# In[ ]:


--R3d
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
SELECT  TyPolicyCode,
        1,
        'Motor',
        max(date_trunc('MINUTE', RenewalStartDate)),
        max(cast(RenewalStartDate as date)),
        'R3d',
        'Motor Renewal - Customer renews on CHAT',
        'Policy' 
from    edw.tbl_fact_policy_renewals 
where   RenewalMonth = '2026-07-31' 
and     channel like '%eb %'
and     PolicyRetNum = 1 
and     PolicyOfferNum = 1 
and		LYPolicyTypeGroup = 'Motor' 
Group by TyPolicyCode


# In[ ]:


--R3b.F1
-- converted literally from the query in this cell, with the seelct typo corrected.
-- CAVEAT: the query is a bare distinct conversationId over stg.R0_genesys_derived_data with no queue,
-- abandoned or wait time filter, so it returns every Genesys conversation in the run window rather than the
-- 969 on the recon tab. The Motor equivalent A0.F1 filters abandoned = 1 and CallWaitTime > 0 on a named
-- queue. Tell me the Motor renewals queue and I will bring this in line.

insert INTO
ods.EpisodeEventStream
(
    EventSourceID,
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
    a.conversationID,
    null,
    2,
    'Motor',
    date_trunc('MINUTE', min(a.conversationStartTime)),
    cast(min(a.conversationStartTime) as date),
    'R3b.F1',
    'Motor Renewal - Call wait time, or fails to make contact',
    'Call'
from    stg.R3bF1_genesys_inbound_call_duration_summary a, 
stg.R0_genesys_derived_data b 
where a.abandoned = 1 and a.CallWaitTime > 0 
and a.ConversationId = b.ConversationId 
Group by a.conversationID;

# In[ ]:


--R3.B1
-- BLOCK HEADER. R3.B1 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from R3.B1.1, R3.B1.2, R3.B1.3, R3.B1.4.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

# In[ ]:


--R3.O1
-- mirrored from HR3.O1. Mirrored from the Home donor with stg.R3B1_LapsedThisYearPolicy built first in the same cell, swapping only the renewals table to stg.R0_MotorPoliciesEligibleForRenewals, which carries the PolicyCode and RenewalDate that the build and the insert need.

-- stg.R3B1_LapsedThisYearPolicy is built in the Derived Data section at the top of this notebook.

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
    date_trunc('MINUTE', max(a.RenewalDate)),
    cast(max(a.RenewalDate) as date),
    'R3.O1',
    'Motor Renewal - Policy lapsed',
    'Policy'
from    stg.R3B1_LapsedThisYearPolicy a
Group by a.PolicyCode
;

# In[ ]:

--R4

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
    'Motor',
    date_trunc('MINUTE', max(a.TYReportingSaleDate)),
    cast(max(a.TYReportingSaleDate) as date),
    'R4',
    'Motor Renewal - Payment taken',
    'Policy'
from    stg.R0_MotorPoliciesEligibleForRenewals a
Where   a.PolicyRetNum = 1
Group by a.TyPolicyCode
;


# In[ ]:


--R4.F1
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
        'Motor',
        max(date_trunc('MINUTE', RenewalStartDate)),
        max(cast(RenewalStartDate as date)),
        'R4.F1',
        'Motor Renewal - Payment failed',
        'Policy'
FROM    (
            select  left(PolicyCode,6) as ClientCode, dateadd(day, -60, RenewalDate) RenewalStartDate, PolicyCode, dateadd(day, 40, RenewalDate) RenewalEndDate
            from stg.R0_MotorPoliciesEligibleForRenewals 
        )   a,
        dlk.AppliedRenewals_PaymentFailedEvent b 
Where   ClientCode = b.PortfolioCode
and     b.`Timestamp` > a.RenewalStartDate
and     b.`Timestamp` < a.RenewalEndDate
group by a.PolicyCode


# In[ ]:


--R4.B2


# In[ ]:


--R4a
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
        'Motor',
        max(date_trunc('MINUTE', RenewalStartDate)),
        max(cast(RenewalStartDate as date)),
        'R4a',
        'Motor Renewal - Pay in full',
        'Policy'
from    (
            select  left(PolicyCode,6) as ClientCode, dateadd(day, -60, RenewalDate) RenewalStartDate, PolicyCode, dateadd(day, 40, RenewalDate) RenewalEndDate
            from stg.R0_MotorPoliciesEligibleForRenewals 
        )   a,
        dlk.AppliedRenewals_PaymentSuccess b 
Where   ClientCode = b.PortfolioCode
and     b.`Timestamp` > a.RenewalStartDate
and     b.`Timestamp` < a.RenewalEndDate
and     PaymentType = 'Full'
Group by PolicyCode
("")


# In[ ]:


--R4c
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
        'Motor',
        max(date_trunc('MINUTE', RenewalStartDate)),
        max(cast(RenewalStartDate as date)),
        'R4c',
        'Motor Renewal - New monthly agreement',
        'Policy'
from    (
            select  left(PolicyCode,6) as ClientCode, dateadd(day, -60, RenewalDate) RenewalStartDate, PolicyCode, dateadd(day, 40, RenewalDate) RenewalEndDate
            from stg.R0_MotorPoliciesEligibleForRenewals 
        )   a,
        dlk.AppliedRenewals_PaymentSuccess b 
Where   ClientCode = b.PortfolioCode
and     b.`Timestamp` > a.RenewalStartDate
and     b.`Timestamp` < a.RenewalEndDate
and     PaymentType = 'Instalments'
Group by PolicyCode
("")


# In[ ]:


--R5
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
        'Motor',
        max(date_trunc('MINUTE', a.EventDateTime)),
        max(cast(a.EventDateTime as date)),
        'R5',
        'Motor Renewal - Renewal processed, policy continued',
        'Policy'
from    stg.R0_MotorPoliciesEligibleForRenewals  a,
        ods.EventStream                          d 
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Motor'
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000' 
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
("")


# In[ ]:


--R6
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
        'Motor',
        max(date_trunc('MINUTE', a.EventDateTime)),
        max(cast(a.EventDateTime as date)),
        'R6',
        'Motor Renewal - Cert and disc sent',
        'Policy'
from    stg.R0_MotorPoliciesEligibleForRenewals  a,
        ods.EventStream                          d 
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Motor'
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000' 
and     EventDescription IN 
    (
        'Renewal Confirmation - Document Transmitted - RNL Cert Issue Letter',
        'Renewal Confirmation - Document Transmitted - Certificate',
        'Renewal Transfer - Document Transmitted - RNL Cert Issue Letter',
        'Renewal Transfer - Document Transmitted - Certificate',
        'New Business - Document Transmitted - NB Cert Issue Letter',
        'New Business - Document Transmitted - Certificate',
        'Renewal Confirmation - Emailed Document - Certificate',
        'Renewal Transfer - Emailed Document - Certificate'
        'Renewal Transfer - Printed Document - RNL Cert Issue Letter'

    )

Group by a.PolicyCode
("")


# In[ ]:


--R2.B1.1
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
        'Motor',
        max(date_trunc('MINUTE', a.QuoteStartDatetime)),
        max(cast(a.QuoteStartDatetime as date)),
        'R2.B1.1',
        'Motor Renewal - MFQ quote started from the renewal price',
        'Policy'
from    stg.R2B1_1_Base
Group by a.PolicyCode


# In[ ]:


--R2.B1.2


# In[ ]:


--R2.B1.3
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
        'Motor',
        max(date_trunc('MINUTE', a.QuoteStartDatetime)),
        max(cast(a.QuoteStartDatetime as date)),
        'R2.B1.3',
        'Motor Renewal - New price returned',
        'Policy'
from    stg.R2B1_3_base
Group by a.PolicyCode


# In[ ]:


--R2.B1.3.F1
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
        'Motor',
        max(date_trunc('MINUTE', a.QuoteStartDatetime)),
        max(cast(a.QuoteStartDatetime as date)),
        'R2.B1.3.F1',
        'Motor Renewal - No price returned, or the quote is abandoned',
        'Policy'
from    stg.R2B1_1_Base a 
left join (select  
           distinct PolicyCode 
           from stg.R2B1_1_Base a, 
                stg.MFQInsurersQuoted   b  
           Where a.MFQQuoteQueryGuid = b.QuoteQueryGuid and InsurersQuoted = 'Y') b 
on a.PolicyCode = b.PolicyCode
Where b.PolicyCode is null
Group by a.PolicyCode;


# In[ ]:


--R2.B1.4.F1
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
        'Motor',
        max(date_trunc('MINUTE', a.QuoteStartDatetime)),
        max(cast(a.QuoteStartDatetime as date)),
        'R2.B1.4.F1',
        'Motor Renewal - New price is worse than the renewal offer',
        'Policy'
from    stg.R2B1_4_F1_MFQPrices 
Where   Rank1PremComp > RenEURPremOffer and RenEURPremOffer > 0
Group by a.PolicyCode;


# In[ ]:


--R2.B1.O1
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
        'Motor',
        max(date_trunc('MINUTE', a.QuoteStartDatetime)),
        max(cast(a.QuoteStartDatetime as date)),
        'R2.B1.O1',
        'Motor Renewal - Renews on the renewal offer',
        'Policy'
from    stg.R2B1_4_F1_MFQPrices  
Where   Rank1PremComp > TYEURGrossPremium
Group by a.PolicyCode;


# In[ ]:


--R2.B1.O2
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
        'Motor',
        max(date_trunc('MINUTE', a.QuoteStartDatetime)),
        max(cast(a.QuoteStartDatetime as date)),
        'R2.B1.O2',
        'Motor Renewal - Renews on a new MFQ price',
        'Policy'
from    stg.R2B1_4_F1_MFQPrices  
Where   RenEURPremOffer > TYEURGrossPremium
Group by a.PolicyCode;


# In[ ]:


--R2.B1.O3
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
        'Motor',
        max(date_trunc('MINUTE', b.QuoteStartDatetime)),
        max(cast(b.QuoteStartDatetime as date)),
        'R2.B1.O3',
        'Motor Renewal - Buys elsewhere, no renewal',
        'Policy'
from    stg.R0_MotorPoliciesEligibleForRenewals a, stg.R2B1_4_F1_MFQPrices  b 
Where   a.PolicyCode = b.PolicyCode 
and     TyReportingSaleDate is null
Group by a.PolicyCode;


# In[ ]:


--R3.B1.1
-- from XX - Episode Reconciliation - Gaps.html, cell 5 (count query)
-- header: Motor	Renewal	R3.B1.1

-- converted from the count query. RenewalDate is the only timestamp available because the filter includes policies with a null TYReportingSaleDate, and note that stg.R0_MotorPoliciesEligibleForRenewals is built in the notebook with LyPolicyTypeGroup = 'Home', which has been left as it is.

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
    date_trunc('MINUTE', min(a.RenewalDate)),
    cast(min(a.RenewalDate) as date),
    'R3.B1.1',
    'Motor Renewal - Renewal date passes with no renewal',
    'Policy'
from    stg.r0_motorpolicieseligibleforrenewals a
Where   (
            a.TYReportingSaleDate > a.RenewalDate
        or
            a.TYReportingSaleDate is null
        )
and     a.PolicyOfferNum > 0
Group by a.PolicyCode
;

# In[ ]:
--R3.B1.2
-- from XX - Episode Reconciliation - Gaps.html, cell 2 (count query)
-- header: Motor	Renewal	R3.B1.2
  -- get Renewal emails from XP table

-- converted from the count query. Timestamp is the first lapse campaign send for the policy, the window of 2026-05-01 to 2026-08-10 has been kept exactly as it was, and note that stg.R0_MotorPoliciesEligibleForRenewals is built in the notebook with LyPolicyTypeGroup = 'Home', which has been left as it is.

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
    date_trunc('MINUTE', min(x.SentTimestamp)),
    cast(min(x.SentTimestamp) as date),
    'R3.B1.2',
    'Motor Renewal - Lapse CRM sequence runs',
    'Policy'
from    (
            select  distinct b.PolicyCode, a.`timestamp` as SentTimestamp
            from    dlk.EXT_XtremePushResults a, stg.R0_MotorPoliciesEligibleForRenewals b
            where   campaign_name like '%Motor%'
            and     campaign_name like '%Lapsed%'
            and     a.PolicyCode = b.PolicyCode
            and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
            and     interaction_type = 'sent'
            and     MessageType  in ( 'EMAIL', 'SMS')
            union
            select  distinct b.PolicyCode, a.`timestamp` as SentTimestamp
            from    dlk.EXT_XtremePushResults_Policy a, stg.R0_MotorPoliciesEligibleForRenewals b
            where   campaign_name like '%Motor%'
            and     campaign_name like '%Lapsed%'
            and     a.PolicyCode = b.PolicyCode
            and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
            and     interaction_type = 'sent'
            and     MessageType  in ( 'EMAIL', 'SMS')
        ) x
Group by x.PolicyCode
;

# In[ ]:
--R3.B1.2.F1
-- from XX - Episode Reconciliation - Gaps.html, cell 3 (count query)
-- header: Motor	Renewal	R3.B1.2.F1

-- converted from the count query. Timestamp is the last send on the lapse sequence because the event is the absence of any open or click, the window of 2026-05-01 to 2026-08-10 has been kept exactly as it was, and note that stg.R0_MotorPoliciesEligibleForRenewals is built in the notebook with LyPolicyTypeGroup = 'Home', which has been left as it is.

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
    date_trunc('MINUTE', max(a.`timestamp`)),
    cast(max(a.`timestamp`) as date),
    'R3.B1.2.F1',
    'Motor Renewal - Unreachable on the lapse sequence',
    'Policy'
from    dlk.EXT_XtremePushResults_Policy a, stg.R0_MotorPoliciesEligibleForRenewals b
where   campaign_name like '%Motor%'
and     campaign_name like '%Lapsed%'
and     a.PolicyCode = b.PolicyCode
and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
and     interaction_type = 'sent'
and     MessageType  in ( 'EMAIL', 'SMS')
and     a.PolicyCode not in
        (
            select  distinct a.PolicyCode
            from    dlk.EXT_XtremePushResults_Policy a, stg.R0_MotorPoliciesEligibleForRenewals b
            where   campaign_name like '%Motor%'
            and     campaign_name like '%Lapsed%'
            and     a.PolicyCode = b.PolicyCode
            and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
            and     interaction_type in ('open','click')
            and     MessageType  in ( 'EMAIL', 'SMS')
        )
Group by a.PolicyCode
;

# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 4 (count query)
-- header: Motor	Renewal	R3.B1.2.F1
select  count(distinct a.PolicyCode)
from    dlk.EXT_XtremePushResults_Policy a, stg.R0_MotorPoliciesEligibleForRenewals b 
where   campaign_name like '%Motor%' 
and     campaign_name like '%Lapsed%' 
and     a.PolicyCode = b.PolicyCode 
and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000' 
and     interaction_type = 'sent' 
and     MessageType  in ( 'EMAIL', 'SMS')
and     a.PolicyCode not in 
        (
            select  distinct a.PolicyCode
            from    dlk.EXT_XtremePushResults_Policy a, stg.R0_MotorPoliciesEligibleForRenewals b 
            where   campaign_name like '%Motor%' 
            and     campaign_name like '%Lapsed%' 
            and     a.PolicyCode = b.PolicyCode 
            and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000' 
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
            and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000' 
            and     interaction_type in ('bounce')
            and     MessageType  in ( 'EMAIL', 'SMS')
        )

# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 21 (count query)
-- header: Motor	Renewal	R3.B1.2.F1
select  count(distinct a.PolicyCode)
from    dlk.EXT_XtremePushResults a, stg.R0_HomePoliciesEligibleForRenewals b 
where   campaign_name like '%Home%' 
and     campaign_name like '%Lapsed%' 
and     a.PolicyCode = b.PolicyCode 
and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000' 
and     interaction_type = 'sent' 
and     MessageType  in ( 'EMAIL', 'SMS')
and     a.PolicyCode not in 
        (
            select  distinct a.PolicyCode
            from    dlk.EXT_XtremePushResults a, stg.R0_HomePoliciesEligibleForRenewals b 
            where   campaign_name like '%Home%' 
            and     campaign_name like '%Lapsed%' 
            and     a.PolicyCode = b.PolicyCode 
            and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000' 
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
            and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000' 
            and     interaction_type in ('bounce')
            and     MessageType  in ( 'EMAIL', 'SMS')
        )

# In[ ]:
--R3.B1.3
-- from XX - Episode Reconciliation - Gaps.html, cell 6 (count query)
-- header: Motor	Renewal	R3.B1.3

-- converted from the count query. RenewalDate is used for the timestamp because TYReportingSaleDate can be null on these rows, the day 7 offset stays in the filter only, and note that stg.R0_MotorPoliciesEligibleForRenewals is built in the notebook with LyPolicyTypeGroup = 'Home', which has been left as it is.

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
    date_trunc('MINUTE', min(a.RenewalDate)),
    cast(min(a.RenewalDate) as date),
    'R3.B1.3',
    'Motor Renewal - Online renewal window closes at day 7',
    'Policy'
from    stg.r0_motorpolicieseligibleforrenewals a
Where   (
            a.TYReportingSaleDate >= dateadd(day,7,a.RenewalDate)
        or
            a.TYReportingSaleDate is null
        )
and     a.PolicyOfferNum > 0
Group by a.PolicyCode
;

# In[ ]:
--R3.B1.4
-- from XX - Episode Reconciliation - Gaps.html, cell 7 (count query)
-- header: Motor	Renewal	R3.B1.4

-- converted from the count query. RenewalDate is used for the timestamp because TYReportingSaleDate can be null on these rows, the day 30 offset stays in the filter only, and note that stg.R0_MotorPoliciesEligibleForRenewals is built in the notebook with LyPolicyTypeGroup = 'Home', which has been left as it is.

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
    date_trunc('MINUTE', min(a.RenewalDate)),
    cast(min(a.RenewalDate) as date),
    'R3.B1.4',
    'Motor Renewal - Phone renewal window closes at day 30',
    'Policy'
from    stg.r0_motorpolicieseligibleforrenewals a
Where   (
            a.TYReportingSaleDate >= dateadd(day,30,a.RenewalDate)
        or
            a.TYReportingSaleDate is null
        )
and     a.PolicyOfferNum > 0
Group by a.PolicyCode
;

# In[ ]:
--R3.B1.O1
-- from XX - Episode Reconciliation - Gaps.html, cell 8 (count query)
-- header: Motor	Renewal	R3.B1.O1

-- converted from the count query. The filter guarantees TYReportingSaleDate is populated so it gives the sale timestamp for this outcome, and note that stg.R0_MotorPoliciesEligibleForRenewals is built in the notebook with LyPolicyTypeGroup = 'Home', which has been left as it is.

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
    date_trunc('MINUTE', max(a.TYReportingSaleDate)),
    cast(max(a.TYReportingSaleDate) as date),
    'R3.B1.O1',
    'Motor Renewal - Renewed inside the window',
    'Policy'
from    stg.r0_motorpolicieseligibleforrenewals a
Where   (
            a.TYReportingSaleDate > a.RenewalDate
        )
and     a.PolicyOfferNum > 0
Group by a.PolicyCode
;

# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 97 (count query)
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
			and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000' 
			and     interaction_type = 'sent' 
			and     MessageType  in ( 'EMAIL', 'SMS')
			union
			select  distinct b.PolicyCode 
			from    dlk.EXT_XtremePushResults_Policy a, stg.VanRenewalsJuly b 
			where   campaign_name like '%Van%' 
			and     campaign_name like '%Lapsed%' 
			and     a.PolicyCode = b.PolicyCode 
			and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000' 
			and     interaction_type = 'sent' 
			and     MessageType  in ( 'EMAIL', 'SMS')
		)

# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 98 (count query)
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
			and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000' 
			and     interaction_type = 'sent' 
			and     MessageType  in ( 'EMAIL', 'SMS')
			union
			select  distinct b.PolicyCode 
			from    dlk.EXT_XtremePushResults_Policy a, stg.VanRenewalsJuly b 
			where   campaign_name like '%Van%' 
			and     campaign_name like '%Lapsed%' 
			and     a.PolicyCode = b.PolicyCode 
			and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000' 
			and     interaction_type = 'sent' 
			and     MessageType  in ( 'EMAIL', 'SMS')
		)

# In[ ]:
--R3.B1.O3
-- from XX - Episode Reconciliation - Gaps.html, cell 9 (count query)
-- header: Motor	Renewal	R3.B1.O3

-- converted from the count query. TYReportingSaleDate is null by definition on these rows so RenewalDate carries the timestamp, and note that stg.R0_MotorPoliciesEligibleForRenewals is built in the notebook with LyPolicyTypeGroup = 'Home', which has been left as it is.

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
    date_trunc('MINUTE', min(a.RenewalDate)),
    cast(min(a.RenewalDate) as date),
    'R3.B1.O3',
    'Motor Renewal - Lost',
    'Policy'
from    stg.r0_motorpolicieseligibleforrenewals a
Where   (
            a.TYReportingSaleDate is null
        )
and     a.PolicyOfferNum > 0
Group by a.PolicyCode
;

# In[ ]:
--R6.F1
-- from XX - Episode Reconciliation - Gaps.html, cell 10 (note or select)
-- header: Motor	Renewal	R6.F1
-- Choose the code for duplicate certificates Motor	Renewal	R6.B1.5

-- mirrored from HR6.F1. Straight swap of the renewals table and the two product literals, since the donor only needs PolicyCode and TyPolicyCode, and the literal window of 2026-06-01 to 2026-08-01 is kept exactly as the donor has it.

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
and     d.EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
and     d.EventDescription like '%Suitability%'
and     d.EventDescription not like 'Renewal Offer - %'
AND     (
            d.EventDescription like '%Emailed Document%'
        OR
            d.EventDescription like '%Document Transmitted%'
        )
Group by a.PolicyCode
;

# In[ ]:
--R6.B1

# In[ ]:

--R4.B2.F1
-- mirrored from VR4.B2.F1. The chase snapshot table is shared between Motor and Van so only the PolicyTypeGroup filter and the product literal change, and the chase window of 2026-05-01 to 2026-07-31 is kept exactly as written.

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
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-07-31'
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


--R4.B2.1
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
SELECT  a.TyPolicyCode,
        1,
        'Motor',
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDateTime as date)),
        'R4.B2.1',
        'Motor Renewal - Document request issued',
        'Policy'
FROM    stg.R0_MotorPoliciesEligibleForRenewals  a,
        ods.EventStream                          d 
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.PolicyTypeGroup = 'Motor'
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000' 
and     EventDescription in 
        (
                'New Business - Saved Document - Document Checklist SMS',
                'New Business - Saved Document - Document Checklist Email'
            )
GROUP BY a.TyPolicyCode;


# In[ ]:


--R4.B2.2
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
        'Motor',
        max(date_trunc('MINUTE', `Timestamp`)),
        max(cast(`Timestamp` as date)),
        'R4.B2.2',
        'Motor Renewal - Customer submits documents',
        'Policy'
from    stg.R0_MotorPoliciesEligibleForRenewals a, dlk.MyChill_NewUploadDocumentEvents  b 
Where   a.TyPolicyCode = b.PolicyCode
and     `Timestamp` > add_months((select startTime from stg.episodeeventstream_buildconfig), -1) 
and     `Timestamp` < add_months((select endTime   from stg.episodeeventstream_buildconfig),  1) 
group by a.PolicyCode;


# In[ ]:


--R4.B2.4
-- mirrored from VR4.B2.4. The chase snapshot table is shared between Motor and Van so only the PolicyTypeGroup filter and the product literal change, and the chase window of 2026-05-01 to 2026-07-31 is kept exactly as written.

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
        Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-07-31'
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


--R4.B2.5
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
        'Motor',
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDateTime as date)),
        'R4.B2.5',
        'Motor Renewal - Chase, escalation',
        'Policy'
from    stg.R0_MotorPoliciesEligibleForRenewals     a,
        ods.EventStream                             d 
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     EventDateTime > add_months((select startTime from stg.episodeeventstream_buildconfig), -1) 
and     EventDateTime < add_months((select endTime   from stg.episodeeventstream_buildconfig),  1) 
and     EventDescription like '%Chase%' 
and     EventDescription like '%Final%'  
group by a.PolicyCode;


# In[ ]:


--R4.B2.3
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
        'Motor',
        max(date_trunc('MINUTE', `Timestamp`)),
        max(cast(`Timestamp` as date)),
        'R4.B2.3',
        'Motor Renewal - Documents validated',
        'Policy'
from    stg.R0_MotorPoliciesEligibleForRenewals a, dlk.MyChillWorkflow_DocumentStatus  b 
Where   a.TyPolicyCode = b.PolicyCode
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
and     `Timestamp` < add_months((select endTime   from stg.episodeeventstream_buildconfig),  1)
and     isAccepted = 'true'
group by a.PolicyCode;


# In[ ]:


--R4.B2.O1
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
        'Motor',
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDateTime as date)),
        'R4.B2.O1',
        'Motor Renewal - Cancellation, non-receipt',
        'Policy'
from    stg.R0_MotorPoliciesEligibleForRenewals                   a,
        ods.EventStream                          d 
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     EventDateTime > add_months((select startTime from stg.episodeeventstream_buildconfig), -1) 
and     EventDescription in 
        (
            'Insurer Led Cancelation - Emailed Document - Reg canx email template',
            'Insurer Led Cancelation - Sent To Document Processing - Reg canx email template'
        )
and     a.TyPolicyCode in 
        (SELECT  distinct a.TyPolicyCode
        FROM    stg.R0_MotorPoliciesEligibleForRenewals     a,
                ods.EventStream                             d 
        Where   a.TyPolicyCode = d.SourcePolicyReference
        and     d.EventSourceId = 3 
        and     EventDateTime > add_months((select startTime from stg.episodeeventstream_buildconfig), -1) 
        and     EventDateTime < add_months((select endTime   from stg.episodeeventstream_buildconfig),  1) 
        and     EventDescription like '%Chase%' 
        and     EventDescription like '%Final%' ) 
group by a.PolicyCode;


# In[ ]:


--R4.B2.6
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
        'Motor',
        max(date_trunc('MINUTE', `Timestamp`)),
        max(cast(`Timestamp` as date)),
        'R4.B2.6',
        'Motor Renewal - Documents received and validated',
        'Policy'
from    stg.R0_MotorPoliciesEligibleForRenewals a, dlk.MyChillWorkflow_DocumentStatus  b 
Where   a.TyPolicyCode = b.PolicyCode
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
and     `Timestamp` < add_months((select endTime   from stg.episodeeventstream_buildconfig),  1)
and     isAccepted = 'true'
group by a.PolicyCode;


# In[ ]:


--R6.B1.1

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
    date_trunc('MINUTE', max(EventDateTime)),
    cast(max(EventDateTime) as date),
    'R6.B1.1',
    'Motor Renewal - Cert and disc dispatched',
    'Policy'
from    ods.eventstream a, stg.R0_MotorPoliciesEligibleForRenewals b
Where   a.SourcePolicyReference = b.TyPolicyCode /* new policy */
and     PolicyRetNum = 1
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
and     (   EventDescription like '%Emailed Document%'
        or
            EventDescription like '%Document Transmitted%'
        )
and     EventDescription not like 'Renewal Offer%'
and     EventDescription not like 'Document Chase%'
Group by b.PolicyCode
;


--R6.B1.2

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
    date_trunc('MINUTE', max(EventDateTime)),
    cast(max(EventDateTime) as date),
    'R6.B1.2',
    'Motor Renewal - Cert and disc dispatched',
    'Policy'
from    ods.eventstream a, stg.R0_MotorPoliciesEligibleForRenewals b
Where   a.SourcePolicyReference = b.TyPolicyCode /* new policy */
and     PolicyRetNum = 1
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
and     (   EventDescription like '%Emailed Document%'
        or
            EventDescription like '%Document Transmitted%'
        )
and     EventDescription not like 'Renewal Offer%'
and     EventDescription not like 'Document Chase%'
Group by b.PolicyCode
;


# In[ ]:


--R6.B1.5
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
        'Motor',
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDateTime as date)),
        'R6.B1.5',
        'Motor Renewal - Replacement requested',
        'Policy'
from    stg.R0_MotorPoliciesEligibleForRenewals  a,
        ods.EventStream                          d 
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Motor'
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000' 
and     EventDescription like 'Duplicate Certificate%'
Group by a.PolicyCode;

# Home Acquisitions

# In[ ]:

--HA1
-- converted from the count query. The staging table stg.HA1_HFQ_Quotes is built first in the same cell and the timestamp is the earliest ts_unix on each quote.

-- stg.HA1_HFQ_Quotes is built in the Derived Data section at the top of this notebook.

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
from    stg.HA1_HFQ_Quotes      a
Group by a.QuoteCodeReference
;

# In[ ]:

--HA1.E1
-- without the below conditions we get 70113 entries but it includes workflow/ sms / email so I think only 2/3 rd contacts sent out
-- and QuoteQueryGuid > ''  --> this brings down to 12148 these 2 conditions are a bit iffy as the volumes drop a lot

-- converted from the count query. The count is a plain count of sends so the grain is the recipient email, which the alternative HA1.E1 cell counts distinctly, and the commented out QuoteQueryGuid filter has been left out.

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
    a.email,
    1,
    'Home',
    date_trunc('MINUTE', min(a.`timestamp`)),
    cast(min(a.`timestamp`) as date),
    'HA1.E1',
    'Home Acquisition - Service retrieve',
    'Customer'
from    dlk.EXT_XtremePushResults   a
where   a.`timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and a.`timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.campaign_name like 'Home % TYR %'
and     a.interaction_type = 'sent'
and     a.MessageType = 'EMAIL'
Group by a.email
;

# In[ ]:

--HA1.E2
-- converted from the count query. The distinct CustomerPhoneNumber gives a customer grain and conversationStartTime supplies the timestamp, with the commented out originatingDirection filter left commented out.

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
    a.CustomerPhoneNumber,
    2,
    'Home',
    date_trunc('MINUTE', min(a.conversationStartTime)),
    cast(min(a.conversationStartTime) as date),
    'HA1.E2',
    'Home Acquisition - Outbound sales callback',
    'Customer'
from    stg.A0_genesys_derived_data     a,
        (select ConversationId, max(sessionIndex) sessionIndex
        from    stg.A0_genesys_derived_data
        Where   queueName is not null
        /*and     originatingDirection = 'inbound'*/
        Group by ConversationId
        )   b
where   a.ConversationId = b.ConversationId
and     a.sessionIndex = b.sessionIndex
and     a.queueName = 'OUTBOUND_SALES_HOME'
Group by a.CustomerPhoneNumber
;

--HA1.F1
-- without the below conditions we get 70113 entries but it includes workflow/ sms / email so I think only 2/3 rd contacts sent out

-- converted from the count query as written, following your note that the price comes through in the email,
-- so a quote with no campaign email is a quote that never got a price. The count(*) on a left join is grouped
-- to the quote so a fan out cannot inflate it.

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
         where  `timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
         and    campaign_name like 'Home % TYR %'
         and    interaction_type = 'sent'
         and    MessageType = 'EMAIL'
        ) b
        on a.proposer_email = b.email
where   b.QuoteQueryGuid is null
Group by a.QuoteCodeReference
;

# In[ ]:

--HA0
-- converted. The Home inbound Genesys queue is INBOUND_SALES_HOME, so the filtered table is built here the
-- same way stg.A0_genesys_derived_data_filtered is built for Motor.
-- CAVEAT: the Motor A0 insert excludes callers whose phone number matches an MFQ quote, so it counts only
-- people who did not quote online first. No HFQ table in this notebook names a customer phone column, so that
-- exclusion is not applied here and this will read above the Fabric figure of 924 by however many Home callers
-- had already quoted online. Give me the HFQ phone column and I will add the exclusion.

-- stg.HA0_genesys_derived_data_filtered is built in the Derived Data section at the top of this notebook.

insert INTO
ods.EpisodeEventStream
(
    EventSourceID,
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
    a.ConversationId,
    null,
    2,
    'Home',
    date_trunc('MINUTE', min(a.conversationStartTime)),
    cast(min(a.conversationStartTime) as date),
    'HA0',
    'Home Acquisition - Straight into the CALL CENTRE',
    'Call'
from    stg.HA0_genesys_derived_data_filtered a
Group by a.ConversationId
;

# In[ ]:

--HA0.F1
-- converted. The call duration summary for Home did not exist, so it is built here exactly as the Motor
-- stg.A0F1_genesys_inbound_call_duration_summary is built, with INBOUND_SALES_HOME. The limit 10 on the
-- original count was for eyeballing and is dropped.

-- stg.HA0F1_genesys_inbound_call_duration_summary is built in the Derived Data section at the top of this notebook.

insert INTO
ods.EpisodeEventStream
(
    EventSourceID,
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
    a.ConversationId,
    null,
    2,
    'Home',
    date_trunc('MINUTE', min(a.conversationStartTime)),
    cast(min(a.conversationStartTime) as date),
    'HA0.F1',
    'Home Acquisition - Call wait time, or fails to make contact',
    'Call'
from    stg.HA0F1_genesys_inbound_call_duration_summary a
Where   a.abandoned = 1
and     a.CallWaitTime > 0
Group by a.ConversationId
;

# In[ ]:

--HA2
--*

-- converted from the count query. One row per quote with the first Quotes_DateCreated as the timestamp.

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
from    dlk.hfq_response_quotes     a
where   a.Quotes_DateCreated >= (select startTime from stg.episodeeventstream_buildconfig) and a.Quotes_DateCreated < (select endTime   from stg.episodeeventstream_buildconfig)
Group by a.QuoteCodeReference
;

# In[ ]:

--HA2.F1
-- converted from the count query. It relies on stg.HA1_HFQ_Quotes built in HA1 and takes the timestamp from ts_unix on that table, since only QuoteCodeReference is ever named on stg.hfq_price_requested.

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
left join
        stg.hfq_price_requested     b
            on a.QuoteCodeReference = b.QuoteCodeReference
Where   b.QuoteCodeReference is null
Group by a.QuoteCodeReference
;

# In[ ]:

--HA2.E1
-- mirrored from A2.E1. Straight swap of the XtremePush campaign filter to the Home spelling, with the donor's missing table alias supplied and a group by added over the three non-aggregated items because the donor carries none.

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
        a.QuoteQueryGuid,
        1,
        'Home',
        date_trunc('MINUTE', `timestamp`),
        cast(`timestamp` as date),
        'HA2.E1',
        'Home Acquisition - TYR Campaign',
        'Quote'
from    dlk.EXT_XtremePushResults   a
where	`timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
and		campaign_name like 'Home % TYR %'
and     interaction_type = 'sent'
and     MessageType = 'EMAIL'
and     QuoteQueryGuid > ''
Group by a.QuoteQueryGuid, date_trunc('MINUTE', `timestamp`), cast(`timestamp` as date)
;

# In[ ]:

--HA3
--*

-- converted from the count query. Only the count query in the cell is converted, because the stg.HA3_HomeAcquisitionQuoteInitiated create is not read by it and it declares ImpervalsBot twice.

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
from    dlk.hfq_response_quotes     a
where   a.Quotes_Premium > 0
and     a.Quotes_Outcome = 'PremiumReturned'
and     a.Quotes_DateCreated >= (select startTime from stg.episodeeventstream_buildconfig) and a.Quotes_DateCreated < (select endTime   from stg.episodeeventstream_buildconfig)
Group by a.QuoteCodeReference
;

# In[ ]:

--HA3.F1
-- from XX - Episode Reconciliation - Gaps.html, cell 27 (count query)
-- header: Home	ACQUISITION	HA3.F1

-- converted from the count query. The first of the two counts sets the grain, so one row per QuoteCodeReference with ts_unix as the timestamp and the proposer_email count dropped.

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
    'HA3.F1',
    'Home Acquisition - No price returned, told to call us',
    'Quote'
from    stg.HA1_HFQ_Quotes  a
Where   a.QuoteCodeReference not in
        (
            select  QuoteCodeReference
            from    dlk.hfq_response_quotes
            where   Quotes_Premium > 0
            and     Quotes_Outcome = 'PremiumReturned'
            and     Quotes_DateCreated >= (select startTime from stg.episodeeventstream_buildconfig) and Quotes_DateCreated < (select endTime   from stg.episodeeventstream_buildconfig)
            Group by QuoteCodeReference
        )
Group by a.QuoteCodeReference
;

# In[ ]:

--HA4a
-- converted from the count query. Buying is a completion so the last successful PaymentResponseResponseTimestamp is used, mirroring the Motor A4a treatment of PaymentDate.

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
from    stg.HA1_HFQ_Quotes      a
join    stg.hfq_payments        b
            on a.QuoteCodeReference = b.QuoteReference
Where   b.PaymentResponseResponseActionResultCode = 'SUCCESS'
and     b.PaymentResponseResponseTimestamp >= (select startTime from stg.episodeeventstream_buildconfig) and b.PaymentResponseResponseTimestamp < (select endTime   from stg.episodeeventstream_buildconfig)
Group by a.QuoteCodeReference
;

# In[ ]:

--HA4b
--*
--limit 10

-- converted from the count query. This is the direct Home equivalent of A4b, with the group by channel dropped because it only broke the count down for eyeballing.

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
    date_trunc('MINUTE', min(a.ReportingSaleDate)),
    cast(min(a.ReportingSaleDate) as date),
    'HA4b',
    'Home Acquisition - Agent quotes and converts on the CALL',
    'Policy'
from    stg.GlobalPoliciesSold      a
Where   a.ReportingSaleType = 'New Business'
and     a.PolicyTypeGroup = 'Home'
and     a.QuoteQueryGuid is null
Group by a.PolicyCode
;

# In[ ]:

--HA4.F1

-- built by mirroring A4.F1, the Motor twin of this step, rather than from the pasted query, because the
-- pasted query had two Where clauses so it would not parse. Three differences to check: the Motor twin
-- tests QuoteQueryGuid is NOT null, which is what starts online then calls to complete means, and it
-- spells the channel 'b) Web Assist'. Say the word if you want the literal reading of the pasted version.
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
    1,
    'Home',
    date_trunc('MINUTE', min(a.ReportingSaleDate)),
    cast(min(a.ReportingSaleDate) as date),
    'HA4.F1',
    'Home Acquisition - Web assist: starts online, then calls to complete',
    'Policy'
from    stg.GlobalPoliciesSold      a
Where   a.ReportingSaleType = 'New Business'
and     a.PolicyTypeGroup = 'Home'
and     a.QuoteQueryGuid is not null
and     a.Channel = 'b) Web Assist'
Group by a.QuoteQueryGuid, a.PolicyCode
;

--HA4b.O1

# In[ ]:

--HA5
--* 
--count(*)
--limit 10

-- converted from the count query. A successful payment is a completion so the latest PaymentResponseResponseTimestamp is used.

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
from    stg.HFQ_payments    a
where   a.PaymentResponseResponseActionResultCode = 'SUCCESS'
and     a.PaymentResponseResponseTimestamp >= (select startTime from stg.episodeeventstream_buildconfig) and a.PaymentResponseResponseTimestamp < (select endTime   from stg.episodeeventstream_buildconfig)
Group by a.QuoteReference
;

# In[ ]:

--HA5.F1
--limit 10

-- converted from the count query. Friction is a first occurrence so the earliest declined PaymentResponseResponseTimestamp is used.

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
from    stg.HFQ_payments    a
where   a.PaymentResponseResponseActionResultCode = 'DECLINED'
and     a.PaymentResponseResponseTimestamp >= (select startTime from stg.episodeeventstream_buildconfig) and a.PaymentResponseResponseTimestamp < (select endTime   from stg.episodeeventstream_buildconfig)
Group by a.QuoteReference
;

# In[ ]:

--HA5.B1
--*
--PaymentResponseType,
--PaymentResponseResponseActionResultCode = 'DECLINED' 

-- BLOCK HEADER. HA5.B1 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from HA5.B1.1, HA5.B1.2, HA5.B1.3, HA5.B1.4, HA5.B1.5.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

# In[ ]:

--HA5.1
       --count(distinct a.PolicyCode)

-- converted from the count query. ods.EventStream is only read here, and the last EventDateTime per policy is used in line with the Motor document dispatch steps.

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
        date_trunc('MINUTE', max(d.EventDateTime)),
        cast(max(d.EventDateTime) as date),
        'HA5.1',
        'Home Acquisition - Terms of business sent',
        'Policy'
from    stg.GlobalPoliciesSold                   a,
        ods.EventStream                          d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
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
-- converted from the count query. This mirrors the Motor A6 treatment, taking the last derived SaleDate per policy as the timestamp and keeping the DAY 1 campaign filter.

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
        date_trunc('MINUTE', max(coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01'))),
        cast(max(coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01')) as date),
        'HA6',
        'Home Acquisition - Documents requested',
        'Policy'
from    edw.exp_mychill_chase_daily_snapshot_home   a
Where   coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.PolicyType = 'New Business'
and     a.Campaign = 'DAY 1'
and     case
    when Gap_In_Cov_Ltr_Status = 'O' then 1
    when Val_For_Spec_Item_Status = 'O' then 1
    when PPS_Num_Status = 'O' then 1
    When Identification_Status = 'O' then 1
    when Finance_Form_Status = 'O' then 1
    when Digital_Journey_Status = 'O' then 1
    else 0
End = 1
Group by a.PolicyCode
;

# In[ ]:

--HA6.F1
-- from XX - Episode Reconciliation - Gaps.html, cell 29 (count query)
-- header: HA6.F1

-- converted from the count query. The derived SaleDate is carried out of the subquery as SaleDateTime so the insert has a timestamp, and the having count greater than one is kept untouched.

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
        date_trunc('MINUTE', max(x.SaleDateTime)),
        cast(max(x.SaleDateTime) as date),
        'HA6.F1',
        'Home Acquisition - Number of chases before the customer submits',
        'Policy'
From    (
            select  PolicyCode,
                    max(coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01')) SaleDateTime
            from    edw.exp_mychill_chase_daily_snapshot_home   a
            Where   coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
            and     a.PolicyType = 'New Business'
            and     case
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
        )   x
Group by x.PolicyCode
;

# In[ ]:
--HA6.B1
--HA6.B1.F1

# In[ ]:

--HA7
-- converted from the count query. Built on the A7 pattern, reading ods.EventStream and taking the last EventDateTime per policy.

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
        date_trunc('MINUTE', max(d.EventDateTime)),
        cast(max(d.EventDateTime) as date),
        'HA7',
        'Home Acquisition - Policy documents dispatched',
        'Policy'
from    stg.globalpoliciessold                   a,
        ods.eventstream                          d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
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

--HA7.B1
--HA7.B1.1
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
        date_trunc('MINUTE', max(d.EventDateTime)),
        cast(max(d.EventDateTime) as date),
        'HA7.B1.1',
        'Home Acquisition - Policy documents dispatched',
        'Policy'
from    stg.globalpoliciessold                   a,
        ods.eventstream                          d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.ReportingSaleType = 'New Business'
and     (
            d.EventDescription like 'New Business - Emailed Document - %'
        or  d.EventDescription like 'New Business - Document Transmitted - %'
        )
and     (
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

# In[ ]:

--HA7.B1.2
-- converted from the count query. The whole document description like list is kept as it stands and the last EventDateTime per policy is used for the dispatch.

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
        date_trunc('MINUTE', max(d.EventDateTime)),
        cast(max(d.EventDateTime) as date),
        'HA7.B1.2',
        'Home Acquisition - Document pack dispatched',
        'Policy'
from    stg.globalpoliciessold                   a,
        ods.eventstream                          d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.ReportingSaleType = 'New Business'
and     (
            d.EventDescription like 'New Business - Emailed Document - %'
        or  d.EventDescription like 'New Business - Document Transmitted - %'
        )
and     (
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

# In[ ]:

--HA6.B1.1
-- mirrored from A6.B1.1. Straight swap of the chase snapshot to the Home table, with the donor's PolicyTypeGroup filter dropped because the Home snapshot is already Home only, as the notebook's other Home chase inserts have it.

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
        date_trunc('MINUTE', max(x.SaleDateTime)),
        cast(max(x.SaleDateTime) as date),
        'HA6.B1.1',
        'Home Acquisition - Document request issued',
        'Policy'
From    (
            select  PolicyCode,
                    max(coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01')) SaleDateTime
            from    edw.exp_mychill_chase_daily_snapshot_home   a
            Where   coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
            and     a.PolicyType = 'New Business'
            Group by PolicyCode
        )   x
Group by x.PolicyCode
;

# In[ ]:

--HA6.B1.2
-- from XX - Episode Reconciliation - Gaps.html, cell 30 (count query)
-- header: HA6.B1.2

-- converted from the count query. This is the Home equivalent of A6.B1.2, with the first upload Timestamp per policy and the column left unqualified exactly as the original query has it.

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
        date_trunc('MINUTE', min(`Timestamp`)),
        cast(min(`Timestamp`) as date),
        'HA6.B1.2',
        'Home Acquisition - Customer submits documents',
        'Policy'
from    stg.GlobalPoliciesSold                  a,
        dlk.MyChill_NewUploadDocumentEvents     b
Where   a.PolicyCode = b.PolicyCode
and     a.ReportingSaleType = 'New Business'
and     a.PolicyTypeGroup = 'Home'
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
Group by b.PolicyCode
;

# In[ ]:
--HA6.B1.4
-- from XX - Episode Reconciliation - Gaps.html, cell 31 (count query)
-- header: HA6.B1.4

-- converted from the count query. The derived SaleDate is carried out of the subquery as SaleDateTime and the DAY 1 campaign filter is kept.

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
        date_trunc('MINUTE', max(x.SaleDateTime)),
        cast(max(x.SaleDateTime) as date),
        'HA6.B1.4',
        'Home Acquisition - Chase, first reminder',
        'Policy'
From    (
            select  PolicyCode,
                    max(coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01')) SaleDateTime
            from    edw.exp_mychill_chase_daily_snapshot_home   a
            Where   coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
            and     a.PolicyType = 'New Business'
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
--HA6.B1.5
-- from XX - Episode Reconciliation - Gaps.html, cell 32 (count query)
-- header: HA6.B1.5

-- converted from the count query. Same shape as the first reminder step with the campaign not equal to DAY 1 filter kept, and the last chase date per policy as the timestamp.

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
        date_trunc('MINUTE', max(x.SaleDateTime)),
        cast(max(x.SaleDateTime) as date),
        'HA6.B1.5',
        'Home Acquisition - Chase, escalation',
        'Policy'
From    (
            select  PolicyCode,
                    max(coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01')) SaleDateTime
            from    edw.exp_mychill_chase_daily_snapshot_home   a
            Where   coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
            and     a.PolicyType = 'New Business'
            and     case
                when Gap_In_Cov_Ltr_Status = 'O' then 1
                when Val_For_Spec_Item_Status = 'O' then 1
                when PPS_Num_Status = 'O' then 1
                When Identification_Status = 'O' then 1
                when Finance_Form_Status = 'O' then 1
                when Digital_Journey_Status = 'O' then 1
                else 0
            End = 1
            and     a.campaign <> 'DAY 1'
            Group by PolicyCode
        )   x
Group by x.PolicyCode
;

# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 33 (count query)
-- header: HA6.B1.5
SELECT  count(distinct a.PolicyCode)
FROM    stg.GlobalPoliciesSold                   a,
        ods.EventStream                          d 
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ReportingSaleType = 'New Business' 
and     EventDescription like '%Chase%' 
and     EventDescription like '%Final%'

# In[ ]:
--HA6.B1.3
-- from XX - Episode Reconciliation - Gaps.html, cell 34 (note or select)
-- header: HA6.B1.3

-- converted from the count query. The group by isAccepted and the limit were only there to eyeball the split, so this mirrors A6.B1.3 and keeps accepted documents only.

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
        date_trunc('MINUTE', min(`Timestamp`)),
        cast(min(`Timestamp`) as date),
        'HA6.B1.3',
        'Home Acquisition - Documents validated',
        'Policy'
from    stg.GlobalPoliciesSold                  a,
        dlk.MyChillWorkflow_DocumentStatus      b
Where   a.PolicyCode = b.PolicyCode
and     a.ReportingSaleType = 'New Business'
and     a.PolicyTypeGroup = 'Home'
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
and     b.isAccepted = 'true'
Group by b.PolicyCode
;

# In[ ]:
--HA6.B1.O1
-- from XX - Episode Reconciliation - Gaps.html, cell 35 (count query)
-- header: HA6.B1.O1 -- no doc escalation and then cancellation

-- converted from the count query. This is the Home equivalent of A6.B1.O1, keeping the final chase subquery and taking the last cancellation EventDateTime per policy.

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
        date_trunc('MINUTE', max(d.EventDateTime)),
        cast(max(d.EventDateTime) as date),
        'HA6.B1.O1',
        'Home Acquisition - Cancellation, non-receipt',
        'Policy'
from    stg.GlobalPoliciesSold                   a,
        ods.EventStream                          d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.ReportingSaleType = 'New Business'
and     d.EventDescription in
        (
            'Insurer Led Cancelation - Emailed Document - Reg canx email template',
            'Insurer Led Cancelation - Sent To Document Processing - Reg canx email template'
        )
and     a.PolicyCode in
        (SELECT  distinct a.PolicyCode
        from    stg.GlobalPoliciesSold                   a,
                ods.EventStream                          d
        Where   a.PolicyCode = d.SourcePolicyReference
        and     d.EventSourceId = 3
        and     d.PolicyTypeGroup = 'Home'
        and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
        and     a.ReportingSaleType = 'New Business'
        and     d.EventDescription like '%Chase%'
        and     d.EventDescription like '%Final%' )
Group by a.PolicyCode
;

# In[ ]:
--HA6.B1.6
-- mirrored from A6.B1.6. Straight swap of the product literals with stg.GlobalPoliciesSold filtered to PolicyTypeGroup Home, joined to dlk.MyChillWorkflow_DocumentStatus on isAccepted true, and the sibling HA6.B1.3 min aggregate and Group by adopted so the insert is one row per policy.

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
        date_trunc('MINUTE', min(`Timestamp`)),
        cast(min(`Timestamp`) as date),
        'HA6.B1.6',
        'Home Acquisition - Documents received and validated',
        'Policy'
from    stg.GlobalPoliciesSold                  a,
        dlk.MyChillWorkflow_DocumentStatus      b
Where   a.PolicyCode = b.PolicyCode
and     a.ReportingSaleType = 'New Business'
and     a.PolicyTypeGroup = 'Home'
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
and     b.isAccepted = 'true'
Group by b.PolicyCode
;

# In[ ]:

--HA7.B1.1
--HA7.B1.2
--HA7.B1.3
-- mirrored from A7.B1.3. Straight swap of the product literals, keeping stg.GlobalPoliciesSold and the product neutral Terms Of Business descriptions, with ods.EventStream read at PolicyTypeGroup Home.

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
        max(cast(EventDate as date)),
        'HA7.B1.3',
        'Home Acquisition - Customer receipt, implicit',
        'Policy'
FROM    stg.GlobalPoliciesSold                    a,
        ods.EventStream                          d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     ReportingSaleType = 'New Business'
and     EventDescription in (
            'New Business - Document Transmitted - Terms Of Business',
            'New Business - Emailed Document - Terms Of Business'
            )

Group by a.PolicyCode
;

# In[ ]:

--HA7.B1.4
-- mirrored from A7.B1.4. Straight swap of the chase snapshot to the Home table, keeping the donor's six document status columns, which the Home snapshot does carry, and dropping the PolicyTypeGroup filter.

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
        date_trunc('MINUTE', max(x.SaleDateTime)),
        cast(max(x.SaleDateTime) as date),
        'HA7.B1.4',
        'Home Acquisition - Non-arrival chase, inbound',
        'Policy'
From    (
            select  PolicyCode,
                    max(coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01')) SaleDateTime
            from    edw.exp_mychill_chase_daily_snapshot_home   a
            Where   coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
            and     a.PolicyType = 'New Business'
            and     case
                when Gap_In_Cov_Ltr_Status = 'O' then 1
                when Val_For_Spec_Item_Status = 'O' then 1
                when PPS_Num_Status = 'O' then 1
                When Identification_Status = 'O' then 1
                when Finance_Form_Status = 'O' then 1
                when Digital_Journey_Status = 'O' then 1
                else 0
            End = 1
            Group by PolicyCode
        )   x
Group by x.PolicyCode
;

# In[ ]:

--HA7.B1.5
-- mirrored from A7.B1.5. The Motor donor is used because Home sells through stg.GlobalPoliciesSold, and the Duplicate Certificate filter is kept as written, matching the notebook's own HR6.B1.5 replacement requested insert for Home.

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
        max(cast(EventDate as date)),
        'HA7.B1.5',
        'Home Acquisition - Replacement requested',
        'Policy'
FROM    stg.GlobalPoliciesSold                    a,
        ods.EventStream                          d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     ReportingSaleType = 'New Business'
and     EventDescription in (
            'Duplicate Certificate - Document Transmitted - Certificate'
            )

Group by a.PolicyCode
;

# In[ ]:

--HR0
-- from XX - Episode Reconciliation - Gaps.html, cell 11 (count query)
-- header: Home	Renewal	HR0

-- converted from the count query. Timestamp is dateadd(day, -40, RenewalDate) because the step is the T-40 window opening, and the original query carries no date window of its own, so no build config run window applies.

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
    date_trunc('MINUTE', min(dateadd(day, -40, a.RenewalDate))),
    cast(min(dateadd(day, -40, a.RenewalDate)) as date),
    'HR0',
    'Home Renewal - Renewal window opens at T-40',
    'Policy'
from    stg.R0_HomePoliciesEligibleForRenewals a
Group by a.PolicyCode
;

# In[ ]:
--HR0.F1
-- from XX - Episode Reconciliation - Gaps.html, cell 13 (note or select)
-- header: Home	Renewal	HR0.F1
-- and     EventType = 'Quotation Provided' 
-- use only Quotation Provided for this count -- 681 -- the unique policycodes involved are 681 too

-- converted from the count query. The Group by EventType was dropped and the cell's own commented EventType = 'Quotation Provided' filter was applied because the cell says that is the 681 count, and the claims window from 2026-05-01 to 2026-08-01 is kept exactly as it is so no build config run window applies.

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
    date_trunc('MINUTE', min(b.TransactionDate)),
    cast(min(b.TransactionDate) as date),
    'HR0.F1',
    'Home Renewal - Declared claims not recorded',
    'Policy'
from    dlk.EXT_Home_QS_ClaimDetails    a,
        dlk.ext_home_qs_policydetails   b,
        stg.R0_HomePoliciesEligibleForRenewals c
Where   a.HomeRiskId = upper(b.RiskId)
and     b.TransactionDate between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
and     b.PolicyCode = c.PolicyCode
and     b.EventType = 'Quotation Provided'
Group by b.PolicyCode
;

# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 83 (note or select)
-- header: Home	Renewal	HR0.F1
select	HomeClaimType, count(distinct b.PolicyCode)
from	dlk.EXT_Home_QS_ClaimDetails    a, 
        dlk.ext_home_qs_policydetails   b
Where	a.HomeRiskId = upper(b.RiskId)
and		TransactionDate >= (select startTime from stg.episodeeventstream_buildconfig) and TransactionDate < (select endTime   from stg.episodeeventstream_buildconfig)
Group by HomeClaimType
order by 2 
-- use only Quotation Provided for this count -- 681 -- the unique policycodes involved are 681 too

# In[ ]:
--HR0.F2
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
    date_trunc('MINUTE', min(b.TransactionDate)),
    cast(min(b.TransactionDate) as date),
    'HR0.F2',
    'Home Renewal - Renewal held letter issued',
    'Policy'
from    dlk.EXT_Home_QS_ClaimDetails    a,
        dlk.ext_home_qs_policydetails   b,
        stg.R0_HomePoliciesEligibleForRenewals c
Where   a.HomeRiskId = upper(b.RiskId)
and     b.TransactionDate between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
and     b.PolicyCode = c.PolicyCode
and     b.EventType = 'Policy Renewal Accepted'
Group by b.PolicyCode
;
--HR0.F3
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
    date_trunc('MINUTE', min(b.TransactionDate)),
    cast(min(b.TransactionDate) as date),
    'HR0.F3',
    'Home Renewal - No terms from the insurer, so no offer is made',
    'Policy'
from    dlk.EXT_Home_QS_ClaimDetails    a,
        dlk.ext_home_qs_policydetails   b,
        stg.R0_HomePoliciesEligibleForRenewals c
Where   a.HomeRiskId = upper(b.RiskId)
and     b.TransactionDate between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
and     b.PolicyCode = c.PolicyCode
and     b.EventType = 'Policy Lapsed'
Group by b.PolicyCode
;
--HR0.1

# In[ ]:

--HR1a
-- converted from the count query. The staging table is built first and kept as written, including its renewal lookback from 2026-05-01 to 2026-08-01, so no build config run window applies.

-- stg.HR1a_Home_Renewals_EmailOffered is built in the Derived Data section at the top of this notebook.

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
    a.SourcePolicyReference,
    1,
    'Home',
    date_trunc('MINUTE', min(a.OfferedDateTime)),
    cast(min(a.OfferedDateTime) as date),
    'HR1a',
    'Home Renewal - Renewal invitation sent by EMAIL',
    'Policy'
from    stg.HR1a_Home_Renewals_EmailOffered a
Group by a.SourcePolicyReference
;

# In[ ]:

--HR1b
-- converted from the count query. The staging table is built first and kept as written, including its renewal lookback from 2026-05-01 to 2026-08-01, so no build config run window applies.

-- stg.HR1b_Home_Renewals_PostOffered is built in the Derived Data section at the top of this notebook.

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
    a.SourcePolicyReference,
    1,
    'Home',
    date_trunc('MINUTE', min(a.OfferedDateTime)),
    cast(min(a.OfferedDateTime) as date),
    'HR1b',
    'Home Renewal - Renewal invitation sent by POST',
    'Policy'
from    stg.HR1b_Home_Renewals_PostOffered a
Group by a.SourcePolicyReference
;

# In[ ]:

--HR2
-- converted from the count query. Grain is policy from count(distinct PolicyCode) and the window is the T-40 to T+40 renewal lookback built from RenewalDate, which is kept exactly as it is so no build config run window applies.

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
    date_trunc('MINUTE', min(b.`Timestamp`)),
    cast(min(b.`Timestamp`) as date),
    'HR2',
    'Home Renewal - Customer logs in to portal',
    'Policy'
from    (
            select  left(PolicyCode,6) as ClientCode, dateadd(day, -40, RenewalDate) RenewalStartDate, PolicyCode, dateadd(day, 40, RenewalDate) RenewalEndDate
            from stg.R0_HomePoliciesEligibleForRenewals
        )   a,
        dlk.appliedrenewals_successfulloginevent b
Where   a.ClientCode = b.PortfolioCode
and     b.`Timestamp` > a.RenewalStartDate
and     b.`Timestamp` < a.RenewalEndDate
Group by a.PolicyCode
;

# In[ ]:

--HR2.F1
-- from XX - Episode Reconciliation - Gaps.html, cell 14 (count query)
-- header: Home	Renewal	HR2.F1
-- Group by QueueName, wrapupCodeName

-- converted from the count query. Genesys ConversationId goes into EventSourceId at call grain with SourceSystemId 2, and the renewal lookback from 2026-05-01 to 2026-08-01 is kept exactly as it is so no build config run window applies.

insert INTO
ods.EpisodeEventStream
(
    EventSourceId,
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
    date_trunc('MINUTE', min(a.ConversationStartTime)),
    cast(min(a.ConversationStartTime) as date),
    'HR2.F1',
    'Home Renewal - Customer does not accept the price',
    'Call'
from    dlk.genesys_session_summary a
Where   a.wrapupCode <> 'ININ-WRAP-UP-TIMEOUT'
and     a.ConversationStartTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
and     a.QueueName = 'INBOUND_Home_Renewals'
and     a.OriginatingDirection = 'inbound'
and     a.wrapupCodeName in
        (
            'UNFAVOURABLE_NCD',
            'REQUOTED_NOT_SOLD',
            'UNDECIDED/SHOPPING AROUND',
            'UNFAVOURABLE_COMPETITOR'
        )
Group by a.ConversationId
;

# In[ ]:

--HR2.B1

-- stg.HomeRenewalScvCustomerKeys, stg.HomeRenewalsDoingHFQ are built in the Derived Data section at the top of this notebook.

-- BLOCK HEADER. HR2.B1 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from HR2.B1.1, HR2.B1.2, HR2.B1.3.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

# In[ ]:

--HR2.B1.F1
-- converted from the count query. The original already uses the build config run window on PaymentResponseResponseTimestamp and it is carried over unchanged, with the payment success taken as a completion so max is used.

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
    date_trunc('MINUTE', max(b.PaymentResponseResponseTimestamp)),
    cast(max(b.PaymentResponseResponseTimestamp) as date),
    'HR2.B1.F1',
    'Home Renewal - The customer shops the renewal',
    'Policy'
from    stg.HomeRenewalsDoingHFQ  a,
        stg.HFQ_Payments          b
Where   b.PaymentResponseResponseActionResultCode = 'SUCCESS'
and     b.QuoteReference = a.QuoteCodeReference
and     b.PaymentResponseResponseTimestamp >= (select startTime from stg.episodeeventstream_buildconfig)
and     b.PaymentResponseResponseTimestamp < (select endTime   from stg.episodeeventstream_buildconfig)
Group by a.PolicyCode
;

# In[ ]:

--HR1.E1
-- from XX - Episode Reconciliation - Gaps.html, cell 15 (count query)
-- header: Home	Renewal	HR1.E1

-- converted from the count query. The limit 100 was dropped and the campaign window from 2026-06-01 to 2026-09-01 is kept exactly as it is, so no build config run window applies.

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
    date_trunc('MINUTE', min(a.`timestamp`)),
    cast(min(a.`timestamp`) as date),
    'HR1.E1',
    'Home Renewal - Renewal campaigns: CRM',
    'Policy'
from    dlk.EXT_XtremePushResults_Policy   a,
        stg.R0_HomePoliciesEligibleForRenewals b
where   a.`timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and add_months((select endTime   from stg.episodeeventstream_buildconfig),  1)
and     a.PolicyCode = b.PolicyCode
and     a.campaign_name like '%Home%'
and     a.campaign_name like '%Renewals%'
and     a.MessageType in ( 'EMAIL', 'SMS')
and     a.interaction_type = 'sent'
Group by a.PolicyCode
;

# In[ ]:
--HR1.E1.F1
-- from XX - Episode Reconciliation - Gaps.html, cell 16 (count query)
-- header: Home	Renewal	HR1.E1.F1

-- converted from the count query. This is an outcome so max of the campaign timestamp is used, and the campaign window from 2026-06-01 to 2026-09-01 is kept exactly as it is so no build config run window applies.

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
    'HR1.E1.F1',
    'Home Renewal - Programme fails and the renewal date is missed',
    'Policy'
from    dlk.EXT_XtremePushResults_Policy   a,
        stg.R0_HomePoliciesEligibleForRenewals b
where   a.`timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and add_months((select endTime   from stg.episodeeventstream_buildconfig),  1)
and     a.PolicyCode = b.PolicyCode
and     a.campaign_name like '%Home%'
and     a.campaign_name like '%Renewals%'
and     a.MessageType in ( 'EMAIL', 'SMS')
and     a.interaction_type = 'sent'
and     coalesce(b.TYReportingSaleDate, b.RenewalDate) > b.RenewalDate
Group by a.PolicyCode
;

# In[ ]:

--HR3a
-- converted from the count query. The join keys were qualified as a.PolicyCode to b.PolicyCodeForRenewal, and the T-60 to T+40 renewal lookback is kept exactly as it is so no build config run window applies.

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
    date_trunc('MINUTE', max(b.`Timestamp`)),
    cast(max(b.`Timestamp`) as date),
    'HR3a',
    'Home Renewal - Customer renews ONLINE',
    'Policy'
from    (
            select  left(PolicyCode,6) as ClientCode, dateadd(day, -60, RenewalDate) RenewalStartDate, PolicyCode, dateadd(day, 40, RenewalDate) RenewalEndDate
            from stg.R0_HomePoliciesEligibleForRenewals
        )   a,
        dlk.AppliedRenewals_PaymentSuccess b
Where   a.PolicyCode = b.PolicyCodeForRenewal
and     b.`Timestamp` > a.RenewalStartDate
and     b.`Timestamp` < a.RenewalEndDate
Group by a.PolicyCode
;

# In[ ]:

--HR3b
-- converted from the count query. Timestamp is TYReportingSaleDate, which the original select already names, and the original query carries no date window of its own, so no build config run window applies.

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
    'Home',
    date_trunc('MINUTE', max(a.TYReportingSaleDate)),
    cast(max(a.TYReportingSaleDate) as date),
    'HR3b',
    'Home Renewal - Customer renews on an INBOUND call',
    'Policy'
from    stg.R0_HomePoliciesEligibleForRenewals a
Where   a.PolicyRetNum = 1
and     a.Channel = 'a) IB'
Group by a.TyPolicyCode
;

# In[ ]:

--HR3b.F1
insert INTO
ods.EpisodeEventStream
(
    EventSourceId,
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
    date_trunc('MINUTE', min(a.ConversationStartTime)),
    cast(min(a.ConversationStartTime) as date),
    'HR3b.F1',
    'Home Renewal - Call wait time, or fails to make contact',
    'Call'
from    dlk.genesys_session_summary a
Where   a.wrapupCode <> 'ININ-WRAP-UP-TIMEOUT'
and     a.ConversationStartTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
and     a.QueueName = 'INBOUND_Home_Renewals'
and     a.OriginatingDirection = 'inbound'
and     a.wrapupCodeName in
        (
            'NO_ANSWER'
        )
Group by a.ConversationId
;

# In[ ]:

--HR3.B1

-- stg.HR3B1_LapsedThisYearPolicy is built in the Derived Data section at the top of this notebook.

-- BLOCK HEADER. HR3.B1 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from HR3.B1.1, HR3.B1.2.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

# In[ ]:

--HR3.O1
-- converted from the count query. The count(*) is one row per lapsed policy so it groups to PolicyCode on the staging table built in HR3.B1, and the original query carries no date window of its own, so no build config run window applies.

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
    'HR3.O1',
    'Home Renewal - Policy lapsed',
    'Policy'
from    stg.HR3B1_LapsedThisYearPolicy a
Group by a.PolicyCode
;

# In[ ]:

--HR4
-- converted from the count query. Timestamp is TYReportingSaleDate, which the notebook uses on this table for the same cohort, and the original query carries no date window of its own, so no build config run window applies.

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
    'Home',
    date_trunc('MINUTE', max(a.TYReportingSaleDate)),
    cast(max(a.TYReportingSaleDate) as date),
    'HR4',
    'Home Renewal - Payment taken',
    'Policy'
from    stg.R0_HomePoliciesEligibleForRenewals a
Where   a.PolicyRetNum = 1
Group by a.TyPolicyCode
;

# In[ ]:

--HR4.B2
-- from XX - Episode Reconciliation - Gaps.html, cell 18 (note or select)
-- header: docs asked for HR4.B2
-- header: Home	Renewal	HR4.B2.F1 --  day 1 should be the full chase and then day 7 / 14 / 20 should reduce as people submit docs and get them approved..
-- header: -- these voluems are messed up for some reason -- so redone below on the 08th
--and Campaign = 'DAY 1'

-- BLOCK HEADER. HR4.B2 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from HR4.B2.1, HR4.B2.2, HR4.B2.3, HR4.B2.4, HR4.B2.5, HR4.B2.6.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 24 (count query)
-- header: docs asked for HR4.B2 -- HR4.B2.F1
-- header: Home	Renewal	HR4.B2.F1 --  day 1 should be the full chase and then day 7 / 14 / 20 should reduce as people submit docs and get them approved..
-- header: -- these voluems are messed up for some reason -- so redone below on the 08th - recalculated below for both cells
select  count(distinct a.PolicyCode) 
from    edw.EXP_MyChill_Chase_Daily_Snapshot_Home a, stg.R0_HomePoliciesEligibleForRenewals b 
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-07-31' 
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
--HR4.B2.F1
-- see the HR4.B2 cell: XX - Episode Reconciliation - Gaps.html cell 18 covers HR4.B2, HR4.B2.F1
-- see the HR4.B2 cell: XX - Episode Reconciliation - Gaps.html cell 24 covers HR4.B2, HR4.B2.F1

-- mirrored from VR4.B2.F1. The chase snapshot swaps to the Home table with PolicyTypeGroup set to Home, the open document status list is cut back to the seven statuses the notebook's own Home chase queries read because the Motor and Van vehicle statuses are not on the Home table, and the literal window of 2026-05-01 to 2026-07-31 is kept exactly as the donor has it.

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
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-07-31'
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

--HR4a
-- converted from the count query. The staging table is built first because HR4c reads it, no pay in full filter is added because the original query applies none, and the T-60 to T+40 renewal lookback is kept exactly as it is so no build config run window applies.

-- stg.HR4_HomeRenewalsOnlinePayments is built in the Derived Data section at the top of this notebook.

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
    date_trunc('MINUTE', max(a.PaymentDateTime)),
    cast(max(a.PaymentDateTime) as date),
    'HR4a',
    'Home Renewal - Pay in full',
    'Policy'
from    stg.HR4_HomeRenewalsOnlinePayments a
Group by a.PolicyCode
;

# In[ ]: 

--HR4c
-- HR4a and HR4c -- Possible loan but old finance or new loan?  

-- converted from the count query. The Group by PaymentType became a PaymentType = 'Instalments' filter, the value the notebook already uses on this column for the same monthly agreement step on Motor, and the staging table it reads carries the renewal lookback so no build config run window applies here.

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
    date_trunc('MINUTE', max(x.PaymentDateTime)),
    cast(max(x.PaymentDateTime) as date),
    'HR4c',
    'Home Renewal - New monthly agreement',
    'Policy'
from    (
        select  a.PolicyCode, a.PaymentDateTime, b.PaymentType
        from    stg.HR4_HomeRenewalsOnlinePayments      a,
                dlk.AppliedRenewals_PaymentSuccess      b
        Where   a.ClientCode = b.PortfolioCode
        and     b.`Timestamp` = a.PaymentDateTime
        ) x
Where   x.PaymentType = 'Instalments'
Group by x.PolicyCode
;

# In[ ]: 

--HR5
-- mirrored from R5. Straight swap of the renewals table and the product literals, with the donor's a.EventDateTime qualified as d.EventDateTime because the timestamp comes from ods.EventStream and not from the renewals table, the suitability statement list left verbatim, and the literal window of 2026-05-01 to 2026-08-01 kept as the donor has it.

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
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
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
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
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

--HR6.F1
-- converted from the count query. The wrapper subquery was flattened and the inner Group by EventDescription dropped so the grain is the distinct PolicyCode the outer count uses, and the window from 2026-06-01 to 2026-08-01 is kept exactly as it is so no build config run window applies.

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
    'HR6.F1',
    'Home Renewal - The suitability letter barely goes out',
    'Policy'
FROM    stg.R0_HomePoliciesEligibleForRenewals  a,
        ods.EventStream                          d
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
and     d.EventDescription like '%Suitability%'
and     d.EventDescription not like 'Renewal Offer - %'
AND     (
            d.EventDescription like '%Emailed Document%'
        OR
            d.EventDescription like '%Document Transmitted%'
        )
Group by a.PolicyCode
;

# In[ ]: 

--HR6.B1
-- BLOCK HEADER. HR6.B1 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from HR6.B1.1, HR6.B1.2, HR6.B1.3, HR6.B1.4, HR6.B1.5.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

# In[ ]: 

--HR2.B1.1
-- converted from the count query. The staging table is built first because later steps read it, the source is HFQ so SourceSystemId is 2, and the lookback from 2026-05-01 is kept exactly as it is so no build config run window applies.

-- stg.HR2B1_1_Base is built in the Derived Data section at the top of this notebook.

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
    date_trunc('MINUTE', min(a.QuoteStartDatetime)),
    cast(min(a.QuoteStartDatetime) as date),
    'HR2.B1.1',
    'Home Renewal - Re-quote started from the renewal price',
    'Policy'
from    stg.HR2B1_1_Base a
Group by a.PolicyCode
;

# In[ ]: 

--HR2.B1.2
-- ideally pull the last record or the least QuoteBestPrice for eventstream

-- converted from the count query. The event is that a price came back, not which price, so the join to
-- stg.hfq_prices only proves one exists and the author's open question about last record against lowest
-- QuoteBestPrice does not affect the insert. Grain follows HR2.B1.1, one row per policy.

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
    date_trunc('MINUTE', min(a.QuoteStartDatetime)),
    cast(min(a.QuoteStartDatetime) as date),
    'HR2.B1.2',
    'Home Renewal - New price returned',
    'Policy'
from    stg.HR2B1_1_Base    a,
        stg.hfq_prices      b
Where   a.QuoteCodeReference = b.QuoteCodeReference
Group by a.PolicyCode
;

# In[ ]: 

--HR2.B1.2.F1

-- from Gaps II. The anti-join against the priced HFQ responses, so it is the mirror of HR2.B1.2.
-- QuoteStartDateTime supplies the timestamp and the grain is the policy, matching HR2.B1.1 and
-- HR2.B1.2. SourceSystemId is 2 because the quote is HFQ.
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
    'HR2.B1.2.F1',
    'Home Renewal - No price returned, or the quote is abandoned',
    'Policy'
from    stg.HomeRenewalsDoingHFQ    a
left join
        (select QuoteCodeReference
        from    dlk.HFQ_Response_Quotes
        where   Quotes_Premium <> 0
        and     Quotes_Outcome = 'PremiumReturned'
        Group by QuoteCodeReference) b
        on a.QuoteCodeReference = b.QuoteCodeReference
Where   b.QuoteCodeReference is null
Group by a.PolicyCode
;

# In[ ]: 

--HR2.B1.3.F1
-- converted from the count query. stg.hfq_prices has no timestamp in the notebook so the QuoteStartDatetime carried on stg.HR2B1_1_Base is used, and that base table already applies its own lookback so no build config run window applies here.

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
    date_trunc('MINUTE', max(a.QuoteStartDatetime)),
    cast(max(a.QuoteStartDatetime) as date),
    'HR2.B1.3.F1',
    'Home Renewal - New price is worse than the renewal offer',
    'Policy'
from    stg.HR2B1_1_Base a,
        stg.hfq_prices   b
Where   a.QuoteCodeReference = b.QuoteCodeReference
and     a.TyEurGrossPremium < b.QuoteBestPrice
Group by a.PolicyCode
;

# In[ ]: 

--HR2.B1.O1
-- converted from the count query. Timestamp is the QuoteStartDatetime carried on stg.HR2B1_1_Base because stg.hfq_prices has no timestamp in the notebook, and that base table already applies its own lookback so no build config run window applies here.

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
    date_trunc('MINUTE', max(a.QuoteStartDatetime)),
    cast(max(a.QuoteStartDatetime) as date),
    'HR2.B1.O1',
    'Home Renewal - Renews on the renewal offer',
    'Policy'
from    stg.HR2B1_1_Base a,
        stg.hfq_prices   b
Where   a.QuoteCodeReference = b.QuoteCodeReference
and     a.TyEurGrossPremium = a.RenEurPremOffer
and     a.PolicyRetNum = 1
Group by a.PolicyCode
;

# In[ ]: 

--HR2.B1.O2
-- converted from the count query. Timestamp is the QuoteStartDatetime carried on stg.HR2B1_1_Base because stg.hfq_prices has no timestamp in the notebook, and that base table already applies its own lookback so no build config run window applies here.

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
    date_trunc('MINUTE', max(a.QuoteStartDatetime)),
    cast(max(a.QuoteStartDatetime) as date),
    'HR2.B1.O2',
    'Home Renewal - Renews on a new price',
    'Policy'
from    stg.HR2B1_1_Base a,
        stg.hfq_prices   b
Where   a.QuoteCodeReference = b.QuoteCodeReference
and     a.TyEurGrossPremium < a.RenEurPremOffer
and     a.PolicyRetNum = 1
Group by a.PolicyCode
;

# In[ ]: 

--HR2.B1.O3
-- converted from the count query. The left join and the is null test are kept as they are, the timestamp is the QuoteStartDatetime on stg.HR2B1_1_Base, and that base table already applies its own lookback so no build config run window applies here.

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
    date_trunc('MINUTE', max(a.QuoteStartDatetime)),
    cast(max(a.QuoteStartDatetime) as date),
    'HR2.B1.O3',
    'Home Renewal - Buys elsewhere, no renewal',
    'Policy'
from    stg.HR2B1_1_Base a
left join stg.R0_HomePoliciesEligibleForRenewals b
        on a.PolicyCode = b.PolicyCode and b.PolicyRetNum = 1
Where   b.PolicyCode is null
Group by a.PolicyCode
;

# In[ ]: 

--HR3.B1.1
-- converted from the count query. The count(*) is one row per eligible policy so it groups to PolicyCode, the limit 10 was dropped, the event time is RenewalDate, and the original query carries no date window of its own, so no build config run window applies.

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
    date_trunc('MINUTE', min(a.RenewalDate)),
    cast(min(a.RenewalDate) as date),
    'HR3.B1.1',
    'Home Renewal - Renewal date passes with no renewal',
    'Policy'
from    stg.R0_HomePoliciesEligibleForRenewals a
Where   a.RenewalDate < a.TYReportingSaleDate
Group by a.PolicyCode
;

# In[ ]: 

--HR3.B1.2
-- mirrored from R3.B1.2. The Motor donor was taken because it uses min of the send timestamp for the start of the sequence, the renewals table and the campaign name filter swap to Home, and the literal window of 2026-05-01 to 2026-08-10 is kept exactly as the donor has it.

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
            and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
            and     interaction_type = 'sent'
            and     MessageType  in ( 'EMAIL', 'SMS')
            union
            select  distinct b.PolicyCode, a.`timestamp` as SentTimestamp
            from    dlk.EXT_XtremePushResults_Policy a, stg.R0_HomePoliciesEligibleForRenewals b
            where   campaign_name like '%Home%'
            and     campaign_name like '%Lapsed%'
            and     a.PolicyCode = b.PolicyCode
            and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
            and     interaction_type = 'sent'
            and     MessageType  in ( 'EMAIL', 'SMS')
        ) x
Group by x.PolicyCode
;

# In[ ]:

--HR3.B1.2.F1
-- mirrored from VR3.B1.2.F1. The Van donor was taken because it carries the bounce clause that makes the policy unreachable, which is the shape the notebook's own Home count query for this step already uses, and the literal window of 2026-05-01 to 2026-08-10 is kept exactly as the donor has it.

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
and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
and     interaction_type = 'sent'
and     MessageType  in ( 'EMAIL', 'SMS')
and     a.PolicyCode not in
        (
            select  distinct a.PolicyCode
            from    dlk.EXT_XtremePushResults_Policy a, stg.R0_HomePoliciesEligibleForRenewals b
            where   campaign_name like '%Home%'
            and     campaign_name like '%Lapsed%'
            and     a.PolicyCode = b.PolicyCode
            and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
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
            and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
            and     interaction_type in ('bounce')
            and     MessageType  in ( 'EMAIL', 'SMS')
        )
Group by a.PolicyCode
;

# In[ ]:

--HR3.B1.O1
-- from XX - Episode Reconciliation - Gaps.html, cell 22 (count query)
-- header: Home	Renewal	HR3.B1.O1

-- converted from the count query. This is an outcome so max of the campaign timestamp is used, and the lapsed campaign window from 2026-06-01 to 2026-09-01 is kept exactly as it is so no build config run window applies.

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
    'HR3.B1.O1',
    'Home Renewal - Renewed inside the window',
    'Policy'
from    dlk.EXT_XtremePushResults  a,
        stg.R0_HomePoliciesEligibleForRenewals b
where   a.`timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and add_months((select endTime   from stg.episodeeventstream_buildconfig),  1)
and     a.PolicyCode = b.PolicyCode
and     a.campaign_name like '%Home%'
and     a.campaign_name like '%Lapsed%'
and     a.MessageType in ( 'EMAIL', 'SMS')
and     a.interaction_type = 'sent'
and     coalesce(b.TYReportingSaleDate, b.RenewalDate) > b.RenewalDate
Group by a.PolicyCode
;

# In[ ]:
--HR3.B1.O3
-- from XX - Episode Reconciliation - Gaps.html, cell 23 (count query)
-- header: Home	Renewal	HR3.B1.O3

-- converted from the count query. This is a lost outcome so max of the campaign timestamp is used, and the lapsed campaign window from 2026-06-01 to 2026-09-01 is kept exactly as it is so no build config run window applies.

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
    'HR3.B1.O3',
    'Home Renewal - Lost',
    'Policy'
from    dlk.EXT_XtremePushResults  a,
        stg.R0_HomePoliciesEligibleForRenewals b
where   a.`timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and add_months((select endTime   from stg.episodeeventstream_buildconfig),  1)
and     a.PolicyCode = b.PolicyCode
and     a.campaign_name like '%Home%'
and     a.campaign_name like '%Lapsed%'
and     a.MessageType in ( 'EMAIL', 'SMS')
and     a.interaction_type = 'sent'
and     b.TYReportingSaleDate is null
Group by a.PolicyCode
;

# In[ ]: 

--HR4.B2.1
-- converted from the count query. The distinct TyPolicyCode becomes the source policy reference and the group by key, and the window from 2026-06-01 to 2026-08-01 is kept exactly as it is so no build config run window applies.

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
    'Home',
    date_trunc('MINUTE', min(d.EventDateTime)),
    cast(min(d.EventDateTime) as date),
    'HR4.B2.1',
    'Home Renewal - Document request issued',
    'Policy'
FROM    stg.R0_HomePoliciesEligibleForRenewals  a,
        ods.EventStream                          d
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
and     d.EventDescription in
        (
            'New Business - Saved Document - Document Checklist SMS',
            'New Business - Saved Document - Document Checklist Email'
        )
Group by a.TyPolicyCode
;

# In[ ]: 

--HR4.B2.2
-- converted from the count query. The limit 100 was dropped, submission is a completion so max is used, and the window from 2026-05-01 to 2026-09-01 is kept exactly as it is so no build config run window applies.

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
    date_trunc('MINUTE', max(b.`Timestamp`)),
    cast(max(b.`Timestamp`) as date),
    'HR4.B2.2',
    'Home Renewal - Customer submits documents',
    'Policy'
from    stg.R0_HomePoliciesEligibleForRenewals a,
        dlk.MyChill_NewUploadDocumentEvents  b
Where   a.TyPolicyCode = b.PolicyCode
and     b.`Timestamp` > add_months((select startTime from stg.episodeeventstream_buildconfig), -1)
and     b.`Timestamp` < add_months((select endTime   from stg.episodeeventstream_buildconfig),  1)
Group by b.PolicyCode
;

# In[ ]: 

--HR4.B2.4

-- from Gaps II. Built like the Motor twin R4.B2.4, with min(CreateDate) pulled out of a derived table
-- so the chase has a timestamp. The 2026-05-01 to 2026-07-31 window is a renewals lookback rather than
-- the run window, so it is kept as the literal the query had.
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
    date_trunc('MINUTE', min(x.FirstDate)),
    cast(min(x.FirstDate) as date),
    'HR4.B2.4',
    'Home Renewal - Chase, first reminder',
    'Policy'
from    (
        select  PolicyCode , min(CreateDate) FirstDate
        from    edw.EXP_MyChill_Chase_Daily_Snapshot_Home a
        Where   coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-07-31'
        and     PolicyTypeGroup = 'Home'
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
        and     Campaign = 'DAY 1'
        and     PolicyType = 'Renewals'
        Group by PolicyCode
        ) x
Group by x.PolicyCode
;

# In[ ]: 

--HR4.B2.5
-- converted from the count query. The final chase is a last occurrence so max is used, and the window from 2026-06-01 to 2026-09-01 is kept exactly as it is so no build config run window applies.

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
    date_trunc('MINUTE', max(d.EventDateTime)),
    cast(max(d.EventDateTime) as date),
    'HR4.B2.5',
    'Home Renewal - Chase, escalation',
    'Policy'
FROM    stg.R0_HomePoliciesEligibleForRenewals     a,
        ods.EventStream                             d
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.EventDateTime > add_months((select startTime from stg.episodeeventstream_buildconfig), -1)
and     d.EventDateTime < add_months((select endTime   from stg.episodeeventstream_buildconfig),  1)
and     d.EventDescription like '%Chase%'
and     d.EventDescription like '%Final%'
Group by a.PolicyCode
;

# In[ ]: 

--HR4.B2.3
-- mirrored from R4.B2.3. Straight swap of the renewals table and the product literal, with the build config run window, the extra cut off at 2026-09-01 and the isAccepted filter all kept exactly as the donor has them.

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
and     `Timestamp` < add_months((select endTime   from stg.episodeeventstream_buildconfig),  1)
and     isAccepted = 'true'
Group by a.PolicyCode
;

# In[ ]: 

--HR4.B2.O1
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
    'HR4.B2.O1',
    'Home Renewal - Cancellation, non-receipt',
    'Policy'
FROM    stg.R0_HomePoliciesEligibleForRenewals  a,
        ods.EventStream                          d
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
and     d.EventDescription not like 'Renewal Offer - %'
and     d.EventDescription like '%Insurer Led Cancelation % Reg canx email template%'
AND     (
            d.EventDescription like '%Emailed Document%'
        OR
            d.EventDescription like '%Document Transmitted%'
        )
Group by a.PolicyCode
;

# In[ ]: 

--HR4.B2.6
-- mirrored from R4.B2.6. Straight swap of the renewals table and the product literal, with the build config run window, the extra cut off at 2026-09-01 and the isAccepted filter all kept exactly as the donor has them.

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
and     `Timestamp` < add_months((select endTime   from stg.episodeeventstream_buildconfig),  1)
and     isAccepted = 'true'
Group by a.PolicyCode
;

# In[ ]:

--HR6.B1.1
-- mirrored from VR6.B1.1. Straight swap of stg.VanRenewalsJuly for the Home renewals table and of the product literal, with no PolicyTypeGroup filter added to ods.EventStream because the donor carries none and the join to TyPolicyCode already confines the rows to Home renewals, and the literal window of 2026-05-01 to 2026-08-10 kept exactly as written.

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
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
and     (   EventDescription like '%Emailed Document%'
        or
            EventDescription like '%Document Transmitted%'
        )
and     EventDescription not like 'Renewal Offer%'
and     EventDescription not like 'Document Chase%'
Group by b.PolicyCode
;

# In[ ]:

--HR6.B1.2
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
    'HR6.B1.2',
    'Home Renewal - Policy documents dispatched',
    'Policy'
from    ods.eventstream a, stg.R0_HomePoliciesEligibleForRenewals b
Where   a.SourcePolicyReference = b.TyPolicyCode /* new policy */
and     PolicyRetNum = 1
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
and     (   EventDescription like '%Emailed Document%'
        or
            EventDescription like '%Document Transmitted%'
        )
and     EventDescription not like 'Renewal Offer%'
and     EventDescription not like 'Document Chase%'
Group by b.PolicyCode
;
--HR6.B1.5
-- mirrored from R6.B1.5. Straight swap of the renewals table and the product literals, with the Duplicate Certificate filter and the literal window of 2026-05-01 to 2026-08-01 kept exactly as the donor has them.

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
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
and     EventDescription like 'Duplicate Certificate%'
Group by a.PolicyCode
;

# In[ ]:

--HM1

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
        a.ConversationId,
        1,
        'Home',
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'HM1',
        'Home MTA - Customer calls Chill with a change request',
        'Call'
from    stg.A0_genesys_derived_data a left join stg.VM0_van_phone_numbers b
        on a.CustomerPhoneNumber = b.CustomerPhone
Where   QueueName in ('INBOUND_HomeChangeOther',
'INBOUND_HomeChangeBuildCost')
and     originatingDirection = 'inbound' 
and     b.CustomerPhone is null
Group by a.ConversationId

--HM1.F1

-- stg.AbandonedHomeMTACalls is built in the Derived Data section at the top of this notebook.
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
        a.ConversationId,
        1,
        'Home',
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'HM1.F1',
        'Home MTA - Customer calls Chill with a change request',
        'Call'
from    stg.A0_genesys_derived_data a, stg.AbandonedHomeMTACalls b 
Where   a.ConversationId = b.ConversationId 
Group by a.ConversationId
--HM2

-- NOTHING TO BUILD: no data for this step, marked in Gaps II as ignore.

--HM2.O1
-- and     PremiumType = 'Mid Term Adjustment'

-- converted from the count query. Timestamp taken from PolicyCancelDate on stg.JulyPolicyState, which is the only cancellation date column that table carries.

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
    date_trunc('MINUTE', max(b.PolicyCancelDate)),
    cast(max(b.PolicyCancelDate) as date),
    'HM2.O1',
    'Home MTA - Cancellation, declined or not proceeded with',
    'Policy'
from    stg.JJulyMTAs a, stg.JulyPolicyState b
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Home'
and     PolicyStatusDesc in (
     'Cancelled Mid Term' , 'Lapsed for Transfer'
)
Group by a.PolicyCode
;

--HM3
-- and     PremiumType = 'Mid Term Adjustment'

-- converted from the count query. Timestamp taken from ReportingSaleDate on stg.JulyPolicyState because stg.JJulyMTAs only carries the integer posting date.

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
    date_trunc('MINUTE', min(b.ReportingSaleDate)),
    cast(min(b.ReportingSaleDate) as date),
    'HM3',
    'Home MTA - Customer accepts',
    'Policy'
from    stg.JJulyMTAs a, stg.JulyPolicyState b
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Home'
and     PolicyStatusDesc not in (
    'Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer'
)
Group by a.PolicyCode
;

--HM4.B1
-- BLOCK HEADER. HM4.B1 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from HM4.B1.1, HM4.B1.2, HM4.B1.3, HM4.B1.4, HM4.B1.5, HM4.B1.6.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

--HM4.B1.F1
-- converted from the count query. The chase lookback window of 2026-05-01 to 2026-07-31 is kept exactly as it was rather than being replaced by the build config window.

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
    date_trunc('MINUTE', min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
    cast(min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01')) as date),
    'HM4.B1.F1',
    'Home MTA - Chases before the customer submits, and documents never submitted',
    'Policy'
from    edw.EXP_MyChill_Chase_Daily_Snapshot_Home a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-07-31'
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
Group by a.PolicyCode
;

# In[ ]:

--HM4
-- from XX - Episode Reconciliation - Gaps.html, cell 43 (note or select)
-- header: Home	MTA	HM4

-- converted from the count query. The group by TransactionDescription and the premium and fee sums were only a breakdown for eyeballing, so the insert is one row per policy with a ReportingSaleDate timestamp.

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
    date_trunc('MINUTE', min(b.ReportingSaleDate)),
    cast(min(b.ReportingSaleDate) as date),
    'HM4',
    'Home MTA - Money due on the change',
    'Policy'
from    stg.JJulyMTAs a, stg.JulyPolicyState b
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Home'
and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
and     (
            CCYGrossPremium <> 0
        or
            CCYFees <> 0 )
Group by b.PolicyCode
;

# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 44 (count query)
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
--HM4.F1

-- NOTHING TO BUILD: no data for this step, marked in Gaps II.

--HM4a

-- NOTHING TO BUILD: not available, the query is commented out in Gaps II.

--HM4c
-- converted from the count query. The premium and fee sums were dropped because the event stream holds no amount, and the timestamp comes from ReportingSaleDate on stg.JulyPolicyState.

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
    date_trunc('MINUTE', min(b.ReportingSaleDate)),
    cast(min(b.ReportingSaleDate) as date),
    'HM4c',
    'Home MTA - No money moves',
    'Policy'
from    stg.JJulyMTAs a, stg.JulyPolicyState b
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Home'
and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
and     (
            CCYGrossPremium = 0
        and
            CCYFees = 0 )
Group by b.PolicyCode
;

--HM5

-- NOTHING TO BUILD: no data for this step, marked in Gaps II.

--HM6
-- converted from the count query. Reads ods.EventStream and writes to ods.EpisodeEventStream, with max EventDateTime for the last document reissue.

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
    'Home',
    date_trunc('MINUTE', max(EventDateTime)),
    cast(max(EventDateTime) as date),
    'HM6',
    'Home MTA - Policy documents reissued',
    'Policy'
from    ods.EventStream
Where   SourcePolicyReference in
        (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Home'
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

--HM6.B1
--HM4.B1.1
-- converted from the second query in this cell, the one you marked 28, per your instruction.
-- The derived table that carried only PolicyCode was flattened so the SaleDate timestamp is reachable.
-- Note this arm carries no Campaign filter, so it will overlap with HM4.B1.4 which filters Campaign = 'DAY 1'.

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
    'HM4.B1.1',
    'Home MTA - Document request issued',
    'Policy'
from    edw.exp_mychill_chase_daily_snapshot_home a
Where	coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig)
and     coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') <  (select endTime   from stg.episodeeventstream_buildconfig)
and     a.PolicyType = 'New Business'
and case
        when a.Gap_In_Cov_Ltr_Status = 'O' then 1
        when a.Val_For_Spec_Item_Status = 'O' then 1
        when a.PPS_Num_Status = 'O' then 1
        When a.Identification_Status = 'O' then 1
        when a.Finance_Form_Status = 'O' then 1
        when a.Digital_Journey_Status = 'O' then 1
        else 0
    End = 1
and     a.PolicyCode in
        (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     b.PolicyTypeGroup = 'Home'
            and     b.PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
        )
Group by a.PolicyCode
;

--HM4.B1.2
-- converted from the count query. Timestamp from the upload event Timestamp, using min for the first submission by the customer.

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
    'HM4.B1.2',
    'Home MTA - Customer submits documents',
    'Policy'
from    (
                select  b.PolicyCode
                from    stg.JJulyMTAs a, stg.JulyPolicyState b
                Where   a.PolicyCode = b.PolicyCode
                and     PolicyTypeGroup = 'Home'
                and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
            ) a,
        dlk.MyChill_NewUploadDocumentEvents  b
Where   a.PolicyCode = b.PolicyCode
and     b.`Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and b.`Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
Group by b.PolicyCode
;

--HM4.B1.4
-- converted from the count query. The derived table that only carried PolicyCode was flattened so that the SaleDate timestamp on the chase snapshot is available.

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
    date_trunc('MINUTE', min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
    cast(min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01')) as date),
    'HM4.B1.4',
    'Home MTA - Chase, first reminder',
    'Policy'
from    edw.exp_mychill_chase_daily_snapshot_home a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
and case
        when Gap_In_Cov_Ltr_Status = 'O' then 1
        when Val_For_Spec_Item_Status = 'O' then 1
        when PPS_Num_Status = 'O' then 1
        When Identification_Status = 'O' then 1
        when Finance_Form_Status = 'O' then 1
        when Digital_Journey_Status = 'O' then 1
        else 0
    End = 1
and     Campaign = 'DAY 1'
and     a.PolicyCode in
        (
                select  b.PolicyCode
                from    stg.JJulyMTAs a, stg.JulyPolicyState b
                Where   a.PolicyCode = b.PolicyCode
                and     PolicyTypeGroup = 'Home'
                and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
        )
Group by a.PolicyCode
;

--HM4.B1.5
-- converted from the count query. Same shape as the first reminder but on the DAY 20 campaign, with the derived table flattened to reach the SaleDate timestamp.

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
    date_trunc('MINUTE', min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
    cast(min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01')) as date),
    'HM4.B1.5',
    'Home MTA - Chase, escalation',
    'Policy'
from    edw.exp_mychill_chase_daily_snapshot_home a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
and case
        when Gap_In_Cov_Ltr_Status = 'O' then 1
        when Val_For_Spec_Item_Status = 'O' then 1
        when PPS_Num_Status = 'O' then 1
        When Identification_Status = 'O' then 1
        when Finance_Form_Status = 'O' then 1
        when Digital_Journey_Status = 'O' then 1
        else 0
    End = 1
and     Campaign = 'DAY 20'
and     a.PolicyCode in
        (
                select  b.PolicyCode
                from    stg.JJulyMTAs a, stg.JulyPolicyState b
                Where   a.PolicyCode = b.PolicyCode
                and     PolicyTypeGroup = 'Home'
                and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
        )
Group by a.PolicyCode
;

--HM4.B1.3
-- converted from the count query. The group by isAccepted was only a breakdown for eyeballing so it was dropped, and no isAccepted filter was added because the original query did not have one.

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
    date_trunc('MINUTE', max(b.`Timestamp`)),
    cast(max(b.`Timestamp`) as date),
    'HM4.B1.3',
    'Home MTA - Documents validated',
    'Policy'
from    (
                select  b.PolicyCode
                from    stg.JJulyMTAs a, stg.JulyPolicyState b
                Where   a.PolicyCode = b.PolicyCode
                and     PolicyTypeGroup = 'Home'
                and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
            )  a, dlk.MyChillWorkflow_DocumentStatus  b
Where   a.PolicyCode = b.PolicyCode
and     b.`Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and b.`Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
Group by b.PolicyCode
;

--HM4.B1.O1
-- converted from the count query. The group by EventDescription was a breakdown for eyeballing so it was dropped, and the timestamp is the latest cancellation document event.

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
    date_trunc('MINUTE', max(d.EventDateTime)),
    cast(max(d.EventDateTime) as date),
    'HM4.B1.O1',
    'Home MTA - Cancellation, non-receipt',
    'Policy'
FROM    (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Home'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
        )                                       a,
        (select  distinct PolicyCode
            from edw.exp_mychill_chase_daily_snapshot_home a
            Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
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
and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     EventDescription like '% CXL %'
and     (   EventDescription like '%Emailed Document%'
        or
            EventDescription like '%Document Transmitted%'
        )
and     a.PolicyCode = d.SourcePolicyReference
and     a.PolicyCode = b.PolicyCode
Group by a.PolicyCode
;

--HM4.B1.6

-- from Gaps II. Same shape as HM4.B1.3 with the isAccepted test added, which is how A6.B1.6 marks
-- documents received and validated. The Group by isAccepted in the count was an eyeballing breakdown
-- and is dropped. The July window is the run window so it takes the build config.
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
    date_trunc('MINUTE', max(b.`Timestamp`)),
    cast(max(b.`Timestamp`) as date),
    'HM4.B1.6',
    'Home MTA - Documents received and validated',
    'Policy'
from    (
                select  b.PolicyCode
                from    stg.JJulyMTAs a, stg.JulyPolicyState b
                Where   a.PolicyCode = b.PolicyCode
                and     PolicyTypeGroup = 'Home'
                and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
            )  a, dlk.MyChillWorkflow_DocumentStatus  b
Where   a.PolicyCode = b.PolicyCode
and     b.`Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and b.`Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
and     b.isAccepted = 'true'
Group by b.PolicyCode
;

--HM6.B1.1
-- converted from the count query. The stray comment terminator at the head of the cell was removed and the document description list was kept exactly as written.

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
    date_trunc('MINUTE', max(d.EventDateTime)),
    cast(max(d.EventDateTime) as date),
    'HM6.B1.1',
    'Home MTA - Policy documents dispatched',
    'Policy'
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
and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
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
Group by a.PolicyCode
;

--HM6.B1.2

-- from Gaps II. The redundant Emailed Document or Document Transmitted test was dropped because the
-- six description IN list already covers it. min(d.EventDateTime) is when the pack went out, and the
-- July window is the run window so it takes the build config.
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
    'HM6.B1.2',
    'Home MTA - Document pack dispatched',
    'Policy'
FROM    (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Home'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
        )                                       a,
        ods.EventStream                          d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     d.EventDescription in
        (
            'New Business - Emailed Document - Terms Of Business',
            'New Business - Emailed Document - Cover Letter',
            'New Business - Emailed Document - 04 - Suitability Statement',
            'New Business - Document Transmitted - 04 - Suitability Statement',
            'New Business - Document Transmitted - Terms Of Business',
            'New Business - Document Transmitted - Cover Letter'
        )
Group by a.PolicyCode
;

--HM6.B1.3
--HC1a
-- converted from the count query. The staging table build is kept because later HC steps read it. The
-- cancellation request itself carries no timestamp on edw.tbl_fact_policy_mtc, so PolicyCancelDate from
-- stg.JulyPolicyState is used. That is when the cancellation took effect, not when the customer asked.
-- The ShortDescription filter is the one the original breakdown query used to isolate customer requests.

-- stg.JulyHomeCancellations, stg.JulyMotorCancellations, stg.JulyVanCancellations are built in the Derived Data section at the top of this notebook.

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
    date_trunc('MINUTE', max(b.PolicyCancelDate)),
    cast(max(b.PolicyCancelDate) as date),
    'HC1a',
    'Home Cancellation - Customer asks to cancel',
    'Policy'
from    edw.tbl_fact_policy_mtc a,
        stg.JulyPolicyState     b
Where   a.PolicyCode = b.PolicyCode
and     a.PolicyTypeGroup = 'Home'
and     a.EffectiveDate = (select effectiveDate from stg.episodeeventstream_buildconfig)
and     (
            a.ShortDescription like 'Client%'
        or
            a.ShortDescription like 'Customer%'
        )
Group by a.PolicyCode
;

--HC1a.F1
-- converted from the select in this cell, now that HC1b.F1 has been removed as its duplicate. The grain is
-- the policy and the timestamp is PolicyCancelDate from stg.JulyPolicyState, the same choice made for HC1a.
-- CAVEAT: the step is described as "No retention or save attempt anywhere" but the query filters
-- ShortDescription like '%NCT%', which matches the wording of the HC1b.F1 step you removed. Worth a look.

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
    date_trunc('MINUTE', max(b.PolicyCancelDate)),
    cast(max(b.PolicyCancelDate) as date),
    'HC1a.F1',
    'Home Cancellation - No retention or save attempt anywhere',
    'Policy'
from    edw.tbl_fact_policy_mtc a,
        stg.JulyPolicyState     b
Where   a.PolicyCode = b.PolicyCode
and     a.PolicyTypeGroup = 'Home'
and     a.EffectiveDate = (select effectiveDate from stg.episodeeventstream_buildconfig)
and     a.ShortDescription like '%NCT%'
Group by a.PolicyCode
;

# In[ ]:
--HC2
-- converted from the count query. The derived table was flattened so that the SaleDate timestamp on the chase snapshot could be used, and the join to the cancellation list is unchanged.

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
    date_trunc('MINUTE', min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
    cast(min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01')) as date),
    'HC2',
    'Home Cancellation - Document chase, reminder',
    'Policy'
from    edw.exp_mychill_chase_daily_snapshot_home a,
        stg.JulyHomeCancellations   b
Where   left(a.PolicyCode,6) = b.ClientCode
and	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
and case
        when Gap_In_Cov_Ltr_Status = 'O' then 1
        when Val_For_Spec_Item_Status = 'O' then 1
        when PPS_Num_Status = 'O' then 1
        When Identification_Status = 'O' then 1
        when Finance_Form_Status = 'O' then 1
        when Digital_Journey_Status = 'O' then 1
        else 0
    End = 1
Group by a.PolicyCode
;

--HC3
-- converted from the count query. Same as HC2 but keeping the Campaign not equal to DAY 1 filter and the author's comment about escalation chases.

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
    date_trunc('MINUTE', min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
    cast(min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01')) as date),
    'HC3',
    'Home Cancellation - Document chase, escalation',
    'Policy'
from    edw.exp_mychill_chase_daily_snapshot_home a,
        stg.JulyHomeCancellations   b
Where   left(a.PolicyCode,6) = b.ClientCode
and	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
and case
        when Gap_In_Cov_Ltr_Status = 'O' then 1
        when Val_For_Spec_Item_Status = 'O' then 1
        when PPS_Num_Status = 'O' then 1
        When Identification_Status = 'O' then 1
        when Finance_Form_Status = 'O' then 1
        when Digital_Journey_Status = 'O' then 1
        else 0
    End = 1
and     Campaign <> 'DAY 1'  /* first is request and all the next are escalation I think - when we go daily build, we could do that */
Group by a.PolicyCode
;

--HC4
-- converted from the count query. Reads ods.EventStream and writes to ods.EpisodeEventStream, with max EventDateTime because a final notice is the last chase.

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
    a.SourcePolicyReference,
    1,
    'Home',
    date_trunc('MINUTE', max(a.EventDateTime)),
    cast(max(a.EventDateTime) as date),
    'HC4',
    'Home Cancellation - Final notice',
    'Policy'
from    ods.eventstream             a,
        stg.JulyHomeCancellations   b
Where   left(a.SourcePolicyReference,6) = b.ClientCode
and     a.PolicyTypeGroup = 'Home'
and     a.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and a.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.EventSourceId = 3
and     a.EventDescription like '%Document Chase%'
and     a.EventDescription like '%Final Notice%'
and     (   a.EventDescription like '%Emailed Document%'
        or
            a.EventDescription like '%Document Transmitted%'
        )
Group by a.SourcePolicyReference
;

--HC5
-- converted from the count query. Max EventDateTime is used because the cancellation document is the completion of the journey.

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
    a.SourcePolicyReference,
    1,
    'Home',
    date_trunc('MINUTE', max(a.EventDateTime)),
    cast(max(a.EventDateTime) as date),
    'HC5',
    'Home Cancellation - Cancellation processed',
    'Policy'
from    ods.eventstream             a,
        stg.JulyHomeCancellations   b
Where   left(a.SourcePolicyReference,6) = b.ClientCode
and     a.PolicyTypeGroup = 'Home'
and     a.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and a.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.EventSourceId = 3
and     a.EventDescription like '%CXL%'
and     (   a.EventDescription like '%Emailed Document%'
        or
            a.EventDescription like '%Document Transmitted%'
        )
Group by a.SourcePolicyReference
;

--HC6

-- mirrored from VC6, which Gaps II gave us. Straight product swap of the ods.eventstream filter to
-- Home, keeping the Relay description and the build config run window exactly as the donor has them.
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
    a.SourcePolicyReference,
    1,
    'Home',
    date_trunc('MINUTE', min(a.EventDateTime)),
    cast(min(a.EventDateTime) as date),
    'HC6',
    'Home Cancellation - Cancellation confirmation sent',
    'Policy'
from    ods.eventstream     a
Where   a.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and a.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.EventSourceId = 3
and     a.PolicyTypeGroup = 'Home'
and     a.EventDescription = 'Insurer Led Cancelation - Emailed Document - Reg canx email template'
Group by a.SourcePolicyReference
;

--HARR.1

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
    date_trunc('MINUTE', max(timestamp)),
    cast(max(timestamp) as date),
    'HARR.1',
    'Home Arrears - Missed payment detected',
    'Policy'
from    dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
and     campaign_name = 'Arrears - Chase 1 - 1 Day Past'
and     MessageType in ('SMS', 'EMAIL')
and     PolicyTypeGroup = 'Home'
group by PolicyCode

--HARR.2

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
    date_trunc('MINUTE', max(timestamp)),
    cast(max(timestamp) as date),
    'HARR.2',
    'Home Arrears - Arrears chase',
    'Policy'
from    dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
and     campaign_name = 'Arrears - Chase 1 - 1 Day Past'
and     MessageType in ('SMS', 'EMAIL')
and     PolicyTypeGroup = 'Home'
group by PolicyCode

--HARR.O1

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
    date_trunc('MINUTE', max(timestamp)),
    cast(max(timestamp) as date),
    'HARR.O1',
    'Home Arrears - Arrears cleared',
    'Policy'
from    dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
and     timestamp < dateadd(day,-28,getdate()) --ensure chaser should have been sent
and     campaign_name = 'Arrears - Chase 1 - 1 Day Past'
and     MessageType in ('SMS', 'EMAIL')
and     PolicyTypeGroup = 'Home'
and     PolicyCode not in
        (select policycode from dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
         where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
         and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
         and     campaign_name = 'Arrears - Chase 5 - 28 Days Past'
         and     MessageType in ('SMS', 'EMAIL')
         and     PolicyTypeGroup = 'Home')
group by PolicyCode

--HARR.3

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
    date_trunc('MINUTE', max(timestamp)),
    cast(max(timestamp) as date),
    'HARR.3',
    'Home Arrears - Loan defaults, arrears not cleared',
    'Policy'
from    dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
and     campaign_name = 'Arrears - Chase 5 - 28 Days Past'
and     MessageType in ('SMS', 'EMAIL')
and     PolicyTypeGroup = 'Home'
group by PolicyCode

--HARR.O2

-- converted from the count query. The Insurer Led subquery now projects EventDateTime as well as the
-- reference so the insert has a timestamp, and min is used because the escalation is the first forced
-- cancellation event. Both July windows are the run window so they take the build config.
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
    a.SourcePolicyReference,
    1,
    'Home',
    date_trunc('MINUTE', min(a.EventDateTime)),
    cast(min(a.EventDateTime) as date),
    'HARR.O2',
    'Home Arrears - Escalation to forced cancellation',
    'Policy'
from            (select  distinct SourcePolicyReference, EventDateTime
                from    ods.eventstream        a
                Where   EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
                and     EventSourceId = 3
                and     PolicyTypeGroup = 'Home'
                and     EventDescription like 'Insurer Led%') a,
                (select  distinct b.PolicyCode
                from    dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b
                where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
                and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig)
                --and     campaign_name = 'Arrears - Chase 5 - 28 Days Past'
                and     MessageType in ('SMS', 'EMAIL')
                and     PolicyTypeGroup = 'Home') b
Where   a.SourcePolicyReference = b.PolicyCode
Group by a.SourcePolicyReference
;

--HCL1a

-- REBUILT on the back of VCL1a from Gaps II. The earlier version read stg.DocRequestClientCodes, the
-- Doc Request staging table, which was the wrong population. This one goes through the INBOUND_Claims
-- queue and stg.Home_PhoneNumbers, built here the same way stg.Van_PhoneNumbers is. SourceSystemId is 2
-- because the call comes from Genesys.
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
    date_trunc('MINUTE', min(b.conversationStartTime)),
    cast(min(b.conversationStartTime) as date),
    'HCL1a',
    'Home Claims - Home claim reported',
    'Policy'
from    stg.Home_PhoneNumbers                       a,
        stg.Claims_genesys_derived_data_filtered    b
Where   b.CustomerPhoneNumber = a.CustomerPhone
Group by a.PolicyCode
;

--HCL1b

-- converted from the count query. TransactionDate and the claim type sit on the policy details and
-- claim details tables the way HR0.F1 reads them, so min(b.TransactionDate) supplies the timestamp, and
-- the July window is the run window so it takes the build config.
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
    date_trunc('MINUTE', min(b.TransactionDate)),
    cast(min(b.TransactionDate) as date),
    'HCL1b',
    'Home Claims - Escape of water or emergency assistance',
    'Policy'
from    dlk.EXT_Home_QS_ClaimDetails    a,
        dlk.ext_home_qs_policydetails   b
Where   a.HomeRiskId = upper(b.RiskId)
and     b.TransactionDate >= (select startTime from stg.episodeeventstream_buildconfig) and b.TransactionDate < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.HomeClaimType = 'Escape Of Water'
Group by b.PolicyCode
;

--HCL1c

-- converted from the count query. TransactionDate and the claim type sit on the policy details and
-- claim details tables the way HR0.F1 reads them, so min(b.TransactionDate) supplies the timestamp, and
-- the July window is the run window so it takes the build config.
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
    date_trunc('MINUTE', min(b.TransactionDate)),
    cast(min(b.TransactionDate) as date),
    'HCL1c',
    'Home Claims - Storm, flood or weather claim',
    'Policy'
from    dlk.EXT_Home_QS_ClaimDetails    a,
        dlk.ext_home_qs_policydetails   b
Where   a.HomeRiskId = upper(b.RiskId)
and     b.TransactionDate >= (select startTime from stg.episodeeventstream_buildconfig) and b.TransactionDate < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.HomeClaimType = 'Storm Damage'
Group by b.PolicyCode
;

--HCL4

--not available for home
-- NOT CONVERTED, and nothing to convert: no source for this step on Home.

--HCL.O2

-- converted from the count query. min(b.TransactionDate) supplies the timestamp, matching how HR0.F1
-- reads this pair of tables, and the 2026-05-01 start is a lookback rather than the run window so it is
-- kept as the literal the query had.
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
    date_trunc('MINUTE', min(b.TransactionDate)),
    cast(min(b.TransactionDate) as date),
    'HCL.O2',
    'Home Claims - Policy ended',
    'Policy'
from    dlk.EXT_Home_QS_ClaimDetails            a,
        dlk.ext_home_qs_policydetails           b,
        stg.R0_HomePoliciesEligibleForRenewals  c
Where   a.HomeRiskId = upper(b.RiskId)
and     b.TransactionDate between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000'
and     b.PolicyCode = c.PolicyCode
and     b.EventType = 'Policy Cancelled'
Group by b.PolicyCode
;

# In[ ]:

--HD1
-- converted from the count query, split by PolicyTypeGroup per your instruction, so HD1, D1 and VD1 each
-- carry their own product. The Group by EventDescription and Order by were an eyeballing breakdown and are
-- dropped. The timestamp is ConversationStartTime, when the customer rang, rather than the document event.
-- The 2026-07-01 to 2026-08-10 document window is not the run window so it is kept exactly as written.

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
    d.SourcePolicyReference,
    1,
    'Home',
    date_trunc('MINUTE', min(a.ConversationStartTime)),
    cast(min(a.ConversationStartTime) as date),
    'HD1',
    'Home Doc Request - Customer rings and asks for a document',
    'Policy'
from    stg.DocRequestClientCodes                a,
        ods.EventStream                          d
Where   a.clientCode = left(d.SourcePolicyReference,6)
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     d.EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-10 00:00:00.000'
and     d.EventDateTime between a.ConversationStartTime and dateadd(day,2,a.ConversationStartTime)
and     (   d.EventDescription like '%Emailed Document%'
        or
            d.EventDescription like '%Document Transmitted%'
        )
Group by d.SourcePolicyReference
;

# In[ ]:
--HD1.F1
-- from XX - Episode Reconciliation - Gaps.html, cell 74 (note or select)
-- header: Home	Doc Request	HD1.F1 -- Motor	Doc Request	D1.F1 -- Van	Doc Request	VD1.F1

-- converted from the count query. The group by PolicyTypeGroup served three products so it was replaced by a filter on Home, the window ending 2026-08-10 is kept exactly, and the Genesys ConversationId goes into EventSourceID.

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
    'HD1.F1',
    'Home Doc Request - Call wait time, or fails to make contact',
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
and     b.PolicyTypeGroup = 'Home'
Group by a.ConversationId
;

# In[ ]:
--HD2
-- from XX - Episode Reconciliation - Gaps.html, cell 75 (count query)
-- header: Home	Doc Request	HD2 - we are counting policies and also storing the breakdown for Chill to confirm

-- converted from the count query. Built from the first of the two statements in the cell, the second being an eyeballing breakdown, and the window of 2026-07-01 to 2026-08-10 is kept exactly.

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
    d.SourcePolicyReference,
    1,
    'Home',
    date_trunc('MINUTE', max(d.EventDateTime)),
    cast(max(d.EventDateTime) as date),
    'HD2',
    'Home Doc Request - Agent locates and sends the document',
    'Policy'
FROM    stg.DocRequestClientCodes                a,
        ods.EventStream                          d
Where   a.clientCode = left(d.SourcePolicyReference,6)
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000'
and     EventDateTime between ConversationStartTime and dateadd(day,2,ConversationStartTime)
and     (   d.EventDescription like '%%Emailed Document%%'
        or
            d.EventDescription like '%%Document Transmitted%%'
        )
Group by d.SourcePolicyReference
;

# In[ ]:
--HD3.F1
-- from XX - Episode Reconciliation - Gaps.html, cell 78 (note or select)
-- header: Home	Doc Request	HD3.F1
-- header: Motor	Doc Request	 D3.F1
-- header: Van 	Doc Request	VD3.F1

-- converted from the count query. The inner query gained a max of ConversationStartTime for the timestamp, the grain is the customer client code, and the window ending 2026-08-10 is kept exactly.

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
    'Home',
    date_trunc('MINUTE', max(x.LastCallTime)),
    cast(max(x.LastCallTime) as date),
    'HD3.F1',
    'Home Doc Request - Non-arrival, and the customer rings again',
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
and     x.PolicyTypeGroup = 'Home'
Group by x.clientCode
;

# In[ ]:
--HD3.F2
-- from XX - Episode Reconciliation - Gaps.html, cell 79 (note or select)
-- header: Home	Doc Request	HD3.F2
-- header: Motor	Doc Request	 D3.F2
-- header: Van 	Doc Request	VD3.F2

-- converted from the count query. The cell counted both client codes and policies so the policy grain was chosen, and the window ending 2026-08-10 is kept exactly.

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
    x.SourcePolicyReference,
    1,
    'Home',
    date_trunc('MINUTE', max(x.LastEventDateTime)),
    cast(max(x.LastEventDateTime) as date),
    'HD3.F2',
    'Home Doc Request - The same document downloaded again and again',
    'Policy'
from    (
            SELECT  d.PolicyTypeGroup, a.clientCode, d.SourcePolicyReference, EventDescription, count(distinct EventDateTime) EventDates, max(EventDateTime) LastEventDateTime
            FROM    stg.DocRequestClientCodes                a,
                    ods.EventStream                          d
            Where   a.clientCode = left(d.SourcePolicyReference,6)
            and     d.EventSourceId = 3
            and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000'
            Group by d.PolicyTypeGroup, a.clientCode, d.SourcePolicyReference, EventDescription
        ) x
Where   x.EventDates > 1
and     x.PolicyTypeGroup = 'Home'
Group by x.SourcePolicyReference
;

# In[ ]:

--M1

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
        a.ConversationId,
        1,
        'Motor',
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'M1',
        'Motor MTA - Customer calls Chill with a change request',
        'Call'
from    stg.A0_genesys_derived_data a left join stg.VM0_van_phone_numbers b
        on a.CustomerPhoneNumber = b.CustomerPhone
Where   QueueName in ('INBOUND_VehicleChangeAddress',
'INBOUND_VehicleChangeOther',
'INBOUND_VehicleChange_Perm',
'INBOUND_VehicleChange_Temp',
'INBOUND_VehicleUpdateLicence',
'INBOUND_Vehicle_Add_Driver')
and     originatingDirection = 'inbound' 
and     b.CustomerPhone is null
Group by a.ConversationId

--M1.F1

-- stg.AbandonedMTACalls is built in the Derived Data section at the top of this notebook.
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
        a.ConversationId,
        1,
        'Motor',
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'M1.F1',
        'Motor MTA - Customer calls Chill with a change request',
        'Call'
from    stg.A0_genesys_derived_data a, stg.AbandonedMTACalls b 
Where   a.ConversationId = b.ConversationId 
and     a.CustomerPhoneNumber not in (select CustomerPhone from stg.VM0_van_phone_numbers)
Group by a.ConversationId


# In[ ]:

--M3
-- mirrored from HM3. Straight swap of the PolicyTypeGroup literal on the stg.JJulyMTAs to stg.JulyPolicyState join, with the timestamp still taken from ReportingSaleDate because stg.JJulyMTAs only carries the integer posting date.

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

--M4a
--M5
--M6
-- mirrored from HM6. Straight swap of the PolicyTypeGroup literal to Motor in the stg.JJulyMTAs subquery, keeping the buildconfig window, the EventSourceId 3 document filters and the max EventDateTime for the last reissue.

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

# In[ ]:

--M.V1

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
        a.ConversationId,
        1,
        'Motor',
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'M.V1',
        'Motor MTA - Vehicle change',
        'Call'
from    stg.A0_genesys_derived_data a left join stg.VM0_van_phone_numbers b
        on a.CustomerPhoneNumber = b.CustomerPhone
Where   QueueName in (
'INBOUND_VehicleChangeOther',
'INBOUND_VehicleChange_Perm',
'INBOUND_VehicleChange_Temp')
and     originatingDirection = 'inbound' 
and     b.CustomerPhone is null
Group by a.ConversationId

--M.V2

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
        a.ConversationId,
        1,
        'Motor',
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'M.V2',
        'Motor MTA - Named driver add or remove',
        'Call'
from    stg.A0_genesys_derived_data a left join stg.VM0_van_phone_numbers b
        on a.CustomerPhoneNumber = b.CustomerPhone
Where   QueueName in (
'INBOUND_Vehicle_Add_Driver')
and     originatingDirection = 'inbound' 
and     b.CustomerPhone is null
Group by a.ConversationId

--M.V3

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
        a.ConversationId,
        1,
        'Motor',
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'M.V3',
        'Motor MTA - Licence update',
        'Call'
from    stg.A0_genesys_derived_data a left join stg.VM0_van_phone_numbers b
        on a.CustomerPhoneNumber = b.CustomerPhone
Where   QueueName = 'INBOUND_VehicleUpdateLicence'
and     originatingDirection = 'inbound' 
and     b.CustomerPhone is null
Group by a.ConversationId

--M.V4

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
        a.ConversationId,
        1,
        'Motor',
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'M.V4',
        'Motor MTA - Address change',
        'Call'
from    stg.A0_genesys_derived_data a left join stg.VM0_van_phone_numbers b
        on a.CustomerPhoneNumber = b.CustomerPhone
Where   QueueName in ('INBOUND_VehicleChangeAddress')
and     originatingDirection = 'inbound' 
and     b.CustomerPhone is null
Group by a.ConversationId

--M3.B1.1

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
        b.SourcePolicyReference,
        1,
        'Motor',
        max(date_trunc('MINUTE', coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
        max(cast(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') as date)),
        'M3.B1.1',
        'Motor MTA - Document request issued',
        'Policy'
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a, stg.MotorMTAPolicies  b 
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig) 
and PolicyTypeGroup = 'Motor' and a.PolicyCode = b.SourcePolicyReference 
and Campaign = 'DAY 1'
Group by b.SourcePolicyReference

--M3.B1.2

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
        b.SourcePolicyReference,
        1,
        'Motor',
        max(date_trunc('MINUTE', coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
        max(cast(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') as date)),
        'M3.B1.2',
        'Motor MTA - Customer submits documents',
        'Policy'
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a, stg.MotorMTAPolicies  b, dlk.MyChill_NewUploadDocumentEvents  c 
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig) 
and     PolicyTypeGroup = 'Motor' and a.PolicyCode = b.SourcePolicyReference 
and     Campaign = 'DAY 1'
and     a.PolicyCode = c.PolicyCode
and     PolicyTypeGroup = 'Motor'
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
Group by b.SourcePolicyReference

--M3.B1.4

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
        b.SourcePolicyReference,
        1,
        'Motor',
        max(date_trunc('MINUTE', coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
        max(cast(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') as date)),
        'M3.B1.4',
        'Motor MTA - Chase, first reminder',
        'Policy'
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a, stg.MotorMTAPolicies  b 
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig) 
and PolicyTypeGroup = 'Motor' and a.PolicyCode = b.SourcePolicyReference 
and Campaign = 'DAY 1'
Group by b.SourcePolicyReference

--M3.B1.5

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
        b.SourcePolicyReference,
        1,
        'Motor',
        max(date_trunc('MINUTE', coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
        max(cast(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') as date)),
        'M3.B1.5',
        'Motor MTA - Chase, escalation',
        'Policy'
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a, stg.MotorMTAPolicies  b 
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig) 
and PolicyTypeGroup = 'Motor' and a.PolicyCode = b.SourcePolicyReference 
and Campaign = 'DAY 20'
Group by b.SourcePolicyReference

--M3.B1.3

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
        b.SourcePolicyReference,
        1,
        'Motor',
        max(date_trunc('MINUTE', coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
        max(cast(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') as date)),
        'M3.B1.3',
        'Motor MTA - Documents validated',
        'Policy'
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a, stg.MotorMTAPolicies  b, dlk.MyChill_NewUploadDocumentEvents  c 
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig) 
and     PolicyTypeGroup = 'Motor' and a.PolicyCode = b.SourcePolicyReference 
and     Campaign = 'DAY 1'
and     a.PolicyCode = c.PolicyCode
and     PolicyTypeGroup = 'Motor'
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 

Group by b.SourcePolicyReference;

--M3.B1.6

-- mirrored from HM4.B1.6. The MTA base swapped to Motor, with isAccepted true marking the
-- documents that were received AND validated, which is how A6.B1.6 and HM4.B1.6 read this step.
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
    date_trunc('MINUTE', max(b.`Timestamp`)),
    cast(max(b.`Timestamp`) as date),
    'M3.B1.6',
    'Motor MTA - Documents received and validated',
    'Policy'
from    (
                select  b.PolicyCode
                from    stg.JJulyMTAs a, stg.JulyPolicyState b
                Where   a.PolicyCode = b.PolicyCode
                and     PolicyTypeGroup = 'Motor'
                and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
            )  a, dlk.MyChillWorkflow_DocumentStatus  b
Where   a.PolicyCode = b.PolicyCode
and     b.`Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and b.`Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
and     b.isAccepted = 'true'
Group by b.PolicyCode
;

--C1a

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
    'C1a',
    'Motor Cancellation - Customer asks to cancel',
    'Policy'
from    edw.tbl_fact_policy_mtc a,
        stg.JulyPolicyState     b
Where   a.PolicyCode = b.PolicyCode
and     a.PolicyTypeGroup = 'Motor'
and     a.EffectiveDate = (select effectiveDate from stg.episodeeventstream_buildconfig)
and     (
            a.ShortDescription like 'Client%'
        or
            a.ShortDescription like 'Customer%'
        )
Group by a.PolicyCode
;


# In[ ]:

--C1a.F1
-- mirrored from HC1a.F1. both source tables are shared, so only the PolicyTypeGroup literal moves to Motor, and the donor's literal 2026-07-31 effective date and NCT short description filter are kept.

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
and     a.EffectiveDate = (select effectiveDate from stg.episodeeventstream_buildconfig)
and     a.ShortDescription like '%NCT%'
Group by a.PolicyCode
;

# In[ ]:

--C2

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
    date_trunc('MINUTE', min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
    cast(min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01')) as date),
    'C2',
    'Motor Cancellation - Document chase, reminder',
    'Policy'
from    edw.exp_mychill_chase_daily_snapshot_motorvan a,
        stg.JulyMotorCancellations   b
Where   left(a.PolicyCode,6) = b.ClientCode
and	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
and case
        when Gap_In_Cov_Ltr_Status = 'O' then 1
        when Val_For_Spec_Item_Status = 'O' then 1
        when PPS_Num_Status = 'O' then 1
        When Identification_Status = 'O' then 1
        when Finance_Form_Status = 'O' then 1
        when Digital_Journey_Status = 'O' then 1
        else 0
    End = 1
Group by a.PolicyCode

--C3
-- converted from the count query. Same as HC2 but keeping the Campaign not equal to DAY 1 filter and the author's comment about escalation chases.

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
    date_trunc('MINUTE', min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
    cast(min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01')) as date),
    'C3',
    'Motor Cancellation - Document chase, escalation',
    'Policy'
from    edw.exp_mychill_chase_daily_snapshot_motorvan a,
        stg.JulyMotorCancellations   b
Where   left(a.PolicyCode,6) = b.ClientCode
and	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
and case
        when Gap_In_Cov_Ltr_Status = 'O' then 1
        when Val_For_Spec_Item_Status = 'O' then 1
        when PPS_Num_Status = 'O' then 1
        When Identification_Status = 'O' then 1
        when Finance_Form_Status = 'O' then 1
        when Digital_Journey_Status = 'O' then 1
        else 0
    End = 1
and     Campaign <> 'DAY 1'  /* first is request and all the next are escalation I think - when we go daily build, we could do that */
Group by a.PolicyCode
;

--C4

-- stg.MotorEscalated20days is built in the Derived Data section at the top of this notebook.
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
        x.SourcePolicyReference,
        1,
        'Motor',
        max(date_trunc('MINUTE', x.EventDate)),
        cast(max(x.EventDate) as date),
        'C4',
        'Motor Cancellation - Final notice',
        'Policy'
from 
    (select	distinct SourcePolicyReference, EventDate from ods.eventstream 
    where	EventSourceId = 3 
    and		EventDate >= (select startTime from stg.episodeeventstream_buildconfig) and EventDate < (select endTime   from stg.episodeeventstream_buildconfig) 
    and		PolicyTypeGroup = 'Motor'
    and		upper(EventDescription) like '%CHASE%' 
    and		upper(EventDescription) like '%FINAL%' ) x ,
    stg.MotorEscalated20days y 
Where     x.SourcePolicyReference = y.PolicyCode
Group by x.SourcePolicyReference

--C5

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
    a.SourcePolicyReference,
    1,
    'Motor',
    date_trunc('MINUTE', max(a.EventDateTime)),
    cast(max(a.EventDateTime) as date),
    'C5',
    'Motor Cancellation - Cancellation processed',
    'Policy'
from    ods.eventstream             a,
        stg.JulyMotorCancellations   b
Where   left(a.SourcePolicyReference,6) = b.ClientCode
and     a.PolicyTypeGroup = 'Motor'
and     a.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and a.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.EventSourceId = 3
and     a.EventDescription like '%CXL%'
and     (   a.EventDescription like '%Emailed Document%'
        or
            a.EventDescription like '%Document Transmitted%'
        )
Group by a.SourcePolicyReference
;

--C6

-- REBUILT on the back of VC6 from Gaps II. The earlier version read stg.JulyMotorCancellations and had
-- to be stamped at the literal EffectiveDate because that table carries no date. This one takes the
-- confirmation straight off the Relay feed, so it has a real event time and follows the run window.
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
    a.SourcePolicyReference,
    1,
    'Motor',
    date_trunc('MINUTE', min(a.EventDateTime)),
    cast(min(a.EventDateTime) as date),
    'C6',
    'Motor Cancellation - Cancellation confirmation sent',
    'Policy'
from    ods.eventstream     a
Where   a.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and a.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.EventSourceId = 3
and     a.PolicyTypeGroup = 'Motor'
and     a.EventDescription = 'Insurer Led Cancelation - Emailed Document - Reg canx email template'
Group by a.SourcePolicyReference
;

--ARR.1

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
    date_trunc('MINUTE', max(timestamp)),
    cast(max(timestamp) as date),
    'ARR.1',
    'Motor Arrears - Missed payment detected',
    'Policy'
from    dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
and     campaign_name = 'Arrears - Chase 1 - 1 Day Past'
and     MessageType in ('SMS', 'EMAIL')
and     PolicyTypeGroup = 'Motor'
group by PolicyCode

--ARR.2

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
    date_trunc('MINUTE', max(timestamp)),
    cast(max(timestamp) as date),
    'ARR.2',
    'Motor Arrears - Arrears chase',
    'Policy'
from    dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
and     campaign_name = 'Arrears - Chase 1 - 1 Day Past'
and     MessageType in ('SMS', 'EMAIL')
and     PolicyTypeGroup = 'Motor'
group by PolicyCode

--ARR.O1

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
    date_trunc('MINUTE', max(timestamp)),
    cast(max(timestamp) as date),
    'ARR.O1',
    'Motor Arrears - Arrears cleared',
    'Policy'
from    dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
and     timestamp < dateadd(day,-28,getdate()) --ensure chaser should have been sent
and     campaign_name = 'Arrears - Chase 1 - 1 Day Past'
and     MessageType in ('SMS', 'EMAIL')
and     PolicyTypeGroup = 'Motor'
and     PolicyCode not in
        (select policycode from dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
         where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
         and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
         and     campaign_name = 'Arrears - Chase 5 - 28 Days Past'
         and     MessageType in ('SMS', 'EMAIL')
         and     PolicyTypeGroup = 'Motor')
group by PolicyCode

--ARR.3

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
    date_trunc('MINUTE', max(timestamp)),
    cast(max(timestamp) as date),
    'ARR.3',
    'Motor Arrears - Loan defaults, arrears not cleared',
    'Policy'
from    dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
and     campaign_name = 'Arrears - Chase 5 - 28 Days Past'
and     MessageType in ('SMS', 'EMAIL')
and     PolicyTypeGroup = 'Motor'
group by PolicyCode

--ARR.O2

-- converted from the count query. The Insurer Led subquery now projects EventDateTime as well as the
-- reference so the insert has a timestamp, and min is used because the escalation is the first forced
-- cancellation event. Both July windows are the run window so they take the build config.
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
    a.SourcePolicyReference,
    1,
    'Motor',
    date_trunc('MINUTE', min(a.EventDateTime)),
    cast(min(a.EventDateTime) as date),
    'ARR.O2',
    'Motor Arrears - Escalation to forced cancellation',
    'Policy'
from            (select  distinct SourcePolicyReference, EventDateTime
                from    ods.eventstream        a
                Where   EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
                and     EventSourceId = 3
                and     PolicyTypeGroup = 'Motor'
                and     EventDescription like 'Insurer Led%') a,
                (select  distinct b.PolicyCode
                from    dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b
                where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
                and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig)
                --and     campaign_name = 'Arrears - Chase 5 - 28 Days Past'
                and     MessageType in ('SMS', 'EMAIL')
                and     PolicyTypeGroup = 'Motor') b
Where   a.SourcePolicyReference = b.PolicyCode
Group by a.SourcePolicyReference
;

--CL1a

-- REBUILT on the back of VCL1a from Gaps II. The earlier version read stg.DocRequestClientCodes, the
-- Doc Request staging table, which was the wrong population. This one goes through the INBOUND_Claims
-- queue and stg.Motor_PhoneNumbers, built here the same way stg.Van_PhoneNumbers is. SourceSystemId is 2
-- because the call comes from Genesys.
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
    'Motor',
    date_trunc('MINUTE', min(b.conversationStartTime)),
    cast(min(b.conversationStartTime) as date),
    'CL1a',
    'Motor Claims - Motor claim reported',
    'Policy'
from    stg.Motor_PhoneNumbers                      a,
        stg.Claims_genesys_derived_data_filtered    b
Where   b.CustomerPhoneNumber = a.CustomerPhone
Group by a.PolicyCode
;

--D1
-- converted from the count query, split by PolicyTypeGroup per your instruction, so HD1, D1 and VD1 each
-- carry their own product. The Group by EventDescription and Order by were an eyeballing breakdown and are
-- dropped. The timestamp is ConversationStartTime, when the customer rang, rather than the document event.
-- The 2026-07-01 to 2026-08-10 document window is not the run window so it is kept exactly as written.

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
    d.SourcePolicyReference,
    1,
    'Motor',
    date_trunc('MINUTE', min(a.ConversationStartTime)),
    cast(min(a.ConversationStartTime) as date),
    'D1',
    'Motor Doc Request - Customer rings and asks for a document',
    'Policy'
from    stg.DocRequestClientCodes                a,
        ods.EventStream                          d
Where   a.clientCode = left(d.SourcePolicyReference,6)
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Motor'
and     d.EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-10 00:00:00.000'
and     d.EventDateTime between a.ConversationStartTime and dateadd(day,2,a.ConversationStartTime)
and     (   d.EventDescription like '%Emailed Document%'
        or
            d.EventDescription like '%Document Transmitted%'
        )
Group by d.SourcePolicyReference
;


# In[ ]:

--D1.F1
-- see the HD1.F1 cell: XX - Episode Reconciliation - Gaps.html cell 74 covers HD1.F1, D1.F1, VD1.F1

-- mirrored from HD1.F1. Straight product swap of the ods.EventStream PolicyTypeGroup filter to Motor, keeping the literal 2026-07-01 to 2026-08-10 window and the donor's three product IN list in the inner query, and noting that stg.DocRequestClientCodes is read by nine queries but is no longer built anywhere in the notebook.

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

# In[ ]:

--D2
-- from XX - Episode Reconciliation - Gaps.html, cell 76 (count query)
-- header: Motor Doc Request	D2 - we are counting policies and also storing the breakdown for Chill to confirm

-- converted from the count query. The second breakdown select and its order by were dropped as eyeballing only, the timestamp is the last matching Relay EventDateTime, and the window of 2026-07-01 to 2026-08-10 has been kept exactly as it was.

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
    d.SourcePolicyReference,
    1,
    'Motor',
    date_trunc('MINUTE', max(d.EventDateTime)),
    cast(max(d.EventDateTime) as date),
    'D2',
    'Motor Doc Request - Agent locates and sends the document',
    'Policy'
FROM    stg.DocRequestClientCodes                a,
        ods.EventStream                          d
Where   a.clientCode = left(d.SourcePolicyReference,6)
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Motor'
and     d.EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000'
and     d.EventDateTime between a.ConversationStartTime and dateadd(day,2,a.ConversationStartTime)
and     (   d.EventDescription like '%Emailed Document%'
        or
            d.EventDescription like '%Document Transmitted%'
        )
Group by d.SourcePolicyReference
;

# In[ ]:
--D3.F1
-- see the HD3.F1 cell: XX - Episode Reconciliation - Gaps.html cell 78 covers HD3.F1, D3.F1, VD3.F1

-- mirrored from HD3.F1. Straight product swap of the outer PolicyTypeGroup filter to Motor, keeping the customer client code grain, the calleddates greater than one test and the literal 2026-07-01 to 2026-08-10 window, and noting that stg.DocRequestClientCodes is kept as the donors name it even though it is no longer built anywhere in the notebook.

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
    'Motor',
    date_trunc('MINUTE', max(x.LastCallTime)),
    cast(max(x.LastCallTime) as date),
    'D3.F1',
    'Motor Doc Request - Non-arrival, and the customer rings again',
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
and     x.PolicyTypeGroup = 'Motor'
Group by x.clientCode
;

# In[ ]:

--D3.F2
-- see the HD3.F2 cell: XX - Episode Reconciliation - Gaps.html cell 79 covers HD3.F2, D3.F2, VD3.F2

-- mirrored from HD3.F2. Straight product swap of the outer PolicyTypeGroup filter to Motor, keeping the policy grain, the EventDates greater than one test and the literal 2026-07-01 to 2026-08-10 window, and noting that stg.DocRequestClientCodes is kept as the donor names it even though it is no longer built anywhere in the notebook.

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
    x.SourcePolicyReference,
    1,
    'Motor',
    date_trunc('MINUTE', max(x.LastEventDateTime)),
    cast(max(x.LastEventDateTime) as date),
    'D3.F2',
    'Motor Doc Request - The same document downloaded again and again',
    'Policy'
from    (
            SELECT  d.PolicyTypeGroup, a.clientCode, d.SourcePolicyReference, EventDescription, count(distinct EventDateTime) EventDates, max(EventDateTime) LastEventDateTime
            FROM    stg.DocRequestClientCodes                a,
                    ods.EventStream                          d
            Where   a.clientCode = left(d.SourcePolicyReference,6)
            and     d.EventSourceId = 3
            and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000'
            Group by d.PolicyTypeGroup, a.clientCode, d.SourcePolicyReference, EventDescription
        ) x
Where   x.EventDates > 1
and     x.PolicyTypeGroup = 'Motor'
Group by x.SourcePolicyReference
;

# In[ ]:

--D.V1

-- REBUILT on the back of VD.V1 from Gaps II. The earlier version read stg.DocRequestPolicies, which
-- nothing in the notebook builds. This one matches the customer to the call through stg.Motor_PhoneNumbers
-- and the INBOUND_Documents_Out queue, and keeps the Motor document description the count query used.
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
    a.SourcePolicyReference,
    1,
    'Motor',
    date_trunc('MINUTE', min(a.EventDateTime)),
    cast(min(a.EventDateTime) as date),
    'D.V1',
    'Motor Doc Request - Replacement cert and disc',
    'Policy'
from    ods.EventStream a,
        (select  distinct PolicyCode , conversationStartTime
        from    stg.Motor_PhoneNumbers a, stg.DocRequest_genesys_derived_data_filtered b
        Where   b.CustomerPhoneNumber = a.CustomerPhone) b
Where   a.SourcePolicyReference = b.PolicyCode
and     a.EventDateTime between b.conversationStartTime and dateadd(day,2,b.conversationStartTime)
and     a.EventDescription = 'Duplicate Certificate - Document Transmitted - Certificate'
Group by a.SourcePolicyReference
;

--VR1a

-- stg.VanRenewals is built in the Derived Data section at the top of this notebook.
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
        'Van',
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDateTime as date)),
        'VR1a',
        'Van Renewals - Renewal invitation sent by EMAIL',
        'Policy'
from    ods.eventstream a, stg.VanRenewalsJuly b  
Where   a.SourcePolicyReference = b.PolicyCode
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000' 
and     EventDescription like 'Renewal Offer - Emailed Document %'
Group by b.PolicyCode

--VR1b

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
        'Van',
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDateTime as date)),
        'VR1b',
        'Van Renewals - Renewal invitation sent by POST',
        'Policy'
from    ods.eventstream a, stg.VanRenewalsJuly b  
Where   a.SourcePolicyReference = b.PolicyCode
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000' 
and     EventDescription like 'Renewal Offer - Document Transmitted - %'
Group by b.PolicyCode

--VR1.E1

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
        'VR1.E1',
        'Van Renewals - Renewal campaigns: CRM',
        'User'
from    dlk.EXT_XtremePushResults a, stg.VanRenewals b 
where campaign_name like '%Van - Renewals%' and a.PolicyCode = b.PolicyCode 
and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000' 
and     interaction_type = 'sent' 
and     MessageType  in ( 'EMAIL', 'SMS') 
group by UserID

--VR2
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
        max(date_trunc('MINUTE', 'Timestamp')),
        max(cast('Timestamp' as date)),
        'VR2',
        'Van Renewal - Customer logs in to portal',
        'Policy'
FROM    (
            select  left(PolicyCode,6) as ClientCode, dateadd(day, -60, RenewalDate) RenewalStartDate, PolicyCode, dateadd(day, 40, RenewalDate) RenewalEndDate
            from stg.R0_VanPoliciesEligibleForRenewals 
        )   a,
        dlk.appliedrenewals_successfulloginevent b 
Where   a.ClientCode = b.PortfolioCode 
and     b.`Timestamp` > a.RenewalStartDate
and     b.`Timestamp` < a.RenewalEndDate
group by a.PolicyCode

# In[ ]:

--VR3a
-- from XX - Episode Reconciliation - Gaps.html, cell 86 (count query)
-- header: Van	Renewal	VR3a
-- header: Van	Renewal	VR4

-- converted from the count query. Timestamp comes from the payment success table, the original query has no date window so none was added, and stg.VanRenewalsJuly is kept as written even though only stg.VanRenewals is built in the notebook.

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
    date_trunc('MINUTE', max(b.`Timestamp`)),
    cast(max(b.`Timestamp`) as date),
    'VR3a',
    'Van Renewal - Customer renews ONLINE',
    'Policy'
from    stg.VanRenewalsJuly a , dlk.appliedrenewals_paymentsuccess b
Where   PolicyRetNum = 1
and     PolicyOfferNum = 1
and     a.TYPolicyCode = b.PolicyCodeForRenewal
Group by a.TyPolicyCode
;

# In[ ]:
--VR3b
-- converted, but note the change of source. The count query in this cell measured receipt documents sent,
-- which is not what VR3b means, and the cell itself was marked as not enough volume. This is the Van mirror
-- of HR3b, the same step for Home, using the Channel and PolicyRetNum columns that stg.VanRenewals carries.
-- stg.VanRenewalsJuly is kept as written for consistency with the other Van renewal steps, though that table
-- is not built anywhere in this notebook.

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
    'VR3b',
    'Van Renewal - Customer renews on an INBOUND call',
    'Policy'
from    stg.VanRenewalsJuly a
Where   a.PolicyRetNum = 1
and     a.Channel = 'a) IB'
Group by a.TyPolicyCode
;

# In[ ]:
--VR3b.F1

-- from Gaps II, which finally gives us the Van renewals queue name. Built to the call grain the other
-- .F1 abandoned call steps use, with the ConversationId in EventSourceId and min(conversationStartTime)
-- as the event time. The run window comes from stg.A0_genesys_derived_data, which is already built to it.
insert INTO
ods.EpisodeEventStream
(
    EventSourceId,
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
    'VR3b.F1',
    'Van Renewal - Call wait time, or fails to make contact',
    'Call'
from    stg.A0_genesys_derived_data     a
where   a.queueName = 'INBOUND_Van_Renewals'
Group by a.ConversationId
HAVING  sum(a.abandoned) > 0
;

--VR3.B1
-- BLOCK HEADER. VR3.B1 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from VR3.B1.1, VR3.B1.2.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

# In[ ]:

--VR3.O1
-- converted from the count query. Timestamp is LYPolicyRenewDateAdj, the same column VR3.B1.1 uses for the
-- renewal date passing, because a lapsed policy has no this year sale date. stg.VanRenewalsJuly is kept as
-- written, though it is not built anywhere in this notebook.

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
    date_trunc('MINUTE', max(b.LYPolicyRenewDateAdj)),
    cast(max(b.LYPolicyRenewDateAdj) as date),
    'VR3.O1',
    'Van Renewal - Policy lapsed',
    'Policy'
from    stg.VanRenewalsJuly b
Where   b.PolicyRetNum is null
and     b.PolicyOfferNum = 1
Group by b.PolicyCode
;

# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 85 (count query)
-- header: Van	Renewal	VR3.O1	Policy lapsed
select  count(distinct PolicyCode)
from    stg.VanRenewalsJuly b  
Where   PolicyRetNum is null
and     PolicyOfferNum = 1
;

# In[ ]:
--VR4
-- see the VR3a cell: XX - Episode Reconciliation - Gaps.html cell 86 covers VR3a, VR4

-- mirrored from HR4. Straight swap of the renewals table to stg.VanRenewalsJuly and of the product literal, since TyPolicyCode, TYReportingSaleDate and PolicyRetNum are all carried by the Van renewals table.

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

--VR4.B2
-- from XX - Episode Reconciliation - Gaps.html, cell 88 (count query)
-- header: Van	Renewal	VR4.B2

-- BLOCK HEADER. VR4.B2 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from VR4.B2.1, VR4.B2.2, VR4.B2.3, VR4.B2.4, VR4.B2.5, VR4.B2.6.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 93 (count query)
-- header: Van	Renewal	VR4.B2
select  count(distinct PolicyCode)
from    (
            select  distinct PolicyCode
            from    ods.eventstream a, stg.VanRenewalsJuly b  
            Where   a.SourcePolicyReference = b.TyPolicyCode
            and     PolicyRetNum = 1 
            and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000' 
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
            and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000' 
            and     EventDescription like '%C&D%'
            and     (   EventDescription like '%Emailed Document%' 
                    or 
                        EventDescription like '%Document Transmitted%'
                    ) 
    ) x

# In[ ]:
--VR4.B2.F1
-- from XX - Episode Reconciliation - Gaps.html, cell 89 (count query)
-- header: Van	Renewal	VR4.B2.F1
-- and Campaign = 'DAY 1'

-- converted from the count query. Timestamp is the derived SaleDate expression the query already builds, following the house A6.F1 pattern, and the renewal chase window of 2026-05-01 to 2026-07-31 is kept exactly as written.

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
    date_trunc('MINUTE', max(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
    cast(max(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01')) as date),
    'VR4.B2.F1',
    'Van Renewal - Chases before the customer submits, and documents never submitted',
    'Policy'
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-07-31'
and PolicyType = 'Renewals'
and PolicyTypeGroup = 'Van'
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
--VR5
-- from XX - Episode Reconciliation - Gaps.html, cell 91 (count query)
-- header: Van	Renewal	VR5

-- converted from the count query. Timestamp is TyReportingSaleDate on the renewals table, the original query has no date window so none was added, and stg.VanRenewalsJuly is kept as written.

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
    date_trunc('MINUTE', max(b.TyReportingSaleDate)),
    cast(max(b.TyReportingSaleDate) as date),
    'VR5',
    'Van Renewal - Renewal processed, policy continued',
    'Policy'
from    stg.VanRenewalsJuly b
Where   PolicyRetNum = 1
Group by b.PolicyCode
;

# In[ ]:
--VR6.B1
--VR3.B1.1
-- from XX - Episode Reconciliation - Gaps.html, cell 94 (count query)
-- header: Van	Renewal	VR3.B1.1

-- converted from the count query. The event is the renewal date passing so LYPolicyRenewDateAdj is used rather than TyReportingSaleDate, which the filter allows to be null, and stg.VanRenewalsJuly is kept as written.

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
    'Van',
    date_trunc('MINUTE', max(LYPolicyRenewDateAdj)),
    cast(max(LYPolicyRenewDateAdj) as date),
    'VR3.B1.1',
    'Van Renewal - Renewal date passes with no renewal',
    'Policy'
from    stg.VanRenewalsJuly
Where (
            LYPolicyRenewDateAdj < TyReportingSaleDate
        OR
            TyReportingSaleDate is null )
and     PolicyOfferNum = 1
Group by PolicyCode
;

# In[ ]:
--VR3.B1.2
-- from XX - Episode Reconciliation - Gaps.html, cell 95 (count query)
-- header: Van	Renewal	VR3.B1.2
  -- get Renewal emails from XP table

-- converted from the count query. The union subquery now carries the XtremePush timestamp so the insert can aggregate it, the campaign window of 2026-05-01 to 2026-08-10 is kept exactly as written, and stg.VanRenewalsJuly is left unrenamed.

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
    date_trunc('MINUTE', max(x.`timestamp`)),
    cast(max(x.`timestamp`) as date),
    'VR3.B1.2',
    'Van Renewal - Lapse CRM sequence runs',
    'Policy'
from
    (
        select  b.PolicyCode, a.`timestamp`
        from    dlk.EXT_XtremePushResults a, stg.VanRenewalsJuly b
        where   campaign_name like '%Van%'
        and     campaign_name like '%Lapsed%'
        and     a.PolicyCode = b.PolicyCode
        and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
        and     interaction_type = 'sent'
        and     MessageType  in ( 'EMAIL', 'SMS')
        union
        select  b.PolicyCode, a.`timestamp`
        from    dlk.EXT_XtremePushResults_Policy a, stg.VanRenewalsJuly b
        where   campaign_name like '%Van%'
        and     campaign_name like '%Lapsed%'
        and     a.PolicyCode = b.PolicyCode
        and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
        and     interaction_type = 'sent'
        and     MessageType  in ( 'EMAIL', 'SMS')
    ) x
Group by x.PolicyCode
;

# In[ ]:
--VR3.B1.2.F1
-- from XX - Episode Reconciliation - Gaps.html, cell 96 (count query)
-- header: Van	Renewal	VR3.B1.2.F1

-- converted from the count query. A bounce with no open or click is a last occurrence so max of the XtremePush timestamp is used, the campaign window of 2026-05-01 to 2026-08-10 is kept exactly as written, and stg.VanRenewalsJuly is left unrenamed.

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
    'VR3.B1.2.F1',
    'Van Renewal - Unreachable on the lapse sequence',
    'Policy'
from    dlk.EXT_XtremePushResults_Policy a, stg.VanRenewalsJuly b
where   campaign_name like '%Van%'
and     campaign_name like '%Lapsed%'
and     a.PolicyCode = b.PolicyCode
and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
and     interaction_type = 'sent'
and     MessageType  in ( 'EMAIL', 'SMS')
and     a.PolicyCode not in
        (
            select  distinct a.PolicyCode
            from    dlk.EXT_XtremePushResults_Policy a, stg.VanRenewalsJuly b
            where   campaign_name like '%Van%'
            and     campaign_name like '%Lapsed%'
            and     a.PolicyCode = b.PolicyCode
            and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
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
            and     `timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
            and     interaction_type in ('bounce')
            and     MessageType  in ( 'EMAIL', 'SMS')
        )
Group by a.PolicyCode
;

# In[ ]:
--VR3.B1.O1
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
    date_trunc('MINUTE', max(a.TYReportingSaleDate)),
    cast(max(a.TYReportingSaleDate) as date),
    'VR3.B1.O1',
    'Van Renewal - Renewed inside the window',
    'Policy'
from    stg.r0_vanpolicieseligibleforrenewals a
Where   (
            a.TYReportingSaleDate > a.RenewalDate
        )
and     a.PolicyOfferNum > 0
Group by a.PolicyCode
;

--VR3.B1.O3
-- mirrored from HR3.B1.O3. The Home donor was used because it only needs PolicyCode and TYReportingSaleDate, both of which the Van renewals table carries, the campaign filter moves to the Van lapse campaign and the literal window of 2026-06-01 to 2026-09-01 is kept exactly as written.

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
where   a.`timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and add_months((select endTime   from stg.episodeeventstream_buildconfig),  1)
and     a.PolicyCode = b.PolicyCode
and     a.campaign_name like '%Van%'
and     a.campaign_name like '%Lapsed%'
and     a.MessageType in ( 'EMAIL', 'SMS')
and     a.interaction_type = 'sent'
and     b.TYReportingSaleDate is null
Group by a.PolicyCode
;

# In[ ]:

--VR4.B2.1

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
    date_trunc('MINUTE', max(a.`timestamp`)),
    cast(max(a.`timestamp`) as date),
    'VR4.B2.1',
    'Van Renewal - Document request issued',
    'Policy'
from    stg.VR0_VanPoliciesEligibleForRenewals  a,
        ods.EventStream                          d 
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.PolicyTypeGroup = 'Van'
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-01 00:00:00.000' 
and     EventDescription in 
        (
                'New Business - Saved Document - Document Checklist SMS',
                'New Business - Saved Document - Document Checklist Email'
            )

Group by a.TyPolicyCode;

--VR4.B2.2
-- from XX - Episode Reconciliation - Gaps.html, cell 99 (count query)
-- header: Van	Renewal	VR4.B2.2

-- converted from the count query. The union subquery now carries the upload event Timestamp, the document window of 2026-05-01 to 2026-08-10 is kept exactly as written, and stg.VanRenewalsJuly is left unrenamed.

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
    date_trunc('MINUTE', max(x.`Timestamp`)),
    cast(max(x.`Timestamp`) as date),
    'VR4.B2.2',
    'Van Renewal - Customer submits documents',
    'Policy'
from    (
            select  b.PolicyCode, b.`Timestamp`
            from    stg.VanRenewalsJuly a, dlk.MyChill_NewUploadDocumentEvents  b
            Where   a.PolicyCode = b.PolicyCode
            and     `Timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
            UNION
            select  b.PolicyCode, b.`Timestamp`
            from    stg.VanRenewalsJuly a, dlk.MyChill_NewUploadDocumentEvents  b
            Where   a.TyPolicyCode = b.PolicyCode
            and     `Timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
        ) x
Group by x.PolicyCode
;

# In[ ]:
--VR4.B2.4
-- from XX - Episode Reconciliation - Gaps.html, cell 100 (note or select)
-- header: Van	Renewal	VR4.B2.4
		-- counting guys who were sent at least once

-- converted from the count query. The outer group by counts was only a distribution for eyeballing so it is dropped, the first chase is min of CreateDate as the original subquery already computed, and the chase window of 2026-05-01 to 2026-07-31 is kept exactly as written.

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
    date_trunc('MINUTE', min(x.FirstDate)),
    cast(min(x.FirstDate) as date),
    'VR4.B2.4',
    'Van Renewal - Chase, first reminder',
    'Policy'
from    (
        select  PolicyCode , min(CreateDate) FirstDate
        from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
        Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-07-31'
        and PolicyType = 'Renewals'
        and PolicyTypeGroup = 'Van'
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
--VR4.B2.5
-- mirrored from HR4.B2.5. Straight swap of the renewals table to stg.VanRenewalsJuly and of the product literal, with the donor's literal window of 2026-06-01 to 2026-09-01 and its lack of a PolicyTypeGroup filter on ods.EventStream both kept as they are.

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
and     d.EventDateTime > add_months((select startTime from stg.episodeeventstream_buildconfig), -1)
and     d.EventDateTime < add_months((select endTime   from stg.episodeeventstream_buildconfig),  1)
and     d.EventDescription like '%Chase%'
and     d.EventDescription like '%Final%'
Group by a.PolicyCode
;

# In[ ]:

--VR4.B2.3
-- from XX - Episode Reconciliation - Gaps.html, cell 101 (count query)
-- header: Van	Renewal	VR4.B2.3

-- converted from the count query. The union subquery now carries the workflow Timestamp, the isAccepted filter suggested in the original comment was not added because the query never applied it, and the window of 2026-05-01 to 2026-08-10 is kept exactly as written.

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
    date_trunc('MINUTE', max(x.`Timestamp`)),
    cast(max(x.`Timestamp`) as date),
    'VR4.B2.3',
    'Van Renewal - Documents validated',
    'Policy'
from    (
            select  b.PolicyCode, b.`Timestamp`
            from    stg.VanRenewalsJuly a, dlk.MyChillWorkflow_DocumentStatus  b
            Where   a.PolicyCode = b.PolicyCode
            and     `Timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
            UNION
            select  b.PolicyCode, b.`Timestamp`
            from    stg.VanRenewalsJuly a, dlk.MyChillWorkflow_DocumentStatus  b
            Where   a.TyPolicyCode = b.PolicyCode
            and     `Timestamp` between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
        ) x
Group by x.PolicyCode
;

# In[ ]:
--VR4.B2.O1
-- from XX - Episode Reconciliation - Gaps.html, cell 102 (count query)
-- header: Van	Renewal	VR4.B2.O1

-- converted from the count query. Cancellation is a completion so max of EventDateTime is used, both the event window of 2026-05-01 to 2026-08-10 and the chase window of 2026-05-01 to 2026-07-31 are kept exactly as written, and stg.VanRenewalsJuly is left unrenamed.

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
    date_trunc('MINUTE', max(EventDateTime)),
    cast(max(EventDateTime) as date),
    'VR4.B2.O1',
    'Van Renewal - Cancellation, non-receipt',
    'Policy'
from    ods.eventstream a, stg.VanRenewalsJuly b
Where   a.SourcePolicyReference = b.TyPolicyCode /* new policy */
and     PolicyRetNum = 1
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
and     EventDescription like '%CXL%'
and     (   EventDescription like '%Emailed Document%'
        or
            EventDescription like '%Document Transmitted%'
        )
and     TyPolicyCode  in
        (select
                PolicyCode
        from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
        Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-07-31'
        and PolicyType = 'Renewals'
        and PolicyTypeGroup = 'Van'
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
        )
Group by b.PolicyCode
;

# In[ ]:
--VR4.B2.6
-- mirrored from R4.B2.6. Straight swap of the renewals table to stg.VanRenewalsJuly and of the product literal, with the build config run window and the extra cut off at 2026-09-01 both kept exactly as the donor has them.

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
and     `Timestamp` < add_months((select endTime   from stg.episodeeventstream_buildconfig),  1)
and     isAccepted = 'true'
Group by a.PolicyCode
;

# In[ ]:

--VR6.B1.1
-- from XX - Episode Reconciliation - Gaps.html, cell 103 (note or select)
-- header: Van	Renewal	VR6.B1.1

-- converted from the count query. The group by EventDescription was only a breakdown for eyeballing so it is dropped in favour of one row per policy, the window of 2026-05-01 to 2026-08-10 is kept exactly as written, and stg.VanRenewalsJuly is left unrenamed.

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
    date_trunc('MINUTE', max(EventDateTime)),
    cast(max(EventDateTime) as date),
    'VR6.B1.1',
    'Van Renewal - Cert and disc dispatched',
    'Policy'
from    ods.eventstream a, stg.VanRenewalsJuly b
Where   a.SourcePolicyReference = b.TyPolicyCode /* new policy */
and     PolicyRetNum = 1
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000'
and     (   EventDescription like '%Emailed Document%'
        or
            EventDescription like '%Document Transmitted%'
        )
and     EventDescription not like 'Renewal Offer%'
and     EventDescription not like 'Document Chase%'
Group by b.PolicyCode
;

# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 104 (note or select)
-- header: Van	Renewal	VR6.B1.1
select  EventDescription, count(distinct b.PolicyCode)
from    ods.eventstream a, stg.VanRenewalsJuly b  
Where   a.SourcePolicyReference = b.TyPolicyCode /* new policy */ 
and     PolicyRetNum = 1 
and     EventDateTime between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-08-10 00:00:00.000' 
/*and     EventDescription like '%CXL%'
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        ) */
Group by EventDescription
Order by 2 desc

# In[ ]:
--VA1

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
        a.Email,
        1,
        'Van',
        max(date_trunc('MINUTE', QuoteStartDateTime)),
        max(cast(QuoteStartDateTime as date)),
        'VA1',
        'Van Acquisition - Quote initiated ONLINE',
        'Email'
from	dlk.vanquotedetails a
Where   CASE WHEN Email like '%att.net' THEN 1 
					 WHEN Email like '%@app.net%' then 1 
					 WHEN Email like '%@Chill.ie' THEN 1 
					 WHEN Email like '%@test%' THEN 1 
					ELSE NULL 
					 END is NULL
and     QuoteType in ('FQ','QQ')                                 
AND     QuoteStartDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and QuoteStartDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
Group by Email 

--VA0.F1

-- stg.Van_genesys_inbound_call_duration_summary is built in the Derived Data section at the top of this notebook.
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
        a.conversationId,
        1,
        'Van',
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'VA0.F1',
        'Van Acquisition - Call wait time, or fails to make contact',
        'Quote'
from	stg.Van_genesys_inbound_call_duration_summary a 
Where   abandoned > 0 
group by a.conversationId;

--VA0

-- stg.Van_genesys_derived_data_filtered is built in the Derived Data section at the top of this notebook.

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
        a.conversationId,
        1,
        'Van',
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'VA0',
        'Van Acquisition - Straight into the CALL CENTRE',
        'Quote'
from stg.Van_genesys_derived_data_filtered a
group by a.conversationId;

--VA5

-- stg.VanSales is built in the Derived Data section at the top of this notebook.
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
        max(date_trunc('MINUTE', ReportingSalesDate)),
        max(cast(ReportingSalesDate as date)),
        'VA5',
        'Van Acquisition - Payment successful',
        'Policy'
from stg.VanSales
where 
channel = 'a) Back Office' and ReportingSalesType = 'New Business'
Group by a.PolicyCode

--VA5.B1
-- BLOCK HEADER. VA5.B1 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from VA5.B1.1, VA5.B1.2, VA5.B1.3, VA5.B1.4, VA5.B1.5.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.


# In[ ]:

--VA6
-- mirrored from A6. the Motor donor already reads the shared MotorVan chase snapshot so only PolicyTypeGroup moves to Van, and the 2ndCar_Cert_Status column is quoted with backticks the way the other Van query on that table writes it.

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

--VA6.B1

# In[ ]:

--VA6.B1.F1
-- converted from the corrected query in this cell. Grain is the policy and the timestamp is the derived
-- SaleDate on the chase snapshot, the same expression the other chase steps use. The 2026-05-01 to 2026-07-31
-- chase window is not the run window so it is kept exactly as written.
-- Note the query filters PolicyType = 'Renewals' while VA6.B1.F1 sits under Van Acquisition. Left as you wrote it.

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
    'Van',
    date_trunc('MINUTE', min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
    cast(min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01')) as date),
    'VA6.B1.F1',
    'Van Acquisition - Documents never submitted, policy at risk of cancellation',
    'Policy'
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-07-31' 
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
;

# In[ ]:
--VA7
-- mirrored from A7. the Motor donor is used rather than the Home one because the target step is the certificate and disc dispatch, so the policies sold table becomes stg.VanSales and ods.EventStream is read at PolicyTypeGroup Van with the donor's certificate description list unchanged.

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

# In[ ]:

--VA7.B1
--VA5.B1.4

-- from Gaps II. The pasted query reads stg.VanSalesJuly, which has no build in the notebook, so it
-- reads stg.VanSales instead, which is the July Van sales table the rest of the notebook uses and
-- carries ReportingSaleType. min(EventDateTime) is the first chase email. The July window is the run
-- window so it takes the build config.
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
    date_trunc('MINUTE', min(d.EventDateTime)),
    cast(min(d.EventDateTime) as date),
    'VA5.B1.4',
    'Van Acquisition - Chase, inconsistency resolution',
    'Policy'
FROM    stg.VanSales                             a,
        ods.EventStream                          d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Van'
and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.ReportingSaleType = 'New Business'
and     d.EventDescription in
        (
            'Document Chase - Emailed Document - PC Chase Email'
        )
Group by a.PolicyCode
;

--VA6.B1.1
-- mirrored from A6.B1.1. Straight swap of the product literals on the same MotorVan chase snapshot, with the PolicyTypeGroup filter moved to Van.

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
        'VA6.B1.1',
        'Van Acquisition - Document request issued',
        'Policy'
From    (
            select  PolicyCode,
                    max(coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01')) SaleDateTime
            from    edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan   a
            Where   coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(a.SaleDate,4), '-',substring(a.SaleDate,4,2),'-',left(a.SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
            and     a.PolicyType = 'New Business'
            and     a.PolicyTypeGroup = 'Van'
            Group by PolicyCode
        )   x
Group by x.PolicyCode
;

# In[ ]:

--VA6.B1.2
-- mirrored from HA6.B1.2. the policies sold table becomes stg.VanSales and the donor's PolicyTypeGroup filter is dropped because stg.VanSales is already restricted to Van and does not project that column.

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

--VA6.B1.5

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
        max(cast(EventDateTime as date)),
        'VA6.B1.5',
        'Van Acquisition - Chase, escalation',
        'Policy'
from    stg.VanSales                             a,
        ods.EventStream                          d 
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Van'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
            (
                'Document Chase - Emailed Document - Chase Final Notice Email'
            )
Group by a.PolicyCode

--VA6.B1.3


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
        'Van',
        max(date_trunc('MINUTE', `Timestamp`)),
        max(cast(`Timestamp` as date)),
        'VA6.B1.3',
        'Van Acquisition - Documents validated',
        'Policy'
from    stg.VanSales a, dlk.MyChillWorkflow_DocumentStatus  b 
Where   a.PolicyCode = b.PolicyCode
and     ReportingSaleType = 'New Business'  
and     `Timestamp` between '2026-07-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
Group by b.PolicyCode

--VA6.B1.O1

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
        max(cast(EventDateTime as date)),
        'VA6.B1.O1',
        'Van Acquisition - Cancellation, non-receipt',
        'Policy'
from    stg.VanSales                             a,
        ods.EventStream                          d 
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Van'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
            (
                'Insurer Led Cancelation - Emailed Document - Reg canx email template'
            )
Group by a.PolicyCode


# In[ ]:

--VA6.B1.6
--?

-- mirrored from A6.B1.6. The policies sold table becomes stg.VanSales and the donor's PolicyTypeGroup filter is dropped because that table is already Van only and does not project the column, with the sibling VA6.B1.3 max aggregate and Group by applied and the donor's buildconfig window kept.

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
        'Van',
        max(date_trunc('MINUTE', `Timestamp`)),
        max(cast(`Timestamp` as date)),
        'VA6.B1.6',
        'Van Acquisition - Documents received and validated',
        'Policy'
from    stg.VanSales                            a,
        dlk.MyChillWorkflow_DocumentStatus      b
Where   a.PolicyCode = b.PolicyCode
and     a.ReportingSaleType = 'New Business'
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
and     b.isAccepted = 'true'
Group by b.PolicyCode
;

# In[ ]:

--VA7.B1.1

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
        max(cast(EventDateTime as date)),
        'VA7.B1.1',
        'Van Acquisition - Cert and disc dispatched',
        'Policy'
from    stg.VanSales                             a,
        ods.EventStream                          d 
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Van'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
            (
                'New Business - Printed Document - CD Issue Letter CV' 
            )
Group by a.PolicyCode

--VA7.B1.2

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
        max(cast(EventDateTime as date)),
        'VA7.B1.2',
        'Van Acquisition - Document pack dispatched',
        'Policy'
from    stg.VanSales                             a,
        ods.EventStream                          d 
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Van'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
            (
                'New Business - Emailed Document - 05E Terms Of Business',
                'New Business - Document Transmitted - 05E Terms Of Business',
                'New Business - Document Transmitted - Terms Of Business'
            )
Group by a.PolicyCode
            

# In[ ]:

--VA7.B1.3
-- mirrored from A7.B1.3. The policies sold table becomes stg.VanSales, which is already restricted to Van, and ods.EventStream is read at PolicyTypeGroup Van with the product neutral Terms Of Business descriptions unchanged.

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
        'VA7.B1.3',
        'Van Acquisition - Customer receipt, implicit',
        'Policy'
FROM    stg.VanSales                              a,
        ods.EventStream                          d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Van'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     ReportingSaleType = 'New Business'
and     EventDescription in (
            'New Business - Document Transmitted - Terms Of Business',
            'New Business - Emailed Document - Terms Of Business'
            )

Group by a.PolicyCode
;

# In[ ]:

--VA7.B1.5

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
        max(cast(EventDateTime as date)),
        'VA7.B1.5',
        'Van Acquisition - Replacement requested',
        'Policy'
from    stg.VanSales                             a,
        ods.EventStream                          d 
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     d.PolicyTypeGroup = 'Van'
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
            (
                'New Business - Printed Document - CD Issue Letter MTA'
            )
Group by a.PolicyCode
            


--VM1

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
        a.ConversationId,
        1,
        'Van',
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'VM1',
        'Van MTA - Customer calls Chill with a change request',
        'Call'
from    stg.A0_genesys_derived_data a join stg.VM0_van_phone_numbers b
        on a.CustomerPhoneNumber = b.CustomerPhone
Where   QueueName in ('INBOUND_VehicleChangeAddress',
'INBOUND_VehicleChangeOther',
'INBOUND_VehicleChange_Perm',
'INBOUND_VehicleChange_Temp',
'INBOUND_VehicleUpdateLicence',
'INBOUND_Vehicle_Add_Driver')
and     originatingDirection = 'inbound'
Group by a.ConversationId

--VM1.F1

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
        a.ConversationId,
        1,
        'Van',
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'VM1.F1',
        'Van MTA - Call wait time, or fails to make contact',
        'Call'
from    stg.A0_genesys_derived_data a, stg.AbandonedMTACalls b 
Where   a.ConversationId = b.ConversationId 
and     a.CustomerPhoneNumber in (select CustomerPhone from stg.VM0_van_phone_numbers)
Group by a.ConversationId


# In[ ]:

--VM2.O1
-- mirrored from HM2.O1. Straight swap of the PolicyTypeGroup literal to Van on the stg.JJulyMTAs to stg.JulyPolicyState join, keeping the cancelled mid term and lapsed for transfer status list and the PolicyCancelDate timestamp exactly as the donor has them.

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
    date_trunc('MINUTE', max(b.PolicyCancelDate)),
    cast(max(b.PolicyCancelDate) as date),
    'VM2.O1',
    'Van MTA - Cancellation, declined or not proceeded with',
    'Policy'
from    stg.JJulyMTAs a, stg.JulyPolicyState b
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Van'
and     PolicyStatusDesc in (
     'Cancelled Mid Term' , 'Lapsed for Transfer'
)
Group by a.PolicyCode
;

# In[ ]:

--VM3

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
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'VM3',
        'Van MTA - Customer accepts',
        'Policy'
from    stg.JJulyMTAs a, stg.JulyPolicyState b 
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Van'
and     PolicyStatusDesc not in (
    'Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer'
) 
group by a.PolicyCode

--VM3.B1

-- BLOCK HEADER. VM3.B1 is the heading for its sub-steps, not an event in its own right, so it
-- writes nothing to the event stream. The events come from VM3.B1.1, VM3.B1.2, VM3.B1.3, VM3.B1.4,
-- VM3.B1.5 and VM3.B1.6. The insert removed from here was the same query as VM3.B1.2 with a
-- different EventTypeId, so it double counted that sub-step.

--VM3.B1.F1

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
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'VM3.B1.F1',
        'Van MTA - Chases before the customer submits, and documents never submitted',
        'Policy'
from    edw.EXP_MyChill_Chase_Daily_Snapshot_Home a 
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between add_months((select startTime from stg.episodeeventstream_buildconfig), -1) and '2026-07-31' 
and     PolicyTypeGroup = 'Van' 
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
and     a.PolicyCode in 
        (
            select  distinct a.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b 
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Van'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
        )
Group by a.PolicyCode
        
--VM4c

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
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'VM4c',
        'Van MTA - Return premium',
        'Policy'
from    stg.JJulyMTAs a, stg.JulyPolicyState b 
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Van'
and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
and     ( 
            CCYGrossPremium = 0 
        and 
            CCYFees = 0 )
group by a.PolicyCode


--VM6

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
    a.SourcePolicyReference,
    1,
    'Van',
    date_trunc('MINUTE', max(a.EventDateTime)),
    cast(max(a.EventDateTime) as date),
    'VM6',
    'Van MTA - Cert and disc sent',
    'Policy'
from    ods.EventStream
Where   SourcePolicyReference in 
        (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Van'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
        )
and     EventDate >= (select startTime from stg.episodeeventstream_buildconfig) and EventDate < (select endTime   from stg.episodeeventstream_buildconfig)
and     EventSourceId = 3 
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        )
group by a.SourcePolicyReference

--VM6.B1
--VM3.B1.1

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
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'VM3.B1.1',
        'Van MTA - Document request issued',
        'Policy'
from    stg.JJulyMTAs a, dlk.MyChill_NewUploadDocumentEvents  b 
Where   a.PolicyCode = b.PolicyCode
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
and     b.PolicyCode in 
        (
            select  distinct a.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b 
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Van'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
        )
Group by a.PolicyCode
        
--VM3.B1.2

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
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'VM3.B1.2',
        'Van MTA - Document request issued',
        'Policy'
from    stg.JJulyMTAs a, dlk.MyChill_NewUploadDocumentEvents  b 
Where   a.PolicyCode = b.PolicyCode
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
and     b.PolicyCode in 
        (
            select  distinct a.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b 
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Van'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
        )
Group by a.PolicyCode

# In[ ]:

--VM3.B1.4

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
        'Van',
        max(date_trunc('MINUTE', time_stamp)),
        max(cast(time_stamp as date)),
        'VM3.B1.4',
        'Van MTA - Chase, first reminder',
        'Policy'
from    (
            select  PolicyCode,
                    coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') as time_stamp
                    from edw.exp_mychill_chase_daily_snapshot_motorvan a
            Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)  
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
                and     PolicyTypeGroup = 'Van'
                and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
            ) 
        )
group by PolicyCode  

--VM3.B1.3

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
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'VM3.B1.3',
        'Van MTA - Documents validated',
        'Policy'
from    (
                select  b.PolicyCode
                from    stg.JJulyMTAs a, stg.JulyPolicyState b
                Where   a.PolicyCode = b.PolicyCode
                and     PolicyTypeGroup = 'Van'
                and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
            )  a, dlk.MyChillWorkflow_DocumentStatus  b 
Where   a.PolicyCode = b.PolicyCode
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
group by a.PolicyCode

--VM3.B1.O1

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
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'VM3.B1.O1',
        'Van MTA - Cancellation, non-receipt',
        'Policy'
from    (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Van'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
        )                                       a,
        (select  distinct PolicyCode  
                    from edw.exp_mychill_chase_daily_snapshot_motorvan a
            Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig) 
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
and     d.PolicyTypeGroup = 'Van'
and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)  
and     EventDescription like '% CXL %' 

and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        )
and     a.PolicyCode = d.SourcePolicyReference 
and     a.PolicyCode = b.PolicyCode
and     d.EventDescription = 'Prior Year Quotes - Document Transmitted - 10 Day CXL Letter'
group by a.PolicyCode

--VM3.B1.6

-- mirrored from HM4.B1.6. The MTA base swapped to Van, with isAccepted true marking the
-- documents that were received AND validated, which is how A6.B1.6 and HM4.B1.6 read this step.
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
    date_trunc('MINUTE', max(b.`Timestamp`)),
    cast(max(b.`Timestamp`) as date),
    'VM3.B1.6',
    'Van MTA - Documents received and validated',
    'Policy'
from    (
                select  b.PolicyCode
                from    stg.JJulyMTAs a, stg.JulyPolicyState b
                Where   a.PolicyCode = b.PolicyCode
                and     PolicyTypeGroup = 'Van'
                and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
            )  a, dlk.MyChillWorkflow_DocumentStatus  b
Where   a.PolicyCode = b.PolicyCode
and     b.`Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and b.`Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
and     b.isAccepted = 'true'
Group by b.PolicyCode
;

# In[ ]:

--VM3.B1.5
-- mirrored from M3.B1.5. The chase snapshot stays but is read at PolicyTypeGroup Van, and the flat join to stg.MotorMTAPolicies is replaced by the nested PolicyCode in list over stg.JJulyMTAs and stg.JulyPolicyState used by the Van sibling VM3.B1.4 because that Motor staging table has no Van counterpart.

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
        'VM3.B1.5',
        'Van MTA - Chase, escalation',
        'Policy'
from    edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan   a
Where   coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.PolicyTypeGroup = 'Van'
and     Campaign = 'DAY 20'
and     a.PolicyCode in
        (
            select  b.PolicyCode
            from    stg.JJulyMTAs           a,
                    stg.JulyPolicyState     b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Van'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
        )
Group by a.PolicyCode
;

# In[ ]:

--VM6.B1.1
-- mirrored from HM6.B1.1. Straight swap of the Home literals to Van on the stg.JJulyMTAs subquery and on the ods.EventStream feed, keeping the buildconfig window and the donor's six document descriptions exactly, with the event description taken from the target step wording of cert and disc dispatched.

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
    'VM6.B1.1',
    'Van MTA - Cert and disc dispatched',
    'Policy'
FROM    (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Van'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
        )                                       a,
        ods.EventStream                          d
Where   d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Van'
and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
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
Group by a.PolicyCode
;

# In[ ]:

--VM6.B1.2

-- mirrored from HM6.B1.2. Straight product swap to Van. Note this is the same population as VM6.B1.1,
-- exactly as HM6.B1.1 and HM6.B1.2 are the same population on Home, which is what the recon expects:
-- HM6.B1.1, HM6.B1.2 and HM6.B1.3 all carry the same Fabric volume.
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
    date_trunc('MINUTE', min(d.EventDateTime)),
    cast(min(d.EventDateTime) as date),
    'VM6.B1.2',
    'Van MTA - Document pack dispatched',
    'Policy'
FROM    (
            select  b.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Van'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer')
        )                                       a,
        ods.EventStream                          d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Van'
and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     d.EventDescription in
        (
            'New Business - Emailed Document - Terms Of Business',
            'New Business - Emailed Document - Cover Letter',
            'New Business - Emailed Document - 04 - Suitability Statement',
            'New Business - Document Transmitted - 04 - Suitability Statement',
            'New Business - Document Transmitted - Terms Of Business',
            'New Business - Document Transmitted - Cover Letter'
        )
Group by a.PolicyCode
;

--VM6.B1.3
--VM6.B1.4
--VM6.B1.5
--VC1a

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
    date_trunc('MINUTE', max(b.PolicyCancelDate)),
    cast(max(b.PolicyCancelDate) as date),
    'VC1a',
    'Van Cancellation - Customer asks to cancel',
    'Policy'
from    edw.tbl_fact_policy_mtc a,
        stg.JulyPolicyState     b
Where   a.PolicyCode = b.PolicyCode
and     a.PolicyTypeGroup = 'Van'
and     a.EffectiveDate = (select effectiveDate from stg.episodeeventstream_buildconfig)
and     (
            a.ShortDescription like 'Client%'
        or
            a.ShortDescription like 'Customer%'
        )
Group by a.PolicyCode
;

--VC1b.F1
--VC2

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
    date_trunc('MINUTE', min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
    cast(min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01')) as date),
    'VC2',
    'Van Cancellation - Document chase, reminder',
    'Policy'
from    edw.exp_mychill_chase_daily_snapshot_motorvan a,
        stg.JulyVanCancellations   b
Where   left(a.PolicyCode,6) = b.ClientCode
and	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
and case
        when Gap_In_Cov_Ltr_Status = 'O' then 1
        when Val_For_Spec_Item_Status = 'O' then 1
        when PPS_Num_Status = 'O' then 1
        When Identification_Status = 'O' then 1
        when Finance_Form_Status = 'O' then 1
        when Digital_Journey_Status = 'O' then 1
        else 0
    End = 1
Group by a.PolicyCode


--VC3
-- converted from the count query. Same as HC2 but keeping the Campaign not equal to DAY 1 filter and the author's comment about escalation chases.

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
    date_trunc('MINUTE', min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01'))),
    cast(min(coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01')) as date),
    'VC3',
    'Van Cancellation - Document chase, escalation',
    'Policy'
from    edw.exp_mychill_chase_daily_snapshot_motorvan a,
        stg.JulyVanCancellations   b
Where   left(a.PolicyCode,6) = b.ClientCode
and	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig)
and case
        when Gap_In_Cov_Ltr_Status = 'O' then 1
        when Val_For_Spec_Item_Status = 'O' then 1
        when PPS_Num_Status = 'O' then 1
        When Identification_Status = 'O' then 1
        when Finance_Form_Status = 'O' then 1
        when Digital_Journey_Status = 'O' then 1
        else 0
    End = 1
and     Campaign <> 'DAY 1'  /* first is request and all the next are escalation I think - when we go daily build, we could do that */
Group by a.PolicyCode
;

--VC4
-- converted from the count query. Reads ods.EventStream and writes to ods.EpisodeEventStream, with max EventDateTime because a final notice is the last chase.

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
    a.SourcePolicyReference,
    1,
    'Van',
    date_trunc('MINUTE', max(a.EventDateTime)),
    cast(max(a.EventDateTime) as date),
    'VC4',
    'Van Cancellation - Final notice',
    'Policy'
from    ods.eventstream             a,
        stg.JulyVanCancellations   b
Where   left(a.SourcePolicyReference,6) = b.ClientCode
and     a.PolicyTypeGroup = 'Van'
and     a.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and a.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.EventSourceId = 3
and     a.EventDescription like '%Document Chase%'
and     a.EventDescription like '%Final Notice%'
and     (   a.EventDescription like '%Emailed Document%'
        or
            a.EventDescription like '%Document Transmitted%'
        )
Group by a.SourcePolicyReference
;

--VC5


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
    a.SourcePolicyReference,
    1,
    'Van',
    date_trunc('MINUTE', max(a.EventDateTime)),
    cast(max(a.EventDateTime) as date),
    'VC5',
    'Van Cancellation - Cancellation processed',
    'Policy'
from    ods.eventstream             a,
        stg.JulyVanCancellations   b
Where   left(a.SourcePolicyReference,6) = b.ClientCode
and     a.PolicyTypeGroup = 'Van'
and     a.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and a.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.EventSourceId = 3
and     a.EventDescription like '%CXL%'
and     (   a.EventDescription like '%Emailed Document%'
        or
            a.EventDescription like '%Document Transmitted%'
        )
Group by a.SourcePolicyReference
;

--VC6

-- from Gaps II. The Group by EventDescription in the count was an eyeballing breakdown and is dropped,
-- leaving one row per policy. min(EventDateTime) is when the confirmation went out and the July window
-- is the run window so it takes the build config. This description also gives us HC6, and a better C6
-- than the one built off stg.JulyMotorCancellations.
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
    a.SourcePolicyReference,
    1,
    'Van',
    date_trunc('MINUTE', min(a.EventDateTime)),
    cast(min(a.EventDateTime) as date),
    'VC6',
    'Van Cancellation - Cancellation confirmation sent',
    'Policy'
from    ods.eventstream     a
Where   a.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and a.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.EventSourceId = 3
and     a.PolicyTypeGroup = 'Van'
and     a.EventDescription = 'Insurer Led Cancelation - Emailed Document - Reg canx email template'
Group by a.SourcePolicyReference
;

--VARR.1

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
    date_trunc('MINUTE', max(timestamp)),
    cast(max(timestamp) as date),
    'VARR.1',
    'Van Arrears - Missed payment detected',
    'Policy'
from    dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
and     campaign_name = 'Arrears - Chase 1 - 1 Day Past'
and     MessageType in ('SMS', 'EMAIL')
and     PolicyTypeGroup = 'Van'
group by PolicyCode

--VARR.2

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
    date_trunc('MINUTE', max(timestamp)),
    cast(max(timestamp) as date),
    'VARR.2',
    'Van Arrears - Arrears chase',
    'Policy'
from    dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
and     campaign_name = 'Arrears - Chase 1 - 1 Day Past'
and     MessageType in ('SMS', 'EMAIL')
and     PolicyTypeGroup = 'Van'
group by PolicyCode

--VARR.O1

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
    date_trunc('MINUTE', max(timestamp)),
    cast(max(timestamp) as date),
    'VARR.O1',
    'Van Arrears - Arrears cleared',
    'Policy'
from    dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
and     timestamp < dateadd(day,-28,getdate()) --ensure chaser should have been sent
and     campaign_name = 'Arrears - Chase 1 - 1 Day Past'
and     MessageType in ('SMS', 'EMAIL')
and     PolicyTypeGroup = 'Van'
and     PolicyCode not in
        (select policycode from dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
         where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
         and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
         and     campaign_name = 'Arrears - Chase 5 - 28 Days Past'
         and     MessageType in ('SMS', 'EMAIL')
         and     PolicyTypeGroup = 'Van')
group by PolicyCode

--VARR.3

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
    date_trunc('MINUTE', max(timestamp)),
    cast(max(timestamp) as date),
    'VARR.3',
    'Van Arrears - Loan defaults, arrears not cleared',
    'Policy'
from    dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
and     campaign_name = 'Arrears - Chase 5 - 28 Days Past'
and     MessageType in ('SMS', 'EMAIL')
and     PolicyTypeGroup = 'Van'
group by PolicyCode
--VARR.4

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
    date_trunc('MINUTE', max(timestamp)),
    cast(max(timestamp) as date),
    'VARR.4',
    'Van Arrears - Default chase and final notice',
    'Policy'
from    dlk.EXT_XtremePushResults  a, tmp.CurrentPolicy b 
where   upper(campaign_name) like '%RREARS%' and a.ClientCode = left(b.PolicyCode,6)
and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig) 
and     campaign_name = 'Arrears - Chase 6 - 38 Days Past'
and     MessageType in ('SMS', 'EMAIL')
and     PolicyTypeGroup = 'Van'
group by PolicyCode
--VARR.O2

-- from Gaps II. The Insurer Led subquery now projects EventDateTime so the insert has a timestamp,
-- and min is used because the escalation is the first forced cancellation event. Note this version
-- takes the arrears population from the two XtremePush feeds unioned, where HARR.O2 and ARR.O2 go
-- through tmp.CurrentPolicy. Say the word and I will put all three on the same route.
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
    a.SourcePolicyReference,
    1,
    'Van',
    date_trunc('MINUTE', min(a.EventDateTime)),
    cast(min(a.EventDateTime) as date),
    'VARR.O2',
    'Van Arrears - Escalation to forced cancellation',
    'Policy'
from            (select  distinct SourcePolicyReference, EventDateTime
                from    ods.eventstream        a
                Where   EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)
                and     EventSourceId = 3
                and     PolicyTypeGroup = 'Van'
                and     EventDescription like 'Insurer Led%') a,
                (select  distinct PolicyCode
                from    dlk.EXT_XtremePushResults
                where   upper(campaign_name) like '%RREARS%'
                and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig)
                and     MessageType in ('SMS', 'EMAIL')
                UNION
                select  distinct PolicyCode
                from    dlk.EXT_XtremePushResults_Policy
                where   upper(campaign_name) like '%RREARS%'
                and     timestamp >= (select startTime from stg.episodeeventstream_buildconfig) and timestamp < (select endTime   from stg.episodeeventstream_buildconfig)
                and     MessageType in ('SMS', 'EMAIL')
                ) b
Where   a.SourcePolicyReference = b.PolicyCode
Group by a.SourcePolicyReference
;

--VCL1a

-- REBUILT from Gaps II. The earlier version read stg.DocRequestClientCodes, which was the Doc Request
-- staging table. This one goes through the INBOUND_Claims queue and the new stg.Van_PhoneNumbers, which
-- is the population you meant. conversationStartTime is when the claim was reported and SourceSystemId
-- is 2 because the call comes from Genesys.
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
    'Van',
    date_trunc('MINUTE', min(b.conversationStartTime)),
    cast(min(b.conversationStartTime) as date),
    'VCL1a',
    'Van Claims - Van claim reported',
    'Policy'
from    stg.Van_PhoneNumbers                        a,
        stg.Claims_genesys_derived_data_filtered    b
Where   b.CustomerPhoneNumber = a.CustomerPhone
Group by a.PolicyCode
;

--VD1
-- converted from the count query, split by PolicyTypeGroup per your instruction, so HD1, D1 and VD1 each
-- carry their own product. The Group by EventDescription and Order by were an eyeballing breakdown and are
-- dropped. The timestamp is ConversationStartTime, when the customer rang, rather than the document event.
-- The 2026-07-01 to 2026-08-10 document window is not the run window so it is kept exactly as written.

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
    d.SourcePolicyReference,
    1,
    'Van',
    date_trunc('MINUTE', min(a.ConversationStartTime)),
    cast(min(a.ConversationStartTime) as date),
    'VD1',
    'Van Doc Request - Customer rings and asks for a document',
    'Policy'
from    stg.DocRequestClientCodes                a,
        ods.EventStream                          d
Where   a.clientCode = left(d.SourcePolicyReference,6)
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Van'
and     d.EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-10 00:00:00.000'
and     d.EventDateTime between a.ConversationStartTime and dateadd(day,2,a.ConversationStartTime)
and     (   d.EventDescription like '%Emailed Document%'
        or
            d.EventDescription like '%Document Transmitted%'
        )
Group by d.SourcePolicyReference
;


# In[ ]:

--VD1.F1
-- see the HD1.F1 cell: XX - Episode Reconciliation - Gaps.html cell 74 covers HD1.F1, D1.F1, VD1.F1

-- mirrored from HD1.F1. Straight product swap of the ods.EventStream PolicyTypeGroup filter to Van, keeping the literal 2026-07-01 to 2026-08-10 window exactly as the donor has it, and noting that stg.DocRequestClientCodes is referenced by nine queries but has no build left in the notebook.

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

--VD2
-- from XX - Episode Reconciliation - Gaps.html, cell 77 (count query)
-- header: Van Doc Request	VD2 - we are counting policies and also storing the breakdown for Chill to confirm

-- converted from the count query. The second statement was only an EventDescription breakdown for Chill to confirm so it is dropped, and the doc request window of 2026-07-01 to 2026-08-10 is kept exactly as written.

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
    d.SourcePolicyReference,
    1,
    'Van',
    date_trunc('MINUTE', max(EventDateTime)),
    cast(max(EventDateTime) as date),
    'VD2',
    'Van Doc Request - Agent locates and sends the document',
    'Policy'
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
Group by d.SourcePolicyReference
;

# In[ ]:
--VD3.F1
-- see the HD3.F1 cell: XX - Episode Reconciliation - Gaps.html cell 78 covers HD3.F1, D3.F1, VD3.F1

-- mirrored from HD3.F1. Straight product swap of the outer PolicyTypeGroup filter to Van, keeping the customer client code grain, the calleddates greater than one test and the literal 2026-07-01 to 2026-08-10 window, and noting that stg.DocRequestClientCodes is no longer built anywhere in the notebook.

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

# In[ ]:

--VD3.F2
-- see the HD3.F2 cell: XX - Episode Reconciliation - Gaps.html cell 79 covers HD3.F2, D3.F2, VD3.F2

-- mirrored from HD3.F2. Straight product swap of the outer PolicyTypeGroup filter to Van, keeping the policy grain, the EventDates greater than one test and the literal 2026-07-01 to 2026-08-10 window, and noting that stg.DocRequestClientCodes is kept as the donor names it even though it is no longer built anywhere in the notebook.

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
    x.SourcePolicyReference,
    1,
    'Van',
    date_trunc('MINUTE', max(x.LastEventDateTime)),
    cast(max(x.LastEventDateTime) as date),
    'VD3.F2',
    'Van Doc Request - The same document downloaded again and again',
    'Policy'
from    (
            SELECT  d.PolicyTypeGroup, a.clientCode, d.SourcePolicyReference, EventDescription, count(distinct EventDateTime) EventDates, max(EventDateTime) LastEventDateTime
            FROM    stg.DocRequestClientCodes                a,
                    ods.EventStream                          d
            Where   a.clientCode = left(d.SourcePolicyReference,6)
            and     d.EventSourceId = 3
            and     EventDateTime between '2026-07-01 00:00:00.000'  and '2026-08-10 00:00:00.000'
            Group by d.PolicyTypeGroup, a.clientCode, d.SourcePolicyReference, EventDescription
        ) x
Where   x.EventDates > 1
and     x.PolicyTypeGroup = 'Van'
Group by x.SourcePolicyReference
;

# In[ ]:

--VD.V1

-- from Gaps II. The customer is matched to the call through the new stg.Van_PhoneNumbers and the
-- INBOUND_Documents_Out queue, and the document has to land within two days of the call.
-- min(a.EventDateTime) is when the replacement certificate and disc went out.
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
    a.SourcePolicyReference,
    1,
    'Van',
    date_trunc('MINUTE', min(a.EventDateTime)),
    cast(min(a.EventDateTime) as date),
    'VD.V1',
    'Van Doc Request - Replacement cert and disc',
    'Policy'
from    ods.EventStream a,
        (select  distinct PolicyCode , conversationStartTime
        from    stg.Van_PhoneNumbers a, stg.DocRequest_genesys_derived_data_filtered b
        Where   b.CustomerPhoneNumber = a.CustomerPhone) b
Where   a.SourcePolicyReference = b.PolicyCode
and     a.EventDateTime between b.conversationStartTime and dateadd(day,2,b.conversationStartTime)
and     a.EventDescription in
        (
            'Prior Year Quotes - Emailed Document - C&D Email'
        )
Group by a.SourcePolicyReference
;

--TA1

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
        a.quote_number,
        1,
        'Travel',
        max(date_trunc('MINUTE', Travel_QuoteDate)),
        max(cast(Travel_QuoteDate as date)),
        'TA1',
        'Travel Acquisition - Travel quote initiated',
        'Quote'
from    dlk.EXT_Travel_Quotes 
WHERE Travel_QuoteDate >= (select startTime from stg.episodeeventstream_buildconfig) and Travel_QuoteDate < (select endTime   from stg.episodeeventstream_buildconfig) 
AND rtrim(ltrim(travel_certificatestatus)) IN ('Completed Quote','Incomplete Quote','Cancelled','Live')
and len(email)>0
Group by a.quote_number

--TA1p

-- stg.TravelQuotes is built in the Derived Data section at the top of this notebook.

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
        a.quote_number,
        1,
        'Travel',
        max(date_trunc('MINUTE', travel_purchaseDate)),
        max(cast(travel_purchaseDate as date)),
        'TA1p',
        'Travel Acquisition - Travel Quote Completed',
        'Quote'
from   stg.TravelQuotes
where  RenewalFlag = 0

--TA3a

Slightly concerning - their number appears to be both acquisition and renewal
Group by a.quote_number

--TA5

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
        a.quote_number,
        1,
        'Travel',
        max(date_trunc('MINUTE', travel_purchaseDate)),
        max(cast(travel_purchaseDate as date)),
        'TA5',
        'Travel Acquisition - Purchase confirmed by next-day CSV',
        'Quote'
from   stg.TravelQuotes a
where travel_purchaseDate >= (select startTime from stg.episodeeventstream_buildconfig) and travel_purchaseDate < (select endTime   from stg.episodeeventstream_buildconfig)	
and RenewalFlag = 0
Group by a.quote_number

--TA3.B1.2

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
        a.quote_number,
        1,
        'Travel',
        max(date_trunc('MINUTE', travel_purchaseDate)),
        max(cast(travel_purchaseDate as date)),
        'TA3.B1.2',
        'Travel Acquisition - Purchase',
        'Quote'
from    edw.tbl_fact_TravelAllQuotesSales a 
Where   Effective_Date = (select effectiveDate from stg.episodeeventstream_buildconfig) 
and     travel_purchaseDate >= (select startTime from stg.episodeeventstream_buildconfig) and travel_purchaseDate < (select endTime   from stg.episodeeventstream_buildconfig)	
and     Business_Type = 'New Business'
group by quote_number

--TR1.E1

-- from Gaps II. The distinct email is the grain so it goes into SourceCustomerReference. The square
-- bracket quoting in the pasted query is T-SQL, so timestamp is written with backticks here. The July
-- window is the run window so it takes the build config.
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
    a.email,
    1,
    'Travel',
    date_trunc('MINUTE', min(a.`timestamp`)),
    cast(min(a.`timestamp`) as date),
    'TR1.E1',
    'Travel Renewal - Travel renewal date campaign',
    'Customer'
from    dlk.ext_xtremepushresults_policy    a
where   a.campaign_name in
        (
            'Travel - Renewal Date in the next 14 Days',
            'Travel - Renewal Date in the next  7 Days'
        )
and     a.`timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and a.`timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)
and     a.MessageType in ('EMAIL', 'SMS')
Group by a.email
;

--TR4

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
        a.quote_number,
        1,
        'Travel',
        max(date_trunc('MINUTE', travel_purchaseDate)),
        max(cast(travel_purchaseDate as date)),
        'TR4',
        'Travel Renewal - Renewal processed',
        'Quote'
from   stg.TravelQuotes a
where travel_purchaseDate >= (select startTime from stg.episodeeventstream_buildconfig) and travel_purchaseDate < (select endTime   from stg.episodeeventstream_buildconfig)	
and RenewalFlag = 1
Group by a.quote_number

--TR.O1

-- from Gaps II. Your note says this is 2130 rather than the 10106 that SQL09 reports, because that
-- figure is renewals and new business together. QuoteId is the reference the other Travel steps use,
-- PurchaseDate supplies the timestamp, and the July window is the run window so it takes the build config.
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
    p.QuoteId,
    1,
    'Travel',
    date_trunc('MINUTE', max(p.PurchaseDate)),
    cast(max(p.PurchaseDate) as date),
    'TR.O1',
    'Travel Renewal - Policy continues, re-purchased',
    'Quote'
from    dlk.EXT_Travel_Policy   p
WHERE   p.PurchaseDate >= (select startTime from stg.episodeeventstream_buildconfig) and p.PurchaseDate < (select endTime   from stg.episodeeventstream_buildconfig)
and     p.RenewalFlag = 1
Group by p.QuoteId
;
