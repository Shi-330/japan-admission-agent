-- Add Chinese simplified aliases to tags so students can search in Chinese
UPDATE schools SET tags = array_cat(tags, ARRAY['情报','情报理工']) WHERE '情報' = ANY(tags);
UPDATE schools SET tags = array_cat(tags, ARRAY['计算机','计算机科学']) WHERE name LIKE '%コンピュータ%' OR name LIKE '%东京大学%';
UPDATE schools SET tags = array_cat(tags, ARRAY['人工智能','AI']) WHERE 'AI' = ANY(tags) OR name LIKE '%人工知能%';
UPDATE schools SET tags = array_cat(tags, ARRAY['电气电子','电子']) WHERE '電気電子' = ANY(majors) OR '電気電子工学' = ANY(majors);
