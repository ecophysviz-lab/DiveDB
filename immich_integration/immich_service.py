"""
Immich Service - Integration with Immich photo management system

Provides functionality to:
- Search for media assets by dataset ID (album name)
- Retrieve detailed metadata for specific media assets
- Generate playback URLs for Dash dashboard integration
"""

import logging
import os
from typing import Dict, List, Optional, Literal, Union

import requests


class ImmichService:
    """Immich integration service for media asset management"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize Immich service client

        Args:
            api_key: Immich API key (defaults to IMMICH_API_KEY env var)
            base_url: Immich API base URL (defaults to IMMICH_BASE_URL env var)
        """
        self.api_key = api_key or os.getenv("IMMICH_API_KEY")
        self.base_url = (base_url or os.getenv("IMMICH_BASE_URL", "")).rstrip("/")

        if not self.api_key:
            raise ValueError(
                "IMMICH_API_KEY must be provided via parameter or environment variable"
            )
        if not self.base_url:
            raise ValueError(
                "IMMICH_BASE_URL must be provided via parameter or environment variable"
            )

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
            }
        )

        logging.info(f"Initialized ImmichService with base URL: {self.base_url}")

    def find_media_by_deployment_id(
        self,
        deployment_id: str,
        media_type: Optional[Literal["IMAGE", "VIDEO"]] = None,
        shared: bool = True,
    ) -> Dict[str, Union[List[Dict], str]]:
        """
        Find media assets associated with a deployment ID (album name)

        Args:
            deployment_id: Deployment ID to search for (matches album name)
            media_type: Filter by media type ("IMAGE" or "VIDEO"), None for all
            shared: Search in shared albums (default: True)

        Returns:
            Dict with 'success' status, 'data' list of assets, or 'error' message
        """
        try:
            # Get all albums (shared or owned)
            albums_response = self.session.get(
                f"{self.base_url}/albums", params={"shared": str(shared).lower()}
            )

            if not albums_response.ok:
                return {
                    "success": False,
                    "error": f"Failed to fetch albums: {albums_response.status_code} {albums_response.text}",
                }

            albums = albums_response.json()

            # Find album matching deployment_id
            target_album = None
            for album in albums:
                if album.get("albumName", "").strip() == deployment_id.strip():
                    target_album = album
                    break

            if not target_album:
                return {
                    "success": True,
                    "data": [],
                    "message": f"No album found with name '{deployment_id}'",
                }

            album_id = target_album["id"]
            logging.info(f"Found album '{deployment_id}' with ID: {album_id}")

            # Get assets from the album
            album_details_response = self.session.get(
                f"{self.base_url}/albums/{album_id}"
            )

            if not album_details_response.ok:
                return {
                    "success": False,
                    "error": f"Failed to fetch album details: {album_details_response.status_code} {album_details_response.text}",
                }

            album_details = album_details_response.json()
            assets = album_details.get("assets", [])

            # Filter by media type if specified
            if media_type:
                assets = [asset for asset in assets if asset.get("type") == media_type]

            logging.info(f"Found {len(assets)} assets in album '{deployment_id}'")

            return {
                "success": True,
                "data": assets,
                "album_info": {
                    "id": album_id,
                    "name": target_album.get("albumName"),
                    "asset_count": len(assets),
                },
            }

        except requests.exceptions.RequestException as e:
            logging.error(
                f"Network error searching for deployment '{deployment_id}': {str(e)}"
            )
            return {"success": False, "error": f"Network error: {str(e)}"}
        except Exception as e:
            logging.error(
                f"Unexpected error searching for deployment '{deployment_id}': {str(e)}"
            )
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    def get_media_details(self, asset_id: str) -> Dict[str, Union[Dict, str]]:
        """
        Get detailed metadata and playback URLs for a specific media asset

        Args:
            asset_id: Unique identifier for the media asset

        Returns:
            Dict with 'success' status, 'data' dict with metadata and URLs, or 'error' message

            On success, 'data' contains:
            - metadata: Asset details (dates, tags, EXIF, etc.)
            - urls: Playback URLs (original, thumbnail, preview)
        """
        try:
            # Get asset details
            asset_response = self.session.get(f"{self.base_url}/assets/{asset_id}")

            if not asset_response.ok:
                return {
                    "success": False,
                    "error": f"Failed to fetch asset details: {asset_response.status_code} {asset_response.text}",
                }

            asset_data = asset_response.json()

            # Extract metadata
            metadata = {
                "id": asset_data.get("id"),
                "type": asset_data.get("type"),  # IMAGE or VIDEO
                "original_filename": asset_data.get("originalFileName"),
                "file_created_at": asset_data.get("fileCreatedAt"),
                "file_modified_at": asset_data.get("fileModifiedAt"),
                "created_at": asset_data.get("createdAt"),
                "updated_at": asset_data.get("updatedAt"),
                "duration": asset_data.get("duration"),  # For videos
                "is_favorite": asset_data.get("isFavorite"),
                "is_archived": asset_data.get("isArchived"),
                "tags": asset_data.get("tags", []),
                "exif_info": asset_data.get("exifInfo", {}),
                "device_info": {
                    "make": asset_data.get("exifInfo", {}).get("make"),
                    "model": asset_data.get("exifInfo", {}).get("model"),
                },
                "location": {
                    "latitude": asset_data.get("exifInfo", {}).get("latitude"),
                    "longitude": asset_data.get("exifInfo", {}).get("longitude"),
                    "city": asset_data.get("exifInfo", {}).get("city"),
                    "state": asset_data.get("exifInfo", {}).get("state"),
                    "country": asset_data.get("exifInfo", {}).get("country"),
                },
            }

            # Generate playback URLs using proper Immich endpoints
            base_asset_url = f"{self.base_url}/assets/{asset_id}"
            urls = {
                "original": f"{base_asset_url}/original",
                "thumbnail": f"{base_asset_url}/thumbnail",
                "preview": f"{base_asset_url}/preview",
                "download": f"{base_asset_url}/download",
                # Use the correct playAssetVideo endpoint for video streaming
                "video_playback": f"{base_asset_url}/video/playback",
            }

            logging.info(f"Retrieved details for asset: {asset_id}")

            return {"success": True, "data": {"metadata": metadata, "urls": urls}}

        except requests.exceptions.RequestException as e:
            logging.error(f"Network error fetching asset '{asset_id}': {str(e)}")
            return {"success": False, "error": f"Network error: {str(e)}"}
        except Exception as e:
            logging.error(f"Unexpected error fetching asset '{asset_id}': {str(e)}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    def create_asset_share_link(
        self, asset_id: str, expires_hours: int = 4
    ) -> Dict[str, Union[bool, str, Dict]]:
        """
        Create a temporary shared link for a specific asset

        Args:
            asset_id: The asset ID to create a share link for
            expires_hours: Number of hours until the share link expires (default: 4)

        Returns:
            Dictionary with success status and share data or error message
        """
        try:
            # Calculate expiration time
            from datetime import datetime, timedelta

            expiration = datetime.utcnow() + timedelta(hours=expires_hours)

            payload = {
                "type": "INDIVIDUAL",
                "assetIds": [asset_id],  # Array of asset IDs for individual sharing
                "expiresAt": expiration.isoformat() + "Z",  # ISO format with Z for UTC
                "allowUpload": False,
                "allowDownload": True,
                "showMetadata": True,
                "description": f"Temporary share for DiveDB asset - expires in {expires_hours} hours",
            }

            response = self.session.post(f"{self.base_url}/shared-links", json=payload)

            if response.status_code == 201:
                share_data = response.json()
                logging.info(
                    f"Created share link for asset {asset_id}, expires in {expires_hours} hours"
                )
                return {
                    "success": True,
                    "share_data": {
                        "key": share_data.get("key"),
                        "id": share_data.get("id"),
                        "expires": expiration.isoformat(),
                    },
                }
            else:
                logging.error(
                    f"Failed to create share link for asset {asset_id}: {response.status_code} - {response.text}"
                )
                return {
                    "success": False,
                    "error": f"Failed to create share link: API returned {response.status_code}: {response.text}",
                }

        except Exception as e:
            logging.error(f"Error creating share link for asset {asset_id}: {str(e)}")
            return {"success": False, "error": f"Error creating share link: {str(e)}"}

    def test_connection(self) -> Dict[str, Union[bool, str]]:
        """
        Test the connection to Immich API

        Returns:
            Dict with 'success' status and optional 'error' message
        """
        try:
            response = self.session.get(
                f"{self.base_url}/albums", params={"shared": "true"}
            )

            if response.ok:
                albums = response.json()
                return {
                    "success": True,
                    "message": f"Connection successful. Found {len(albums)} shared albums.",
                }
            else:
                return {
                    "success": False,
                    "error": f"API returned {response.status_code}: {response.text}",
                }

        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Network error: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {str(e)}"}
