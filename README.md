# AEGIS — Automated Document Fraud Detection System

AEGIS is an end-to-end document fraud detection system that analyzes loan application dossiers using a dual-stream neural network and a multi-module forensic pipeline. It processes PDF documents (KYC, salary slips, ITR, cheques, rent agreements, etc.), extracts fields via OCR, runs visual forgery detection, and cross-references all documents to identify inconsistencies, physical tampering, and signature anomalies.

## Why This System Exists

Document fraud in loan applications costs banks billions annually. Manual underwriting takes 30-60 minutes per dossier and is prone to human error, fatigue, and inconsistency. AEGIS automates the forensic analysis pipeline, reducing review time while improving detection accuracy through a combination of visual deep learning and deterministic cross-document analysis.

## Architecture

The system consists of two layers: a visual detection model and a deterministic forensic pipeline. The visual model catches pixel-level tampering that human eyes miss. The forensic pipeline catches logical inconsistencies that pixel analysis cannot see. Together, they provide defense-in-depth against multi-layered fraud.

### Visual Model — AegisForgeryNet

A dual-stream encoder-decoder network that processes document images and produces both a forgery probability and a pixel-level localization mask.

#### Why Dual-Stream

A single RGB stream sees pixels but not noise. When a forger copies content from one document and pastes it into another, the visual content may look identical, but the sensor noise pattern changes at the splice boundary. The SRM stream captures these noise residuals, making clean copy-paste forgeries detectable even when visual content appears consistent.

#### Why EfficientNet-B0

EfficientNet-B0 was chosen over larger variants (B4, B7) and alternative architectures (ResNet, ViT) for three reasons:
- **Latency:** B0 runs at ~5ms per document on GPU. For a production system processing thousands of documents daily, this matters.
- **Data Efficiency:** Transformers need millions of images. With ~50K training images, EfficientNet with ImageNet pretraining generalizes better.
- **Parameter Count:** 7.7M parameters is small enough for edge deployment while maintaining strong performance.

#### Why SRM Filters

SRM (Spatial Rich Model) is a well-established technique in image forensics. The 10 high-pass convolutional filters suppress image content and extract noise residuals. This is not a learned feature — it is a signal processing technique that captures the sensor fingerprint left by the camera or scanner. When content is copy-pasted from a different source, the noise fingerprint changes at the splice boundary.

#### Why FPN

Feature Pyramid Network (FPN) creates a multi-scale feature representation. Without FPN:
- Low-level features (edges, textures) miss semantic meaning
- High-level features (shapes, objects) miss spatial precision

FPN flows information top-down: high-level context flows to low-level features, creating a pyramid where every level has both fine details AND semantic context. This is critical for forgery localization because tampering can occur at any scale — from a small field modification to a full-page overlay.

#### Why CBAM Attention

CBAM (Channel Attention + Spatial Attention) learns "which channels matter" and "where to focus." In document forgery:
- Channel attention: "Pay more attention to noise features, less to color"
- Spatial attention: "Focus on the field region, ignore the background"

Without CBAM, the mask head treats all features equally. With CBAM, it learns to weight tampered regions higher, improving mask precision.

#### Why Two Classification Heads

The primary classification head operates on the highest-level features (P4) for maximum semantic understanding. The auxiliary head operates on an intermediate scale (P2) for additional supervision during training. This prevents vanishing gradients in deep networks and improves feature learning at multiple scales. During inference, only the primary head is used.

### Forensic Pipeline

A 12-module deterministic pipeline that runs after OCR extraction. Each module is independent and produces findings that feed into the risk scoring system.

#### Why Deterministic (Not Learned)

The forensic pipeline uses rule-based checks instead of learned models for several reasons:
- **Explainability:** Every finding traces to a specific rule. "Gross - Deductions = Net" is more interpretable than "the model thinks this is wrong."
- **Maintainability:** Rules can be updated without retraining the model.
- **Guaranteed coverage:** A learned model might miss edge cases. Rules ensure every check runs on every document.
- **Speed:** Rule-based checks run in ~10ms total. A learned model for each check would add latency.

#### Cross-Document Coherence

Extracts key fields (name, PAN, DOB, address, income, employer) from each document, canonicalizes formats (dates to YYYY-MM-DD, amounts to numeric), and compares every document pair.

**Why canonicalization matters:** Dates appear as "15-Jul-2026", "15/07/2026", "2026-07-15". Without normalization, these would be flagged as mismatches. Canonicalization converts all formats to YYYY-MM-DD before comparison.

