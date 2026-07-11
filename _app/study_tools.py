from __future__ import annotations

import hashlib
import json
import random
import re
import threading
from collections import Counter
from pathlib import Path
from typing import Any, Callable


TURKISH_STOPWORDS = {
    "acaba", "ama", "ancak", "artık", "aslında", "aynı", "bana", "bazen", "bazı", "belki", "bile", "biri", "birkaç",
    "biz", "bize", "bizi", "bizim", "böyle", "bunu", "bunun", "burada", "çok", "çünkü", "daha", "değil", "diye", "dolayı",
    "eğer", "fakat", "falan", "gibi", "göre", "hala", "hangi", "hani", "hatta", "hem", "hep", "hepsi", "her", "için", "ile",
    "ise", "işte", "kadar", "kendi", "kez", "ki", "kim", "mı", "mi", "mu", "mü", "nasıl", "neden", "nerede", "olan", "olarak",
    "oldu", "olduğu", "olur", "onu", "onun", "orada", "öyle", "sadece", "şey", "şimdi", "şöyle", "sonra", "tabii", "tam", "tüm",
    "var", "veya", "yani", "yine", "yok", "zaten", "üzere", "hakkında", "tarafından", "sonuç", "zaman", "şekilde", "şeklinde",
}


def transcript_paths(assets_dir: Path) -> tuple[Path, Path]:
    return assets_dir / "transkript.json", assets_dir / "transkript.txt"


def quiz_path(assets_dir: Path) -> Path:
    return assets_dir / "test.json"


def load_transcript(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def transcribe_video(
    video_path: Path,
    assets_dir: Path,
    *,
    model_size: str = "base",
    duration: float = 0.0,
    stop_event: threading.Event | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[Path, Path, list[dict[str, Any]]]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Yerel transkript bileşeni kurulmamış. EchoWraith'i yeniden açın; kurulum otomatik tamamlanacaktır.") from exc

    assets_dir.mkdir(parents=True, exist_ok=True)
    json_target, text_target = transcript_paths(assets_dir)
    if progress:
        progress({"progress": 0.02, "stage": "MODEL", "message": "Türkçe konuşma modeli hazırlanıyor…"})
    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=max(2, min(8, (__import__("os").cpu_count() or 4))))
    except Exception:
        if model_size == "tiny":
            raise
        if progress:
            progress({"progress": 0.03, "stage": "RECOVERY", "message": "Seçilen model hazırlanamadı; hızlı model otomatik deneniyor…"})
        model = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=max(2, min(8, (__import__("os").cpu_count() or 4))))
    segments, info = model.transcribe(
        str(video_path),
        language="tr",
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=True,
    )
    rows: list[dict[str, Any]] = []
    total = float(duration or getattr(info, "duration", 0.0) or 0.0)
    for index, segment in enumerate(segments, start=1):
        if stop_event and stop_event.is_set():
            raise RuntimeError("Transkript işlemi durduruldu.")
        text = re.sub(r"\s+", " ", str(segment.text or "")).strip()
        if not text:
            continue
        row = {"id": index, "start": round(float(segment.start), 3), "end": round(float(segment.end), 3), "text": text}
        rows.append(row)
        if progress:
            ratio = min(0.97, float(segment.end) / total) if total else min(0.95, index / 200)
            progress({"progress": ratio, "stage": "TRANSCRIBE", "message": f"{int(ratio * 100)}% · konuşma metne çevriliyor"})
    if not rows:
        raise RuntimeError("Videoda anlaşılır konuşma bulunamadı; transkript oluşturulamadı.")
    json_target.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    text_target.write_text("\n".join(f"[{_clock(row['start'])}] {row['text']}" for row in rows) + "\n", encoding="utf-8")
    if progress:
        progress({"progress": 1.0, "stage": "DONE", "message": "Transkript hazır."})
    return json_target, text_target, rows


