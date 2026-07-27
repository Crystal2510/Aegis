import json
import random
from pathlib import Path
from dataclasses import dataclass

import numpy as np
import torch
import torchvision.transforms.functional as TF
from torch.utils.data import Dataset, WeightedRandomSampler
from PIL import Image
import cv2


TECHNIQUE_TARGET_DOC = {
    "tier_a_income_inflation": "salary", "tier_a_dob_shift": "kyc",
    "tier_a_cross_doc_mismatch": "salary", "tier_b_amount_splice_easy": "salary",
    "tier_b_amount_splice_hard": "salary", "tier_a_fully_manufactured_salary": "salary",
    "tier_a_cheque_visible_micr_mismatch": "cheque", "tier_b_cheque_amount_splice_easy": "cheque",
    "tier_b_cheque_amount_splice_hard": "cheque", "tier_a_rent_deposit_inflation": "rent",
    "tier_a_rent_fabricated_tenancy": "rent", "tier_a_rent_cross_doc_mismatch": "rent",
    "tier_a_legal_heir_fabrication": "legal_heir",
    "tier_a_id_card_employee_code_mismatch": "idcard", "tier_a_id_card_cross_doc_mismatch": "idcard",
    "tier_a_nri_income_inflation": "nri_salary", "tier_a_nri_employer_swap": "nri_salary",
    "tier_a_nri_balance_tamper": "nri_bank", "tier_a_rera_status_flip": "rera",
    "tier_a_oc_plan_approval_mismatch": "occupancy_cert", "tier_a_plan_oc_cross_doc_mismatch": "occupancy_cert",
    "tier_a_oc_completion_date_shift": "occupancy_cert",
    "tier_a_itr_anchor_retained_edit": "itr", "tier_a_itr_fully_manufactured": "itr",
    "tier_a_itr_cross_doc_mismatch": "itr",
    "tier_a_appointment_ctc_inflation": "appointment", "tier_a_appointment_cross_doc_mismatch": "appointment",
    "tier_a_appointment_fully_manufactured": "appointment", "tier_a_appointment_tenure_shift": "appointment",
    "tier_a_ca_turnover_networth_inflation": "ca_certificate", "tier_a_ca_udin_anchor_retained": "ca_certificate",
    "tier_a_ca_cross_doc_mismatch": "ca_certificate",
    "tier_a_roc_status_flip": "roc_certificate", "tier_a_roc_filing_date_tamper": "roc_certificate",
    "tier_a_roc_cross_doc_mismatch": "roc_certificate",
    "tier_a_death_cert_date_shift": "death_certificate", "tier_a_death_cert_cross_doc_mismatch": "death_certificate",
    "tier_b_kyc_dob_splice_easy": "kyc", "tier_b_kyc_dob_splice_hard": "kyc",
    "tier_b_salary_designation_splice_easy": "salary", "tier_b_salary_designation_splice_hard": "salary",
    "tier_d_tape_occlusion": "kyc", "tier_d_ink_spill": "kyc",
    "tier_d_scribble_cross_out": "kyc", "tier_d_signature_retrace": "kyc",
    "tier_d_salary_tape_occlusion": "salary", "tier_d_salary_ink_spill": "salary",
    "tier_d_salary_scribble_cross_out": "salary",
}


def _technique_tier(technique):
    if technique and technique.startswith("tier_a_"):
        return "tier_a"
    if technique and technique.startswith("tier_b_"):
        return "tier_b"
    if technique and technique.startswith("tier_d_"):
        return "tier_d"
    return "none"


@dataclass
class DocumentSample:
    dossier_dir: Path
    doc_name: str
    delivery_mode: str
    image_path: Path
    mask_path: Path | None
    physical_mask_path: Path | None
    label: int
    technique: str | None
    technique_tier: str
    dossier_split: str
    dossier_fraudulent: bool = False


