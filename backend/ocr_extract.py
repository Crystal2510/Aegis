"""
ocr_extract.py (v2)

Wraps EasyOCR and adds confidence-tracked label-anchored key-value extraction.

Key fixes from v1:
  1. extract_fields() now returns dict of {field_name: {value, confidence, failure_reason}}
     instead of raw values. Confidence tracks OCR confidence + label match quality.
  2. When a label or value is not found, records WHY (label_not_found, ocr_low_confidence,
     value_not_found) instead of just None.
  3. Added document-type-aware preprocessing for better OCR on hard copies.
"""

import re
from dataclasses import dataclass
import numpy as np


@dataclass
class OCRToken:
    text: str
    bbox: tuple
    confidence: float

    @property
    def center(self):
        x0, y0, x1, y1 = self.bbox
        return ((x0 + x1) / 2, (y0 + y1) / 2)


class OCREngine:
    _instance = None

    def __init__(self):
        import easyocr
        import torch
        self.reader = easyocr.Reader(["en"], gpu=torch.cuda.is_available())

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = OCREngine()
        return cls._instance

    def run(self, image_np: np.ndarray) -> list[OCRToken]:
        results = self.reader.readtext(image_np)
        tokens = []
        for bbox_poly, text, conf in results:
            xs = [p[0] for p in bbox_poly]
            ys = [p[1] for p in bbox_poly]
            bbox = (min(xs), min(ys), max(xs), max(ys))
            tokens.append(OCRToken(text=text.strip(), bbox=bbox, confidence=float(conf)))
        return tokens


