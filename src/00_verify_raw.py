"""Verify the raw input files and write data/MANIFEST.csv.

For every raw file: size in bytes, SHA-256 and MD5, compared with the
expected checksum. Later scripts read the manifest and stop if a file they
need did not pass.
"""

import hashlib

import pandas as pd

import config as C
from common import rel


def file_hashes(path, chunk=1 << 20):
    sha = hashlib.sha256()
    md5 = hashlib.md5()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            sha.update(block)
            md5.update(block)
    return sha.hexdigest(), md5.hexdigest()


def main():
    rows = []
    for path, meta, algo, expected, expected_size in C.RAW_FILES:
        row = {"path": rel(path)}
        row.update({k: meta[k] for k in ("source", "version", "release_date", "download_date")})
        if path.exists():
            sha, md5 = file_hashes(path)
            size = path.stat().st_size
            got = sha if algo == "sha256" else md5
            match = got == expected
        else:
            sha = md5 = size = "missing"
            match = False
        row.update({
            "size_bytes": size,
            "sha256": sha,
            "md5": md5,
            "expected_checksum": f"{algo}:{expected}"
                                 + (f" ({meta['checksum_note']})" if meta.get("checksum_note") else ""),
            "checksum_match": "true" if match else "false",
            "licence": meta["licence"],
            "doi_or_url": meta["doi_or_url"],
        })
        rows.append(row)

        status = "OK" if match else ("MISSING" if size == "missing" else "MISMATCH")
        print(f"{status:8s} {row['path']}  size={size}")
        if expected_size is not None and size != "missing" and size != expected_size:
            print(f"         size differs from recorded size {expected_size}")
        if not match and size != "missing":
            print(f"         expected {algo} {expected}\n         obtained {algo} {got}")

    out = pd.DataFrame(rows)
    C.MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(C.MANIFEST, index=False)
    n_ok = (out["checksum_match"] == "true").sum()
    print(f"{rel(C.MANIFEST)}: {n_ok} of {len(out)} files verified")


if __name__ == "__main__":
    main()
