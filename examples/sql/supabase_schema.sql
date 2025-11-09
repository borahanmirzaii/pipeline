-- Supabase Schema for Asset Metadata and Management
-- Enable required extensions

-- Enable pgvector for semantic search with embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable pg_trgm for fuzzy text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Main asset metadata table
CREATE TABLE IF NOT EXISTS asset_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('pexels', 'pixabay', 'unsplash', 'freesound', 'giphy', 'other')),
    type TEXT NOT NULL CHECK (type IN ('image', 'video', 'audio', 'gif')),
    url TEXT NOT NULL,
    thumbnail_url TEXT,
    title TEXT,
    description TEXT,
    tags TEXT[] DEFAULT '{}',
    license TEXT DEFAULT 'Royalty-free',

    -- Technical specifications
    duration INTEGER, -- Duration in seconds (for video/audio)
    width INTEGER,
    height INTEGER,
    file_size BIGINT,
    file_format TEXT,

    -- Search and classification
    search_keywords TEXT[] DEFAULT '{}',
    embedding VECTOR(1536), -- For semantic search with OpenAI embeddings

    -- Metadata and timestamps
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Usage tracking
    view_count INTEGER DEFAULT 0,
    download_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_asset_source_type ON asset_metadata(source, type);
CREATE INDEX IF NOT EXISTS idx_asset_type ON asset_metadata(type);
CREATE INDEX IF NOT EXISTS idx_asset_tags ON asset_metadata USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_asset_keywords ON asset_metadata USING GIN(search_keywords);
CREATE INDEX IF NOT EXISTS idx_asset_created ON asset_metadata(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_asset_id ON asset_metadata(asset_id);

-- Vector index for semantic search (using IVFFlat)
CREATE INDEX IF NOT EXISTS idx_asset_embedding
ON asset_metadata
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Full-text search index
CREATE INDEX IF NOT EXISTS idx_asset_fts
ON asset_metadata
USING GIN(to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(description, '')));

-- Trigram index for fuzzy search on title
CREATE INDEX IF NOT EXISTS idx_asset_title_trgm
ON asset_metadata
USING GIN(title gin_trgm_ops);

