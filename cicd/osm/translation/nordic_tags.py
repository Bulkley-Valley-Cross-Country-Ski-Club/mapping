"""
Translations for Nordic Centre trails.
Dog-friendly trails are treated as one-way. These trails are only one-way for dogs but the OSM tags do not appear to support this nuance.
"""
from os import environ
from typing import Final  # type: ignore

from ogr2osm import TranslationBase

PISTE_PREFIX: Final = "piste:"
BVNORDIC_PREFIX: Final = "bvnordic:"


class NordicTags(TranslationBase):
    def filter_tags(self, tags):
        if not tags:
            return
        return {
            f"{BVNORDIC_PREFIX}trail_name": tags.get("trail_name", ""),
            "name": tags.get("segment_name", ""),
            f"{PISTE_PREFIX}type": "nordic",
            f"{PISTE_PREFIX}difficulty": [
                value
                for key, value in {
                    (0, 1): "easy",
                    (2,): "intermediate",
                    (3,): "advanced",
                }.items()
                if int(tags.get("difficulty", 0)) in key
            ][0],
            f"{PISTE_PREFIX}oneway": {0: "no", 1: "yes"}[int(tags.get("dog_friend", 0))],
            "dog": {0: "no", 1: "yes"}[int(tags.get("dog_friend", 0))],
            "lit": {0: "no", 1: "yes"}[int(tags.get("lights", 0))],
            f"{PISTE_PREFIX}grooming": {0: "classic;skating", 1: "classic"}[int(tags.get("classic_only", 0))],
            "network": "BV Nordic Centre",
            f"{BVNORDIC_PREFIX}closed": {"0": "no", "1": "yes"}[str(tags.get("closed"))],
            f"{BVNORDIC_PREFIX}readme": "Created by Bulkley Valley Nordic Centre GIS. Please contact osm@bvnordic.ca before making any changes.",
            f"{BVNORDIC_PREFIX}commit-sha": f"{environ['GITHUB_SHA']}",
        }
