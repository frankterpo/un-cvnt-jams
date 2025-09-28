"""
YouTube Search Module for Scooby Doo Shorts
Searches for YouTube shorts with specific hashtags and queries
"""

import os
import json
from typing import List, Dict, Any
from googleapiclient.discovery import build
from config import YOUTUBE_API_KEY, YOUTUBE_SEARCH_QUERY, YOUTUBE_MAX_RESULTS, SCOOBY_CHANNELS, YOUTUBE_SHORTS_PREFIX


class YouTubeSearcher:
    def __init__(self):
        if not YOUTUBE_API_KEY:
            raise ValueError("YouTube API key not found. Set YOUTUBE_API_KEY in config.")

        self.youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        self.max_results = YOUTUBE_MAX_RESULTS

    def search_shorts(self, query: str, max_results: int = None) -> List[Dict[str, Any]]:
        """
        Search for YouTube shorts with specific query
        Focuses on shorts by using videoDuration=short
        """
        if max_results is None:
            max_results = self.max_results

        print(f"🔍 Searching YouTube for: '{query}' (max {max_results} shorts)")

        # Search for shorts specifically
        search_request = self.youtube.search().list(
            q=query,
            part="id,snippet",
            type="video",
            maxResults=max_results,
            order="relevance",
            safeSearch="moderate",
            videoDuration="short",  # This targets shorts (under 60 seconds)
            regionCode="US",
        )

        search_response = search_request.execute()
        video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]

        if not video_ids:
            print("❌ No shorts found for query")
            return []

        # Get detailed video information
        videos_request = self.youtube.videos().list(
            part="snippet,contentDetails,statistics,status",
            id=",".join(video_ids),
        )

        videos_response = videos_request.execute()
        videos = videos_response.get("items", [])

        shorts_data = []
        for video in videos:
            # Double-check it's actually a short (under 60 seconds)
            duration = video.get("contentDetails", {}).get("duration", "")
            if self._is_short_duration(duration):
                short_info = self._extract_short_info(video)
                shorts_data.append(short_info)

        print(f"✅ Found {len(shorts_data)} Scooby Doo shorts")
        return shorts_data

    def _is_short_duration(self, duration: str) -> bool:
        """Check if video duration is maximum 8 seconds (ultra-short clips)"""
        if not duration:
            return False

        # Parse ISO 8601 duration (PT1M30S = 1 minute 30 seconds)
        import re
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if not match:
            return False

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        total_seconds = hours * 3600 + minutes * 60 + seconds
        return total_seconds <= 8  # Maximum 8 seconds as per requirements

    def _extract_short_info(self, video: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant information from video data"""
        snippet = video.get("snippet", {})
        statistics = video.get("statistics", {})
        content_details = video.get("contentDetails", {})
        status = video.get("status", {})

        # Get best thumbnail
        thumbnails = snippet.get("thumbnails", {})
        thumbnail_url = None
        for quality in ["maxres", "high", "medium", "default"]:
            if quality in thumbnails:
                thumbnail_url = thumbnails[quality]["url"]
                break

        short_url = f"https://www.youtube.com/shorts/{video['id']}"

        return {
            "video_id": video["id"],
            "channel_id": snippet.get("channelId", ""),  # Add channel ID for premium channel detection
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt", ""),
            "duration": content_details.get("duration", ""),
            "view_count": int(statistics.get("viewCount", 0)),
            "like_count": int(statistics.get("likeCount", 0)) if statistics.get("likeCount") else 0,
            "thumbnail_url": thumbnail_url,
            "url_watch": f"https://www.youtube.com/watch?v={video['id']}",
            "url_embed": f"https://www.youtube.com/embed/{video['id']}",
            "url_short": short_url,  # YouTube shorts URL - must start with https://www.youtube.com/shorts/
            "license": status.get("license", "youtube"),
            "tags": snippet.get("tags", []),
        }

    def search_scooby_shorts(self) -> List[Dict[str, Any]]:
        """Search for Daphne Scooby Doo quotes - ONLY YouTube shorts with strict validation"""
        print(f"🎬 Searching YouTube shorts for: '{YOUTUBE_SEARCH_QUERY}'")

        # Single focused search for Daphne Scooby Doo quotes (only shorts)
        all_shorts = self.search_shorts(YOUTUBE_SEARCH_QUERY, max_results=YOUTUBE_MAX_RESULTS)  # Get more to filter

        # Enhanced deduplication with multiple checks
        unique_shorts = []
        seen_ids = set()
        seen_titles = set()

        for short in all_shorts:
            video_id = short["video_id"]
            title = short["title"].lower().strip()

            # Skip if we've seen this video ID
            if video_id in seen_ids:
                print(f"⏭️ Skipping duplicate video ID: {video_id}")
                continue

            # Skip if we've seen a very similar title (basic fuzzy dedupe)
            title_words = set(title.split())
            is_duplicate_title = False
            for seen_title in seen_titles:
                seen_words = set(seen_title.split())
                # If 80% of words overlap, consider it a duplicate
                if len(title_words) > 0 and len(seen_words) > 0:
                    overlap = len(title_words.intersection(seen_words))
                    if overlap / len(title_words) > 0.8 and overlap / len(seen_words) > 0.8:
                        is_duplicate_title = True
                        print(f"⏭️ Skipping similar title: '{title[:50]}...' (similar to existing)")
                        break

            if is_duplicate_title:
                continue

            # STRICT validation: ensure it's actually a YouTube short
            # YouTube shorts have URLs starting with https://www.youtube.com/shorts/
            short_url = short.get("url_short", "")
            if not short_url.startswith("https://www.youtube.com/shorts/"):
                print(f"⏭️ Skipping non-short video: {video_id} (URL: {short_url})")
                continue

            # Double-check it's actually a short (should be due to videoDuration filter, but be safe)
            if not self._is_short_duration(short.get("duration", "")):
                print(f"⏭️ Skipping non-short video: {video_id} (duration: {short.get('duration', 'unknown')})")
                continue

            # Content validation: ensure they contain Daphne/Scooby related keywords
            title_desc = (short["title"] + " " + short.get("description", "")).lower()
            daphne_keywords = ["daphne", "scooby", "quote", "quotes", "line", "lines", "dialogue", "sarah michelle gellar"]
            if not any(keyword in title_desc for keyword in daphne_keywords):
                print(f"⏭️ Skipping non-Daphne video: {video_id} - {short['title'][:50]}...")
                continue

            # This is a validated Daphne Scooby Doo quote short
            unique_shorts.append(short)
            seen_ids.add(video_id)
            seen_titles.add(title)

        # Sort by view count (highest first) and ensure they're all shorts about Daphne quotes
        unique_shorts.sort(key=lambda x: x.get("view_count", 0), reverse=True)

        print(f"🎯 Found {len(all_shorts)} total results → {len(unique_shorts)} validated Daphne Scooby Doo quote shorts")
        print("✅ All results are YouTube shorts from: https://www.youtube.com/shorts/")

        return unique_shorts

    def resolve_channel_handle(self, handle: str) -> str:
        """
        Resolve a YouTube channel handle (e.g., @BoomerangUK) to channel ID
        """
        try:
            # First try searching for the handle
            search_request = self.youtube.search().list(
                q=handle,
                part="id,snippet",
                type="channel",
                maxResults=1,
            )

            search_response = search_request.execute()
            items = search_response.get("items", [])

            if items:
                channel_id = items[0]["id"]["channelId"]
                return channel_id

        except Exception as e:
            print(f"⚠️ Error resolving handle {handle}: {e}")

        return None

    def get_premium_scooby_channels(self) -> List[str]:
        """
        Get channel IDs for the premium Scooby Doo channels specified by user
        """
        print("🎯 Getting premium Scooby Doo channel IDs...")

        premium_handles = [
            "@BoomerangUK",
            "@PixaWaveStudio",
            "@hbomaxfamily",
            "@GenerationWB"
        ]

        channel_ids = []

        for handle in premium_handles:
            print(f"🔍 Resolving {handle}...")
            channel_id = self.resolve_channel_handle(handle)

            if channel_id:
                channel_ids.append(channel_id)
                print(f"   ✅ Found: {channel_id}")
            else:
                print(f"   ❌ Could not resolve: {handle}")

        # Remove duplicates
        unique_channels = list(set(channel_ids))
        print(f"✅ Resolved {len(unique_channels)} premium Scooby channels")
        return unique_channels

    def find_scooby_channels(self, max_channels: int = 10) -> List[str]:
        """
        Find YouTube channels related to Scooby Doo content
        Returns list of channel IDs
        """
        print("🔍 Finding Scooby Doo related channels...")

        channels = []

        # First, get the premium channels specified by user
        premium_channels = self.get_premium_scooby_channels()
        channels.extend(premium_channels)

        # Then search for additional channels if needed
        if len(channels) < max_channels:
            search_terms = [
                "scooby doo",
                "scooby doo official",
                "scooby doo clips",
                "scooby doo quotes",
                "daphne scooby doo"
            ]

            seen_channel_ids = set(channels)  # Include premium channels

            for term in search_terms:
                try:
                    search_request = self.youtube.search().list(
                        q=term,
                        part="id,snippet",
                        type="channel",
                        maxResults=3,  # Get fewer additional channels
                        order="relevance",
                    )

                    search_response = search_request.execute()

                    for item in search_response.get("items", []):
                        channel_id = item["id"]["channelId"]
                        channel_title = item["snippet"]["title"].lower()

                        # Filter for Scooby-related channels
                        scooby_keywords = ["scooby", "daphne", "velma", "shaggy", "fred", "mystery"]
                        if any(keyword in channel_title for keyword in scooby_keywords) and channel_id not in seen_channel_ids:
                            channels.append(channel_id)
                            seen_channel_ids.add(channel_id)

                            if len(channels) >= max_channels:
                                break

                    if len(channels) >= max_channels:
                        break

                except Exception as e:
                    print(f"⚠️ Error searching for channels with term '{term}': {e}")
                    continue

        print(f"✅ Found {len(channels)} Scooby Doo related channels (including {len(premium_channels)} premium)")
        return channels[:max_channels]

    def channel_id_to_shorts_playlist(self, channel_id: str) -> str:
        """
        Convert channel ID to shorts playlist ID
        UC[channel_id] -> UUSH[channel_id]
        """
        if channel_id.startswith("UC"):
            return YOUTUBE_SHORTS_PREFIX + channel_id[2:]
        else:
            # Handle other channel ID formats if needed
            return channel_id

    def search_channel_videos(self, channel_id: str, query: str = "", max_results: int = 20) -> List[Dict[str, Any]]:
        """
        Search for videos within a specific channel using channelId parameter
        This is more reliable than playlist-based search
        """
        videos = []

        try:
            # Search within specific channel
            search_request = self.youtube.search().list(
                q=query or YOUTUBE_SEARCH_QUERY,
                part="id,snippet",
                type="video",
                channelId=channel_id,  # Search only within this channel
                maxResults=max_results,
                order="relevance",
                safeSearch="moderate",
                videoDuration="short",  # Filter for short videos
            )

            search_response = search_request.execute()
            video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]

            if video_ids:
                # Get detailed video information
                videos_request = self.youtube.videos().list(
                    part="snippet,contentDetails,statistics,status",
                    id=",".join(video_ids),
                )

                videos_response = videos_request.execute()

                for video_data in videos_response.get("items", []):
                    video_info = self._extract_short_info(video_data)

                    # Apply strict content and duration validation
                    if self._validate_daphne_content(video_info):
                        videos.append(video_info)

        except Exception as e:
            print(f"⚠️ Error searching channel {channel_id}: {e}")

        return videos

    def search_channel_shorts_playlist(self, playlist_id: str, query: str = "", max_results: int = 20) -> List[Dict[str, Any]]:
        """
        Search for videos in a specific YouTube playlist (like a channel's shorts)
        """
        shorts = []

        try:
            # Get playlist items (videos in the playlist)
            playlist_request = self.youtube.playlistItems().list(
                part="id,snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=max_results,
            )

            playlist_response = playlist_request.execute()

            for item in playlist_response.get("items", []):
                video_id = item["contentDetails"]["videoId"]
                snippet = item["snippet"]

                # Get full video details to check duration and other metadata
                try:
                    video_details = self.youtube.videos().list(
                        part="contentDetails,status,snippet",
                        id=video_id
                    ).execute()

                    if video_details.get("items"):
                        video_data = video_details["items"][0]
                        short_info = self._extract_short_info(video_data)

                        # Apply content filtering
                        if self._validate_daphne_content(short_info):
                            shorts.append(short_info)

                except Exception as e:
                    print(f"⚠️ Error getting details for video {video_id}: {e}")
                    continue

        except Exception as e:
            print(f"⚠️ Error searching playlist {playlist_id}: {e}")

        return shorts

    def _validate_daphne_content(self, video_info: Dict[str, Any]) -> bool:
        """
        Validate that video content is related to Daphne Scooby Doo quotes
        """
        title_desc = (video_info["title"] + " " + video_info.get("description", "")).lower()

        # Must contain Daphne/Scooby related keywords
        daphne_keywords = ["daphne", "scooby", "quote", "quotes", "line", "lines", "dialogue", "sarah michelle gellar"]
        has_keywords = any(keyword in title_desc for keyword in daphne_keywords)

        # Must be a short (under 60 seconds)
        is_short = self._is_short_duration(video_info.get("duration", ""))

        # Must have shorts URL format
        has_shorts_url = video_info.get("url_short", "").startswith("https://www.youtube.com/shorts/")

        return has_keywords and is_short and has_shorts_url

    def search_scooby_shorts_advanced(self) -> List[Dict[str, Any]]:
        """
        Advanced search prioritizing premium channels and using channel-specific searches
        """
        print("🎬 Advanced Scooby Doo Shorts search prioritizing premium channels...")

        all_shorts = []

        # Step 1: Search premium channels specifically for "daphne scooby doo quotes"
        print("🌟 Step 1: Searching premium channels for exact query...")
        premium_channels = self.get_premium_scooby_channels()

        # First try with exact query, then fall back to broader Scooby search
        search_queries = [YOUTUBE_SEARCH_QUERY, "scooby doo", "daphne scooby"]

        for channel_id in premium_channels:
            print(f"🎯 Searching premium channel {channel_id}...")
            channel_found_any = False

            for query in search_queries:
                if channel_found_any:
                    break  # Don't search further queries for this channel if we found results

                try:
                    channel_videos = self.search_channel_videos(
                        channel_id,
                        query=query,
                        max_results=5 if query == YOUTUBE_SEARCH_QUERY else 3  # More results for exact query
                    )

                    if channel_videos:
                        all_shorts.extend(channel_videos)
                        print(f"   → Found {len(channel_videos)} videos with query '{query}'")
                        channel_found_any = True

                except Exception as e:
                    print(f"   → Error searching channel {channel_id} with '{query}': {e}")
                    continue

            if not channel_found_any:
                print(f"   → No matching videos found in channel")

        # Step 2: Search additional Scooby channels if we need more content
        if len(all_shorts) < 10:  # If we don't have enough from premium channels
            print("🔍 Step 2: Searching additional Scooby channels...")
            additional_channels = self.find_scooby_channels(max_channels=20)
            premium_set = set(premium_channels)

            for channel_id in additional_channels:
                if channel_id not in premium_set:  # Skip premium channels we already searched
                    try:
                        channel_videos = self.search_channel_videos(
                            channel_id,
                            query=YOUTUBE_SEARCH_QUERY,
                            max_results=5
                        )
                        all_shorts.extend(channel_videos)
                        print(f"   → Additional channel {channel_id}: {len(channel_videos)} videos")

                    except Exception as e:
                        print(f"   → Error searching additional channel {channel_id}: {e}")
                        continue

        # Step 3: Fallback to regular search if still need more
        if len(all_shorts) < 5:
            print("🔄 Step 3: Supplementing with general search...")
            regular_shorts = self.search_shorts(YOUTUBE_SEARCH_QUERY, max_results=15)
            all_shorts.extend(regular_shorts)

        # Enhanced deduplication with strict validation
        unique_shorts = []
        seen_ids = set()
        seen_titles = set()

        for short in all_shorts:
            video_id = short["video_id"]
            title = short["title"].lower().strip()

            # Skip if we've seen this video ID
            if video_id in seen_ids:
                continue

            # Skip if we've seen a very similar title
            title_words = set(title.split())
            is_duplicate_title = False
            for seen_title in seen_titles:
                seen_words = set(seen_title.split())
                overlap = len(title_words.intersection(seen_words))
                if len(title_words) > 0 and len(seen_words) > 0:
                    if overlap / len(title_words) > 0.8 and overlap / len(seen_words) > 0.8:
                        is_duplicate_title = True
                        break

            if is_duplicate_title:
                continue

            # Strict validation: must be 8 seconds or less, YouTube shorts, and Daphne content
            if self._validate_daphne_content(short):
                unique_shorts.append(short)
                seen_ids.add(video_id)
                seen_titles.add(title)

        # Sort by view count (highest first) - premium channels get priority
        def sort_key(video):
            base_score = video.get("view_count", 0)
            # Boost premium channel videos
            premium_channel_ids = set(premium_channels)
            if video.get("channel_id") in premium_channel_ids:
                base_score *= 2  # Double the score for premium channels
            return base_score

        unique_shorts.sort(key=sort_key, reverse=True)

        print(f"🎯 Advanced search complete: Found {len(all_shorts)} total → {len(unique_shorts)} validated ultra-short Daphne Scooby Doo clips (≤8 seconds)")
        return unique_shorts


def main():
    """Test the YouTube search functionality"""
    searcher = YouTubeSearcher()

    print("🔍 Testing advanced Scooby Doo Shorts search...")
    shorts = searcher.search_scooby_shorts_advanced()

    # Save results to JSON for inspection
    with open("scooby_shorts_advanced_test.json", "w") as f:
        json.dump(shorts, f, indent=2)

    print(f"💾 Saved {len(shorts)} shorts to scooby_shorts_advanced_test.json")

    # Print summary
    for i, short in enumerate(shorts[:3], 1):  # Show first 3
        print(f"{i}. {short['title'][:50]}... ({short['video_id']})")
        print(f"   URL: {short['url_short']}")

    # Show some channel info if available
    channels_found = set()
    for short in shorts:
        if 'channel_title' in short:
            channels_found.add(short['channel_title'])

    print(f"\n📺 Found content from {len(channels_found)} different channels")
    if channels_found:
        print("Channels:", list(channels_found)[:3], "..." if len(channels_found) > 3 else "")


if __name__ == "__main__":
    main()
