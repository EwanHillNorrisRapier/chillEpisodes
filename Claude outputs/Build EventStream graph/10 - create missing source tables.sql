/*
    10 - create missing source tables.sql

    Surfaces every source the 38 graph nodes read but do not create, from the ChillLH
    lakehouse into this warehouse. 36 objects, carrying 41 names.

    Prerequisite: add the lakehouse to this warehouse first, through "+ Warehouses" in the
    query editor Explorer. Without it the three-part names below will not resolve.

    NOTHING HERE DROPS ANYTHING

    Every create is guarded with IF OBJECT_ID(...) IS NULL, so an object that already
    exists is left alone and the script does nothing at all in a database where these
    names belong to something else. Run it anywhere and the worst case is no change.
    That also means it will not refresh a snapshot you already took. Section 5 holds the
    drop statements for that, commented out, so a rebuild has to be deliberate.

    The creates run through sp_executesql. A guarded CTAS cannot be written as plain
    control flow, since CREATE TABLE AS SELECT has to start its own batch.

    THE FOUR OBJECTS THE NODES CREATE THEMSELVES ARE NOT HERE

        lkp.EventSource            node 7010
        ods.EventStream            node 7020
        ods.EpisodeEventStream     node 7030
        ods.EventStreamSummary     node 7380

    SPELLING

    Everything in ChillLH is lower case, so every source reference below is lower case. The
    warehouse-side names keep the spellings the nodes use, which are not always the same.
    5 objects are spelled two ways by the notebook, so each is copied once under the
    mixed-case spelling with a view under the lower-case spelling pointing at it. All
    41 names then resolve against 36 copies of the data.

    If the lakehouse stores one of these under a different casing and this warehouse is
    case-sensitive, that CTAS will fail to resolve. Flip the spelling in the FROM clause
    if so. The target name is independent of the source name, so leave the CREATE alone.

    These are snapshots, not links. The data is as of the moment you run it.
*/

-- ==============================================================================================
--  0.  WHERE AM I
-- ==============================================================================================

SELECT DB_NAME() AS RunningIn;
GO

-- ==============================================================================================
--  1.  SCHEMAS
--      Guarded, so this is a no-op for any that already exist.
-- ==============================================================================================

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'dlk')
    EXEC sp_executesql N'CREATE SCHEMA dlk';
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'edw')
    EXEC sp_executesql N'CREATE SCHEMA edw';
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'ods')
    EXEC sp_executesql N'CREATE SCHEMA ods';
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'stg')
    EXEC sp_executesql N'CREATE SCHEMA stg';
GO

-- ==============================================================================================
--  2.  THE TABLES, 36 OF THEM
-- ==============================================================================================

