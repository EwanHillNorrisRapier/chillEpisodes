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
Where   a. LyPolicyTypeGroup = 'Vam' 
and     a.LYPolicyRenewDateAdj >= (select startTime from stg.episodeeventstream_buildconfig) and a.LYPolicyRenewDateAdj < (select endTime   from stg.episodeeventstream_buildconfig) 
and     PolicyOfferNum = 1 
Group by   PolicyCode, LyPolicyRenewDateAdj, TyPolicyCode  , TyPolicyRenewDateAdj


Create Table stg.MotorMTAPolicies as 
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
        'Quote'
from    dlk.EXT_XtremePushResults
where	`timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
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
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
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
        'Motor Acquisition - Customer submits documents',
        'Policy'
from    stg.GlobalPoliciesSold a, dlk.MyChillWorkflow_DocumentStatus  b 
Where   a.PolicyCode = b.PolicyCode
and     ReportingSaleType = 'New Business' 
and     PolicyTypeGroup = 'Motor'
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
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
--R0.B1
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
--R1.E1
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
            and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
            and     interaction_type = 'sent'
            and     MessageType  in ( 'EMAIL', 'SMS')
            union
            select  distinct b.PolicyCode, a.`timestamp` as SentTimestamp
            from    dlk.EXT_XtremePushResults_Policy a, stg.R0_MotorPoliciesEligibleForRenewals b
            where   campaign_name like '%Motor%'
            and     campaign_name like '%TYR%'
            and     a.PolicyCode = b.PolicyCode
            and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
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
        'R3c',
        'Motor Renewal - Customer renews ONLINE',
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
;

# In[ ]:


--R3.B1
-- BLOCK HEADER. R3.B1 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from R3.B1.1, R3.B1.2, R3.B1.3, R3.B1.4.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

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
            and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
            and     interaction_type = 'sent'
            and     MessageType  in ( 'EMAIL', 'SMS')
            union
            select  distinct b.PolicyCode, a.`timestamp` as SentTimestamp
            from    dlk.EXT_XtremePushResults_Policy a, stg.R0_MotorPoliciesEligibleForRenewals b
            where   campaign_name like '%Motor%'
            and     campaign_name like '%Lapsed%'
            and     a.PolicyCode = b.PolicyCode
            and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
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

-- from XX - Episode Reconciliation - Gaps.html, cell 21 (count query)
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

# In[ ]:
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
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
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
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
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
and     EventDescription like 'Duplicate Certificate%'
Group by a.PolicyCode;

# Home Acquisitions

# In[ ]:

--HA1
-- converted from the count query. The staging table stg.HA1_HFQ_Quotes is built first in the same cell and the timestamp is the earliest ts_unix on each quote.

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

-- ALTERNATIVE VERSION for HA1.E1, from XX - Episode Reconciliation - Gaps.html cell 25
-- The HA1.E1 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
-- header: HA1.E1
select  count(distinct email), count(*)
from	dlk.EXT_XtremePushResults   a 
where	`timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
and		campaign_name like 'Home % TYR %' 
and     interaction_type = 'sent' 
and     MessageType in ('SMS', 'EMAIL')
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

Create or Replace Table stg.HA0F1_genesys_inbound_call_duration_summary as
select	a.ConversationId, min(a.conversationStartTime) as conversationStartTime,
        sum(a.agentAnswered) as agentAnswered, sum(a.alertNoAnswer) alertNoAnswer, sum(a.abandoned) abandoned,
        sum(a.totalAcdWaitDuration) CallWaitTime, sum(a.totalAgentAlertDuration) CallRingTime,
        sum(a.totalAgentHoldDuration) CallHoldTime, sum(a.totalAgentTalkDuration) CallSpokenTime
from	stg.A0_genesys_derived_data	a
where	a.queueName = 'INBOUND_SALES_HOME'
Group by a.ConversationId
;

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

-- ALTERNATIVE VERSION for HA6, from XX - Episode Reconciliation - Gaps.html cell 28
-- The HA6 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
-- header: HA6
select 
		count(distinct PolicyCode)  
		from edw.exp_mychill_chase_daily_snapshot_home a
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig) and PolicyType = 'New Business' 
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
--HA7.B1.1
--HA7.B1.2
--HA7.B1.3
--HA7.B1.4
--HA7.B1.5
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
and     b.TransactionDate between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000'
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
--HR0.F3
--HR0.1

