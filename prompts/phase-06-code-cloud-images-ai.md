# Phase 6 — Code, cloud shares, images, AI resources

Read `CLAUDE.md` (routing steps 4, 5, 7, 9, 10) first.

Deliverables:
- `handlers/git_code.py`: GitHub, GitLab, Codeberg, Bitbucket, gists — clone repo (shallow option), download a folder or single file via raw URLs, release assets (GitHub REST, optional token in settings).
- `handlers/cloud_share.py`: Google Drive (incl. large-file confirm), Dropbox (`dl=1`), OneDrive public links → direct URLs; MEGA via `megatools` if installed.
- `handlers/gallery.py`: gallery-dl as a subprocess (GPL); grid preview of items; pick some or all.
- `handlers/ai_resources.py`: Hugging Face models/datasets via `huggingface_hub` (file picker, revision), Civitai pages, Kaggle (needs user key), prompt repos.
- `handlers/webpage.py`: fallback for HTML pages — save as single HTML or PDF, list media/document links found on the page for the user to pick.
- Web: Code and AI page, Images page.
- respx tests for each handler.

**Acceptance check:** a repo, a single file from a repo, a public Drive file and a Flickr CC album all download.
Commit: `feat: phase 6 code, cloud, images and ai`.
