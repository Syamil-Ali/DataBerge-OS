-- Data-Berge Supabase connector demo
-- Run this entire file in a NEW Supabase project's SQL Editor.
-- Before running it, replace CHANGE_ME_WITH_A_STRONG_PASSWORD below.
-- Use a unique password. An alphanumeric password is easiest for this first test.

create schema if not exists data_berge_demo;

create table if not exists data_berge_demo.retail_sales (
    sale_id bigint generated always as identity primary key,
    order_id text not null unique,
    order_date date not null,
    state text not null,
    city text not null,
    sales_channel text not null,
    customer_segment text not null,
    product_category text not null,
    product_name text not null,
    payment_method text not null,
    units integer not null check (units > 0),
    unit_price numeric(12, 2) not null check (unit_price >= 0),
    discount_pct numeric(5, 2) not null check (discount_pct between 0 and 100),
    revenue numeric(14, 2) not null check (revenue >= 0),
    satisfaction_score numeric(3, 1) check (satisfaction_score between 1 and 5)
);

truncate table data_berge_demo.retail_sales restart identity;

with generated_sales as (
    select
        g,
        (date '2024-01-01' + ((g * 17) % 730))::date as order_date,
        (array['Selangor', 'Kuala Lumpur', 'Johor', 'Penang', 'Sabah', 'Sarawak'])[((g - 1) % 6) + 1] as state,
        (array['Shah Alam', 'Kuala Lumpur', 'Johor Bahru', 'George Town', 'Kota Kinabalu', 'Kuching'])[((g - 1) % 6) + 1] as city,
        (array['Online', 'Retail Store', 'Marketplace'])[((g - 1) % 3) + 1] as sales_channel,
        (array['Consumer', 'SME', 'Enterprise'])[((g - 1) % 3) + 1] as customer_segment,
        (array['Electronics', 'Home', 'Fashion', 'Food & Beverage', 'Health'])[((g - 1) % 5) + 1] as product_category,
        (array['Wireless Earbuds', 'Rice Cooker', 'Running Shoes', 'Coffee Beans', 'Vitamin Pack'])[((g - 1) % 5) + 1] as product_name,
        (array['FPX', 'Card', 'E-Wallet', 'Cash'])[((g - 1) % 4) + 1] as payment_method,
        ((g * 7) % 8) + 1 as units,
        (array[129.90, 189.00, 249.50, 42.90, 68.00]::numeric[])[((g - 1) % 5) + 1] as unit_price,
        (array[0, 5, 10, 15]::numeric[])[((g - 1) % 4) + 1] as discount_pct,
        (1 + ((g * 13) % 41) / 10.0)::numeric(3, 1) as satisfaction_score
    from generate_series(1, 3000) as series(g)
)
insert into data_berge_demo.retail_sales (
    order_id,
    order_date,
    state,
    city,
    sales_channel,
    customer_segment,
    product_category,
    product_name,
    payment_method,
    units,
    unit_price,
    discount_pct,
    revenue,
    satisfaction_score
)
select
    'MY-' || to_char(order_date, 'YYYY') || '-' || lpad(g::text, 6, '0'),
    order_date,
    state,
    city,
    sales_channel,
    customer_segment,
    product_category,
    product_name,
    payment_method,
    units,
    unit_price,
    discount_pct,
    round(units * unit_price * (1 - discount_pct / 100), 2),
    satisfaction_score
from generated_sales;

-- Create an account that Data-Berge can use without receiving owner access.
do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'data_berge_reader') then
        create role data_berge_reader login;
    end if;
end
$$;

-- Supabase's dashboard postgres role is not a true superuser, so do not include
-- SUPERUSER/REPLICATION attribute changes here. A newly created role does not
-- receive those elevated privileges by default.
alter role data_berge_reader
    with password 'CHANGE_ME_WITH_A_STRONG_PASSWORD';

grant connect on database postgres to data_berge_reader;
grant usage on schema data_berge_demo to data_berge_reader;
grant select on all tables in schema data_berge_demo to data_berge_reader;

alter default privileges in schema data_berge_demo
    grant select on tables to data_berge_reader;

-- Quick verification: this should return 3,000 rows and a positive revenue total.
select count(*) as row_count, round(sum(revenue), 2) as total_revenue
from data_berge_demo.retail_sales;
