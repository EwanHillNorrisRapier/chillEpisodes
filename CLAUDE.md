# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Working copies of Microsoft Fabric notebooks (PySpark / Spark SQL) and Fabric warehouse T-SQL for the Chill **Episode Event Stream**: a table of customer journey events (quotes, calls, sales, renewals, chases, and so on) built from the client's data. Nothing here builds, lints or tests locally. Notebooks run in the Fabric workspace **Dev_CGP** (lakehouse `ChillLH`, kernel `synapse_pyspark`), and the T-SQL runs in a Fabric warehouse. There is no package manifest or test runner in this repo.

`.ipynb` files are large single-line JSON. To read one, extract the cells with node rather than reading the raw file:

```
node -e "const nb=JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'));nb.cells.forEach((c,i)=>console.log('--- ['+i+'] '+c.cell_type+'\n'+[].concat(c.source).join('')))" "main_v2/ADS_v2_00_Setup.ipynb"
```

## Layout

- `main_v2/` is the current build (v2), described below. Its two PDFs are the main design references: `Team pack.pdf` (architecture, table catalogue, agreed rules, what is still outstanding) and `Episode Event Stream build — bugs and lessons.pdf` (why the v1 stream was wrong, plus the checklist for every new step).
- `main/` is the legacy v1 build. `04 - Populate Episode Event Stream` appends about 300 event types into `ods.EpisodeEventStream` from dlk/edw/ods/stg/lkp with literal dates. `05 - Attach SCV ID` links events to SCV customers. v2 replaces both, plus notebook 06 (episode numbering). Use v1 for parity comparison and history, not as a pattern to copy.
- `scratchCode/`, `fabric_extract_20260923/` hold scratch work and exports of the per-journey reconciliation notebooks. The root `.xlsx` files are reconciliation and planning workbooks.
- `Claude outputs/` and `main/config/` hold T-SQL for the **ops harness**, a stored procedure graph scheduler (`ops.CSP*`) being deployed into a Fabric warehouse (see below).

## v2 architecture (main_v2)

Data flows through these layers: `dlk` / `edw` (client source replicas) and `pii` (read only inside Fabric to make hash keys) → **`ods_v2`** (53 tables of reassembled client data, nothing derived, no personal data) → **`ads_v2`** (event stream built from `ods_v2` only, plus the SCV link `ods.scveadmlinkfinal`) → `prd`.

**The notebooks are generated.** They are written by generators in a different repo (`C:\Workspaces\CGP_analysis`):
- ODS: `ods_build/v2/build_notebook.py` from `ods_build/v2/settings.yaml` + `entities/*.yaml` (one entry per table).
- ADS: `ads_build/v2/build_ads.py` from `ads_build/v2/settings.yaml` + `families/*.yaml` (one entry per event type). Event descriptions come from `seeds/ChillEpisodeTypes.csv`.

A fix made only in a notebook here is lost at the next generation (`checks/drift_check.py` lists such cells). If you change SQL in a `main_v2` notebook, say so and point out that the YAML has to change too.

**Notebook pattern**, the same in every build notebook:
1. A parameters cell (`batch_id`, and for ODS `source_set`).
2. `%run ODS_v2_00_Setup` / `%run ADS_v2_00_Setup`. Setup sets Spark conf variables (`ods.target`, `ods.stg`, `ods.cutoff_date`, `ods.batch_id`, `ods.dlk`/`ods.edw`/... for ODS; `ads.target`, `ads.ods`, `ads.stg`, `ads.start_time`, `ads.end_time`, `ads.effective_date` for ADS). It also registers the hash/redact UDFs (`ods_hash_email`, `ods_hash_phone`, `ods_hash_id`, `ods_eircode_area`, `ods_redact`) and the run log helper.
3. A start log, then one SQL statement per cell. SQL refers to schemas and windows only through `${ods.*}` / `${ads.*}` substitution.
4. A final checks cell: unique non-null business key, distinct surrogate key, no PII-named columns, no email/mobile values in text. It writes to `OdsBuildLog` / `AdsBuildLog` and fails the notebook on any failure.

**House style for SQL cells:** no CTEs. Intermediate steps are their own tables (`stg.odsv2_*`, `stg.adsv2_*`, event families as `stg.adsv2_evt_<code>`). Every cell is `create or replace`, so re-running from a failed cell is always safe. Every cell starts with the boxed header comment: Name, Description, Grain, Business key / Surrogate key, Source, Reads. No literal dates: the window comes from settings only.

