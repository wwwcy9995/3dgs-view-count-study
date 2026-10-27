"""Download torchvision's official LPIPS feature weights with resumable retries."""

import hashlib
from pathlib import Path
from urllib.parse import urlsplit

from download_lego import download


def prepare_alexnet():
    import torch
    from torchvision.models import AlexNet_Weights
    url = AlexNet_Weights.IMAGENET1K_V1.url
    filename = Path(urlsplit(url).path).name
    prefix = Path(filename).stem.rsplit("-",1)[1]
    destination = Path(torch.hub.get_dir()) / "checkpoints" / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    def valid(file):
        digest = hashlib.sha256()
        with file.open("rb") as stream:
            for chunk in iter(lambda: stream.read(2**20),b""):
                digest.update(chunk)
        return digest.hexdigest().startswith(prefix)
    download(url, destination, validator=valid)
    print("OFFICIAL_ALEXNET_HASH_VERIFIED", filename, flush=True)


if __name__ == "__main__":
    prepare_alexnet()
