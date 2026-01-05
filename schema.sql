-- ============================================
-- MAHAVIHARA DATABASE SCHEMA
-- Run this in Supabase SQL Editor
-- ============================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- SUBJECTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS subjects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed subjects
INSERT INTO subjects (name, display_name) VALUES
    ('physics', 'Physics'),
    ('chemistry', 'Chemistry'),
    ('mathematics', 'Mathematics')
ON CONFLICT (name) DO NOTHING;

-- ============================================
-- USERS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number TEXT NOT NULL UNIQUE,
    name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    current_streak INTEGER DEFAULT 0,
    best_streak INTEGER DEFAULT 0,
    last_active_at TIMESTAMPTZ,
    last_message_at TIMESTAMPTZ,
    last_drill_at TIMESTAMPTZ,
    preferred_time TEXT DEFAULT '18:00',
    timezone TEXT DEFAULT 'Asia/Kolkata',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for phone lookups
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone_number);

-- ============================================
-- QUESTIONS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option TEXT NOT NULL CHECK (correct_option IN ('A', 'B', 'C', 'D')),
    subject TEXT NOT NULL,
    chapter TEXT,
    topic TEXT,
    difficulty INTEGER DEFAULT 2 CHECK (difficulty >= 1 AND difficulty <= 5),
    source TEXT,
    source_question_id TEXT,
    year INTEGER,
    is_pyq BOOLEAN DEFAULT FALSE,
    solution TEXT,
    hint_1 TEXT,
    hint_2 TEXT,
    hint_3 TEXT,
    content_hash TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for question lookups
CREATE INDEX IF NOT EXISTS idx_questions_subject ON questions(subject);
CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic);
CREATE INDEX IF NOT EXISTS idx_questions_content_hash ON questions(content_hash);

-- ============================================
-- STUDENT MISTAKES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS student_mistakes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    subject TEXT NOT NULL,
    chapter TEXT,
    topic TEXT,
    source_type TEXT DEFAULT 'self_reported',

    -- SM-2 Spaced Repetition fields
    ease_factor FLOAT DEFAULT 2.5,
    interval_days INTEGER DEFAULT 1,
    repetitions INTEGER DEFAULT 0,
    next_review_at TIMESTAMPTZ DEFAULT NOW(),

    -- Progress tracking
    times_drilled INTEGER DEFAULT 0,
    times_correct INTEGER DEFAULT 0,
    is_mastered BOOLEAN DEFAULT FALSE,
    mastered_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for mistake lookups
CREATE INDEX IF NOT EXISTS idx_mistakes_user ON student_mistakes(user_id);
CREATE INDEX IF NOT EXISTS idx_mistakes_next_review ON student_mistakes(next_review_at);
CREATE INDEX IF NOT EXISTS idx_mistakes_mastered ON student_mistakes(is_mastered);

-- ============================================
-- DRILL ATTEMPTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS drill_attempts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mistake_id UUID REFERENCES student_mistakes(id) ON DELETE SET NULL,
    question_id UUID REFERENCES questions(id) ON DELETE SET NULL,

    user_answer TEXT,
    is_correct BOOLEAN,
    hints_used INTEGER DEFAULT 0,
    time_taken_seconds INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for drill history
CREATE INDEX IF NOT EXISTS idx_drills_user ON drill_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_drills_created ON drill_attempts(created_at);

-- ============================================
-- CONVERSATION STATES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS conversation_states (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    state TEXT NOT NULL DEFAULT 'IDLE',
    context JSONB DEFAULT '{}',
    current_mistake_id UUID REFERENCES student_mistakes(id),
    current_question_id UUID REFERENCES questions(id),
    hints_given INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraint - one state per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_conversation_user ON conversation_states(user_id);

-- ============================================
-- MESSAGE HISTORY TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS message_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    message_text TEXT,
    message_type TEXT DEFAULT 'text',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for message history
CREATE INDEX IF NOT EXISTS idx_messages_user ON message_history(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON message_history(created_at);

-- ============================================
-- NUDGE LOG TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS nudge_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    nudge_type TEXT NOT NULL,
    message_sent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for nudge history
CREATE INDEX IF NOT EXISTS idx_nudges_user ON nudge_log(user_id);

-- ============================================
-- ROW LEVEL SECURITY (Optional)
-- ============================================
-- Enable RLS on tables if needed
-- ALTER TABLE users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE student_mistakes ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE drill_attempts ENABLE ROW LEVEL SECURITY;

-- ============================================
-- UPDATED_AT TRIGGER FUNCTION
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables with updated_at
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_mistakes_updated_at ON student_mistakes;
CREATE TRIGGER update_mistakes_updated_at
    BEFORE UPDATE ON student_mistakes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_conversation_updated_at ON conversation_states;
CREATE TRIGGER update_conversation_updated_at
    BEFORE UPDATE ON conversation_states
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
