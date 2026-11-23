# restic: pinned binary for the backup copy (A4.5)

Approved by the owner on 21/11/2026 ("duyệt tải"). Downloaded by hand into `infra/local/tools/restic-0.19.1/` (git-ignored).

| Item | Value |
|---|---|
| Version | restic 0.19.1 (published 2026-07-05; 0.20.0 was only two days old, so the older stable release was chosen) |
| Source | https://github.com/restic/restic/releases/tag/v0.19.1 |
| Archive | `restic_0.19.1_windows_amd64.zip`, 11,237,567 bytes |
| Archive SHA-256 | `da948ad707ed690426473aaba2046cd61f8f90f6f0e7dab6be0d5796531de67d` (matches the `SHA256SUMS` file of the same release) |
| Executable SHA-256 | `b0dd1fd21eea5d8fe1325f55f7118213c21f36de8a261e04c0624a5ab9fd7830` |
| Not done | The GPG signature (`SHA256SUMS.asc`) was not verified: no signing key is held here. Trust rests on the release page and the checksum file. |

Check done: `infra/cloud/offsite.py init` and `check` against a local scratch repository with this binary (`CAMPUS247_RESTIC_BIN`), after one file was backed up by restic itself. Nothing was sent anywhere. The off-site location (A4.6) is still the owner's choice.

To use it: set `CAMPUS247_RESTIC_BIN` to the executable path, `CAMPUS247_RESTIC_REPOSITORY` to the repository and `RESTIC_PASSWORD_FILE` to the password file.
