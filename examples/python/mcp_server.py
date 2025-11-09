"""
Model Context Protocol (MCP) Server for Asset Management
Enables AI assistants to search and retrieve royalty-free assets.
"""

import json
from typing import Dict, List, Optional
from datetime import datetime

try:
    from fastmcp import FastMCP
except ImportError:
    print("FastMCP not installed. Install with: pip install fastmcp")
    exit(1)

from asset_api import AssetAPI
from asset_cache import AssetCache

# Initialize MCP server
mcp = FastMCP(name="AssetSearchServer")

# Initialize API and cache clients
api_client = AssetAPI()
cache = AssetCache()


@mcp.tool()
def search_images(
    query: str, sources: Optional[List[str]] = None, limit: int = 15
) -> Dict:
    """
    Search for royalty-free images across multiple sources.

    Args:
        query: Search keywords (e.g., "mountain landscape", "office workspace")
        sources: List of sources to search (pexels, pixabay, unsplash). Default: all
        limit: Maximum number of results per source (default: 15)

    Returns:
        Dictionary with cached status and list of image results
    """
    if sources is None:
        sources = ["pexels", "pixabay", "unsplash"]

    # Check cache first
    cached = cache.get_cached_assets(query, "image")
    if cached and len(cached) >= limit:
        return {
            "cached": True,
            "query": query,
            "count": len(cached[:limit]),
            "results": cached[:limit],
        }

    results = []

    # Fetch from requested sources
    if "pexels" in sources:
        pexels_results = api_client.search_pexels_images(query, per_page=limit)
        results.extend(pexels_results)

    if "pixabay" in sources:
        pixabay_results = api_client.search_pixabay_images(query, per_page=limit)
        results.extend(pixabay_results)

    if "unsplash" in sources:
        unsplash_results = api_client.search_unsplash_images(query, per_page=limit)
        results.extend(unsplash_results)

    # Cache results for future queries
    if results:
        cache.cache_assets(query, results, ttl_hours=24)

    return {
        "cached": False,
        "query": query,
        "sources": sources,
        "count": len(results),
        "results": results,
    }


@mcp.tool()
def search_videos(
    query: str, max_duration: Optional[int] = None, limit: int = 10
) -> Dict:
    """
    Search for royalty-free video clips.

    Args:
        query: Search keywords (e.g., "city timelapse", "nature scenes")
        max_duration: Maximum video duration in seconds (optional)
        limit: Maximum number of results (default: 10)

    Returns:
        Dictionary with cached status and list of video results
    """
    # Check cache first
    cached = cache.get_cached_assets(query, "video")
    if cached:
        # Filter by duration if specified
        if max_duration:
            cached = [v for v in cached if v.get("metadata", {}).get("duration", 0) <= max_duration]

        if cached and len(cached) >= limit:
            return {
                "cached": True,
                "query": query,
                "count": len(cached[:limit]),
                "results": cached[:limit],
            }

    results = []

    # Fetch from sources
    pexels_videos = api_client.search_pexels_videos(query, per_page=limit)
    pixabay_videos = api_client.search_pixabay_videos(query, per_page=limit)

    results.extend(pexels_videos)
    results.extend(pixabay_videos)

    # Filter by duration if specified
    if max_duration:
        results = [v for v in results if v.get("duration", 0) <= max_duration]

    # Cache results
    if results:
        cache.cache_assets(query, results, ttl_hours=24)

    return {
        "cached": False,
        "query": query,
        "max_duration": max_duration,
        "count": len(results[:limit]),
        "results": results[:limit],
    }


@mcp.tool()
def search_audio(
    query: str, min_duration: int = 0, max_duration: int = 300, limit: int = 10
) -> Dict:
    """
    Search for royalty-free audio files and sound effects.

    Args:
        query: Search keywords (e.g., "ambient music", "water sounds")
        min_duration: Minimum audio duration in seconds (default: 0)
        max_duration: Maximum audio duration in seconds (default: 300)
        limit: Maximum number of results (default: 10)

    Returns:
        Dictionary with cached status and list of audio results with licensing info
    """
    # Check cache first
    cached = cache.get_cached_assets(query, "audio")
    if cached:
        # Filter by duration
        cached = [
            a
            for a in cached
            if min_duration <= a.get("metadata", {}).get("duration", 0) <= max_duration
        ]

        if cached and len(cached) >= limit:
            return {
                "cached": True,
                "query": query,
                "count": len(cached[:limit]),
                "results": cached[:limit],
            }

    # Fetch from Freesound
    results = api_client.search_freesound(query, max_results=limit * 2)

    # Filter by duration
    results = [r for r in results if min_duration <= r.get("duration", 0) <= max_duration]

    # Cache results
    if results:
        cache.cache_assets(query, results, ttl_hours=24)

    return {
        "cached": False,
        "query": query,
        "duration_range": {"min": min_duration, "max": max_duration},
        "count": len(results[:limit]),
        "results": results[:limit],
    }