# In[ ]:

--HR1a
-- converted from the count query. The staging table is built first and kept as written, including its renewal lookback from 2026-05-01 to 2026-08-01, so no build config run window applies.

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

insert INTO
ods.EpisodeEventStream
(
    SourcePolicyReference,
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

Create or Replace Table stg.HR1b_Home_Renewals_PostOffered as
select  SourcePolicyReference, min(EventDateTime) OfferedDateTime
from    ods.EventStream a, stg.R0_HomePoliciesEligibleForRenewals b
Where   EventDescription like 'Renewal Offer - Document Transmitted %'
and     a.PolicyTypeGroup = 'Home'
and     a.SourcePolicyReference = b.PolicyCode
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000'
Group by SourcePolicyReference
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
and     a.ConversationStartTime between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000'
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

-- Staging tables that the HR2.B1 block needs. These were inlined in the HR2.B1 cell before its
-- insert was removed as a block header, so they are kept here. They build data only and write
-- nothing to the event stream.

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
where   a.`timestamp` between '2026-06-01 00:00:00.000' and '2026-09-01 00:00:00.000'
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
where   a.`timestamp` between '2026-06-01 00:00:00.000' and '2026-09-01 00:00:00.000'
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

# In[ ]:

--HR3.B1

-- Staging tables that the HR3.B1 block needs. These were inlined in the HR3.B1 cell before its
-- insert was removed as a block header, so they are kept here. They build data only and write
-- nothing to the event stream.

Create or Replace Table stg.HR3B1_LapsedThisYearPolicy as
select  distinct b.PolicyCode , b.RenewalDate
from    dlk.rbsdata2_policy_physical a,
        stg.R0_HomePoliciesEligibleForRenewals b
Where   trim(a.pl_code) = trim(b.PolicyCode)  -- trim is important as the source tables have trailing spaces
and     trim(a.pl_status) = 'L'
;

-- BLOCK HEADER. HR3.B1 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from HR3.B1.1, HR3.B1.2.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

# In[ ]:

-- ALTERNATIVE VERSION for HR3.B1, from XX - Episode Reconciliation - Gaps.html cell 17
-- The HR3.B1 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
-- header: Home	Renewal	HR3.B1
select	count(distinct a.PolicyCode)
from	dlk.EXT_XtremePushResults    a, stg.R0_HomePoliciesEligibleForRenewals b 
where	`timestamp` between '2026-06-01 00:00:00.000' and '2026-09-01 00:00:00.000' 
and     a.PolicyCode = b.PolicyCode 
and		campaign_name like 'Home - This Year Lapsed%' 
and     MessageType in ( 'EMAIL', 'SMS')
and     interaction_type = 'sent'
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
--HR4.B2.F1

-- see the HR4.B2 cell: XX - Episode Reconciliation - Gaps.html cell 18 covers HR4.B2, HR4.B2.F1

-- see the HR4.B2 cell: XX - Episode Reconciliation - Gaps.html cell 24 covers HR4.B2, HR4.B2.F1

# In[ ]:

--HR4a
-- converted from the count query. The staging table is built first because HR4c reads it, no pay in full filter is added because the original query applies none, and the T-60 to T+40 renewal lookback is kept exactly as it is so no build config run window applies.

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

insert INTO
ods.EpisodeEventStream
(
    SourcePolicyReference,
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
--HR6

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

# In[ ]: 

--HR6.B1
-- BLOCK HEADER. HR6.B1 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from HR6.B1.1, HR6.B1.2, HR6.B1.3, HR6.B1.4, HR6.B1.5.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

# In[ ]: 

--HR2.B1.1
-- converted from the count query. The staging table is built first because later steps read it, the source is HFQ so SourceSystemId is 2, and the lookback from 2026-05-01 is kept exactly as it is so no build config run window applies.

Create or Replace Table stg.HR2B1_1_Base as
SELECT  distinct b.PolicyCode, b.QuoteCodeReference, b.QuoteStartDatetime , RenEURPremOffer, TYEURGrossPremium, PolicyRetNum
FROM    stg.HomeRenewalsDoingHFQ                b,
        stg.R0_HomePoliciesEligibleForRenewals  c
Where   b.PolicyCode = c.PolicyCode
and     b.QuoteStartDateTime > '2026-05-01 00:00:00.000'
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
--HR3.B1.2.F1
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
where   a.`timestamp` between '2026-06-01 00:00:00.000' and '2026-09-01 00:00:00.000'
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
where   a.`timestamp` between '2026-06-01 00:00:00.000' and '2026-09-01 00:00:00.000'
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
and     d.EventDateTime between '2026-06-01 00:00:00.000' and '2026-08-01 00:00:00.000'
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
and     b.`Timestamp` > '2026-05-01 00:00:00.000'
and     b.`Timestamp` < '2026-09-01 00:00:00.000'
Group by b.PolicyCode
;

# In[ ]: 

--HR4.B2.4

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
and     d.EventDateTime > '2026-06-01 00:00:00.000'
and     d.EventDateTime < '2026-09-01 00:00:00.000'
and     d.EventDescription like '%Chase%'
and     d.EventDescription like '%Final%'
Group by a.PolicyCode
;

# In[ ]: 

--HR4.B2.3

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
and     d.EventDateTime between '2026-06-01 00:00:00.000' and '2026-08-01 00:00:00.000'
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
--HR6.B1.1
--HR6.B1.2
--HR6.B1.5
--HM1
--HM1.F1
--HM2
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
--HM4a
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
--HM6.B1.3
--HC1a
-- converted from the count query. The staging table build is kept because later HC steps read it. The
-- cancellation request itself carries no timestamp on edw.tbl_fact_policy_mtc, so PolicyCancelDate from
-- stg.JulyPolicyState is used. That is when the cancellation took effect, not when the customer asked.
-- The ShortDescription filter is the one the original breakdown query used to isolate customer requests.

Create or Replace Table stg.JulyHomeCancellations as
select  distinct PolicyStatusDesc,  ShortDescription, PolicyCode, ClientCode
from    edw.tbl_fact_policy_mtc
Where   PolicyTypeGroup = 'Home'
and     EffectiveDate = '2026-07-31'
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
    date_trunc('MINUTE', max(b.PolicyCancelDate)),
    cast(max(b.PolicyCancelDate) as date),
    'HC1a',
    'Home Cancellation - Customer asks to cancel',
    'Policy'
from    edw.tbl_fact_policy_mtc a,
        stg.JulyPolicyState     b
Where   a.PolicyCode = b.PolicyCode
and     a.PolicyTypeGroup = 'Home'
and     a.EffectiveDate = '2026-07-31'
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
and     a.EffectiveDate = '2026-07-31'
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
Group by a.ConversationId

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
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig) 
and PolicyTypeGroup = 'Motor' and a.PolicyCode = b.SourcePolicyReference 
and Campaign = 'DAY 1'
Group by b.SourcePolicyReference

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
        'M3.B1.1',
        'Motor MTA - Chase, escalation',
        'Policy'
from edw.EXP_MyChill_Chase_Daily_Snapshot_MotorVan a, stg.MotorMTAPolicies  b, dlk.MyChill_NewUploadDocumentEvents  c 
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig) 
and     PolicyTypeGroup = 'Motor' and a.PolicyCode = b.SourcePolicyReference 
and     Campaign = 'DAY 1'
and     a.PolicyCode = c.PolicyCode
and     PolicyTypeGroup = 'Motor'
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
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
Group by b.SourcePolicyReference

