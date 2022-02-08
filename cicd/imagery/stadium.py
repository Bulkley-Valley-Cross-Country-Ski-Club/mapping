from argparse import ArgumentParser
from logging import getLogger
from os import path
from typing import Final  # type: ignore

from osgeo import ogr
from pyproj import Transformer

from cicd.imagery.bounds import Bounds
from cicd.imagery.settings import EPSG_3857, EPSG_4326
from cicd.imagery.tiles_to_tiff import execute as tiles_to_tiff

LOGGER: Final = getLogger(__file__)


def execute(zoom: int, image_name: str, tile_src: str) -> None:
    gpkg_driver = ogr.GetDriverByName("GPKG")
    data_source = gpkg_driver.Open(
        path.abspath(path.join(path.dirname(__file__), "..", "..", "stadium-data.gpkg"))
    )
    opacity_layer = data_source.GetLayerByName("opacity_cover")
    opacity_extent = opacity_layer.GetExtent()
    transformer = Transformer.from_crs(EPSG_3857, EPSG_4326)
    latmin, lonmin = transformer.transform(opacity_extent[0], opacity_extent[2])
    latmax, lonmax = transformer.transform(opacity_extent[1], opacity_extent[3])
    tiles_to_tiff(
        tile_src,
        zoom,
        Bounds(
            ymin=latmin,
            ymax=latmax,
            xmin=lonmin,
            xmax=lonmax,
        ),
        image_name,
        EPSG_3857,
        EPSG_4326,
    )


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("zoom", type=int, help="zoom level for merged tiles")
    parser.add_argument("image_name", type=str, help="Name for the generated tif")
    parser.add_argument(
        "--tile_src",
        dest="tile_src",
        nargs=2,
        default=[
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        ],
        help="xyz URL template for source tiles",
    )
    args = vars(parser.parse_args())
    LOGGER.info(f"{__file__} called with {args}")
    execute(
        args["zoom"],
        args["image_name"],
        args["tile_src"][0],
    )
