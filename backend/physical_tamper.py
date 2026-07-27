import numpy as np
import cv2
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PhysicalTamperFinding:
    check_type: str
    document: str
    passed: bool
    detail: str
    confidence: str = "medium"
    region: Optional[list] = None


SUPPORTED_DOC_TYPES = {
    "kyc", "salary", "cheque", "itr", "rent", "appointment", "idcard",
    "nri_salary", "nri_bank", "ca_certificate", "roc_certificate",
    "plan_approval", "occupancy_cert", "death_certificate", "legal_heir", "rera",
}


def detect_scribble_cross_out(img_rgb: np.ndarray, doc_name: str) -> PhysicalTamperFinding:
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 30, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80, minLineLength=40, maxLineGap=15)
    if lines is None:
        return PhysicalTamperFinding(
            check_type="scribble_cross_out", document=doc_name,
            passed=True, detail="No scribble or cross-out lines detected", confidence="high")
    h, w = gray.shape
    total_area = h * w
    line_mask = np.zeros_like(gray)
    flat_lines = lines.reshape(-1, 4) if lines.ndim > 2 else lines
    for line in flat_lines:
        x1, y1, x2, y2 = line
        cv2.line(line_mask, (int(x1), int(y1)), (int(x2), int(y2)), 255, 3)
    line_pixels = cv2.countNonZero(line_mask)
    line_density = line_pixels / total_area
    lengths = [np.sqrt((l[2]-l[0])**2 + (l[3]-l[1])**2) for l in flat_lines]
    avg_length = np.mean(lengths) if len(lengths) > 0 else 0
    n_angled = 0
    for line in flat_lines:
        x1, y1, x2, y2 = line
        dx, dy = abs(int(x2) - int(x1)), abs(int(y2) - int(y1))
        if dx > 10 and dy > 10 and max(dx, dy) / max(min(dx, dy), 1) < 5:
            n_angled += 1
    ratio_angled = n_angled / max(len(flat_lines), 1)

    if line_density > 0.15 and ratio_angled > 0.4 and avg_length > 60:
        return PhysicalTamperFinding(
            check_type="scribble_cross_out", document=doc_name,
            passed=False,
            detail=f"Dense scribble/cross-out pattern detected: {len(lines)} line segments, density={line_density:.4f}, {n_angled} angled strokes",
            confidence="high")
    if line_density > 0.12:
        return PhysicalTamperFinding(
            check_type="scribble_cross_out", document=doc_name,
            passed=False,
            detail=f"Moderate line pattern detected: {len(lines)} segments, density={line_density:.4f}",
            confidence="medium")
    return PhysicalTamperFinding(
        check_type="scribble_cross_out", document=doc_name,
        passed=True, detail="No scribble or cross-out lines detected", confidence="high")


