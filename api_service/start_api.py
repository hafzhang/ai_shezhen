#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API服务启动脚本

Simple script to start the FastAPI server with proper configuration.

Usage:
    python start_api.py              # Start with default settings
    python start_api.py --port 9000  # Start on custom port
    python start_api.py --reload     # Start with auto-reload
"""

import os
import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="AI舌诊智能诊断系统 API服务")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="API监听地址 (默认: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API监听端口 (默认: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="启用自动重载（开发模式）"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Worker进程数 (默认: 1)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["critical", "error", "warning", "info", "debug"],
        help="日志级别 (默认: info)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("AI舌诊智能诊断系统 - API服务")
    print("=" * 60)
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Workers: {args.workers}")
    print(f"Log Level: {args.log_level}")
    print(f"Reload: {'是' if args.reload else '否'}")
    print("=" * 60)
    print()
    print("API文档:")
    print(f"  - Swagger UI: http://{args.host}:{args.port}/docs")
    print(f"  - ReDoc: http://{args.host}:{args.port}/redoc")
    print()
    print("健康检查:")
    print(f"  - GET http://{args.host}:{args.port}/api/v1/health")
    print()
    print("=" * 60)

    uvicorn.run(
        "api_service.app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level=args.log_level,
        access_log=True
    )


if __name__ == "__main__":
    main()