@mcp.tool()
def search_gifs(query: str, limit: int = 20) -> Dict:
    """
    Search for GIF animations.

    Args:
        query: Search keywords (e.g., "happy cat", "celebration")
        limit: Maximum number of results (default: 20, max: 50)

    Returns:
        Dictionary with cached status and list of GIF results
    """
    # Check cache first
    cached = cache.get_cached_assets(query, "gif")
    if cached and len(cached) >= limit:
        return {
            "cached": True,
            "query": query,
            "count": len(cached[:limit]),
            "results": cached[:limit],
        }

    # Fetch from Giphy
    results = api_client.search_giphy_gifs(query, limit=min(limit, 50))

    # Cache results
    if results:
        cache.cache_assets(query, results, ttl_hours=24)

    return {
        "cached": False,
        "query": query,
        "count": len(results),
        "results": results,
    }


@mcp.tool()
def get_asset_by_id(asset_id: str, source: str) -> Optional[Dict]:
    """
    Retrieve a specific asset by its ID and source.

    Args:
        asset_id: The asset's unique identifier
        source: The source platform (pexels, pixabay, unsplash, freesound, giphy)

    Returns:
        Asset dictionary if found in cache, None otherwise
    """
    # This would query the cache for a specific asset
    # Implementation depends on your caching strategy
    return {"message": "Direct asset retrieval not yet implemented"}


@mcp.resource("asset://cache/stats")
def get_cache_stats() -> str:
    """
    Get cache statistics and health metrics.

    Returns:
        JSON string with cache statistics including:
        - Total assets cached
        - Cache hit rate
        - Assets by type and source
        - Expired entries count
    """
    stats = cache.get_cache_stats()
    stats["timestamp"] = datetime.now().isoformat()

    return json.dumps(stats, indent=2)


@mcp.resource("asset://cache/clear")
def clear_cache(asset_type: Optional[str] = None, source: Optional[str] = None) -> str:
    """
    Clear cache entries.

    Args:
        asset_type: Optional filter by asset type (image, video, audio, gif)
        source: Optional filter by source platform

    Returns:
        Confirmation message
    """
    cache.clear_cache(asset_type=asset_type, source=source)

    filters = []
    if asset_type:
        filters.append(f"type={asset_type}")
    if source:
        filters.append(f"source={source}")

    filter_str = " with filters: " + ", ".join(filters) if filters else ""
    return json.dumps({"status": "success", "message": f"Cache cleared{filter_str}"})


@mcp.prompt()
def create_asset_search_prompt(
    content_brief: str, asset_types: Optional[List[str]] = None
) -> str:
    """
    Generate a prompt for searching assets based on a content brief.

    Args:
        content_brief: Description of the content being created
        asset_types: Types of assets needed (image, video, audio, gif)

    Returns:
        Formatted prompt for asset searching
    """
    if asset_types is None:
        asset_types = ["image", "video", "audio"]

    return f"""
Based on this content brief, search for appropriate royalty-free assets:

Content Brief: {content_brief}

Asset Types Needed: {', '.join(asset_types)}

For each asset type, generate appropriate search queries and use the available
search tools to find relevant content. Consider:

1. Key themes and subjects in the brief
2. Visual style and mood
3. Technical requirements (duration, quality, format)
4. Attribution requirements for each source

After finding assets, provide a summary with:
- Download URLs
- Source and attribution information
- Technical specifications
- Licensing details
"""


# Error handling
@mcp.exception_handler()
def handle_error(error: Exception) -> Dict:
    """Handle errors gracefully"""
    return {
        "error": str(error),
        "type": type(error).__name__,
        "message": "An error occurred while searching for assets",
    }


if __name__ == "__main__":
    # Run the MCP server
    print("Starting Asset Search MCP Server...")
    print("Available tools:")
    print("  - search_images: Search for royalty-free images")
    print("  - search_videos: Search for royalty-free videos")
    print("  - search_audio: Search for royalty-free audio")
    print("  - search_gifs: Search for GIF animations")
    print("  - get_cache_stats: Get cache statistics")
    print("\nServer running on default port...")

    mcp.run()