-- ==============================================================================================
--  schema dlk, 22 object(s)
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
--  dlk.AppliedRenewals_FailedLoginEvent
--  from  [ChillLH].[dlk].[appliedrenewals_failedloginevent]
--  read by node(s) 7250
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[AppliedRenewals_FailedLoginEvent]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[AppliedRenewals_FailedLoginEvent]
AS
SELECT  *
FROM    [ChillLH].[dlk].[appliedrenewals_failedloginevent];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.appliedrenewals_paymentfailedevent
--  from  [ChillLH].[dlk].[appliedrenewals_paymentfailedevent]
--  read by node(s) 7220
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[appliedrenewals_paymentfailedevent]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[appliedrenewals_paymentfailedevent]
AS
SELECT  *
FROM    [ChillLH].[dlk].[appliedrenewals_paymentfailedevent];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.appliedrenewals_paymentsuccess
--  from  [ChillLH].[dlk].[appliedrenewals_paymentsuccess]
--  read by node(s) 7220
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[appliedrenewals_paymentsuccess]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[appliedrenewals_paymentsuccess]
AS
SELECT  *
FROM    [ChillLH].[dlk].[appliedrenewals_paymentsuccess];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.AppliedRenewals_SuccessfulLoginEvent
--  from  [ChillLH].[dlk].[appliedrenewals_successfulloginevent]
--  read by node(s) 7250
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[AppliedRenewals_SuccessfulLoginEvent]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[AppliedRenewals_SuccessfulLoginEvent]
AS
SELECT  *
FROM    [ChillLH].[dlk].[appliedrenewals_successfulloginevent];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.EXT_Home_QS_ClaimDetails
--  from  [ChillLH].[dlk].[ext_home_qs_claimdetails]
--  read by node(s) 7230
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[EXT_Home_QS_ClaimDetails]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[EXT_Home_QS_ClaimDetails]
AS
SELECT  *
FROM    [ChillLH].[dlk].[ext_home_qs_claimdetails];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.EXT_Home_QS_PolicyDetails
--  from  [ChillLH].[dlk].[ext_home_qs_policydetails]
--  read by node(s) 7190
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[EXT_Home_QS_PolicyDetails]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[EXT_Home_QS_PolicyDetails]
AS
SELECT  *
FROM    [ChillLH].[dlk].[ext_home_qs_policydetails];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.EXT_Home_QS_QuoteDetails
--  from  [ChillLH].[dlk].[ext_home_qs_quotedetails]
--  read by node(s) 7190
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[EXT_Home_QS_QuoteDetails]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[EXT_Home_QS_QuoteDetails]
AS
SELECT  *
FROM    [ChillLH].[dlk].[ext_home_qs_quotedetails];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.ext_quotationstorage_policydetails
--  from  [ChillLH].[dlk].[ext_quotationstorage_policydetails]
--  read by node(s) 7080
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[ext_quotationstorage_policydetails]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[ext_quotationstorage_policydetails]
AS
SELECT  *
FROM    [ChillLH].[dlk].[ext_quotationstorage_policydetails];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.ext_travel_policy
--  from  [ChillLH].[dlk].[ext_travel_policy]
--  read by node(s) 7330
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[ext_travel_policy]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[ext_travel_policy]
AS
SELECT  *
FROM    [ChillLH].[dlk].[ext_travel_policy];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.EXT_Travel_Policy_Trans
--  from  [ChillLH].[dlk].[ext_travel_policy_trans]
--  read by node(s) 7340, 7350
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[EXT_Travel_Policy_Trans]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[EXT_Travel_Policy_Trans]
AS
SELECT  *
FROM    [ChillLH].[dlk].[ext_travel_policy_trans];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.EXT_Travel_Quotes
--  from  [ChillLH].[dlk].[ext_travel_quotes]
--  read by node(s) 7320, 7330
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[EXT_Travel_Quotes]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[EXT_Travel_Quotes]
AS
SELECT  *
FROM    [ChillLH].[dlk].[ext_travel_quotes];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.EXT_Travel_Quotes_AllQuotesFile
--  from  [ChillLH].[dlk].[ext_travel_quotes_allquotesfile]
--  read by node(s) 7320, 7330
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[EXT_Travel_Quotes_AllQuotesFile]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[EXT_Travel_Quotes_AllQuotesFile]
AS
SELECT  *
FROM    [ChillLH].[dlk].[ext_travel_quotes_allquotesfile];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.hfq_paymentresponse_response
--  from  [ChillLH].[dlk].[hfq_paymentresponse_response]
--  read by node(s) 7290
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[hfq_paymentresponse_response]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[hfq_paymentresponse_response]
AS
SELECT  *
FROM    [ChillLH].[dlk].[hfq_paymentresponse_response];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.HFQ_QuoteDetails
--  from  [ChillLH].[dlk].[hfq_quotedetails]
--  read by node(s) 7310   (you have already created this one)
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[HFQ_QuoteDetails]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[HFQ_QuoteDetails]
AS
SELECT  *
FROM    [ChillLH].[dlk].[hfq_quotedetails];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.HFQ_QuoteDetails_snapshot_v2
--  from  [ChillLH].[dlk].[hfq_quotedetails_snapshot_v2]
--  read by node(s) 7310
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[HFQ_QuoteDetails_snapshot_v2]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[HFQ_QuoteDetails_snapshot_v2]
AS
SELECT  *
FROM    [ChillLH].[dlk].[hfq_quotedetails_snapshot_v2];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.hfq_sales
--  from  [ChillLH].[dlk].[hfq_sales]
--  read by node(s) 7290
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[hfq_sales]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[hfq_sales]
AS
SELECT  *
FROM    [ChillLH].[dlk].[hfq_sales];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.mfq_quotequery
--  from  [ChillLH].[dlk].[mfq_quotequery]
--  read by node(s) 7070, 7140
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[mfq_quotequery]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[mfq_quotequery]
AS
SELECT  *
FROM    [ChillLH].[dlk].[mfq_quotequery];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.MyChillWorkflow_DocumentStatus
--  from  [ChillLH].[dlk].[mychillworkflow_documentstatus]
--  read by node(s) 7210
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[MyChillWorkflow_DocumentStatus]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[MyChillWorkflow_DocumentStatus]
AS
SELECT  *
FROM    [ChillLH].[dlk].[mychillworkflow_documentstatus];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.RBSDATA2_MTA_History
--  from  [ChillLH].[dlk].[rbsdata2_mta_history]
--  read by node(s) 7170
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[RBSDATA2_MTA_History]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[RBSDATA2_MTA_History]
AS
SELECT  *
FROM    [ChillLH].[dlk].[rbsdata2_mta_history];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.RBSDATA2_NewArchive
--  from  [ChillLH].[dlk].[rbsdata2_newarchive]
--  read by node(s) 7160
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[RBSDATA2_NewArchive]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[RBSDATA2_NewArchive]
AS
SELECT  *
FROM    [ChillLH].[dlk].[rbsdata2_newarchive];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.vanpaymentjourney
--  from  [ChillLH].[dlk].[vanpaymentjourney]
--  read by node(s) 7370
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[vanpaymentjourney]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[vanpaymentjourney]
AS
SELECT  *
FROM    [ChillLH].[dlk].[vanpaymentjourney];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.vanquotejourney
--  from  [ChillLH].[dlk].[vanquotejourney]
--  read by node(s) 7360
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[vanquotejourney]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [dlk].[vanquotejourney]
AS
SELECT  *
FROM    [ChillLH].[dlk].[vanquotejourney];
';
GO

