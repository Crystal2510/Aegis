import cv2
import numpy as np
from dataclasses import dataclass, field


@dataclass
class SignatureFinding:
    document: str
    check_name: str
    passed: bool
    detail: str
    confidence: float = 1.0
    severity: str = "medium"


def _detect_signature_regions(image_np: np.ndarray) -> list[tuple]:
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(binary, kernel, iterations=2)
    
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    h, w = gray.shape
    min_area = w * h * 0.003
    max_area = w * h * 0.25
    
    regions = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect = bw / max(bh, 1)
            if 0.3 < aspect < 6.0:
                regions.append((x, y, bw, bh))
    
    return regions


def _measure_blur(image_np: np.ndarray, region: tuple) -> float:
    x, y, bw, bh = region
    crop = image_np[y:y+bh, x:x+bw]
    if crop.size == 0:
        return 0.0
    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    return laplacian_var


def _compare_signatures_tm(sig_a: np.ndarray, sig_b: np.ndarray) -> float:
    if sig_a.size == 0 or sig_b.size == 0:
        return 0.0
    gray_a = cv2.cvtColor(sig_a, cv2.COLOR_RGB2GRAY)
    gray_b = cv2.cvtColor(sig_b, cv2.COLOR_RGB2GRAY)
    
    h_a, w_a = gray_a.shape
    h_b, w_b = gray_b.shape
    
    if h_a > h_b or w_a > w_b:
        gray_a = cv2.resize(gray_a, (w_b, h_b))
    elif h_b > h_a or w_b > w_a:
        gray_b = cv2.resize(gray_b, (w_a, h_a))
    
    result = cv2.matchTemplate(gray_a, gray_b, cv2.TM_CCOEFF_NORMED)
    return float(np.max(result))


def _count_signatures(regions: list, blur_threshold: float = 80.0) -> dict:
    n_total = len(regions)
    n_blurry = 0
    for r in regions:
        pass
    return {"total": n_total, "blurry": 0}


DOC_SIGNATURE_FIELDS = {
    "cheque": ["signature"],
    "rent": ["tenant_signature", "landlord_signature"],
    "appointment": ["signature"],
    "plan_approval": ["signature"],
    "occupancy_cert": ["signature"],
    "ca_certificate": ["ca_signature"],
    "roc_certificate": ["signature"],
    "nri_salary": ["hr_signature"],
    "nri_bank": ["signature"],
    "kyc": ["signature", "stamp"],
    "itr": ["taxpayer_signature"],
    "death_certificate": ["signature"],
    "legal_heir": ["signature"],
    "salary": ["signature"],
}


def analyze_signature_quality(image_np: np.ndarray, doc_name: str) -> list[SignatureFinding]:
    findings = []
    regions = _detect_signature_regions(image_np)
    
    if not regions:
        findings.append(SignatureFinding(
            document=doc_name, check_name="signature_presence",
            passed=False, detail=f"No signature region detected on {doc_name}.",
            confidence=0.6, severity="high",
        ))
        return findings
    
    blur_values = [_measure_blur(image_np, r) for r in regions]
    avg_blur = np.mean(blur_values) if blur_values else 0.0
    min_blur = min(blur_values) if blur_values else 0.0
    
    if avg_blur < 50.0:
        findings.append(SignatureFinding(
            document=doc_name, check_name="signature_blurry",
            passed=False,
            detail=f"Signature region has abnormally low sharpness (Laplacian variance={avg_blur:.1f}). "
                   f"Blurry signatures often indicate copy-paste from another document.",
            confidence=0.7, severity="critical",
        ))
    elif avg_blur < 80.0:
        findings.append(SignatureFinding(
            document=doc_name, check_name="signature_blurry",
            passed=True,
            detail=f"Signature sharpness is marginal (Laplacian variance={avg_blur:.1f}). "
                   f"Monitor closely , may be a low-quality scan or mild editing artifact.",
            confidence=0.5, severity="low",
        ))
    else:
        findings.append(SignatureFinding(
            document=doc_name, check_name="signature_blurry",
            passed=True,
            detail=f"Signature sharpness normal (Laplacian variance={avg_blur:.1f}).",
            confidence=0.8, severity="low",
        ))
    
    if len(regions) > 2:
        findings.append(SignatureFinding(
            document=doc_name, check_name="signature_edge_artifacts",
            passed=False,
            detail=f"{len(regions)} separate signature-like regions detected. "
                   f"Multiple disjoint ink strokes may indicate composite signature fabrication.",
            confidence=0.5, severity="medium",
        ))
    
    return findings


def cross_doc_signature_match(
    doc_a_name: str, doc_a_image: np.ndarray,
    doc_b_name: str, doc_b_image: np.ndarray,
) -> list[SignatureFinding]:
    findings = []
    
    regions_a = _detect_signature_regions(doc_a_image)
    regions_b = _detect_signature_regions(doc_b_image)
    
    if not regions_a or not regions_b:
        return findings
    
    def _best_match(sig_a, sig_b):
        x1, y1, w1, h1 = sig_a
        x2, y2, w2, h2 = sig_b
        crop_a = doc_a_image[y1:y1+h1, x1:x1+w1]
        crop_b = doc_b_image[y2:y2+h2, x2:x2+w2]
        return _compare_signatures_tm(crop_a, crop_b)
    
    matches = []
    for ra in regions_a:
        for rb in regions_b:
            score = _best_match(ra, rb)
            matches.append(score)
    
    max_match = max(matches) if matches else 0.0
    
    if max_match < 0.3 and len(matches) > 0:
        findings.append(SignatureFinding(
            document=f"{doc_a_name}_vs_{doc_b_name}", check_name="signature_mismatch",
            passed=False,
            detail=f"Signature mismatch between {doc_a_name} and {doc_b_name} (match score={max_match:.3f}). "
                   f"Signatures on these documents appear to be from different persons.",
            confidence=0.7, severity="critical",
        ))
    elif 0.75 < max_match < 0.95:
        findings.append(SignatureFinding(
            document=f"{doc_a_name}_vs_{doc_b_name}", check_name="signature_copy_paste_suspicion",
            passed=False,
            detail=f"Signature match score={max_match:.3f} between {doc_a_name} and {doc_b_name}. "
                   f"High but not perfect , suggests copy-pasted signature with minor resizing or rotation.",
            confidence=0.6, severity="critical",
        ))
    elif max_match >= 0.95:
        findings.append(SignatureFinding(
            document=f"{doc_a_name}_vs_{doc_b_name}", check_name="signature_copy_paste_detected",
            passed=False,
            detail=f"Signature match score={max_match:.3f} between {doc_a_name} and {doc_b_name}. "
                   f"Near-identical signatures detected across different document types , "
                   f"strong indicator of signature cloning.",
            confidence=0.85, severity="critical",
        ))
    
    return findings
