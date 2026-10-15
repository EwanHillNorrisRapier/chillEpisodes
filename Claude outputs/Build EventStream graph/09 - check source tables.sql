/*
    09 - check source tables.sql

    Read only. Lists every table the 38 graph nodes read from or write to, and tells you
    which of them are not present. 45 distinct names across 38 nodes.

    Run it in the same database the harness runs in. If the sources live in a lakehouse
    rather than the warehouse, they will not appear in INFORMATION_SCHEMA here and every
    one will report as missing, which tells you the graph cannot reach them either.

    Three results come back:
        1  the missing list, which is the short answer
        2  the full picture, one row per name, with a Status of ok, case mismatch or missing
        3  the names the notebook spells more than one way

    Status values:
        ok              found, spelled exactly as the node SQL spells it
        case mismatch   found, but the catalog spells it differently. Harmless on a
                        case-insensitive database, fatal on a case-sensitive one
        missing         not found under any casing
        built by graph  created by a node of this graph, so it need not exist beforehand

    Names are compared as binary rather than with COLLATE, so the case check gives the
    same answer whatever collation the database carries.
*/

-- ==============================================================================================
--  THE LIST OF NAMES, TAKEN FROM THE NODE SQL
-- ==============================================================================================

DROP TABLE IF EXISTS #GraphSourceTables;

CREATE TABLE #GraphSourceTables
    (
        SchemaName   varchar(128),
        TableName    varchar(128),
        UsedFor      varchar(10),
        BuiltByNode  int,
        UsedByNodes  varchar(400)
    );

INSERT INTO #GraphSourceTables
    (
        SchemaName,
        TableName,
        UsedFor,
        BuiltByNode,
        UsedByNodes
    )
VALUES
    ('dlk',   'AppliedRenewals_FailedLoginEvent',              'read',        NULL,  '7250'),
    ('dlk',   'appliedrenewals_paymentfailedevent',            'read',        NULL,  '7220'),
    ('dlk',   'appliedrenewals_paymentsuccess',                'read',        NULL,  '7220'),
    ('dlk',   'AppliedRenewals_SuccessfulLoginEvent',          'read',        NULL,  '7250'),
    ('dlk',   'EXT_Home_QS_ClaimDetails',                      'read',        NULL,  '7230'),
    ('dlk',   'EXT_Home_QS_PolicyDetails',                     'read',        NULL,  '7190'),
    ('dlk',   'EXT_Home_QS_QuoteDetails',                      'read',        NULL,  '7190'),
    ('dlk',   'ext_quotationstorage_policydetails',            'read',        NULL,  '7080'),
    ('dlk',   'ext_travel_policy',                             'read',        NULL,  '7330'),
    ('dlk',   'ext_travel_policy_trans',                       'read',        NULL,  '7330'),
    ('dlk',   'EXT_Travel_Policy_Trans',                       'read',        NULL,  '7340, 7350'),
    ('dlk',   'EXT_Travel_Quotes',                             'read',        NULL,  '7320, 7330'),
    ('dlk',   'EXT_Travel_Quotes_AllQuotesFile',               'read',        NULL,  '7320, 7330'),
    ('dlk',   'hfq_paymentresponse_response',                  'read',        NULL,  '7290'),
    ('dlk',   'hfq_quotedetails',                              'read',        NULL,  '7260, 7270, 7280'),
    ('dlk',   'HFQ_QuoteDetails',                              'read',        NULL,  '7310'),
    ('dlk',   'hfq_quotedetails_snapshot_v2',                  'read',        NULL,  '7260, 7270, 7280'),
    ('dlk',   'HFQ_QuoteDetails_snapshot_v2',                  'read',        NULL,  '7310'),
    ('dlk',   'hfq_sales',                                     'read',        NULL,  '7290'),
    ('dlk',   'mfq_quotequery',                                'read',        NULL,  '7070, 7140'),
    ('dlk',   'MyChillWorkflow_DocumentStatus',                'read',        NULL,  '7210'),
    ('dlk',   'RBSDATA2_MTA_History',                          'read',        NULL,  '7170'),
    ('dlk',   'RBSDATA2_NewArchive',                           'read',        NULL,  '7160'),
    ('dlk',   'vanpaymentjourney',                             'read',        NULL,  '7370'),
    ('dlk',   'vanquotejourney',                               'read',        NULL,  '7360'),
    ('edw',   'tbl_fact_ga_clicks_GA4',                        'read',        NULL,  '7050'),
    ('edw',   'tbl_fact_policy_sales',                         'read',        NULL,  '7100, 7120, 7180, 7190'),
    ('edw',   'tbl_ref_policy',                                'read',        NULL,  '7060, 7180'),
    ('lkp',   'EventSource',                                   'write',       7010,  '7010'),
    ('ods',   'CustomerCallEvents',                            'read',        NULL,  '7200'),
    ('ods',   'EpisodeEventStream',                            'write',       7030,  '7030'),
    ('ods',   'EventStream',                                   'read/write',  7020,  '7020, 7040, 7050, 7060, 7070, 7080, 7090, 7100, 7110, 7120, 7130, 7140, 7150, 7160, 7170, 7180, 7190, 7200, 7210, 7220, 7230, 7240, 7250, 7260, 7270, 7280, 7290, 7300, 7310, 7320, 7330, 7340, 7350, 7360, 7370, 7380'),
    ('ods',   'EventStreamSummary',                            'write',       7380,  '7380'),
    ('ods',   'MFQQuoteToPolicy',                              'read',        NULL,  '7110'),
    ('ods',   'MfqScvLink',                                    'read',        NULL,  '7090, 7110, 7140, 7150'),
    ('ods',   'motorcustomerpolicyquotelinks',                 'read',        NULL,  '7070, 7100, 7110, 7120, 7140, 7150'),
    ('ods',   'MotorCustomerPolicyQuoteLinksdeduped',          'read',        NULL,  '7080'),
    ('ods',   'motorcustomerpolicyquotelinksdeduped',          'read',        NULL,  '7130'),
    ('ods',   'Policy',                                        'read',        NULL,  '7160, 7170, 7210'),
    ('ods',   'policy',                                        'read',        NULL,  '7220, 7300'),
    ('ods',   'RelayDocumentEvents',                           'read',        NULL,  '7060'),
    ('stg',   'MFQ_Quote_Payments',                            'read',        NULL,  '7090'),
    ('stg',   'MFQ_Steps_Summary',                             'read',        NULL,  '7150'),
    ('stg',   'MFQCallEvents',                                 'read',        NULL,  '7040'),
    ('stg',   'MotorClaims',                                   'read',        NULL,  '7240');
