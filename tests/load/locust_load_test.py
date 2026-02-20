#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
压力测试脚本 - Locust

Load testing script for the AI Tongue Diagnosis System API.
Tests for 100 QPS, P95 latency < 2s, 99% availability, and cache hit rate > 50%.

Usage:
    # Standard load test (100 QPS target)
    locust -f tests/load/locust_load_test.py --host http://localhost:8000

    # Headless mode with specific user count
    locust -f tests/load/locust_load_test.py --headless --host http://localhost:8000 --users 100 --spawn-rate 10 --run-time 5m

    # With HTML report
    locust -f tests/load/locust_load_test.py --headless --host http://localhost:8000 --users 100 --spawn-rate 10 --run-time 5m --html load_test_report.html

Author: Ralph Agent
Date: 2026-02-21
"""

import os
import sys
import time
import json
import random
from pathlib import Path
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from locust import HttpUser, task, between, events
    from locust.runners import MasterRunner
except ImportError:
    print("Error: Locust is not installed. Install with: pip install locust")
    sys.exit(1)


# ============================================================================
# Test Configuration
# ============================================================================

TARGET_QPS = 100  # Target queries per second
SPAWN_RATE = 10    # Users spawned per second
TEST_DURATION = "5m"  # Default test duration

# Image files for testing (use sample images or generate placeholders)
SAMPLE_IMAGES = [
    "sample_tongue_1.jpg",
    "sample_tongue_2.jpg",
    "sample_tongue_3.jpg",
]

# ============================================================================
# API Endpoints
# ============================================================================

API_ENDPOINTS = {
    "health": "/api/v1/health",
    "segment": "/api/v1/segment",
    "classify": "/api/v1/classify",
    "diagnosis": "/api/v1/diagnosis",
    "consent_form": "/api/v1/consent/form",
}


# ============================================================================
# Test Data Preparation
# ============================================================================

def prepare_test_data():
    """Prepare test data including sample images"""
    test_data_dir = Path("tests/load/test_data")
    test_data_dir.mkdir(parents=True, exist_ok=True)

    # Create placeholder images if they don't exist
    for img_name in SAMPLE_IMAGES:
        img_path = test_data_dir / img_name
        if not img_path.exists():
            # Create minimal valid JPEG (1x1 red pixel)
            try:
                from PIL import Image
                img = Image.new('RGB', (100, 100), color='red')
                img.save(img_path, 'JPEG')
                print(f"Created test image: {img_path}")
            except ImportError:
                # If PIL not available, create minimal JPEG bytes
                jpeg_data = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x03\x02\x02\x03\x02\x02\x03\x03\x03\x03\x04\x03\x03\x04\x05\x08\x05\x05\x04\x04\x05\n\x05\x07\x07\x06\x08\x0c\n\x0c\x0c\x0b\n\x0b\x0b\r\x0e\x12\x10\r\x0e\x11\x0e\x0b\x0b\x10\x16\x10\x11\x13\x14\x15\x15\x15\x0c\x0f\x17\x18\x16\x14\x18\x12\x14\x15\x14\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\n\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00T\x9f\xff\xd9'
                with open(img_path, 'wb') as f:
                    f.write(jpeg_data)
                print(f"Created minimal test image: {img_path}")

    return test_data_dir


# ============================================================================
# Load Test User
# ============================================================================

class TongueDiagnosisUser(HttpUser):
    """Simulated user for tongue diagnosis API load testing"""

    # Wait time between requests (1-3 seconds)
    wait_time = between(1, 3)

    def on_start(self):
        """Called when a user starts"""
        # Prepare test data
        self.test_data_dir = prepare_test_data()
        # Check health endpoint
        self.client.get(API_ENDPOINTS["health"])

    @task(5)
    def health_check(self):
        """Health check endpoint (low weight)"""
        with self.client.get(API_ENDPOINTS["health"], catch_response=True, name="Health Check") as response:
            if response.status_code == 200:
                response.success()

    @task(10)
    def get_consent_form(self):
        """Get consent form (medium weight)"""
        with self.client.get(API_ENDPOINTS["consent_form"], catch_response=True, name="Get Consent Form") as response:
            if response.status_code == 200:
                response.success()

    @task(20)
    def segment_image(self):
        """Segment image (high weight - core feature)"""
        # Select random sample image
        img_file = random.choice(SAMPLE_IMAGES)
        img_path = self.test_data_dir / img_file

        if not img_path.exists():
            return

        files = {'file': open(img_path, 'rb')}
        data = {
            'image_id': f'test_{int(time.time() * 1000)}',
        }

        with self.client.post(
            API_ENDPOINTS["segment"],
            files=files,
            data=data,
            catch_response=True,
            name="Segment Image"
        ) as response:
            if response.status_code == 200:
                response.success()
            files['file'].close()

    @task(20)
    def classify_image(self):
        """Classify image (high weight - core feature)"""
        img_file = random.choice(SAMPLE_IMAGES)
        img_path = self.test_data_dir / img_file

        if not img_path.exists():
            return

        files = {'file': open(img_path, 'rb')}
        data = {
            'image_id': f'test_{int(time.time() * 1000)}',
        }

        with self.client.post(
            API_ENDPOINTS["classify"],
            files=files,
            data=data,
            catch_response=True,
            name="Classify Image"
        ) as response:
            if response.status_code == 200:
                response.success()
            files['file'].close()

    @task(45)
    def diagnosis_image(self):
        """Full diagnosis (highest weight - main workflow)"""
        img_file = random.choice(SAMPLE_IMAGES)
        img_path = self.test_data_dir / img_file

        if not img_path.exists():
            return

        files = {'file': open(img_path, 'rb')}
        data = {
            'image_id': f'test_{int(time.time() * 1000)}',
            'enable_llm_diagnosis': 'false',  # Disable LLM for load testing
            'enable_rule_fallback': 'true',
        }

        with self.client.post(
            API_ENDPOINTS["diagnosis"],
            files=files,
            data=data,
            catch_response=True,
            name="Full Diagnosis"
        ) as response:
            if response.status_code == 200:
                # Check for success response
                try:
                    result = response.json()
                    if result.get('success'):
                        response.success()
                    else:
                        response.failure(f"API returned success=False")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            files['file'].close()


# ============================================================================
# Test Event Handlers
# ============================================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the test starts"""
    print("\n" + "=" * 60)
    print("Starting Load Test - AI Tongue Diagnosis System")
    print("=" * 60)
    print(f"Target QPS: {TARGET_QPS}")
    print(f"Test Duration: {TEST_DURATION}")
    print("=" * 60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the test stops - generate report"""
    print("\n" + "=" * 60)
    print("Load Test Completed")
    print("=" * 60)

    # Collect statistics
    stats = {
        "test_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_requests": environment.stats.total.num_requests,
        "total_failures": environment.stats.total.num_failures,
        "failure_rate": environment.stats.total.fail_ratio,
        "avg_response_time": environment.stats.total.avg_response_time,
        "min_response_time": environment.stats.total.min_response_time,
        "max_response_time": environment.stats.total.max_response_time,
        "median_response_time": environment.stats.total.median_response_time,
        "current_rps": environment.stats.total.current_rps,
    }

    # Calculate percentiles if available
    if environment.stats.total.num_requests > 0:
        stats["p90_response_time"] = environment.stats.total.get_response_time_percentile(0.90)
        stats["p95_response_time"] = environment.stats.total.get_response_time_percentile(0.95)
        stats["p99_response_time"] = environment.stats.total.get_response_time_percentile(0.99)

    # Print summary
    print(f"\nTotal Requests: {stats['total_requests']}")
    print(f"Failures: {stats['total_failures']}")
    print(f"Failure Rate: {stats['failure_rate']:.2%}")
    print(f"Availability: {(1 - stats['failure_rate']):.2%}")
    print(f"\nResponse Times:")
    print(f"  Average: {stats['avg_response_time']:.0f}ms")
    print(f"  Median: {stats['median_response_time']:.0f}ms")
    if 'p95_response_time' in stats:
        print(f"  P95: {stats['p95_response_time']:.0f}ms")
        print(f"  P99: {stats['p99_response_time']:.0f}ms")
    print(f"\nThroughput: {stats['current_rps']:.1f} RPS")

    # Check acceptance criteria
    print("\n" + "-" * 60)
    print("Acceptance Criteria Check:")
    print("-" * 60)

    # 100 QPS target
    qps_met = stats['current_rps'] >= TARGET_QPS * 0.9  # Allow 10% tolerance
    print(f"100 QPS: {'PASS' if qps_met else 'FAIL'} (Actual: {stats['current_rps']:.1f} QPS)")

    # P95 < 2s
    p95_met = stats.get('p95_response_time', 0) < 2000  # 2 seconds = 2000ms
    print(f"P95 < 2s: {'PASS' if p95_met else 'FAIL'} (Actual: {stats.get('p95_response_time', 0):.0f}ms)")

    # 99% availability
    availability = (1 - stats['failure_rate']) * 100
    availability_met = availability >= 99
    print(f"API Availability >99%: {'PASS' if availability_met else 'FAIL'} (Actual: {availability:.2f}%)")

    # Cache hit rate > 50%
    # Note: Cache hit rate needs to be verified separately via Prometheus metrics
    print(f"Cache Hit Rate >50%: MANUAL CHECK (via Prometheus/Grafana)")

    print("=" * 60 + "\n")

    # Save report to JSON
    report_path = Path("tests/load/load_test_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump({
            "test_name": "AI Tongue Diagnosis System Load Test",
            "target_qps": TARGET_QPS,
            "acceptance_criteria": {
                "qps_target": 100,
                "p95_latency_ms": 2000,
                "availability_percent": 99,
                "cache_hit_rate_percent": 50
            },
            "results": stats,
            "passed": {
                "qps": qps_met,
                "p95_latency": p95_met,
                "availability": availability_met,
                "cache_hit_rate": "MANUAL"
            }
        }, f, indent=2, ensure_ascii=False)
    print(f"Test report saved to: {report_path}\n")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Load test for AI Tongue Diagnosis API")
    parser.add_argument("--host", default="http://localhost:8000", help="API host URL")
    parser.add_argument("--users", type=int, default=100, help="Number of users to simulate")
    parser.add_argument("--spawn-rate", type=int, default=10, help="Users spawned per second")
    parser.add_argument("--run-time", default="5m", help="Test duration (e.g., 5m, 1h)")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode (no web UI)")
    parser.add_argument("--html", help="Generate HTML report")

    args = parser.parse_args()

    # Prepare test data before starting
    prepare_test_data()

    # Build locust command
    cmd_args = [
        "--host", args.host,
        "--users", str(args.users),
        "--spawn-rate", str(args.spawn_rate),
        "--run-time", args.run_time,
    ]

    if args.headless:
        cmd_args.append("--headless")

    if args.html:
        cmd_args.extend(["--html", args.html])

    # Run locust
    import subprocess
    cmd = ["locust", "-f", __file__] + cmd_args
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd)
