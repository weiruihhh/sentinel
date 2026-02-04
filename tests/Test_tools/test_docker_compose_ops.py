#!/usr/bin/env python3
"""
简单的测试脚本，用于测试 docker-compose 写操作。

这个脚本测试 scale_service 和 restart_service 与监控环境。

Usage:
    # 测试扩容 (dry_run)
    python test_docker_compose_ops.py --action scale --service auth-service --replicas 3

    # 测试扩容 (execute)
    python test_docker_compose_ops.py --action scale --service auth-service --replicas 3 --execute

    # 测试重启 (dry_run)
    python test_docker_compose_ops.py --action restart --service auth-service

    # 测试重启 (execute)
    python test_docker_compose_ops.py --action restart --service auth-service --execute
"""

import argparse
import json
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sentinel.config import DataSourcesConfig
from sentinel.tools.real_tools import scale_service, restart_service


def print_result(result: dict, action: str):
    """美化打印结果。"""
    print("\n" + "=" * 80)
    print(f"📊 {action.upper()} RESULT")
    print("=" * 80)

    # 状态
    if result.get("success"):
        print("✅ Status: SUCCESS")
    else:
        print("❌ Status: FAILED")

    # 模式
    if result.get("dry_run"):
        print("🔒 Mode: DRY RUN (no actual changes)")
    else:
        print("⚠️  Mode: EXECUTE (actual changes made)")

    print()

    # 主消息
    if "message" in result:
        print(f"📝 Message: {result['message']}")
        print()

    # 详情
    print("📋 Details:")
    for key, value in result.items():
        if key not in ["success", "dry_run", "message"]:
            print(f"  {key}: {value}")

    print("=" * 80)
    print()


def main():
    """主入口。"""
    parser = argparse.ArgumentParser(
        description="Test docker-compose write operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--action",
        type=str,
        required=True,
        choices=["scale", "restart"],
        help="要执行的操作",
    )
    parser.add_argument(
        "--service",
        type=str,
        required=True,
        help="服务名称 (来自 docker-compose.yml)",
    )
    parser.add_argument(
        "--replicas",
        type=int,
        help="目标副本数 (扩容时必需)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行模式 (实际执行操作)",
    )
    parser.add_argument(
        "--compose-file",
        type=str,
        default="./monitoring/docker-compose.yml",
        help="docker-compose.yml 文件路径",
    )
    parser.add_argument(
        "--project",
        type=str,
        default="monitoring",
        help="Docker Compose 项目名称",
    )

    args = parser.parse_args()

    # 验证参数
    if args.action == "scale" and args.replicas is None:
        parser.error("--replicas is required for scale action")

    # 打印头
    print("=" * 80)
    print("🧪 DOCKER-COMPOSE WRITE OPERATIONS TEST")
    print("=" * 80)

    # 创建配置
    config = DataSourcesConfig(
        execute_write_operations=args.execute,
        docker_compose_file=args.compose_file,
        docker_compose_project=args.project,
    )

    print(f"\n⚙️  Configuration:")
    print(f"  Execute mode: {config.execute_write_operations}")
    print(f"  Compose file: {config.docker_compose_file}")
    print(f"  Project: {config.docker_compose_project}")
    print()

    # 执行操作
    try:
        if args.action == "scale":
            print(f"🔧 Testing scale_service...")
            print(f"  Service: {args.service}")
            print(f"  Target replicas: {args.replicas}")
            print(f"  Mode: {'EXECUTE' if config.execute_write_operations else 'DRY RUN'}")

            result = scale_service(
                config=config,
                service=args.service,
                replicas=args.replicas,
            )

            print_result(result, "scale_service")

        elif args.action == "restart":
            print(f"🔧 Testing restart_service...")
            print(f"  Service: {args.service}")
            print(f"  Mode: {'EXECUTE' if config.execute_write_operations else 'DRY RUN'}")

            result = restart_service(
                config=config,
                service=args.service,
            )

            print_result(result, "restart_service")

        # 退出 with appropriate code
        if result.get("success"):
            print("✅ Test completed successfully!")
            sys.exit(0)
        else:
            print("❌ Test failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
