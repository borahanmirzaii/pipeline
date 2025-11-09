"""
Asset API Client
Unified interface for searching royalty-free assets across multiple providers.
"""

import os
import requests
from typing import List, Dict, Optional
from datetime import datetime


class AssetAPI:
    """Multi-source API client for royalty-free assets"""

    def __init__(self):
        self.pexels_key = os.getenv("PEXELS_API_KEY")
        self.unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")
        self.pixabay_key = os.getenv("PIXABAY_API_KEY")
        self.freesound_key = os.getenv("FREESOUND_API_KEY")
        self.giphy_key = os.getenv("GIPHY_API_KEY")

    def search_pexels_images(self, query: str, per_page: int = 15) -> List[Dict]:
        """
        Search Pexels for images with caching

        Args:
            query: Search keywords
            per_page: Number of results per page (max 80)

        Returns:
            List of image dictionaries with metadata
        """
        url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": self.pexels_key}
        params = {"query": query, "per_page": per_page}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            return [
                {
                    "id": photo["id"],
                    "url": photo["src"]["original"],
                    "thumbnail": photo["src"]["medium"],
                    "photographer": photo["photographer"],
                    "photographer_url": photo["photographer_url"],
                    "source": "pexels",
                    "type": "image",
                    "width": photo["width"],
                    "height": photo["height"],
                    "alt": photo.get("alt", ""),
                }
                for photo in data.get("photos", [])
            ]
        except requests.RequestException as e:
            print(f"Error fetching from Pexels: {e}")
            return []

    def search_pexels_videos(self, query: str, per_page: int = 10) -> List[Dict]:
        """
        Search Pexels for videos

        Args:
            query: Search keywords
            per_page: Number of results per page

        Returns:
            List of video dictionaries with metadata
        """
        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": self.pexels_key}
        params = {"query": query, "per_page": per_page}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            return [
                {
                    "id": video["id"],
                    "url": video["video_files"][0]["link"]
                    if video["video_files"]
                    else "",
                    "thumbnail": video["image"],
                    "duration": video["duration"],
                    "width": video["width"],
                    "height": video["height"],
                    "user": video["user"]["name"],
                    "source": "pexels",
                    "type": "video",
                }
                for video in data.get("videos", [])
            ]
        except requests.RequestException as e:
            print(f"Error fetching videos from Pexels: {e}")
            return []

    def search_pixabay_images(self, query: str, per_page: int = 20) -> List[Dict]:
        """
        Search Pixabay for images

        Args:
            query: Search keywords
            per_page: Number of results per page (max 200)

        Returns:
            List of image dictionaries with metadata
        """
        url = "https://pixabay.com/api/"
        params = {"key": self.pixabay_key, "q": query, "per_page": per_page}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            return [
                {
                    "id": hit["id"],
                    "url": hit["largeImageURL"],
                    "thumbnail": hit["previewURL"],
                    "photographer": hit["user"],
                    "source": "pixabay",
                    "type": "image",
                    "width": hit["imageWidth"],
                    "height": hit["imageHeight"],
                    "tags": hit["tags"].split(", "),
                }
                for hit in data.get("hits", [])
            ]
        except requests.RequestException as e:
            print(f"Error fetching from Pixabay: {e}")
            return []

    def search_pixabay_videos(self, query: str, per_page: int = 10) -> List[Dict]:
        """
        Search Pixabay for video content

        Args:
            query: Search keywords
            per_page: Number of results per page

        Returns:
            List of video dictionaries with metadata
        """
        url = "https://pixabay.com/api/videos/"
        params = {"key": self.pixabay_key, "q": query, "per_page": per_page}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            return [
                {
                    "id": video["id"],
                    "url": video["videos"]["large"]["url"],
                    "thumbnail": video["userImageURL"],
                    "duration": video["duration"],
                    "width": video["videos"]["large"]["width"],
                    "height": video["videos"]["large"]["height"],
                    "user": video["user"],
                    "source": "pixabay",
                    "type": "video",
                    "tags": video["tags"].split(", "),
                }
                for video in data.get("hits", [])
            ]
        except requests.RequestException as e:
            print(f"Error fetching videos from Pixabay: {e}")
            return []

    def search_unsplash_images(self, query: str, per_page: int = 10) -> List[Dict]:
        """
        Search Unsplash for images

        Args:
            query: Search keywords
            per_page: Number of results per page (max 30)

        Returns:
            List of image dictionaries with metadata
        """
        url = "https://api.unsplash.com/search/photos"
        headers = {"Authorization": f"Client-ID {self.unsplash_key}"}
        params = {"query": query, "per_page": per_page}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            return [
                {
                    "id": photo["id"],
                    "url": photo["urls"]["full"],
                    "thumbnail": photo["urls"]["small"],
                    "photographer": photo["user"]["name"],
                    "photographer_url": photo["user"]["links"]["html"],
                    "source": "unsplash",
                    "type": "image",
                    "width": photo["width"],
                    "height": photo["height"],
                    "description": photo.get("description", ""),
                    "alt": photo.get("alt_description", ""),
                }
                for photo in data.get("results", [])
            ]
        except requests.RequestException as e:
            print(f"Error fetching from Unsplash: {e}")
            return []

    def search_freesound(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Search Freesound for audio files

        Args:
            query: Search keywords
            max_results: Maximum number of results

        Returns:
            List of audio dictionaries with metadata
        """
        url = "https://freesound.org/apiv2/search/text/"
        params = {
            "query": query,
            "token": self.freesound_key,
            "page_size": max_results,
            "fields": "id,name,tags,duration,license,previews,username",
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            return [
                {
                    "id": result["id"],
                    "name": result["name"],
                    "preview_url": result["previews"]["preview-hq-mp3"],
                    "duration": result["duration"],
                    "license": result["license"],
                    "tags": result["tags"],
                    "username": result["username"],
                    "source": "freesound",
                    "type": "audio",
                }
                for result in data.get("results", [])
            ]
        except requests.RequestException as e:
            print(f"Error fetching from Freesound: {e}")
            return []

    def search_giphy_gifs(self, query: str, limit: int = 25) -> List[Dict]:
        """
        Search Giphy for GIFs

        Args:
            query: Search keywords
            limit: Maximum number of results (max 50)

        Returns:
            List of GIF dictionaries with metadata
        """
        url = "https://api.giphy.com/v1/gifs/search"
        params = {"api_key": self.giphy_key, "q": query, "limit": limit, "rating": "g"}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            return [
                {
                    "id": gif["id"],
                    "url": gif["images"]["original"]["url"],
                    "thumbnail": gif["images"]["preview_gif"]["url"],
                    "title": gif["title"],
                    "width": gif["images"]["original"]["width"],
                    "height": gif["images"]["original"]["height"],
                    "source": "giphy",
                    "type": "gif",
                }
                for gif in data.get("data", [])
            ]
        except requests.RequestException as e:
            print(f"Error fetching from Giphy: {e}")
            return []


# Example usage
if __name__ == "__main__":
    api = AssetAPI()

    # Search for images
    print("Searching for mountain images...")
    images = api.search_pexels_images("mountains", per_page=5)
    print(f"Found {len(images)} images")

    # Search for videos
    print("\nSearching for nature videos...")
    videos = api.search_pixabay_videos("nature", per_page=3)
    print(f"Found {len(videos)} videos")

    # Search for audio
    print("\nSearching for ambient audio...")
    audio = api.search_freesound("ambient", max_results=5)
    print(f"Found {len(audio)} audio files")

    # Search for GIFs
    print("\nSearching for cat GIFs...")
    gifs = api.search_giphy_gifs("cat", limit=5)
    print(f"Found {len(gifs)} GIFs")