insert INTO
ods.EpisodeEventStream
(        
    SourcePolicyReference,
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
    and		EventDate >= (select startTime from stg.episodeeventstream_buildconfig) and EventDate < (select endTime   from stg.episodeeventstream_buildconfig) 
    and		PolicyTypeGroup = 'Motor'
    and		upper(EventDescription) like '%CHASE%' 
    and		upper(EventDescription) like '%FINAL%' ) x ,
    tmp.MotorEscalated20days y 
Where     SourcePolicyReference = PolicyCode
Group by a.SourcePolicyReference

--C5
--C6
--ARR.1
--ARR.2
--ARR.O1
--ARR.3
--ARR.O2
--CL1a
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

--D1.F1

-- see the HD1.F1 cell: XX - Episode Reconciliation - Gaps.html cell 74 covers HD1.F1, D1.F1, VD1.F1

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
--D3.F2

-- see the HD3.F2 cell: XX - Episode Reconciliation - Gaps.html cell 79 covers HD3.F2, D3.F2, VD3.F2
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
and     EventDateTime between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000' 
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
and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-01 00:00:00.000' 
and     interaction_type = 'sent' 
and     MessageType  in ( 'EMAIL', 'SMS') 
group by UserID

--VR2

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
Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-05-01' and '2026-07-31'
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
        and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
        and     interaction_type = 'sent'
        and     MessageType  in ( 'EMAIL', 'SMS')
        union
        select  b.PolicyCode, a.`timestamp`
        from    dlk.EXT_XtremePushResults_Policy a, stg.VanRenewalsJuly b
        where   campaign_name like '%Van%'
        and     campaign_name like '%Lapsed%'
        and     a.PolicyCode = b.PolicyCode
        and     `timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
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
Group by a.PolicyCode
;

# In[ ]:
--VR3.B1.O1
--VR3.B1.O3
--VR4.B2.1
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
            and     `Timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
            UNION
            select  b.PolicyCode, b.`Timestamp`
            from    stg.VanRenewalsJuly a, dlk.MyChill_NewUploadDocumentEvents  b
            Where   a.TyPolicyCode = b.PolicyCode
            and     `Timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
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
        Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') between '2026-05-01' and '2026-07-31'
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
            and     `Timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
            UNION
            select  b.PolicyCode, b.`Timestamp`
            from    stg.VanRenewalsJuly a, dlk.MyChillWorkflow_DocumentStatus  b
            Where   a.TyPolicyCode = b.PolicyCode
            and     `Timestamp` between '2026-05-01 00:00:00.000' and '2026-08-10 00:00:00.000'
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

