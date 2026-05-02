-- 更新杯型尺寸數據 v2（outer_r / inner_r 更新，theta_deg 不變）
-- 在 Supabase SQL Editor 執行

UPDATE cup_sizes SET outer_r=337.28, inner_r=248.29 WHERE cup_name='8oz_冷熱杯';
UPDATE cup_sizes SET outer_r=381.41, inner_r=273.41 WHERE cup_name='12oz_冷熱杯';
UPDATE cup_sizes SET outer_r=439.65, inner_r=307.24 WHERE cup_name='16oz_冷熱杯';
UPDATE cup_sizes SET outer_r=516.95, inner_r=356.90 WHERE cup_name='20oz_冷熱杯';
UPDATE cup_sizes SET outer_r=618.61, inner_r=452.47 WHERE cup_name='22oz_冷熱杯';
UPDATE cup_sizes SET outer_r=530.29, inner_r=363.22 WHERE cup_name='24oz_冷熱杯';
UPDATE cup_sizes SET outer_r=371.42, inner_r=289.44 WHERE cup_name='8oz_雙層杯';
UPDATE cup_sizes SET outer_r=411.00, inner_r=310.68 WHERE cup_name='12oz_雙層杯';
UPDATE cup_sizes SET outer_r=479.33, inner_r=356.26 WHERE cup_name='16oz_雙層杯';
UPDATE cup_sizes SET outer_r=569.89, inner_r=418.87 WHERE cup_name='20oz_雙層杯';

-- 驗證
SELECT cup_name, outer_r, inner_r, theta_deg FROM cup_sizes ORDER BY cup_series, id;
