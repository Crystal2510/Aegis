import torch
import torch.nn as nn
import torch.nn.functional as F
import timm


class ChannelAttention(nn.Module):
    def __init__(self, channels, reduction=16):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        self.mlp = nn.Sequential(
            nn.Conv2d(channels, channels // reduction, 1, bias=False),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels // reduction, channels, 1, bias=False),
        )

    def forward(self, x):
        avg_out = self.mlp(self.avg_pool(x))
        max_out = self.mlp(self.max_pool(x))
        scale = torch.sigmoid(avg_out + max_out)
        return x * scale


class SpatialAttention(nn.Module):
    def __init__(self, kernel_size=7):
        super().__init__()
        self.conv = nn.Conv2d(2, 1, kernel_size, padding=kernel_size // 2, bias=False)

    def forward(self, x):
        avg_out = torch.mean(x, dim=1, keepdim=True)
        max_out, _ = torch.max(x, dim=1, keepdim=True)
        concat = torch.cat([avg_out, max_out], dim=1)
        scale = torch.sigmoid(self.conv(concat))
        return x * scale


class CBAM(nn.Module):
    def __init__(self, channels, reduction=16):
        super().__init__()
        self.channel = ChannelAttention(channels, reduction)
        self.spatial = SpatialAttention()

    def forward(self, x):
        x = self.channel(x)
        x = self.spatial(x)
        return x


class SRMStream(nn.Module):
    def __init__(self, base_channels=32):
        super().__init__()
        c = base_channels
        self.stage1 = nn.Sequential(
            nn.Conv2d(1, c, 3, stride=2, padding=1), nn.BatchNorm2d(c), nn.ReLU(inplace=True))
        self.stage2 = nn.Sequential(
            nn.Conv2d(c, c * 2, 3, stride=2, padding=1), nn.BatchNorm2d(c * 2), nn.ReLU(inplace=True))
        self.stage3 = nn.Sequential(
            nn.Conv2d(c * 2, c * 4, 3, stride=2, padding=1), nn.BatchNorm2d(c * 4), nn.ReLU(inplace=True))
        self.stage4 = nn.Sequential(
            nn.Conv2d(c * 4, c * 8, 3, stride=2, padding=1), nn.BatchNorm2d(c * 8), nn.ReLU(inplace=True))

    def forward(self, x):
        f1 = self.stage1(x)
        f2 = self.stage2(f1)
        f3 = self.stage3(f2)
        f4 = self.stage4(f3)
        return [f1, f2, f3, f4]


class FusionBlock(nn.Module):
    def __init__(self, rgb_channels, srm_channels, out_channels):
        super().__init__()
        self.proj = nn.Sequential(
            nn.Conv2d(rgb_channels + srm_channels, out_channels, 1),
            nn.BatchNorm2d(out_channels), nn.ReLU(inplace=True))
        self.cbam = CBAM(out_channels)

    def forward(self, rgb_feat, srm_feat):
        if rgb_feat.shape[-2:] != srm_feat.shape[-2:]:
            srm_feat = F.interpolate(srm_feat, size=rgb_feat.shape[-2:], mode="bilinear", align_corners=False)
        return self.cbam(self.proj(torch.cat([rgb_feat, srm_feat], dim=1)))


class FPNNeck(nn.Module):
    def __init__(self, channels):
        super().__init__()
        top = channels[3]
        self.lateral4 = nn.Conv2d(channels[3], top, 1)
        self.lateral3 = nn.Conv2d(channels[2], top, 1)
        self.lateral2 = nn.Conv2d(channels[1], top, 1)
        self.lateral1 = nn.Conv2d(channels[0], top, 1)

        self.smooth4 = nn.Sequential(
            nn.Conv2d(top, channels[3], 3, padding=1), nn.BatchNorm2d(channels[3]), nn.ReLU(inplace=True))
        self.smooth3 = nn.Sequential(
            nn.Conv2d(top, channels[2], 3, padding=1), nn.BatchNorm2d(channels[2]), nn.ReLU(inplace=True))
        self.smooth2 = nn.Sequential(
            nn.Conv2d(top, channels[1], 3, padding=1), nn.BatchNorm2d(channels[1]), nn.ReLU(inplace=True))
        self.smooth1 = nn.Sequential(
            nn.Conv2d(top, channels[0], 3, padding=1), nn.BatchNorm2d(channels[0]), nn.ReLU(inplace=True))

    def forward(self, feats):
        c1, c2, c3, c4 = feats
        p4 = self.lateral4(c4)
        p3 = self.lateral3(c3) + F.interpolate(p4, size=c3.shape[-2:], mode="bilinear", align_corners=False)
        p2 = self.lateral2(c2) + F.interpolate(p3, size=c2.shape[-2:], mode="bilinear", align_corners=False)
        p1 = self.lateral1(c1) + F.interpolate(p2, size=c1.shape[-2:], mode="bilinear", align_corners=False)
        return [self.smooth1(p1), self.smooth2(p2), self.smooth3(p3), self.smooth4(p4)]


class DecoderBlock(nn.Module):
    def __init__(self, in_channels, skip_channels, out_channels):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels + skip_channels, out_channels, 3, padding=1),
            nn.BatchNorm2d(out_channels), nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1),
            nn.BatchNorm2d(out_channels), nn.ReLU(inplace=True),
        )

    def forward(self, x, skip):
        x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        x = torch.cat([x, skip], dim=1)
        return self.conv(x)


