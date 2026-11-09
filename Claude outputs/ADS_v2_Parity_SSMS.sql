/*
    ADS v2 parity with the current event stream (T-SQL for the lakehouse SQL analytics endpoint, run in SSMS).
    The same comparison as ADS_v2_22_Parity cell 5: per EventTypeId, events on each side, reference keys matched at
    the same minute / same day, keys only on one side, and SCV agreement on the same-minute matches (negative SCV keys
    count as unlinked). Matches on references (policy, quote, source reference), not EventId: the two streams compute
    EventId differently. Returns the result; nothing is written.

    Set @start / @end to the window of the ads_v2 run (the ADS_v2_00_Setup defaults are below).
*/
DECLARE @start datetime2(6) = '2021-07-01';
DECLARE @end   datetime2(6) = '2026-09-01';

WITH old_k AS (
    SELECT  CAST(EventTypeId AS varchar(50))                                   AS EventTypeId,
            CONCAT_WS('|', CAST(EventTypeId AS varchar(50)),
                      COALESCE(UPPER(TRIM(SourcePolicyReference)), ''),
                      COALESCE(LOWER(TRIM(SourceQuoteReference)), ''),
                      COALESCE(TRIM(CAST(EventSourceReference AS varchar(400))), '')) AS RefKey,
            DATEADD(minute, DATEDIFF(minute, 0, EventDateTime), 0)              AS EventMinute,
            CAST(EventDateTime AS date)                                         AS EventDay,
            CASE WHEN SCV_Customer_Key > 0 THEN SCV_Customer_Key END            AS SCV_Customer_Key
    FROM    ods.scveventstreamfinal
    WHERE   EventDateTime >= @start AND EventDateTime < @end
),
new_k AS (
    SELECT  CAST(EventTypeId AS varchar(50))                                   AS EventTypeId,
            CONCAT_WS('|', CAST(EventTypeId AS varchar(50)),
                      COALESCE(UPPER(TRIM(SourcePolicyReference)), ''),
                      COALESCE(LOWER(TRIM(SourceQuoteReference)), ''),
                      COALESCE(TRIM(CAST(EventSourceReference AS varchar(400))), '')) AS RefKey,
            DATEADD(minute, DATEDIFF(minute, 0, EventDateTime), 0)              AS EventMinute,
            CAST(EventDateTime AS date)                                         AS EventDay,
            CASE WHEN SCV_Customer_Key > 0 THEN SCV_Customer_Key END            AS SCV_Customer_Key
    FROM    ads_v2.ScvEventStream
    WHERE   EventDateTime >= @start AND EventDateTime < @end
),
old_min AS (SELECT EventTypeId, RefKey, EventMinute, MIN(SCV_Customer_Key) AS SCV FROM old_k GROUP BY EventTypeId, RefKey, EventMinute),
new_min AS (SELECT EventTypeId, RefKey, EventMinute, MIN(SCV_Customer_Key) AS SCV FROM new_k GROUP BY EventTypeId, RefKey, EventMinute),
old_day AS (SELECT DISTINCT EventTypeId, RefKey, EventDay FROM old_k),
new_day AS (SELECT DISTINCT EventTypeId, RefKey, EventDay FROM new_k),
old_sum AS (SELECT EventTypeId, COUNT(*) AS Events, SUM(CASE WHEN SCV_Customer_Key IS NULL THEN 1 ELSE 0 END) AS Unlinked FROM old_k GROUP BY EventTypeId),
new_sum AS (SELECT EventTypeId, COUNT(*) AS Events, SUM(CASE WHEN SCV_Customer_Key IS NULL THEN 1 ELSE 0 END) AS Unlinked FROM new_k GROUP BY EventTypeId),
old_mk  AS (SELECT EventTypeId, COUNT(*) AS MinuteKeys FROM old_min GROUP BY EventTypeId),
new_mk  AS (SELECT EventTypeId, COUNT(*) AS MinuteKeys FROM new_min GROUP BY EventTypeId),
old_dk  AS (SELECT EventTypeId, COUNT(*) AS DayKeys FROM old_day GROUP BY EventTypeId),
new_dk  AS (SELECT EventTypeId, COUNT(*) AS DayKeys FROM new_day GROUP BY EventTypeId),
m AS (
    SELECT  o.EventTypeId,
            COUNT(*)                                                            AS MatchedMinute,
            SUM(CASE WHEN o.SCV IS NOT NULL AND n.SCV IS NOT NULL THEN 1 ELSE 0 END) AS ScvBothLinked,
            SUM(CASE WHEN o.SCV = n.SCV THEN 1 ELSE 0 END)                      AS ScvAgree
    FROM    old_min o
    JOIN    new_min n ON n.EventTypeId = o.EventTypeId AND n.RefKey = o.RefKey AND n.EventMinute = o.EventMinute
    GROUP BY o.EventTypeId
),
d AS (
    SELECT  o.EventTypeId, COUNT(*) AS MatchedDay
    FROM    old_day o
    JOIN    new_day n ON n.EventTypeId = o.EventTypeId AND n.RefKey = o.RefKey AND n.EventDay = o.EventDay
    GROUP BY o.EventTypeId
),
types AS (SELECT EventTypeId FROM old_sum UNION SELECT EventTypeId FROM new_sum)
SELECT  t.EventTypeId,
        COALESCE(os.Events, 0)                                     AS OldEvents,
        COALESCE(ns.Events, 0)                                     AS NewEvents,
        COALESCE(omk.MinuteKeys, 0)                                AS OldMinuteKeys,
        COALESCE(nmk.MinuteKeys, 0)                                AS NewMinuteKeys,
        COALESCE(odk.DayKeys, 0)                                   AS OldDayKeys,
        COALESCE(ndk.DayKeys, 0)                                   AS NewDayKeys,
        COALESCE(m.MatchedMinute, 0)                               AS MatchedMinute,
        COALESCE(d.MatchedDay, 0)                                  AS MatchedDay,
        COALESCE(odk.DayKeys, 0) - COALESCE(d.MatchedDay, 0)       AS OnlyOldDayKeys,
        COALESCE(ndk.DayKeys, 0) - COALESCE(d.MatchedDay, 0)       AS OnlyNewDayKeys,
        COALESCE(m.ScvBothLinked, 0)                               AS ScvBothLinked,
        COALESCE(m.ScvAgree, 0)                                    AS ScvAgree,
        COALESCE(os.Unlinked, 0)                                   AS OldUnlinked,
        COALESCE(ns.Unlinked, 0)                                   AS NewUnlinked,
        ROUND(100.0 * COALESCE(d.MatchedDay, 0) / NULLIF(odk.DayKeys, 0), 1)   AS PctOldMatchedDay,
        ROUND(100.0 * COALESCE(m.ScvAgree, 0) / NULLIF(m.ScvBothLinked, 0), 1) AS PctScvAgree
FROM    types t
LEFT JOIN old_sum os  ON os.EventTypeId  = t.EventTypeId
LEFT JOIN new_sum ns  ON ns.EventTypeId  = t.EventTypeId
LEFT JOIN old_mk  omk ON omk.EventTypeId = t.EventTypeId
LEFT JOIN new_mk  nmk ON nmk.EventTypeId = t.EventTypeId
LEFT JOIN old_dk  odk ON odk.EventTypeId = t.EventTypeId
LEFT JOIN new_dk  ndk ON ndk.EventTypeId = t.EventTypeId
LEFT JOIN m           ON m.EventTypeId   = t.EventTypeId
LEFT JOIN d           ON d.EventTypeId   = t.EventTypeId
ORDER BY t.EventTypeId;
