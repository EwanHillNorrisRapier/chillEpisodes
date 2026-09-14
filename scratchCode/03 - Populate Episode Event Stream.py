#!/usr/bin/env python
# coding: utf-8

# ## 03 - Populate Episode Event Stream
# 
# null

# In[ ]:


-- reate the event stream table
Create or Replace Table ods.EpisodeEventStream 
(
    EventId     BigInt IDENTITY,
    EventSourceId   Int,
    EventSourceReference    Varchar(128),
    SourceQuoteReference    Varchar(128),
    SourcePolicyReference   Varchar(128),
    SourceCustomerReference Varchar(128),
    SourceSystemId          int,
    PolicyTypeGroup         varchar(50),
    EventDateTime           TIMESTAMP,
    EventDate               Date,
    EventTypeId             VARCHAR(10),
    EventDescription        varchar(1024),
    Grain                   varchar(50)
)


# In[ ]:


--Add start and end date variables here


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
Where	conversationStartTime >= '{run_start}' and conversationStartTime < '{run_end}' 
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
Where   CreatedDateTime >= '{run_start}' and CreatedDateTime < '{run_end}' 
Group by QuoteQueryGuid
("")


# In[ ]:


Create or Replace Table stg.A0_mfq_derived_data as 
SELECT distinct
    contactmobile,
    QuoteQueryGuid
from
    dlk.mfq_quotequery
Where   CreatedDateTime >= '{run_start}' and CreatedDateTime < '{run_end}' 
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
WHERE   s.EffectiveDate = '{effective_date}'
  AND   s.ReportingSaleCategory = 'Cat A1: Active Sale'
  AND   s.OrgID = 1
  AND   s.SaleCount = 1
("")


# In[ ]:


Create or Replace Table stg.R0_MotorPoliciesEligibleForRenewals as 
select  PolicyCode, LyPolicyRenewDateAdj as RenewalDate, TyPolicyCode , TyPolicyRenewDateAdj
from    edw.tbl_fact_policy_renewals    a 
Where   a. LyPolicyTypeGroup = 'Home' 
and     a.LYPolicyRenewDateAdj >= '{run_start_date}' and a.LYPolicyRenewDateAdj < '{run_end_date}' 
and     PolicyOfferNum = 1 
Group by   PolicyCode, LyPolicyRenewDateAdj, TyPolicyCode  , TyPolicyRenewDateAdj
("")


# In[ ]:


create or Replace table stg.CDAPurchasePolicyList as 
select  trim(PolicyNumber) PolicyCode , max(UTCDateUpdated) SentDate
from    dlk.SQL07CDA_Messages
where	RenderedMessage like 'Hi, thanks for choosing us, we really appreciate it.%be sending out your welcome pack shortly. Thanks, Chill Insurance.' 
and		UTCDateAdded >= '{run_start}' and UTCDateAdded < '{run_end}' 
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
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
Group by SourcePolicyReference
("")


# In[ ]:


Create or Replace Table stg.MotorRenewalsOnline as 
select  distinct PolicyCode, SalesSource,,RenewalStartDate
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
        select  PolicyCode, 3 , a.EventDateTime
        from    stg.MFQ_Quote_Payments a, stg.RenewalsDoingMFQ  b 
        Where   a.QuotequeryGuId = b.MFQQuotequeryGuId and PaymentType in (0,5)
        ) x 


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
Where	conversationStartTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
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
Where   a. LyPolicyTypeGroup = 'Vam' 
and     a.LYPolicyRenewDateAdj >= '{run_start_date}' and a.LYPolicyRenewDateAdj < '{run_end_date}' 
and     PolicyOfferNum = 1 
Group by   PolicyCode, LyPolicyRenewDateAdj, TyPolicyCode  , TyPolicyRenewDateAdj


Create Table stg.MotorMTAPolicies as 
select  distinct SourcePolicyReference
from    ods.EventStream Where EventSourceId = 3 and EventDescription like 'Permanent%' and PolicyTypeGroup = 'Motor' 
and     EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000'

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

insert INTO
ods.EpisodeEventStream
(        
    SourcePolicyReference,
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
        'A1.E1',
        'Motor Acquisition - Service retrieve',
        'Policy'
from    dlk.EXT_XtremePushResults
where	`timestamp` >= '{run_start}' and `timestamp` < '{run_end}' 
and		campaign_name like 'Motor % TYR %' 
and     interaction_type = 'sent' 
and     MessageType = 'EMAIL'
and     QuoteQueryGuid > ''
("")


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


# In[ ]:


--A2.F1


# In[ ]:


--A2.E1


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
        (select QuoteId, ABPAction from dlk.MFQ_MON_Session Where IsKnownBot = TRUE or case when ABPAction = '' then null else ABPAction end is not null  and `$ExtractDateTime` >= '{run_start}' and `$ExtractDateTime` < '{run_end}' ) c  
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


--A3.E1


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
    2,
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
        and     PaymentDate >= '{run_start}' and PaymentDate < '{run_end}' 
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
    9,
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
("")


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
    9,
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
where   PaymentDate >= '{run_start}' and PaymentDate < '{run_end}' 
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
where   PaymentDate >= '{run_start}' and PaymentDate < '{run_end}' 
and     PaymentType not in (0,5)
("")


# In[ ]:


--A5.B1

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
Where   PaymentDate >= '{run_start}' and PaymentDate < '{run_end}' 
and     PaymentType in (0,5)
and     FullPaymentFlag is FALSE 
("")


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
where	`timestamp` >= '{run_start}' and `timestamp` < '{run_end}' 
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
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDate as date)),
        'A6',
        'Motor Acquisition - Documents requested',
        'Policy'
FROM    edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '{run_start}' and '{run_end}' and PolicyType = 'New Business' and PolicyTypeGroup = 'Motor' and 
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
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDate as date)),
        'A6',
        'Motor Acquisition - Documents requested',
        'Policy'
FROM    edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '{run_start}' and '{run_end}' and PolicyType = 'New Business' and PolicyTypeGroup = 'Motor' and 
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


# In[ ]:


--A6.B1


# In[ ]:


--A6.B1.F1


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
and     EventDateTime >= '{run_start}' and EventDateTime < '{run_end}' 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
            ( 
                'New Business - Document Transmission Confirmed - Certificate',
                'New Business - Document Posted Confirmation - Certificate',
                'New Business - Document Transmitted - Certificate'
            )   
("")


# In[ ]:


--A7.F1


# In[ ]:


