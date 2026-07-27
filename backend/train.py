import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torch.optim.lr_scheduler import CosineAnnealingLR, SequentialLR, LinearLR

from model import build_model
from dataset import AegisForgeryDataset, collate_fn
from losses import AegisLoss

CHECKPOINT_DIR = Path(__file__).parent.parent / "checkpoints"


def accuracy(pred_logits, labels, threshold=0.5):
    probs = torch.sigmoid(pred_logits)
    preds = (probs >= threshold).float()
    correct = (preds == labels).float().sum()
    return correct / labels.size(0)


def precision_recall_f1(pred_logits, labels, threshold=0.5):
    probs = torch.sigmoid(pred_logits)
    preds = (probs >= threshold).float()
    tp = ((preds == 1) & (labels == 1)).float().sum()
    fp = ((preds == 1) & (labels == 0)).float().sum()
    fn = ((preds == 0) & (labels == 1)).float().sum()
    prec = tp / (tp + fp + 1e-8)
    rec = tp / (tp + fn + 1e-8)
    f1 = 2 * prec * rec / (prec + rec + 1e-8)
    return prec.item(), rec.item(), f1.item()


def evaluate(model, loader, criterion, device, epoch=None):
    model.eval()
    total_loss = 0.0
    all_logits = []
    all_labels = []
    n_total = len(loader)

    with torch.no_grad():
        for bidx, batch in enumerate(loader):
            images = batch["image"].to(device)
            srms = batch["srm"].to(device)
            labels = batch["label"].to(device)
            masks = batch["mask"].to(device)

            outputs = model(images, srms)
            loss, _ = criterion(outputs, labels, masks)
            total_loss += loss.item() * images.size(0)

            all_logits.append(outputs["cls_logit"].cpu())
            all_labels.append(labels.cpu())

            if bidx % 20 == 0 or bidx == n_total - 1:
                tag = f"Epoch {epoch} val" if epoch is not None else "Val"
                print(f"  [{tag}] batch {bidx}/{n_total}  loss={loss.item():.4f}")

    logits = torch.cat(all_logits)
    labels = torch.cat(all_labels)
    avg_loss = total_loss / len(loader.dataset)
    acc = accuracy(logits, labels).item()
    prec, rec, f1 = precision_recall_f1(logits, labels)

    return avg_loss, acc, prec, rec, f1


def save_checkpoint(model, optimizer, scheduler, epoch, metrics, path, config=None):
    state = {
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "scheduler_state_dict": scheduler.state_dict() if scheduler else None,
        "metrics": metrics,
    }
    if config:
        state["config"] = config
    torch.save(state, path)


def train_epoch(model, loader, criterion, optimizer, device, scaler, cutmix_prob, epoch=None):
    model.train()
    total_loss = 0.0
    all_logits = []
    all_labels = []
    n_total = len(loader)
    t_start = time.time()

    for bidx, batch in enumerate(loader):
        images = batch["image"].to(device)
        srms = batch["srm"].to(device)
        labels = batch["label"].to(device)
        masks = batch["mask"].to(device)

        optimizer.zero_grad()

        with torch.amp.autocast("cuda" if torch.cuda.is_available() else "cpu"):
            outputs = model(images, srms)
            loss, _ = criterion(outputs, labels, masks)

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
        scaler.step(optimizer)
        scaler.update()

        total_loss += loss.item() * images.size(0)
        all_logits.append(outputs["cls_logit"].detach().cpu())
        all_labels.append(labels.cpu())

        if bidx % 20 == 0 or bidx == n_total - 1:
            elapsed = time.time() - t_start
            remaining = (elapsed / (bidx + 1)) * (n_total - bidx - 1) if bidx > 0 else 0
            tag = f"Epoch {epoch}" if epoch is not None else "Train"
            print(f"  [{tag}] batch {bidx}/{n_total}  loss={loss.item():.4f}  {elapsed:.0f}s elapsed  ~{remaining:.0f}s remaining")

    logits = torch.cat(all_logits)
    labels = torch.cat(all_labels)
    avg_loss = total_loss / len(loader.dataset)
    acc = accuracy(logits, labels).item()
    prec, rec, f1 = precision_recall_f1(logits, labels)

    return avg_loss, acc, prec, rec, f1


