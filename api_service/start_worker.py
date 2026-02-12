#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Celery Worker启动脚本

Celery worker startup script for local development.
Provides easy command-line interface for running workers.

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def run_worker(
    loglevel: str = "info",
    concurrency: int = None,
    queue: str = None,
    beat: bool = False,
    flower: bool = False
):
    """
    Run Celery worker or beat

    Args:
        loglevel: Logging level (debug, info, warning, error)
        concurrency: Number of worker processes
        queue: Queue to consume from
        beat: Run Celery Beat instead of worker
        flower: Run Flower monitoring instead
    """
    # Build command
    if flower:
        cmd = [
            "celery", "-A", "api_service.worker.celery_app",
            "flower", "--port=5555",
            f"--broker={os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1')}"
        ]
    elif beat:
        cmd = [
            "celery", "-A", "api_service.worker.celery_app",
            "beat", "--loglevel=" + loglevel
        ]
    else:
        cmd = [
            "celery", "-A", "api_service.worker.celery_app",
            "worker", "--loglevel=" + loglevel
        ]

        # Add concurrency
        if concurrency:
            cmd.append(f"--concurrency={concurrency}")

        # Add queue
        if queue:
            cmd.extend(["-Q", queue])

    # Set UTF-8 encoding for Windows
    if sys.platform == "win32":
        os.environ["PYTHONIOENCODING"] = "utf-8"

    print(f"Starting: {' '.join(cmd)}")

    # Run command
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("\nShutting down worker...")
        sys.exit(0)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Celery Worker Startup Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start default worker
  python start_worker.py

  # Start worker with 4 processes
  python start_worker.py --concurrency 4

  # Start worker for specific queue
  python start_worker.py --queue segmentation

  # Start Celery Beat scheduler
  python start_worker.py --beat

  # Start Flower monitoring
  python start_worker.py --flower

  # Start with debug logging
  python start_worker.py --loglevel debug
        """
    )

    parser.add_argument(
        "--loglevel", "-l",
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="Logging level (default: info)"
    )

    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=None,
        help="Number of worker processes (default: CPU count)"
    )

    parser.add_argument(
        "--queue", "-q",
        type=str,
        default=None,
        help="Queue to consume from (default: all queues)"
    )

    parser.add_argument(
        "--beat", "-b",
        action="store_true",
        help="Run Celery Beat scheduler instead of worker"
    )

    parser.add_argument(
        "--flower", "-f",
        action="store_true",
        help="Run Flower monitoring instead of worker"
    )

    args = parser.parse_args()

    # Check for conflicting options
    if args.beat and args.flower:
        print("Error: Cannot specify both --beat and --flower")
        sys.exit(1)

    run_worker(
        loglevel=args.loglevel,
        concurrency=args.concurrency,
        queue=args.queue,
        beat=args.beat,
        flower=args.flower
    )


if __name__ == "__main__":
    main()