--A7.B1


# In[ ]:


--A3.B1.1


# In[ ]:


--A3.B1.2


# In[ ]:


--A3.B1.O1


# In[ ]:


--A6.B1.1


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
and     `Timestamp` >= '{run_start}' and `Timestamp` < '{run_end}' 
("")


# In[ ]:


--A6.B1.4


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
and     EventDateTime >= '{run_start}' and EventDateTime < '{run_end}' 
and     ReportingSaleType = 'New Business' 
and     EventDescription like '%Chase%' 
and     EventDescription like '%Final%' 
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
        'Motor Acquisition - Customer submits documents',
        'Policy'
from    stg.GlobalPoliciesSold a, dlk.MyChillWorkflow_DocumentStatus  b 
Where   a.PolicyCode = b.PolicyCode
and     ReportingSaleType = 'New Business' 
and     PolicyTypeGroup = 'Motor'
and     `Timestamp` >= '{run_start}' and `Timestamp` < '{run_end}' 
and     isAccepted = 'true'
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
and     EventDateTime >= '{run_start}' and EventDateTime < '{run_end}' 
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
        and     EventDateTime >= '{run_start}' and EventDateTime < '{run_end}' 
        and     ReportingSaleType = 'New Business' 
        and     EventDescription like '%Chase%' 
        and     EventDescription like '%Final%' )
("")


# In[ ]:


--A6.B1.6


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
and     EventDateTime >= '{run_start}' and EventDateTime < '{run_end}' 
and     ReportingSaleType = 'New Business' 
and     EventDescription IN 
            ( 
                'New Business - Document Transmitted - Certificate' /* as confirmed by 2003 / 2004 / 2014 only this exists --Document Transmitted */
            )   
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
and     EventDateTime >= '{run_start}' and EventDateTime < '{run_end}' 
and     ReportingSaleType = 'New Business' 
and     EventDescription in (
            'New Business - Document Transmitted - Terms Of Business',
            'New Business - Emailed Document - Terms Of Business'
            )
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
and     EventDateTime >= '{run_start}' and EventDateTime < '{run_end}' 
and     ReportingSaleType = 'New Business' 
and     EventDescription in (
            'New Business - Document Transmitted - Terms Of Business',
            'New Business - Emailed Document - Terms Of Business'
            )
("")


# In[ ]:


--A7.B1.4


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
and     EventDateTime >= '{run_start}' and EventDateTime < '{run_end}' 
and     ReportingSaleType = 'New Business' 
and     EventDescription in (
            'Duplicate Certificate - Document Transmitted - Certificate'
            )
("")


# Motor Renewals

# In[ ]:


--RO.F1
--R0.B1
--RO.F2


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
--R1.E1
--R1.E1.F3


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
("")


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
        'R2',
        'Motor Renewal - Customer logs in to portal',
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
insert INTO
ods.EpisodeEventStream
(        
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
            and     PaymentDate  between '2026-05-01 00:00:00.000' and '2026-08-31 00:00:00.000' 
            Group by PolicyCode
        ) b 
        on b.PolicyCode = a.PolicyCode
where b.PolicyCode is null  
group by a.PolicyCode
("")


# In[ ]:


--R2.E1


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
        'R3c',
        'Motor Renewal - Customer renews ONLINE',
        'Policy' 
from    edw.tbl_fact_policy_renewals 
where   RenewalMonth = '2026-07-31' 
and     channel like '%eb %'
and     PolicyRetNum = 1 
and     PolicyOfferNum = 1 
and		LYPolicyTypeGroup = 'Motor' 


# In[ ]:


--R3b.F1
stg.R0_genesys_derived_data


# In[ ]:


--R3.B1
insert INTO
ods.EpisodeEventStream
(        
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


# In[ ]:


--R3.O1
--R4


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
        'Renewal Transfer - Emailed Document - Certificate'
        'Renewal Transfer - Printed Document - RNL Cert Issue Letter'

    )
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
Where b.PolicyCode is null;


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
Where   Rank1PremComp > RenEURPremOffer and RenEURPremOffer > 0 ;


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
Where   Rank1PremComp > TYEURGrossPremium;


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
Where   RenEURPremOffer > TYEURGrossPremium;


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
and     TyReportingSaleDate is null;


# In[ ]:


--R3.B1.1
--R3.B1.2
--R3.B1.2.F1
--R3.B1.3
--R3.B1.4
--R3.B1.O1
--R3.B1.O3
--R6.F1
--R6.B1

# In[ ]:

--R4.B2.F1

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
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
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
and     `Timestamp` > '2026-05-01 00:00:00.000' 
and     `Timestamp` < '2026-09-01 00:00:00.000' 
group by a.PolicyCode;


# In[ ]:


--R4.B2.4


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
and     EventDateTime > '2026-05-01 00:00:00.000' 
and     EventDateTime < '2026-09-01 00:00:00.000' 
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
and     `Timestamp` > '2026-07-01 00:00:00.000' 
and     `Timestamp` < '2026-09-01 00:00:00.000'
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
and     EventDateTime > '2026-05-01 00:00:00.000' 
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
        and     EventDateTime > '2026-05-01 00:00:00.000' 
        and     EventDateTime < '2026-09-01 00:00:00.000' 
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
and     `Timestamp` > '2026-07-01 00:00:00.000' 
and     `Timestamp` < '2026-09-01 00:00:00.000'
and     isAccepted = 'true'
group by a.PolicyCode;


# In[ ]:


--R6.B1.1
--R6.B1.2


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
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
and     EventDescription like 'Duplicate Certificate%';

# Home Acquisitions

# In[ ]:

--HA1
Create Or Replace Table stg.HA1_HFQ_Quotes_Raw as 
SELECT  *, 	
        CAST(from_unixtime(_ts) AS TIMESTAMP) as ts_unix,
        ROW_NUMBER() OVER(PARTITION BY QuoteCodeReference, RetrieveCount order by _ts desc) AS RN,
        COUNT(*)     OVER (PARTITION BY QuoteCodeReference, RetrieveCount) AS MaxRN
FROM    dlk.HFQ_QuoteDetails_Snapshot_v2
Where   CAST(from_unixtime(_ts) AS TIMESTAMP) between '2026-07-01' and '2026-07-31'  
;


