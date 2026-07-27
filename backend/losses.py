import torch
import torch.nn as nn
import torch.nn.functional as F


def dice_loss(pred_logits, target_mask, smooth=1.0):
    pred = torch.sigmoid(pred_logits)
    pred_flat = pred.flatten(1)
    target_flat = target_mask.flatten(1)
    intersection = (pred_flat * target_flat).sum(dim=1)
    union = pred_flat.sum(dim=1) + target_flat.sum(dim=1)
    dice = (2 * intersection + smooth) / (union + smooth)
    return 1 - dice.mean()


class FocalLoss(nn.Module):
    def __init__(self, alpha=0.25, gamma=2.0, reduction="mean"):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, logits, targets):
        bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
        prob = torch.sigmoid(logits)
        p_t = prob * targets + (1 - prob) * (1 - targets)
        focal_weight = (1 - p_t) ** self.gamma
        if self.alpha >= 0:
            alpha_t = self.alpha * targets + (1 - self.alpha) * (1 - targets)
            focal_weight = focal_weight * alpha_t
        loss = focal_weight * bce
        if self.reduction == "mean":
            return loss.mean()
        return loss.sum()


def label_smoothing_bce(logits, targets, smoothing=0.1):
    with torch.no_grad():
        targets = targets * (1 - smoothing) + 0.5 * smoothing
    return F.binary_cross_entropy_with_logits(logits, targets)


class AegisLoss(nn.Module):
    def __init__(self, pos_weight, mask_bce_weight=1.0, mask_dice_weight=1.0,
                 cls_loss_type="bce", focal_gamma=2.0, label_smoothing=0.0,
                 aux_cls_weight=0.2):
        super().__init__()
        self.register_buffer("pos_weight", torch.tensor(pos_weight))
        self.mask_bce_weight = mask_bce_weight
        self.mask_dice_weight = mask_dice_weight
        self.cls_loss_type = cls_loss_type
        self.label_smoothing = label_smoothing
        self.aux_cls_weight = aux_cls_weight
        self.focal_loss = FocalLoss(alpha=pos_weight / (pos_weight + 1), gamma=focal_gamma) if cls_loss_type == "focal" else None

    def forward(self, outputs, labels, masks):
        if self.label_smoothing > 0:
            cls_loss = label_smoothing_bce(outputs["cls_logit"], labels, self.label_smoothing)
        elif self.cls_loss_type == "focal":
            cls_loss = self.focal_loss(outputs["cls_logit"], labels)
        else:
            cls_loss = F.binary_cross_entropy_with_logits(
                outputs["cls_logit"], labels, pos_weight=self.pos_weight)

        aux_loss = 0.0
        if "aux_cls" in outputs and outputs["aux_cls"] is not None:
            if self.label_smoothing > 0:
                aux_loss = label_smoothing_bce(outputs["aux_cls"], labels, self.label_smoothing)
            elif self.cls_loss_type == "focal":
                aux_loss = self.focal_loss(outputs["aux_cls"], labels)
            else:
                aux_loss = F.binary_cross_entropy_with_logits(
                    outputs["aux_cls"], labels, pos_weight=self.pos_weight)

        mask_bce = F.binary_cross_entropy_with_logits(outputs["mask_logit"], masks)

        has_positive_mask = masks.flatten(1).sum(dim=1) > 0
        if has_positive_mask.any():
            mask_dice = dice_loss(outputs["mask_logit"][has_positive_mask], masks[has_positive_mask])
        else:
            mask_dice = torch.tensor(0.0, device=masks.device)

        total = cls_loss + self.aux_cls_weight * aux_loss + self.mask_bce_weight * mask_bce + self.mask_dice_weight * mask_dice

        return total, {
            "cls_loss": cls_loss.item(),
            "aux_loss": aux_loss.item() if isinstance(aux_loss, torch.Tensor) else aux_loss,
            "mask_bce": mask_bce.item(),
            "mask_dice": mask_dice.item() if isinstance(mask_dice, torch.Tensor) else mask_dice,
            "total": total.item(),
        }