def _levenshtein_ratio(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()


def _words_match(token_text: str, label_text: str) -> bool:
    tw = set(token_text.lower().split())
    lw = set(label_text.lower().split())
    if not lw:
        return True
    matches = sum(1 for w in tw if len(w) >= 3 and w in lw)
    return len(tw) >= 2 and matches >= len(lw) * 0.5


def _find_label_token(tokens: list[OCRToken], label_text: str, min_similarity: float = 0.75) -> tuple:
    """
    Returns (token, match_confidence, failure_reason).
    match_confidence = fuzzy similarity score if fuzzy matched, 1.0 if exact.
    """
    label_lower = label_text.lower()
    for t in tokens:
        tl = t.text.lower().strip()
        if label_lower == tl or label_lower in tl:
            return t, 1.0, None
        if len(tl) >= 3 and tl in label_lower and _words_match(tl, label_lower):
            return t, 1.0, None
    best_token, best_score = None, 0.0
    for t in tokens:
        score = _levenshtein_ratio(label_lower, t.text.lower())
        if score > best_score:
            best_score, best_token = score, t
    if best_token and best_score >= min_similarity:
        return best_token, round(best_score, 3), None
    if best_token:
        return None, round(best_score, 3), "label_low_confidence"
    return None, 0.0, "label_not_found"


ALL_KNOWN_LABELS = set()


def _register_all_labels(field_templates: dict, extra_labels: dict = None):
    for doc_fields in field_templates.values():
        for label_text, _ in doc_fields.values():
            ALL_KNOWN_LABELS.add(label_text.lower())
    if extra_labels:
        for labels in extra_labels.values():
            for label in labels:
                ALL_KNOWN_LABELS.add(label.lower())


NOISE_WORDS = {
    "paid", "pald", "amount", "monthly", "signature", "date", "stamp",
    "tenant", "landlord", "details", "agreement", "party", "first", "second",
    "rs", "rupees", "particulars", "description", "witness", "seal"
}

SKIP_VALUES = {"female", "male", "other", "gender", "male/female", "transgender", "not specified",
               "truc and correct", "contact details"}


def _clean_token_text(text: str) -> str:
    return text.strip().lower().rstrip(".:,;!?-()[]{}'\"").strip()


def _looks_like_a_label(text: str) -> bool:
    text_lower = _clean_token_text(text)
    if text_lower in NOISE_WORDS:
        return True
    for label in ALL_KNOWN_LABELS:
        ll = label.lower()
        if text_lower == ll:
            return True
        if len(text_lower) < 25 and (ll in text_lower or text_lower in ll):
            return True
    return False


def _find_value_near_label_directional(tokens: list[OCRToken], label_token: OCRToken,
                                        direction: str, max_distance: float = 800) -> tuple:
    lx0, ly0, lx1, ly1 = label_token.bbox
    label_cy = (ly0 + ly1) / 2
    row_height = ly1 - ly0
    candidates = []

    for t in tokens:
        if t.text == label_token.text and t.bbox == label_token.bbox:
            continue
        if _looks_like_a_label(t.text):
            continue
        if len(t.text.strip()) < 2:
            continue

        tx0, ty0, tx1, ty1 = t.bbox
        t_cy = (ty0 + ty1) / 2

        if direction == "right":
            same_row = abs(t_cy - label_cy) < (row_height * 1.5)
            is_right = tx0 >= lx1 - 5
            if same_row and is_right:
                dist = tx0 - lx1
                if dist < max_distance:
                    candidates.append((dist, t))
        elif direction == "below":
            is_below = ty0 >= ly1 - 5
            roughly_aligned = abs(tx0 - lx0) < 900
            if is_below and roughly_aligned:
                dist = ty0 - ly1
                if dist < max_distance:
                    candidates.append((dist, t))

    if not candidates:
        return None, "value_not_found"
    candidates.sort(key=lambda c: c[0])
    return candidates[0][1], None


def _find_value_near_label(tokens: list[OCRToken], label_token: OCRToken,
                            direction: str, max_distance: float = 800) -> tuple:
    tok, reason = _find_value_near_label_directional(tokens, label_token, direction, max_distance)
    if tok is not None:
        return tok, reason
    alt_direction = "right" if direction == "below" else "below"
    return _find_value_near_label_directional(tokens, label_token, alt_direction, max_distance)


def extract_kyc_full_name(tokens: list[OCRToken], header_band_bottom: float = 100) -> tuple:
    candidates = [t for t in tokens if t.bbox[1] > header_band_bottom
                  and t.bbox[1] < 350
                  and not _looks_like_a_label(t.text)
                  and _clean_token_text(t.text) not in SKIP_VALUES
                  and len(t.text.strip()) > 1]
    if not candidates:
        return None, "name_region_empty"
    candidates.sort(key=lambda t: t.bbox[1])
    tok = candidates[0]
    if _clean_token_text(tok.text) in SKIP_VALUES:
        return None, "name_is_non_name_word"
    return tok.text, None


def extract_token_in_fixed_box(tokens: list[OCRToken], box: tuple) -> tuple:
    x0, y0, x1, y1 = box
    candidates = [
        t for t in tokens
        if x0 <= t.center[0] <= x1 and y0 <= t.center[1] <= y1
    ]
    if not candidates:
        return None, "fixed_box_empty"
    candidates.sort(key=lambda t: t.center[1])
    bottom_y = candidates[-1].center[1]
    row_tokens = [t for t in candidates if abs(t.center[1] - bottom_y) < 15]
    row_tokens.sort(key=lambda t: t.center[0])
    combined = " ".join(t.text.strip() for t in row_tokens if t.text.strip())
    combined = " ".join(combined.split())
    most_conf = max(row_tokens, key=lambda t: t.confidence)
    most_conf.text = combined
    return most_conf, None


def preprocess_for_ocr(image_np: np.ndarray, doc_type: str = None) -> np.ndarray:
    """Apply document-type-specific preprocessing to improve OCR."""
    import cv2
    img = image_np.copy()

    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    elif img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    if doc_type in ("cheque", "salary", "itr"):
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)

    sharpened = cv2.addWeighted(gray, 1.5, cv2.GaussianBlur(gray, (0, 0), 2.0), -0.5, 0)
    return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2RGB)


