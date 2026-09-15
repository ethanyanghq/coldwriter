-- db/schema.sql
-- SQLite schema for Coldwriter. Applied to <workspace>/db/outreach.sqlite
-- by /init. The workspace is never a git repo; everything versioned lives here.
--
-- Two layers, one file:
--   LEARN CORE  drafts, edits, preferences, constitutions, learn_runs
--               domain-agnostic, keyed by (domain, context_ref). Never references
--               contacts. Becomes a standalone skill when a second consumer exists.
--   OUTREACH    contacts, sends
--               the first consumer. Links via the nullable contact_id column and
--               context_ref = 'contact:<id>'.
--
-- Nothing derived is stored. Diff hunks are computed from drafts.text and
-- edits.final_text when /learn needs them. No gates, no caps, no outcomes,
-- no dates in the pipeline.
-- Apply with:  sqlite3 db/outreach.sqlite < db/schema.sql

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '9');

-- ===========================================================================
-- OUTREACH LAYER
-- ===========================================================================

-- contacts: one row per person. Identity is the normalized URL, nothing else.
CREATE TABLE IF NOT EXISTS contacts (
    id            INTEGER PRIMARY KEY,
    linkedin_url  TEXT NOT NULL UNIQUE,          -- normalized: lowercase, https, no www, no query, no fragment, no trailing slash
    name          TEXT NOT NULL,
    headline      TEXT,
    company       TEXT,
    title         TEXT,
    status        TEXT NOT NULL DEFAULT 'queued'
                  CHECK (status IN ('queued', 'drafted', 'approved', 'sent')),
    profile_json  TEXT NOT NULL,                 -- normalized shape, posts included (DESIGN §6)
    captured_at   TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts (status);

-- sends: one per contact. The text sent is edits.final_text — if you changed
-- the note in LinkedIn's box, /send writes that back to the edit first.
CREATE TABLE IF NOT EXISTS sends (
    id         INTEGER PRIMARY KEY,
    contact_id INTEGER NOT NULL UNIQUE REFERENCES contacts(id) ON DELETE CASCADE,
    edit_id    INTEGER NOT NULL,                 -- edits.id; soft reference across layers
    sent_at    TEXT NOT NULL
);

-- ===========================================================================
-- LEARN CORE
-- ===========================================================================

-- constitutions: every rendered version of constitution.md. The file is a
-- cache of the render; this table is the history. sha = sha256(text)[:16].
CREATE TABLE IF NOT EXISTS constitutions (
    sha          TEXT PRIMARY KEY,
    domain       TEXT NOT NULL DEFAULT 'outreach',
    version      INTEGER NOT NULL,
    text         TEXT NOT NULL,
    parent_sha   TEXT REFERENCES constitutions(sha),
    learn_run_id INTEGER,                        -- learn_runs.id; NULL for /init and /prefer renders
    created_at   TEXT NOT NULL,
    UNIQUE (domain, version)
);

-- drafts: a context may be drafted more than once (/draft --redraft); the
-- newest row is the live one. constitution_sha is the provenance. No dates.
CREATE TABLE IF NOT EXISTS drafts (
    id                INTEGER PRIMARY KEY,
    domain            TEXT NOT NULL DEFAULT 'outreach',
    context_ref       TEXT NOT NULL,             -- 'contact:17', 'email:msg-abc', ...
    contact_id        INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
    text              TEXT NOT NULL,
    sources_json      TEXT NOT NULL DEFAULT '[]',-- what the draft drew on; stored, not shown
    constitution_sha  TEXT NOT NULL REFERENCES constitutions(sha),
    created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_drafts_ctx     ON drafts (domain, context_ref);
CREATE INDEX IF NOT EXISTS idx_drafts_contact ON drafts (contact_id);

-- edits: one per reviewed context. draft_id NULL when FINAL was written from
-- scratch or imported from past notes (edit_distance = 1.0). final_text is
-- the note as actually sent; /send updates it if you edited in LinkedIn's box.
CREATE TABLE IF NOT EXISTS edits (
    id                 INTEGER PRIMARY KEY,
    domain             TEXT NOT NULL DEFAULT 'outreach',
    context_ref        TEXT NOT NULL,            -- 'contact:17' or 'past:<n>'
    contact_id         INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
    draft_id           INTEGER REFERENCES drafts(id),
    final_text         TEXT NOT NULL,
    edit_distance      REAL NOT NULL,            -- 1 - difflib ratio vs draft, in [0,1]; 0 untouched, 1.0 from scratch
    reason_text        TEXT,                     -- your review note, verbatim ("wrong: ..." included)
    constitution_sha   TEXT NOT NULL REFERENCES constitutions(sha),
    reviewed_at        TEXT NOT NULL,
    learned_at         TEXT,                     -- NULL until consumed by /learn
    UNIQUE (domain, context_ref)
);
CREATE INDEX IF NOT EXISTS idx_edits_unlearned ON edits (domain, learned_at) WHERE learned_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_edits_const     ON edits (domain, constitution_sha);
CREATE INDEX IF NOT EXISTS idx_edits_contact   ON edits (contact_id);

-- preferences: the single source of truth for style. The constitution is a
-- render of the active rows. `condition` is a natural-language applicability
-- clause; NULL = always. Lifecycle (script-enforced):
--   candidate -> active   when support_count >= 3 AND support_count > 2 * contradiction_count
--   active    -> retired  when contradiction_count >= support_count
-- Non-learned rows start active with a small prior so edits can disprove them.
CREATE TABLE IF NOT EXISTS preferences (
    id                  INTEGER PRIMARY KEY,
    domain              TEXT NOT NULL DEFAULT 'outreach',
    statement           TEXT NOT NULL,           -- imperative, one sentence, testable against a draft
    condition           TEXT,
    source              TEXT NOT NULL
                        CHECK (source IN ('seed', 'history', 'manual', 'imported', 'learned')),
    status              TEXT NOT NULL DEFAULT 'candidate'
                        CHECK (status IN ('candidate', 'active', 'retired')),
    support_count       INTEGER NOT NULL DEFAULT 0,
    contradiction_count INTEGER NOT NULL DEFAULT 0,
    evidence_edit_ids   TEXT NOT NULL DEFAULT '[]', -- JSON array of edits.id
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    retired_reason      TEXT
);
CREATE INDEX IF NOT EXISTS idx_prefs_lookup ON preferences (domain, status);

CREATE TABLE IF NOT EXISTS learn_runs (
    id                    INTEGER PRIMARY KEY,
    domain                TEXT NOT NULL DEFAULT 'outreach',
    ran_at                TEXT NOT NULL,
    edits_consumed        INTEGER NOT NULL,
    constitution_sha_from TEXT NOT NULL,
    constitution_sha_to   TEXT NOT NULL,
    prefs_created         INTEGER NOT NULL DEFAULT 0,
    prefs_activated       INTEGER NOT NULL DEFAULT 0,
    prefs_retired         INTEGER NOT NULL DEFAULT 0,
    summary               TEXT                   -- shareable changelog, markdown
);

-- ===========================================================================
-- VIEWS
-- ===========================================================================

CREATE VIEW IF NOT EXISTS v_learning_curve AS
SELECT
    e.domain,
    c.version,
    e.constitution_sha,
    MIN(e.reviewed_at)                      AS first_used,
    COUNT(*)                                AS n_edits,
    ROUND(AVG(e.edit_distance), 3)          AS mean_edit_distance,
    ROUND(AVG(CASE WHEN e.edit_distance = 0 THEN 1.0 ELSE 0.0 END), 3) AS untouched_rate
FROM edits e
JOIN constitutions c ON c.sha = e.constitution_sha
WHERE e.draft_id IS NOT NULL
GROUP BY e.domain, c.version
ORDER BY e.domain, c.version;

CREATE VIEW IF NOT EXISTS v_learning_curve_daily AS
SELECT
    domain,
    substr(reviewed_at, 1, 10)              AS day,
    COUNT(*)                                AS n_edits,
    ROUND(AVG(edit_distance), 3)            AS mean_edit_distance
FROM edits
WHERE draft_id IS NOT NULL
GROUP BY domain, day
ORDER BY domain, day;

-- Unlearned edits with their draft text; /learn diffs these at read time.
CREATE VIEW IF NOT EXISTS v_unlearned AS
SELECT e.*, d.text AS draft_text
FROM edits e
LEFT JOIN drafts d ON d.id = e.draft_id
WHERE e.learned_at IS NULL
ORDER BY e.domain, e.reviewed_at;

-- Exemplars for drafting: (draft -> final, note) pairs, newest first.
CREATE VIEW IF NOT EXISTS v_exemplars AS
SELECT e.id AS edit_id, e.domain, e.context_ref,
       d.text AS draft_text, e.final_text, e.reason_text, e.reviewed_at
FROM edits e
LEFT JOIN drafts d ON d.id = e.draft_id
ORDER BY e.reviewed_at DESC;

-- The review queue: newest draft per context that has no edits row yet.
-- queue.py renders queue.md from exactly this.
CREATE VIEW IF NOT EXISTS v_queue AS
SELECT d.*
FROM drafts d
WHERE d.id = (SELECT MAX(id) FROM drafts x WHERE x.domain = d.domain AND x.context_ref = d.context_ref)
  AND NOT EXISTS (SELECT 1 FROM edits e WHERE e.domain = d.domain AND e.context_ref = d.context_ref)
ORDER BY d.created_at;

CREATE VIEW IF NOT EXISTS v_pipeline AS
SELECT status, COUNT(*) AS n FROM contacts GROUP BY status;

CREATE VIEW IF NOT EXISTS v_sends_this_week AS
SELECT COUNT(*) AS n FROM sends
WHERE julianday('now') - julianday(sent_at) <= 7;

-- ===========================================================================
-- TRIGGERS: outreach status transitions; fire only when contact_id is set.
-- ===========================================================================
CREATE TRIGGER IF NOT EXISTS trg_drafts_status AFTER INSERT ON drafts
WHEN NEW.contact_id IS NOT NULL
BEGIN
    UPDATE contacts SET status = 'drafted', updated_at = NEW.created_at
    WHERE id = NEW.contact_id AND status = 'queued';
END;

CREATE TRIGGER IF NOT EXISTS trg_edits_status AFTER INSERT ON edits
WHEN NEW.contact_id IS NOT NULL
BEGIN
    UPDATE contacts SET status = 'approved', updated_at = NEW.reviewed_at
    WHERE id = NEW.contact_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_sends_status AFTER INSERT ON sends
BEGIN
    UPDATE contacts SET status = 'sent', updated_at = NEW.sent_at
    WHERE id = NEW.contact_id;
END;

-- ===========================================================================
-- CONSUMER -> CORE BRIDGE
-- ===========================================================================
-- v_context_labels: the one thing the learn core may know about a context, so
-- /learn can show "Senior PM, Google" next to an edit. The core joins this by
-- (domain, context_ref) and never reads contact_id. A second consumer defines
-- its own view with the same name and columns.
CREATE VIEW IF NOT EXISTS v_context_labels AS
SELECT 'outreach'        AS domain,
       'contact:' || id  AS context_ref,
       NULLIF(COALESCE(headline,
                       TRIM(COALESCE(title, '') || ', ' || COALESCE(company, ''), ', ')),
              '')        AS label
FROM contacts;