-- ==============================================================================================
--  schema edw, 3 object(s)
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
--  edw.tbl_fact_ga_clicks_GA4
--  from  [ChillLH].[edw].[tbl_fact_ga_clicks_ga4]
--  read by node(s) 7050
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[edw].[tbl_fact_ga_clicks_GA4]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [edw].[tbl_fact_ga_clicks_GA4]
AS
SELECT  *
FROM    [ChillLH].[edw].[tbl_fact_ga_clicks_ga4];
';
GO

-- ----------------------------------------------------------------------------------------------
--  edw.tbl_fact_policy_sales
--  from  [ChillLH].[edw].[tbl_fact_policy_sales]
--  read by node(s) 7100, 7120, 7180, 7190
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[edw].[tbl_fact_policy_sales]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [edw].[tbl_fact_policy_sales]
AS
SELECT  *
FROM    [ChillLH].[edw].[tbl_fact_policy_sales];
';
GO

-- ----------------------------------------------------------------------------------------------
--  edw.tbl_ref_policy
--  from  [ChillLH].[edw].[tbl_ref_policy]
--  read by node(s) 7060, 7180
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[edw].[tbl_ref_policy]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [edw].[tbl_ref_policy]
AS
SELECT  *
FROM    [ChillLH].[edw].[tbl_ref_policy];
';
GO

-- ==============================================================================================
--  schema ods, 7 object(s)
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
--  ods.CustomerCallEvents
--  from  [ChillLH].[ods].[customercallevents]
--  read by node(s) 7200
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[ods].[CustomerCallEvents]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [ods].[CustomerCallEvents]
AS
SELECT  *
FROM    [ChillLH].[ods].[customercallevents];
';
GO

-- ----------------------------------------------------------------------------------------------
--  ods.MFQQuoteToPolicy
--  from  [ChillLH].[ods].[mfqquotetopolicy]
--  read by node(s) 7110
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[ods].[MFQQuoteToPolicy]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [ods].[MFQQuoteToPolicy]
AS
SELECT  *
FROM    [ChillLH].[ods].[mfqquotetopolicy];
';
GO

-- ----------------------------------------------------------------------------------------------
--  ods.MfqScvLink
--  from  [ChillLH].[ods].[mfqscvlink]
--  read by node(s) 7090, 7110, 7140, 7150
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[ods].[MfqScvLink]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [ods].[MfqScvLink]
AS
SELECT  *
FROM    [ChillLH].[ods].[mfqscvlink];
';
GO

