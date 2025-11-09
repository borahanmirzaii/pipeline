"""
LangChain Agent with Asset Search Tools
Demonstrates how to integrate asset search into LangChain agents.
"""

import json
import os
from typing import Dict, List

try:
    from langchain.agents import AgentExecutor, create_openai_functions_agent
    from langchain.tools import Tool
    from langchain_openai import ChatOpenAI
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
except ImportError:
    print("LangChain not installed. Install with: pip install langchain langchain-openai")
    exit(1)

from asset_api import AssetAPI
from asset_cache import AssetCache

# Initialize API and cache
api_client = AssetAPI()
cache = AssetCache()


def search_images_tool(query: str) -> str:
    """
    Search for royalty-free images

    Args:
        query: Search keywords

    Returns:
        JSON string with image results
    """
    # Check cache first
    cached = cache.get_cached_assets(query, "image")
    if cached:
        results = cached[:5]
    else:
        results = api_client.search_pexels_images(query, per_page=5)
        if results:
            cache.cache_assets(query, results)

    return json.dumps(
        {
            "query": query,
            "count": len(results),
            "images": [
                {
                    "url": r["url"],
                    "thumbnail": r["thumbnail"],
                    "photographer": r.get("photographer", "Unknown"),
                    "source": r["source"],
                }
                for r in results
            ],
        },
        indent=2,
    )


def search_videos_tool(query: str) -> str:
    """
    Search for royalty-free videos

    Args:
        query: Search keywords

    Returns:
        JSON string with video results
    """
    # Check cache first
    cached = cache.get_cached_assets(query, "video")
    if cached:
        results = cached[:3]
    else:
        results = api_client.search_pixabay_videos(query, per_page=3)
        if results:
            cache.cache_assets(query, results)

    return json.dumps(
        {
            "query": query,
            "count": len(results),
            "videos": [
                {
                    "url": r["url"],
                    "thumbnail": r["thumbnail"],
                    "duration": r.get("duration", 0),
                    "source": r["source"],
                }
                for r in results
            ],
        },
        indent=2,
    )


def search_audio_tool(query: str) -> str:
    """
    Search for royalty-free audio

    Args:
        query: Search keywords

    Returns:
        JSON string with audio results
    """
    # Check cache first
    cached = cache.get_cached_assets(query, "audio")
    if cached:
        results = cached[:5]
    else:
        results = api_client.search_freesound(query, max_results=5)
        if results:
            cache.cache_assets(query, results)

    return json.dumps(
        {
            "query": query,
            "count": len(results),
            "audio": [
                {
                    "name": r.get("name", "Unknown"),
                    "preview_url": r.get("preview_url", ""),
                    "duration": r.get("duration", 0),
                    "license": r.get("license", "Unknown"),
                    "source": r["source"],
                }
                for r in results
            ],
        },
        indent=2,
    )


def create_asset_agent():
    """
    Create a LangChain agent with asset search tools

    Returns:
        Configured AgentExecutor
    """
    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY")
    )

    # Define tools
    tools = [
        Tool(
            name="SearchImages",
            func=search_images_tool,
            description="""Search for royalty-free images. Input should be descriptive keywords.
            Returns JSON with image URLs, thumbnails, photographer credits, and source.
            Use this when you need to find photos or visual content.""",
        ),
        Tool(
            name="SearchVideos",
            func=search_videos_tool,
            description="""Search for royalty-free video clips. Input should be descriptive keywords.
            Returns JSON with video URLs, thumbnails, duration, and source.
            Use this when you need video footage or motion content.""",
        ),
        Tool(
            name="SearchAudio",
            func=search_audio_tool,
            description="""Search for royalty-free audio and sound effects. Input should be descriptive keywords.
            Returns JSON with audio preview URLs, duration, license info, and source.
            Use this when you need background music or sound effects.""",
        ),
    ]

    # Create agent prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful content creation assistant that finds royalty-free assets.

        When users request media assets:
        1. Use the available tools to search across multiple sources
        2. Provide direct URLs and download links
        3. Always include proper attribution information
        4. Explain licensing requirements
        5. Suggest multiple options when possible

        Be thorough but concise. Focus on high-quality, relevant results."""),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Create agent
    agent = create_openai_functions_agent(llm, tools, prompt)

    # Create executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=5,
        handle_parsing_errors=True,
    )

    return agent_executor


def run_example():
    """Run example queries with the asset agent"""

    print("Creating LangChain agent with asset search tools...\n")
    agent = create_asset_agent()

    # Example 1: Simple image search
    print("=" * 80)
    print("Example 1: Search for images")
    print("=" * 80)
    result1 = agent.invoke({
        "input": "Find me 3 high-quality images of mountain landscapes for a blog post"
    })
    print(f"\nResult: {result1['output']}\n")

    # Example 2: Multi-asset search
    print("=" * 80)
    print("Example 2: Search for multiple asset types")
    print("=" * 80)
    result2 = agent.invoke({
        "input": """I'm creating a video about productivity. I need:
        - 2 images of office workspaces
        - 1 short video clip of someone working on a laptop
        - 1 ambient background music track"""
    })
    print(f"\nResult: {result2['output']}\n")

    # Example 3: Specific requirements
    print("=" * 80)
    print("Example 3: Search with specific requirements")
    print("=" * 80)
    result3 = agent.invoke({
        "input": """Find me audio tracks that are:
        - Under 2 minutes long
        - Suitable for a meditation app
        - Have Creative Commons licenses"""
    })
    print(f"\nResult: {result3['output']}\n")


if __name__ == "__main__":
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Please set it with: export OPENAI_API_KEY='your-key-here'")
        exit(1)

    run_example()
