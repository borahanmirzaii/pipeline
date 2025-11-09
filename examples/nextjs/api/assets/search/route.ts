/**
 * Next.js API Route for Asset Search
 * Integrates with Supabase for caching and multiple asset APIs
 */

import { createClient } from '@supabase/supabase-js';
import { NextRequest, NextResponse } from 'next/server';

// Initialize Supabase client
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// Asset source interfaces
interface AssetResult {
  id: string;
  source: string;
  type: string;
  url: string;
  thumbnail?: string;
  title?: string;
  photographer?: string;
  duration?: number;
  width?: number;
  height?: number;
  tags?: string[];
  metadata?: Record<string, any>;
}

interface SearchRequest {
  query: string;
  type: 'image' | 'video' | 'audio' | 'gif';
  sources?: string[];
  limit?: number;
}

/**
 * POST /api/assets/search
 * Search for assets across multiple sources with caching
 */
export async function POST(request: NextRequest) {
  try {
    const body: SearchRequest = await request.json();
    const { query, type, sources = ['pexels', 'pixabay'], limit = 20 } = body;

    if (!query || !type) {
      return NextResponse.json(
        { error: 'Query and type are required' },
        { status: 400 }
      );
    }

    // First, check Supabase cache
    const { data: cachedAssets, error: cacheError } = await supabase
      .from('asset_metadata')
      .select('*')
      .contains('search_keywords', [query])
      .eq('type', type)
      .limit(limit);

    if (cachedAssets && cachedAssets.length > 0) {
      return NextResponse.json({
        cached: true,
        query,
        type,
        count: cachedAssets.length,
        results: cachedAssets.map(normalizeAsset),
      });
    }

    // If not cached, fetch from external APIs
    const results = await fetchFromAPIs(query, type, sources, limit);

    // Store in Supabase for future queries
    if (results.length > 0) {
      await storeAssets(results, query);
    }

    return NextResponse.json({
      cached: false,
      query,
      type,
      sources,
      count: results.length,
      results,
    });
  } catch (error) {
    console.error('Asset search error:', error);
    return NextResponse.json(
      { error: 'Failed to search assets', details: String(error) },
      { status: 500 }
    );
  }
}

/**
 * Fetch assets from multiple external APIs in parallel
 */
async function fetchFromAPIs(
  query: string,
  type: string,
  sources: string[],
  limit: number
): Promise<AssetResult[]> {
  const results: AssetResult[] = [];

  // Parallel API calls for better performance
  const promises = sources.map(async (source) => {
    try {
      switch (source) {
        case 'pexels':
          return type === 'image'
            ? await fetchPexelsImages(query, limit)
            : await fetchPexelsVideos(query, limit);
        case 'pixabay':
          return type === 'image'
            ? await fetchPixabayImages(query, limit)
            : await fetchPixabayVideos(query, limit);
        case 'unsplash':
          return type === 'image' ? await fetchUnsplashImages(query, limit) : [];
        case 'giphy':
          return type === 'gif' ? await fetchGiphyGifs(query, limit) : [];
        default:
          return [];
      }
    } catch (error) {
      console.error(`Error fetching from ${source}:`, error);
      return [];
    }
  });

  const apiResults = await Promise.all(promises);
  return apiResults.flat();
}

/**
 * Fetch images from Pexels API
 */
