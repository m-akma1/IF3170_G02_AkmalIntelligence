import uma_ai.core.model as model

def extents(package: model.PackageState) -> tuple[int, int, int]:
    """
    Panjang paket di sumbu (x, y, z) sesuai orientasinya.

    Contoh: Dimension(w=1, l=2, h=3) dengan Orientation(w=y, l=z, h=x)
    menghasilkan (3, 1, 2).
    """
    orient = model.ORIENTATION[package.orientation_id]
    size = {
        orient["w"]: package.width,
        orient["l"]: package.length,
        orient["h"]: package.height,
    }
    return size["x"], size["y"], size["z"]

def bounds(package: model.PackageState) -> tuple[int, int, int, int, int, int]:
    """(x_min, y_min, z_min, x_max, y_max, z_max) dari paket."""
    dx, dy, dz = extents(package)
    return (
        package.x, package.y, package.z,
        package.x + dx, package.y + dy, package.z + dz,
    )

def overlap_xy(a: model.PackageState, b: model.PackageState) -> bool:
    """True jika proyeksi kedua paket pada bidang xy beririsan (luas > 0)."""
    ax0, ay0, _, ax1, ay1, _ = bounds(a)
    bx0, by0, _, bx1, by1, _ = bounds(b)
    return ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0

def is_on_top_of(upper: model.PackageState, lower: model.PackageState) -> bool:
    """True jika paket atas menempel pada paket bawah."""
    return upper.z == bounds(lower)[5] and overlap_xy(upper, lower)

def percent_on_top_of(upper: model.PackageState, lower: model.PackageState) -> float:
    """Persentase bagian paket atas yang ditumpu paket bawah terhadap luas paket ataas."""
    ax0, ay0, az0, ax1, ay1, _ = bounds(upper)
    bx0, by0, _, bx1, by1, bz1 = bounds(lower)

    if az0 != bz1:
        return 0.0

    overlap_area = max(0, min(ax1, bx1) - max(ax0, bx0)) * max(0, min(ay1, by1) - max(ay0, by0))
    upper_area = (ax1 - ax0) * (ay1 - ay0)
    return overlap_area / upper_area if upper_area > 0 else 0.0