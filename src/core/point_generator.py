import numpy as np
from src.models.project import Point


def generate_points(
    image_width: int,
    image_height: int,
    count: int,
    distribution: str = "random",
    border: int = 0,
    border_rect: list | None = None,
) -> list[Point]:
    """
    Generate points on an image.

    Args:
        image_width: Width of the image in pixels
        image_height: Height of the image in pixels
        count: Number of points to generate
        distribution: 'random', 'stratified', or 'uniform'
        border: Uniform pixel border to exclude (ignored when border_rect is set)
        border_rect: [x_min, y_min, x_max, y_max] from manual click; overrides border

    Returns:
        List of Point objects
    """
    if border_rect:
        x_min, y_min, x_max, y_max = border_rect
    else:
        x_min = border
        x_max = image_width - border
        y_min = border
        y_max = image_height - border

    if x_min >= x_max or y_min >= y_max:
        raise ValueError("Border exclusion too large for image size.")

    if distribution == "random":
        coords = _random_points(x_min, x_max, y_min, y_max, count)
    elif distribution == "stratified":
        coords = _stratified_points(x_min, x_max, y_min, y_max, count)
    elif distribution == "uniform":
        coords = _uniform_grid_points(x_min, x_max, y_min, y_max, count)
    else:
        raise ValueError(f"Unknown distribution: {distribution}")

    return [Point(x=float(x), y=float(y), index=i) for i, (x, y) in enumerate(coords)]


def _random_points(x_min, x_max, y_min, y_max, count):
    xs = np.random.uniform(x_min, x_max, count)
    ys = np.random.uniform(y_min, y_max, count)
    return list(zip(xs, ys))


def _stratified_points(x_min, x_max, y_min, y_max, count):
    """Stratified random sampling — divides image into grid cells, one point per cell."""
    cols = int(np.ceil(np.sqrt(count)))
    rows = int(np.ceil(count / cols))

    cell_w = (x_max - x_min) / cols
    cell_h = (y_max - y_min) / rows

    coords = []
    for row in range(rows):
        for col in range(cols):
            if len(coords) >= count:
                break
            x = x_min + col * cell_w + np.random.uniform(0, cell_w)
            y = y_min + row * cell_h + np.random.uniform(0, cell_h)
            x = min(x, x_max)
            y = min(y, y_max)
            coords.append((x, y))

    return coords[:count]


def _uniform_grid_points(x_min, x_max, y_min, y_max, count):
    """Uniform grid — evenly spaced points across the image."""
    cols = int(np.ceil(np.sqrt(count)))
    rows = int(np.ceil(count / cols))

    xs = np.linspace(x_min, x_max, cols)
    ys = np.linspace(y_min, y_max, rows)

    coords = [(x, y) for y in ys for x in xs]
    return coords[:count]