-- from XX - Episode Reconciliation - Gaps.html, cell 104 (note or select)
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
Group by a.PolicyCode

--VA5.B1
-- BLOCK HEADER. VA5.B1 is the heading for its sub-steps, not an event in its own right,
-- so it writes nothing to the event stream. The events come from VA5.B1.1, VA5.B1.2, VA5.B1.3, VA5.B1.4, VA5.B1.5.
-- The insert that used to sit here was removed on 14 September 2026 because it double
-- counted one of those sub-steps. It is kept in Removed_block_header_inserts.py.

--VA6
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
;

# In[ ]:
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
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
            (
                'Insurer Led Cancelation - Emailed Document - Reg canx email template'
            )
Group by a.PolicyCode

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
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
            (
                'New Business - Emailed Document - 05E Terms Of Business',
                'New Business - Document Transmitted - 05E Terms Of Business',
                'New Business - Document Transmitted - Terms Of Business'
            )
Group by a.PolicyCode
            
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
and     EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig) 
and     ReportingSaleType = 'New Business' 
and     EventDescription in 
            (
                'New Business - Printed Document - CD Issue Letter MTA'
            )
Group by a.PolicyCode
            
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

--VD1.F1

-- see the HD1.F1 cell: XX - Episode Reconciliation - Gaps.html cell 74 covers HD1.F1, D1.F1, VD1.F1

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
--VD3.F2

-- see the HD3.F2 cell: XX - Episode Reconciliation - Gaps.html cell 79 covers HD3.F2, D3.F2, VD3.F2
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
WHERE Travel_QuoteDate >= (select startTime from stg.episodeeventstream_buildconfig) and Travel_QuoteDate < (select endTime   from stg.episodeeventstream_buildconfig) 
AND rtrim(ltrim(travel_certificatestatus)) IN ('Completed Quote','Incomplete Quote','Cancelled','Live')
and len(email)>0

--TA1p

Create or Replace table stg.TravelQuotes 
select	quote_number, 'Q' as SourceType , travel_certificatestatus, travel_purchaseDate, case when business_type = 'Renewal' then 1 else 0 end RenewalFlag
FROM dlk.EXT_Travel_Quotes 
    WHERE Travel_QuoteDate >= (select startTime from stg.episodeeventstream_buildconfig) and Travel_QuoteDate < (select endTime   from stg.episodeeventstream_buildconfig) 
	     AND rtrim(ltrim(travel_certificatestatus)) IN ('Completed Quote','Incomplete Quote','Cancelled')   and len(email)>0
Group by quote_number, travel_certificatestatus, travel_purchaseDate, case when business_type = 'Renewal' then 1 else 0 end 
union all 
select p.QuoteId, 'P' , RecordType , p.PurchaseDate, RenewalFlag,
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

