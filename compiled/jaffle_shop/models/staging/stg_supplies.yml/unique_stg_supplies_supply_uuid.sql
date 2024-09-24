
    
    

select
    supply_uuid as unique_field,
    count(*) as n_records

from "jaffle_shop"."main"."stg_supplies"
where supply_uuid is not null
group by supply_uuid
having count(*) > 1