Create Or Replace Table stg.HA1_HFQ_Quotes as 
SELECT  *
FROM    (SELECT  *, 	
                CAST(from_unixtime(_ts) AS TIMESTAMP) as ts_unix,
                ROW_NUMBER() OVER(PARTITION BY QuoteCodeReference, RetrieveCount order by _ts desc) AS RN,
                COUNT(*)     OVER (PARTITION BY QuoteCodeReference, RetrieveCount) AS MaxRN
        FROM    dlk.HFQ_QuoteDetails_Snapshot_v2) a
where   RN =1
and     ts_unix between '2026-07-01' and '2026-07-31'  

select count(*) from stg.HA1_HFQ_Quotes

# In[ ]:

--HA1.E1
select	count(*)
from	dlk.EXT_XtremePushResults   a 
where	`timestamp` between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
and		campaign_name like 'Home % TYR %' 
and interaction_type = 'sent' 
-- without the below conditions we get 70113 entries but it includes workflow/ sms / email so I think only 2/3 rd contacts sent out
and MessageType = 'EMAIL'  --> this brings down to 23058
-- and QuoteQueryGuid > ''  --> this brings down to 12148 these 2 conditions are a bit iffy as the volumes drop a lot


# In[ ]:

--HA1.E2
select	count(distinct CustomerPhoneNumber) 
from	stg.A0_genesys_derived_data	a,
		(select	ConversationId, max(sessionIndex) sessionIndex
		from	stg.A0_genesys_derived_data
		Where	queueName is not null 
		/*and		originatingDirection = 'inbound'*/
		Group by ConversationId
		)	b 
where	a.ConversationId = b.ConversationId
and		a.sessionIndex = b.sessionIndex
and		queueName = 'OUTBOUND_SALES_HOME'

--HA1.F1
select count(*) from stg.HA1_HFQ_Quotes a left join (select * from dlk.EXT_XtremePushResults   a 
where	`timestamp` between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
and		campaign_name like 'Home % TYR %' 
and interaction_type = 'sent' 
-- without the below conditions we get 70113 entries but it includes workflow/ sms / email so I think only 2/3 rd contacts sent out
and MessageType = 'EMAIL' ) b
on a.proposer_email = b.email
where b.QuoteQueryGuid is null

# In[ ]:

--HA0
SELECT count(distinct  ConversationId)
FROM stg.A0_MFQ_genesys_link

# In[ ]:

--HA0.F1
select count(*) from stg.HA0F1_genesys_inbound_call_duration_summary where abandoned = 1 and CallWaitTime > 0 limit 10

# In[ ]:

--HA2
select 
count(distinct QuoteCodeReference) 
--*
from dlk.hfq_response_quotes
where Quotes_DateCreated between '2026-07-01' and '2026-07-31'

# In[ ]:

--HA2.F1

select count(distinct a.QuoteCodeReference) from stg.HA1_HFQ_Quotes a left join stg.hfq_price_requested b 
on a.QuoteCodeReference = b.QuoteCodeReference
Where b.QuoteCodeReference is null 

# In[ ]:

--HA2.E1

# In[ ]:

--HA3

Create or Replace table stg.HA3_HomeAcquisitionQuoteInitiated as 
select  QuoteQueryGuid, 
        max(RetrieveSessionToken) RetrieveSessionToken,
        min(case when StepId = 1 then CreatedOn else null end) Step1DateTime,
        max(case when StepId in (2,3,4,5) then StepId else null end) Step2To5,
        min(case when StepId in (2,3,4) then CreatedOn else null end) FirstStep2to4DateTime,
        min(case when StepId = 5 then CreatedDateCreatedOnTime else null end) FirstStep5DateTime,
        max(case when StepId = 5 then CreatedOn else null end) LastStep5DateTime, 
        max(BrokerId) BrokerId,
        max(case when ImpervalsBot = 'true' then 1 else 0 end) ImpervalsBot,
        max(case when ImpervalsBot = 'true' then 1 else 0 end) ImpervalsBot
from    dlk.hfq_quotedetails_snapshot_v2
Where   CreatedOn between '2026-07-01' and '2026-07-31'
Group by QuoteQueryGuid
;

select 
count(distinct QuoteCodeReference) 
--*
from dlk.hfq_response_quotes
where Quotes_Premium > 0
and Quotes_Outcome = 'PremiumReturned'
and Quotes_DateCreated between '2026-07-01' and '2026-07-31'

--HA3.F1

# In[ ]:

--HA4a

select count(distinct a.QuoteCodeReference) from stg.HA1_HFQ_Quotes a join stg.hfq_payments b 
on a.QuoteCodeReference = b.QuoteReference
Where b.PaymentResponseResponseActionResultCode = 'SUCCESS' and 
PaymentResponseResponseTimestamp   between '2026-07-01' and '2026-07-31' 

# In[ ]:

--HA4b
SELECT 
a.channel,
COUNT(distinct a.PolicyCode) 
--*
FROM stg.GlobalPoliciesSold      a
Where   a.ReportingSaleType = 'New Business' 
and     a.PolicyTypeGroup = 'Home'
and     a.QuoteQueryGuid is null 
group by a.channel
--limit 10
;

# In[ ]:

--HA4.F1
--HA4b.O1

# In[ ]:

--HA5

select 
--* 
count(distinct QuoteReference)
--count(*)
from stg.HFQ_payments where PaymentResponseResponseActionResultCode = 'SUCCESS' and 
PaymentResponseResponseTimestamp   between '2026-07-01' and '2026-07-31' 
--limit 10

# In[ ]:

--HA5.F1

select 
count(distinct QuoteReference)
from stg.HFQ_payments 
where 
PaymentResponseResponseActionResultCode = 'DECLINED' 
and PaymentResponseResponseTimestamp   between '2026-07-01' and '2026-07-31' 
--limit 10

# In[ ]:

--HA5.B1

select 
--*
--PaymentResponseType,
count(*)
from stg.HFQ_payments 
where 
--PaymentResponseResponseActionResultCode = 'DECLINED' 
PaymentResponseResponseTimestamp   between '2026-07-01' and '2026-07-31' 
and isFullPayment = 'false'

# In[ ]:

--HA5.1

SELECT
count(distinct a.PolicyCode)
       --count(distinct a.PolicyCode)
from    stg.GlobalPoliciesSold                   a,
        ods.EventStream                          d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000'
and     ReportingSaleType = 'New Business'
and     EventDescription in
            (
                'New Business - Emailed Document - Terms Of Business',
                'New Business - Document Transmitted - Terms Of Business',
                'New Business - Emailed Document - Chill Terms of Business'
            );

# In[ ]:

--HA6

