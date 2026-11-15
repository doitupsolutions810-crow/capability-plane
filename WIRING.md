# Wiring notes (Harbor audit follow-through, 2026-11-15)

This repo had **no CI at all** and no test suite of its own — its code is
exercised only indirectly through capability-authority's tests. Staged here:

- `ci/smoke.yml` — a complete GitHub Actions workflow: byte-compile the
  service, then run the crypto smoke test on every push and PR.
- `ci/smoke_test.py` — issue -> sign -> verify -> execute round-trip plus a
  tamper case that must be rejected. Verified locally before staging
  (PASS, exit 0).

The workflow is staged under `ci/` because the Muse GitHub App integration
does not hold GitHub's `workflows` permission and cannot write into
`.github/workflows/` (403 via both the contents and git-trees APIs). To
activate:

    mkdir -p .github/workflows && git mv ci/smoke.yml .github/workflows/smoke.yml

One move, no edits needed. Longer term, this repo should carry the same
pytest suite as capability-authority — the two `plane_service` packages are
diverged copies of one codebase, and only one of them is tested today.