insert INTO
ods.EpisodeEventStream
(        
    SourcePolicyReference,
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
from   stg.TravelQuotes
where travel_purchaseDate >= (select startTime from stg.episodeeventstream_buildconfig) and travel_purchaseDate < (select endTime   from stg.episodeeventstream_buildconfig)	
and RenewalFlag = 0
Group by a.quote_number

--TA3.B1.2
--TR1.E1
--TR4
--TR.O1


# In[ ]:

-- ALTERNATIVE VERSION for HM3, from XX - Episode Reconciliation - Gaps.html cell 37
-- The HM3 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
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

-- ALTERNATIVE VERSION for HM3, from XX - Episode Reconciliation - Gaps.html cell 39
-- The HM3 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
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

-- ALTERNATIVE VERSION for HM2.O1, from XX - Episode Reconciliation - Gaps.html cell 40
-- The HM2.O1 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
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

-- ALTERNATIVE VERSION for HM4.B1, from XX - Episode Reconciliation - Gaps.html cell 41
-- The HM4.B1 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
-- header: Home	MTA	HM4.B1  - the base policy list is the one to be confirmed
select  count(distinct b.PolicyCode)
from    stg.JJulyMTAs a, dlk.MyChill_NewUploadDocumentEvents  b 
Where   a.PolicyCode = b.PolicyCode
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
and     b.PolicyCode in 
        (
            select  distinct a.PolicyCode
            from    stg.JJulyMTAs a, stg.JulyPolicyState b 
            Where   a.PolicyCode = b.PolicyCode
            and     PolicyTypeGroup = 'Home'
            and     PolicyStatusDesc not in ('Cancelled', 'Lapsed', 'Cancelled Mid Term' , 'Lapsed for Transfer') 
        )

# In[ ]:

-- ALTERNATIVE VERSION for HM4.B1.F1, from XX - Episode Reconciliation - Gaps.html cell 42
-- The HM4.B1.F1 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
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

-- ALTERNATIVE VERSION for HM4c, from XX - Episode Reconciliation - Gaps.html cell 47
-- The HM4c cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
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

-- ALTERNATIVE VERSION for HM6, from XX - Episode Reconciliation - Gaps.html cell 49
-- The HM6 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
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
and     EventDate >= (select startTime from stg.episodeeventstream_buildconfig) and EventDate < (select endTime   from stg.episodeeventstream_buildconfig)
and     EventSourceId = 3 
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        )

# In[ ]:

-- ALTERNATIVE VERSION for HM4.B1.1, from XX - Episode Reconciliation - Gaps.html cell 50
-- The HM4.B1.1 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
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
and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)  
and     EventDescription like '% Body' 
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        )
and     a.PolicyCode = d.SourcePolicyReference

# In[ ]:

-- ALTERNATIVE VERSION for HM4.B1.1, from XX - Episode Reconciliation - Gaps.html cell 51
-- The HM4.B1.1 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
-- header: Home	MTA	HM4.B1.1
select  count(distinct PolicyCode)
From    (
            select  PolicyCode  
                    from edw.exp_mychill_chase_daily_snapshot_home a
            Where	coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') >= (select startTime from stg.episodeeventstream_buildconfig) and coalesce(try_cast(concat(right(SaleDate,4), '-',substring(SaleDate,4,2),'-',left(SaleDate,2)) as date),'1900-01-01') < (select endTime   from stg.episodeeventstream_buildconfig) and PolicyType = 'New Business' 
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

-- ALTERNATIVE VERSION for HM4.B1.2, from XX - Episode Reconciliation - Gaps.html cell 52
-- The HM4.B1.2 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
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
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig)

# In[ ]:

-- ALTERNATIVE VERSION for HM4.B1.4, from XX - Episode Reconciliation - Gaps.html cell 53
-- The HM4.B1.4 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
-- header: Home	MTA	HM4.B1.4
select  count(distinct PolicyCode)
From    (
            select  PolicyCode  
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

-- ALTERNATIVE VERSION for HM4.B1.5, from XX - Episode Reconciliation - Gaps.html cell 54
-- The HM4.B1.5 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
-- header: Home	MTA	HM4.B1.5
select  count(distinct PolicyCode)
From    (
            select  PolicyCode  
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

-- ALTERNATIVE VERSION for HM4.B1.3, from XX - Episode Reconciliation - Gaps.html cell 55
-- The HM4.B1.3 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
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
and     `Timestamp` >= (select startTime from stg.episodeeventstream_buildconfig) and `Timestamp` < (select endTime   from stg.episodeeventstream_buildconfig) 
/*and     isAccepted IsRejected */
Group by isAccepted
limit 100
;

# In[ ]:

-- ALTERNATIVE VERSION for HM4.B1.O1, from XX - Episode Reconciliation - Gaps.html cell 56
-- The HM4.B1.O1 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
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
Group by EventDescription

# In[ ]:

-- ALTERNATIVE VERSION for HM6.B1.1, from XX - Episode Reconciliation - Gaps.html cell 57
-- The HM6.B1.1 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
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
and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)  
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        )
and     a.PolicyCode = d.SourcePolicyReference 
Group by EventDescription               
Order by 2 desc