select 
		count(distinct PolicyCode)  
		from edw.exp_mychill_chase_daily_snapshot_home a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-07-01' and '2026-07-31' and PolicyType = 'New Business' 
and Campaign = 'DAY 1'
and 
case 
	when Gap_In_Cov_Ltr_Status = 'O' then 1 
	when Val_For_Spec_Item_Status = 'O' then 1 
	when PPS_Num_Status = 'O' then 1 
	When Identification_Status = 'O' then 1 
	when Finance_Form_Status = 'O' then 1 
	when Digital_Journey_Status = 'O' then 1 
	else 0
End = 1

# In[ ]:

--HA6.F1
--HA6.B1
--HA6.B1.F1

# In[ ]:

--HA7

select count(distinct PolicyCode)
FROM    stg.globalpoliciessold                   a,
        ods.eventstream                          d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime > '2026-07-01 00:00:00.000'
and     ReportingSaleType = 'New Business'
and     EventDescription in 
(
'New Business - Emailed Document - Terms Of Business',
'New Business - Document Transmitted - Terms Of Business',
'New Business - Emailed Document - Chill Terms of Business',
'New Business - Document Transmitted - Chill Terms of Business',
'New Business - Emailed Document - 05E Terms Of Business')

# In[ ]:

--HA7.B1
--HA7.B1.1

# In[ ]:

--HA7.B1.2

select count(distinct PolicyCode)
FROM    stg.globalpoliciessold                   a,
        ods.eventstream                          d
Where   a.PolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime > '2026-07-01 00:00:00.000'
and     ReportingSaleType = 'New Business'
and     (
            EventDescription like 'New Business - Emailed Document - %'     
        or  EventDescription like 'New Business - Document Transmitted - %' 
            )
and (
   EventDescription like '%04 - Suitability Statement'
Or EventDescription like '%05E Terms Of Business'
Or EventDescription like '%205 SOF- Proposal_Placeholder'
Or EventDescription like '%300 NB Home Email'
Or EventDescription like '%Chill Terms of Business'
Or EventDescription like '%Cover Letter'
Or EventDescription like '%CV Checklist Link'
Or EventDescription like '%CV Cover Letter'
Or EventDescription like '%CV Email Body'
Or EventDescription like '%CV Suitability Statment.'
Or EventDescription like '%Direct Debit Mandate'
Or EventDescription like '%Document Checklist Email'
Or EventDescription like '%Document Checklist SMS'
Or EventDescription like '%Gap In Cover Letter'
Or EventDescription like '%Home Cover Letter'
Or EventDescription like '%Home LOI_Placeholder'
Or EventDescription like '%Home Schedule_Placeholder'
Or EventDescription like '%Home SOF / Proposal_Placeholder'
Or EventDescription like '%Home Suitability Statement'
Or EventDescription like '%Insurance Product Information Document'
Or EventDescription like '%InsuranceProductInformationDocument'
Or EventDescription like '%Insurer Doc 1_Placeholder'
Or EventDescription like '%Insurer Doc 2_Placeholder'
Or EventDescription like '%Insurer Doc 3_Placeholder'
Or EventDescription like '%Interested Party'
Or EventDescription like '%Interested Party - Allied Irish Bank plc(AIB Mortgage Bank)'
Or EventDescription like '%Interested Party - Bank of Ireland (2 College Green)(Bank of Ireland)'
Or EventDescription like '%Interested Party - Bank of Ireland Mortgage Bank U.C.(College Green)'
Or EventDescription like '%Interested Party - Bank of Ireland Mortgages(Dublin - 2 College Green)'
Or EventDescription like '%Interested Party - Bank of Ireland(College Green)'
Or EventDescription like '%Interested Party - Bankinter SA(Maynooth)'
Or EventDescription like '%Interested Party - EBS D.A.C(Artane)'
Or EventDescription like '%Interested Party - Haven Mortgages Limited(Head Office)'
Or EventDescription like '%Interested Party - Permanent TSB(Dublin - Head Office)'
Or EventDescription like '%Interested Party - Permanent TSB(Head Office)'
Or EventDescription like '%InterestedParty'
Or EventDescription like '%Key Facts'
Or EventDescription like '%Premium Breakdown'
Or EventDescription like '%PremiumBreakdown'
Or EventDescription like '%Quote Breakdown'
Or EventDescription like '%Receipt'
Or EventDescription like '%Receipt_Template'
Or EventDescription like '%Schedule'
Or EventDescription like '%Statement Of Fact'
Or EventDescription like '%StatementOfFact'
Or EventDescription like '%Terms Of Business'
)

# In[ ]:

--HA6.B1.1
--HA6.B1.2
--HA6.B1.4
--HA6.B1.5
--HA6.B1.3
--HA6.B1.O1
--HA6.B1.6
--HA7.B1.1
--HA7.B1.2
--HA7.B1.3
--HA7.B1.4
--HA7.B1.5
--HR0
--HR0.F1
--HR0.F2
--HR0.F3
--HR0.1

# In[ ]:

--HR1a

Create or Replace Table stg.HR1a_Home_Renewals_EmailOffered as 
select  SourcePolicyReference, min(EventDateTime) OfferedDateTime
from    ods.EventStream                             a, 
        stg.R0_HomePoliciesEligibleForRenewals     b 
Where   EventDescription like 'Renewal Offer - Emailed Document %'
and     a.PolicyTypeGroup = 'Home'
and     a.SourcePolicyReference = b.PolicyCode 
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
Group by SourcePolicyReference
;

# In[ ]:

--HR1b

Create or Replace Table stg.HR1b_Home_Renewals_PostOffered as  
select  SourcePolicyReference, min(EventDateTime) OfferedDateTime
from    ods.EventStream a, stg.R0_HomePoliciesEligibleForRenewals b 
Where   EventDescription like 'Renewal Offer - Document Transmitted %'
and     a.PolicyTypeGroup = 'Home'
and     a.SourcePolicyReference = b.PolicyCode 
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
Group by SourcePolicyReference
;

# In[ ]:

--HR2

select  count(*), count(distinct ClientCode), count(distinct PolicyCode)
from    (
            select  left(PolicyCode,6) as ClientCode, dateadd(day, -40, RenewalDate) RenewalStartDate, PolicyCode, dateadd(day, 40, RenewalDate) RenewalEndDate
            from stg.R0_HomePoliciesEligibleForRenewals 
        )   a,
        dlk.appliedrenewals_successfulloginevent b 
