"""
CrewAI Production Workflow
Demonstrates hierarchical agent workflow for professional asset management.
"""

import os
import json
from typing import Dict, List

try:
    from crewai import Agent, Task, Crew, Process
    from crewai_tools import tool
except ImportError:
    print("CrewAI not installed. Install with: pip install crewai crewai-tools")
    exit(1)

from asset_api import AssetAPI
from asset_cache import AssetCache

# Initialize API and cache
api_client = AssetAPI()
cache = AssetCache()


# Define custom tools for CrewAI
@tool("Search Images")
def search_images(query: str) -> str:
    """
    Search for royalty-free images

    Args:
        query: Search keywords

    Returns:
        JSON string with image results
    """
    cached = cache.get_cached_assets(query, "image")
    if cached:
        results = cached[:5]
    else:
        results = api_client.search_pexels_images(query, per_page=5)
        if results:
            cache.cache_assets(query, results)

    return json.dumps({
        "query": query,
        "count": len(results),
        "results": results[:5]
    }, indent=2)


@tool("Search Videos")
def search_videos(query: str) -> str:
    """
    Search for royalty-free videos

    Args:
        query: Search keywords

    Returns:
        JSON string with video results
    """
    cached = cache.get_cached_assets(query, "video")
    if cached:
        results = cached[:3]
    else:
        results = api_client.search_pixabay_videos(query, per_page=3)
        if results:
            cache.cache_assets(query, results)

    return json.dumps({
        "query": query,
        "count": len(results),
        "results": results[:3]
    }, indent=2)


@tool("Search Audio")
def search_audio(query: str) -> str:
    """
    Search for royalty-free audio

    Args:
        query: Search keywords

    Returns:
        JSON string with audio results
    """
    cached = cache.get_cached_assets(query, "audio")
    if cached:
        results = cached[:3]
    else:
        results = api_client.search_freesound(query, max_results=3)
        if results:
            cache.cache_assets(query, results)

    return json.dumps({
        "query": query,
        "count": len(results),
        "results": results[:3]
    }, indent=2)


@tool("Download Asset")
def download_asset(url: str, filename: str) -> str:
    """
    Download asset to local storage

    Args:
        url: Asset URL
        filename: Local filename to save as

    Returns:
        Success message or error
    """
    try:
        import requests
        import os

        os.makedirs("assets", exist_ok=True)
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        filepath = f"assets/{filename}"
        with open(filepath, "wb") as f:
            f.write(response.content)

        return f"✅ Downloaded: {filepath} ({len(response.content)} bytes)"
    except Exception as e:
        return f"❌ Error downloading {filename}: {str(e)}"


