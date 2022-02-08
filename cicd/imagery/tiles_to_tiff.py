from hashlib import md5
from http import HTTPStatus
from logging import getLogger
from math import atan, cos, degrees, floor, log, pi, radians, sinh, tan
from os import path
from random import choice
from re import search
from typing import Final, List, Tuple  # type: ignore

from osgeo.gdal import BuildVRT, Translate
from PIL import Image
from pygeotile.tile import Tile
from requests import get

from cicd.imagery.bounds import Bounds
from cicd.imagery.settings import EPSG_3857, EPSG_4326
from cicd.imagery.url_format import UrlFormat

LOGGER: Final = getLogger(__file__)
OUTPUT_DIR: Final = path.join(path.dirname(__file__), "output")
MERCATOR_AXIS_MAX: Final = 20037508.3427892
ZOOM_TO_TILE_COUNT_ONE_AXIS: Final = [pow(2, x) for x in range(21)]
TILE_PIXELS: Final = 256


def execute(
    tile_src: str,
    zoom: int,
    bounds: Bounds,
    image_name: str,
    target_epsg_code: str,
    source_epsg_code: str,
) -> str:
    bbox_to_xyz = {
        EPSG_4326: bbox_4326_to_xyz,
        EPSG_3857: bbox_3857_to_xyz,
    }
    x_min, x_max, y_min, y_max = bbox_to_xyz[source_epsg_code](
        bounds.xmin, bounds.xmax, bounds.ymin, bounds.ymax, zoom
    )
    LOGGER.info(f"Fetching up to {(x_max - x_min + 1) * (y_max - y_min + 1)} tiles")
    tmpdirpath = path.join(path.dirname(__file__), "tmp")
    tif_paths = []
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            img_base = path.join(
                tmpdirpath, f"{zoom}-{y}-{x}_{md5(tile_src.encode()).hexdigest()}."
            )
            png_path = f"{img_base}png"
            png_rgb_path = f"{img_base}rgb.png"
            tif_path = f"{img_base}tif"
            if path.exists(tif_path):
                LOGGER.debug(f"file exists {tif_path}")
            else:
                try:
                    if not path.exists(png_path):
                        url = build_tile_url(tile_src, zoom, x, y)
                        LOGGER.debug(f"retrieving {zoom}/{y}/{x} from {url}")
                        with get(
                            url, headers={"User-Agent": get_random_user_agent()}
                        ) as response:
                            if response.status_code == HTTPStatus.OK:
                                with open(png_path, "wb") as file:
                                    file.write(response.content)
                            else:
                                LOGGER.warning(
                                    f"failed to retrieve {url}: {response.status_code}, {response.text}"
                                )
                    png_use_path = png_path
                    if Image.open(png_path).mode == "P":
                        Translate(png_rgb_path, png_path, rgbExpand="rgb")
                        png_use_path = png_rgb_path
                    georeference_tile(
                        target_epsg_code, x, y, zoom, png_use_path, tif_path
                    )
                except Exception as e:
                    LOGGER.error(e)
                    raise e
            tif_paths.append(tif_path)

    output_path = path.join(OUTPUT_DIR, f"{image_name}.tif")
    LOGGER.info(f"generating merged tif to {output_path}")
    vrt = BuildVRT("", tif_paths, addAlpha=True)
    Translate(
        output_path,
        vrt,
        format="GTiff",
        projWin=[
            bounds.xmin,
            bounds.ymax,
            bounds.xmax,
            bounds.ymin,
        ],
        projWinSRS=source_epsg_code,
    )
    return output_path


def bbox_4326_to_xyz(
    lon_min: float, lon_max: float, lat_min: float, lat_max: float, z: int
) -> Tuple[int, int, int, int]:
    def sec(x):
        return 1 / cos(x)

    def latlon_to_xyz(lat, lon, z):
        tile_count = pow(2, z)
        x = (lon + 180) / 360
        y = (1 - log(tan(radians(lat)) + sec(radians(lat))) / pi) / 2
        return (tile_count * x, tile_count * y)

    x_min, y_max = latlon_to_xyz(lat_min, lon_min, z)
    x_max, y_min = latlon_to_xyz(lat_max, lon_max, z)

    return (floor(x_min), floor(x_max), floor(y_min), floor(y_max))


