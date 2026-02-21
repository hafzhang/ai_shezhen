#!/usr/bin/env python3
"""
服务健康监控脚本
Service health monitoring script for automatic failover

Usage:
    python health_monitor.py [--interval SECONDS] [--config PATH]

Author: Ralph Agent
Date: 2026-02-21
"""

import argparse
import json
import logging
import subprocess
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/shezhen_health_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """服务状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    service: str
    status: ServiceStatus
    response_time_ms: float
    status_code: Optional[int]
    message: str
    timestamp: float

    def to_dict(self):
        return {
            **asdict(self),
            'status': self.status.value,
            'timestamp_str': datetime.fromtimestamp(self.timestamp).isoformat()
        }


class HealthMonitor:
    """服务健康监控器"""

    def __init__(self, config_path: str = "/opt/shezhen/health_config.json"):
        self.config = self._load_config(config_path)
        self.failure_counts: Dict[str, int] = {}
        self.recovery_counts: Dict[str, int] = {}
        self.last_results: Dict[str, HealthCheckResult] = {}

    def _load_config(self, config_path: str) -> dict:
        """加载监控配置"""
        default_config = {
            "services": {
                "api": {
                    "url": "http://localhost:8000/health",
                    "timeout": 5,
                    "failure_threshold": 3,
                    "recovery_threshold": 2,
                    "container_name": "shezhen-api"
                },
                "redis": {
                    "url": "http://localhost:6379",
                    "timeout": 3,
                    "failure_threshold": 3,
                    "recovery_threshold": 2,
                    "container_name": "shezhen-redis"
                },
                "elasticsearch": {
                    "url": "http://localhost:9200/_cluster/health",
                    "timeout": 10,
                    "failure_threshold": 5,
                    "recovery_threshold": 3,
                    "container_name": "shezhen-elasticsearch"
                },
                "celery-worker": {
                    "url": "http://localhost:5555",
                    "timeout": 5,
                    "failure_threshold": 3,
                    "recovery_threshold": 2,
                    "container_name": "shezhen-celery-worker"
                }
            },
            "monitoring": {
                "interval_seconds": 30,
                "enable_auto_restart": True,
                "alert_on_failure": True,
                "alert_command": "logger -t shezhen-alert 'Service {service} is unhealthy'"
            }
        }

        config_path_obj = Path(config_path)
        if config_path_obj.exists():
            try:
                with open(config_path_obj) as f:
                    user_config = json.load(f)
                    # 合并配置
                    for key, value in user_config.items():
                        if key in default_config and isinstance(default_config[key], dict):
                            default_config[key].update(value)
                        else:
                            default_config[key] = value
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}, using defaults")

        return default_config

    def check_service(self, service_name: str) -> HealthCheckResult:
        """检查单个服务的健康状态"""
        config = self.config["services"].get(service_name)
        if not config:
            return HealthCheckResult(
                service=service_name,
                status=ServiceStatus.UNKNOWN,
                response_time_ms=0,
                status_code=None,
                message="Service not configured",
                timestamp=time.time()
            )

        url = config["url"]
        timeout = config["timeout"]

        try:
            start_time = time.time()
            response = requests.get(url, timeout=timeout)
            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return HealthCheckResult(
                    service=service_name,
                    status=ServiceStatus.HEALTHY,
                    response_time_ms=response_time,
                    status_code=200,
                    message="OK",
                    timestamp=time.time()
                )
            elif response.status_code >= 500:
                return HealthCheckResult(
                    service=service_name,
                    status=ServiceStatus.UNHEALTHY,
                    response_time_ms=response_time,
                    status_code=response.status_code,
                    message=f"Server error: HTTP {response.status_code}",
                    timestamp=time.time()
                )
            else:
                return HealthCheckResult(
                    service=service_name,
                    status=ServiceStatus.DEGRADED,
                    response_time_ms=response_time,
                    status_code=response.status_code,
                    message=f"HTTP {response.status_code}",
                    timestamp=time.time()
                )

        except requests.exceptions.Timeout:
            return HealthCheckResult(
                service=service_name,
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=timeout * 1000,
                status_code=None,
                message="Timeout",
                timestamp=time.time()
            )
        except requests.exceptions.ConnectionError as e:
            return HealthCheckResult(
                service=service_name,
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=0,
                status_code=None,
                message=f"Connection error: {str(e)}",
                timestamp=time.time()
            )
        except Exception as e:
            return HealthCheckResult(
                service=service_name,
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=0,
                status_code=None,
                message=f"Error: {str(e)}",
                timestamp=time.time()
            )

    def check_all_services(self) -> List[HealthCheckResult]:
        """检查所有服务的健康状态"""
        results = []
        for service_name in self.config["services"].keys():
            result = self.check_service(service_name)
            results.append(result)
            self.last_results[service_name] = result

            # 更新计数器
            if result.status == ServiceStatus.UNHEALTHY:
                self.failure_counts[service_name] = \
                    self.failure_counts.get(service_name, 0) + 1
                self.recovery_counts[service_name] = 0
            else:
                self.recovery_counts[service_name] = \
                    self.recovery_counts.get(service_name, 0) + 1
                threshold = self.config["services"][service_name]["recovery_threshold"]
                if self.recovery_counts[service_name] >= threshold:
                    self.failure_counts[service_name] = 0

        return results

    def should_trigger_failover(self, service_name: str) -> bool:
        """判断是否应该触发故障转移"""
        threshold = self.config["services"][service_name]["failure_threshold"]
        return self.failure_counts.get(service_name, 0) >= threshold

    def execute_failover(self, service_name: str):
        """执行故障转移 - 重启服务"""
        logger.warning(f"Executing failover for {service_name}...")

        config = self.config["services"].get(service_name)
        container_name = config.get("container_name") if config else None

        if not container_name:
            logger.error(f"No container_name configured for {service_name}")
            return

        try:
            # 重启 Docker 容器
            logger.info(f"Restarting container: {container_name}")
            subprocess.run(
                ["docker", "restart", container_name],
                check=True,
                capture_output=True
            )

            logger.info(f"Container {container_name} restarted successfully")

            # 发送告警
            if self.config["monitoring"]["alert_on_failure"]:
                self._send_alert(service_name, "restarted")

            # 重置计数器
            self.failure_counts[service_name] = 0

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restart {container_name}: {e}")
            self._send_alert(service_name, f"restart failed: {e}")

    def _send_alert(self, service_name: str, action: str):
        """发送告警通知"""
        alert_command = self.config["monitoring"].get("alert_command")
        if alert_command:
            try:
                cmd = alert_command.format(service=service_name, action=action)
                subprocess.run(cmd, shell=True, check=True)
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")

    def generate_report(self) -> dict:
        """生成健康状态报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "services": {},
            "summary": {
                "total": len(self.config["services"]),
                "healthy": 0,
                "degraded": 0,
                "unhealthy": 0,
                "unknown": 0
            }
        }

        for service_name, result in self.last_results.items():
            report["services"][service_name] = result.to_dict()
            report["summary"][result.status.value] += 1

        return report

    def run_monitoring_loop(self, interval_seconds: Optional[int] = None):
        """运行监控循环"""
        if interval_seconds is None:
            interval_seconds = self.config["monitoring"]["interval_seconds"]

        logger.info(f"Starting health monitoring loop (interval: {interval_seconds}s)")
        logger.info(f"Monitoring services: {list(self.config['services'].keys())}")
        logger.info(f"Auto-restart enabled: {self.config['monitoring']['enable_auto_restart']}")

        while True:
            try:
                # 检查所有服务
                results = self.check_all_services()

                # 记录状态
                for result in results:
                    if result.status == ServiceStatus.HEALTHY:
                        logger.debug(
                            f"{result.service}: HEALTHY "
                            f"({result.response_time_ms:.0f}ms)"
                        )
                    elif result.status == ServiceStatus.DEGRADED:
                        logger.warning(
                            f"{result.service}: DEGRADED - {result.message}"
                        )
                    else:
                        failure_count = self.failure_counts.get(result.service, 0)
                        logger.error(
                            f"{result.service}: UNHEALTHY - {result.message} "
                            f"(failures: {failure_count})"
                        )

                    # 检查是否需要故障转移
                    if self.should_trigger_failover(result.service):
                        logger.error(
                            f"Service {result.service} has failed "
                            f"{self.failure_counts[result.service]} times"
                        )

                        if self.config["monitoring"]["enable_auto_restart"]:
                            self.execute_failover(result.service)
                        else:
                            logger.warning(
                                f"Auto-restart disabled for {result.service}, "
                                f"manual intervention required"
                            )
                            self._send_alert(result.service, "manual intervention required")

                # 生成报告并保存
                report = self.generate_report()
                report_path = Path("/tmp/health_report.json")
                try:
                    with open(report_path, "w") as f:
                        json.dump(report, f, indent=2)
                except Exception as e:
                    logger.warning(f"Failed to save health report: {e}")

                # 等待下次检查
                time.sleep(interval_seconds)

            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                time.sleep(interval_seconds)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Service health monitoring for automatic failover"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Monitoring interval in seconds (default: from config or 30s)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="/opt/shezhen/health_config.json",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run health check once and exit"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate and display health report"
    )

    args = parser.parse_args()

    # 创建监控器
    monitor = HealthMonitor(config_path=args.config)

    if args.once or args.report:
        # 运行一次检查
        results = monitor.check_all_services()

        if args.report:
            report = monitor.generate_report()
            print(json.dumps(report, indent=2))
        else:
            for result in results:
                print(f"{result.service}: {result.status.value} - {result.message}")
    else:
        # 运行监控循环
        monitor.run_monitoring_loop(interval_seconds=args.interval)


if __name__ == "__main__":
    main()
