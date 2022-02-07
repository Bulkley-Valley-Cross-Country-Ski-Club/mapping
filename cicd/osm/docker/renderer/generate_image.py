"""
Adapted from https://raw.githubusercontent.com/openstreetmap/mapnik-stylesheets/master/generate_image.py
"""

from hashlib import md5
from json import dumps, loads
from logging import getLogger
from os import environ, linesep, path
from typing import Final, List  # type: ignore

import mapnik

from .render_candidate import RenderCandidate

LOGGER: Final = getLogger(__file__)
ZOOM_TO_TILE_COUNT: Final = [pow(4, x) for x in range(21)]
MERCATOR_AXIS_MAX: Final = 20037508.3427892
MERCATOR_AXIS_RANGE: Final = MERCATOR_AXIS_MAX * 2
TILE_PIXELS: Final = 256


def generate() -> None:
    pixel_max = int(environ.get("PIXEL_MAX", 1200))
    # currently generating one image for each change MBR
    # preferred solution requires solving an optimisation problem - attempt to include as many other changes
    # in the same image without exceeding a maximum preferred extent or image size
    with open(environ["CHANGES_3857"], "r") as f:
        changes = loads(f.read())
    for multipolygon in changes["features"]:
        for polygon in multipolygon["geometry"]["coordinates"]:
            change_rect = grow_rect_for_rendering(polygon[0])
            preferred_candidate = None
            # assumes candidates list is ordered zoom_level ascending, order derived from ZOOM_TO_TILE_COUNT
            for candidate in image_dims_for_rect(change_rect):
                if candidate.x <= pixel_max and candidate.y <= pixel_max:
                    preferred_candidate = candidate
            if preferred_candidate is None:
                LOGGER.error(
                    f"Unable to determine preferred export candidate from list: {linesep}{image_dims_for_rect(change_rect)}"
                )

            map = mapnik.Map(preferred_candidate.x, preferred_candidate.y)
            mapnik.load_map(map, environ["MAPNIK_MAP_FILE"])
            map.aspect_fix_mode = mapnik.aspect_fix_mode.RESPECT
            map.zoom_to_box(
                mapnik.Box2d(
                    change_rect[0][0],
                    change_rect[0][1],
                    change_rect[1][0],
                    change_rect[2][1],
                )
            )
            png_path = path.join(
                environ["OUTPUT_DIR"],
                f"{environ.get('OUTPUT_PREFIX', 'osm-')}{md5(dumps(change_rect).encode()).hexdigest()}.png",
            )
            mapnik.render_to_file(map, png_path, "png")
            LOGGER.info(f"rendered to {png_path}")


def grow_rect_for_rendering(
    rect_3857: List[List[float]], grow_factor: float = 1.5, min_ratio: float = 0.2
) -> List[List[float]]:
    xs = [pair[0] for pair in rect_3857]
    ys = [pair[1] for pair in rect_3857]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    xfactor = (xmax - xmin) * grow_factor
    yfactor = (ymax - ymin) * grow_factor
    xminnew, xmaxnew = xmin - xfactor, xmax + xfactor
    yminnew, ymaxnew = ymin - yfactor, ymax + yfactor
    xrangenew = xmaxnew - xminnew
    yrangenew = ymaxnew - yminnew
    if xrangenew < yrangenew and xrangenew / yrangenew < min_ratio:
        xrangenewchange = yrangenew * min_ratio
        xmaxnew += (xrangenewchange - xrangenew) / 2
        xminnew -= (xrangenewchange - xrangenew) / 2
    if xrangenew > yrangenew and yrangenew / xrangenew < min_ratio:
        yrangenewchange = xrangenew * min_ratio
        ymaxnew += (yrangenewchange - yrangenew) / 2
        yminnew -= (yrangenewchange - yrangenew) / 2

    return [
        [xminnew, yminnew],
        [xmaxnew, yminnew],
        [xmaxnew, ymaxnew],
        [xminnew, ymaxnew],
        [xminnew, yminnew],
    ]


def image_dims_for_rect(rect_3857: List[List[float]]) -> List[RenderCandidate]:
    x_range = rect_3857[1][0] - rect_3857[0][0]
    y_range = rect_3857[2][1] - rect_3857[0][1]
    return [
        RenderCandidate(
            zoom_level=i,
            x=round(TILE_PIXELS * x_range / (MERCATOR_AXIS_RANGE / count)),
            y=round(TILE_PIXELS * y_range / (MERCATOR_AXIS_RANGE / count)),
        )
        for i, count in enumerate(ZOOM_TO_TILE_COUNT)
    ]


if __name__ == "__main__":
    generate()