def bbox_3857_to_xyz(
    xmin: float, xmax: float, ymin: float, ymax: float, z: int
) -> Tuple[int, int, int, int]:
    tiles_one_axis = ZOOM_TO_TILE_COUNT_ONE_AXIS[z]
    metres_per_tile = (MERCATOR_AXIS_MAX * 2) / tiles_one_axis
    tile_x_min = floor((xmin + MERCATOR_AXIS_MAX) / metres_per_tile)
    tile_x_max = floor((xmax + MERCATOR_AXIS_MAX) / metres_per_tile)
    tile_y_min = tiles_one_axis - floor((ymax + MERCATOR_AXIS_MAX) / metres_per_tile) - 1
    tile_y_max = tiles_one_axis - floor((ymin + MERCATOR_AXIS_MAX) / metres_per_tile) - 1
    return (tile_x_min, tile_x_max, tile_y_min, tile_y_max)


def georeference_tile(
    epsg_code: str, x: int, y: int, z: int, tile_path: str, output_path: str
) -> None:
    bounds_providers = {
        EPSG_4326: tile_bounds_4326,
        EPSG_3857: tile_bounds_3857,
    }
    if epsg_code not in bounds_providers.keys():
        raise Exception(
            f"cannot georeference tile in {epsg_code}. Options: {bounds_providers.keys()}"
        )
    bounds = bounds_providers[epsg_code](x, y, z)
    Translate(output_path, tile_path, outputSRS=epsg_code, outputBounds=bounds)


def tile_bounds_3857(x: int, y: int, z: int) -> List[float]:
    metres_per_tile = (MERCATOR_AXIS_MAX * 2) / ZOOM_TO_TILE_COUNT_ONE_AXIS[z]
    return [
        -MERCATOR_AXIS_MAX + metres_per_tile * x,
        MERCATOR_AXIS_MAX - metres_per_tile * y,
        -MERCATOR_AXIS_MAX + metres_per_tile * (x + 1),
        MERCATOR_AXIS_MAX - metres_per_tile * (y + 1),
    ]


def tile_bounds_4326(x: int, y: int, z: int) -> List[float]:
    def mercatorToLat(mercatorY: int) -> float:
        return degrees(atan(sinh(mercatorY)))

    def y_to_lat_edges(y: int, z: int) -> Tuple[float, float]:
        tile_count = pow(2, z)
        unit = 1 / tile_count
        relative_y1 = y * unit
        relative_y2 = relative_y1 + unit
        lat1 = mercatorToLat(pi * (1 - 2 * relative_y1))
        lat2 = mercatorToLat(pi * (1 - 2 * relative_y2))
        return (lat1, lat2)

    def x_to_lon_edges(x: int, z: int) -> Tuple[float, float]:
        tile_count = pow(2, z)
        unit = 360 / tile_count
        lon1 = -180 + x * unit
        lon2 = lon1 + unit
        return (lon1, lon2)

    def tile_edges(x: int, y: int, z: int) -> List[float]:
        lat1, lat2 = y_to_lat_edges(y, z)
        lon1, lon2 = x_to_lon_edges(x, z)
        return [lon1, lat1, lon2, lat2]

    return tile_edges(x, y, z)


# https://www.scrapehero.com/how-to-fake-and-rotate-user-agents-using-python-3/
def get_random_user_agent() -> str:
    user_agent_list = (
        # Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36",
        "Mozilla/5.0 (Windows NT 5.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.157 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36",
        # Firefox
        "Mozilla/4.0 (compatible; MSIE 9.0; Windows NT 6.1)",
        "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko",
        "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; WOW64; Trident/5.0)",
        "Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko",
        "Mozilla/5.0 (Windows NT 6.2; WOW64; Trident/7.0; rv:11.0) like Gecko",
        "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
        "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.0; Trident/5.0)",
        "Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; rv:11.0) like Gecko",
        "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0)",
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64; Trident/7.0; rv:11.0) like Gecko",
        "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; WOW64; Trident/6.0)",
        "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; Trident/6.0)",
        "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0; .NET CLR 2.0.50727; .NET CLR 3.0.4506.2152; .NET CLR 3.5.30729)",
    )
    return choice(user_agent_list)


def determine_url_format(url_template: str) -> UrlFormat:
    if search(r"\{q\}", url_template):
        return UrlFormat.QUADKEY
    elif (
        search(r"\{z\}", url_template)
        and search(r"\{x\}", url_template)
        and search(r"\{y\}", url_template)
    ):
        return UrlFormat.XYZ
    else:
        raise ValueError(f"URL is not an expected format: {url_template}")


def build_tile_url(url_template: str, z: int, x: int, y: int) -> str:
    url_format = determine_url_format(url_template)
    if url_format == UrlFormat.QUADKEY:
        return url_template.format(
            q=Tile.from_google(google_x=x, google_y=y, zoom=z).quad_tree
        )
    if url_format == UrlFormat.XYZ:
        return url_template.format(z=z, x=x, y=y)