-- ----------------------------------------------------------------------------------------------
--  ods.motorcustomerpolicyquotelinks
--  from  [ChillLH].[ods].[motorcustomerpolicyquotelinks]
--  read by node(s) 7070, 7100, 7110, 7120, 7140, 7150
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[ods].[motorcustomerpolicyquotelinks]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [ods].[motorcustomerpolicyquotelinks]
AS
SELECT  *
FROM    [ChillLH].[ods].[motorcustomerpolicyquotelinks];
';
GO

-- ----------------------------------------------------------------------------------------------
--  ods.MotorCustomerPolicyQuoteLinksdeduped
--  from  [ChillLH].[ods].[motorcustomerpolicyquotelinksdeduped]
--  read by node(s) 7080
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[ods].[MotorCustomerPolicyQuoteLinksdeduped]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [ods].[MotorCustomerPolicyQuoteLinksdeduped]
AS
SELECT  *
FROM    [ChillLH].[ods].[motorcustomerpolicyquotelinksdeduped];
';
GO

-- ----------------------------------------------------------------------------------------------
--  ods.Policy
--  from  [ChillLH].[ods].[policy]
--  read by node(s) 7160, 7170, 7210
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[ods].[Policy]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [ods].[Policy]
AS
SELECT  *
FROM    [ChillLH].[ods].[policy];
';
GO

-- ----------------------------------------------------------------------------------------------
--  ods.RelayDocumentEvents
--  from  [ChillLH].[ods].[relaydocumentevents]
--  read by node(s) 7060
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[ods].[RelayDocumentEvents]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [ods].[RelayDocumentEvents]
AS
SELECT  *
FROM    [ChillLH].[ods].[relaydocumentevents];
';
GO

-- ==============================================================================================
--  schema stg, 4 object(s)
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
--  stg.MFQ_Quote_Payments
--  from  [ChillLH].[stg].[mfq_quote_payments]
--  read by node(s) 7090
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[stg].[MFQ_Quote_Payments]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [stg].[MFQ_Quote_Payments]
AS
SELECT  *
FROM    [ChillLH].[stg].[mfq_quote_payments];
';
GO

-- ----------------------------------------------------------------------------------------------
--  stg.MFQ_Steps_Summary
--  from  [ChillLH].[stg].[mfq_steps_summary]
--  read by node(s) 7150
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[stg].[MFQ_Steps_Summary]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [stg].[MFQ_Steps_Summary]
AS
SELECT  *
FROM    [ChillLH].[stg].[mfq_steps_summary];
';
GO

-- ----------------------------------------------------------------------------------------------
--  stg.MFQCallEvents
--  from  [ChillLH].[stg].[mfqcallevents]
--  read by node(s) 7040
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[stg].[MFQCallEvents]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [stg].[MFQCallEvents]
AS
SELECT  *
FROM    [ChillLH].[stg].[mfqcallevents];
';
GO

-- ----------------------------------------------------------------------------------------------
--  stg.MotorClaims
--  from  [ChillLH].[stg].[motorclaims]
--  read by node(s) 7240
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[stg].[MotorClaims]') IS NULL
    EXEC sp_executesql N'
CREATE TABLE [stg].[MotorClaims]
AS
SELECT  *
FROM    [ChillLH].[stg].[motorclaims];
';
GO

-- ==============================================================================================
--  3.  THE SECOND SPELLING, 5 VIEW(S)
--      A view, so there is one copy of the data and the two names cannot disagree.
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
--  dlk.ext_travel_policy_trans  ->  dlk.EXT_Travel_Policy_Trans
--  read by node(s) 7330
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[ext_travel_policy_trans]') IS NULL
    EXEC sp_executesql N'
CREATE VIEW [dlk].[ext_travel_policy_trans]
AS
SELECT  *
FROM    [dlk].[EXT_Travel_Policy_Trans];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.hfq_quotedetails  ->  dlk.HFQ_QuoteDetails
--  read by node(s) 7260, 7270, 7280
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[hfq_quotedetails]') IS NULL
    EXEC sp_executesql N'
CREATE VIEW [dlk].[hfq_quotedetails]
AS
SELECT  *
FROM    [dlk].[HFQ_QuoteDetails];
';
GO