**Run order.**
- ODS: `10_Policy` → `20_Quote` → `21`–`24`, `30_Interaction` in parallel; `40_Reference` can run at any point. `ODS_v2_Run` holds the DAG and resumes a failed batch by skipping notebooks already `succeeded` in `OdsRunLog`. Notebook-launched orchestration (`runMultiple` / `notebook.run`) fails in Fabric, though, so in practice the notebooks run one at a time, by hand or as jobs.
- ADS: `10_Common` (shared tables: active sales, Relay documents, renewal cycles, re-quotes, HFQ prices/payments) → `11`–`14` (Motor and Home acquisition and renewal families) → `19_EventStream`. `19_EventStream` unions every family into `ads_v2.EventStream`, one row per `EventId`, and writes per-family output tests to `ads_v2.AdsFamilyCheck`.

**Key conventions:**
- `EventId = xxhash64(code, grain, references, minute)`, stable across runs. Duplicates from a repeated source row collapse in the union.
- Every event carries `EventTimeBasis` (actual / derived) and real `SourceSystemId`s: 1 Relay, 2 MFQ, 3 HFQ, 4 Home QS, 5 Mapfre, 7 Van, 8 Travel quotes, 9 QuotationStorage, 20 Genesys, 21 Xtremepush, 22 Mercury, 23 CDA.
- Personal data only ever appears as salted SHA-256 `*Key` columns. Free text that can contain contact details goes through `ods_redact`. Names, addresses, DOB and full Eircodes are never taken. **The hash salt in the two setup notebooks must be identical and must never change**: every key depends on it.
- `source_set` switches between the `frozen` dev sources (`dlk`, `edw`, `dlk_bak_20260914`, `ods`, `pii`) and `prod` (`prod_dlk`, `prod_edw`, `prod_pii`).
- ODS event/transaction tables start at the cut-off 2021-04-01. Policy tables keep their full history.
- `ods.scveadmlinkfinal` is the **only** policy / quote / client → SCV link. References that do not link go to `ads_v2.ScvLinkExceptions`; they are never given a silent negative key.

## Writing or reviewing an event family

The bugs-and-lessons PDF lists 15 recurring v1 failure patterns. The ones to check every time:
- Read the flow sheet text for the step, not only its name (`Chill_Episode_Frameworks.xlsx`). If it says "no signal", do not build the step.
- Do not infer what a code, channel or flag means from its values. Ask Vijay, then record the answer in the decision log (`out/e1_findings.md` in the CGP_analysis repo).
- Profile the source before joining on it. Look for `GDPR` sentinel values, unreliable flags (`RecordVersionIsLatest`: use `max(RecordVersion)`), mixed clocks (MFQ was Irish local time until 2026-06-11 and UTC after that), and keys a product does not fill (Home sales have no `QuoteQueryGuid`; use `HEQReference`).
- Anchor each event to its cycle or sale with a date range, not only to the policy or customer. Use the real event time, not a proxy such as the sale date or due − 60. Keep one event per occurrence at its first time: no `GROUP BY PolicyCode` over the whole window, and no month bucketing.
- Put only keys of the right type in reference columns: only an SCV key in the customer column, never an email or a guid.
- Watch for SQL that cannot work: `NOT IN` against a list that contains NULL, or a quoted string compared as if it were a column (use backticks).
- Before handover, check the step's output: row count against the source's own event count, zero exact duplicates, min and max time inside the window and not after the data date, and an explanation for zero rows or a count identical to another family.

## Ops harness (Fabric warehouse T-SQL)

`ops.CSP*` is a graph scheduler. A graph (`CSPScheduleGraph`) has nodes (`CSPScheduleGraphNode`) joined by segments (`CSPScheduleGraphSegment`), and each node's SQL is stored in `CSPScheduledItemString` with `##` tokens that `ops.CSPSubstituteParams` replaces. The entry point is `EXECUTE ops.CSPExecuteGenericGraph @cspgraphid = <id>`.

To deploy into a new warehouse, run these in order: `Claude outputs/Deploy harness/1 - check schemas.sql` → `2 - create tables and seed.sql` → `create_harness_trimmed.sql` → `3 - dummy graph.sql` (graph 9001, a smoke test). The order matters because the inline TVFs bind their tables at create time.

`Build EventStream graph/` defines graph 7001: 38 nodes mirroring a Fabric notebook, node ids from 7010 in steps of 10, and scheduled item id = node id. Its node SQL is still Spark SQL, so build nodes fail until that SQL is translated to T-SQL.

Fabric warehouses are **case sensitive**: schema and object names must match exactly (`ops`, `stg`, `trk`, all lower case).
