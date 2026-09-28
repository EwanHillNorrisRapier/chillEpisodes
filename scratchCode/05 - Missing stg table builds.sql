/*
    05 - Missing stg table builds

    The staging tables that 03 - Populate Episode Event Stream reads but never builds, recovered
    from the Fabric scratch notebooks in fabric_extract_20260923 on 23 September 2026.

    The statements are verbatim as extracted, in dependency order, so they can be reviewed against
    the originals. Three of them carry hard coded date windows, called out in the comment above
    each one, which want swapping for stg.episodeeventstream_buildconfig before they go into the
    main notebook.

    Still missing, with no build anywhere in the extract:
        stg.MFQ_Quote_Payments     feeds the stg.MotorRenewalsOnline build, A4a, A5a, A5.F1, R2.B1.F1
        stg.VM0_van_phone_numbers  feeds HM1, M1, M1.F1, M.V1 to M.V4, VM1, VM1.F1
        stg.A3_SL10_QQGUIDS        feeds A3 and A3.F1
        stg.MFQ_Quotes             feeds R2.B1.2
        stg.motorclaims            feeds R0.F2
*/


-- ----------------------------------------------------------------------------------------------
-- 1. stg.HFQ_Quotes
--    source: XX - Episode Reconciliation - Home Renewals EHN.ipynb, cell 19
--    Read by the stg.HomeRenewalsDoingHFQ build.
--    NOTE the ts_unix window is a literal 2026-06-01 to 2026-08-01. Everything else in
--    03 - Populate Episode Event Stream now reads its dates from stg.episodeeventstream_buildconfig.
--    Close cousin of stg.HA1_HFQ_Quotes, which we already build off the same snapshot but
--    which also carries a MaxRN column.
-- ----------------------------------------------------------------------------------------------

Create Or Replace Table stg.HFQ_Quotes as 
SELECT  *
FROM    (SELECT  *, 	
                CAST(from_unixtime(_ts) AS TIMESTAMP) as ts_unix,
                ROW_NUMBER() OVER(PARTITION BY QuoteCodeReference, RetrieveCount order by _ts desc) AS RN 
        FROM    dlk.HFQ_QuoteDetails_Snapshot_v2) a
where   RN =1
and     ts_unix between '2026-06-01 00:00:00.000' and '2026-08-01 00:00:00.000'
;


-- ----------------------------------------------------------------------------------------------
-- 2. stg.hfq_price_requested
--    source: XX - Episode Reconciliation - Home Acquisitions  EHN.ipynb, cell 26
--    Read by HA2.F1.
-- ----------------------------------------------------------------------------------------------

Create or Replace Table stg.hfq_price_requested as 
select  QuoteCodeReference 
from    dlk.HFQ_Response_Quotes 
Group by QuoteCodeReference
;


-- ----------------------------------------------------------------------------------------------
-- 3. stg.hfq_prices
--    source: XX - Episode Reconciliation - Home Acquisitions  EHN.ipynb, cell 27
--    Read by HR2.B1.2, HR2.B1.3.F1, HR2.B1.O1 and HR2.B1.O2.
--    Also appears in Home Renewals EHN cell 52, identical.
-- ----------------------------------------------------------------------------------------------

Create or Replace Table stg.hfq_prices as 
select  QuoteCodeReference ,  min(Quotes_TotalPayable) as QuoteBestPrice
from    dlk.HFQ_Response_Quotes 
where   Quotes_Premium <> 0 
and     Quotes_Outcome = 'PremiumReturned'
Group by QuoteCodeReference
;


-- ----------------------------------------------------------------------------------------------
-- 4. stg.HFQ_Payments
--    source: XX - Episode Reconciliation - Home Acquisitions  EHN.ipynb, cell 34
--    Read by HA4a, HA5, HA5.F1 and HR2.B1.F1.
--    Also appears in Home Renewals EHN cell 25, identical.
--    Mirrors DWH.usp_Load_fact_HFQ_Payment. Read only, no date window of its own.
-- ----------------------------------------------------------------------------------------------

