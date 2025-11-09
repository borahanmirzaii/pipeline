/**
 * Asset Gallery Component
 * Responsive gallery with optimized image loading and search
 */

'use client';

import { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';

interface Asset {
  id: string;
  url: string;
  thumbnail?: string;
  title: string;
  source: string;
  type: string;
  photographer?: string;
  duration?: number;
  width?: number;
  height?: number;
  tags?: string[];
  metadata?: Record<string, any>;
}

interface AssetGalleryProps {
  query: string;
  type?: 'image' | 'video' | 'audio' | 'gif';
  sources?: string[];
  limit?: number;
  onAssetSelect?: (asset: Asset) => void;
}

export default function AssetGallery({
  query,
  type = 'image',
  sources = ['pexels', 'pixabay', 'unsplash'],
  limit = 30,
  onAssetSelect,
}: AssetGalleryProps) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cached, setCached] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);

  // Search for assets
  const searchAssets = useCallback(async () => {
    if (!query) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/assets/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          type,
          sources,
          limit,
        }),
      });

      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`);
      }

      const data = await response.json();
      setAssets(data.results);
      setCached(data.cached);
    } catch (err) {
      console.error('Search failed:', err);
      setError(err instanceof Error ? err.message : 'Failed to search assets');
    } finally {
      setLoading(false);
    }
  }, [query, type, sources, limit]);

  // Search when query changes
  useEffect(() => {
    if (query) {
      searchAssets();
    }
  }, [query, searchAssets]);

  // Handle asset selection
  const handleAssetClick = (asset: Asset) => {
    setSelectedAsset(asset);
    onAssetSelect?.(asset);
  };

  // Close modal
  const handleCloseModal = () => {
    setSelectedAsset(null);
  };

  // Render loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
          <p className="mt-4 text-gray-600">Searching for assets...</p>
        </div>
      </div>
    );
  }

  // Render error state
  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="text-red-500 text-5xl mb-4">⚠️</div>
          <h3 className="text-xl font-semibold text-gray-800 mb-2">
            Search Failed
          </h3>
          <p className="text-gray-600">{error}</p>
          <button
            onClick={searchAssets}
            className="mt-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Render empty state
  if (!query) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center text-gray-500">
          <div className="text-6xl mb-4">🔍</div>
          <p>Enter a search query to find assets</p>
        </div>
      </div>
    );
  }

  // Render gallery
  return (
    <>
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-800">
              {assets.length} {type}s found
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              {cached ? (
                <span className="flex items-center gap-1">
                  <span className="text-green-500">●</span> Loaded from cache
                </span>
              ) : (
                <span className="flex items-center gap-1">
                  <span className="text-blue-500">●</span> Fresh results from{' '}
                  {sources.join(', ')}
                </span>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* Gallery Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {assets.map((asset) => (
          <AssetCard
            key={asset.id}
            asset={asset}
            onClick={() => handleAssetClick(asset)}
          />
        ))}
      </div>

      {/* Asset Detail Modal */}
      {selectedAsset && (
        <AssetModal asset={selectedAsset} onClose={handleCloseModal} />
      )}
    </>
  );
}

/**
 * Individual Asset Card Component
 */
function AssetCard({
  asset,
  onClick,
}: {
  asset: Asset;
  onClick: () => void;
}) {
  const imageUrl = asset.thumbnail || asset.url;
  const showDuration = asset.type === 'video' && asset.duration;

  return (
    <div
      className="relative aspect-square overflow-hidden rounded-lg bg-gray-100 cursor-pointer group"
      onClick={onClick}
    >
      {/* Image */}
      <Image
        src={imageUrl}
        alt={asset.title}
        fill
        className="object-cover transition-transform duration-300 group-hover:scale-110"
        sizes="(max-width: 768px) 50vw, (max-width: 1200px) 33vw, 20vw"
        loading="lazy"
        unoptimized={asset.source === 'giphy'} // GIFs need to be unoptimized
      />

      {/* Duration Badge (for videos) */}
      {showDuration && (
        <div className="absolute top-2 right-2 bg-black/70 text-white text-xs px-2 py-1 rounded">
          {formatDuration(asset.duration!)}
        </div>
      )}

      {/* Overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300">
        <div className="absolute bottom-0 left-0 right-0 p-3">
          <p className="text-white text-sm font-medium truncate">
            {asset.title}
          </p>
          <p className="text-white/80 text-xs truncate">
            {asset.photographer || asset.source}
          </p>
        </div>
      </div>

      {/* Source Badge */}
      <div className="absolute top-2 left-2 bg-white/90 text-gray-700 text-xs px-2 py-1 rounded font-medium">
        {asset.source}
      </div>
    </div>
  );
}

/**
 * Asset Detail Modal Component
 */
function AssetModal({
  asset,
  onClose,
}: {
  asset: Asset;
  onClose: () => void;
}) {
  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  // Format attribution
  const getAttribution = () => {
    if (asset.photographer) {
      return `${asset.photographer} on ${asset.source}`;
    }
    return asset.source;
  };

  // Copy URL to clipboard
  const copyUrl = () => {
    navigator.clipboard.writeText(asset.url);
    alert('URL copied to clipboard!');
  };

  return (
    <div
      className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-xl font-bold text-gray-800">{asset.title}</h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Preview Image */}
          <div className="relative w-full aspect-video bg-gray-100 rounded-lg overflow-hidden mb-6">
            <Image
              src={asset.url}
              alt={asset.title}
              fill
              className="object-contain"
              unoptimized={asset.source === 'giphy'}
            />
          </div>

          {/* Details */}
          <div className="space-y-4">
            {/* Attribution */}
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-1">
                Attribution
              </h4>
              <p className="text-gray-600">{getAttribution()}</p>
            </div>

            {/* Dimensions */}
            {asset.width && asset.height && (
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-1">
                  Dimensions
                </h4>
                <p className="text-gray-600">
                  {asset.width} × {asset.height} px
                </p>
              </div>
            )}

            {/* Duration */}
            {asset.duration && (
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-1">
                  Duration
                </h4>
                <p className="text-gray-600">{formatDuration(asset.duration)}</p>
              </div>
            )}

            {/* Tags */}
            {asset.tags && asset.tags.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-1">
                  Tags
                </h4>
                <div className="flex flex-wrap gap-2">
                  {asset.tags.map((tag, index) => (
                    <span
                      key={index}
                      className="bg-gray-100 text-gray-700 text-xs px-2 py-1 rounded"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-3 pt-4">
              <a
                href={asset.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-center"
              >
                View Original
              </a>
              <button
                onClick={copyUrl}
                className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
              >
                Copy URL
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Format duration in seconds to MM:SS
 */
function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
