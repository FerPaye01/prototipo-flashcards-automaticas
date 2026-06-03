-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Table for Session management
CREATE TABLE IF NOT EXISTS session_metadata (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mode VARCHAR(50),
    meta_data JSONB -- Storage for deck names, prefixes, etc.
);

-- Table for generated Flashcards
CREATE TABLE IF NOT EXISTS generated_flashcards (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) REFERENCES session_metadata(session_id),
    card_type VARCHAR(50),
    front TEXT,
    back TEXT,
    options JSONB, -- For multiple choice
    tags VARCHAR(255)[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_status BOOLEAN DEFAULT FALSE,
    embedding vector(768) -- Ajustar según GEMINI_EMBEDDING_DIM
);

-- Table for document chunks (for RAG/LangChain)
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) REFERENCES session_metadata(session_id),
    content TEXT,
    embedding vector(768), -- Ajustar según GEMINI_EMBEDDING_DIM
    meta_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
