"""Fit reviewed physical assets without stretching them into placement boxes."""
from cityg.assets import AssetRecord
from cityg.geometry.model import Vec3


def outdoor_asset_yaw_offset(record: AssetRecord) -> float:
    """Explicitly reviewed axis mapping, not an inferred front/back reversal."""
    angle = float(record.metadata.get("placement_yaw_offset_deg", 0))
    if angle % 90:
        raise ValueError("Outdoor placement-axis mapping must be a quarter turn")
    return angle


def outdoor_asset_ground_offset(record: AssetRecord, size: Vec3) -> float:
    """Distance from box bottom to the reviewed/authored soil contact plane."""
    fraction = float(record.metadata.get("ground_anchor_fraction", 0))
    if not 0 <= fraction <= 1:
        raise ValueError("Ground anchor fraction must be within unit bounds")
    return fraction * size.z


def fit_outdoor_asset(record: AssetRecord, envelope: Vec3) -> Vec3:
    """Opt-in proportional fitting within the already validated placement envelope.

    Legacy assets retain their existing interpretation. New curated assets carry
    measured proportions: all three dimensions get the same physical scale.
    The caller preserves the old bottom elevation when recentering the result.
    """
    if not record.metadata.get("preserve_physical_proportions") or not record.dimensions_m:
        return envelope
    if outdoor_asset_yaw_offset(record) % 180:
        envelope = Vec3(envelope.y, envelope.x, envelope.z)
    dimensions = record.dimensions_m
    scale = min(envelope.x / dimensions[0], envelope.y / dimensions[1], envelope.z / dimensions[2])
    return Vec3(*(value * scale for value in dimensions))
