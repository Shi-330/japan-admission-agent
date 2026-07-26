-- Academic hierarchy: University → Graduate School → Program → Documents
-- Replaces the flat "schools" table with a 3-tier structure.
-- Existing schools table is preserved as a denormalized search cache (built from programs).

-- 1. Universities
CREATE TABLE IF NOT EXISTS universities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  name_jp TEXT,
  type TEXT DEFAULT '国立',       -- 国立 / 公立 / 私立
  location TEXT,                  -- 都道府县
  website TEXT,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Graduate Schools (研究科)
CREATE TABLE IF NOT EXISTS graduate_schools (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id UUID NOT NULL REFERENCES universities(id) ON DELETE CASCADE,
  name TEXT NOT NULL,             -- e.g. "理学系研究科"
  name_jp TEXT,
  website TEXT,
  exam_type TEXT,                 -- 一般入试 / 外国人特别选拔 / SGU
  jlpt JSONB,                    -- 研究科级别日语要求（所有专攻默认继承）
  english JSONB,                 -- 研究科级别英语要求（所有专攻默认继承）
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(university_id, name)
);

-- 3. Programs (专攻)
-- jlpt/english fields: NULL = inherit from graduate_school; non-NULL = override
CREATE TABLE IF NOT EXISTS programs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  graduate_school_id UUID NOT NULL REFERENCES graduate_schools(id) ON DELETE CASCADE,
  name TEXT NOT NULL,             -- e.g. "地球惑星科学専攻"
  name_jp TEXT,
  degree TEXT DEFAULT '修士',     -- 修士 / 博士 / 研究生
  capacity INTEGER,               -- 定员
  jlpt JSONB,                    -- NULL=继承研究科 / non-NULL=专攻特有要求
  english JSONB,                 -- NULL=继承研究科 / non-NULL=专攻特有要求（如更高分）
  research_areas TEXT[],          -- ['地震学', '火山学', '地球物理学']
  exam_periods JSONB,             -- [{name: "夏季入试", month: 7}, ...]
  application_deadlines JSONB,    -- [{year: "2027", type: "出願", date: "2026-07-15"}]
  url TEXT,                       -- 专攻官网
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(graduate_school_id, name)
);

-- 4. Documents (募集要項 / 过去问 — lifecycle-managed PDFs)
CREATE TABLE IF NOT EXISTS program_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
  doc_type TEXT NOT NULL,           -- 募集要項 / 過去問 / 入試日程 / シラバス / 教授一覧
  year_tag TEXT NOT NULL,           -- e.g. "2027"
  title TEXT,
  file_url TEXT,                    -- URL to official PDF (不存文件本体)
  valid_from DATE,
  valid_until DATE,
  is_current BOOLEAN DEFAULT false,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_gs_university ON graduate_schools(university_id);
CREATE INDEX IF NOT EXISTS idx_programs_gs ON programs(graduate_school_id);
CREATE INDEX IF NOT EXISTS idx_docs_program ON program_documents(program_id);
CREATE INDEX IF NOT EXISTS idx_docs_year ON program_documents(year_tag, doc_type);
CREATE INDEX IF NOT EXISTS idx_docs_current ON program_documents(program_id) WHERE is_current = true;