Where   a.ClientCode = b.PortfolioCode 
and     b.`Timestamp` > a.RenewalStartDate
and     b.`Timestamp` < a.RenewalEndDate
;

# In[ ]:

--HR2.F1

# In[ ]:

--HR2.B1

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

select count(distinct PolicyCode), count(distinct QuoteCodeReference)
from stg.HomeRenewalsDoingHFQ 

# In[ ]:

--HR2.B1.F1

select count(distinct a.PolicyCode), count(distinct a.QuoteCodeReference)
from stg.HomeRenewalsDoingHFQ  a, stg.HFQ_Payments  b 
Where   PaymentResponseResponseActionResultCode = 'SUCCESS' and b.QuoteReference = a.QuoteCodeReference
and     PaymentResponseResponseTimestamp between '2026-07-01' and '2026-07-31' 

# In[ ]:

--HR1.E1
--HR1.E1.F1

# In[ ]:

--HR3a

select  count(*), count(distinct ClientCode), count(distinct PolicyCode)
from    (
            select  left(PolicyCode,6) as ClientCode, dateadd(day, -60, RenewalDate) RenewalStartDate, PolicyCode, dateadd(day, 40, RenewalDate) RenewalEndDate
            from stg.R0_HomePoliciesEligibleForRenewals 
        )   a,
        dlk.AppliedRenewals_PaymentSuccess b 
Where   PolicyCode = PolicyCodeForRenewal
and     b.`Timestamp` > a.RenewalStartDate
and     b.`Timestamp` < a.RenewalEndDate;

# In[ ]:

--HR3b

select  distinct TyPolicyCode,  TYReportingSaleDate
from    stg.R0_HomePoliciesEligibleForRenewals
Where   PolicyRetNum = 1 
and     Channel = 'a) IB' 

# In[ ]:

--HR3b.F1

# In[ ]:

--HR3.B1

Create or Replace Table stg.HR3B1_LapsedThisYearPolicy as 
select  distinct b.PolicyCode , b.RenewalDate
from    dlk.rbsdata2_policy_physical a, stg.R0_HomePoliciesEligibleForRenewals b
Where   trim(a.pl_code) = trim(b.PolicyCode)  -- trim is important as the source tables have trailing spaces -- Urska needs to address this 
and     trim(a.pl_status) = 'L' 

# In[ ]:

--HR3.O1

select  count(*) 
from    stg.HR3B1_LapsedThisYearPolicy 

# In[ ]:

--HR4

select count(distinct TyPolicyCode)
from stg.R0_HomePoliciesEligibleForRenewals 
Where PolicyRetNum = 1 

# In[ ]:

--HR4.B2
--HR4.B2.F1

# In[ ]:

--HR4a

Create or Replace Table stg.HR4_HomeRenewalsOnlinePayments as 
select  ClientCode, PolicyCode, max(`Timestamp`) PaymentDateTime 
from    (
            select  left(PolicyCode,6) as ClientCode, dateadd(day, -60, RenewalDate) RenewalStartDate, PolicyCode, dateadd(day, 40, RenewalDate) RenewalEndDate
            from stg.R0_HomePoliciesEligibleForRenewals 
        )   a,
        dlk.AppliedRenewals_PaymentSuccess b 
Where   ClientCode = b.PortfolioCode
and     b.`Timestamp` > a.RenewalStartDate
and     b.`Timestamp` < a.RenewalEndDate 
Group by ClientCode, PolicyCode
;    

# In[ ]: 

--HR4c

-- HR4a and HR4c -- Possible loan but old finance or new loan?  

select  PaymentType, count(distinct PolicyCode)
from    (
        select  PolicyCode, PaymentDateTime, b.PaymentType
        from    stg.HR4_HomeRenewalsOnlinePayments      a,
                dlk.AppliedRenewals_PaymentSuccess      b 
        Where   ClientCode = b.PortfolioCode
        and     b.`Timestamp` = a.PaymentDateTime
        ) x 
Group by PaymentType
;

# In[ ]: 

--HR5
--HR6

# In[ ]: 

--HR6.F1

select count(distinct PolicyCode) from ( 
        SELECT  a.PolicyCode, EventDescription, min(EventDateTime) EventDateTime
        FROM    stg.R0_HomePoliciesEligibleForRenewals  a,
                ods.EventStream                          d 
        Where   a.TyPolicyCode = d.SourcePolicyReference
        and     d.EventSourceId = 3 
        and     d.PolicyTypeGroup = 'Home'
        and     EventDateTime between '2026-06-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
        and     EventDescription like '%Suitability%'
        and     EventDescription not like 'Renewal Offer - %'
        AND     (
                    EventDescription like '%Emailed Document%'
                OR    
                    EventDescription like '%Document Transmitted%'
                )    
        Group by a.PolicyCode, EventDescription ) x 

# In[ ]: 

--HR6.B1

select count(*) from ( 
        SELECT  a.PolicyCode, min(EventDateTime) EventDateTime
        FROM    stg.R0_HomePoliciesEligibleForRenewals  a,
                ods.EventStream                          d 
        Where   a.TyPolicyCode = d.SourcePolicyReference
        and     d.EventSourceId = 3 
        and     d.PolicyTypeGroup = 'Home'
        and     EventDateTime between '2026-06-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
        AND      EventDescription not like 'Renewal Offer - %'            
        AND     (
                    EventDescription like '%Emailed Document%'
                OR    
                    EventDescription like '%Document Transmitted%'
                )    
        Group by a.PolicyCode ) x 

# In[ ]: 

--HR2.B1.1

Create or Replace Table stg.HR2B1_1_Base as 
SELECT  distinct b.PolicyCode, b.QuoteCodeReference, b.QuoteStartDatetime , RenEURPremOffer, TYEURGrossPremium, PolicyRetNum
FROM    stg.HomeRenewalsDoingHFQ                b,
        stg.R0_HomePoliciesEligibleForRenewals  c 
Where   b.PolicyCode = c.PolicyCode 
and     QuoteStartDateTime > '2026-05-01 00:00:00.000'

# In[ ]: 

--HR2.B1.2

select *  from stg.HR2B1_1_Base a, stg.hfq_prices b Where a.QuoteCodeReference = b.QuoteCodeReference 
limit 100 
-- ideally pull the last record or the least QuoteBestPrice for eventstream

# In[ ]: 

--HR2.B1.2.F1

# In[ ]: 

--HR2.B1.3.F1

