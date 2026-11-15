from __future__ import annotations

import json
import sys
from getpass import getpass

from app.modules.auth.credentials import hash_password, load_test_accounts


def prompt(label: str) -> str:
    print(label, end="", file=sys.stderr, flush=True)
    return input().strip()


def main() -> int:
    records: list[dict[str, str]] = []
    try:
        for number in range(1, 6):
            print(f"\n测试账号 {number}/5", file=sys.stderr)
            username = prompt("用户名: ")
            owner_id = prompt("稳定身份 ID（例如 tester-1）: ")
            display_name = prompt("显示名称: ")
            password = getpass("初始密码（输入不回显）: ")
            confirmation = getpass("再次输入初始密码: ")
            if password != confirmation:
                raise ValueError("两次密码不一致。")
            records.append({
                "username": username,
                "owner_id": owner_id,
                "display_name": display_name,
                "password_hash": hash_password(password),
            })
        load_test_accounts(json.dumps(records, ensure_ascii=False))
    except (EOFError, KeyboardInterrupt):
        print("\n已取消，未输出账号配置。", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"账号配置无效：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(records, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