def detect_tape_occlusion(img_rgb: np.ndarray, doc_name: str) -> PhysicalTamperFinding:
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    laplacian = cv2.Laplacian(blur, cv2.CV_64F)
    edge_mag = np.abs(laplacian).astype(np.float32)
    mean_edge = float(np.mean(edge_mag))

    edges = cv2.Canny(gray, 30, 150)
    edge_density = float(np.mean(edges)) / 255.0

    local_var = cv2.boxFilter(gray.astype(np.float32), -1, (15, 15))
    local_var = np.abs(gray.astype(np.float32) - local_var)
    smooth_regions = (local_var < 8).astype(np.uint8)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    smooth_regions = cv2.morphologyEx(smooth_regions, cv2.MORPH_CLOSE, kernel, iterations=2)

    smooth_edge_overlap = cv2.Canny(smooth_regions * 255, 10, 50)
    boundary_edge_ratio = float(np.mean(smooth_edge_overlap)) / 255.0 if np.any(smooth_edge_overlap) else 0

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(smooth_regions, connectivity=8)
    large_blobs = 0
    total_blob_area = 0
    for i in range(1, n_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area > 500:
            x, y, bw, bh = stats[i, 0], stats[i, 1], stats[i, 2], stats[i, 3]
            blob_edge = np.mean(edge_mag[y:y+bh, x:x+bw])
            if blob_edge < mean_edge * 0.5:
                large_blobs += 1
                total_blob_area += area
    blob_ratio = total_blob_area / (h * w) if (h * w) > 0 else 0

    if edge_density > 0.05 and blob_ratio > 0.20 and large_blobs >= 2 and boundary_edge_ratio > 0.01:
        return PhysicalTamperFinding(
            check_type="tape_occlusion", document=doc_name,
            passed=False,
            detail=f"Tape occlusion pattern detected: {large_blobs} smooth blobs covering {blob_ratio:.1%} of document",
            confidence="high")
    return PhysicalTamperFinding(
        check_type="tape_occlusion", document=doc_name,
        passed=True, detail="No tape occlusion pattern detected", confidence="high")


def detect_ink_spill(img_rgb: np.ndarray, doc_name: str) -> PhysicalTamperFinding:
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
    h, w, _ = img_rgb.shape

    saturation = hsv[:, :, 1].astype(np.float32)
    value = hsv[:, :, 2].astype(np.float32)
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)

    dark_ink = (value < 60).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    dark_ink = cv2.morphologyEx(dark_ink, cv2.MORPH_OPEN, kernel, iterations=1)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(dark_ink, connectivity=8)
    large_spots = 0
    total_ink_area = 0
    ink_regions = []
    for i in range(1, n_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area > 200:
            x, y, bw, bh = stats[i, 0], stats[i, 1], stats[i, 2], stats[i, 3]
            roi_sat = np.mean(saturation[y:y+bh, x:x+bw])
            large_spots += 1
            total_ink_area += area
            ink_regions.append(area)
    ink_ratio = total_ink_area / (h * w) if (h * w) > 0 else 0

    mean_sat = np.mean(saturation)
    sat_variance = np.var(saturation)

    if ink_ratio > 0.03 and large_spots >= 5 and sat_variance > 1000:
        return PhysicalTamperFinding(
            check_type="ink_spill", document=doc_name,
            passed=False,
            detail=f"Ink spill/blotch pattern detected: {large_spots} spots covering {ink_ratio:.1%} of document, saturation variance={sat_variance:.0f}",
            confidence="high")
    if ink_ratio > 0.02 and large_spots >= 4:
        return PhysicalTamperFinding(
            check_type="ink_spill", document=doc_name,
            passed=False,
            detail=f"Suspicious dark spots detected: {large_spots} spots covering {ink_ratio:.1%} of document",
            confidence="medium")
    return PhysicalTamperFinding(
        check_type="ink_spill", document=doc_name,
        passed=True, detail="No ink spill/blotch pattern detected", confidence="high")


def detect_signature_retrace(img_rgb: np.ndarray, doc_name: str) -> PhysicalTamperFinding:
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((2, 2), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    sig_regions = []
    for i in range(1, n_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if 50 < area < 5000:
            x, y, bw, bh = stats[i, 0], stats[i, 1], stats[i, 2], stats[i, 3]
            aspect = max(bw, bh) / max(min(bw, bh), 1)
            if aspect < 5:
                sig_regions.append(area)
    if not sig_regions:
        return PhysicalTamperFinding(
            check_type="signature_retrace", document=doc_name,
            passed=True, detail="No signature region detected for retrace analysis", confidence="medium")

    total_sig_pixels = sum(sig_regions)
    sig_mask = np.zeros_like(gray)
    for i in range(1, n_labels):
        if 50 < stats[i, cv2.CC_STAT_AREA] < 5000:
            sig_mask[labels == i] = 255

    sobelx = cv2.Sobel(gray.astype(np.float32), cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray.astype(np.float32), cv2.CV_64F, 0, 1, ksize=3)
    grad_mag = np.sqrt(sobelx**2 + sobely**2)
    sig_grad = np.mean(grad_mag[sig_mask > 0]) if np.any(sig_mask > 0) else 0

    ink_density = total_sig_pixels / max(h * w, 1)
    thick_pixels = 0
    try:
        skel_fn = getattr(cv2.ximgproc, 'thinning', None) if hasattr(cv2, 'ximgproc') else None
        if skel_fn:
            skel = skel_fn(binary)
            if np.any(skel > 0):
                thick_mask = binary.copy().astype(np.int32) - skel.astype(np.int32)
                thick_pixels = int(np.sum(thick_mask > 0))
    except Exception:
        pass

    if ink_density > 0.04 and thick_pixels > 200 and sig_grad < 25:
        return PhysicalTamperFinding(
            check_type="signature_retrace", document=doc_name,
            passed=False,
            detail=f"Signature retrace/over-inking detected: density={ink_density:.4f}, thick pixels={thick_pixels}, gradient={sig_grad:.1f}",
            confidence="high")
    if ink_density > 0.03 and thick_pixels > 150:
        return PhysicalTamperFinding(
            check_type="signature_retrace", document=doc_name,
            passed=False,
            detail=f"Suspicious signature ink density: density={ink_density:.4f}, thick pixels={thick_pixels}",
            confidence="medium")
    return PhysicalTamperFinding(
        check_type="signature_retrace", document=doc_name,
        passed=True, detail="Signature ink density within normal range", confidence="high")


def detect_colored_overlay(img_rgb: np.ndarray, doc_name: str) -> PhysicalTamperFinding:
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
    h, w = img_rgb.shape[:2]
    hue = hsv[:, :, 0]
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]

    colored = (sat > 30).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    dilated = cv2.dilate(colored, kernel, iterations=2)
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(dilated, connectivity=8)

    for i in range(1, n_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 2000:
            continue
        x, y, bw, bh = int(stats[i, 0]), int(stats[i, 1]), int(stats[i, 2]), int(stats[i, 3])
        if y < h * 0.08:
            continue
        aspect = max(bw, bh) / max(min(bw, bh), 1)
        if aspect > 5 and bh < h * 0.05:
            continue
        if 0.7 < aspect < 1.4 and min(bw, bh) < 200:
            continue
        region_sat = sat[y:y+bh, x:x+bw]
        region_hue = hue[y:y+bh, x:x+bw]
        mask = region_sat > 30
        actual = np.sum(mask)
        if actual < 200:
            continue
        pct = actual / max(bw * bh, 1)
        dom_hue = float(np.median(region_hue[mask]))
        mean_sat = float(np.mean(region_sat[mask]))

        if 40 < dom_hue < 130 and mean_sat > 30 and pct > 0.08 and bw > 100 and bh > 100:
            return PhysicalTamperFinding(
                check_type="colored_overlay", document=doc_name,
                passed=False,
                detail=f"Colored overlay (tape) detected at ({x},{y}) {bw}x{bh}: hue={dom_hue:.0f} sat={mean_sat:.0f} cover={pct:.1%} , possible DOB/field tampering",
                confidence="high",
                region=[x, y, x + bw, y + bh])

    return PhysicalTamperFinding(
        check_type="colored_overlay", document=doc_name,
        passed=True, detail="No colored overlay detected", confidence="high")


def detect_localized_scribble(img_rgb: np.ndarray, doc_name: str) -> PhysicalTamperFinding:
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    edges = cv2.Canny(gray, 20, 100)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=10, minLineLength=10, maxLineGap=10)
    if lines is None:
        return PhysicalTamperFinding(
            check_type="localized_scribble", document=doc_name,
            passed=True, detail="No line segments detected", confidence="high")

    flat = lines.reshape(-1, 4)
    grid_size = 150
    cols = w // grid_size + 1
    rows = h // grid_size + 1
    grid = np.zeros((rows, cols), dtype=int)
    for l in flat:
        cx = int((l[0] + l[2]) / 2)
        cy = int((l[1] + l[3]) / 2)
        gx = min(cx // grid_size, cols - 1)
        gy = min(cy // grid_size, rows - 1)
        grid[gy, gx] += 1

    for gy in range(rows):
        for gx in range(cols):
            count = grid[gy, gx]
            if count < 60:
                continue
            x0 = gx * grid_size
            y0 = gy * grid_size
            x1 = min(x0 + grid_size, w)
            y1 = min(y0 + grid_size, h)
            roi_lines = []
            for l in flat:
                lx = (l[0] + l[2]) / 2
                ly = (l[1] + l[3]) / 2
                if x0 <= lx <= x1 and y0 <= ly <= y1:
                    roi_lines.append(l)
            if len(roi_lines) < 40:
                continue
            angles = []
            lengths = []
            for l in roi_lines:
                dx, dy = l[2] - l[0], l[3] - l[1]
                if abs(dx) > 2 or abs(dy) > 2:
                    angles.append(np.degrees(np.arctan2(dy, dx)) % 180)
                    lengths.append(np.sqrt(dx*dx + dy*dy))
            if len(angles) < 30:
                continue
            angle_bins = np.histogram(angles, bins=12, range=(0, 180))
            nonzero_bins = int(np.sum(angle_bins[0] > 0))
            if nonzero_bins < 8:
                continue
            length_cv = np.std(lengths) / max(np.mean(lengths), 1) if lengths else 0
            short_ratio = sum(1 for l in lengths if l < 25) / max(len(lengths), 1)
            score = nonzero_bins * length_cv * short_ratio
            if score < 4.0:
                continue
            return PhysicalTamperFinding(
                check_type="localized_scribble", document=doc_name,
                passed=False,
                detail=f"Localized scribble detected at ({x0},{y0}) {x1-x0}x{y1-y0}: {len(roi_lines)} lines across {nonzero_bins} angle bins, score={score:.1f} , possible field tampering",
                confidence="high",
                region=[x0, y0, x1, y1])

    return PhysicalTamperFinding(
        check_type="localized_scribble", document=doc_name,
        passed=True, detail="No localized scribble detected", confidence="high")


def analyze_physical_tamper(img_rgb: np.ndarray, doc_name: str) -> list[PhysicalTamperFinding]:
    findings = []
    findings.append(detect_scribble_cross_out(img_rgb, doc_name))
    findings.append(detect_tape_occlusion(img_rgb, doc_name))
    findings.append(detect_ink_spill(img_rgb, doc_name))
    findings.append(detect_signature_retrace(img_rgb, doc_name))
    findings.append(detect_colored_overlay(img_rgb, doc_name))
    findings.append(detect_localized_scribble(img_rgb, doc_name))
    return findings
