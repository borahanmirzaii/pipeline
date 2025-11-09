"""
Production-Ready Content Generation Pipeline
Complete end-to-end pipeline: Brief → Asset Discovery → Download → Manifest
"""

import asyncio
import aiohttp
import os
import json
import time
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

try:
    from openai import AsyncOpenAI
except ImportError:
    print("OpenAI not installed. Install with: pip install openai")
    exit(1)

from asset_api import AssetAPI
from asset_cache import AssetCache


class ContentProductionPipeline:
    """
    Complete pipeline for automated asset discovery and management
    """

    def __init__(self, output_dir: str = "production_assets"):
        """
        Initialize production pipeline

        Args:
            output_dir: Directory for output assets
        """
        self.api = AssetAPI()
        self.cache = AssetCache()
        self.output_dir = Path(output_dir)
        self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Create output directories
        self.output_dir.mkdir(exist_ok=True)
        (self.output_dir / "images").mkdir(exist_ok=True)
        (self.output_dir / "videos").mkdir(exist_ok=True)
        (self.output_dir / "audio").mkdir(exist_ok=True)

    async def generate_social_video_assets(
        self,
        brief: str,
        style: str = "modern",
        duration: int = 60,
        store_in_supabase: bool = False
    ) -> Dict:
        """
        Complete pipeline: Brief → Asset Discovery → Download → Manifest

        Args:
            brief: Content brief describing the video
            style: Visual style (modern, vintage, minimalist, etc.)
            duration: Video duration in seconds
            store_in_supabase: Whether to store metadata in Supabase

        Returns:
            Manifest dictionary with all asset information
        """
        print(f"🚀 Starting production pipeline...")
        print(f"📋 Brief: {brief[:100]}...")
        print(f"🎨 Style: {style}")
        print(f"⏱️  Duration: {duration}s\n")

        # Step 1: Analyze brief with LLM
        print("🤖 Step 1: Analyzing content brief with AI...")
        requirements = await self.analyze_brief(brief, style, duration)
        print(f"✅ Generated {len(requirements['image_queries'])} image queries, "
              f"{len(requirements['video_queries'])} video queries, "
              f"{len(requirements['audio_queries'])} audio queries\n")

        # Step 2: Search for assets in parallel
        print("🔍 Step 2: Searching for assets across multiple sources...")
        start_time = time.time()
        tasks = [
            self.fetch_images(requirements["image_queries"]),
            self.fetch_videos(requirements["video_queries"]),
            self.fetch_audio(requirements["audio_queries"])
        ]
        images, videos, audio = await asyncio.gather(*tasks)
        search_time = time.time() - start_time
        print(f"✅ Found {len(images)} images, {len(videos)} videos, "
              f"{len(audio)} audio tracks in {search_time:.2f}s\n")

        # Step 3: Download and organize
        print("📥 Step 3: Downloading and organizing assets...")
        manifest = await self.download_and_organize({
            "images": images,
            "videos": videos,
            "audio": audio
        }, brief, style)
        print(f"✅ Downloaded {len(manifest['assets'])} assets\n")

        # Step 4: Store in Supabase (optional)
        if store_in_supabase:
            print("💾 Step 4: Storing metadata in Supabase...")
            await self.store_in_supabase(manifest)
            print("✅ Metadata stored\n")

        print(f"🎉 Pipeline completed successfully!")
        print(f"📁 Assets saved to: {self.output_dir}")
        print(f"📄 Manifest: {self.output_dir / 'manifest.json'}")

        return manifest

    async def analyze_brief(
        self, brief: str, style: str, duration: int
    ) -> Dict:
        """
        Use LLM to extract asset requirements from content brief

        Args:
            brief: Content brief
            style: Visual style
            duration: Duration in seconds

        Returns:
            Dictionary with search queries for each asset type
        """
        response = await self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{
                "role": "system",
                "content": """You are an expert content strategist who extracts
                media asset requirements from content briefs. Analyze briefs and
                generate specific, descriptive search queries for finding royalty-free
                assets."""
            }, {
                "role": "user",
                "content": f"""Analyze this content brief and generate search queries:

Brief: {brief}
Style: {style}
Duration: {duration} seconds

Generate specific search queries for:
1. Images (3-5 queries): Focus on key visual themes, subjects, and mood
2. Videos (2-3 queries): Focus on action, scenes, and b-roll footage
3. Audio (1-2 queries): Focus on mood, genre, and style

Return ONLY a JSON object with this exact structure:
{{
  "image_queries": ["query 1", "query 2", "query 3"],
  "video_queries": ["query 1", "query 2"],
  "audio_queries": ["query 1"]
}}

Make queries specific and descriptive (e.g., "modern office workspace with natural light"
not just "office")."""
            }],
            response_format={"type": "json_object"},
            temperature=0.3
        )

        result = json.loads(response.choices[0].message.content)
        return result

    async def fetch_images(self, queries: List[str]) -> List[Dict]:
        """
        Fetch images for all queries with caching

        Args:
            queries: List of search queries

        Returns:
            List of image dictionaries
        """
        results = []
        for query in queries:
            # Check cache
            cached = self.cache.get_cached_assets(query, "image")
            if cached:
                results.extend(cached[:2])  # Top 2 per query
                print(f"  💾 Cache hit: '{query}' ({len(cached[:2])} images)")
            else:
                fresh = self.api.search_pexels_images(query, per_page=2)
                if fresh:
                    self.cache.cache_assets(query, fresh)
                    results.extend(fresh)
                    print(f"  🌐 API call: '{query}' ({len(fresh)} images)")
                await asyncio.sleep(0.1)  # Rate limiting

        return results

    async def fetch_videos(self, queries: List[str]) -> List[Dict]:
        """
        Fetch video clips for all queries with caching

        Args:
            queries: List of search queries

        Returns:
            List of video dictionaries
        """
        results = []
        for query in queries:
            cached = self.cache.get_cached_assets(query, "video")
            if cached:
                results.extend(cached[:1])  # Top 1 per query
                print(f"  💾 Cache hit: '{query}' ({len(cached[:1])} videos)")
            else:
                fresh = self.api.search_pixabay_videos(query, per_page=1)
                if fresh:
                    self.cache.cache_assets(query, fresh)
                    results.extend(fresh)
                    print(f"  🌐 API call: '{query}' ({len(fresh)} videos)")
                await asyncio.sleep(0.1)  # Rate limiting

        return results

    async def fetch_audio(self, queries: List[str]) -> List[Dict]:
        """
        Fetch audio tracks for all queries with caching

        Args:
            queries: List of search queries

        Returns:
            List of audio dictionaries
        """
        results = []
        for query in queries:
            cached = self.cache.get_cached_assets(query, "audio")
            if cached:
                results.append(cached[0])
                print(f"  💾 Cache hit: '{query}' (1 audio track)")
            else:
                fresh = self.api.search_freesound(query, max_results=1)
                if fresh:
                    self.cache.cache_assets(query, fresh)
                    results.append(fresh[0])
                    print(f"  🌐 API call: '{query}' (1 audio track)")
                await asyncio.sleep(0.1)  # Rate limiting

        return results

    async def download_and_organize(
        self, assets: Dict, brief: str, style: str
    ) -> Dict:
        """
        Download assets and create manifest

        Args:
            assets: Dictionary of assets by type
            brief: Original content brief
            style: Visual style

        Returns:
            Complete manifest dictionary
        """
        manifest = {
            "project_id": f"project_{int(time.time())}",
            "created_at": datetime.now().isoformat(),
            "brief": brief,
            "style": style,
            "assets": []
        }

        async with aiohttp.ClientSession() as session:
            download_tasks = []

            for asset_type, items in assets.items():
                for idx, item in enumerate(items):
                    url = item.get("url") or item.get("preview_url", "")
                    if not url:
                        continue

                    # Determine file extension
                    ext = self._get_file_extension(url, asset_type)
                    filename = f"{asset_type}/{asset_type}_{idx:03d}{ext}"

                    # Create download task
                    task = self._download_file(session, url, filename, item, asset_type)
                    download_tasks.append(task)

            # Download all assets in parallel
            downloaded = await asyncio.gather(*download_tasks, return_exceptions=True)

            # Filter successful downloads
            manifest["assets"] = [
                asset for asset in downloaded
                if isinstance(asset, dict) and not isinstance(asset, Exception)
            ]

        # Save manifest
        manifest_path = self.output_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        # Create attribution file
        await self._create_attribution_file(manifest)

        return manifest

    async def _download_file(
        self, session: aiohttp.ClientSession, url: str, filename: str,
        item: Dict, asset_type: str
    ) -> Dict:
        """Download a single file"""
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    filepath = self.output_dir / filename

                    with open(filepath, "wb") as f:
                        f.write(content)

                    print(f"  ✅ Downloaded: {filename} ({len(content) / 1024:.1f} KB)")

                    return {
                        "type": asset_type,
                        "filename": filename,
                        "filepath": str(filepath),
                        "source": item.get("source", "unknown"),
                        "original_url": url,
                        "attribution": self._get_attribution(item),
                        "license": item.get("license", "Royalty-free"),
                        "file_size": len(content),
                        "metadata": {
                            k: v for k, v in item.items()
                            if k not in ["url", "preview_url", "thumbnail"]
                        }
                    }
                else:
                    print(f"  ❌ Failed to download: {filename} (HTTP {resp.status})")
                    return {}

        except Exception as e:
            print(f"  ❌ Error downloading {filename}: {str(e)}")
            return {}

    def _get_file_extension(self, url: str, asset_type: str) -> str:
        """Determine file extension from URL or asset type"""
        url_lower = url.lower()

        if asset_type == "image":
            if ".jpg" in url_lower or ".jpeg" in url_lower:
                return ".jpg"
            elif ".png" in url_lower:
                return ".png"
            return ".jpg"  # default

        elif asset_type == "video":
            if ".mp4" in url_lower:
                return ".mp4"
            elif ".webm" in url_lower:
                return ".webm"
            return ".mp4"  # default

        elif asset_type == "audio":
            if ".mp3" in url_lower:
                return ".mp3"
            elif ".wav" in url_lower:
                return ".wav"
            return ".mp3"  # default

        return ""

    def _get_attribution(self, item: Dict) -> str:
        """Generate attribution text for an asset"""
        source = item.get("source", "Unknown")
        creator = (
            item.get("photographer") or
            item.get("user") or
            item.get("username") or
            "Unknown"
        )

        if source == "pexels":
            return f"Photo by {creator} from Pexels"
        elif source == "pixabay":
            return f"Image/Video by {creator} from Pixabay"
        elif source == "unsplash":
            return f"Photo by {creator} on Unsplash"
        elif source == "freesound":
            return f"Sound by {creator} from Freesound"
        else:
            return f"Media by {creator} from {source}"

    async def _create_attribution_file(self, manifest: Dict):
        """Create a text file with all attributions"""
        attribution_path = self.output_dir / "ATTRIBUTION.txt"

        with open(attribution_path, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("ASSET ATTRIBUTION\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Project: {manifest['project_id']}\n")
            f.write(f"Created: {manifest['created_at']}\n\n")
            f.write("All assets used in this project:\n\n")

            for asset in manifest["assets"]:
                f.write(f"• {asset['filename']}\n")
                f.write(f"  {asset['attribution']}\n")
                f.write(f"  License: {asset['license']}\n")
                f.write(f"  Source URL: {asset['original_url']}\n\n")

            f.write("=" * 80 + "\n")
            f.write("Thank you to all content creators!\n")

        print(f"  📝 Created attribution file: ATTRIBUTION.txt")

    async def store_in_supabase(self, manifest: Dict):
        """
        Store asset metadata in Supabase (requires supabase-py)

        Args:
            manifest: Asset manifest dictionary
        """
        try:
            from supabase import create_client

            supabase = create_client(
                os.getenv("SUPABASE_URL"),
                os.getenv("SUPABASE_SERVICE_KEY")
            )

            for asset in manifest["assets"]:
                supabase.table("asset_metadata").insert({
                    "project_id": manifest["project_id"],
                    "type": asset["type"],
                    "filename": asset["filename"],
                    "source": asset["source"],
                    "original_url": asset["original_url"],
                    "attribution": asset["attribution"],
                    "license": asset["license"],
                    "file_size": asset["file_size"],
                    "metadata": asset["metadata"]
                }).execute()

        except ImportError:
            print("  ⚠️  Supabase not installed. Skipping database storage.")
        except Exception as e:
            print(f"  ⚠️  Error storing in Supabase: {str(e)}")


# Example usage
async def main():
    """Run example pipeline"""

    # Example 1: Social media video about remote work
    pipeline = ContentProductionPipeline(output_dir="example_output")

    result = await pipeline.generate_social_video_assets(
        brief="""Create an inspiring 60-second video about remote work.
        Show diverse people working from different locations - home offices,
        cafes, outdoor spaces. Include shots of collaboration tools and happy
        productive moments. Uplifting background music.""",
        style="modern",
        duration=60
    )

    print("\n" + "=" * 80)
    print("📊 PIPELINE SUMMARY")
    print("=" * 80)
    print(f"Project ID: {result['project_id']}")
    print(f"Total Assets: {len(result['assets'])}")
    print(f"Images: {len([a for a in result['assets'] if a['type'] == 'images'])}")
    print(f"Videos: {len([a for a in result['assets'] if a['type'] == 'videos'])}")
    print(f"Audio: {len([a for a in result['assets'] if a['type'] == 'audio'])}")
    print(f"\n📁 Output Directory: example_output/")
    print("📄 Manifest: example_output/manifest.json")
    print("📝 Attribution: example_output/ATTRIBUTION.txt")
    print("=" * 80)


if __name__ == "__main__":
    # Check for required API keys
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        exit(1)

    asyncio.run(main())