def _clock(seconds: float) -> str:
    value = max(0, int(seconds))
    hours, rem = divmod(value, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def _sentences(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        text = re.sub(r"\s+", " ", str(row.get("text", ""))).strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            sentence = sentence.strip(" -–—")
            if 35 <= len(sentence) <= 260 and len(sentence.split()) >= 6:
                output.append({"text": sentence, "time": float(row.get("start", 0) or 0)})
    return output


def _terms(sentences: list[dict[str, Any]]) -> list[str]:
    words = []
    for item in sentences:
        words.extend(re.findall(r"(?u)\b[A-Za-zÇĞİÖŞÜçğıöşü][A-Za-zÇĞİÖŞÜçğıöşü'-]{4,}\b", item["text"]))
    counts = Counter(word.casefold() for word in words if word.casefold() not in TURKISH_STOPWORDS)
    preferred = sorted(counts, key=lambda word: (counts[word] > 12, -min(counts[word], 5), -len(word), word))
    return preferred


def generate_quiz(rows: list[dict[str, Any]], title: str, count: int = 10) -> list[dict[str, Any]]:
    sentences = _sentences(rows)
    vocabulary = _terms(sentences)
    if len(sentences) < 2 or len(vocabulary) < 5:
        raise RuntimeError("Test üretmek için transkriptte yeterli açıklayıcı cümle bulunamadı.")
    seed = int(hashlib.sha1((title + str(len(rows))).encode("utf-8")).hexdigest()[:12], 16)
    rng = random.Random(seed)
    ranked: list[tuple[float, dict[str, Any], str]] = []
    frequency = Counter(word.casefold() for item in sentences for word in re.findall(r"(?u)\b[\wÇĞİÖŞÜçğıöşü'-]+\b", item["text"]))
    for item in sentences:
        candidates = [
            word for word in re.findall(r"(?u)\b[A-Za-zÇĞİÖŞÜçğıöşü][A-Za-zÇĞİÖŞÜçğıöşü'-]{4,}\b", item["text"])
            if word.casefold() in vocabulary and word.casefold() not in TURKISH_STOPWORDS
        ]
        if not candidates:
            continue
        answer = max(candidates, key=lambda word: (len(word), -frequency[word.casefold()]))
        score = len(set(item["text"].casefold().split())) + min(len(answer), 14) - frequency[answer.casefold()] * 0.25
        ranked.append((score + rng.random(), item, answer))
    ranked.sort(key=lambda row: row[0], reverse=True)
    quizzes: list[dict[str, Any]] = []
    used_answers: set[str] = set()
    for _score, item, answer in ranked:
        correct = answer.casefold()
        if correct in used_answers:
            continue
        pool = [word for word in vocabulary if word != correct and word not in used_answers and abs(len(word) - len(correct)) <= 6]
        if len(pool) < 3:
            pool = [word for word in vocabulary if word != correct and word not in used_answers]
        if len(pool) < 3:
            continue
        distractors = rng.sample(pool, 3)
        shown_answer = answer
        options = [shown_answer, *[word.capitalize() if answer[:1].isupper() else word for word in distractors]]
        rng.shuffle(options)
        question_text = re.sub(rf"(?iu)\b{re.escape(answer)}\b", "________", item["text"], count=1)
        quizzes.append(
            {
                "id": f"q{len(quizzes) + 1}",
                "question": "Boş bırakılan yere hangi kavram gelmelidir?\n" + question_text,
                "options": options,
                "answer": options.index(shown_answer),
                "answer_text": shown_answer,
                "explanation": f"Transkriptteki özgün cümle: {item['text']}",
                "time": round(float(item["time"]), 3),
            }
        )
        used_answers.add(correct)
        if len(quizzes) >= max(3, min(int(count), 20)):
            break
    if len(quizzes) < 3:
        raise RuntimeError("Transkriptten güvenilir seçenekler üretilemedi. Daha uzun bir ders bölümünü deneyin.")
    return quizzes


def save_quiz(items: list[dict[str, Any]], assets_dir: Path) -> Path:
    assets_dir.mkdir(parents=True, exist_ok=True)
    target = quiz_path(assets_dir)
    target.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_quiz(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []
