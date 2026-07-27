import cv2
import numpy as np
from dataclasses import dataclass


@dataclass
class QualityFinding:
    document: str
    check_name: str
    passed: bool
    detail: str
    confidence: float = 1.0
    severity: str = "medium"


def analyze_blur(image_np: np.ndarray, doc_name: str) -> list[QualityFinding]:
    findings = []
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
    
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    if laplacian_var < 20.0:
        findings.append(QualityFinding(
            document=doc_name, check_name="global_blur_detected",
            passed=False,
            detail=f"Document is severely blurry (Laplacian variance={laplacian_var:.1f}). "
                   f"Full-page blur is consistent with a photocopy of a photocopy or "
                   f"intentional blurring to hide pixel-level tampering artifacts.",
            confidence=0.8, severity="critical",
        ))
    elif laplacian_var < 50.0:
        findings.append(QualityFinding(
            document=doc_name, check_name="global_blur_detected",
            passed=False,
            detail=f"Document has below-average sharpness (Laplacian variance={laplacian_var:.1f}). "
                   f"May be a low-quality scan or mild defocus. Cross-verify with source submission method.",
            confidence=0.5, severity="medium",
        ))
    else:
        findings.append(QualityFinding(
            document=doc_name, check_name="global_blur_detected",
            passed=True,
            detail=f"Document sharpness normal (Laplacian variance={laplacian_var:.1f}).",
            confidence=0.9, severity="low",
        ))
    
    return findings


def analyze_jpeg_artifacts(image_np: np.ndarray, doc_name: str) -> list[QualityFinding]:
    findings = []
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY).astype(np.float32)
    
    block_diffs = []
    h, w = gray.shape
    for y in range(0, h - 8, 8):
        for x in range(0, w - 8, 8):
            block = gray[y:y+8, x:x+8]
            edge_h = np.abs(np.diff(block, axis=1))
            edge_v = np.abs(np.diff(block, axis=0))
            block_diffs.append(np.mean(edge_h) + np.mean(edge_v))
    
    if not block_diffs:
        return findings
    
    mean_edge = np.mean(block_diffs)
    std_edge = np.std(block_diffs)
    blockiness = std_edge / max(mean_edge, 1e-6)
    
    if blockiness > 2.5:
        findings.append(QualityFinding(
            document=doc_name, check_name="jpeg_block_artifact",
            passed=False,
            detail=f"Strong 8x8 block boundary artifacts detected (blockiness index={blockiness:.2f}). "
                   f"Indicates heavy JPEG compression or multiple re-compression cycles. "
                   f"Consistent with document image downloaded from the web and re-saved.",
            confidence=0.7, severity="medium",
        ))
    elif blockiness > 1.5:
        findings.append(QualityFinding(
            document=doc_name, check_name="jpeg_block_artifact",
            passed=True,
            detail=f"Mild block boundary artifacts (blockiness index={blockiness:.2f}). "
                   f"Within expected range for scanned documents.",
            confidence=0.5, severity="low",
        ))
    else:
        findings.append(QualityFinding(
            document=doc_name, check_name="jpeg_block_artifact",
            passed=True,
            detail=f"No significant block compression artifacts (blockiness index={blockiness:.2f}).",
            confidence=0.9, severity="low",
        ))
    
    return findings


def analyze_noise_inconsistency(image_np: np.ndarray, doc_name: str) -> list[QualityFinding]:
    findings = []
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY).astype(np.float32)
    
    h, w = gray.shape
    grid_size = 32
    noise_vars = []
    for y in range(0, h - grid_size, grid_size):
        for x in range(0, w - grid_size, grid_size):
            patch = gray[y:y+grid_size, x:x+grid_size]
            noise_vars.append(np.var(patch))
    
    if not noise_vars:
        return findings
    
    noise_vars = np.array(noise_vars)
    cv_noise = np.std(noise_vars) / max(np.mean(noise_vars), 1e-6)
    
    if cv_noise > 0.50:
        findings.append(QualityFinding(
            document=doc_name, check_name="noise_inconsistency",
            passed=False,
            detail=f"Region-wise noise variance is highly inconsistent (CV={cv_noise:.3f}). "
                   f"Suggests composite document assembled from multiple sources with "
                   f"different camera/scanner sensor noise profiles.",
            confidence=0.7, severity="critical",
        ))
    else:
        findings.append(QualityFinding(
            document=doc_name, check_name="noise_inconsistency",
            passed=True,
            detail=f"Noise profile consistent across document regions (CV={cv_noise:.3f}).",
            confidence=0.8, severity="low",
        ))
    
    return findings


def analyze_all_quality(image_np: np.ndarray, doc_name: str) -> dict:
    findings = {}
    findings["blur"] = analyze_blur(image_np, doc_name)
    findings["jpeg"] = analyze_jpeg_artifacts(image_np, doc_name)
    findings["noise"] = analyze_noise_inconsistency(image_np, doc_name)
    return findings