def create_asset_crew(content_brief: str):
    """
    Create a CrewAI crew for asset management

    Args:
        content_brief: Content description

    Returns:
        Configured Crew instance
    """

    # Define agents
    content_strategist = Agent(
        role="Content Strategist",
        goal="Understand content requirements and plan comprehensive asset needs",
        backstory="""You are an experienced content strategist with expertise in
        visual storytelling and media production. You excel at breaking down
        content briefs into specific, actionable asset requirements. You consider
        themes, mood, target audience, and technical specifications.""",
        tools=[],
        verbose=True,
        allow_delegation=True
    )

    media_curator = Agent(
        role="Media Curator",
        goal="Find and curate high-quality royalty-free assets that match requirements",
        backstory="""You are a professional media curator specializing in sourcing
        and evaluating visual and audio content. You have an eye for quality and
        understand licensing requirements. You use multiple search strategies to
        find the best assets for each project.""",
        tools=[search_images, search_videos, search_audio],
        verbose=True,
        allow_delegation=False
    )

    asset_manager = Agent(
        role="Asset Manager",
        goal="Download, organize, and document assets for production use",
        backstory="""You are a meticulous digital asset manager. You organize
        files systematically, maintain proper documentation, track licensing,
        and ensure all assets are production-ready. You create comprehensive
        manifests with attribution information.""",
        tools=[download_asset],
        verbose=True,
        allow_delegation=False
    )

    # Define tasks
    task1 = Task(
        description=f"""Analyze this content brief and create detailed asset requirements:

{content_brief}

Your output should include:
1. List of required images with specific search queries
2. List of required videos with specific search queries
3. List of required audio with specific search queries
4. Technical specifications (dimensions, duration, format requirements)
5. Style and mood guidelines

Be specific and thorough in your asset descriptions.""",
        expected_output="""Detailed asset requirements document with:
- 3-5 specific image search queries
- 2-3 specific video search queries
- 1-2 specific audio search queries
- Technical specifications for each asset type
- Style and mood guidelines""",
        agent=content_strategist
    )

    task2 = Task(
        description="""Using the asset requirements from the Content Strategist:

1. Search for images using the provided queries
2. Search for videos using the provided queries
3. Search for audio using the provided queries
4. Evaluate results for quality and relevance
5. Select the top 3 options for each asset type

For each selected asset, provide:
- Direct download URL
- Thumbnail/preview URL
- Source platform
- Attribution information
- Technical specifications
- Licensing details""",
        expected_output="""Curated asset collection with:
- Top 3 images with complete metadata
- Top 2 videos with complete metadata
- Top 2 audio tracks with complete metadata
All formatted as structured JSON with URLs and attribution""",
        agent=media_curator
    )

    task3 = Task(
        description="""Download and organize the selected assets:

1. Create organized folder structure (assets/images, assets/videos, assets/audio)
2. Download assets with descriptive filenames
3. Generate a comprehensive manifest.json with:
   - Project metadata
   - Complete asset inventory
   - Attribution text for each asset
   - Licensing summary
   - Usage guidelines

4. Create a README.txt with attribution instructions

Ensure all files are properly named and documented.""",
        expected_output="""Complete asset package with:
- Downloaded assets in organized folders
- manifest.json with complete metadata
- README.txt with attribution instructions
- Confirmation of all downloads
- File size and format information""",
        agent=asset_manager
    )

    # Create and configure crew
    crew = Crew(
        agents=[content_strategist, media_curator, asset_manager],
        tasks=[task1, task2, task3],
        process=Process.sequential,
        verbose=2,
        memory=True,
        embedder={
            "provider": "openai",
            "config": {
                "model": "text-embedding-3-small"
            }
        }
    )

    return crew


def run_crewai_workflow(content_brief: str):
    """
    Execute the CrewAI workflow

    Args:
        content_brief: Content description
    """
    print("🚀 Initializing CrewAI Asset Management Crew...")
    print("=" * 80)
    print(f"Content Brief:\n{content_brief}")
    print("=" * 80)
    print()

    # Create and run crew
    crew = create_asset_crew(content_brief)

    print("🎬 Starting CrewAI workflow...\n")
    result = crew.kickoff(inputs={"content_brief": content_brief})

    print("\n" + "=" * 80)
    print("✅ Workflow Completed!")
    print("=" * 80)
    print(f"\nResult:\n{result}")

    return result


if __name__ == "__main__":
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Please set it with: export OPENAI_API_KEY='your-key-here'")
        exit(1)

    # Example: Educational video about AI in healthcare
    content_brief = """
    Create a 60-second explainer video about AI in healthcare.

    Topic: How artificial intelligence is transforming medical diagnosis and patient care
    Target Audience: General public interested in healthcare technology
    Tone: Professional yet accessible, optimistic about technology

    Required Assets:
    - 3 images showing medical technology, doctors using AI tools, or healthcare settings
    - 2 video clips of healthcare environments or medical technology in action
    - 1 professional background music track (corporate/technology style, 60 seconds)

    Visual Style:
    - Clean, modern aesthetic
    - Professional medical/technology feel
    - High-quality, crisp images
    - Blue/white color palette preferred

    Technical Requirements:
    - Images: Minimum 1920x1080 resolution
    - Videos: HD quality (1080p), 5-15 seconds each
    - Audio: MP3 format, suitable for background

    Licensing: All assets must be royalty-free for commercial use
    """

    result = run_crewai_workflow(content_brief)

    print("\n📦 Asset package ready for production!")
    print("Check the 'assets' directory for downloaded files")
    print("See manifest.json for complete asset inventory")
