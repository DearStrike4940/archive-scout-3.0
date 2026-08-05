Archive Scout 3.0 Beta 1.4 for Windows

VERIFY THE DOWNLOAD
1. Download ArchiveScout-Windows-x64.zip and its matching .sha256 file from the official GitHub release.
2. In PowerShell, run:
   Get-FileHash .\ArchiveScout-Windows-x64.zip -Algorithm SHA256
3. Confirm that the displayed hash matches the published checksum.
4. For signed releases, right-click ArchiveScout\ArchiveScout.exe, choose Properties, open Digital Signatures, and confirm that Windows reports a valid signature from the published Archive Scout signer.

MARK OF THE WEB / UNBLOCK
Windows normally marks ZIP files downloaded from the internet. Before extracting, right-click ArchiveScout-Windows-x64.zip, choose Properties, select Unblock when that option is present, click Apply, and then extract the ZIP. Only do this after verifying the source, checksum, and digital signature. Unblocking the ZIP before extraction prevents the internet-zone marker from being copied to every extracted file.

RUN WITHOUT INSTALLING
Open the extracted ArchiveScout folder and run ArchiveScout.exe.

OPTIONAL INSTALLER
The included Install Archive Scout.cmd copies the onedir application to your local Programs folder and creates shortcuts. It does not require administrator access.

DEFENDER FALSE POSITIVES
If Microsoft Defender identifies the verified, signed ArchiveScout.exe as malware:
1. Do not disable Defender globally.
2. Record the exact detection name and Defender security-intelligence version.
3. Confirm the SHA-256 hash and Authenticode signature.
4. Submit the exact flagged file to Microsoft as a software developer / clean false positive:
   https://www.microsoft.com/wdsi/filesubmission
5. Keep the Microsoft submission ID and wait for the final determination before redistributing that exact binary.

A digital signature and a matching checksum establish publisher and file integrity, but no build setting can force antivirus software to classify a file as safe. Each released Windows executable should be signed consistently and submitted to Microsoft if it is incorrectly detected.