select count(distinct PolicyCode) from stg.HR2B1_1_Base a, stg.hfq_prices b Where a.QuoteCodeReference = b.QuoteCodeReference and TyEurGrossPremium < QuoteBestPrice 

# In[ ]: 

--HR2.B1.O1

select count(distinct PolicyCode) from stg.HR2B1_1_Base a, stg.hfq_prices b 
Where a.QuoteCodeReference = b.QuoteCodeReference and TyEurGrossPremium = RenEurPremOffer and PolicyRetNum = 1 

# In[ ]: 

--HR2.B1.O2

select count(distinct PolicyCode) from stg.HR2B1_1_Base a, stg.hfq_prices b 
Where a.QuoteCodeReference = b.QuoteCodeReference and TyEurGrossPremium < RenEurPremOffer and PolicyRetNum = 1 

# In[ ]: 

--HR2.B1.O3

select count(distinct a.PolicyCode) from  stg.HR2B1_1_Base a left join stg.R0_HomePoliciesEligibleForRenewals b on a.PolicyCode = b.PolicyCode and PolicyRetNum = 1 
Where b.PolicyCode is null 

# In[ ]: 

--HR3.B1.1

select count(*) from  stg.R0_HomePoliciesEligibleForRenewals 
Where RenewalDate < TyReportingSaleDate 
limit 10 

# In[ ]: 

--HR3.B1.2
--HR3.B1.2.F1
--HR3.B1.O1
--HR3.B1.O3

# In[ ]: 

--HR4.B2.1

SELECT  count(distinct a.TyPolicyCode)
FROM    stg.R0_HomePoliciesEligibleForRenewals  a,
        ods.EventStream                          d 
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.PolicyTypeGroup = 'Home'
and     EventDateTime between '2026-06-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
and     EventDescription in 
        (
                'New Business - Saved Document - Document Checklist SMS',
                'New Business - Saved Document - Document Checklist Email'
            )  

# In[ ]: 

--HR4.B2.2

select  count(distinct b.PolicyCode)
from    stg.R0_HomePoliciesEligibleForRenewals a, dlk.MyChill_NewUploadDocumentEvents  b 
Where   a.TyPolicyCode = b.PolicyCode
and     `Timestamp` > '2026-05-01 00:00:00.000' 
and     `Timestamp` < '2026-09-01 00:00:00.000' 
limit 100
;

# In[ ]: 

--HR4.B2.4

# In[ ]: 

--HR4.B2.5

SELECT  distinct a.PolicyCode
FROM    stg.R0_HomePoliciesEligibleForRenewals     a,
        ods.EventStream                             d 
Where   a.TyPolicyCode = d.SourcePolicyReference
and     d.EventSourceId = 3 
and     EventDateTime > '2026-06-01 00:00:00.000' 
and     EventDateTime < '2026-09-01 00:00:00.000' 
and     EventDescription like '%Chase%' 
and     EventDescription like '%Final%' 

# In[ ]: 

--HR4.B2.3

# In[ ]: 

--HR4.B2.O1

select count(*) from ( 
        SELECT  a.PolicyCode, min(EventDateTime) EventDateTime
        FROM    stg.R0_HomePoliciesEligibleForRenewals  a,
                ods.EventStream                          d 
        Where   a.TyPolicyCode = d.SourcePolicyReference
        and     d.EventSourceId = 3 
        and     d.PolicyTypeGroup = 'Home'
        and     EventDateTime between '2026-06-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
        and     EventDescription not like 'Renewal Offer - %'
        and     EventDescription like '%Insurer Led Cancelation % Reg canx email template%'
        AND     (
                    EventDescription like '%Emailed Document%'
                OR    
                    EventDescription like '%Document Transmitted%'
                )    
        Group by a.PolicyCode ) x 

# In[ ]: 

--HR4.B2.6
--HR6.B1.1
--HR6.B1.2
--HR6.B1.5
--HM1
--HM1.F1
--HM2
--HM2.O1

select  count(distinct a.PolicyCode)
from    stg.JJulyMTAs a, stg.JulyPolicyState b 
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Home'
-- and     PremiumType = 'Mid Term Adjustment'
and     PolicyStatusDesc in (
     'Cancelled Mid Term' , 'Lapsed for Transfer'
) 

--HM3

select  count(distinct a.PolicyCode)
from    stg.JJulyMTAs a, stg.JulyPolicyState b 
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Home'
-- and     PremiumType = 'Mid Term Adjustment'
and     PolicyStatusDesc not in (
    'Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer'
) 

--HM4.B1

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

--HM4.B1.F1

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

--HM4
--HM4.F1
--HM4a
--HM4c

select  Count(distinct b.PolicyCode), sum(CCYGrossPremium), sum(CCYFees)
from    stg.JJulyMTAs a, stg.JulyPolicyState b 
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Home'
and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
and     ( 
            CCYGrossPremium = 0 
        and 
            CCYFees = 0 )

--HM5
--HM6

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

--HM6.B1
--HM4.B1.1

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
and     a.PolicyCode = d.SourcePolicyReference --0
           
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
        )    --28       

--HM4.B1.2

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
            

--HM4.B1.4

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

--HM4.B1.5

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

--HM4.B1.3

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
;

--HM4.B1.O1

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

--HM4.B1.6
--HM6.B1.1

*/
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

--HM6.B1.2
--HM6.B1.3
--HC1a

Create or Replace Table stg.JulyHomeCancellations as 
select  distinct PolicyStatusDesc,  ShortDescription, PolicyCode, ClientCode
from    edw.tbl_fact_policy_mtc 
Where   PolicyTypeGroup = 'Home'
and     EffectiveDate = '2026-07-31'

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

--HC1a.F1

select  *
from    edw.tbl_fact_policy_mtc 
Where   PolicyTypeGroup = 'Home'
and     EffectiveDate = '2026-07-31'
and     ShortDescription like '%NCT%'

--HC1b.F1
--HC2

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

--HC3

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

--HC4

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

--HC5

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

--HC6
--HARR.1
--HARR.2
--HARR.O1
--HARR.3
--HARR.O2
--HCL1a
--HCL1b
--HCL1c
--HCL4
--HCL.O2
--HD1
--HD1.F1
--HD2
--HD3.F1
--HD3.F2

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
from    stg.A0_genesys_derived_data 
Where   QueueName in ('INBOUND_VehicleChangeAddress',
'INBOUND_VehicleChangeOther',
'INBOUND_VehicleChange_Perm',
'INBOUND_VehicleChange_Temp',
'INBOUND_VehicleUpdateLicence',
'INBOUND_Vehicle_Add_Driver')
and     originatingDirection = 'inbound' 

