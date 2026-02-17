"""第六勢力・第七勢力: 外部AI APIを使ったお題生成

第六勢力: 事前に学習させた参考お題群に倣い、登録済み単語を使ってAIがお題を生成
第七勢力: 参考お題なしで、登録済み単語を使ってAIが自由にお題を生成
"""

import httpx
import json
import os
import re
import random
from datetime import datetime


# 第六勢力の参考お題データパス
SIXTH_FORCE_DATA_PATH = "app/data/sixth_force_reference_odais.json"


def load_reference_odais():
    """第六勢力の参考お題を読み込み"""
    try:
        if os.path.exists(SIXTH_FORCE_DATA_PATH):
            with open(SIXTH_FORCE_DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("odais", [])
        return []
    except Exception:
        return []


def save_reference_odais(odais):
    """第六勢力の参考お題を保存"""
    os.makedirs(os.path.dirname(SIXTH_FORCE_DATA_PATH), exist_ok=True)
    data = {
        "odais": odais,
        "updated_at": datetime.now().isoformat(),
        "count": len(odais),
    }
    with open(SIXTH_FORCE_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_reference_stats():
    """第六勢力の参考お題統計を取得"""
    odais = load_reference_odais()
    updated_at = ""
    try:
        if os.path.exists(SIXTH_FORCE_DATA_PATH):
            with open(SIXTH_FORCE_DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                updated_at = data.get("updated_at", "")
    except Exception:
        pass
    return {
        "reference_odais_count": len(odais),
        "updated_at": updated_at,
    }


async def call_gemini_api(prompt, api_key, model="gemini-2.0-flash"):
    """Gemini APIを呼び出す"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 1.0,
            "maxOutputTokens": 4096,
        },
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{url}?key={api_key}",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            raise Exception(
                f"Gemini API error ({response.status_code}): {response.text[:500]}"
            )

        result = response.json()

        candidates = result.get("candidates", [])
        if not candidates:
            raise Exception("Gemini APIからの応答にcandidatesがありません")

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            raise Exception("Gemini APIからの応答にpartsがありません")

        return parts[0].get("text", "")


async def call_openai_api(prompt, api_key, model="gpt-4o-mini"):
    """OpenAI APIを呼び出す"""
    url = "https://api.openai.com/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 1.0,
        "max_tokens": 4096,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

        if response.status_code != 200:
            raise Exception(
                f"OpenAI API error ({response.status_code}): {response.text[:500]}"
            )

        result = response.json()
        return result["choices"][0]["message"]["content"]


async def call_ai_api(prompt, api_key, provider="gemini"):
    """AI APIを呼び出す（プロバイダー選択）"""
    if provider == "gemini":
        return await call_gemini_api(prompt, api_key)
    elif provider == "openai":
        return await call_openai_api(prompt, api_key)
    else:
        raise Exception(f"未対応のAIプロバイダー: {provider}")


def parse_generated_odais(text, words_to_use, source_label, method_label):
    """AI生成テキストからお題を抽出・パース"""
    lines = text.strip().split("\n")
    odais = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 番号や記号を除去
        line = re.sub(r"^[\d]+[\.）\)]\s*", "", line)
        line = re.sub(r"^[・\-\*]\s*", "", line)
        line = re.sub(r'^「(.+)」$', r"\1", line)
        line = line.strip()

        if not line or len(line) < 3 or len(line) > 100:
            continue

        # 登録済み単語の使用チェック
        used_words = [w for w in words_to_use if w in line]

        odais.append(
            {
                "text": line,
                "source": source_label,
                "method": method_label,
                "quality_score": min(1.0, 0.5 + 0.1 * len(used_words)),
                "used_words": used_words,
            }
        )

    return odais


async def generate_sixth_force(
    words_to_use, count=10, api_key="", provider="gemini"
):
    """第六勢力: 事前学習させたお題群に倣ってAIが生成

    - 登録済み単語を必ず使用
    - 参考お題のスタイル・構造を踏襲
    """
    reference_odais = load_reference_odais()

    if not reference_odais:
        raise Exception(
            "第六勢力の参考お題がありません。先に「第六勢力で学習」を実行してください。"
        )

    if not api_key:
        raise Exception(
            f"AI APIキーが設定されていません。.envファイルに"
            f"{'GEMINI_API_KEY' if provider == 'gemini' else 'OPENAI_API_KEY'}"
            f"を設定してください。"
        )

    # 参考お題からランダムに最大50件を選択
    sample_odais = random.sample(
        reference_odais, min(50, len(reference_odais))
    )
    examples_text = "\n".join(f"- {odai}" for odai in sample_odais)

    # 登録済み単語をシャッフルして提示
    shuffled_words = list(words_to_use)
    random.shuffle(shuffled_words)
    words_text = "、".join(shuffled_words)

    prompt = f"""あなたは大喜利のお題を考える天才です。

以下は過去に作成された大喜利のお題の例です。これらのスタイルや構造を参考にしてください：

{examples_text}

以下の「登録済み単語」を必ず使って、上記の例に倣った新しい大喜利のお題を{count}個生成してください。

【重要なルール】
- 各お題には「登録済み単語」から必ず1つ以上の単語をそのまま含めてください
- お題に使う特定の単語は登録済み単語で賄ってください。登録済み単語にない固有名詞は使わないでください
- お題は回答者が面白い回答を考えられるような形式にしてください
- 上記の例のスタイルに倣いつつ、新しい組み合わせやひねりを加えてください
- 1行に1つのお題のみ出力してください
- 番号や記号は付けないでください

登録済み単語：
{words_text}"""

    text = await call_ai_api(prompt, api_key, provider)
    return parse_generated_odais(
        text, words_to_use, "sixth_force_ai", "ai_with_reference"
    )


async def generate_seventh_force(
    words_to_use, count=10, api_key="", provider="gemini"
):
    """第七勢力: 事前学習なしでAIが自由に生成

    - 登録済み単語を必ず使用
    - 参考お題には依存せず自由に生成
    """
    if not api_key:
        raise Exception(
            f"AI APIキーが設定されていません。.envファイルに"
            f"{'GEMINI_API_KEY' if provider == 'gemini' else 'OPENAI_API_KEY'}"
            f"を設定してください。"
        )

    shuffled_words = list(words_to_use)
    random.shuffle(shuffled_words)
    words_text = "、".join(shuffled_words)

    prompt = f"""あなたは大喜利のお題を考える天才です。

以下の「登録済み単語」を使って、面白い大喜利のお題を{count}個生成してください。

【重要なルール】
- 各お題には「登録済み単語」から必ず1つ以上の単語をそのまま含めてください
- お題に使う特定の単語は登録済み単語で賄ってください。登録済み単語にない固有名詞は使わないでください
- 多様なパターンのお題を作ってください（例：「○○な△△とは？」「○○あるある」「○○で一番困ること」「こんな○○は嫌だ」「もし○○が△△だったら」など）
- お題は回答者が面白い回答を考えられるような形式にしてください
- 既存の大喜利のお題にとらわれず、自由な発想でお題を考えてください
- 1行に1つのお題のみ出力してください
- 番号や記号は付けないでください

登録済み単語：
{words_text}"""

    text = await call_ai_api(prompt, api_key, provider)
    return parse_generated_odais(
        text, words_to_use, "seventh_force_ai", "ai_free_generation"
    )


def learn_from_text(text_content):
    """テキストから参考お題を学習（第六勢力用）

    既存の参考お題に追加する形で学習する。
    """
    lines = text_content.strip().split("\n")
    existing = load_reference_odais()
    existing_set = set(existing)

    new_count = 0
    for line in lines:
        line = line.strip()
        if line and len(line) >= 3 and line not in existing_set:
            existing.append(line)
            existing_set.add(line)
            new_count += 1

    save_reference_odais(existing)
    return new_count, len(existing)


def learn_from_json(data):
    """JSONデータから参考お題を学習（第六勢力用）"""
    existing = load_reference_odais()
    existing_set = set(existing)

    new_count = 0
    for item in data:
        odai_text = None
        if isinstance(item, str):
            odai_text = item
        elif isinstance(item, dict) and "odai_text" in item:
            odai_text = item["odai_text"]

        if odai_text:
            odai_text = odai_text.strip()
            if odai_text and len(odai_text) >= 3 and odai_text not in existing_set:
                existing.append(odai_text)
                existing_set.add(odai_text)
                new_count += 1

    save_reference_odais(existing)
    return new_count, len(existing)


def reset_reference_odais():
    """第六勢力の参考お題をリセット"""
    save_reference_odais([])