async function fetchPexelsImages(
  query: string,
  limit: number
): Promise<AssetResult[]> {
  const response = await fetch(
    `https://api.pexels.com/v1/search?query=${encodeURIComponent(query)}&per_page=${limit}`,
    {
      headers: {
        Authorization: process.env.PEXELS_API_KEY!,
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Pexels API error: ${response.statusText}`);
  }

  const data = await response.json();

  return data.photos.map((photo: any) => ({
    id: photo.id.toString(),
    source: 'pexels',
    type: 'image',
    url: photo.src.original,
    thumbnail: photo.src.medium,
    title: photo.alt || query,
    photographer: photo.photographer,
    width: photo.width,
    height: photo.height,
    metadata: {
      photographer_url: photo.photographer_url,
      avg_color: photo.avg_color,
    },
  }));
}

/**
 * Fetch videos from Pexels API
 */
async function fetchPexelsVideos(
  query: string,
  limit: number
): Promise<AssetResult[]> {
  const response = await fetch(
    `https://api.pexels.com/videos/search?query=${encodeURIComponent(query)}&per_page=${limit}`,
    {
      headers: {
        Authorization: process.env.PEXELS_API_KEY!,
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Pexels Video API error: ${response.statusText}`);
  }

  const data = await response.json();

  return data.videos.map((video: any) => ({
    id: video.id.toString(),
    source: 'pexels',
    type: 'video',
    url: video.video_files[0]?.link || '',
    thumbnail: video.image,
    title: query,
    photographer: video.user.name,
    duration: video.duration,
    width: video.width,
    height: video.height,
    metadata: {
      user_url: video.user.url,
    },
  }));
}

/**
 * Fetch images from Pixabay API
 */
async function fetchPixabayImages(
  query: string,
  limit: number
): Promise<AssetResult[]> {
  const response = await fetch(
    `https://pixabay.com/api/?key=${process.env.PIXABAY_API_KEY}&q=${encodeURIComponent(query)}&per_page=${limit}`
  );

  if (!response.ok) {
    throw new Error(`Pixabay API error: ${response.statusText}`);
  }

  const data = await response.json();

  return data.hits.map((hit: any) => ({
    id: hit.id.toString(),
    source: 'pixabay',
    type: 'image',
    url: hit.largeImageURL,
    thumbnail: hit.previewURL,
    title: hit.tags,
    photographer: hit.user,
    width: hit.imageWidth,
    height: hit.imageHeight,
    tags: hit.tags.split(', '),
    metadata: {
      user_id: hit.user_id,
      likes: hit.likes,
      downloads: hit.downloads,
    },
  }));
}

/**
 * Fetch videos from Pixabay API
 */
async function fetchPixabayVideos(
  query: string,
  limit: number
): Promise<AssetResult[]> {
  const response = await fetch(
    `https://pixabay.com/api/videos/?key=${process.env.PIXABAY_API_KEY}&q=${encodeURIComponent(query)}&per_page=${limit}`
  );

  if (!response.ok) {
    throw new Error(`Pixabay Video API error: ${response.statusText}`);
  }

  const data = await response.json();

  return data.hits.map((hit: any) => ({
    id: hit.id.toString(),
    source: 'pixabay',
    type: 'video',
    url: hit.videos.large.url,
    thumbnail: hit.userImageURL,
    title: hit.tags,
    photographer: hit.user,
    duration: hit.duration,
    width: hit.videos.large.width,
    height: hit.videos.large.height,
    tags: hit.tags.split(', '),
    metadata: {
      user_id: hit.user_id,
    },
  }));
}

/**
 * Fetch images from Unsplash API
 */
async function fetchUnsplashImages(
  query: string,
  limit: number
): Promise<AssetResult[]> {
  const response = await fetch(
    `https://api.unsplash.com/search/photos?query=${encodeURIComponent(query)}&per_page=${limit}`,
    {
      headers: {
        Authorization: `Client-ID ${process.env.UNSPLASH_ACCESS_KEY}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Unsplash API error: ${response.statusText}`);
  }

  const data = await response.json();

  return data.results.map((photo: any) => ({
    id: photo.id,
    source: 'unsplash',
    type: 'image',
    url: photo.urls.full,
    thumbnail: photo.urls.small,
    title: photo.description || photo.alt_description || query,
    photographer: photo.user.name,
    width: photo.width,
    height: photo.height,
    metadata: {
      photographer_url: photo.user.links.html,
      likes: photo.likes,
      description: photo.description,
    },
  }));
}

/**
 * Fetch GIFs from Giphy API
 */
async function fetchGiphyGifs(
  query: string,
  limit: number
): Promise<AssetResult[]> {
  const response = await fetch(
    `https://api.giphy.com/v1/gifs/search?api_key=${process.env.GIPHY_API_KEY}&q=${encodeURIComponent(query)}&limit=${limit}&rating=g`
  );

  if (!response.ok) {
    throw new Error(`Giphy API error: ${response.statusText}`);
  }

  const data = await response.json();

  return data.data.map((gif: any) => ({
    id: gif.id,
    source: 'giphy',
    type: 'gif',
    url: gif.images.original.url,
    thumbnail: gif.images.preview_gif.url,
    title: gif.title,
    width: parseInt(gif.images.original.width),
    height: parseInt(gif.images.original.height),
    metadata: {
      rating: gif.rating,
      trending_datetime: gif.trending_datetime,
    },
  }));
}

/**
 * Store assets in Supabase for caching
 */
async function storeAssets(
  assets: AssetResult[],
  query: string
): Promise<void> {
  try {
    const { error } = await supabase.from('asset_metadata').upsert(
      assets.map((asset) => ({
        asset_id: `${asset.source}_${asset.id}`,
        source: asset.source,
        type: asset.type,
        url: asset.url,
        thumbnail_url: asset.thumbnail,
        title: asset.title || query,
        tags: asset.tags || [],
        search_keywords: [query],
        width: asset.width,
        height: asset.height,
        duration: asset.duration,
        metadata: asset.metadata || {},
      })),
      { onConflict: 'asset_id' }
    );

    if (error) {
      console.error('Failed to cache assets:', error);
    }
  } catch (error) {
    console.error('Error storing assets:', error);
  }
}

/**
 * Normalize asset from Supabase format
 */
function normalizeAsset(dbAsset: any): AssetResult {
  return {
    id: dbAsset.asset_id,
    source: dbAsset.source,
    type: dbAsset.type,
    url: dbAsset.url,
    thumbnail: dbAsset.thumbnail_url,
    title: dbAsset.title,
    width: dbAsset.width,
    height: dbAsset.height,
    duration: dbAsset.duration,
    tags: dbAsset.tags,
    metadata: dbAsset.metadata,
  };
}
