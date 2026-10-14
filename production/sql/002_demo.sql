-- Synthetic records only. Tenant A north=300, south=700; tenant B north=9000.
INSERT INTO analytics.customers VALUES
 (1,'11111111-1111-1111-1111-111111111111','north','retail'),
 (2,'11111111-1111-1111-1111-111111111111','south','business'),
 (3,'22222222-2222-2222-2222-222222222222','north','retail') ON CONFLICT DO NOTHING;
INSERT INTO analytics.products VALUES
 (1,'11111111-1111-1111-1111-111111111111','north','Notebook','stationery'),
 (2,'11111111-1111-1111-1111-111111111111','south','Desk','furniture'),
 (3,'22222222-2222-2222-2222-222222222222','north','Monitor','electronics') ON CONFLICT DO NOTHING;
INSERT INTO analytics.sales VALUES
 (1,'11111111-1111-1111-1111-111111111111','north',1,1,'2026-03-01',2,100,'completed'),
 (2,'11111111-1111-1111-1111-111111111111','north',1,1,'2026-04-01',4,200,'completed'),
 (3,'11111111-1111-1111-1111-111111111111','south',2,2,'2026-03-01',1,700,'completed'),
 (4,'22222222-2222-2222-2222-222222222222','north',3,3,'2026-03-01',1,9000,'completed'),
 (5,'11111111-1111-1111-1111-111111111111','north',1,1,'2026-05-01',1,999,'cancelled') ON CONFLICT DO NOTHING;