# In[ ]:

-- ALTERNATIVE VERSION for HM6.B1.1, from XX - Episode Reconciliation - Gaps.html cell 58
-- The HM6.B1.1 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
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
and     d.EventDateTime >= (select startTime from stg.episodeeventstream_buildconfig) and d.EventDateTime < (select endTime   from stg.episodeeventstream_buildconfig)  
and     (   EventDescription like '%Emailed Document%' 
        or 
            EventDescription like '%Document Transmitted%'
        )
and     a.PolicyCode = d.SourcePolicyReference 
Group by EventDescription               
Order by 2 desc

# In[ ]:

-- ALTERNATIVE VERSION for HM6.B1.1, from XX - Episode Reconciliation - Gaps.html cell 59
-- The HM6.B1.1 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
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

# In[ ]:

-- ALTERNATIVE VERSION for HC1a, from XX - Episode Reconciliation - Gaps.html cell 62
-- The HC1a cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
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

-- ALTERNATIVE VERSION for HC2, from XX - Episode Reconciliation - Gaps.html cell 64
-- The HC2 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
-- header: Home	CANCELLATION	HC2
select  Count(distinct a.PolicyCode)  
from    (select  distinct PolicyCode  
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
                )               a,
        stg.JulyHomeCancellations   b
Where   left(a.PolicyCode,6) = b.ClientCode

# In[ ]:

-- ALTERNATIVE VERSION for HC3, from XX - Episode Reconciliation - Gaps.html cell 65
-- The HC3 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
-- header: Home	CANCELLATION	HC3
select  Count(distinct a.PolicyCode)  
from    (select  PolicyCode  
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
            and Campaign <> 'DAY 1'  /* first is request and all the next are escalation I think - when we go daily build, we could do that */
                )               a,
        stg.JulyHomeCancellations   b
Where   left(a.PolicyCode,6) = b.ClientCode

# In[ ]:

-- ALTERNATIVE VERSION for HC4, from XX - Episode Reconciliation - Gaps.html cell 66
-- The HC4 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
-- header: Home	CANCELLATION	HC4
select  Count(distinct SourcePolicyReference) 
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
-- left(a.SourcePolicyReference,6) = b.PolicyCode

# In[ ]:

-- ALTERNATIVE VERSION for HC5, from XX - Episode Reconciliation - Gaps.html cell 67
-- The HC5 cell above already had content, so this was not merged into it.
-- Review the two, keep one, then delete this cell.
-- header: Home	CANCELLATION	HC5
select  Count(distinct SourcePolicyReference) 
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

# Gaps export: cells with no step id

# In[ ]:

-- The cells below come from XX - Episode Reconciliation - Gaps.html and had no step id in their header.
-- Several are staging table builds that the queries above depend on, so they
-- need a home in the Derived Data section once you decide where they belong.


# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 0 (count query)
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

-- from XX - Episode Reconciliation - Gaps.html, cell 12 (note or select)
-- header: worthwhile to know
select	EventType, count(*), count(distinct PolicyCode)
from	dlk.ext_home_qs_policydetails 
Where	TransactionDate >= (select startTime from stg.episodeeventstream_buildconfig) and TransactionDate < (select endTime   from stg.episodeeventstream_buildconfig)
Group by EventType

/* Even though not sure if this is used in SQL 09 reports */


# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 20 (count query)
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

-- from XX - Episode Reconciliation - Gaps.html, cell 26 (count query)
select count(distinct QuoteCodeReference) from stg.HA1_HFQ_Quotes
limit 10


# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 36 (staging table build)
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

