"""Download the NeRF authors' example archive and extract only the Lego scene.

Source URL is the HTTPS equivalent of bmild/nerf/download_example_data.sh.
No external Python packages are required. Existing downloaded bytes are reused.
"""

from pathlib import Path, PurePosixPath
import hashlib
import http.client
import json
import shutil
import struct
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
URL = "https://cseweb.ucsd.edu/~viscomp/projects/LF/papers/ECCV20/nerf/nerf_example_data.zip"


def download(url, destination, validator=zipfile.is_zipfile):
    if destination.exists() and validator(destination):
        print("Reusing download", destination, flush=True)
        return
    temporary = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(1, 9):
        offset = temporary.stat().st_size if temporary.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                append = response.status == 206 and offset > 0
                if not append:
                    offset = 0
                total = offset + int(response.headers.get("Content-Length", 0))
                print("Downloading", response.url, "attempt", attempt,
                      "resume_bytes", offset, "expected_bytes", total, flush=True)
                last_notice = time.monotonic()
                received = offset
                with temporary.open("ab" if append else "wb") as output:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
                        received += len(chunk)
                        if time.monotonic() - last_notice >= 15:
                            print("Downloaded MiB", round(received / 2**20, 1), flush=True)
                            last_notice = time.monotonic()
            if total and received < total:
                raise IOError(f"Connection ended after {received} of {total} bytes")
            if not validator(temporary):
                raise ValueError("Downloaded file failed integrity validation")
            temporary.replace(destination)
            return
        except (OSError, ValueError, http.client.HTTPException) as error:
            print("Download interrupted:", error, flush=True)
            if attempt == 8:
                raise
            time.sleep(min(attempt * 2, 10))


def main():
    archive = ROOT / "data/downloads/nerf_example_data.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    download(URL, archive)
    scene = ROOT / "data/raw/nerf_synthetic/lego"
    scene.mkdir(parents=True, exist_ok=True)
    manifest = {
        "dataset": "NeRF Synthetic",
        "scene": "lego",
        "kind": "synthetic rendered RGBA images with supplied Blender camera poses",
        "project": "https://github.com/bmild/nerf",
        "download_script": "https://github.com/bmild/nerf/blob/master/download_example_data.sh",
        "download_url": URL,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": None,
        "splits": {},
        "initial_point_cloud": "none provided or reconstructed; to use image-independent initialization",
        "pretrained_scene_model": "none; Splatfacto will optimize a scene from scratch",
    }
    if manifest["archive_sha256"] is None:
        digest = hashlib.sha256()
        with archive.open("rb") as stream:
            for chunk in iter(lambda: stream.read(2**20), b""):
                digest.update(chunk)
        manifest["archive_sha256"] = digest.hexdigest()
    with zipfile.ZipFile(archive) as z:
        candidates = [name for name in z.namelist() if name.endswith("lego/transforms_train.json")]
        if len(candidates) != 1:
            raise ValueError(f"Expected exactly one Lego scene, found {candidates}")
        prefix = candidates[0][:-len("transforms_train.json")]
        for split in ["train", "val", "test"]:
            metadata_name = f"transforms_{split}.json"
            metadata = json.loads(z.read(prefix + metadata_name))
            (scene / metadata_name).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            filenames = []
            shapes = set()
            for frame in metadata["frames"]:
                relative = PurePosixPath(frame["file_path"] + ".png")
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("Unsafe image path in archive")
                target = scene.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(prefix + str(relative)) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                with target.open("rb") as stream:
                    header = stream.read(26)
                if header[:8] != b"\x89PNG\r\n\x1a\n":
                    raise ValueError(f"Invalid PNG image: {target}")
                shapes.add(struct.unpack(">II", header[16:24]))
                filenames.append(str(relative))
            manifest["splits"][split] = {
                "image_count": len(filenames),
                "image_sizes": sorted(shapes),
                "camera_angle_x": metadata["camera_angle_x"],
                "filenames": filenames,
            }
            print("Extracted", split, len(filenames), "images", "sizes", sorted(shapes), flush=True)
    records = ROOT / "records/data"
    records.mkdir(parents=True, exist_ok=True)
    (records / "lego-source.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("DATASET_READY", scene, flush=True)


if __name__ == "__main__":
    main()