BACKBONE_CONFIGS = {
    "b0": {"model": "efficientnet_b0", "out_indices": (1, 2, 3, 4)},
    "b1": {"model": "efficientnet_b1", "out_indices": (1, 2, 3, 4)},
    "b2": {"model": "efficientnet_b2", "out_indices": (1, 2, 3, 4)},
    "b3": {"model": "efficientnet_b3", "out_indices": (1, 2, 3, 4)},
    "b4": {"model": "efficientnet_b4", "out_indices": (1, 2, 3, 4)},
}


class AegisForgeryNet(nn.Module):
    def __init__(self, img_size=384, backbone="b0", pretrained=True, srm_base_channels=32):
        super().__init__()
        self.img_size = img_size

        cfg = BACKBONE_CONFIGS.get(backbone, BACKBONE_CONFIGS["b0"])
        self.rgb_backbone = timm.create_model(
            cfg["model"], pretrained=pretrained, features_only=True,
            out_indices=cfg["out_indices"],
        )
        rgb_channels = self.rgb_backbone.feature_info.channels()

        self.srm_stream = SRMStream(base_channels=srm_base_channels)
        srm_c = [srm_base_channels, srm_base_channels * 2, srm_base_channels * 4, srm_base_channels * 8]

        fused_channels = [max(rc, sc) for rc, sc in zip(rgb_channels, srm_c)]
        self.fuse1 = FusionBlock(rgb_channels[0], srm_c[0], fused_channels[0])
        self.fuse2 = FusionBlock(rgb_channels[1], srm_c[1], fused_channels[1])
        self.fuse3 = FusionBlock(rgb_channels[2], srm_c[2], fused_channels[2])
        self.fuse4 = FusionBlock(rgb_channels[3], srm_c[3], fused_channels[3])

        self.fpn = FPNNeck(fused_channels)

        dec_skip = [fused_channels[0], fused_channels[1], fused_channels[2]]
        dec_out = [64, 128, 192]

        self.dec3 = DecoderBlock(fused_channels[3], dec_skip[2], dec_out[2])
        self.dec2 = DecoderBlock(dec_out[2], dec_skip[1], dec_out[1])
        self.dec1 = DecoderBlock(dec_out[1], dec_skip[0], dec_out[0])

        self.mask_head = nn.Sequential(
            nn.Conv2d(dec_out[0], 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(inplace=True),
            CBAM(32),
            nn.Conv2d(32, 1, 1),
        )

        pool_channels = fused_channels[3]
        self.cls_head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1), nn.Flatten(),
            nn.Linear(pool_channels, 256), nn.ReLU(inplace=True), nn.Dropout(0.3),
            nn.Linear(256, 128), nn.ReLU(inplace=True), nn.Dropout(0.2),
            nn.Linear(128, 1),
        )

        self.aux_cls_head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1), nn.Flatten(),
            nn.Linear(fused_channels[1], 64), nn.ReLU(inplace=True),
            nn.Linear(64, 1),
        )

    def forward(self, image, srm):
        rgb_feats = self.rgb_backbone(image)
        srm_feats = self.srm_stream(srm)

        f1 = self.fuse1(rgb_feats[0], srm_feats[0])
        f2 = self.fuse2(rgb_feats[1], srm_feats[1])
        f3 = self.fuse3(rgb_feats[2], srm_feats[2])
        f4 = self.fuse4(rgb_feats[3], srm_feats[3])

        p1, p2, p3, p4 = self.fpn([f1, f2, f3, f4])

        cls_logit = self.cls_head(p4).squeeze(-1)
        aux_cls = self.aux_cls_head(p2).squeeze(-1)

        d = self.dec3(p4, p3)
        d = self.dec2(d, p2)
        d = self.dec1(d, p1)
        mask_logit = self.mask_head(d)
        mask_logit = F.interpolate(mask_logit, size=(self.img_size, self.img_size),
                                   mode="bilinear", align_corners=False)

        return {"cls_logit": cls_logit, "mask_logit": mask_logit, "aux_cls": aux_cls}

    def freeze_backbone(self):
        for p in self.rgb_backbone.parameters():
            p.requires_grad = False

    def unfreeze_backbone_top(self, n_blocks=2):
        for p in self.rgb_backbone.parameters():
            p.requires_grad = False
        blocks = list(self.rgb_backbone.blocks) if hasattr(self.rgb_backbone, "blocks") else []
        for block in blocks[-n_blocks:]:
            for p in block.parameters():
                p.requires_grad = True


def build_model(img_size=384, backbone="b0", pretrained=True, srm_base_channels=32):
    return AegisForgeryNet(
        img_size=img_size, backbone=backbone,
        pretrained=pretrained, srm_base_channels=srm_base_channels,
    )


if __name__ == "__main__":
    for variant in ["b0", "b1", "b2"]:
        model = build_model(img_size=384, backbone=variant, pretrained=False)
        dummy_img = torch.randn(2, 3, 384, 384)
        dummy_srm = torch.randn(2, 1, 384, 384)
        out = model(dummy_img, dummy_srm)
        n_params = sum(p.numel() for p in model.parameters())
        print(f"{variant}: cls={out['cls_logit'].shape} mask={out['mask_logit'].shape} aux={out['aux_cls'].shape} params={n_params:,}")
