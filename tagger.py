# -*- coding: utf-8 -*-
"""
chunking_engine/tagger.py
=========================
Bilingual (Arabic + English) Term-Frequency smart keyword extractor.
"""

from __future__ import annotations

import re
from collections import Counter

STOPWORDS: frozenset[str] = frozenset(
    {
        # Arabic standard & unhamzated functional stopwords
        "في", "من", "على", "إلى", "عن", "مع", "هذا", "هذه", "ذلك", "تلك",
        "الذي", "التي", "الذين", "اللاتي", "اللواتي", "كان", "كانت", "كانوا",
        "يكون", "تكون", "أن", "إن", "أنه", "أنها", "إنه", "إنها", "لا", "ما",
        "لم", "لن", "هو", "هي", "هم", "هما", "هن", "نحن", "أنا", "أنت", "أنتم",
        "كل", "بعض", "غير", "سوى", "بين", "عند", "عندما", "بعد", "قبل", "حيث",
        "قد", "لقد", "بل", "أو", "أم", "ثم", "حتى", "إذا", "إذ", "لو", "لولا",
        "كما", "كذلك", "أيضا", "فقط", "جدا", "عليه", "عليها", "فيها", "فيه",
        "منه", "منها", "له", "لها", "لهم", "بها", "به", "بهم", "عنها", "عنه",
        "إليه", "إليها", "فإن", "وإن", "وأن", "ولا", "ولم", "وهو", "وهي",
        "وهم", "وقد", "ولقد", "فهو", "فهي", "فقد", "لكن", "ولكن", "أجل", "نعم",
        "منذ", "خلال", "حول", "دون", "بدل", "نحو", "فوق", "تحت", "أمام", "خلف",
        "الآن", "اليوم", "أمس", "غدا", "هنا", "هناك", "هنالك", "كيف", "ماذا",
        "لماذا", "متى", "أين", "كم", "أي", "أية", "ذات", "ذو", "ذي", "أول",
        "آخر", "أخرى", "أكثر", "أقل", "أحد", "إحدى", "كلا", "كلتا", "جميع",
        "الى", "ان", "انه", "انها", "او", "ام", "اذا", "اذ", "اي", "ايه",
        "ايضا", "اول", "اخر", "اخرى", "اكثر", "اكتر", "اقل", "احد", "احدى",
        "الاول", "الأول", "الاخير", "الأخير", "الثاني", "الثالث", "الرابع",
        "عشان", "علشان", "يعني", "اللي", "احنا", "إحنا", "انت", "إنت",
        "عايز", "عاوز", "اريد", "أريد", "كده", "كدا", "طيب", "تمام", "فعلا",
        "حاليا", "دلوقتي", "مجرد", "بسبب", "بدون", "حوالي", "ربما", "غالبا",
        # English stopwords
        "the", "and", "for", "that", "this", "with", "from", "are", "was",
        "were", "have", "has", "had", "not", "but", "what", "all", "when",
        "who", "will", "more", "can", "out", "into", "about", "which", "their",
        "there", "been", "one", "would", "could", "should", "also", "other",
        "some", "such", "than", "then", "them", "these", "those", "they",
        "your", "you", "our", "his", "her", "its", "over", "under", "between",
        "after", "before", "where", "while", "through", "during", "within",
        "without", "because", "however", "therefore", "thus", "unto", "upon",
        "page", "image", "chunk", "http", "https", "www", "com", "org", "html",
    }
)


def extract_smart_tags(text: str, top_k: int = 10) -> list[str]:
    """Extract `top_k` meaningful Arabic/English keywords using stopword-filtered TF."""
    clean_text = re.sub(r"!\[[^\]]*\]\([^\)]*\)", " ", text)
    clean_text = re.sub(r"[#*|>`~_\-\[\]\(\)]", " ", clean_text)

    raw_tokens = re.findall(r"[\w\u0600-\u06FF]{4,}", clean_text)
    filtered: list[str] = []

    for tok in raw_tokens:
        low = tok.lower()
        if low.isdigit() or any(c.isdigit() for c in low):
            continue
        if low in STOPWORDS:
            continue
        if len(low) > 4 and low[0] in ("و", "ف") and low[1:] in STOPWORDS:
            continue
        filtered.append(low)

    if not filtered:
        return []

    counts = Counter(filtered)
    return [word for word, _ in counts.most_common(top_k)]

