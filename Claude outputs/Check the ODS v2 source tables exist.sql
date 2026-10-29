/*
    Check the ODS v2 source tables exist.sql

    Lists the 71 source tables the ODS v2 build notebooks (ODS_v2_10_Policy ... ODS_v2_40_Reference) read, and
    whether each one exists, so a new environment can be checked before the first ODS run. ODS_Build_v2 needs the same
    tables except dlk.cda_loanse (it has no loan section).

    Where to run it: the SQL analytics endpoint of the lakehouse the notebooks run against (ChillLH in Dev_CGP), as
    T-SQL. Read only. It only sees schemas in that lakehouse: a source that lives in another lakehouse shows as MISSING.

    Set @source_set to the source_set the ODS run will use (blank in the notebooks = 'frozen'). The schema each slot
    means, from ODS_v2_00_Setup:
        slot        frozen              prod
        dlk         dlk                 prod_dlk            (53 tables)
        edw         edw                 prod_edw            (13)
        ods_carry   ods                 ods                 (3)
        pii         pii                 prod_pii            (2)
    The output schemas (ods_v2, stg) are not checked: ODS_v2_00_Setup creates them if they are missing.

    One row per table, missing first. Every row 'present' = the sources are all there.

    Generated on 2026-10-28 from the notebooks in main_v2. If the ODS notebooks change, regenerate it
    rather than editing it by hand.
*/
declare @source_set varchar(10) = 'frozen';     -- 'frozen' or 'prod'

if @source_set not in ('frozen', 'prod')
    throw 50000, '@source_set must be frozen or prod', 1;

