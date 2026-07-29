-- Add credibility fields to schools table
-- Run in Supabase SQL Editor

ALTER TABLE schools ADD COLUMN IF NOT EXISTS website TEXT DEFAULT '';
ALTER TABLE schools ADD COLUMN IF NOT EXISTS source TEXT DEFAULT '';
ALTER TABLE schools ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- Update existing rows with real data
UPDATE schools SET website = 'https://www.i.u-tokyo.ac.jp/edu/entra/entra_e.shtml', source = '東大IST公式サイト 2026年度募集要項', updated_at = '2026-07-12' WHERE name LIKE '%东京大学%';
UPDATE schools SET website = 'https://www.isee.kyushu-u.ac.jp/', source = '九州大学システム情報科学府 2026年度募集要項', updated_at = '2026-07-12' WHERE name LIKE '%九州大学%';
UPDATE schools SET website = 'https://www.ist.hokudai.ac.jp/', source = '北海道大学情報科学研究院公式サイト', updated_at = '2026-07-12' WHERE name LIKE '%北海道大学%';
UPDATE schools SET website = 'https://www.meiji.ac.jp/gst/', source = '明治大学理工学研究科 2026年度学生募集要項', updated_at = '2026-07-12' WHERE name LIKE '%明治大学%';
UPDATE schools SET website = 'https://www.aoyama.ac.jp/faculty/science/', source = '青山学院大学理工学部公式サイト', updated_at = '2026-07-12' WHERE name LIKE '%青山学院%';
UPDATE schools SET website = 'https://www.rikkyo.ac.jp/grad/ais/', source = '立教大学人工知能科学研究科 2026年度入試要項', updated_at = '2026-07-12' WHERE name LIKE '%立教大学%';
UPDATE schools SET website = 'https://www.chuo-u.ac.jp/academics/faculties/science/', source = '中央大学理工学部公式サイト', updated_at = '2026-07-12' WHERE name LIKE '%中央大学%';
UPDATE schools SET website = 'https://www.hosei.ac.jp/grad/computer/', source = '法政大学情報科学研究科公式サイト', updated_at = '2026-07-12' WHERE name LIKE '%法政大学%';
UPDATE schools SET website = 'https://www.i.kyoto-u.ac.jp/', source = '京都大学情報学研究科 2027年度募集要項', updated_at = '2026-07-12' WHERE name LIKE '%京都大学%';
UPDATE schools SET website = 'https://www.isct.ac.jp/', source = '東京科学大学情報理工学院 2026年度募集要項', updated_at = '2026-07-12' WHERE name LIKE '%东京科学%';
UPDATE schools SET website = 'https://www.sie.tsukuba.ac.jp/', source = '筑波大学システム情報工学研究群 2026年度募集要項', updated_at = '2026-07-12' WHERE name LIKE '%筑波大学%';
UPDATE schools SET website = 'https://www.ist.osaka-u.ac.jp/', source = '大阪大学情報科学研究科 2026年度募集要項', updated_at = '2026-07-12' WHERE name LIKE '%大阪大学%';
UPDATE schools SET website = 'https://www.i.nagoya-u.ac.jp/', source = '名古屋大学情報学研究科 2026年度募集要項', updated_at = '2026-07-12' WHERE name LIKE '%名古屋大学%';
UPDATE schools SET website = 'https://www.waseda.jp/fsci/gips/', source = '早稲田大学基幹理工学研究科 2026年度募集要項', updated_at = '2026-07-12' WHERE name LIKE '%早稻田%';
UPDATE schools SET website = 'https://www.is.tohoku.ac.jp/', source = '東北大学情報科学研究科 2026年度募集要項', updated_at = '2026-07-12' WHERE name LIKE '%东北大学%';
