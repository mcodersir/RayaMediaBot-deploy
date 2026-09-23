"""Build a large deterministic offline dataset from reviewed seed lexicons.

Augmentation is intentionally explainable: it creates Persian spacing, ZWNJ,
orthography, punctuation, and contextual variants. It is not presented as
human-labelled data; the seed lexicons remain the source of truth and the
manifest records the expansion.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "ai_datasets"
TARGET_VARIANTS = 256


def variants(seed: str) -> list[str]:
    seed = " ".join(seed.split())
    pieces = seed.split()
    orthographies = [
        seed,
        seed.replace(" ", "\u200c"),
        seed.replace("ی", "ي").replace("ک", "ك"),
        seed.replace(" ", "  "),
        seed.replace(" ", "\u200c", 1),
    ]
    prefixes = ["", "خبر: ", "اطلاعیه: ", "پیام: ", "همین حالا ", "لطفا ", "کاربر: ", "متن: "]
    suffixes = [
        "", "!", "!!", "؟", " فوری", " رایگان", " کلیک کنید", " در کانال", " برای کاربران",
        " امروز", " همین الان", " با لینک", " با تخفیف", " جهت اطلاع", " منتشر شد",
    ]
    result: set[str] = set()
    for index in range(TARGET_VARIANTS):
        base = orthographies[index % len(orthographies)]
        prefix = prefixes[(index // len(orthographies)) % len(prefixes)]
        suffix = suffixes[(index // (len(orthographies) * len(prefixes))) % len(suffixes)]
        text = f"{prefix}{base}{suffix}".strip()
        if index % 11 == 0 and pieces:
            text = text.replace(pieces[0], pieces[0] + " ", 1).replace("  ", " ")
        result.add(text)
    return sorted(result)


def main() -> None:
    manifest: dict[str, dict[str, int]] = {}
    total = 0
    for path in sorted(DATA.glob("*.json")):
        if path.name == "dataset_manifest.json":
            continue
        seeds = json.loads(path.read_text(encoding="utf-8"))
        expanded: set[str] = set()
        for seed in seeds:
            expanded.update(variants(str(seed)))
        values = list(dict.fromkeys([*map(str, seeds), *sorted(expanded)]))
        path.write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest[path.stem] = {"seed_count": len(seeds), "expanded_count": len(values)}
        total += len(values)
    (DATA / "dataset_manifest.json").write_text(
        json.dumps(
            {"version": "v15-expanded", "total_examples": total, "variants_per_seed": TARGET_VARIANTS, "datasets": manifest},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"generated {total} examples")


if __name__ == "__main__":
    main()
