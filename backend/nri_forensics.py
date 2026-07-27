import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class NriForensicFinding:
    check_type: str
    passed: bool
    detail: str
    confidence: str = "medium"
    doc_a: Optional[str] = None
    doc_b: Optional[str] = None
    val_a: Optional[float] = None
    val_b: Optional[float] = None


def _parse_num(val) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip().replace("$", "").replace("€", "").replace("£", "")
    s = re.sub(r'[₹,\s]', "", s)
    try:
        n = float(s)
        return n if n > 0 else None
    except (ValueError, TypeError):
        return None


def _get_field(extracted_by_doc: dict, doc_name: str, field: str) -> Optional[str]:
    doc_fields = extracted_by_doc.get(doc_name, {})
    entry = doc_fields.get(field)
    if isinstance(entry, dict):
        return str(entry.get("value", ""))
    if entry is not None:
        return str(entry)
    return None


def check_nri_income_plausibility(extracted_by_doc: dict) -> list[NriForensicFinding]:
    findings = []
    monthly = _parse_num(_get_field(extracted_by_doc, "nri_salary", "monthly_salary_foreign"))
    annual = _parse_num(_get_field(extracted_by_doc, "nri_salary", "annual_salary_foreign"))
    employer = _get_field(extracted_by_doc, "nri_salary", "employer_name")
    designation = _get_field(extracted_by_doc, "nri_salary", "designation")

    if monthly and annual:
        implied_annual = monthly * 12
        ratio = annual / max(implied_annual, 1)
        deviation = abs(ratio - 1.0)
        if deviation > 0.20:
            findings.append(NriForensicFinding(
                check_type="nri_income_mismatch", passed=False,
                detail=f"NRI monthly ({monthly:.2f}) × 12 = {implied_annual:.2f} but annual states {annual:.2f} (ratio={ratio:.2f}, expected ~1.0)",
                confidence="high", doc_a="nri_salary", val_a=monthly, doc_b="nri_salary", val_b=annual))
        else:
            findings.append(NriForensicFinding(
                check_type="nri_income_mismatch", passed=True,
                detail=f"NRI monthly × 12 = {implied_annual:.2f} consistent with annual {annual:.2f}",
                confidence="high"))

    if monthly and monthly > 100000:
        findings.append(NriForensicFinding(
            check_type="nri_income_extreme", passed=False,
            detail=f"NRI monthly salary ({monthly:.2f}) is unusually high for foreign income",
            confidence="medium", doc_a="nri_salary", val_a=monthly))
    else:
        findings.append(NriForensicFinding(
            check_type="nri_income_extreme", passed=True,
            detail="NRI monthly salary within typical range", confidence="medium"))

    return findings


def check_nri_balance_plausibility(extracted_by_doc: dict) -> list[NriForensicFinding]:
    findings = []
    opening = _parse_num(_get_field(extracted_by_doc, "nri_bank", "opening_balance"))
    closing = _parse_num(_get_field(extracted_by_doc, "nri_bank", "closing_balance"))

    if opening is not None and closing is not None:
        delta = closing - opening
        abs_delta = abs(delta)
        avg_balance = (opening + closing) / 2
        if avg_balance > 0:
            change_pct = abs_delta / avg_balance
            if change_pct > 0.90:
                findings.append(NriForensicFinding(
                    check_type="nri_balance_swing", passed=False,
                    detail=f"NRI bank balance swing of {change_pct:.0%} (opening={opening:.2f}, closing={closing:.2f}) is extreme",
                    confidence="high", doc_a="nri_bank", val_a=opening, doc_b="nri_bank", val_b=closing))
            else:
                findings.append(NriForensicFinding(
                    check_type="nri_balance_swing", passed=True,
                    detail=f"NRI bank balance change ({change_pct:.0%}) within normal range", confidence="high"))
    else:
        findings.append(NriForensicFinding(
            check_type="nri_balance_swing", passed=True,
            detail="NRI bank balance data not available for comparison", confidence="low"))

    return findings


def check_nri_employer_consistency(extracted_by_doc: dict) -> list[NriForensicFinding]:
    findings = []
    employer_salary = _get_field(extracted_by_doc, "nri_salary", "employer_name")
    employer_bank = _get_field(extracted_by_doc, "nri_bank", "employer_name")

    if isinstance(employer_salary, str) and isinstance(employer_bank, str):
        if employer_salary.strip().lower() != employer_bank.strip().lower():
            findings.append(NriForensicFinding(
                check_type="nri_employer_mismatch", passed=False,
                detail=f"Employer name differs: NRI salary says '{employer_salary}' but NRI bank says '{employer_bank}'",
                confidence="high", doc_a="nri_salary", val_a=employer_salary, doc_b="nri_bank", val_b=employer_bank))
        else:
            findings.append(NriForensicFinding(
                check_type="nri_employer_mismatch", passed=True,
                detail=f"Employer name '{employer_salary}' consistent across documents", confidence="high"))
    return findings


def check_nri_salary_vs_bank_credit(extracted_by_doc: dict) -> list[NriForensicFinding]:
    findings = []
    salary_monthly = _parse_num(_get_field(extracted_by_doc, "nri_salary", "monthly_salary_foreign"))
    bank_credit = _parse_num(_get_field(extracted_by_doc, "nri_bank", "salary_credit_row"))

    if salary_monthly and bank_credit:
        if abs(salary_monthly - bank_credit) > 1.0:
            ratio = salary_monthly / max(bank_credit, 1)
            findings.append(NriForensicFinding(
                check_type="nri_salary_bank_mismatch", passed=False,
                detail=f"NRI salary certificate declares {salary_monthly:,.0f} but bank statement shows salary credit of {bank_credit:,.0f} , {ratio:.1f}x discrepancy indicates income inflation",
                confidence="high", doc_a="nri_salary", val_a=salary_monthly, doc_b="nri_bank", val_b=bank_credit))
        else:
            findings.append(NriForensicFinding(
                check_type="nri_salary_bank_mismatch", passed=True,
                detail=f"NRI salary ({salary_monthly:,.0f}) matches bank credit ({bank_credit:,.0f})", confidence="high"))
    else:
        findings.append(NriForensicFinding(
            check_type="nri_salary_bank_mismatch", passed=True,
            detail="NRI salary/bank credit data not available for cross-check", confidence="low"))

    return findings


def analyze_nri_documents(extracted_by_doc: dict) -> list[NriForensicFinding]:
    findings = []
    findings.extend(check_nri_income_plausibility(extracted_by_doc))
    findings.extend(check_nri_balance_plausibility(extracted_by_doc))
    findings.extend(check_nri_employer_consistency(extracted_by_doc))
    findings.extend(check_nri_salary_vs_bank_credit(extracted_by_doc))
    return findings
