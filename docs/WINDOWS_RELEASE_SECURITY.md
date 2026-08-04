# Windows release security and signing

Beta 1.3 keeps Archive Scout's application features intact while changing the Windows release pipeline to reduce false-positive detections.

## Package layout

The Windows application remains a PyInstaller `--onedir` build. UPX is explicitly disabled, Windows version metadata is embedded in `ArchiveScout.exe`, and the release no longer contains PowerShell installation scripts or command files that use `ExecutionPolicy Bypass`.

The Windows executable uses the in-process `httpx` and `urllib3` transports. The external curl subprocess fallback is not included in Windows builds. Linux and macOS source builds can still load the curl fallback dynamically.

## Artifact Signing configuration

Tagged releases are blocked unless Windows Artifact Signing is enabled. Manual workflow runs can still produce unsigned test artifacts.

Create these repository variables:

```text
ENABLE_WINDOWS_ARTIFACT_SIGNING=true
WINDOWS_SIGNING_ENDPOINT=https://<region>.codesigning.azure.net/
WINDOWS_SIGNING_ACCOUNT_NAME=<account>
WINDOWS_SIGNING_PROFILE_NAME=<profile>
```

Create these repository secrets for the Azure workload identity used by `azure/login`:

```text
AZURE_CLIENT_ID
AZURE_TENANT_ID
AZURE_SUBSCRIPTION_ID
```

The identity needs the Artifact Signing Certificate Profile Signer role and a federated credential scoped to the repository/workflow.

The workflow signs and timestamps:

```text
release/ArchiveScout-Windows-x64/ArchiveScout/ArchiveScout.exe
```

It then verifies the Authenticode signature before generating hashes and the final ZIP.

## Release evidence

Every Windows package contains:

```text
ArchiveScout-Windows-x64.signature.txt
ArchiveScout-Windows-x64.spdx.json
SHA256SUMS.txt
```

The workflow also publishes:

```text
ArchiveScout-Windows-x64.files.sha256
ArchiveScout-Windows-x64.spdx.json
```

## Defender false-positive submission

Signing does not retroactively clear an antivirus detection on an older binary. Submit the exact flagged executable or ZIP to Microsoft's file-submission portal as a software developer and select the option indicating that the file is clean/incorrectly detected. Keep the submission ID and the exact SHA-256 hash with the release record. After a Windows package is staged, `scripts/create_defender_submission.ps1` creates a compact submission ZIP containing the executable and available signature, SBOM, hash, and validation evidence.

Do not instruct users to disable Defender or add broad exclusions. Replace the affected public asset only after a clean rebuild, signature verification, and submission when needed.