-- ----------------------------------------------------------------------------------------------
--  dlk.hfq_quotedetails_snapshot_v2  ->  dlk.HFQ_QuoteDetails_snapshot_v2
--  read by node(s) 7260, 7270, 7280
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[dlk].[hfq_quotedetails_snapshot_v2]') IS NULL
    EXEC sp_executesql N'
CREATE VIEW [dlk].[hfq_quotedetails_snapshot_v2]
AS
SELECT  *
FROM    [dlk].[HFQ_QuoteDetails_snapshot_v2];
';
GO

-- ----------------------------------------------------------------------------------------------
--  ods.motorcustomerpolicyquotelinksdeduped  ->  ods.MotorCustomerPolicyQuoteLinksdeduped
--  read by node(s) 7130
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[ods].[motorcustomerpolicyquotelinksdeduped]') IS NULL
    EXEC sp_executesql N'
CREATE VIEW [ods].[motorcustomerpolicyquotelinksdeduped]
AS
SELECT  *
FROM    [ods].[MotorCustomerPolicyQuoteLinksdeduped];
';
GO

-- ----------------------------------------------------------------------------------------------
--  ods.policy  ->  ods.Policy
--  read by node(s) 7220, 7300
-- ----------------------------------------------------------------------------------------------
IF OBJECT_ID('[ods].[policy]') IS NULL
    EXEC sp_executesql N'
CREATE VIEW [ods].[policy]
AS
SELECT  *
FROM    [ods].[Policy];
';
GO

-- ==============================================================================================
--  4.  CHECK
-- ==============================================================================================

--  All 41 names should come back, 36 tables and 5 views.

SELECT  TABLE_SCHEMA,
        TABLE_NAME,
        TABLE_TYPE
FROM    INFORMATION_SCHEMA.TABLES
WHERE   TABLE_SCHEMA + '.' + TABLE_NAME IN (
            'dlk.AppliedRenewals_FailedLoginEvent',
            'dlk.appliedrenewals_paymentfailedevent',
            'dlk.appliedrenewals_paymentsuccess',
            'dlk.AppliedRenewals_SuccessfulLoginEvent',
            'dlk.EXT_Home_QS_ClaimDetails',
            'dlk.EXT_Home_QS_PolicyDetails',
            'dlk.EXT_Home_QS_QuoteDetails',
            'dlk.ext_quotationstorage_policydetails',
            'dlk.ext_travel_policy',
            'dlk.EXT_Travel_Policy_Trans',
            'dlk.ext_travel_policy_trans',
            'dlk.EXT_Travel_Quotes',
            'dlk.EXT_Travel_Quotes_AllQuotesFile',
            'dlk.hfq_paymentresponse_response',
            'dlk.HFQ_QuoteDetails',
            'dlk.hfq_quotedetails',
            'dlk.HFQ_QuoteDetails_snapshot_v2',
            'dlk.hfq_quotedetails_snapshot_v2',
            'dlk.hfq_sales',
            'dlk.mfq_quotequery',
            'dlk.MyChillWorkflow_DocumentStatus',
            'dlk.RBSDATA2_MTA_History',
            'dlk.RBSDATA2_NewArchive',
            'dlk.vanpaymentjourney',
            'dlk.vanquotejourney',
            'edw.tbl_fact_ga_clicks_GA4',
            'edw.tbl_fact_policy_sales',
            'edw.tbl_ref_policy',
            'ods.CustomerCallEvents',
            'ods.MFQQuoteToPolicy',
            'ods.MfqScvLink',
            'ods.motorcustomerpolicyquotelinks',
            'ods.MotorCustomerPolicyQuoteLinksdeduped',
            'ods.motorcustomerpolicyquotelinksdeduped',
            'ods.Policy',
            'ods.policy',
            'ods.RelayDocumentEvents',
            'stg.MFQ_Quote_Payments',
            'stg.MFQ_Steps_Summary',
            'stg.MFQCallEvents',
            'stg.MotorClaims'
        )
ORDER BY TABLE_SCHEMA, TABLE_NAME;
--  expect 41 rows: 36 BASE TABLE, 5 VIEW
GO

--  Row counts against the lakehouse. This reads every table twice, so on the larger
--  ones it is slow. Run it when you want the assurance, not as a matter of course.

