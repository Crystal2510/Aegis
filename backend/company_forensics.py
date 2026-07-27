import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class CompanyForensicFinding:
    check_type: str
    passed: bool
    detail: str
    confidence: str = "medium"
    doc_a: Optional[str] = None
    doc_b: Optional[str] = None
    val_a: Optional[str] = None
    val_b: Optional[str] = None


def _parse_num(val) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip()
    s = re.sub(r'[₹,\s]', "", s)
    try:
        return float(s)
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


VALID_COMPANY_STATUSES = {"active", "under process of striking off", "strike off", "dormant under section 455",
                          "dissolved", "liquidated", "amalgamated", "converted to llp"}


def check_ca_turnover_networth(extracted_by_doc: dict) -> list[CompanyForensicFinding]:
    findings = []
    turnover = _parse_num(_get_field(extracted_by_doc, "ca_certificate", "turnover"))
    net_worth = _parse_num(_get_field(extracted_by_doc, "ca_certificate", "net_worth"))
    paid_up = _parse_num(_get_field(extracted_by_doc, "ca_certificate", "paid_up_capital"))

    if turnover and paid_up and paid_up > 0:
        ratio = turnover / paid_up
        if ratio > 5.0:
            findings.append(CompanyForensicFinding(
                check_type="ca_turnover_paidup_ratio", passed=False,
                detail=f"CA turnover ({turnover:,.0f}) is {ratio:.1f}x paid-up capital ({paid_up:,.0f}) , extreme inflation, implausible for stated business scale",
                confidence="high", doc_a="ca_certificate", val_a=str(turnover), doc_b="ca_certificate", val_b=str(paid_up)))
        else:
            findings.append(CompanyForensicFinding(
                check_type="ca_turnover_paidup_ratio", passed=True,
                detail=f"CA turnover/paid-up ratio ({ratio:.1f}x) within normal range", confidence="high"))

    if turnover and net_worth:
        ratio = net_worth / max(turnover, 1)
        if ratio > 2.0:
            findings.append(CompanyForensicFinding(
                check_type="ca_networth_turnover_ratio", passed=False,
                detail=f"CA net worth ({net_worth:.2f}) is {ratio:.1f}x turnover ({turnover:.2f}) , unusually high",
                confidence="high", doc_a="ca_certificate", val_a=str(turnover), doc_b="ca_certificate", val_b=str(net_worth)))
        elif ratio < 0.01:
            findings.append(CompanyForensicFinding(
                check_type="ca_networth_turnover_ratio", passed=False,
                detail=f"CA net worth ({net_worth:.2f}) is only {ratio:.2%} of turnover ({turnover:.2f}) , unusually low",
                confidence="high", doc_a="ca_certificate", val_a=str(turnover), doc_b="ca_certificate", val_b=str(net_worth)))
        else:
            findings.append(CompanyForensicFinding(
                check_type="ca_networth_turnover_ratio", passed=True,
                detail=f"CA net worth/turnover ratio ({ratio:.2f}) within normal range", confidence="high"))
    else:
        findings.append(CompanyForensicFinding(
            check_type="ca_networth_turnover_ratio", passed=True,
            detail="CA turnover/net worth data not available for comparison", confidence="low"))

    return findings


def check_ca_udin_format(extracted_by_doc: dict) -> list[CompanyForensicFinding]:
    findings = []
    udin = _get_field(extracted_by_doc, "ca_certificate", "udin")
    if udin:
        clean = str(udin).strip()
        if re.match(r'^\d{20}$', clean):
            findings.append(CompanyForensicFinding(
                check_type="ca_udin_format", passed=True,
                detail=f"UDIN '{clean}' is valid 20-digit format", confidence="high"))
        elif re.match(r'^\d{10,25}$', clean):
            findings.append(CompanyForensicFinding(
                check_type="ca_udin_format", passed=False,
                detail=f"UDIN '{clean}' has {len(clean)} digits (expected 20) , possible forgery indicator",
                confidence="medium", doc_a="ca_certificate", val_a=clean))
        else:
            findings.append(CompanyForensicFinding(
                check_type="ca_udin_format", passed=False,
                detail=f"UDIN '{clean}' is not a valid numeric code",
                confidence="high", doc_a="ca_certificate", val_a=clean))
    else:
        findings.append(CompanyForensicFinding(
            check_type="ca_udin_format", passed=True,
            detail="UDIN not checked (field not available)", confidence="low"))
    return findings


def check_roc_status(extracted_by_doc: dict) -> list[CompanyForensicFinding]:
    findings = []
    status = _get_field(extracted_by_doc, "roc_certificate", "company_status")
    authorized = _parse_num(_get_field(extracted_by_doc, "roc_certificate", "authorized_capital"))
    paid_up = _parse_num(_get_field(extracted_by_doc, "roc_certificate", "paid_up_capital"))

    if status:
        clean = status.strip().lower()
        if clean not in VALID_COMPANY_STATUSES and not any(v in clean for v in ["active", "strike", "dormant", "dissolved", "liquidated"]):
            findings.append(CompanyForensicFinding(
                check_type="roc_status_invalid", passed=False,
                detail=f"ROC company status '{status}' is not a recognized MCA status code",
                confidence="high", doc_a="roc_certificate", val_a=status))
        else:
            findings.append(CompanyForensicFinding(
                check_type="roc_status_invalid", passed=True,
                detail=f"ROC company status '{status}' is valid", confidence="high"))
    else:
        findings.append(CompanyForensicFinding(
            check_type="roc_status_invalid", passed=True,
            detail="ROC status not checked (field not available)", confidence="low"))

    if authorized and paid_up:
        if paid_up > authorized:
            findings.append(CompanyForensicFinding(
                check_type="roc_capital_ratio", passed=False,
                detail=f"Paid-up capital ({paid_up:.2f}) exceeds authorized capital ({authorized:.2f}) , impossible",
                confidence="high", doc_a="roc_certificate", val_a=authorized, doc_b="roc_certificate", val_b=paid_up))
        elif paid_up < authorized * 0.001:
            findings.append(CompanyForensicFinding(
                check_type="roc_capital_ratio", passed=False,
                detail=f"Paid-up capital ({paid_up:.2f}) is only {paid_up/authorized:.1%} of authorized ({authorized:.2f}) , unusually low",
                confidence="medium", doc_a="roc_certificate", val_a=authorized, doc_b="roc_certificate", val_b=paid_up))
        else:
            findings.append(CompanyForensicFinding(
                check_type="roc_capital_ratio", passed=True,
                detail=f"Paid-up capital ({paid_up:.2f}) vs authorized ({authorized:.2f}) ratio acceptable",
                confidence="high"))

    return findings


def analyze_company_documents(extracted_by_doc: dict) -> list[CompanyForensicFinding]:
    findings = []
    findings.extend(check_ca_turnover_networth(extracted_by_doc))
    findings.extend(check_ca_udin_format(extracted_by_doc))
    findings.extend(check_roc_status(extracted_by_doc))
    return findings