def index_dataset(root_dir: str) -> list[DocumentSample]:
    root = Path(root_dir)
    samples = []

    dossier_dirs = sorted([d for d in root.iterdir() if d.is_dir() and d.name.startswith("dossier_")])
    if not dossier_dirs:
        raise FileNotFoundError(f"No dossier_XXXXXX folders found under {root_dir}")

    for d in dossier_dirs:
        meta_path = d / f"{d.name}_metadata.json"
        if not meta_path.exists():
            candidates = list(d.glob("*_metadata.json"))
            if not candidates:
                continue
            meta_path = candidates[0]

        meta = json.loads(meta_path.read_text())
        outputs = meta.get("outputs", {})
        techniques = meta.get("techniques", meta.get("technique") and [meta["technique"]] or [])
        split = meta.get("split", "train")
        dossier_fraudulent = meta.get("fraudulent", False)

        targeted_docs = {TECHNIQUE_TARGET_DOC.get(t) for t in techniques if t in TECHNIQUE_TARGET_DOC}
        doc_to_technique = {}
        for t in techniques:
            td = TECHNIQUE_TARGET_DOC.get(t)
            if td:
                doc_to_technique[td] = t

        for doc_name in meta.get("documents_rendered", []):
            for mode in ("soft_copy", "hard_copy"):
                out_key = f"{doc_name}_{mode}"
                if out_key not in outputs:
                    continue
                image_path = d / outputs[out_key]
                if not image_path.exists():
                    continue

                is_targeted = doc_name in targeted_docs
                technique = doc_to_technique.get(doc_name) if is_targeted else None
                tier = _technique_tier(technique) if technique else "none"

                mask_key = f"{doc_name}_mask"
                mask_path = d / outputs[mask_key] if mask_key in outputs else None
                if mask_path is not None and not mask_path.exists():
                    mask_path = None

                physical_mask_path = None
                if mode == "hard_copy":
                    phys_key = f"{doc_name}_physical_mask"
                    if phys_key in outputs:
                        candidate = d / outputs[phys_key]
                        if candidate.exists():
                            physical_mask_path = candidate

                label = 1 if is_targeted else 0

                samples.append(DocumentSample(
                    dossier_dir=d, doc_name=doc_name, delivery_mode=mode,
                    image_path=image_path, mask_path=mask_path,
                    physical_mask_path=physical_mask_path,
                    label=label, technique=technique, technique_tier=tier,
                    dossier_split=split, dossier_fraudulent=dossier_fraudulent,
                ))

    return samples


def _build_split(samples, split, val_split=0.15, seed=42):
    if split == "train" or split == "val":
        by_dossier = {}
        for s in samples:
            by_dossier.setdefault(s.dossier_dir.name, []).append(s)
        dossier_ids = sorted(by_dossier.keys())

        if any(s.dossier_split == split for s in samples):
            return [s for s in samples if s.dossier_split == split]

        rng = random.Random(seed)
        rng.shuffle(dossier_ids)
        n_val = max(1, int(len(dossier_ids) * val_split))
        val_ids = set(dossier_ids[:n_val])
        selected = [s for s in samples
                    if (split == "val" and s.dossier_dir.name in val_ids)
                    or (split == "train" and s.dossier_dir.name not in val_ids)]
        if selected:
            return selected

    return [s for s in samples if s.dossier_split == split]


def compute_srm_residual(img_rgb: np.ndarray, cache_path: str | None = None) -> np.ndarray:
    if cache_path:
        cp = Path(cache_path)
        if cp.exists():
            return np.load(str(cp)).astype(np.float32)
    kernel = np.array([
        [-1,  2, -2,  2, -1],
        [2,  -6,  8,  -6,  2],
        [-2,  8, -12,  8, -2],
        [2,  -6,  8,  -6,  2],
        [-1,  2, -2,  2, -1],
    ], dtype=np.float32) / 12.0

    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    residual = cv2.filter2D(gray, -1, kernel)
    residual = np.clip(residual, -3, 3)
    residual = (residual + 3) / 6.0
    result = residual.astype(np.float32)
    if cache_path:
        cp = Path(cache_path)
        cp.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(cp), result)
    return result


def _paired_augment(img, mask_np, img_size):
    angle = random.uniform(-2, 2)
    translate = (random.uniform(-0.01, 0.01) * img_size, random.uniform(-0.01, 0.01) * img_size)
    scale = random.uniform(0.97, 1.03)

    img = TF.affine(img, angle=angle, translate=[int(translate[0]), int(translate[1])],
                    scale=scale, shear=0, fill=255)

    mask_pil = Image.fromarray((mask_np * 255).astype(np.uint8))
    mask_pil = TF.affine(mask_pil, angle=angle, translate=[int(translate[0]), int(translate[1])],
                         scale=scale, shear=0, fill=0)
    mask_np = (np.array(mask_pil, dtype=np.float32) > 127).astype(np.float32)

    if random.random() < 0.5:
        img = TF.adjust_brightness(img, random.uniform(0.85, 1.15))
    if random.random() < 0.5:
        img = TF.adjust_contrast(img, random.uniform(0.85, 1.15))
    if random.random() < 0.3:
        img = TF.adjust_saturation(img, random.uniform(0.85, 1.15))
    if random.random() < 0.2:
        img = TF.adjust_sharpness(img, random.uniform(0.5, 1.5))
    if random.random() < 0.15:
        noise = torch.randn(*img.size[::-1], 3) * 8
        img_np = np.array(img).astype(np.float32) + noise.numpy()
        img_np = np.clip(img_np, 0, 255).astype(np.uint8)
        img = Image.fromarray(img_np)

    return img, mask_np


