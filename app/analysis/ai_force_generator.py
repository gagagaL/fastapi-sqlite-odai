"""第六勢力・第七勢力: 外部AI APIを使ったお題生成

第六勢力: 事前に学習させた参考お題群に倣い、登録済み単語を使ってAIがお題を生成
第七勢力: 参考お題なしで、登録済み単語を使ってAIが自由にお題を生成
"""

import httpx
import json
import os
import re
import random
import asyncio
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


async def call_ai_api_with_retry(prompt, api_key, provider="gemini", max_retries=5):
    """AI APIを呼び出す（リトライ付き）"""
    last_error = None
    for attempt in range(max_retries):
        try:
            if provider == "gemini":
                return await call_gemini_api(prompt, api_key)
            elif provider == "openai":
                return await call_openai_api(prompt, api_key)
            else:
                raise Exception(f"未対応のAIプロバイダー: {provider}")
        except Exception as e:
            last_error = e
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait_time = (2 ** attempt) * 3
                print(f"[{provider}] レート制限。{wait_time}秒後にリトライ ({attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)
            else:
                raise
    raise last_error


async def call_ai_api(prompt, api_key, provider="gemini", fallback_key=None, fallback_provider=None):
    """AI APIを呼び出す（フォールバック対応）"""
    try:
        return await call_ai_api_with_retry(prompt, api_key, provider)
    except Exception as e:
        error_str = str(e)
        if ("429" in error_str or "RESOURCE_EXHAUSTED" in error_str) and fallback_key:
            print(f"[{provider}] レート制限継続。{fallback_provider}にフォールバック")
            return await call_ai_api_with_retry(prompt, fallback_key, fallback_provider)
        raise


def normalize_japanese_text(text):
    """日本語テキストの正規化（不要なスペース・鉤括弧を除去）"""
    text = re.sub(r'[「」]', '', text)
    text = re.sub(r'(?<=[ぁ-んァ-ン一-龥々])\s+(?=[ぁ-んァ-ン一-龥々])', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_generated_odais(text, words_to_use, source_label, method_label):
    """AI生成テキストからお題を抽出・パース"""
    lines = text.strip().split("\n")
    odais = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 日本語テキストの不要なスペースを除去
        line = normalize_japanese_text(line)

        # 番号や記号を除去
        line = re.sub(r"^[\d]+[\.）\)]\s*", "", line)
        line = re.sub(r"^[・\-\*]\s*", "", line)
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
    words_to_use, count=10, api_key="", provider="gemini",
    fallback_key="", fallback_provider=""
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

    sample_odais = random.sample(
        reference_odais, min(50, len(reference_odais))
    )
    examples_text = "\n".join(f"- {odai}" for odai in sample_odais)

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

    text = await call_ai_api(
        prompt, api_key, provider,
        fallback_key=fallback_key if fallback_key else None,
        fallback_provider=fallback_provider if fallback_provider else None
    )
    return parse_generated_odais(
        text, words_to_use, "sixth_force_ai", "ai_with_reference"
    )


async def generate_seventh_force(
    words_to_use, count=10, api_key="", provider="gemini",
    fallback_key="", fallback_provider=""
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

    text = await call_ai_api(
        prompt, api_key, provider,
        fallback_key=fallback_key if fallback_key else None,
        fallback_provider=fallback_provider if fallback_provider else None
    )
    return parse_generated_odais(
        text, words_to_use, "seventh_force_ai", "ai_free_generation"
    )


async def generate_eighth_force(
    words_to_use, count=10, api_key="", provider="gemini",
    fallback_key="", fallback_provider=""
):
    """第八勢力: 突飛な設定 + 明確な回答導線

    - 第六勢力ベース（参考お題を使用）
    - 意外性のある状況設定を重視
    - 何を答えるべきかが明確
    """
    reference_odais = load_reference_odais()

    if not reference_odais:
        raise Exception(
            "第八勢力の参考お題がありません。先に「第六勢力で学習」を実行してください。"
        )

    if not api_key:
        raise Exception(
            f"AI APIキーが設定されていません。.envファイルに"
            f"{'GEMINI_API_KEY' if provider == 'gemini' else 'OPENAI_API_KEY'}"
            f"を設定してください。"
        )

    sample_odais = random.sample(
        reference_odais, min(50, len(reference_odais))
    )
    examples_text = "\n".join(f"- {odai}" for odai in sample_odais)

    shuffled_words = list(words_to_use)
    random.shuffle(shuffled_words)
    words_text = "、".join(shuffled_words)

    prompt = f"""あなたは大喜利のお題を考える天才です。特に「突飛な設定」と「明確な回答の方向性」を両立させたお題作りが得意です。

以下は過去に作成された大喜利のお題の例です：

{examples_text}

以下の「登録済み単語」を必ず使って、新しい大喜利のお題を{count}個生成してください。

【最重要ポイント】
このお題作成で最も重視すべきは以下の2点です：

1. **突飛な設定**: 日常ではありえない意外な状況、予想外の組み合わせ、常識を覆す前提を設定する
   - 例：「宇宙人が経営するラーメン屋」「時速3kmでしか走れないF1」「全員が嘘つきの裁判所」
   - ありきたりな設定は避け、聞いた瞬間に「え？」と思わせる意外性を持たせる

2. **明確な回答導線**: 何を答えればいいかが一目瞭然である
   - 「〇〇とは？」「〇〇の特徴」「〇〇で起きそうなこと」など、回答の形式がはっきりしている
   - 回答者が「何を言えばいいかわからない」と迷わないお題にする
   - 面白い回答が生まれやすい余白を残しつつ、方向性は明確に

【その他のルール】
- 各お題には「登録済み単語」から必ず1つ以上の単語をそのまま含めてください
- お題に使う特定の単語は登録済み単語で賄ってください。登録済み単語にない固有名詞は使わないでください
- 1行に1つのお題のみ出力してください
- 番号や記号は付けないでください

登録済み単語：
{words_text}"""

    text = await call_ai_api(
        prompt, api_key, provider,
        fallback_key=fallback_key if fallback_key else None,
        fallback_provider=fallback_provider if fallback_provider else None
    )
    return parse_generated_odais(
        text, words_to_use, "eighth_force_ai", "ai_creative_guided"
    )


async def generate_strict_words_only(
    words_to_use, count=10, api_key="", provider="gemini",
    fallback_key="", fallback_provider=""
):
    """登録単語のみ厳密使用: 与えられた単語だけでお題を構成

    - 登録済み単語以外の固有名詞・具体的な名詞は一切使用しない
    - 助詞・助動詞・一般的な動詞のみ追加可能
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

    prompt = f"""あなたは大喜利のお題を作成するエキスパートです。

【最重要ルール - 厳守】
以下の「使用可能単語リスト」に含まれる単語**のみ**を使ってお題を作成してください。
リストにない固有名詞、人名、地名、商品名、具体的な名詞は**絶対に使用禁止**です。

使用可能単語リスト：
{words_text}

【許可される追加要素】
- 助詞（が、の、を、に、で、と、は、も、や、から、まで、など）
- 助動詞（です、ます、た、だ、ない、れる、られる、など）
- 一般的な動詞（する、なる、ある、いる、言う、思う、見る、聞く、など）
- 一般的な形容詞（大きい、小さい、多い、少ない、良い、悪い、など）
- 疑問詞（何、どんな、なぜ、どう、いつ、どこ、など）
- 数詞・接続詞など基本的な語彙

【禁止事項】
- リストにない固有名詞（人名、地名、会社名、商品名など）
- リストにない具体的な名詞（例：「ラーメン」「電車」「学校」など、リストになければ使用不可）
- お題の中に新しい具体物を勝手に追加すること

【お題の形式例】
- 「〇〇あるある」
- 「〇〇の特徴」
- 「〇〇が〇〇な理由」
- 「〇〇で起きそうなこと」
- 「〇〇と〇〇の共通点」
- 「〇〇な〇〇」

{count}個のお題を生成してください。
1行に1つのお題のみ、番号や記号は付けないでください。"""

    text = await call_ai_api(
        prompt, api_key, provider,
        fallback_key=fallback_key if fallback_key else None,
        fallback_provider=fallback_provider if fallback_provider else None
    )
    return parse_generated_odais(
        text, words_to_use, "strict_words_only", "ai_strict_words"
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