-- from XX - Episode Reconciliation - Gaps.html, cell 38 (note or select)
select  PolicyTypeGroup, PremiumType, count(*)
from    stg.JJulyMTAs a, stg.JulyPolicyState b 
Where a.PolicyCode = b.PolicyCode
Group by PolicyTypeGroup, PremiumType
limit 100


# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 45 (note or select)
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

-- from XX - Episode Reconciliation - Gaps.html, cell 46 (note or select)
-- header: FINR20001
-- header: MULC8K007
Select  *
from    stg.JJulyMTAs a, stg.JulyPolicyState b 
Where   a.PolicyCode = b.PolicyCode
and     PolicyTypeGroup = 'Home'
and     a.PolicyCode = '0YAJ41002'


# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 48 (note or select)
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
and     EventDate >= (select startTime from stg.episodeeventstream_buildconfig) and EventDate < (select endTime   from stg.episodeeventstream_buildconfig)
and     EventSourceId = 3 
Group by EventDescription
Order by 2 desc 
/*
    Emailed Document
    Document Transmitted
*/


# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 60 (staging table build)
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

-- from XX - Episode Reconciliation - Gaps.html, cell 61 (note or select)
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

-- from XX - Episode Reconciliation - Gaps.html, cell 68 (note or select)



# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 69 (staging table build)
-- header: Doc Request
Create or Replace table stg.DocRequestCustomers as 
Select  CustomerPhoneNumber, ConversationStartTime, ConversationId
from    stg.A0_genesys_derived_data
Where   ConversationStartTime >= (select startTime from stg.episodeeventstream_buildconfig) and ConversationStartTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     QueueName = 'INBOUND_Documents_Out'
Group by CustomerPhoneNumber, ConversationStartTime, ConversationId


# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 70 (staging table build)
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

-- from XX - Episode Reconciliation - Gaps.html, cell 71 (note or select)
select * from stg.DocRequestClientCodes limit 10


# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 73 (note or select)
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

-- from XX - Episode Reconciliation - Gaps.html, cell 80 (staging table build)
-- header: Claims
Create or Replace table stg.ClaimCustomers as 
Select  CustomerPhoneNumber, ConversationStartTime, ConversationId
from    stg.A0_genesys_derived_data
Where   ConversationStartTime >= (select startTime from stg.episodeeventstream_buildconfig) and ConversationStartTime < (select endTime   from stg.episodeeventstream_buildconfig)
and     QueueName = 'INBOUND_Claims'
Group by CustomerPhoneNumber, ConversationStartTime, ConversationId


# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 81 (staging table build)
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

-- from XX - Episode Reconciliation - Gaps.html, cell 82 (note or select)
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

-- from XX - Episode Reconciliation - Gaps.html, cell 90 (count query)
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

-- from XX - Episode Reconciliation - Gaps.html, cell 92 (note or select)
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

-- from XX - Episode Reconciliation - Gaps.html, cell 105 (note or select)
select  OriginatingDirection , 
        case when ANI like '%anonymous%' then 'anonymous' else 'normal' end, 
        count(*) from (
select DISTINCT replace(ani, 'tel:+', '' ) ANI, conversationstarttime , OriginatingDirection 
from dlk.genesys_session_summary 
where conversationstarttime >= (select startTime from stg.episodeeventstream_buildconfig) and conversationstarttime < (select endTime   from stg.episodeeventstream_buildconfig)
and queuename = 'INBOUND_SALES_MOTOR') x group by OriginatingDirection , case when ANI like '%anonymous%' then 'anonymous' else 'normal' end  
ORder by 1


# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 106 (staging table build)
Create or Replace Table stg.MarieJulyGenesysReconciliation as 
select DISTINCT replace(ani, 'tel:+', '' ) ANI, conversationstarttime , OriginatingDirection 
from dlk.genesys_session_summary 
where conversationstarttime >= (select startTime from stg.episodeeventstream_buildconfig) and conversationstarttime < (select endTime   from stg.episodeeventstream_buildconfig)
and queuename = 'INBOUND_SALES_MOTOR'


# In[ ]:

-- from XX - Episode Reconciliation - Gaps.html, cell 107 (note or select)
select  OriginatingDirection , 
        case when ANI like '%anonymous%' then 'anonymous' else 'normal' end, 
        count(*) 
from    stg.MarieJulyGenesysReconciliation x 
group by OriginatingDirection , case when ANI like '%anonymous%' then 'anonymous' else 'normal' end  
ORder by 1
