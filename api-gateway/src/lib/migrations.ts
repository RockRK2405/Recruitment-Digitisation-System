/**
 * Idempotent schema migrations run at gateway startup.
 *
 * Why: database/schema.sql only runs on Postgres initdb (empty volume).
 * If a user upgrades the code without `docker compose down -v`, the new
 * columns/tables added in later phases never exist, and every INSERT
 * referencing them fails silently in background tasks.
 *
 * This file re-asserts every schema change since Phase 4 using
 * IF NOT EXISTS / IF NOT EXISTS clauses, so it's safe to run on every
 * startup against any database state.
 */

import { Pool } from 'pg'

const MIGRATIONS: Array<{ name: string; sql: string }> = [
  {
    name: 'phase4_candidate_notes',
    sql: `
      CREATE TABLE IF NOT EXISTS candidate_notes (
          id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
          candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
          body TEXT NOT NULL,
          author VARCHAR(150),
          created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
          updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
      );
      CREATE INDEX IF NOT EXISTS idx_candidate_notes_candidate ON candidate_notes(candidate_id, created_at DESC);
    `,
  },
  {
    name: 'phase5_job_descriptions_extra_fields',
    sql: `
      ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS department VARCHAR(150);
      ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS employment_type VARCHAR(50);
      ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS mandatory_skills TEXT[] DEFAULT '{}';
      ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS preferred_skills TEXT[] DEFAULT '{}';
      ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS soft_skills TEXT[] DEFAULT '{}';
      ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS responsibilities TEXT;
      ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS salary_range VARCHAR(150);
      ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS keywords TEXT[] DEFAULT '{}';
      ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS parsed_json JSONB;
      ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS parsed_at TIMESTAMP WITH TIME ZONE;
    `,
  },
  {
    name: 'phase5_match_results_llm_columns',
    sql: `
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS llm_score REAL DEFAULT 0;
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS experience_match REAL DEFAULT 0;
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS education_match REAL DEFAULT 0;
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS certification_match REAL DEFAULT 0;
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS industry_match REAL DEFAULT 0;
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS leadership_score REAL DEFAULT 0;
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS communication_score REAL DEFAULT 0;
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS growth_score REAL DEFAULT 0;
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS resume_quality REAL DEFAULT 0;
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS strengths TEXT[] DEFAULT '{}';
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS weaknesses TEXT[] DEFAULT '{}';
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS interview_focus TEXT[] DEFAULT '{}';
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS recommendation VARCHAR(50);
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS llm_summary TEXT;
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS llm_model_used VARCHAR(150);
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(20);
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS evaluated_at TIMESTAMP WITH TIME ZONE;
      ALTER TABLE match_results ADD COLUMN IF NOT EXISTS stage VARCHAR(20) DEFAULT 'prefilter';
    `,
  },
  {
    name: 'phase5_scoring_weights',
    sql: `
      CREATE TABLE IF NOT EXISTS scoring_weights (
          key VARCHAR(50) PRIMARY KEY,
          value REAL NOT NULL,
          updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
      );
      INSERT INTO scoring_weights (key, value) VALUES
          ('llm_weight', 0.40),
          ('skill_weight', 0.25),
          ('experience_weight', 0.15),
          ('certification_weight', 0.10),
          ('education_weight', 0.05),
          ('resume_quality_weight', 0.05)
      ON CONFLICT (key) DO NOTHING;
    `,
  },
]

export async function runMigrations(pool: Pool): Promise<void> {
  for (const m of MIGRATIONS) {
    try {
      await pool.query(m.sql)
      console.log(`✓ migration ok: ${m.name}`)
    } catch (e) {
      console.error(`✗ migration FAILED: ${m.name}`, e instanceof Error ? e.message : e)
      throw e
    }
  }
  console.log(`✓ all ${MIGRATIONS.length} migrations applied`)
}
