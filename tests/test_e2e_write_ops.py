#!/usr/bin/env python3
"""
端到端测试脚本，用于测试 Sentinel 写操作。

这个脚本测试完整的流程：
1. 启动监控环境
2. 触发故障 (CPU 高)
3. 运行 Sentinel 诊断和修复
4. 验证修复是否成功

使用方法：
    # 测试模式 (安全)
    python test_e2e_write_ops.py

    # 执行模式 (实际执行操作)
    python test_e2e_write_ops.py --execute
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_command(cmd: list[str], description: str, check: bool = True, env: dict = None) -> subprocess.CompletedProcess:
    """运行一个shell命令并打印状态。"""
    print(f"\n{'='*80}")
    print(f"🔧 {description}")
    print(f"{'='*80}")
    print(f"Command: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)

    if result.returncode == 0:
        print(f"✅ Success")
        if result.stdout:
            print(f"Output:\n{result.stdout}")
    else:
        print(f"❌ Failed (exit code: {result.returncode})")
        if result.stderr:
            print(f"Error:\n{result.stderr}")
        if check:
            sys.exit(1)

    return result


def check_monitoring_health() -> bool:
    """检查监控服务是否健康。"""
    print("\n🔍 Checking monitoring services health...")

    try:
        # 检查 Prometheus
        result = subprocess.run(
            ["curl", "-s", "http://localhost:9091/-/healthy"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            print("❌ Prometheus not healthy")
            return False
        print("✅ Prometheus healthy")

        # 检查 Loki
        result = subprocess.run(
            ["curl", "-s", "http://localhost:3100/ready"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            print("❌ Loki not healthy")
            return False
        print("✅ Loki healthy")

        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def get_service_scale(service: str) -> int:
    """获取 docker-compose 服务的当前规模。"""
    # Get the monitoring directory path (parent of tests directory)
    monitoring_dir = Path(__file__).parent.parent / "monitoring"

    result = subprocess.run(
        ["docker-compose", "-p", "monitoring", "ps", "-q", service],
        capture_output=True,
        text=True,
        cwd=str(monitoring_dir)
    )

    if result.returncode != 0:
        return 0

    container_ids = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
    return len(container_ids)


def main():
    """主入口。"""
    parser = argparse.ArgumentParser(
        description="End-to-end test for Sentinel write operations"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行模式 (实际执行写操作)"
    )
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="跳过监控环境设置 (假设已经运行)"
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="跳过清理 (在最后)"
    )

    args = parser.parse_args()

    # Get paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    monitoring_dir = project_root / "monitoring"

    print("="*80)
    print("🧪 SENTINEL END-TO-END WRITE OPERATIONS TEST")
    print("="*80)
    print(f"\n模式: {'EXECUTE' if args.execute else 'DRY RUN'}")
    print(f"监控目录: {monitoring_dir}")
    print()

    # Check monitoring directory exists
    if not monitoring_dir.exists():
        print(f"\n❌ 监控目录不存在: {monitoring_dir}")
        print("请确保 monitoring/ 目录存在")
        sys.exit(1)

    # Step 1: Setup monitoring environment
    if not args.skip_setup:
        print("\n" + "="*80)
        print("📦 步骤 1: 设置监控环境")
        print("="*80)

        start_script = monitoring_dir / "start.sh"
        if not start_script.exists():
            print(f"\n❌ 启动脚本不存在: {start_script}")
            sys.exit(1)

        run_command(
            ["bash", str(start_script)],
            "启动监控堆栈",
            check=True
        )

        print("\n⏳ 等待服务就绪 (30秒)...")
        time.sleep(30)

        if not check_monitoring_health():
            print("\n❌ 监控服务不健康. 退出.")
            sys.exit(1)
    else:
        print("\n⏭️ 跳过监控设置 (--skip-setup)")
        if not check_monitoring_health():
            print("\n❌ Monitoring services not healthy. Please start them first.")
            sys.exit(1)

    # Step 2: Check initial state
    print("\n" + "="*80)
    print("📊 步骤 2: 检查初始状态")
    print("="*80)

    initial_scale = get_service_scale("auth-service")
    print(f"\n📋 auth-service 初始规模: {initial_scale}")

    run_command(
        ["docker-compose", "-p", "monitoring", "ps", "auth-service"],
        "显示 auth-service 容器",
        check=False
    )

    # Step 3: Trigger fault
    print("\n" + "="*80)
    print("🔥 步骤 3: 触发 CPU 高故障")
    print("="*80)

    test_script = monitoring_dir / "test.sh"
    if not test_script.exists():
        print(f"\n❌ 测试脚本不存在: {test_script}")
        sys.exit(1)

    run_command(
        ["bash", str(test_script), "cpu_high"],
        "触发 CPU 高故障",
        check=True
    )

    print("\n⏳ 等待故障传播 (10秒)...")
    time.sleep(10)

    # Step 4: Run Sentinel (diagnosis + fix)
    print("\n" + "="*80)
    print("🤖 步骤 4: 运行 Sentinel 诊断和修复")
    print("="*80)

    # Set environment variables for local LLM
    import os
    env = os.environ.copy()
    env["SENTINEL_LLM_PROVIDER"] = "local_model"
    env["SENTINEL_ADAPTER_PATH"] = str(project_root / "sentinel/models/Qwen3-4B-base-lora")
    env["CUDA_VISIBLE_DEVICES"] = "0"  # Use GPU 0 which has more free memory
    env["SENTINEL_DEBUG_LLM"] = "1"  # Enable LLM debug logging

    sentinel_cmd = [
        "python", str(project_root / "main.py"),
        "--use-real-tools",
        "--prometheus-url", "http://localhost:9091",
        "--loki-url", "http://localhost:3100",
        "--scenario", "cpu_thrash"
    ]

    if args.execute:
        sentinel_cmd.append("--execute")

    run_command(
        sentinel_cmd,
        f"运行 Sentinel ({'EXECUTE' if args.execute else 'DRY RUN'} 模式)",
        check=True,
        env=env
    )

    # Step 5: Verify results
    print("\n" + "="*80)
    print("✅ 步骤 5: 验证结果")
    print("="*80)

    # Check final scale
    final_scale = get_service_scale("auth-service")
    print(f"\n📋 auth-service 最终规模: {final_scale}")

    run_command(
        ["docker-compose", "-p", "monitoring", "ps", "auth-service"],
        "显示修复后的 auth-service 容器",
        check=False
    )

    # Check Sentinel outputs
    print("\n📄 Checking Sentinel outputs...")

    # Find latest run directory
    runs_dir = project_root / "runs"
    if runs_dir.exists():
        run_dirs = sorted(runs_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if run_dirs:
            latest_run = run_dirs[0]
            print(f"Latest run: {latest_run}")

            # Check report
            report_file = latest_run / "report.json"
            if report_file.exists():
                with open(report_file) as f:
                    report = json.load(f)

                print("\n📊 报告摘要:")
                print(f"  Status: {report.get('status', 'unknown')}")
                print(f"  摘要: {report.get('summary', 'N/A')}")

                print("\n💡 推荐操作:")
                for i, action in enumerate(report.get('recommended_actions', []), 1):
                    print(f"  {i}. {action}")

                print("\n📈 Metrics:")
                for key, value in report.get('metrics', {}).items():
                    print(f"  {key}: {value}")

            # Check trace for tool calls
            trace_file = latest_run / "trace.jsonl"
            if trace_file.exists():
                print("\n🔧 工具调用:")
                with open(trace_file) as f:
                    for line in f:
                        entry = json.loads(line)
                        if entry.get('type') == 'tool_call':
                            tool_name = entry.get('tool_name', 'unknown')
                            tool_args = entry.get('args', {})
                            print(f"  - {tool_name}: {tool_args}")

    # Step 6: Verify fix effectiveness
    print("\n" + "="*80)
    print("🔍 步骤 6: 验证修复效果")
    print("="*80)

    if args.execute:
        if final_scale > initial_scale:
            print(f"\n✅ 服务规模从 {initial_scale} 增加到 {final_scale} 副本")
        elif final_scale == initial_scale:
            print(f"\n⚠️ 服务规模不变 ({initial_scale} 副本)")
        else:
            print(f"\n❌ 服务规模从 {initial_scale} 减少到 {final_scale} 副本")
    else:
        print(f"\n🔒 DRY RUN 模式: 没有实际变化")
        print(f"  初始规模: {initial_scale}")
        print(f"  最终规模: {final_scale} (不变)")

    # Step 7: Cleanup
    if not args.skip_cleanup:
        print("\n" + "="*80)
        print("🧹 步骤 7: 清理")
        print("="*80)

        # Reset fault
        run_command(
            ["bash", str(test_script), "reset"],
            "重置故障",
            check=False
        )

        # Scale back to original if needed
        if args.execute and final_scale != initial_scale:
            print(f"\n🔄 恢复到原始规模 ({initial_scale})...")
            run_command(
                [
                    "docker-compose", "-p", "monitoring",
                    "up", "-d", "--scale", f"auth-service={initial_scale}",
                    "--no-recreate"
                ],
                f"将 auth-service 恢复到 {initial_scale}",
                check=False
            )
    else:
        print("\n⏭️ 跳过清理 (--skip-cleanup)")

    # Final summary
    print("\n" + "="*80)
    print("🎉 测试完成")
    print("="*80)
    print(f"\n模式: {'EXECUTE' if args.execute else 'DRY RUN'}")
    print(f"初始规模: {initial_scale}")
    print(f"最终规模: {final_scale}")

    if args.execute:
        if final_scale > initial_scale:
            print("\n✅ 测试通过: 服务成功扩容")
        else:
            print("\n⚠️ 测试警告: 服务未扩容")
    else:
        print("\n✅ 测试通过: Dry run 完成")

    print("\n💡 下一步:")
    if not args.execute:
        print("  - 使用 --execute 执行实际操作")
    print("  - 检查 runs/ 目录查看详细日志")
    print("  - 查看 trace.jsonl 了解工具调用详情")
    print("  - 查看 report.json 了解推荐操作")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
