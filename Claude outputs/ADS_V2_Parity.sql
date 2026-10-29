
/* 1. One pass over each source: rows per event, minute and day */
select  EventTypeId, EventId, EventDateTime, EventDate,
        count(*)                                                  as RowsN,
        sum(case when SCV_Customer_Key is null then 1 else 0 end) as UnlinkedN,
        min(SCV_Customer_Key)                                     as SCV_Customer_Key
into    #old_raw
from    ods.scvepisodeeventstreamfinal
group by EventTypeId, EventId, EventDateTime, EventDate;

select  EventTypeId, EventId, EventDateTime, EventDate,
        count(*)                                                  as RowsN,
        sum(case when SCV_Customer_Key is null then 1 else 0 end) as UnlinkedN,
        min(SCV_Customer_Key)                                     as SCV_Customer_Key
into    #new_raw
from    [ads_v2].[episodeeventsnumbered]
group by EventTypeId, EventId, EventDateTime, EventDate;

/* 2. Minute keys (one row per event and minute, with its SCV) */
select  EventTypeId, EventId, EventDateTime, min(SCV_Customer_Key) as SCV_Customer_Key
into    #old_min
from    #old_raw
where   EventId is not null and EventDateTime is not null
group by EventTypeId, EventId, EventDateTime;

select  EventTypeId, EventId, EventDateTime, min(SCV_Customer_Key) as SCV_Customer_Key
into    #new_min
from    #new_raw
where   EventId is not null and EventDateTime is not null
group by EventTypeId, EventId, EventDateTime;

/* 3. Day keys */
select  distinct EventTypeId, EventId, EventDate
into    #old_day
from    #old_raw
where   EventId is not null and EventDate is not null;

select  distinct EventTypeId, EventId, EventDate
into    #new_day
from    #new_raw
where   EventId is not null and EventDate is not null;

/* 4. Per event type summaries */
select  r.EventTypeId,
        sum(r.RowsN)     as [Events],
        sum(r.UnlinkedN) as Unlinked,
        (select count(*) from #old_min m where m.EventTypeId = r.EventTypeId) as MinuteKeys,
        (select count(*) from #old_day d where d.EventTypeId = r.EventTypeId) as DayKeys
into    #old_sum
from    #old_raw r
group by r.EventTypeId;

select  r.EventTypeId,
        sum(r.RowsN)     as [Events],
        sum(r.UnlinkedN) as Unlinked,
        (select count(*) from #new_min m where m.EventTypeId = r.EventTypeId) as MinuteKeys,
        (select count(*) from #new_day d where d.EventTypeId = r.EventTypeId) as DayKeys
into    #new_sum
from    #new_raw r
group by r.EventTypeId;

/* 5. Matches */
select  o.EventTypeId,
        count(*) as MatchedMinute,
        sum(case when o.SCV_Customer_Key is not null and n.SCV_Customer_Key is not null then 1 else 0 end) as ScvBothLinked,
        sum(case when o.SCV_Customer_Key = n.SCV_Customer_Key then 1 else 0 end)                          as ScvAgree
into    #matched_min
from    #old_min o
join    #new_min n
        on n.EventTypeId = o.EventTypeId and n.EventId = o.EventId and n.EventDateTime = o.EventDateTime
group by o.EventTypeId;

select  o.EventTypeId, count(*) as MatchedDay
into    #matched_day
from    #old_day o
join    #new_day n
        on n.EventTypeId = o.EventTypeId and n.EventId = o.EventId and n.EventDate = o.EventDate
group by o.EventTypeId;

/* 6. Result */
--drop table if exists {target_schema}.EventStreamParity;
select  coalesce(o.EventTypeId, n.EventTypeId)                  as EventTypeId,
        coalesce(o.[Events], 0)                                as OldEvents,
        coalesce(n.[Events], 0)                                as NewEvents,
        coalesce(o.MinuteKeys, 0)                              as OldMinuteKeys,
        coalesce(n.MinuteKeys, 0)                              as NewMinuteKeys,
        coalesce(o.DayKeys, 0)                                 as OldDayKeys,
        coalesce(n.DayKeys, 0)                                 as NewDayKeys,
        coalesce(m.MatchedMinute, 0)                           as MatchedMinute,
        coalesce(d.MatchedDay, 0)                              as MatchedDay,
        coalesce(o.DayKeys, 0) - coalesce(d.MatchedDay, 0)     as OnlyOldDayKeys,
        coalesce(n.DayKeys, 0) - coalesce(d.MatchedDay, 0)     as OnlyNewDayKeys,
        coalesce(m.ScvBothLinked, 0)                           as ScvBothLinked,
        coalesce(m.ScvAgree, 0)                                as ScvAgree,
        coalesce(o.Unlinked, 0)                                as OldUnlinked,
        coalesce(n.Unlinked, 0)                                as NewUnlinked
--into    {target_schema}.EventStreamParity
from    #old_sum o
full join #new_sum n
        on n.EventTypeId = o.EventTypeId
left join #matched_min m
        on m.EventTypeId = coalesce(o.EventTypeId, n.EventTypeId)
left join #matched_day d
        on d.EventTypeId = coalesce(o.EventTypeId, n.EventTypeId)
order by EventTypeId;