/*
SELECT  'dlk.AppliedRenewals_FailedLoginEvent' AS TableName,
        (SELECT count_big(*) FROM [dlk].[AppliedRenewals_FailedLoginEvent])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[appliedrenewals_failedloginevent])   AS LakehouseRows
UNION ALL
SELECT  'dlk.appliedrenewals_paymentfailedevent' AS TableName,
        (SELECT count_big(*) FROM [dlk].[appliedrenewals_paymentfailedevent])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[appliedrenewals_paymentfailedevent])   AS LakehouseRows
UNION ALL
SELECT  'dlk.appliedrenewals_paymentsuccess' AS TableName,
        (SELECT count_big(*) FROM [dlk].[appliedrenewals_paymentsuccess])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[appliedrenewals_paymentsuccess])   AS LakehouseRows
UNION ALL
SELECT  'dlk.AppliedRenewals_SuccessfulLoginEvent' AS TableName,
        (SELECT count_big(*) FROM [dlk].[AppliedRenewals_SuccessfulLoginEvent])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[appliedrenewals_successfulloginevent])   AS LakehouseRows
UNION ALL
SELECT  'dlk.EXT_Home_QS_ClaimDetails' AS TableName,
        (SELECT count_big(*) FROM [dlk].[EXT_Home_QS_ClaimDetails])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[ext_home_qs_claimdetails])   AS LakehouseRows
UNION ALL
SELECT  'dlk.EXT_Home_QS_PolicyDetails' AS TableName,
        (SELECT count_big(*) FROM [dlk].[EXT_Home_QS_PolicyDetails])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[ext_home_qs_policydetails])   AS LakehouseRows
UNION ALL
SELECT  'dlk.EXT_Home_QS_QuoteDetails' AS TableName,
        (SELECT count_big(*) FROM [dlk].[EXT_Home_QS_QuoteDetails])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[ext_home_qs_quotedetails])   AS LakehouseRows
UNION ALL
SELECT  'dlk.ext_quotationstorage_policydetails' AS TableName,
        (SELECT count_big(*) FROM [dlk].[ext_quotationstorage_policydetails])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[ext_quotationstorage_policydetails])   AS LakehouseRows
UNION ALL
SELECT  'dlk.ext_travel_policy' AS TableName,
        (SELECT count_big(*) FROM [dlk].[ext_travel_policy])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[ext_travel_policy])   AS LakehouseRows
UNION ALL
SELECT  'dlk.EXT_Travel_Policy_Trans' AS TableName,
        (SELECT count_big(*) FROM [dlk].[EXT_Travel_Policy_Trans])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[ext_travel_policy_trans])   AS LakehouseRows
UNION ALL
SELECT  'dlk.EXT_Travel_Quotes' AS TableName,
        (SELECT count_big(*) FROM [dlk].[EXT_Travel_Quotes])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[ext_travel_quotes])   AS LakehouseRows
UNION ALL
SELECT  'dlk.EXT_Travel_Quotes_AllQuotesFile' AS TableName,
        (SELECT count_big(*) FROM [dlk].[EXT_Travel_Quotes_AllQuotesFile])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[ext_travel_quotes_allquotesfile])   AS LakehouseRows
UNION ALL
SELECT  'dlk.hfq_paymentresponse_response' AS TableName,
        (SELECT count_big(*) FROM [dlk].[hfq_paymentresponse_response])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[hfq_paymentresponse_response])   AS LakehouseRows
UNION ALL
SELECT  'dlk.HFQ_QuoteDetails' AS TableName,
        (SELECT count_big(*) FROM [dlk].[HFQ_QuoteDetails])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[hfq_quotedetails])   AS LakehouseRows
UNION ALL
SELECT  'dlk.HFQ_QuoteDetails_snapshot_v2' AS TableName,
        (SELECT count_big(*) FROM [dlk].[HFQ_QuoteDetails_snapshot_v2])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[hfq_quotedetails_snapshot_v2])   AS LakehouseRows
UNION ALL
SELECT  'dlk.hfq_sales' AS TableName,
        (SELECT count_big(*) FROM [dlk].[hfq_sales])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[hfq_sales])   AS LakehouseRows
UNION ALL
SELECT  'dlk.mfq_quotequery' AS TableName,
        (SELECT count_big(*) FROM [dlk].[mfq_quotequery])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[mfq_quotequery])   AS LakehouseRows
UNION ALL
SELECT  'dlk.MyChillWorkflow_DocumentStatus' AS TableName,
        (SELECT count_big(*) FROM [dlk].[MyChillWorkflow_DocumentStatus])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[mychillworkflow_documentstatus])   AS LakehouseRows
UNION ALL
SELECT  'dlk.RBSDATA2_MTA_History' AS TableName,
        (SELECT count_big(*) FROM [dlk].[RBSDATA2_MTA_History])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[rbsdata2_mta_history])   AS LakehouseRows
UNION ALL
SELECT  'dlk.RBSDATA2_NewArchive' AS TableName,
        (SELECT count_big(*) FROM [dlk].[RBSDATA2_NewArchive])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[rbsdata2_newarchive])   AS LakehouseRows
UNION ALL
SELECT  'dlk.vanpaymentjourney' AS TableName,
        (SELECT count_big(*) FROM [dlk].[vanpaymentjourney])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[vanpaymentjourney])   AS LakehouseRows
UNION ALL
SELECT  'dlk.vanquotejourney' AS TableName,
        (SELECT count_big(*) FROM [dlk].[vanquotejourney])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[dlk].[vanquotejourney])   AS LakehouseRows
UNION ALL
SELECT  'edw.tbl_fact_ga_clicks_GA4' AS TableName,
        (SELECT count_big(*) FROM [edw].[tbl_fact_ga_clicks_GA4])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[edw].[tbl_fact_ga_clicks_ga4])   AS LakehouseRows
UNION ALL
SELECT  'edw.tbl_fact_policy_sales' AS TableName,
        (SELECT count_big(*) FROM [edw].[tbl_fact_policy_sales])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[edw].[tbl_fact_policy_sales])   AS LakehouseRows
UNION ALL
SELECT  'edw.tbl_ref_policy' AS TableName,
        (SELECT count_big(*) FROM [edw].[tbl_ref_policy])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[edw].[tbl_ref_policy])   AS LakehouseRows
UNION ALL
SELECT  'ods.CustomerCallEvents' AS TableName,
        (SELECT count_big(*) FROM [ods].[CustomerCallEvents])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[ods].[customercallevents])   AS LakehouseRows
UNION ALL
SELECT  'ods.MFQQuoteToPolicy' AS TableName,
        (SELECT count_big(*) FROM [ods].[MFQQuoteToPolicy])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[ods].[mfqquotetopolicy])   AS LakehouseRows
UNION ALL
SELECT  'ods.MfqScvLink' AS TableName,
        (SELECT count_big(*) FROM [ods].[MfqScvLink])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[ods].[mfqscvlink])   AS LakehouseRows
UNION ALL
SELECT  'ods.motorcustomerpolicyquotelinks' AS TableName,
        (SELECT count_big(*) FROM [ods].[motorcustomerpolicyquotelinks])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[ods].[motorcustomerpolicyquotelinks])   AS LakehouseRows
UNION ALL
SELECT  'ods.MotorCustomerPolicyQuoteLinksdeduped' AS TableName,
        (SELECT count_big(*) FROM [ods].[MotorCustomerPolicyQuoteLinksdeduped])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[ods].[motorcustomerpolicyquotelinksdeduped])   AS LakehouseRows
UNION ALL
SELECT  'ods.Policy' AS TableName,
        (SELECT count_big(*) FROM [ods].[Policy])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[ods].[policy])   AS LakehouseRows
UNION ALL
SELECT  'ods.RelayDocumentEvents' AS TableName,
        (SELECT count_big(*) FROM [ods].[RelayDocumentEvents])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[ods].[relaydocumentevents])   AS LakehouseRows
UNION ALL
SELECT  'stg.MFQ_Quote_Payments' AS TableName,
        (SELECT count_big(*) FROM [stg].[MFQ_Quote_Payments])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[stg].[mfq_quote_payments])   AS LakehouseRows
UNION ALL
SELECT  'stg.MFQ_Steps_Summary' AS TableName,
        (SELECT count_big(*) FROM [stg].[MFQ_Steps_Summary])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[stg].[mfq_steps_summary])   AS LakehouseRows
UNION ALL
SELECT  'stg.MFQCallEvents' AS TableName,
        (SELECT count_big(*) FROM [stg].[MFQCallEvents])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[stg].[mfqcallevents])   AS LakehouseRows
UNION ALL
SELECT  'stg.MotorClaims' AS TableName,
        (SELECT count_big(*) FROM [stg].[MotorClaims])          AS WarehouseRows,
        (SELECT count_big(*) FROM [ChillLH].[stg].[motorclaims])   AS LakehouseRows;
*/
GO