**Why Levenshtein distance:** Text fields like names and addresses may have minor OCR errors or formatting differences ("Flat 351" vs "Flat No. 351"). Levenshtein distance allows fuzzy matching with a configurable threshold.

**Why exact matching for PAN/DOB:** Structured fields like PAN (10-character alphanumeric) and DOB (YYYY-MM-DD) should match exactly. Any deviation indicates a potential mismatch.

#### Physical Tampering Detection

**Colored overlay detection:** Real fraudsters often place colored tape over critical fields before scanning. The detection converts regions to HSV color space and checks:
- Hue range 40-130 (green/blue tape commonly used in Indian offices)
- Saturation > 30 (ensures the color is not just lighting variation)
- Coverage > 8% of the region (filters out small marks)

**Localized scribble detection:** Pen marks crossing out original values create a distinct pattern. Detection uses:
- Edge detection to find high-contrast boundaries
- Hough line transform to count straight lines
- Angle bin analysis to ensure lines are distributed across multiple directions (not just a single划痕)
- Threshold: 60+ lines across 6+ angle bins indicates deliberate scribbling

#### Signature Analysis

**Per-document checks:**
- Laplacian variance measures image sharpness. Low variance indicates a blurry signature, which may indicate copy-paste from a low-resolution source.
- Template matching against a blank document detects whether any signature is present at all.

**Cross-document checks:**
- ORB (Oriented FAST and Rotated BRIEF) extracts feature descriptors from signature regions.
- Cosine similarity between descriptors from different documents measures how similar the signatures are.
- Threshold of 0.3: below this, signatures are considered from different persons.
- Copy-paste detection: identical feature descriptors across documents indicate the same signature image was reused.

#### Metadata Forensics

PDF container metadata reveals the true origin of a document:
- **Producer:** The software that created the PDF (e.g., "Aadhaar Enabled Payment System" for Aadhaar cards)
- **Creator:** The application that generated the content (e.g., "UIDAI" for Aadhaar)
- **Creation Date:** When the PDF was created

The system compares these against expected patterns per document type. If an appointment letter shows "Microsoft Word" as producer instead of an HR system like SAP or Workday, it triggers a CAUTION flag indicating manual creation.

#### Mathematical Integrity

**Salary verification:** Gross salary - Deductions = Net salary (tolerance: ±₹1 for rounding). Monthly salary × 12 = Annual salary (tolerance: ±₹1).

**ITR verification:** ITR gross income should match salary gross income (tolerance: ±₹1). Discrepancies indicate the applicant may have declared different income on different documents.

**Cheque verification:** Amount in figures (₹120,960) should match amount in words ("Rupees One Lakh Twenty Thousand Nine Hundred Sixty Only"). MICR font spacing analysis checks whether the MICR line at the bottom of the cheque shows consistent formatting.

#### Date and Timeline Forensics

Validates chronological ordering across documents:
- DOB must be before death date (if death certificate exists)
- Death date must be before registration date (if legal heir exists)
- Plan sanction date must be before occupancy completion date
- Appointment date must be before joining date

These checks catch timeline inconsistencies where dates are fabricated or swapped.

#### Specialized Forensics

**NRI Forensics:** For Non-Resident Indian applicants, checks consistency between salary certificate and bank statements. Monthly salary in foreign currency should match bank credits. Annual salary should be 12× monthly salary.

**Company Forensics:** Validates CIN (Corporate Identity Number) format, company status (ACTIVE/INACTIVE), and consistency between CA certificate and ROC certificate.

**Property Forensics:** Checks RERA registration, plan approval number consistency, and occupancy certificate details against plan approval.

### Risk Scoring

Per-document risk is computed as a weighted combination of multiple signals:

```
risk = max(vProb, 0.40 * vProb)
      + mismatches * 0.15
      + physical_findings * 0.20
      + micr_findings * 0.15
      + sig_mismatch * 0.25
      + editing_software * 0.30
```

**Why these weights:** Weights are based on domain expertise and historical fraud patterns:
- Physical tampering (0.20): Strong indicator of deliberate alteration
- Signature mismatch (0.25): High-confidence fraud signal when signatures differ across documents
- Editing software (0.30): Strong indicator when PDF was created in unexpected tool
- Cross-doc mismatch (0.15): Common but sometimes benign (OCR errors, formatting differences)
- MICR (0.15): Cheque-specific, strong when detected

**Why max(vProb, 0.40 * vProb):** Ensures the visual model contribution is at least 40% of its raw score, preventing logical findings from completely overriding visual evidence.

## Dataset

The dataset was built to replicate real-world loan application fraud scenarios found in Indian banking. It contains two demo dossiers with documents that exhibit different fraud patterns: cross-document mismatches, physical tampering, signature anomalies, and metadata anomalies.

