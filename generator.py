"""通过 OpenRouter API 调用 Claude Opus 4.8 生成 Token染色 训练数据集。

用法:
    python generate_dataset.py [--rounds N] [--model MODEL_ID]

约定:
    - API Key 从 ~/.api_key 读取（纯文本，第一行即为 key）
    - Prompt 从 ./prompt.md 读取
    - 每一次请求/响应都会立即写入日志文件（无论成功与否），避免生成内容丢失
    - 输出数据保存为 JSONL，文件名包含生成时刻的时间戳
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ---------- 路径配置 ----------
API_KEY_PATH = Path.home() / ".api_key"
PROMPT_PATH = Path("./prompt.md")
OUTPUT_DIR = Path("./.output")
LOG_DIR = Path("./.logs")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-opus-4.8"

# 时间戳：整个脚本运行期间统一使用同一个，方便日志和输出文件配对
RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"gen_log_{RUN_TS}.log"

    logger = logging.getLogger("dataset_gen")
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    logger.info(f"日志文件: {log_path.resolve()}")
    return logger


def load_api_key(logger: logging.Logger) -> str:
    if not API_KEY_PATH.exists():
        logger.error(f"未找到 API Key 文件: {API_KEY_PATH}")
        sys.exit(1)
    key = API_KEY_PATH.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    if not key:
        logger.error("API Key 文件内容为空")
        sys.exit(1)
    logger.info(f"已读取 API Key (长度 {len(key)}，前缀 {key[:8]}...)")
    return key


def load_prompt(logger: logging.Logger) -> str:
    if not PROMPT_PATH.exists():
        logger.error(f"未找到 Prompt 文件: {PROMPT_PATH}")
        sys.exit(1)
    prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    if not prompt:
        logger.error("Prompt 文件内容为空")
        sys.exit(1)
    logger.info(f"已读取 Prompt，长度 {len(prompt)} 字符")
    return prompt


def call_openrouter(
    api_key: str,
    model: str,
    prompt: str,
    logger: logging.Logger,
    round_idx: int,
    max_tokens: int = 8000,
    timeout: int = 300,
) -> str | None:
    """调用一次 OpenRouter API，返回模型回复文本；失败返回 None。"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }

    # 无论成败，先记录发出的请求内容
    logger.info(
        f"[第{round_idx}轮] >>> 发出请求 model={model} prompt_chars={len(prompt)}",
    )
    logger.info(f"[第{round_idx}轮] >>> 请求内容(原文):\n{prompt}")

    try:
        resp = requests.post(
            headers=headers,
            url=OPENROUTER_URL,
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as e:
        logger.error(f"[第{round_idx}轮] 请求异常: {e}")
        return None

    # 记录原始响应（无论是否200），防止丢失
    logger.info(f"[第{round_idx}轮] <<< HTTP状态码: {resp.status_code}")
    logger.info(f"[第{round_idx}轮] <<< 响应原文:\n{resp.text}")

    if resp.status_code != 200:
        logger.error(f"[第{round_idx}轮] 请求失败，状态码 {resp.status_code}")
        return None

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"[第{round_idx}轮] 解析响应失败: {e}")
        return None

    logger.info(f"[第{round_idx}轮] 解析成功，返回内容长度 {len(content)} 字符")
    return content


def strip_code_fence(text: str) -> str:
    """去除可能包裹的 ```jsonl ... ``` 代码块标记。"""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        # 去掉第一行 ```xxx 和最后一行 ```
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip()


def parse_jsonl_lines(
    raw_text: str,
    logger: logging.Logger,
    round_idx: int,
) -> list[dict]:
    """逐行解析 JSONL，跳过解析失败的行并记录日志，不让单行错误丢掉整批数据。"""
    cleaned = strip_code_fence(raw_text)
    valid_records = []
    bad_count = 0

    for line_no, line in enumerate(cleaned.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            valid_records.append(obj)
        except json.JSONDecodeError as e:
            bad_count += 1
            logger.warning(
                f"[第{round_idx}轮] 第{line_no}行解析失败: {e} | 原文: {line[:200]}",
            )

    logger.info(
        f"[第{round_idx}轮] 解析完成: 成功 {len(valid_records)} 条, 失败 {bad_count} 条",
    )
    return valid_records


def append_jsonl(records: list[dict], output_path: Path, logger: logging.Logger):
    """追加写入 JSONL，每条立即 flush，防止中途中断丢数据。"""
    with output_path.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
    logger.info(f"已写入 {len(records)} 条记录到 {output_path.resolve()}")


def main():
    parser = argparse.ArgumentParser(description="生成 Token染色 训练数据集")
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="调用 API 的轮数，每轮独立请求一次",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help="OpenRouter 模型 ID",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8000,
        help="单次请求的 max_tokens",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=2.0,
        help="每轮请求之间的等待秒数",
    )
    args = parser.parse_args()

    logger = setup_logging()
    logger.info(
        f"=== 开始运行 run_ts={RUN_TS} rounds={args.rounds} model={args.model} ===",
    )

    api_key = load_api_key(logger)
    prompt = load_prompt(logger)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"dataset_{RUN_TS}.jsonl"
    logger.info(f"输出文件: {output_path.resolve()}")

    total_saved = 0

    for round_idx in range(1, args.rounds + 1):
        content = call_openrouter(
            api_key=api_key,
            model=args.model,
            prompt=prompt,
            logger=logger,
            round_idx=round_idx,
            max_tokens=args.max_tokens,
        )

        if content is None:
            logger.error(
                f"[第{round_idx}轮] 未获得有效响应，跳过本轮（已在日志中保留原始请求/响应记录）",
            )
        else:
            records = parse_jsonl_lines(content, logger, round_idx)
            if records:
                append_jsonl(records, output_path, logger)
                total_saved += len(records)
            else:
                logger.warning(
                    f"[第{round_idx}轮] 未解析出任何有效记录，原始响应已完整记录在日志中，可手动恢复",
                )

        if round_idx < args.rounds:
            time.sleep(args.sleep)

    logger.info(
        f"=== 运行结束，共保存 {total_saved} 条记录到 {output_path.resolve()} ===",
    )
    print(f"\n完成。共保存 {total_saved} 条记录。")
    print(f"数据文件: {output_path.resolve()}")
    print(f"日志文件: {LOG_DIR.resolve()} 目录下 gen_log_{RUN_TS}.log")


if __name__ == "__main__":
    main()