Create or Replace Table stg.HFQ_Payments as 
WITH Request_Request AS
(
    SELECT *
    FROM
    (
        SELECT trim(upper(globalPayment_reference)) AS PaymentReference, trim(upper(reference)) AS QuoteReference,
               SchemeCode, TemporaryQuoteId, CacheId, amount, depositAmount,
               isFullPayment, monthlyAmount, payer_email, policyStartDate, BrokerID,
               ROW_NUMBER() OVER
                 (PARTITION BY globalPayment_reference ORDER BY globalPayment_reference DESC) AS rn
        FROM dlk.HFQ_PaymentRequest_Request
        WHERE SourceFilePath NOT LIKE '%Global%'
          AND TemporaryQuoteId IS NOT NULL AND CacheId IS NOT NULL
          AND globalPayment_reference IS NOT NULL AND reference IS NOT NULL
    ) AS source_data
    WHERE rn = 1
),
Request_Response AS
(
    SELECT *
    FROM
    (
        SELECT trim(upper(REPLACE(SUBSTRING(SourceFilePath, 26, LEN(SourceFilePath)), '.json', ''))) AS PaymentReference,
               action_time_created, action_result_code, action_type,
               ROW_NUMBER() OVER
                 (PARTITION BY REPLACE(SUBSTRING(SourceFilePath, 26, LEN(SourceFilePath)), '.json', '')
                  ORDER BY action_time_created DESC) AS rn
        FROM dlk.HFQ_PaymentRequest_Response
    ) AS source_data
    WHERE rn = 1
),
Response_Response AS
(
    SELECT *
    FROM
    (
        SELECT trim(upper(reference)) AS PaymentReference, action_result_code, action_time_created,
               type, status, amount, payment_method_result, payment_method_message,
               ROW_NUMBER() OVER (PARTITION BY reference ORDER BY action_time_created DESC) AS rn
        FROM dlk.HFQ_PaymentResponse_Response
    ) AS source_data
    WHERE rn = 1
),
Request_Failed AS
(
    SELECT *
    FROM
    (
        SELECT trim(upper(REPLACE(SUBSTRING(SourceFilePath, 24, LEN(SourceFilePath)), '.json', ''))) AS PaymentReference,
               StatusCode, ReasonPhrase, IsSuccessStatusCode,
               REPLACE(REPLACE(Headers_Value, '["', ''), '"]', '') AS FailureTimestamp,
               ROW_NUMBER() OVER
                 (PARTITION BY REPLACE(SUBSTRING(SourceFilePath, 24, LEN(SourceFilePath)), '.json', '')
                  ORDER BY Headers_Value DESC) AS rn
        FROM dlk.HFQ_PaymentRequest_Failed
    ) AS source_data
    WHERE rn = 1
)
SELECT
    req.PaymentReference AS RequestPaymentReference,
    req.QuoteReference, req.BrokerID, req.SchemeCode, req.TemporaryQuoteId, req.CacheId,
    req.amount AS RequestAmount, req.depositAmount, req.isFullPayment, req.monthlyAmount,
    req.payer_email, req.policyStartDate,
    reqRes.PaymentReference AS RequestResponsePaymentReference,
    reqRes.action_time_created AS RequestResponseTimestamp,
    reqRes.action_result_code AS RequestResponseActionResult,
    reqRes.action_type AS RequestResponseActionType,
    resRes.PaymentReference AS PaymentResponsePaymentReference,
    resRes.action_result_code AS PaymentResponseActionResultCode,
    resRes.action_time_created AS PaymentResponseTimestamp,
    resRes.type AS PaymentResponseType, resRes.status AS PaymentResponseStatus,
    resRes.amount AS PaymentResponseAmount,
    resRes.payment_method_result AS PaymentMethodResult,
    resRes.payment_method_message AS PaymentMethodMessage,
    fail.PaymentReference AS FailedRequestPaymentReference,
    fail.StatusCode AS FailedRequestStatusCode, fail.ReasonPhrase AS FailedRequestReason,
    fail.IsSuccessStatusCode AS FailedRequestIsSuccessStatusCode, fail.FailureTimestamp,

    /* Fact flags and dates, named to match DWH.tbl_fact_HFQ_Payment. */
    CASE WHEN fail.PaymentReference IS NULL THEN 0 ELSE 1 END AS PaymentRequestFailed,
    fail.FailureTimestamp AS PaymentRequestFailedTimestamp,
    CASE WHEN reqRes.PaymentReference IS NULL THEN 0 ELSE 1 END AS PaymentRequestResponse,
    reqRes.action_time_created AS PaymentRequestResponseTimestamp,
    CASE WHEN resRes.PaymentReference IS NULL THEN 0 ELSE 1 END AS PaymentResponseResponse,
    resRes.action_result_code AS PaymentResponseResponseActionResultCode,
    resRes.action_time_created AS PaymentResponseResponseTimestamp,
    CASE WHEN resRes.action_result_code IS NOT NULL THEN 1 END AS RecordVersionIsLatestFlag,
    CASE
        WHEN resRes.action_time_created IS NOT NULL THEN CAST(resRes.action_time_created AS date)
        WHEN reqRes.action_time_created IS NOT NULL THEN CAST(reqRes.action_time_created AS date)
        WHEN fail.FailureTimestamp IS NOT NULL THEN 
                            cast(concat(
                                SUBSTRING(fail.FailureTimestamp, 13, 4) , '-' ,
                                CASE SUBSTRING(fail.FailureTimestamp, 9, 3)
                                    WHEN 'Jan' THEN '01' WHEN 'Feb' THEN '02' WHEN 'Mar' THEN '03'
                                    WHEN 'Apr' THEN '04' WHEN 'May' THEN '05' WHEN 'Jun' THEN '06'
                                    WHEN 'Jul' THEN '07' WHEN 'Aug' THEN '08' WHEN 'Sep' THEN '09'
                                    WHEN 'Oct' THEN '10' WHEN 'Nov' THEN '11' WHEN 'Dec' THEN '12'
                                        END , '-' , SUBSTRING(fail.FailureTimestamp, 6, 2), ' ',
                                        Substring(fail.FailureTimestamp,18,8)) 
                                        as timestamp)
    END AS WorkDate