--M1.F1

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
and abandoned = 1 and CallWaitTime > 0 
Group by ConversationId) x 

insert INTO
ods.EpisodeEventStream
(        
    SourcePolicyReference,
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

--M3
--M4
--M4a
--M5
--M6
--M.V1
--M.V2
--M.V3
--M.V4
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
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-07-01' and '2026-07-31' 
and PolicyTypeGroup = 'Motor' and a.PolicyCode = b.SourcePolicyReference 
and Campaign = 'DAY 1'

--M3.B1.2
--M3.B1.4
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
        'M3.B1.1',
        'Motor MTA - Chase, escalation',
        'Policy'
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a, stg.MotorMTAPolicies  b 
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-07-01' and '2026-07-31' 
and PolicyTypeGroup = 'Motor' and a.PolicyCode = b.SourcePolicyReference 
and Campaign = 'DAY 20'

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
        'M3.B1.1',
        'Motor MTA - Chase, escalation',
        'Policy'
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a, stg.MotorMTAPolicies  b, dlk.MyChill_NewUploadDocumentEvents  c 
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-07-01' and '2026-07-31' 
and     PolicyTypeGroup = 'Motor' and a.PolicyCode = b.SourcePolicyReference 
and     Campaign = 'DAY 1'
and     a.PolicyCode = c.PolicyCode
and     PolicyTypeGroup = 'Motor'
and     `Timestamp` > '2026-07-01 00:00:00.000' 
;

--M3.B1.6
--C1a
--C1a.F1
--C2
--C3
--C4

Create or replace table tmp.MotorEscalated20days as 
select  
		distinct PolicyCode 
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-07-01' and '2026-07-31' 
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

insert INTO
ods.EpisodeEventStream
(        
    SourcePolicyReference,
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
        max(date_trunc('MINUTE', EventDate)),
        max(EventDate as date),
        'C4',
        'Motor Cancellation - Final notice',
        'Policy'
from 
    (select	distinct SourcePolicyReference from ods.eventstream 
    where	EventSourceId = 3 
    and		EventDate between '2026-07-01' and '2026-07-31' 
    and		PolicyTypeGroup = 'Motor'
    and		upper(EventDescription) like '%CHASE%' 
    and		upper(EventDescription) like '%FINAL%' ) x ,
    tmp.MotorEscalated20days y 
Where     SourcePolicyReference = PolicyCode

--C5
--C6
--ARR.1
--ARR.2
--ARR.O1
--ARR.3
--ARR.O2
--CL1a
--D1
--D1.F1
--D2
--D3.F1
--D3.F2
--D.V1
--VR1a

Create or Replace Table stg.VanRenewals as 
select  PolicyCode, TYPolicyCode, LYPolicyRenewDateAdj, LYEURGrossPremium, LYEURCommission,	LYEURFees, RenEURPremInvite,	RenEURPremAlternative, RenEURFee, PolicyOfferNum, PolicyRetNum, TYReportingSaleType,	TYReportingSaleCategory,	TYReportingSaleDate,
TYEURGrossPremium,	TYEURCommission,	TYEURFees, Channel, RenewalsPortal,	SuccessfulLoginCount,FailedLoginCount, SuccessfulPaymentCount, FailedPaymentCount, DiaryPaymentTypeTY, PolicyCodeRevisedAtOffer
from    edw.tbl_fact_policy_renewals
where   RenewalMonth = '2026-07-31' 
and     LYPolicyTypeGroup = 'Van' 
Group by PolicyCode, TYPolicyCode, LYPolicyRenewDateAdj, LYEURGrossPremium, LYEURCommission,	LYEURFees, RenEURPremInvite,	RenEURPremAlternative, RenEURFee, PolicyOfferNum, PolicyRetNum, TYReportingSaleType,	TYReportingSaleCategory,	TYReportingSaleDate,
TYEURGrossPremium,	TYEURCommission,	TYEURFees, Channel, RenewalsPortal,	SuccessfulLoginCount,FailedLoginCount, SuccessfulPaymentCount, FailedPaymentCount, DiaryPaymentTypeTY, PolicyCodeRevisedAtOffer

insert INTO
ods.EpisodeEventStream
(        
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
        max(date_trunc('MINUTE', EventDateTime)),
        max(cast(EventDateTime as date)),
        'VR1a',
        'Van Renewals - Renewal invitation sent by EMAIL',
        'Policy'
from    ods.eventstream a, stg.VanRenewalsJuly b  
Where   a.SourcePolicyReference = b.PolicyCode
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
and     EventDescription like 'Renewal Offer - Emailed Document %'

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
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
and     EventDescription like 'Renewal Offer - Document Transmitted - %'

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
and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
and     interaction_type = 'sent' 
and     MessageType  in ( 'EMAIL', 'SMS') 
group by UserID

--VR2
--VR3a
--VR3b
--VR3b.F1
--VR3.B1


insert INTO
ods.EpisodeEventStream
(        
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

--VR3.O1
--VR4
--VR4.B2
--VR4.B2.F1
--VR5
--VR6.B1
--VR3.B1.1
--VR3.B1.2
--VR3.B1.2.F1
--VR3.B1.O1
--VR3.B1.O3
--VR4.B2.1
--VR4.B2.2
--VR4.B2.4
--VR4.B2.5
--VR4.B2.3
--VR4.B2.O1
--VR4.B2.6
--VR6.B1.1
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
AND     QuoteStartDateTime between '2026-07-01 00:00:00.000' and  '2026-08-01 00:00:00.000' 
Group by Email 

--VA0.F1

Create or Replace Table stg.Van_genesys_inbound_call_duration_summary as 
select	a.ConversationId, min(conversationStartTime) as conversationStartTime, 
            sum(agentAnswered) as agentAnswered, sum(alertNoAnswer) alertNoAnswer, sum(abandoned) abandoned, 
            sum(totalAcdWaitDuration) CallWaitTime, sum(totalAgentAlertDuration) CallRingTime, sum(totalAgentHoldDuration) CallHoldTime, sum(totalAgentTalkDuration) CallSpokenTime
from	stg.A0_genesys_derived_data	a
where	a.queueName = 'INBOUND_SALES_VAN'  
Group by ConversationId

insert INTO
ods.EpisodeEventStream
(        
    SourcePolicyReference,
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
        'Travel',
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'VA0',
        'Van Acquisition - Straight into the CALL CENTRE',
        'Quote'
from	stg.Van_genesys_inbound_call_duration_summary a 
Where   abandoned > 0 
group by a.conversationId;

--VA0

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

insert INTO
ods.EpisodeEventStream
(        
    SourcePolicyReference,
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
        'Travel',
        max(date_trunc('MINUTE', conversationStartTime)),
        max(cast(conversationStartTime as date)),
        'VA0',
        'Van Acquisition - Straight into the CALL CENTRE',
        'Quote'
from stg.Van_genesys_derived_data_filtered a
group by a.conversationId;

--VA5

Create or Replace Table stg.VanSales as 
select  PolicyCode, PolicyStatusDesc, Channel, FinanceFlag, RenewalTransferFlag, EURGrossPremium, EURFees, ReportingSaleCategory, ReportingSaleType, ReportingSalesDate
from    edw.tbl_fact_policy_sales 
where   EffectiveDate = '2026-07-31' 
and     PolicyTypeGroup = 'Van' 
and     ReportingSaleCategory = 'Cat A1: Active Sale'
and     PolicyCloseNum = 1 
Group by PolicyCode, PolicyStatusDesc, Channel, FinanceFlag, RenewalTransferFlag, EURGrossPremium, EURFees , ReportingSaleCategory, ReportingSaleType, ReportingSalesDate

insert INTO
ods.EpisodeEventStream
(        
    SourcePolicyReference,
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
        'Travel',
        max(date_trunc('MINUTE', ReportingSalesDate)),
        max(cast(ReportingSalesDate as date)),
        'VA5',
        'Van Acquisition - Payment successful',
        'Policy'
from stg.VanSales
where 
channel = 'a) Back Office' and ReportingSalesType = 'New Business'

--VA5.B1

insert INTO
ods.EpisodeEventStream
(        
    SourcePolicyReference,
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
WHERE   QuoteStartDateTime between '2026-07-01 00:00:00.000' and  '2026-08-01 00:00:00.000' 
and     PaymentStatus = 'Success'
and     PaymentType = 'Instalments'

--VA6
--VA6.B1
--VA6.B1.F1
--VA7
--VA7.B1
--VA5.B1.4
--VA6.B1.1
--VA6.B1.2
--VA6.B1.4
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
        'Motor',
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
and     EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
            (
                'Document Chase - Emailed Document - Chase Final Notice Email'
            )

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
        'Motor',
        max(date_trunc('MINUTE', `Timestamp`)),
        max(cast(`Timestamp` as date)),
        'VA6.B1.3',
        'Van Acquisition - Documents validated',
        'Policy'
from    stg.VanSales a, dlk.MyChillWorkflow_DocumentStatus  b 
Where   a.PolicyCode = b.PolicyCode
and     ReportingSaleType = 'New Business'  
and     `Timestamp` between '2026-07-01 00:00:00.000' and '2026-08-10 00:00:00.000' 

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
        'Motor',
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
and     EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
            (
                'Insurer Led Cancelation - Emailed Document - Reg canx email template'
            )

--VA6.B1.6

--?

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
        'Motor',
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
and     EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
            (
                'New Business - Printed Document - CD Issue Letter CV' 
            )

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
        'Motor',
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
and     EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
            (
                'New Business - Emailed Document - 05E Terms Of Business',
                'New Business - Document Transmitted - 05E Terms Of Business',
                'New Business - Document Transmitted - Terms Of Business'
            )
            
--VA7.B1.3
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
        'Motor',
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
and     EventDateTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
            (
                'New Business - Printed Document - CD Issue Letter MTA'
            )
            
--VM1
--VM1.F1
--VM2.O1
--VM3
--VM3.B1
--VM3.B1.F1
--VM4c
--VM6
--VM6.B1
--VM3.B1.1
--VM3.B1.2
--VM3.B1.4
--VM3.B1.5
--VM3.B1.3
--VM3.B1.O1
--VM3.B1.6
--VM6.B1.1
--VM6.B1.2
--VM6.B1.3
--VM6.B1.4
--VM6.B1.5
--VC1a
--VC1b.F1
--VC2
--VC3
--VC4
--VC5
--VC6
--VARR.1
--VARR.2
--VARR.O1
--VARR.3
--VARR.4
--VARR.O2
--VCL1a
--VD1
--VD1.F1
--VD2
--VD3.F1
--VD3.F2
--VD.V1
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
WHERE Travel_QuoteDate BETWEEN  '2026-07-01' and '2026-07-31' 
AND rtrim(ltrim(travel_certificatestatus)) IN ('Completed Quote','Incomplete Quote','Cancelled','Live')
and len(email)>0

--TA1p

Create or Replace table stg.TravelQuotes 
select	quote_number, 'Q' as SourceType , travel_certificatestatus, travel_purchaseDate, case when business_type = 'Renewal' then 1 else 0 end RenewalFlag
FROM dlk.EXT_Travel_Quotes 
    WHERE Travel_QuoteDate BETWEEN  '2026-07-01' and '2026-07-31' 
	     AND rtrim(ltrim(travel_certificatestatus)) IN ('Completed Quote','Incomplete Quote','Cancelled')   and len(email)>0
Group by quote_number, travel_certificatestatus, travel_purchaseDate, case when business_type = 'Renewal' then 1 else 0 end 
union all 
select p.QuoteId, 'P' , RecordType , p.PurchaseDate, RenewalFlag,
FROM dlk.EXT_Travel_policy p
	left join dlk.EXT_Travel_Quotes  q on p.QuoteId = q.quote_number 
WHERE p.PurchaseDate BETWEEN  '2026-07-01' and '2026-07-31'	
and	  q.quote_number is null 	
Group by p.QuoteId , RecordType ,p.PurchaseDate, RenewalFlag
union all 
select p.QuoteId, 'P' , q.travel_certificatestatus , p.PurchaseDate, RenewalFlag
FROM dlk.EXT_Travel_policy p
	join dlk.EXT_Travel_Quotes  q on p.QuoteId = q.quote_number 
WHERE p.PurchaseDate BETWEEN  '2026-07-01' and '2026-07-31'	
Group by p.QuoteId ,q.travel_certificatestatus , p.PurchaseDate, RenewalFlag
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
from   stg.TravelQuotes
where travel_purchaseDate between  '2026-07-01' and '2026-07-31'	
and RenewalFlag = 0

--TA3.B1.2
--TR1.E1
--TR4
--TR.O1
