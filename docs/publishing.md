# Publishing to GitHub

The prepared repository has this origin configured:

```text
https://github.com/RMF112018/Lakehouse-Weather.git
```

The ChatGPT GitHub connection used during scaffolding can write to existing repositories but cannot create a new repository or fork. The target repository therefore must exist before the initial push.

## Initial publication

After creating an empty private repository named `Lakehouse-Weather` under `RMF112018`:

```bash
git remote -v
git push -u origin main
```

## Upstream forks

The root repository already contains pinned submodule gitlinks to authoritative upstream commits. Initially they point upstream.

Recommended forks only where Lakehouse-specific changes are expected:

- `matthewwall/weewx-sdr` -> `RMF112018/weewx-sdr`
- `uajqq/weewx-belchertown-new` -> `RMF112018/weewx-belchertown-new`

After those forks exist:

```bash
./scripts/repoint-forks.sh RMF112018
git add .gitmodules
git commit -m "Point modifiable upstreams to Lakehouse forks"
git push
```

Then initialize all pinned code:

```bash
git submodule sync --recursive
git submodule update --init --recursive
```

Do not repoint `rtl_433`, `weewx-docker`, or `rtl_433_docker` unless Lakehouse actually needs to carry patches against them.
