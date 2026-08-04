Archive Scout 3.0 Beta 1.3 — Windows x64

1. Extract the entire ZIP to a normal folder.
2. Open the ArchiveScout folder.
3. Run ArchiveScout.exe.

Keep every file in the ArchiveScout folder together. Archive Scout is packaged as a normal on-directory application and does not unpack an embedded executable into a temporary folder.

The release folder includes:
- SHA256SUMS.txt: hashes for the files in this package
- ArchiveScout-Windows-x64.spdx.json: software bill of materials

Official builds may be Authenticode signed. To check a signature:
1. Right-click ArchiveScout.exe.
2. Choose Properties.
3. Open Digital Signatures.

A missing Digital Signatures tab means the repository owner has not configured release signing yet. It does not by itself indicate malware. Download only from the official GitHub Release and compare the ZIP SHA-256 value with the published .sha256 file.