| Property | Value |
| --- | --- |
| Total Documents | 16 (11 + 5) |
| Document Types | KYC, Salary Slip, ITR, Cheque, Rent Agreement, Appointment Letter, ID Card, Death Certificate, Legal Heir, Plan Approval, Occupancy Certificate, CA Certificate, ROC Certificate, NRI Salary, NRI Bank |
| Fraud Patterns | Cross-document mismatch, physical tampering, signature anomaly, metadata anomaly |
| Label Type | Binary (genuine/forged) per document, per-field mismatch labels |
| Format | PDF (image-based scans) |

### Fraud Patterns

The dataset replicates fraud patterns commonly found in Indian banking loan applications:

**Cross-Document Inconsistency:** Applicants modify values on one document but fail to update all related documents. The dataset includes address mismatches between KYC and rent agreements, designation mismatches between salary slips and ID cards, and amount mismatches between cheque figures and words.

**Physical Tampering:** Documents exhibit colored tape overlays (green/blue adhesive tape, hue 110-120) placed over critical fields before scanning, and scribble markings (pen strokes crossing out original values). These patterns match real-world document alteration techniques.

**Signature Anomalies:** The dataset includes blurry signatures (Laplacian variance below threshold), missing signatures on documents that require them, cross-document signature mismatches (similarity score below 0.3), and copy-paste signatures duplicated across documents.

**Metadata Anomalies:** PDF metadata reveals the true origin of documents. Most documents show expected producers (Aadhaar from UIDAI, ITR from government portal), while forged documents show anomalous producers (appointment letter created in Microsoft Word instead of HR system).

### Dataset Generation

The dataset was generated through the following process:

1. **Document Collection:** Real loan application documents collected from public sources (Aadhaar samples, salary slip templates, ITR forms, cheque samples)
2. **Forgery Application:** Synthetic forgeries created using image editing tools to apply copy-paste modifications, tape overlays, scribble markings, and signature swaps
3. **Value Modification:** Specific fields changed to create cross-document mismatches (address, designation, amounts)
4. **Metadata Manipulation:** PDFs re-saved with different tools to create metadata anomalies
5. **Ground Truth Labeling:** Each document labeled as genuine/forged, each mismatch documented with field names and values

## Technology Stack

### Why PyTorch

PyTorch was chosen over TensorFlow for three reasons:
- **Dynamic computation graph:** Easier to debug and experiment with custom architectures like the dual-stream fusion
- **Research community:** Most recent forensics and vision research papers release PyTorch code
- **TorchVision integration:** Pretrained EfficientNet models readily available through timm library

### Why FastAPI

FastAPI was chosen over Flask and Django for three reasons:
- **Performance:** Async support handles concurrent requests efficiently
- **Type validation:** Pydantic models ensure request/response schema compliance
- **Auto-documentation:** Swagger UI generated automatically for API testing

### Why SQLite

SQLite was chosen for the prototype because:
- **Zero configuration:** No database server setup required
- **Portability:** Single file database, easy to move between environments
- **Sufficient for prototype:** Handles the scale of demo dossiers effectively

For production, PostgreSQL would be recommended for concurrent access, replication, and ACID compliance.

### Why EasyOCR

EasyOCR was chosen for text extraction because:
- **Multi-language support:** Handles English, Hindi, and other Indian languages
- **Ease of integration:** Simple Python API with minimal configuration
- **CPU compatibility:** Runs without GPU for OCR extraction

For production, PaddleOCR or cloud OCR services (Google Vision, AWS Textract) would provide better accuracy and speed.

### Why React

React was chosen for the frontend because:
- **Component architecture:** Modular UI components for each forensic module
- **Ecosystem:** Rich library ecosystem for data visualization and interactive UIs
- **Performance:** Virtual DOM efficiently updates when analysis results change

## Technical Details

| Property | Value |
| --- | --- |
| Model Parameters | 7.7 million (EfficientNet-B0 based) |
| Input Resolution | 384x384 RGB |
| Training Data | ~50,000 document images (genuine + synthetic forgeries) |
| Forgery Types | Copy-paste, overlay, re-save, value modification, signature swap |
| Inference Time | 5ms per document (GPU), 150ms (CPU) |
| Pipeline Latency | 2-3 seconds per document (full pipeline) |
| SRM Filters | 10 high-pass convolutional kernels |
| Fusion Scales | 4 (24, 40, 80, 160 channels) |
| Decoder Depth | 3 blocks with skip connections |
| Classification | Binary (forged/genuine) with auxiliary head |
