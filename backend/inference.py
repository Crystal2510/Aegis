import os
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from model import build_model
from dataset import compute_srm_residual

IMG_SIZE = 384
DEFAULT_CHECKPOINT = Path(__file__).parent.parent / "checkpoints" / "best_model.pt"


def _tta_transforms(image_np):
    yield image_np, 1.0
    yield np.fliplr(image_np), 1.0
    yield np.flipud(image_np), 1.0
    yield np.flipud(np.fliplr(image_np)), 1.0
    yield cv2.rotate(image_np, cv2.ROTATE_90_CLOCKWISE), 0.7
    yield cv2.rotate(image_np, cv2.ROTATE_90_COUNTERCLOCKWISE), 0.7


class _InferenceEngine:
    def __init__(self, checkpoint_path, device, tta=False, tta_weighted=True):
        self.device = device
        self.tta = tta
        self.tta_weighted = tta_weighted
        self.checkpoint_path = checkpoint_path

        state = torch.load(str(checkpoint_path), map_location=device, weights_only=True)

        cfg = state.get("config", {})
        backbone = cfg.get("backbone", "b0")
        img_size = cfg.get("img_size", IMG_SIZE)
        self.img_size = img_size

        self.model = build_model(img_size=img_size, backbone=backbone, pretrained=False).to(device)
        self.model.load_state_dict(state["model_state_dict"] if "model_state_dict" in state else state)
        self.model.eval()

        n_params = sum(p.numel() for p in self.model.parameters())
        tta_str = f" TTA={'weighted' if tta_weighted else 'unweighted'}" if tta else ""
        print(f"[InferenceEngine] loaded {Path(checkpoint_path).name} ({backbone}, {n_params:,} params){tta_str}")

    @torch.no_grad()
    def predict(self, image_np):
        if self.tta:
            return self._predict_with_tta(image_np)

        img_resized = cv2.resize(image_np, (self.img_size, self.img_size), interpolation=cv2.INTER_AREA)
        srm = compute_srm_residual(img_resized)

        img_tensor = (
            torch.from_numpy(img_resized.astype(np.float32) / 255.0)
            .permute(2, 0, 1)
            .unsqueeze(0)
            .to(self.device)
        )
        srm_tensor = (
            torch.from_numpy(srm)
            .unsqueeze(0)
            .unsqueeze(0)
            .to(self.device)
        )

        outputs = self.model(img_tensor, srm_tensor)
        forged_prob = float(torch.sigmoid(outputs["cls_logit"]).item())
        mask = torch.sigmoid(outputs["mask_logit"]).squeeze().cpu().numpy()

        return {"forged_prob": forged_prob, "mask": mask, "cls_logit": outputs["cls_logit"].item()}

    def _predict_with_tta(self, image_np):
        logits = []
        masks = []
        total_weight = 0.0

        for aug_img, weight in _tta_transforms(image_np):
            img_resized = cv2.resize(aug_img, (self.img_size, self.img_size), interpolation=cv2.INTER_AREA)
            srm = compute_srm_residual(img_resized)

            img_tensor = (
                torch.from_numpy(img_resized.astype(np.float32) / 255.0)
                .permute(2, 0, 1)
                .unsqueeze(0)
                .to(self.device)
            )
            srm_tensor = (
                torch.from_numpy(srm)
                .unsqueeze(0)
                .unsqueeze(0)
                .to(self.device)
            )

            outputs = self.model(img_tensor, srm_tensor)
            logits.append(outputs["cls_logit"].item() * weight)
            masks.append(torch.sigmoid(outputs["mask_logit"]).cpu().numpy() * weight)
            total_weight += weight

        if total_weight > 0:
            avg_logit = sum(logits) / total_weight
            avg_mask = sum(masks) / total_weight
        else:
            avg_logit = logits[0]
            avg_mask = masks[0]

        forged_prob = float(torch.sigmoid(torch.tensor(avg_logit)).item())
        return {"forged_prob": forged_prob, "mask": avg_mask.squeeze(), "cls_logit": avg_logit}


class EnsembleEngine:
    def __init__(self, checkpoint_paths, device, tta=False):
        self.engines = [_InferenceEngine(cp, device, tta=tta) for cp in checkpoint_paths]
        print(f"[EnsembleEngine] {len(self.engines)} models loaded")

    @torch.no_grad()
    def predict(self, image_np):
        logits = []
        masks = []
        for engine in self.engines:
            result = engine.predict(image_np)
            logits.append(result["cls_logit"])
            masks.append(result["mask"])

        avg_logit = np.mean(logits)
        avg_mask = np.mean(masks, axis=0)
        forged_prob = float(torch.sigmoid(torch.tensor(avg_logit)).item())

        return {"forged_prob": forged_prob, "mask": avg_mask, "cls_logit": avg_logit}


_engine = None


def load_engine(checkpoint_path=None, tta=False, ensemble_paths=None):
    global _engine
    if _engine is None:
        if ensemble_paths:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            _engine = EnsembleEngine([Path(p) for p in ensemble_paths], device, tta=tta)
            return _engine

        cp = checkpoint_path or Path(
            os.environ.get("AEGIS_CHECKPOINT", str(DEFAULT_CHECKPOINT))
        )
        if not Path(cp).exists():
            raise FileNotFoundError(
                f"Checkpoint not found: {cp}. "
                "Run train.py first or set the AEGIS_CHECKPOINT env var."
            )
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _engine = _InferenceEngine(Path(cp), device, tta=tta)
    return _engine


def predict_document(image_np, tta=False):
    return load_engine(tta=tta).predict(image_np)
