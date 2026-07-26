ALTER TABLE schools ADD COLUMN type TEXT DEFAULT '';

UPDATE schools SET type = '私立' WHERE name LIKE '%早稻田%' OR name LIKE '%庆应%' OR name LIKE '%明治%' OR name LIKE '%青山%' OR name LIKE '%立教%' OR name LIKE '%中央%' OR name LIKE '%法政%';
UPDATE schools SET type = '国立' WHERE type = '';