def extract_fields(image_np: np.ndarray, field_template: dict, doc_type: str = None, boxes: dict = None) -> dict:
    processed = preprocess_for_ocr(image_np, doc_type)
    tokens = OCREngine.get().run(processed)
    extracted = {}

    for field_name, (label_text, direction) in field_template.items():
        confidence = 1.0
        failure_reason = None

        if boxes and field_name in boxes:
            box = tuple(boxes[field_name])
            tok, reason = extract_token_in_fixed_box(tokens, box)
            if tok:
                extracted[field_name] = {"value": tok.text.strip(), "confidence": tok.confidence, "failure_reason": None}
            else:
                extracted[field_name] = {"value": None, "confidence": 0.0, "failure_reason": reason}
            continue

        if doc_type == "nri_bank" and field_name == "full_name":
            label_tok, _, _ = _find_label_token(tokens, "Account Holder:")
            if label_tok:
                txt = label_tok.text.strip()
                idx = txt.lower().find("account holder:")
                if idx >= 0:
                    after = txt[idx + len("account holder:"):].strip()
                    if after:
                        extracted[field_name] = {"value": after, "confidence": label_tok.confidence * 0.9, "failure_reason": None}
                        continue
            extracted[field_name] = {"value": None, "confidence": 0.0, "failure_reason": "name_not_found"}
            continue

        if doc_type == "nri_salary" and field_name == "full_name":
            label_token, _, _ = _find_label_token(tokens, "to certify that")
            if label_token:
                txt = label_token.text.strip()
                after = txt[txt.lower().find("to certify that") + len("to certify that"):].strip().rstrip(".,;:")
                if after:
                    extracted[field_name] = {"value": after, "confidence": label_token.confidence * 0.9, "failure_reason": None}
                    continue
            extracted[field_name] = {"value": None, "confidence": 0.0, "failure_reason": "name_not_found"}
            continue

        if doc_type == "nri_salary" and field_name == "annual_salary_foreign":
            found = False
            for t in tokens:
                if "annual" in t.text.lower() and t.bbox[1] >= 590:
                    label_tok = t
                    lx1 = label_tok.bbox[2]
                    for tt in tokens:
                        if "aed" in tt.text.lower() and abs(tt.center[1] - label_tok.center[1]) < 15 and tt.bbox[0] > lx1:
                            extracted[field_name] = {"value": tt.text.strip(), "confidence": tt.confidence, "failure_reason": None}
                            found = True
                            break
                    break
            if not found:
                extracted[field_name] = {"value": None, "confidence": 0.0, "failure_reason": "annual_salary_not_found"}
            continue

        if doc_type == "nri_salary" and field_name == "employer_name":
            label_tok, _, _ = _find_label_token(tokens, "employed with")
            if label_tok:
                val_tok, _ = _find_value_near_label(tokens, label_tok, "below")
                if val_tok:
                    val = val_tok.text.strip()
                    idx = val.lower().find("since")
                    if idx >= 0:
                        val = val[:idx].strip()
                    val = val.rstrip("_ ").strip()
                    if val:
                        extracted[field_name] = {"value": val, "confidence": label_tok.confidence * val_tok.confidence, "failure_reason": None}
                        continue
            extracted[field_name] = {"value": None, "confidence": 0.0, "failure_reason": "employer_not_found"}
            continue

        if doc_type == "nri_salary" and field_name == "joining_date":
            label_tok, _, _ = _find_label_token(tokens, "since")
            if label_tok:
                txt = label_tok.text.strip()
                dates = re.findall(r'\d{1,2}-[A-Za-z]{3}-\d{4}', txt)
                if dates:
                    extracted[field_name] = {"value": dates[0], "confidence": label_tok.confidence * 0.9, "failure_reason": None}
                    continue
            extracted[field_name] = {"value": None, "confidence": 0.0, "failure_reason": "joining_date_not_found"}
            continue

        if doc_type == "nri_salary" and field_name == "designation":
            label_tok, _, _ = _find_label_token(tokens, "serving as")
            if label_tok:
                txt = label_tok.text.strip()
                idx = txt.lower().find("serving as")
                if idx >= 0:
                    after = txt[idx + len("serving as"):].strip().rstrip(".:;,")
                    if after:
                        extracted[field_name] = {"value": after, "confidence": label_tok.confidence * 0.9, "failure_reason": None}
                        continue
            extracted[field_name] = {"value": None, "confidence": 0.0, "failure_reason": "designation_not_found"}
            continue

        if doc_type == "cheque" and field_name == "amount_figures":
            h, w = image_np.shape[:2]
            scale_x = w / 1500.0
            scale_y = h / 650.0
            scaled_box = (1220 * scale_x, 175 * scale_y, 1440 * scale_x, 220 * scale_y)
            tok, reason = extract_token_in_fixed_box(tokens, scaled_box)
            if tok:
                val = tok.text.strip().lstrip('₹').lstrip('Rs.').rstrip('/-').strip()
                extracted[field_name] = {"value": val if val else None, "confidence": tok.confidence, "failure_reason": None}
            else:
                extracted[field_name] = {"value": None, "confidence": 0.0, "failure_reason": reason}
            continue

        label_token, label_conf, fail_reason = _find_label_token(tokens, label_text)
        if label_token is None:
            extracted[field_name] = {"value": None, "confidence": 0.0, "failure_reason": fail_reason or "label_not_found"}
            continue

        value_token, fail_reason = _find_value_near_label(tokens, label_token, direction)
        if value_token is None:
            extracted[field_name] = {"value": None, "confidence": 0.0, "failure_reason": fail_reason or "value_not_found"}
            continue

        val = value_token.text.strip()
        if val and val.lower().strip() in NOISE_WORDS:
            extracted[field_name] = {"value": None, "confidence": 0.0, "failure_reason": "value_is_noise_word"}
            continue

        combined_conf = round(label_conf * value_token.confidence, 3)
        extracted[field_name] = {"value": val, "confidence": combined_conf, "failure_reason": None}

    return extracted