def _cutmix(img1, mask1, img2, mask2, label1, label2, alpha=1.0):
    lam = np.random.beta(alpha, alpha)
    h, w = img1.shape[1], img1.shape[2]
    cx, cy = int(w * random.random()), int(h * random.random())
    cut_w = int(w * np.sqrt(1 - lam))
    cut_h = int(h * np.sqrt(1 - lam))
    x1 = max(0, cx - cut_w // 2)
    y1 = max(0, cy - cut_h // 2)
    x2 = min(w, x1 + cut_w)
    y2 = min(h, y1 + cut_h)

    mixed_img = img1.clone()
    mixed_img[:, y1:y2, x1:x2] = img2[:, y1:y2, x1:x2]
    mixed_mask = mask1.clone()
    mixed_mask[:, y1:y2, x1:x2] = mask2[:, y1:y2, x1:x2]
    lam = 1 - ((x2 - x1) * (y2 - y1) / (w * h))
    mixed_label = lam * label1 + (1 - lam) * label2
    return mixed_img, mixed_mask, mixed_label, lam


class AegisForgeryDataset(Dataset):
    def __init__(self, root_dir, split, img_size=384, augment=None, cutmix_prob=0.0):
        all_samples = index_dataset(root_dir)
        self.samples = _build_split(all_samples, split)
        if not self.samples:
            raise ValueError(f"No samples found for split='{split}' under {root_dir}")
        self.img_size = img_size
        self.augment = augment if augment is not None else (split == "train")
        self.cutmix_prob = cutmix_prob if split == "train" else 0.0

        self.n_pos = sum(s.label for s in self.samples)
        self.n_neg = len(self.samples) - self.n_pos

        print(f"[AegisForgeryDataset] split={split}: {len(self.samples)} samples "
              f"({self.n_pos} forged / {self.n_neg} genuine, cutmix={self.cutmix_prob}, augment={self.augment})")

        sample_weights = []
        for s in self.samples:
            weight = 1.0
            if s.dossier_fraudulent and s.label == 1:
                weight = 3.0
            elif s.dossier_fraudulent and s.label == 0:
                weight = 0.5
            if s.technique_tier == "tier_a":
                weight *= 2.0
            sample_weights.append(weight)

        self.sample_weights = torch.tensor(sample_weights, dtype=torch.float32)
        self.weighted_sampler = WeightedRandomSampler(sample_weights, len(sample_weights), replacement=True)

    def __len__(self):
        return len(self.samples)

    def _load_sample(self, idx):
        s = self.samples[idx]
        img = Image.open(s.image_path).convert("RGB")
        img = img.resize((self.img_size, self.img_size), Image.BILINEAR)

        mask = np.zeros((self.img_size, self.img_size), dtype=np.float32)
        for mp in (s.mask_path, s.physical_mask_path):
            if mp is not None:
                m = Image.open(mp).convert("L")
                m = m.resize((self.img_size, self.img_size), Image.NEAREST)
                m_np = (np.array(m, dtype=np.float32) > 0).astype(np.float32)
                mask = np.maximum(mask, m_np)

        if self.augment:
            img, mask = _paired_augment(img, mask, self.img_size)

        img_np = np.array(img, dtype=np.float32) / 255.0
        srm_cache = Path(str(s.image_path) + ".srm.npy")
        srm = compute_srm_residual(np.array(img.convert("RGB")), cache_path=str(srm_cache))
        srm = cv2.resize(srm, (self.img_size, self.img_size))

        img_tensor = torch.from_numpy(img_np).permute(2, 0, 1)
        srm_tensor = torch.from_numpy(srm).unsqueeze(0)
        mask_tensor = torch.from_numpy(mask.copy()).unsqueeze(0)
        label_tensor = torch.tensor(s.label, dtype=torch.float32)

        return {
            "image": img_tensor, "srm": srm_tensor, "mask": mask_tensor,
            "label": label_tensor, "technique_tier": s.technique_tier,
            "doc_name": s.doc_name, "dossier": s.dossier_dir.name,
        }

    def __getitem__(self, idx):
        a = self._load_sample(idx)

        if self.cutmix_prob > 0 and random.random() < self.cutmix_prob and a["label"].item() > 0.5:
            other_idx = random.randint(0, len(self.samples) - 1)
            b = self._load_sample(other_idx)
            mixed_img, mixed_mask, mixed_label, lam = _cutmix(
                a["image"], a["mask"], b["image"], b["mask"], a["label"], b["label"]
            )
            a["image"] = mixed_img
            a["mask"] = mixed_mask
            a["label"] = mixed_label
            a["cutmix_lam"] = lam

        return a


def collate_fn(batch):
    return {
        "image": torch.stack([b["image"] for b in batch]),
        "srm": torch.stack([b["srm"] for b in batch]),
        "mask": torch.stack([b["mask"] for b in batch]),
        "label": torch.stack([b["label"] for b in batch]),
        "technique_tier": [b["technique_tier"] for b in batch],
        "doc_name": [b["doc_name"] for b in batch],
        "dossier": [b["dossier"] for b in batch],
    }
