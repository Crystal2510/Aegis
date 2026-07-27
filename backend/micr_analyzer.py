import re
import cv2
import numpy as np
from dataclasses import dataclass


@dataclass
class MICRFinding:
    document: str
    check_name: str
    passed: bool
    detail: str
    confidence: float = 1.0
    severity: str = "medium"


MICR_BASELINE_WIDTH_MM = 3.6
MICR_TOLERANCE_MM = 0.2
CTS_EXPECTED_DIGITS = 6


def analyze_micr_cheque_number(image_np: np.ndarray, cheque_number_str: str) -> list[MICRFinding]:
    findings = []
    
    if not cheque_number_str:
        findings.append(MICRFinding(
            document="cheque", check_name="micr_cheque_number_presence",
            passed=False, detail="No cheque number extracted for MICR analysis.",
            confidence=0.5, severity="medium",
        ))
        return findings
    
    cheque_num = str(cheque_number_str).strip()
    
    if not cheque_num.isdigit():
        findings.append(MICRFinding(
            document="cheque", check_name="micr_cheque_number_format",
            passed=False,
            detail=f"Cheque number '{cheque_num}' contains non-digit characters. "
                   f"Standard MICR E-13B cheque numbers are 6-digit numeric.",
            confidence=0.8, severity="medium",
        ))
        return findings
    
    if len(cheque_num) != 6:
        findings.append(MICRFinding(
            document="cheque", check_name="micr_cheque_number_length",
            passed=False,
            detail=f"Cheque number '{cheque_num}' has {len(cheque_num)} digits. "
                   f"CTS-2010 standard requires 6-digit cheque numbers for MICR E-13B encoding.",
            confidence=0.7, severity="high",
        ))
    
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    
    micr_band = gray[int(h * 0.87):int(h * 0.97), :]
    if micr_band.size == 0:
        findings.append(MICRFinding(
            document="cheque", check_name="micr_band_detection",
            passed=False, detail="Could not isolate MICR band at bottom 13% of cheque image.",
            confidence=0.5, severity="medium",
        ))
        return findings
    
    _, binary = cv2.threshold(micr_band, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    char_gaps = []
    prev_x = -1
    n_chars = 0
    
    for col in range(binary.shape[1]):
        col_sum = np.sum(binary[:, col]) / 255
        if col_sum > 5:
            if prev_x == -1:
                prev_x = col
            else:
                gap = col - prev_x
                char_gaps.append(gap)
            prev_x = col
            n_chars += 1
    
    if not char_gaps:
        findings.append(MICRFinding(
            document="cheque", check_name="micr_band_detection",
            passed=False, detail="No printable characters detected in MICR band region.",
            confidence=0.4, severity="medium",
        ))
        return findings
    
    gap_mean = np.mean(char_gaps)
    gap_std = np.std(char_gaps)
    
    if gap_std > gap_mean * 0.4 and len(char_gaps) > 3:
        anomalies = []
        for i, g in enumerate(char_gaps):
            deviation = abs(g - gap_mean) / gap_mean
            if deviation > 0.35:
                anomalies.append(f"pos {i+1}: {g:.1f}px (σ={deviation:.2f})")
        
        if anomalies:
            findings.append(MICRFinding(
                document="cheque", check_name="micr_font_spacing_anomaly",
                passed=False,
                detail=f"MICR E-13B character spacing anomalies detected: {'; '.join(anomalies[:5])}. "
                       f"Baseline E-13B spacing is {MICR_BASELINE_WIDTH_MM:.1f}mm ±{MICR_TOLERANCE_MM:.1f}mm. "
                       f"Irregular spacing indicates digital compositing rather than magnetic ink printing.",
                confidence=0.75, severity="critical",
            ))
    else:
        findings.append(MICRFinding(
            document="cheque", check_name="micr_font_spacing_anomaly",
            passed=True,
            detail=f"MICR E-13B character spacing consistent (mean={gap_mean:.1f}px, σ/μ={gap_std/gap_mean:.2f}). "
                   f"Within expected tolerance for magnetic ink printing.",
            confidence=0.8, severity="low",
        ))
    
    return findings


def analyze_amount_consistency(amount_figures_str: str, amount_words_str: str) -> list[MICRFinding]:
    findings = []
    
    if not amount_figures_str or not amount_words_str:
        return findings
    
    try:
        fig_val = float(re.sub(r'[^0-9.]', '', str(amount_figures_str)))
    except ValueError:
        return findings
    
    from cross_doc_check import words_to_number
    words_val = words_to_number(amount_words_str)
    if words_val is None:
        return findings
    
    if fig_val != words_val:
        ratio = fig_val / words_val if words_val > 0 else 0
        if ratio >= 5:
            findings.append(MICRFinding(
                document="cheque", check_name="micr_amount_multiplier_anomaly",
                passed=False,
                detail=f"Amount figures ({amount_figures_str}) is {ratio:.0f}× the amount in words ({amount_words_str}). "
                       f"Pattern matches numeral splicing , a digit was prepended to inflate the cheque amount. "
                       f"For example, '50000' became '500000' by adding one digit.",
                confidence=0.85, severity="critical",
            ))
        else:
            findings.append(MICRFinding(
                document="cheque", check_name="micr_amount_multiplier_anomaly",
                passed=False,
                detail=f"Figures-vs-words discrepancy: ₹{fig_val:,.0f} ≠ ₹{words_val:,.0f}. "
                       f"One of the two amount representations is fabricated.",
                confidence=0.9, severity="critical",
            ))
    
    return findings


def analyze_micr_code(micr_code_str: str) -> list[MICRFinding]:
    findings = []
    if not micr_code_str:
        return findings
    
    code = re.sub(r'[^0-9]', '', str(micr_code_str))
    
    if len(code) != 9:
        findings.append(MICRFinding(
            document="cheque", check_name="micr_code_format",
            passed=False,
            detail=f"MICR routing code '{code}' has {len(code)} digits. "
                   f"Standard 9-digit format: 3-digit city + 3-digit bank + 3-digit branch.",
            confidence=0.7, severity="high",
        ))
        return findings
    
    city_code = code[:3]
    bank_code = code[3:6]
    branch_code = code[6:9]
    
    null_cities = {"000", "111", "999"}
    null_banks = {"000", "999"}
    
    city_ok = city_code not in null_cities
    bank_ok = bank_code not in null_banks
    
    if not city_ok:
        findings.append(MICRFinding(
            document="cheque", check_name="micr_city_code_validity",
            passed=False,
            detail=f"MICR city code '{city_code}' is a null/default code. "
                   f"Legitimate city codes start from 100 (Mumbai) upwards.",
            confidence=0.8, severity="high",
        ))
    
    if not bank_ok:
        findings.append(MICRFinding(
            document="cheque", check_name="micr_bank_code_validity",
            passed=False,
            detail=f"MICR bank code '{bank_code}' is a null/default code.",
            confidence=0.8, severity="high",
        ))
    
    if city_ok and bank_ok:
        findings.append(MICRFinding(
            document="cheque", check_name="micr_code_format",
            passed=True,
            detail=f"MICR routing code '{code}' appears structurally valid. "
                   f"City={city_code}, Bank={bank_code}, Branch={branch_code}.",
            confidence=0.8, severity="low",
        ))
    
    return findings
