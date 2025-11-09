"""
Asset Cache
Local SQLite caching layer for asset metadata and search results.
"""

import sqlite3
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import hashlib


class AssetCache:
    """Local cache for asset metadata with TTL support"""

    def __init__(self, db_path: str = "assets_cache.db"):
        """
        Initialize asset cache with SQLite backend

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.setup_database()

    def setup_database(self):
        """Initialize cache database with metadata support"""
        cursor = self.conn.cursor()

        # Main assets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                type TEXT NOT NULL,
                query TEXT NOT NULL,
                query_hash TEXT NOT NULL,
                url TEXT NOT NULL,
                thumbnail TEXT,
                metadata TEXT,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP
            )
        """)

        # Indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_hash
            ON assets(query_hash, type, source)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires
            ON assets(expires_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_type_source
            ON assets(type, source)
        """)

        # Cache statistics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL,
                query TEXT NOT NULL,
                hit BOOLEAN NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    def _normalize_query(self, query: str) -> str:
        """
        Normalize query string for better cache hits

        Args:
            query: Raw search query

        Returns:
            Normalized query string
        """
        # Convert to lowercase and remove extra whitespace
        normalized = " ".join(query.lower().split())
        return normalized

    def _hash_query(self, query: str, asset_type: Optional[str] = None) -> str:
        """
        Generate hash for query to use as cache key

        Args:
            query: Search query
            asset_type: Optional asset type filter

        Returns:
            MD5 hash of normalized query
        """
        normalized = self._normalize_query(query)
        key = f"{normalized}:{asset_type or 'all'}"
        return hashlib.md5(key.encode()).hexdigest()

    def get_cached_assets(
        self, query: str, asset_type: Optional[str] = None, source: Optional[str] = None
    ) -> List[Dict]:
        """
        Retrieve cached assets if not expired

        Args:
            query: Search query
            asset_type: Optional filter by asset type
            source: Optional filter by source

        Returns:
            List of cached asset dictionaries
        """
        cursor = self.conn.cursor()
        query_hash = self._hash_query(query, asset_type)

        sql = """
            SELECT id, source, type, url, thumbnail, metadata
            FROM assets
            WHERE query_hash = ? AND (expires_at IS NULL OR expires_at > ?)
        """
        params = [query_hash, datetime.now()]

        if asset_type:
            sql += " AND type = ?"
            params.append(asset_type)

        if source:
            sql += " AND source = ?"
            params.append(source)

        sql += " ORDER BY access_count DESC, last_accessed DESC"

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # Update access statistics
        if rows:
            asset_ids = [row[0] for row in rows]
            placeholders = ",".join("?" * len(asset_ids))
            cursor.execute(
                f"""
                UPDATE assets
                SET access_count = access_count + 1,
                    last_accessed = ?
                WHERE id IN ({placeholders})
            """,
                [datetime.now()] + asset_ids,
            )
            self.conn.commit()

            # Log cache hit
            self._log_cache_stat("get", query, hit=True)

        else:
            # Log cache miss
            self._log_cache_stat("get", query, hit=False)

        return [
            {
                "id": row[0],
                "source": row[1],
                "type": row[2],
                "url": row[3],
                "thumbnail": row[4],
                "metadata": json.loads(row[5]) if row[5] else {},
            }
            for row in rows
        ]

    def cache_assets(
        self, query: str, assets: List[Dict], ttl_hours: int = 24
    ) -> int:
        """
        Cache assets with expiration

        Args:
            query: Search query used
            assets: List of asset dictionaries to cache
            ttl_hours: Time-to-live in hours

        Returns:
            Number of assets cached
        """
        if not assets:
            return 0

        cursor = self.conn.cursor()
        query_hash = self._hash_query(query, assets[0].get("type"))
        expires_at = datetime.now() + timedelta(hours=ttl_hours)
        cached_count = 0

        for asset in assets:
            try:
                asset_id = f"{asset['source']}_{asset['id']}"
                metadata = {
                    k: v
                    for k, v in asset.items()
                    if k not in ["id", "source", "type", "url", "thumbnail"]
                }

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO assets
                    (id, source, type, query, query_hash, url, thumbnail, metadata, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        asset_id,
                        asset["source"],
                        asset["type"],
                        query,
                        query_hash,
                        asset["url"],
                        asset.get("thumbnail"),
                        json.dumps(metadata),
                        expires_at,
                    ),
                )
                cached_count += 1
            except (KeyError, sqlite3.Error) as e:
                print(f"Error caching asset: {e}")
                continue

        self.conn.commit()
        self._log_cache_stat("set", query, hit=True)
        return cached_count

    def evict_expired(self) -> int:
        """
        Remove expired cache entries

        Returns:
            Number of entries evicted
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM assets WHERE expires_at IS NOT NULL AND expires_at < ?",
            (datetime.now(),),
        )
        deleted = cursor.rowcount
        self.conn.commit()
        return deleted

    def get_cache_stats(self) -> Dict:
        """
        Get cache statistics and health metrics

        Returns:
            Dictionary with cache statistics
        """
        cursor = self.conn.cursor()

        # Total assets by type and source
        cursor.execute("""
            SELECT
                type,
                source,
                COUNT(*) as count,
                MAX(cached_at) as latest
            FROM assets
            WHERE expires_at IS NULL OR expires_at > ?
            GROUP BY type, source
        """, (datetime.now(),))
        type_stats = cursor.fetchall()

        # Cache hit rate (last 1000 operations)
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN hit = 1 THEN 1 END) as hits,
                COUNT(*) as total
            FROM (
                SELECT hit FROM cache_stats
                ORDER BY timestamp DESC
                LIMIT 1000
            )
        """)
        hit_stats = cursor.fetchone()
        hit_rate = (hit_stats[0] / hit_stats[1] * 100) if hit_stats[1] > 0 else 0

        # Total cache size
        cursor.execute("""
            SELECT COUNT(*) FROM assets
            WHERE expires_at IS NULL OR expires_at > ?
        """, (datetime.now(),))
        total_assets = cursor.fetchone()[0]

        # Expired entries
        cursor.execute("""
            SELECT COUNT(*) FROM assets
            WHERE expires_at IS NOT NULL AND expires_at <= ?
        """, (datetime.now(),))
        expired = cursor.fetchone()[0]

        return {
            "total_assets": total_assets,
            "expired_entries": expired,
            "hit_rate_percent": round(hit_rate, 2),
            "by_type_source": [
                {"type": s[0], "source": s[1], "count": s[2], "latest": s[3]}
                for s in type_stats
            ],
        }

    def _log_cache_stat(self, operation: str, query: str, hit: bool):
        """
        Log cache operation for statistics

        Args:
            operation: Operation type ('get' or 'set')
            query: Search query
            hit: Whether operation was a cache hit
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO cache_stats (operation, query, hit)
            VALUES (?, ?, ?)
        """,
            (operation, query, hit),
        )
        self.conn.commit()

    def clear_cache(self, asset_type: Optional[str] = None, source: Optional[str] = None):
        """
        Clear cache entries

        Args:
            asset_type: Optional filter by asset type
            source: Optional filter by source
        """
        cursor = self.conn.cursor()

        if asset_type or source:
            conditions = []
            params = []

            if asset_type:
                conditions.append("type = ?")
                params.append(asset_type)

            if source:
                conditions.append("source = ?")
                params.append(source)

            sql = f"DELETE FROM assets WHERE {' AND '.join(conditions)}"
            cursor.execute(sql, params)
        else:
            cursor.execute("DELETE FROM assets")

        self.conn.commit()

    def close(self):
        """Close database connection"""
        self.conn.close()


# Example usage
if __name__ == "__main__":
    from asset_api import AssetAPI

    # Initialize API and cache
    api = AssetAPI()
    cache = AssetCache()

    # First search - will hit API
    print("First search (API call)...")
    query = "mountain landscape"
    cached = cache.get_cached_assets(query, "image")

    if not cached:
        print("Cache miss - fetching from API")
        results = api.search_pexels_images(query, per_page=5)
        cache.cache_assets(query, results, ttl_hours=24)
        print(f"Cached {len(results)} images")
    else:
        print(f"Cache hit - found {len(cached)} images")
        results = cached

    # Second search - will hit cache
    print("\nSecond search (cache)...")
    cached = cache.get_cached_assets(query, "image")
    print(f"Retrieved {len(cached)} images from cache")

    # Get cache statistics
    print("\nCache Statistics:")
    stats = cache.get_cache_stats()
    print(json.dumps(stats, indent=2))

    # Clean up expired entries
    print("\nCleaning expired entries...")
    evicted = cache.evict_expired()
    print(f"Evicted {evicted} expired entries")

    cache.close()