-- User collections for organizing assets
CREATE TABLE IF NOT EXISTS asset_collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_user_collection_name UNIQUE(user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_collection_user ON asset_collections(user_id);
CREATE INDEX IF NOT EXISTS idx_collection_public ON asset_collections(is_public) WHERE is_public = TRUE;

-- Many-to-many relationship between collections and assets
CREATE TABLE IF NOT EXISTS collection_assets (
    collection_id UUID REFERENCES asset_collections(id) ON DELETE CASCADE,
    asset_id UUID REFERENCES asset_metadata(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT,

    PRIMARY KEY (collection_id, asset_id)
);

CREATE INDEX IF NOT EXISTS idx_collection_assets_collection ON collection_assets(collection_id);
CREATE INDEX IF NOT EXISTS idx_collection_assets_asset ON collection_assets(asset_id);

-- Project assets table for tracking assets used in specific projects
CREATE TABLE IF NOT EXISTS project_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id TEXT NOT NULL,
    asset_id UUID REFERENCES asset_metadata(id) ON DELETE CASCADE,
    used_in TEXT, -- e.g., "video_intro", "background_music"
    attribution_text TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_project_asset UNIQUE(project_id, asset_id, used_in)
);

CREATE INDEX IF NOT EXISTS idx_project_assets_project ON project_assets(project_id);
CREATE INDEX IF NOT EXISTS idx_project_assets_asset ON project_assets(asset_id);

-- Asset usage analytics table
CREATE TABLE IF NOT EXISTS asset_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID REFERENCES asset_metadata(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('view', 'download', 'share', 'collection_add')),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    project_id TEXT,
    metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analytics_asset ON asset_analytics(asset_id);
CREATE INDEX IF NOT EXISTS idx_analytics_type ON asset_analytics(event_type);
CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON asset_analytics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_user ON asset_analytics(user_id) WHERE user_id IS NOT NULL;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_asset_metadata_updated_at
    BEFORE UPDATE ON asset_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_asset_collections_updated_at
    BEFORE UPDATE ON asset_collections
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function for semantic search using embeddings
CREATE OR REPLACE FUNCTION search_assets_by_embedding(
    query_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 10,
    asset_type_filter TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    asset_id TEXT,
    source TEXT,
    type TEXT,
    url TEXT,
    title TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        am.id,
        am.asset_id,
        am.source,
        am.type,
        am.url,
        am.title,
        1 - (am.embedding <=> query_embedding) AS similarity
    FROM asset_metadata am
    WHERE
        (asset_type_filter IS NULL OR am.type = asset_type_filter)
        AND am.embedding IS NOT NULL
        AND 1 - (am.embedding <=> query_embedding) > match_threshold
    ORDER BY am.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- Function for full-text search
CREATE OR REPLACE FUNCTION search_assets_by_text(
    search_query TEXT,
    asset_type_filter TEXT DEFAULT NULL,
    match_count INT DEFAULT 20
)
RETURNS TABLE (
    id UUID,
    asset_id TEXT,
    source TEXT,
    type TEXT,
    url TEXT,
    title TEXT,
    description TEXT,
    rank FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        am.id,
        am.asset_id,
        am.source,
        am.type,
        am.url,
        am.title,
        am.description,
        ts_rank(
            to_tsvector('english', COALESCE(am.title, '') || ' ' || COALESCE(am.description, '')),
            plainto_tsquery('english', search_query)
        ) AS rank
    FROM asset_metadata am
    WHERE
        (asset_type_filter IS NULL OR am.type = asset_type_filter)
        AND to_tsvector('english', COALESCE(am.title, '') || ' ' || COALESCE(am.description, ''))
            @@ plainto_tsquery('english', search_query)
    ORDER BY rank DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- Function to track asset access
CREATE OR REPLACE FUNCTION track_asset_access(
    p_asset_id UUID,
    p_event_type TEXT,
    p_user_id UUID DEFAULT NULL,
    p_project_id TEXT DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    -- Insert analytics event
    INSERT INTO asset_analytics (asset_id, event_type, user_id, project_id)
    VALUES (p_asset_id, p_event_type, p_user_id, p_project_id);

    -- Update asset metadata counters
    IF p_event_type = 'view' THEN
        UPDATE asset_metadata
        SET view_count = view_count + 1,
            last_accessed = NOW()
        WHERE id = p_asset_id;
    ELSIF p_event_type = 'download' THEN
        UPDATE asset_metadata
        SET download_count = download_count + 1,
            last_accessed = NOW()
        WHERE id = p_asset_id;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Row Level Security (RLS) Policies
ALTER TABLE asset_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE collection_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_analytics ENABLE ROW LEVEL SECURITY;

-- Asset metadata: Public read, authenticated write
CREATE POLICY "Assets are viewable by everyone"
    ON asset_metadata FOR SELECT
    USING (true);

CREATE POLICY "Assets are insertable by authenticated users"
    ON asset_metadata FOR INSERT
    WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Assets are updatable by authenticated users"
    ON asset_metadata FOR UPDATE
    USING (auth.role() = 'authenticated');

-- Collections: Users can only manage their own collections
CREATE POLICY "Users can view their own collections"
    ON asset_collections FOR SELECT
    USING (auth.uid() = user_id OR is_public = true);

CREATE POLICY "Users can insert their own collections"
    ON asset_collections FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own collections"
    ON asset_collections FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own collections"
    ON asset_collections FOR DELETE
    USING (auth.uid() = user_id);

-- Collection assets: Inherit from collections
CREATE POLICY "Users can view collection assets"
    ON collection_assets FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM asset_collections
            WHERE id = collection_id
            AND (user_id = auth.uid() OR is_public = true)
        )
    );

CREATE POLICY "Users can manage their collection assets"
    ON collection_assets FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM asset_collections
            WHERE id = collection_id
            AND user_id = auth.uid()
        )
    );

-- Analytics: Users can view their own analytics
CREATE POLICY "Users can view their own analytics"
    ON asset_analytics FOR SELECT
    USING (user_id = auth.uid() OR auth.role() = 'service_role');

CREATE POLICY "Analytics can be inserted by anyone"
    ON asset_analytics FOR INSERT
    WITH CHECK (true);

-- Grant permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT ON asset_metadata TO anon, authenticated;
GRANT ALL ON asset_metadata TO authenticated;
GRANT ALL ON asset_collections TO authenticated;
GRANT ALL ON collection_assets TO authenticated;
GRANT ALL ON project_assets TO authenticated;
GRANT ALL ON asset_analytics TO anon, authenticated;

-- Create view for popular assets
CREATE OR REPLACE VIEW popular_assets AS
SELECT
    am.*,
    am.view_count + (am.download_count * 2) AS popularity_score
FROM asset_metadata am
WHERE am.view_count > 0 OR am.download_count > 0
ORDER BY popularity_score DESC;

-- Create view for recent assets
CREATE OR REPLACE VIEW recent_assets AS
SELECT *
FROM asset_metadata
ORDER BY created_at DESC
LIMIT 100;

-- Comments
COMMENT ON TABLE asset_metadata IS 'Main table storing metadata for all cached assets';
COMMENT ON TABLE asset_collections IS 'User-created collections for organizing assets';
COMMENT ON TABLE collection_assets IS 'Junction table linking collections to assets';
COMMENT ON TABLE project_assets IS 'Tracks which assets are used in which projects';
COMMENT ON TABLE asset_analytics IS 'Analytics and usage tracking for assets';

COMMENT ON FUNCTION search_assets_by_embedding IS 'Semantic search using vector embeddings';
COMMENT ON FUNCTION search_assets_by_text IS 'Full-text search on asset titles and descriptions';
COMMENT ON FUNCTION track_asset_access IS 'Track and record asset access events';
