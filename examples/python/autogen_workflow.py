"""
AutoGen Multi-Agent Content Pipeline
Demonstrates multi-agent collaboration for asset discovery and management.
"""

import os
import json
from typing import Dict, List

try:
    from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
except ImportError:
    print("AutoGen not installed. Install with: pip install pyautogen")
    exit(1)

from asset_api import AssetAPI
from asset_cache import AssetCache

# Initialize API and cache
api_client = AssetAPI()
cache = AssetCache()


def create_asset_pipeline():
    """
    Create a multi-agent pipeline for asset discovery and curation

    Returns:
        Tuple of (user_proxy, manager) for running the pipeline
    """

    # Configuration for OpenAI
    config_list = [{
        "model": "gpt-4",
        "api_key": os.getenv("OPENAI_API_KEY")
    }]

    # Asset Research Agent
    asset_researcher = AssistantAgent(
        name="AssetResearcher",
        system_message="""You are an asset research specialist. Your job is to:

1. Understand content requirements from briefs
2. Identify needed asset types (images, videos, audio)
3. Generate specific, descriptive search queries
4. Return structured asset requests in JSON format

When given a content brief, analyze it and output:
{
  "images": ["search query 1", "search query 2", ...],
  "videos": ["search query 1", "search query 2", ...],
  "audio": ["search query 1", ...]
}

Be specific and descriptive in your queries. Consider themes, mood, style, and technical requirements.""",
        llm_config={"config_list": config_list, "temperature": 0.3}
    )

    # Asset Fetcher Agent
    asset_fetcher = AssistantAgent(
        name="AssetFetcher",
        system_message="""You fetch assets from APIs. When given search queries:

1. Call appropriate API functions for each asset type
2. Filter and rank results based on quality and relevance
3. Return downloadable URLs with complete metadata
4. Include attribution and licensing information

Respond with structured data including:
- Direct download URLs
- Thumbnails
- Source attribution
- License type
- Technical specs (dimensions, duration, etc.)

IMPORTANT: You have access to these functions:
- search_images(query: str) -> List[Dict]
- search_videos(query: str) -> List[Dict]
- search_audio(query: str) -> List[Dict]""",
        llm_config={
            "config_list": config_list,
            "temperature": 0,
            "functions": [
                {
                    "name": "search_images",
                    "description": "Search royalty-free images from multiple sources",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search keywords"
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "search_videos",
                    "description": "Search royalty-free video clips",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search keywords"
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "search_audio",
                    "description": "Search royalty-free audio and music",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search keywords"
                            }
                        },
                        "required": ["query"]
                    }
                }
            ]
        }
    )

    # Content Assembler Agent
    content_assembler = AssistantAgent(
        name="ContentAssembler",
        system_message="""You assemble final content packages. Your responsibilities:

1. Review fetched assets for quality and relevance
2. Select best matches for the content brief
3. Generate attribution and licensing notes
4. Create final asset manifest in JSON format

Output a structured manifest:
{
  "project_name": "...",
  "assets": {
    "images": [{url, source, attribution, license}, ...],
    "videos": [{url, source, attribution, license}, ...],
    "audio": [{url, source, attribution, license}, ...]
  },
  "attribution_text": "Credits text...",
  "license_summary": "Summary of licensing requirements"
}

Ensure all assets are properly documented and ready for use.""",
        llm_config={"config_list": config_list, "temperature": 0.2}
    )

    # User proxy for execution
    user_proxy = UserProxyAgent(
        name="ContentCreator",
        human_input_mode="NEVER",
        code_execution_config={
            "work_dir": "assets_output",
            "use_docker": False
        },
        function_map={
            "search_images": lambda query: search_images_function(query),
            "search_videos": lambda query: search_videos_function(query),
            "search_audio": lambda query: search_audio_function(query),
        }
    )

    # Group chat for coordination
    groupchat = GroupChat(
        agents=[asset_researcher, asset_fetcher, content_assembler, user_proxy],
        messages=[],
        max_round=10,
        speaker_selection_method="round_robin"
    )

    manager = GroupChatManager(
        groupchat=groupchat,
        llm_config={"config_list": config_list}
    )

    return user_proxy, manager


def search_images_function(query: str) -> str:
    """Function callable by AutoGen agents"""
    cached = cache.get_cached_assets(query, "image")
    if cached:
        results = cached[:3]
    else:
        results = api_client.search_pexels_images(query, per_page=3)
        if results:
            cache.cache_assets(query, results)

    return json.dumps({
        "query": query,
        "count": len(results),
        "results": [
            {
                "url": r["url"],
                "thumbnail": r["thumbnail"],
                "source": r["source"],
                "photographer": r.get("photographer", "Unknown"),
                "width": r.get("width"),
                "height": r.get("height")
            }
            for r in results
        ]
    })


def search_videos_function(query: str) -> str:
    """Function callable by AutoGen agents"""
    cached = cache.get_cached_assets(query, "video")
    if cached:
        results = cached[:2]
    else:
        results = api_client.search_pixabay_videos(query, per_page=2)
        if results:
            cache.cache_assets(query, results)

    return json.dumps({
        "query": query,
        "count": len(results),
        "results": [
            {
                "url": r["url"],
                "thumbnail": r["thumbnail"],
                "source": r["source"],
                "duration": r.get("duration", 0),
                "width": r.get("width"),
                "height": r.get("height")
            }
            for r in results
        ]
    })


def search_audio_function(query: str) -> str:
    """Function callable by AutoGen agents"""
    cached = cache.get_cached_assets(query, "audio")
    if cached:
        results = cached[:2]
    else:
        results = api_client.search_freesound(query, max_results=2)
        if results:
            cache.cache_assets(query, results)

    return json.dumps({
        "query": query,
        "count": len(results),
        "results": [
            {
                "name": r.get("name", "Unknown"),
                "preview_url": r.get("preview_url", ""),
                "source": r["source"],
                "duration": r.get("duration", 0),
                "license": r.get("license", "Unknown")
            }
            for r in results
        ]
    })


def run_pipeline(content_brief: str):
    """
    Run the AutoGen pipeline with a content brief

    Args:
        content_brief: Description of content to create
    """
    print("Initializing AutoGen multi-agent pipeline...\n")
    user_proxy, manager = create_asset_pipeline()

    print("Starting asset discovery workflow...")
    print("=" * 80)
    print(f"Content Brief: {content_brief}")
    print("=" * 80)
    print()

    # Execute workflow
    user_proxy.initiate_chat(
        manager,
        message=f"""Create a complete asset package for this content brief:

{content_brief}

Please:
1. Analyze the brief and identify needed assets
2. Search for appropriate images, videos, and audio
3. Compile everything into a final manifest with attribution

Provide the final manifest as structured JSON."""
    )


if __name__ == "__main__":
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Please set it with: export OPENAI_API_KEY='your-key-here'")
        exit(1)

    # Example: Social media video about sustainable living
    content_brief = """
    Create a 60-second social media video about sustainable living.

    Theme: Eco-friendly lifestyle and environmental consciousness
    Tone: Inspiring and hopeful
    Target Audience: Young adults (25-35) interested in sustainability

    Required Assets:
    - 3 high-quality images of nature and sustainable practices
    - 2 short video clips showing renewable energy or eco-friendly activities
    - 1 uplifting background music track (under 60 seconds)

    Visual Style: Bright, natural colors with modern aesthetic
    """

    run_pipeline(content_brief)

    print("\n" + "=" * 80)
    print("Pipeline completed!")
    print("=" * 80)
