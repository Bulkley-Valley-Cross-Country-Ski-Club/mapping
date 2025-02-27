import re
from argparse import ArgumentParser
from json import dumps
from logging import getLogger
from os import pardir, path, walk
from typing import Final  # type: ignore

from googleapiclient.http import MediaFileUpload
from yaml import safe_load

from cicd.upload.data_object import DataObject
from cicd.upload.service import create_service
from cicd.upload.settings import MIME_FOLDER, ROOT_FOLDER_NAME

LOGGER: Final = getLogger(__file__)
UPLOAD_FOLDER_NAME_KEY: Final = "UPLOAD_FOLDER_NAME"
UPLOAD_FOLDER_ROOT_KEY: Final = "UPLOAD_FOLDER_ROOT"
UPLOAD_REPORT_FILENAME: Final = "uploads.json"
BLACKLIST_PATHS: Final = [UPLOAD_REPORT_FILENAME, "changes.json"]


def set_permissions(service, id) -> None:
    service.permissions().create(
        fileId=id,
        body={
            "role": "reader",
            "type": "anyone",
            "allowFileDiscovery": True,
        },
        fields="*",
    ).execute()


def create_folder(service, name: str, parent_id: str = None) -> DataObject:
    LOGGER.info(f"creating folder {name}, parent: {parent_id}")
    folder_metadata = {
        "name": name,
        "mimeType": MIME_FOLDER,
    }
    if parent_id is not None:
        folder_metadata = {**folder_metadata, "parents": [parent_id]}
    folder = service.files().create(body=folder_metadata, fields="*").execute()
    LOGGER.debug(f"making folder {folder['id']} public")
    set_permissions(service, folder["id"])
    return DataObject(id=folder["id"])


def get_or_create_folder(service, name: str, parent_id: str = None) -> DataObject:
    safe_name: Final = re.sub("'", "_", name)
    LOGGER.info(f"searching for folder {safe_name}")
    folder_search: Final = (
        service.files()
        .list(q=f"name='{safe_name}' and mimeType='{MIME_FOLDER}'")
        .execute()
        .get("files")
    )
    if len(folder_search) == 0:
        return create_folder(service, safe_name, parent_id)
    else:
        LOGGER.debug(f"found folder {safe_name}")
        return DataObject(id=folder_search[0]["id"])


def create_or_update_latest(
    service, name: str, file_path: str, parent_folder_id: str
) -> None:
    safe_name: Final = re.sub("'", "_", name)
    LOGGER.info(f"searching for {safe_name}")
    search: Final = service.files().list(q=f"name='{safe_name}'").execute().get("files")
    if len(search) == 0:
        LOGGER.info(f"creating {safe_name} with {file_path}")
        remote_file_id = (
            service.files()
            .create(
                body={
                    "name": safe_name,
                    "parents": [parent_folder_id],
                },
                media_body=MediaFileUpload(file_path),
                fields="*",
            )
            .execute()["id"]
        )
        LOGGER.debug(f"making {remote_file_id} public")
        set_permissions(service, remote_file_id)
    else:
        LOGGER.info(f"updating {safe_name} with {file_path}")
        existing_file = search[0]
        service.files().update(
            fileId=existing_file["id"], media_body=MediaFileUpload(file_path), fields="*"
        ).execute()


def upload_folder(service, folder_name: str, root_path: str, update_latest: bool) -> None:
    LOGGER.info(f"uploading folder {folder_name}")
    remote_root_folder: Final = get_or_create_folder(service, ROOT_FOLDER_NAME, None)
    upload_path: Final = path.join(root_path, folder_name)

    with open(path.join(path.dirname(__file__), "latests.yml"), "r") as config_file:
        latests = safe_load(config_file)["latests"]

    folder_ids = {
        upload_path: create_folder(service, folder_name, remote_root_folder.id).id
    }
    file_ids = dict()
    for root, _, files in walk(upload_path):
        if root != upload_path:
            LOGGER.info(f"uploading folder {path.basename(root)}")
            parent_folder_id = folder_ids[path.abspath(path.join(root, pardir))]
            folder_ids[root] = create_folder(
                service,
                path.basename(root),
                parent_folder_id,
            ).id
        for file in files:
            if file in BLACKLIST_PATHS:
                LOGGER.debug(f"ignoring blacklist file {file}")
                continue
            LOGGER.info(
                f"uploading file {path.basename(file)} within {path.basename(root)}"
            )
            remote_file_id = (
                service.files()
                .create(
                    body={
                        "name": path.basename(file),
                        "parents": [folder_ids[root]],
                    },
                    media_body=MediaFileUpload(path.join(root, file)),
                    fields="*",
                )
                .execute()["id"]
            )
            LOGGER.debug(f"making file {remote_file_id} public")
            set_permissions(service, remote_file_id)

            local_unique_path = path.join(
                path.basename(root.replace(upload_path, "")), file
            )
            if local_unique_path in latests:
                if update_latest:
                    LOGGER.info(f"updating latest ({local_unique_path})")
                    create_or_update_latest(
                        service,
                        f"latest-{file}",
                        path.join(root, file),
                        remote_root_folder.id,
                    )
                else:
                    LOGGER.debug(f"not updating latest ({local_unique_path})")

            file_ids[local_unique_path] = remote_file_id

    with open(path.join(upload_path, UPLOAD_REPORT_FILENAME), "w") as report_file:
        report_file.write(dumps(file_ids))

    LOGGER.info(f"https://drive.google.com/drive/folders/{folder_ids[upload_path]}")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "upload_folder_name", type=str, help="Name of the folder to be uploaded"
    )
    parser.add_argument(
        "upload_folder_root_path",
        type=str,
        help="Path for the parent of the folder to be uploaded",
    )
    parser.add_argument(
        "--update_latest",
        dest="update_latest",
        action="store_true",
        help="If this upload should be considered the latest content",
    )
    parser.set_defaults(update_latest=False)
    args = vars(parser.parse_args())
    LOGGER.info(f"{__name__} called with {args}")
    upload_folder(
        create_service(),
        args["upload_folder_name"],
        args["upload_folder_root_path"],
        args["update_latest"],
    )
