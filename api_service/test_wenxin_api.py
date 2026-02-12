"""
文心一言 API 测试脚本

此脚本用于测试文心一言 ERNIE-Speed API 的连通性和功能

使用方法:
    python api_service/test_wenxin_api.py

环境要求:
    - 设置 BAIDU_API_KEY 和 BAIDU_SECRET_KEY 环境变量
    - 或创建 .env 文件（参考 .env.example）
"""

import os
import sys
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime

# Windows console UTF-8 encoding wrapper for proper Unicode display
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    import requests
except ImportError:
    print("错误: 请安装 requests 库")
    print("安装命令: pip install requests")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    has_dotenv = True
except ImportError:
    has_dotenv = False
    print("警告: python-dotenv 未安装，将从环境变量读取配置")


class WenxinAPITester:
    """文心一言 API 测试类"""

    def __init__(self):
        self.base_url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop"
        self.api_key: Optional[str] = None
        self.secret_key: Optional[str] = None
        self.access_token: Optional[str] = None
        self.test_results: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "tests": []
        }

    def load_credentials(self) -> bool:
        """加载 API 凭证"""
        print("\n" + "="*60)
        print("步骤 1/5: 加载 API 凭证")
        print("="*60)

        # 尝试从 .env 文件加载
        if has_dotenv:
            env_path = os.path.join(os.path.dirname(__file__), ".env")
            if os.path.exists(env_path):
                load_dotenv(env_path)
                print(f"✓ 从 .env 文件加载配置")

        # 从环境变量读取
        self.api_key = os.getenv("BAIDU_API_KEY")
        self.secret_key = os.getenv("BAIDU_SECRET_KEY")

        if not self.api_key or not self.secret_key:
            print("✗ 错误: 未找到 API 凭证")
            print("\n请设置以下环境变量或在 .env 文件中配置:")
            print("  - BAIDU_API_KEY")
            print("  - BAIDU_SECRET_KEY")
            print("\n获取方式:")
            print("  1. 访问: https://cloud.baidu.com/product/wenxinworkshop")
            print("  2. 注册/登录百度云账号")
            print("  3. 开通千帆大模型平台服务")
            print("  4. 创建应用获取 API Key 和 Secret Key")
            return False

        # 验证凭证格式
        if len(self.api_key) < 10 or len(self.secret_key) < 10:
            print("✗ 错误: API 凭证格式不正确")
            print(f"  API Key 长度: {len(self.api_key)} (预期 > 10)")
            print(f"  Secret Key 长度: {len(self.secret_key)} (预期 > 10)")
            return False

        print(f"✓ API Key: {self.api_key[:8]}...{self.api_key[-4:]}")
        print(f"✓ Secret Key: {self.secret_key[:8]}...{self.secret_key[-4:]}")
        return True

    def get_access_token(self) -> bool:
        """获取 Access Token"""
        print("\n" + "="*60)
        print("步骤 2/5: 获取 Access Token")
        print("="*60)

        token_url = f"{self.base_url}/oauth/token"

        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }

        try:
            print("正在请求 Access Token...")
            response = requests.post(token_url, params=params, timeout=10)

            result = {
                "test": "get_access_token",
                "status_code": response.status_code,
                "success": False,
                "error": None
            }

            if response.status_code == 200:
                data = response.json()
                if "access_token" in data:
                    self.access_token = data["access_token"]
                    expires_in = data.get("expires_in", 2592000)
                    expires_days = expires_in / 86400

                    print(f"✓ Access Token 获取成功")
                    print(f"  Token: {self.access_token[:20]}...{self.access_token[-10:]}")
                    print(f"  有效期: {expires_in} 秒 ({expires_days:.1f} 天)")

                    result["success"] = True
                    result["expires_in"] = expires_in

                    self.test_results["tests"].append(result)
                    return True
                else:
                    error_msg = data.get("error_description", "未知错误")
                    print(f"✗ 错误: {error_msg}")
                    result["error"] = error_msg
            else:
                print(f"✗ HTTP 错误: {response.status_code}")
                result["error"] = f"HTTP {response.status_code}"

            self.test_results["tests"].append(result)
            return False

        except requests.exceptions.Timeout:
            print("✗ 错误: 请求超时")
            self.test_results["tests"].append({
                "test": "get_access_token",
                "status_code": None,
                "success": False,
                "error": "timeout"
            })
            return False
        except requests.exceptions.ConnectionError:
            print("✗ 错误: 网络连接失败")
            print("  请检查:")
            print("  1. 网络连接是否正常")
            print("  2. 防火墙是否允许访问 aip.baidubce.com")
            self.test_results["tests"].append({
                "test": "get_access_token",
                "status_code": None,
                "success": False,
                "error": "connection_error"
            })
            return False
        except Exception as e:
            print(f"✗ 错误: {str(e)}")
            self.test_results["tests"].append({
                "test": "get_access_token",
                "status_code": None,
                "success": False,
                "error": str(e)
            })
            return False

    def test_chat_completion(self) -> bool:
        """测试对话补全功能"""
        print("\n" + "="*60)
        print("步骤 3/5: 测试对话补全 (ERNIE-Speed)")
        print("="*60)

        chat_url = f"{self.base_url}/chat/ernie_speed"
        params = {"access_token": self.access_token}

        # 测试用的简单对话
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": "你好，请用一句话介绍你自己。"
                }
            ],
            "temperature": 0.7,
            "top_p": 0.9,
            "max_output_tokens": 100
        }

        try:
            print("发送测试请求...")
            start_time = time.time()

            response = requests.post(
                chat_url,
                params=params,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            elapsed_time = time.time() - start_time

            result = {
                "test": "chat_completion",
                "status_code": response.status_code,
                "success": False,
                "response_time": elapsed_time,
                "error": None
            }

            if response.status_code == 200:
                data = response.json()

                if "result" in data:
                    reply = data["result"]
                    usage = data.get("usage", {})

                    print(f"✓ 请求成功 (耗时: {elapsed_time:.2f} 秒)")
                    print(f"\n模型回复:")
                    print(f"  {reply}")
                    print(f"\nToken 使用:")
                    print(f"  输入: {usage.get('prompt_tokens', 'N/A')}")
                    print(f"  输出: {usage.get('completion_tokens', 'N/A')}")
                    print(f"  总计: {usage.get('total_tokens', 'N/A')}")

                    result["success"] = True
                    result["reply"] = reply
                    result["usage"] = usage
                else:
                    error_msg = data.get("error_msg", "未知错误")
                    print(f"✗ API 错误: {error_msg}")
                    result["error"] = error_msg
            else:
                print(f"✗ HTTP 错误: {response.status_code}")
                print(f"  响应: {response.text[:200]}")
                result["error"] = f"HTTP {response.status_code}"

            self.test_results["tests"].append(result)
            return result["success"]

        except requests.exceptions.Timeout:
            print("✗ 错误: 请求超时 (超过 30 秒)")
            self.test_results["tests"].append({
                "test": "chat_completion",
                "status_code": None,
                "success": False,
                "error": "timeout"
            })
            return False
        except Exception as e:
            print(f"✗ 错误: {str(e)}")
            self.test_results["tests"].append({
                "test": "chat_completion",
                "status_code": None,
                "success": False,
                "error": str(e)
            })
            return False

    def test_json_output(self) -> bool:
        """测试 JSON 结构化输出"""
        print("\n" + "="*60)
        print("步骤 4/5: 测试 JSON 结构化输出")
        print("="*60)

        chat_url = f"{self.base_url}/chat/ernie_speed"
        params = {"access_token": self.access_token}

        # 测试 JSON 输出
        prompt = """请分析以下舌象特征，以 JSON 格式输出诊断结果:

舌象特征:
- 舌色: 淡红舌
- 苔色: 白苔
- 舌形: 正常
- 苔质: 薄苔
- 特征: 无

请按以下 JSON 格式输出（不要包含其他内容）:
{
  "diagnosis": "诊断结论",
  "syndrome": "证型",
  "health_status": "健康状态",
  "recommendations": ["建议1", "建议2"]
}
"""

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.5,
            "top_p": 0.9
        }

        try:
            print("发送 JSON 输出测试请求...")
            start_time = time.time()

            response = requests.post(
                chat_url,
                params=params,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            elapsed_time = time.time() - start_time

            result = {
                "test": "json_output",
                "status_code": response.status_code,
                "success": False,
                "response_time": elapsed_time,
                "error": None
            }

            if response.status_code == 200:
                data = response.json()

                if "result" in data:
                    reply = data["result"]

                    print(f"✓ 请求成功 (耗时: {elapsed_time:.2f} 秒)")
                    print(f"\n模型回复:")
                    print(f"  {reply[:200]}...")

                    # 尝试解析 JSON
                    try:
                        # 提取 JSON（可能在代码块中）
                        import re
                        json_match = re.search(r'\{[\s\S]*\}', reply)
                        if json_match:
                            json_str = json_match.group()
                            json_data = json.loads(json_str)
                            print(f"\n✓ JSON 解析成功:")
                            print(f"  诊断: {json_data.get('diagnosis', 'N/A')}")
                            print(f"  证型: {json_data.get('syndrome', 'N/A')}")
                            print(f"  健康状态: {json_data.get('health_status', 'N/A')}")

                            result["success"] = True
                            result["json_data"] = json_data
                        else:
                            print(f"\n⚠ 未找到有效的 JSON 格式")
                            result["error"] = "no_json_found"
                    except json.JSONDecodeError as e:
                        print(f"\n⚠ JSON 解析失败: {e}")
                        result["error"] = f"json_parse_error: {e}"
                else:
                    error_msg = data.get("error_msg", "未知错误")
                    print(f"✗ API 错误: {error_msg}")
                    result["error"] = error_msg
            else:
                print(f"✗ HTTP 错误: {response.status_code}")
                result["error"] = f"HTTP {response.status_code}"

            self.test_results["tests"].append(result)
            return result["success"]

        except Exception as e:
            print(f"✗ 错误: {str(e)}")
            self.test_results["tests"].append({
                "test": "json_output",
                "status_code": None,
                "success": False,
                "error": str(e)
            })
            return False

    def estimate_cost(self) -> Dict[str, Any]:
        """估算 API 调用成本"""
        print("\n" + "="*60)
        print("步骤 5/5: 成本估算")
        print("="*60)

        # ERNIE-Speed 定价（2026年2月）
        input_price = 0.004  # 元/千 tokens
        output_price = 0.004  # 元/千 tokens

        # 从测试结果获取实际 token 使用
        total_input_tokens = 0
        total_output_tokens = 0

        for test in self.test_results["tests"]:
            if "usage" in test:
                total_input_tokens += test["usage"].get("prompt_tokens", 0)
                total_output_tokens += test["usage"].get("completion_tokens", 0)

        # 计算测试成本
        test_input_cost = (total_input_tokens / 1000) * input_price
        test_output_cost = (total_output_tokens / 1000) * output_price
        total_test_cost = test_input_cost + test_output_cost

        print(f"测试 Token 使用:")
        print(f"  输入 Token: {total_input_tokens}")
        print(f"  输出 Token: {total_output_tokens}")
        print(f"  总计 Token: {total_input_tokens + total_output_tokens}")
        print(f"\n测试成本:")
        print(f"  输入成本: ¥{test_input_cost:.6f}")
        print(f"  输出成本: ¥{test_output_cost:.6f}")
        print(f"  总成本: ¥{total_test_cost:.6f}")

        # 估算生产环境成本
        print(f"\n生产环境成本估算 (ERNIE-Speed):")
        print(f"  定价: 输入 ¥{input_price}/千tokens, 输出 ¥{output_price}/千tokens")
        print(f"\n  日调用量估算:")
        for daily_requests in [100, 500, 1000]:
            avg_input_tokens = 800  # 平均输入 token 数
            avg_output_tokens = 400  # 平均输出 token 数
            daily_input_cost = (daily_requests * avg_input_tokens / 1000) * input_price
            daily_output_cost = (daily_requests * avg_output_tokens / 1000) * output_price
            daily_total = daily_input_cost + daily_output_cost
            monthly_total = daily_total * 30
            print(f"    {daily_requests} 请求/日:")
            print(f"      日成本: ¥{daily_total:.2f}")
            print(f"      月成本: ¥{monthly_total:.2f}")

        cost_info = {
            "test_cost": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "input_cost": test_input_cost,
                "output_cost": test_output_cost,
                "total_cost": total_test_cost
            },
            "pricing": {
                "input_per_1k": input_price,
                "output_per_1k": output_price
            }
        }

        self.test_results["cost"] = cost_info
        return cost_info

    def generate_report(self) -> str:
        """生成测试报告"""
        print("\n" + "="*60)
        print("测试报告")
        print("="*60)

        total_tests = len(self.test_results["tests"])
        passed_tests = sum(1 for t in self.test_results["tests"] if t.get("success", False))
        failed_tests = total_tests - passed_tests

        print(f"\n总测试数: {total_tests}")
        print(f"通过: {passed_tests}")
        print(f"失败: {failed_tests}")
        print(f"成功率: {(passed_tests/total_tests*100):.1f}%")

        print(f"\n详细结果:")
        for test in self.test_results["tests"]:
            status = "✓ PASS" if test.get("success", False) else "✗ FAIL"
            print(f"  [{status}] {test['test']}")
            if test.get("error"):
                print(f"    错误: {test['error']}")

        # 保存报告到文件
        report_path = "api_service/test_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2)
        print(f"\n详细报告已保存至: {report_path}")

        return report_path

    def run_all_tests(self) -> bool:
        """运行所有测试"""
        print("\n" + "="*60)
        print("文心一言 API 连通性测试")
        print("="*60)
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 步骤 1: 加载凭证
        if not self.load_credentials():
            return False

        # 步骤 2: 获取 Access Token
        if not self.get_access_token():
            return False

        # 步骤 3: 测试对话补全
        if not self.test_chat_completion():
            print("\n⚠ 警告: 对话测试失败，但继续其他测试")

        # 步骤 4: 测试 JSON 输出
        if not self.test_json_output():
            print("\n⚠ 警告: JSON 输出测试失败")

        # 步骤 5: 成本估算
        self.estimate_cost()

        # 生成报告
        self.generate_report()

        # 返回总体结果
        passed = all(t.get("success", False) for t in self.test_results["tests"])
        if passed:
            print("\n" + "="*60)
            print("✓ 所有测试通过！API 连接正常")
            print("="*60)
        else:
            print("\n" + "="*60)
            print("⚠ 部分测试失败，请检查配置和网络连接")
            print("="*60)

        return passed


def main():
    """主函数"""
    tester = WenxinAPITester()

    try:
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