FROM Request_Request AS req
FULL OUTER JOIN Request_Response AS reqRes
    ON req.PaymentReference = reqRes.PaymentReference
FULL OUTER JOIN Response_Response AS resRes
    ON req.PaymentReference = resRes.PaymentReference
FULL OUTER JOIN Request_Failed AS fail
    ON req.PaymentReference = fail.PaymentReference
;


-- ----------------------------------------------------------------------------------------------
-- 5. stg.VanRenewalsJuly
--    source: XX - Episode Reconciliation - Travel and Van.ipynb, cell 37
--    Read by 19 Van renewal steps, 30 references in all, the widest gap of the set.
--    NOTE RenewalMonth is the literal 2026-07-31. The equivalent in our script would be
--    (select effectiveDate from stg.episodeeventstream_buildconfig).
--    Note also we already build stg.VanRenewals with the same column list and filter.
-- ----------------------------------------------------------------------------------------------

Create or Replace Table stg.VanRenewalsJuly as 
select  PolicyCode, TYPolicyCode, LYPolicyRenewDateAdj, LYEURGrossPremium, LYEURCommission,	LYEURFees, RenEURPremInvite,	RenEURPremAlternative, RenEURFee, PolicyOfferNum, PolicyRetNum, TYReportingSaleType,	TYReportingSaleCategory,	TYReportingSaleDate,
TYEURGrossPremium,	TYEURCommission,	TYEURFees, Channel, RenewalsPortal,	SuccessfulLoginCount,FailedLoginCount, SuccessfulPaymentCount, FailedPaymentCount, DiaryPaymentTypeTY, PolicyCodeRevisedAtOffer
from    edw.tbl_fact_policy_renewals
where   RenewalMonth = '2026-07-31' 
and     LYPolicyTypeGroup = 'Van' 
Group by PolicyCode, TYPolicyCode, LYPolicyRenewDateAdj, LYEURGrossPremium, LYEURCommission,	LYEURFees, RenEURPremInvite,	RenEURPremAlternative, RenEURFee, PolicyOfferNum, PolicyRetNum, TYReportingSaleType,	TYReportingSaleCategory,	TYReportingSaleDate,
TYEURGrossPremium,	TYEURCommission,	TYEURFees, Channel, RenewalsPortal,	SuccessfulLoginCount,FailedLoginCount, SuccessfulPaymentCount, FailedPaymentCount, DiaryPaymentTypeTY, PolicyCodeRevisedAtOffer
;


-- ----------------------------------------------------------------------------------------------
-- 6. stg.DocRequestCustomers
--    source: XX - Episode Reconciliation - Gaps.ipynb, cell 76
--    Feeds stg.DocRequestClientCodes below, so it has to run first.
--    Motor InLife cell 23 builds a table of the same name with a completely different shape,
--    projecting SCV keys. That one will NOT satisfy the join below. This is the right version.
--    NOTE the ConversationStartTime window is a literal 2026-07-01 to 2026-08-01, which is
--    startTime to endTime on the build config.
-- ----------------------------------------------------------------------------------------------

Create or Replace table stg.DocRequestCustomers as 
Select  CustomerPhoneNumber, ConversationStartTime, ConversationId
from    stg.A0_genesys_derived_data
Where   ConversationStartTime between '2026-07-01 00:00:00.000' and '2026-08-01 00:00:00.000'
and     QueueName = 'INBOUND_Documents_Out'
Group by CustomerPhoneNumber, ConversationStartTime, ConversationId
;


-- ----------------------------------------------------------------------------------------------
-- 7. stg.DocRequestClientCodes
--    source: XX - Episode Reconciliation - Gaps.ipynb, cell 77
--    Read by all 15 Doc Request steps: HD1, HD1.F1, HD2, HD3.F1, HD3.F2 and the Motor and
--    Van equivalents. 15 references in all.
-- ----------------------------------------------------------------------------------------------

Create or Replace table stg.DocRequestClientCodes as 
Select  CustomerPhoneNumber, a.RapierCustomerId, a.SourceSystemCustomerId as ClientCode, ConversationStartTime, ConversationId
from    pii.customer_data_assembled a, 
        stg.DocRequestCustomers     b
Where   a.CustomerPhone = b.CustomerPhoneNumber
and     a.SourceSystemId = 1 
and     a.SubSourceSystemId = 1 
Group by CustomerPhoneNumber, a.RapierCustomerId, a.SourceSystemCustomerId , ConversationStartTime, ConversationId
;