GO

-- ==============================================================================================
--  1.  MISSING
-- ==============================================================================================

SELECT  s.SchemaName,
        s.TableName,
        s.UsedFor,
        s.UsedByNodes
FROM    #GraphSourceTables AS s
WHERE   s.BuiltByNode IS NULL
        AND NOT EXISTS (SELECT 1
                        FROM   INFORMATION_SCHEMA.TABLES AS t
                        WHERE  t.TABLE_SCHEMA = s.SchemaName
                               AND t.TABLE_NAME = s.TableName)
ORDER BY s.SchemaName, s.TableName;
--  no rows is the answer you want
GO

-- ==============================================================================================
--  2.  THE FULL PICTURE
-- ==============================================================================================

SELECT  s.SchemaName,
        s.TableName,
        s.UsedFor,
        CASE
            WHEN s.BuiltByNode IS NOT NULL THEN 'built by graph'
            WHEN t.TABLE_NAME IS NULL       THEN 'missing'
            WHEN CAST(CAST(t.TABLE_SCHEMA AS varchar(128)) AS varbinary(256))
                 = CAST(CAST(s.SchemaName AS varchar(128)) AS varbinary(256))
                 AND CAST(CAST(t.TABLE_NAME AS varchar(128)) AS varbinary(256))
                 = CAST(CAST(s.TableName AS varchar(128)) AS varbinary(256))
                                            THEN 'ok'
            ELSE 'case mismatch'
        END                                         AS Status,
        COALESCE(t.TABLE_SCHEMA + '.' + t.TABLE_NAME, '') AS NameInCatalog,
        s.BuiltByNode,
        s.UsedByNodes
FROM    #GraphSourceTables AS s
        LEFT OUTER JOIN INFORMATION_SCHEMA.TABLES AS t
        ON  t.TABLE_SCHEMA = s.SchemaName
            AND t.TABLE_NAME = s.TableName
ORDER BY CASE
             WHEN s.BuiltByNode IS NOT NULL THEN 3
             WHEN t.TABLE_NAME IS NULL      THEN 1
             ELSE 2
         END,
         s.SchemaName,
         s.TableName;
GO

-- ==============================================================================================
--  3.  NAMES THE NOTEBOOK SPELLS MORE THAN ONE WAY
-- ==============================================================================================

--  The notebook is Spark SQL, which resolves table names without regard to case, so
--  both spellings work there. A case-sensitive warehouse will accept only one, and the
--  node SQL carries whichever spelling the cell used.

SELECT  SchemaName,
        TableName,
        UsedByNodes
FROM    #GraphSourceTables
WHERE   LOWER(SchemaName) + '.' + LOWER(TableName) IN (
            'dlk.ext_travel_policy_trans',
            'dlk.hfq_quotedetails',
            'dlk.hfq_quotedetails_snapshot_v2',
            'ods.motorcustomerpolicyquotelinksdeduped',
            'ods.policy'
        )
ORDER BY LOWER(SchemaName), LOWER(TableName), TableName;
--  expect 10 rows covering 5 objects:
--      dlk.EXT_Travel_Policy_Trans and dlk.ext_travel_policy_trans
--      dlk.HFQ_QuoteDetails and dlk.hfq_quotedetails
--      dlk.HFQ_QuoteDetails_snapshot_v2 and dlk.hfq_quotedetails_snapshot_v2
--      ods.MotorCustomerPolicyQuoteLinksdeduped and ods.motorcustomerpolicyquotelinksdeduped
--      ods.Policy and ods.policy
GO

-- ==============================================================================================
--  TIDY UP
-- ==============================================================================================

DROP TABLE IF EXISTS #GraphSourceTables;
GO