def main():
    parser = argparse.ArgumentParser(description="AegisForgeryNet Trainer v2")
    parser.add_argument("--data-root", type=str, required=True,
                        help="Path to dataset root with dossier_XXXXXX folders")
    parser.add_argument("--img-size", type=int, default=384)
    parser.add_argument("--backbone", type=str, default="b0", choices=["b0", "b1", "b2", "b3", "b4"])
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--warmup-epochs", type=int, default=3)
    parser.add_argument("--cutmix-prob", type=float, default=0.0,
                        help="Probability of applying CutMix (0.0 = disabled)")
    parser.add_argument("--cls-loss", type=str, default="bce", choices=["bce", "focal"],
                        help="Classification loss type")
    parser.add_argument("--focal-gamma", type=float, default=2.0)
    parser.add_argument("--label-smoothing", type=float, default=0.0)
    parser.add_argument("--mask-bce-weight", type=float, default=1.0)
    parser.add_argument("--mask-dice-weight", type=float, default=1.0)
    parser.add_argument("--resume", type=str, default=None,
                        help="Path to checkpoint to resume from")
    parser.add_argument("--eval-only", action="store_true",
                        help="Run evaluation only (requires --resume)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--patience", type=int, default=10,
                        help="Early stopping patience (epochs)")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"AegisForgeryNet v2 , Training Pipeline")
    print(f"Backbone: efficientnet-{args.backbone} | Image size: {args.img_size}")
    print(f"Device: {device} | Batch: {args.batch_size} | Epochs: {args.epochs}")
    print(f"LR: {args.lr} | Warmup: {args.warmup_epochs} | Weight decay: {args.weight_decay}")
    print(f"CutMix: {args.cutmix_prob} | Cls loss: {args.cls_loss} | Label smoothing: {args.label_smoothing}")
    print(f"Data root: {args.data_root}")
    print("=" * 60)

    train_dataset = AegisForgeryDataset(
        args.data_root, split="train", img_size=args.img_size,
        augment=True, cutmix_prob=args.cutmix_prob,
    )
    val_dataset = AegisForgeryDataset(
        args.data_root, split="val", img_size=args.img_size,
        augment=False, cutmix_prob=0.0,
    )

    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=False,
        sampler=train_dataset.weighted_sampler,
        num_workers=args.workers, collate_fn=collate_fn,
    )
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False,
        num_workers=args.workers, collate_fn=collate_fn,
    )

    model = build_model(
        img_size=args.img_size, backbone=args.backbone,
        pretrained=True, srm_base_channels=32,
    ).to(device)

    n_pos = train_dataset.n_pos
    n_neg = train_dataset.n_neg
    pos_weight = n_neg / max(n_pos, 1)

    criterion = AegisLoss(
        pos_weight=pos_weight,
        mask_bce_weight=args.mask_bce_weight,
        mask_dice_weight=args.mask_dice_weight,
        cls_loss_type=args.cls_loss,
        focal_gamma=args.focal_gamma,
        label_smoothing=args.label_smoothing,
    )

    if args.backbone in ("b3", "b4"):
        optimizer = optim.AdamW(model.parameters(), lr=args.lr * 0.5,
                                weight_decay=args.weight_decay)
    else:
        optimizer = optim.AdamW(model.parameters(), lr=args.lr,
                                weight_decay=args.weight_decay)

    warmup_scheduler = LinearLR(optimizer, start_factor=0.1, total_iters=args.warmup_epochs)
    cosine_scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs - args.warmup_epochs)
    scheduler = SequentialLR(optimizer, [warmup_scheduler, cosine_scheduler],
                             milestones=[args.warmup_epochs])

    scaler = torch.amp.GradScaler("cuda" if torch.cuda.is_available() else "cpu")
    start_epoch = 0
    best_f1 = 0.0
    patience_counter = 0

    if args.resume:
        cp = torch.load(args.resume, map_location=device)
        model.load_state_dict(cp["model_state_dict"])
        optimizer.load_state_dict(cp["optimizer_state_dict"])
        if cp.get("scheduler_state_dict") and scheduler:
            scheduler.load_state_dict(cp["scheduler_state_dict"])
        start_epoch = cp.get("epoch", 0) + 1
        best_f1 = cp.get("metrics", {}).get("val_f1", 0.0)
        print(f"Resumed from {args.resume} (epoch {start_epoch - 1}, best val F1={best_f1:.4f})")

    if args.eval_only:
        val_loss, val_acc, val_prec, val_rec, val_f1 = evaluate(model, val_loader, criterion, device)
        print(f"\n[Evaluation] Loss={val_loss:.4f} Acc={val_acc:.4f} "
              f"Prec={val_prec:.4f} Rec={val_rec:.4f} F1={val_f1:.4f}")
        return

    print(f"\n{'Epoch':<6} {'Train Loss':<12} {'Train Acc':<12} {'Train F1':<12} "
          f"{'Val Loss':<12} {'Val Acc':<12} {'Val F1':<12} {'Best F1':<10}")
    print("-" * 80)

    for epoch in range(start_epoch, args.epochs):
        t0 = time.time()

        train_loss, train_acc, train_prec, train_rec, train_f1 = train_epoch(
            model, train_loader, criterion, optimizer, device, scaler, args.cutmix_prob, epoch=epoch)
        val_loss, val_acc, val_prec, val_rec, val_f1 = evaluate(
            model, val_loader, criterion, device, epoch=epoch)

        if scheduler:
            scheduler.step()
        current_lr = optimizer.param_groups[0]["lr"]
        elapsed = time.time() - t0

        ckpt_config = {"backbone": args.backbone, "img_size": args.img_size, "srm_base_channels": 32}

        is_best = val_f1 > best_f1
        if is_best:
            best_f1 = val_f1
            patience_counter = 0
            save_checkpoint(model, optimizer, scheduler, epoch,
                            {"val_f1": val_f1, "val_acc": val_acc, "val_loss": val_loss},
                            CHECKPOINT_DIR / "best_model.pt", config=ckpt_config)
        else:
            patience_counter += 1

        save_checkpoint(model, optimizer, scheduler, epoch,
                        {"val_f1": val_f1, "val_acc": val_acc, "val_loss": val_loss},
                        CHECKPOINT_DIR / "last_model.pt", config=ckpt_config)

        marker = " *" if is_best else "  "
        print(f"{epoch:<6} {train_loss:<12.4f} {train_acc:<12.4f} {train_f1:<12.4f} "
              f"{val_loss:<12.4f} {val_acc:<12.4f} {val_f1:<12.4f} {best_f1:<10.4f}{marker} "
              f"{elapsed:.1f}s  lr={current_lr:.2e}")

        if patience_counter >= args.patience:
            print(f"\nEarly stopping triggered after {epoch + 1} epochs (patience={args.patience})")
            break

    print(f"\nTraining complete. Best val F1: {best_f1:.4f}")
    print(f"Best checkpoint: {CHECKPOINT_DIR / 'best_model.pt'}")
    print(f"Last checkpoint: {CHECKPOINT_DIR / 'last_model.pt'}")

    final_val_loss, final_val_acc, final_val_prec, final_val_rec, final_val_f1 = evaluate(
        model, val_loader, criterion, device)
    print(f"\nFinal validation: Loss={final_val_loss:.4f} Acc={final_val_acc:.4f} "
          f"Prec={final_val_prec:.4f} Rec={final_val_rec:.4f} F1={final_val_f1:.4f}")


if __name__ == "__main__":
    main()