-- ==============================================================================================
--  5.  REBUILD, IF YOU WANT A FRESH SNAPSHOT
--      Deliberately commented out. Uncomment what you want, run it, then run sections
--      2 and 3 again.
-- ==============================================================================================

-- DROP TABLE IF EXISTS [dlk].[AppliedRenewals_FailedLoginEvent];
-- DROP TABLE IF EXISTS [dlk].[appliedrenewals_paymentfailedevent];
-- DROP TABLE IF EXISTS [dlk].[appliedrenewals_paymentsuccess];
-- DROP TABLE IF EXISTS [dlk].[AppliedRenewals_SuccessfulLoginEvent];
-- DROP TABLE IF EXISTS [dlk].[EXT_Home_QS_ClaimDetails];
-- DROP TABLE IF EXISTS [dlk].[EXT_Home_QS_PolicyDetails];
-- DROP TABLE IF EXISTS [dlk].[EXT_Home_QS_QuoteDetails];
-- DROP TABLE IF EXISTS [dlk].[ext_quotationstorage_policydetails];
-- DROP TABLE IF EXISTS [dlk].[ext_travel_policy];
-- DROP VIEW  IF EXISTS [dlk].[ext_travel_policy_trans];
-- DROP TABLE IF EXISTS [dlk].[EXT_Travel_Policy_Trans];
-- DROP TABLE IF EXISTS [dlk].[EXT_Travel_Quotes];
-- DROP TABLE IF EXISTS [dlk].[EXT_Travel_Quotes_AllQuotesFile];
-- DROP TABLE IF EXISTS [dlk].[hfq_paymentresponse_response];
-- DROP VIEW  IF EXISTS [dlk].[hfq_quotedetails];
-- DROP TABLE IF EXISTS [dlk].[HFQ_QuoteDetails];
-- DROP VIEW  IF EXISTS [dlk].[hfq_quotedetails_snapshot_v2];
-- DROP TABLE IF EXISTS [dlk].[HFQ_QuoteDetails_snapshot_v2];
-- DROP TABLE IF EXISTS [dlk].[hfq_sales];
-- DROP TABLE IF EXISTS [dlk].[mfq_quotequery];
-- DROP TABLE IF EXISTS [dlk].[MyChillWorkflow_DocumentStatus];
-- DROP TABLE IF EXISTS [dlk].[RBSDATA2_MTA_History];
-- DROP TABLE IF EXISTS [dlk].[RBSDATA2_NewArchive];
-- DROP TABLE IF EXISTS [dlk].[vanpaymentjourney];
-- DROP TABLE IF EXISTS [dlk].[vanquotejourney];
-- DROP TABLE IF EXISTS [edw].[tbl_fact_ga_clicks_GA4];
-- DROP TABLE IF EXISTS [edw].[tbl_fact_policy_sales];
-- DROP TABLE IF EXISTS [edw].[tbl_ref_policy];
-- DROP TABLE IF EXISTS [ods].[CustomerCallEvents];
-- DROP TABLE IF EXISTS [ods].[MFQQuoteToPolicy];
-- DROP TABLE IF EXISTS [ods].[MfqScvLink];
-- DROP TABLE IF EXISTS [ods].[motorcustomerpolicyquotelinks];
-- DROP VIEW  IF EXISTS [ods].[motorcustomerpolicyquotelinksdeduped];
-- DROP TABLE IF EXISTS [ods].[MotorCustomerPolicyQuoteLinksdeduped];
-- DROP VIEW  IF EXISTS [ods].[policy];
-- DROP TABLE IF EXISTS [ods].[Policy];
-- DROP TABLE IF EXISTS [ods].[RelayDocumentEvents];
-- DROP TABLE IF EXISTS [stg].[MFQ_Quote_Payments];
-- DROP TABLE IF EXISTS [stg].[MFQ_Steps_Summary];
-- DROP TABLE IF EXISTS [stg].[MFQCallEvents];
-- DROP TABLE IF EXISTS [stg].[MotorClaims];
-- GO
