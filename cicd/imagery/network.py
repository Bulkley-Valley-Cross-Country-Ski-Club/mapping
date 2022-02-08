from argparse import ArgumentParser
from logging import getLogger
from os import path
from typing import Final  # type: ignore

from osgeo import ogr

from cicd.imagery.bounds import Bounds
from cicd.imagery.settings import EPSG_3857, EPSG_4326
from cicd.imagery.tiles_to_tiff import execute as tiles_to_tiff

LOGGER: Final = getLogger(__file__)


def execute(zoom: int, image_name: str, tile_src: str) -> None:
    gpkg_driver = ogr.GetDriverByName("GPKG")
    data_source = gpkg_driver.Open(
        path.abspath(path.join(path.dirname(__file__), "..", "..", "main-data.gpkg"))
    )
    bounds_layer = data_source.ExecuteSQL(
        "SELECT ST_Envelope(ST_Transform(ST_Buffer(ST_Envelope(ST_Union(geom)), 100), 4326)) FROM Trails"
    )
    lonmin, lonmax, latmin, latmax = bounds_layer.GetExtent()
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
        default=["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        help="xyz URL template for source tiles",
    )
    args = vars(parser.parse_args())
    LOGGER.info(f"{__file__} called with {args}")
    execute(
        args["zoom"],
        args["image_name"],
        args["tile_src"][0],
    )
