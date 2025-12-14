"""
Service for Just-in-Time Materialization of Assets.
Handles fetching bytes from S3 or RDS Blob and placing them in a deterministic container path.
"""
import os
import shutil
import boto3
from contextlib import contextmanager
from typing import Generator, Optional
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import select

from agent.db.models import Asset
# Constants
HOST_ASSET_ROOT = "/var/lib/publishing-worker/job_assets"
CONTAINER_ASSET_ROOT = "/job_assets"

class AssetMaterializerFactory:
    """Factory to get the correct materializer."""
    
    @staticmethod
    def get_materializer(session: Session, job_id: int):
        return AssetMaterializer(session, job_id)

class AssetMaterializer:
    def __init__(self, session: Session, job_id: int):
        self.session = session
        self.job_id = job_id
        self.host_job_dir = os.path.join(HOST_ASSET_ROOT, str(job_id))
        self.container_job_dir = os.path.join(CONTAINER_ASSET_ROOT, str(job_id))
        self._assets_materialized = []

    def materialize_asset(self, asset_id: int) -> str:
        """
        Materializes an asset to the host filesystem.
        Returns the absolute path inside the container.
        """
        asset = self.session.get(Asset, asset_id)
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")

        # 1. Create Host Directory (idempotent)
        os.makedirs(self.host_job_dir, mode=0o700, exist_ok=True)
        
        # 2. Determine Filename and Paths
        filename = asset.original_name
        # Sanitize filename if needed, but for V1 assume trusted internal input or simple valid chars
        host_path = os.path.join(self.host_job_dir, filename)
        container_path = os.path.join(self.container_job_dir, filename)
        
        if os.path.exists(host_path):
             logger.warning(f"Asset {asset_id} already materialized at {host_path}. Re-verifying.")
             if os.path.getsize(host_path) > 0:
                 self._assets_materialized.append(host_path)
                 return container_path
             # If empty/corrupt, proceed to overwrite

        # 3. Fetch Bytes
        logger.info(f"Materializing asset {asset_id} ({asset.storage_type}) to {host_path}")
        
        try:
            if asset.storage_type == "S3":
                self._download_from_s3(asset, host_path)
            elif asset.storage_type == "RDS_BLOB":
                self._stream_from_db(asset, host_path)
            else:
                raise ValueError(f"Unsupported storage_type: {asset.storage_type}")
                
            # 4. Validate
            if not os.path.exists(host_path) or os.path.getsize(host_path) == 0:
                 raise RuntimeError(f"Materialization failed: File {host_path} is empty or missing.")
            
            # (Optional) Checksum validation logic here
            
            self._assets_materialized.append(host_path)
            logger.info(f"Asset {asset_id} materialized successfully.")
            return container_path
            
        except Exception as e:
            # If fetch fails, we should probably delete the partial file
            if os.path.exists(host_path):
                os.remove(host_path)
            raise RuntimeError(f"Failed to materialize asset {asset_id}: {e}")

    def _download_from_s3(self, asset: Asset, target_path: str):
        if not asset.s3_bucket or not asset.s3_key:
             raise ValueError("Asset marked as S3 but missing bucket/key")
             
        s3 = boto3.client("s3")
        try:
             s3.download_file(asset.s3_bucket, asset.s3_key, target_path)
        except Exception as e:
             raise RuntimeError(f"S3 Download failed: {e}")

    def _stream_from_db(self, asset: Asset, target_path: str):
         # Streaming from DB Blob
         # For V1 with SQLAlchemy ORM and generic drivers, robust strict streaming of a single row's column 
         # without loading into RAM can be database dependent.
         # For `bytea` in Postgres (psycopg2) or `LONGBLOB` in MySQL, standard ORM access loads it.
         # However, if the blob fits in RAM (e.g. <50MB short video), direct write is acceptable for V1.
         # If we need strict streaming, we'd need raw cursor usage.
         # Given constraints (V1, likely short form usually), we will do generic fetch-write, 
         # but acknowledge the RAM implication.
         
         if not asset.blob_data:
             raise ValueError("Asset marked as RDS_BLOB but blob_data is empty")
             
         try:
             # NOTE: This loads blob into memory. For strictly "streamed from cursor", we need raw connection.
             # Implementing generic raw streaming is risky without knowing exact driver capabilities in this env.
             # We will accept memory load for V1 JIT bridge.
             with open(target_path, "wb") as f:
                 f.write(asset.blob_data)
         except Exception as e:
             raise RuntimeError(f"DB Blob Write failed: {e}")
             
    def cleanup(self):
        """Deterministically remove the job directory."""
        if os.path.exists(self.host_job_dir):
            try:
                logger.info(f"Cleaning up job assets at {self.host_job_dir}")
                shutil.rmtree(self.host_job_dir)
            except Exception as e:
                logger.error(f"Failed to cleanup job dir {self.host_job_dir}: {e}")

@contextmanager
def materialized_scope(session: Session, job_id: int) -> Generator[AssetMaterializer, None, None]:
    """Context manager for ensuring cleanup."""
    materializer = AssetMaterializer(session, job_id)
    try:
        yield materializer
    finally:
        materializer.cleanup()