with slots as (
    select * from (values
        ('dlk', 'dlk', 'prod_dlk'),
        ('edw', 'edw', 'prod_edw'),
        ('ods_carry', 'ods', 'ods'),
        ('pii', 'pii', 'prod_pii')
    ) s (Slot, FrozenSchema, ProdSchema)
),
needed as (
    select * from (values
        ('dlk', 'appliedrenewals_failedloginevent', '10_Policy'),
        ('dlk', 'appliedrenewals_paymentfailedevent', '10_Policy'),
        ('dlk', 'appliedrenewals_paymentsuccess', '10_Policy'),
        ('dlk', 'appliedrenewals_successfulloginevent', '10_Policy'),
        ('dlk', 'cda_loanse', '11_Policy_Loan'),
        ('dlk', 'cda_messages', '30_Interaction'),
        ('dlk', 'ext_home_qs_claimdetails', '10_Policy'),
        ('dlk', 'ext_home_qs_policydetails', '10_Policy, 20_Quote, 22_Quote_Home'),
        ('dlk', 'ext_home_qs_quotedetails', '20_Quote, 22_Quote_Home'),
        ('dlk', 'ext_home_qs_riskdetails', '22_Quote_Home'),
        ('dlk', 'ext_home_qs_specifieditemsdetails', '22_Quote_Home'),
        ('dlk', 'ext_quotationstorage_driver', '21_Quote_Motor'),
        ('dlk', 'ext_quotationstorage_policydetails', '20_Quote'),
        ('dlk', 'ext_quotationstorage_riskdetails', '20_Quote, 21_Quote_Motor'),
        ('dlk', 'ext_quotationstorage_schemeresult', '20_Quote'),
        ('dlk', 'ext_travel_policy', '10_Policy'),
        ('dlk', 'ext_travel_policy_trans', '10_Policy'),
        ('dlk', 'ext_travel_quotes', '20_Quote, 23_Quote_Travel'),
        ('dlk', 'ext_xtremepushresults', '30_Interaction'),
        ('dlk', 'ext_xtremepushresults_policy', '30_Interaction'),
        ('dlk', 'ga4_page_views_daily', '30_Interaction'),
        ('dlk', 'genesys_session_summary', '30_Interaction'),
        ('dlk', 'hfq_paymentrequest_request', '22_Quote_Home'),
        ('dlk', 'hfq_paymentresponse_response', '22_Quote_Home'),
        ('dlk', 'hfq_quotedetails', '20_Quote, 22_Quote_Home'),
        ('dlk', 'hfq_response_quotes', '20_Quote, 22_Quote_Home'),
        ('dlk', 'hfq_sales', '20_Quote, 22_Quote_Home'),
        ('dlk', 'merc_actiontracks', '30_Interaction'),
        ('dlk', 'merc_apps', '30_Interaction'),
        ('dlk', 'merc_servicecallstracks', '30_Interaction'),
        ('dlk', 'mfq_clientsteps', '21_Quote_Motor'),
        ('dlk', 'mfq_mon_session', '21_Quote_Motor'),
        ('dlk', 'mfq_payments', '21_Quote_Motor'),
        ('dlk', 'mfq_quotedrivers', '21_Quote_Motor'),
        ('dlk', 'mfq_quotequery', '20_Quote'),
        ('dlk', 'mfq_quoteresponses', '21_Quote_Motor'),
        ('dlk', 'mfq_quotesummary', '21_Quote_Motor'),
        ('dlk', 'mychill_newuploaddocumentevents', '10_Policy'),
        ('dlk', 'mychillworkflow_documentstatus', '10_Policy'),
        ('dlk', 'rbsdata2_motor_clm', '10_Policy'),
        ('dlk', 'rbsdata2_mta_history', '10_Policy'),
        ('dlk', 'rbsdata2_newarchive', '10_Policy'),
        ('dlk', 'relay_documentation_document', '10_Policy'),
        ('dlk', 'relay_documentation_policydocument', '10_Policy'),
        ('dlk', 'relay_eventmodel_documentevent', '10_Policy'),
        ('dlk', 'relay_eventmodel_event', '10_Policy'),
        ('dlk', 'relay_eventmodel_policyevent', '10_Policy'),
        ('dlk', 'relay_policy', '10_Policy'),
        ('dlk', 'relay_portfolio', '10_Policy'),
        ('dlk', 'relay_reporting_relaycodelist', '10_Policy'),
        ('dlk', 'vanpaymentjourney', '24_Quote_Van'),
        ('dlk', 'vanquotedetails', '20_Quote, 24_Quote_Van'),
        ('dlk', 'vanquotejourney', '24_Quote_Van'),
        ('edw', 'exp_mychill_chase_daily_snapshot_home', '10_Policy'),
        ('edw', 'exp_mychill_chase_daily_snapshot_motorvan', '10_Policy'),
        ('edw', 'tbl_fact_ga_clicks_ga4', '30_Interaction'),
        ('edw', 'tbl_fact_mfq', '20_Quote, 21_Quote_Motor'),
        ('edw', 'tbl_fact_policy_mtc', '10_Policy'),
        ('edw', 'tbl_fact_policy_mvt', '10_Policy'),
        ('edw', 'tbl_fact_policy_quotes', '20_Quote'),
        ('edw', 'tbl_fact_policy_renewals', '10_Policy'),
        ('edw', 'tbl_fact_policy_sales', '10_Policy'),
        ('edw', 'tbl_fact_telephony_call_detail', '30_Interaction'),
        ('edw', 'tbl_ref_calendarlookup', '40_Reference'),
        ('edw', 'tbl_ref_mapping_bar_premium_type', '10_Policy'),
        ('edw', 'tbl_ref_policy', '10_Policy'),
        ('ods_carry', 'policyhome', '10_Policy'),
        ('ods_carry', 'policymotorproposer', '10_Policy'),
        ('ods_carry', 'policymotorvehicle', '10_Policy'),
        ('pii', 'addresses_assembled', '30_Interaction'),
        ('pii', 'customer_data_assembled', '30_Interaction')
    ) n (Slot, TableName, ReadBy)
),
expected as (
    select  n.Slot,
            case when @source_set = 'prod' then s.ProdSchema else s.FrozenSchema end as SchemaName,
            n.TableName, n.ReadBy
    from    needed n
    join    slots s on s.Slot = n.Slot
)
select  case when t.TABLE_NAME is null then 'MISSING' else 'present' end   as Status,
        e.SchemaName + '.' + e.TableName                                    as SourceTable,
        e.Slot,
        e.ReadBy                                                            as ReadByNotebooks,
        t.TABLE_TYPE                                                        as FoundAs
from    expected e
left join INFORMATION_SCHEMA.TABLES t
        on  lower(t.TABLE_SCHEMA) = lower(e.SchemaName)          -- the endpoint is case sensitive; the notebooks are not
        and lower(t.TABLE_NAME)   = lower(e.TableName)
order by case when t.TABLE_NAME is null then 0 else 1 end, SourceTable;
