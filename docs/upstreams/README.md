# Upstream dependencies

`vendor/` contains pinned Git submodule links. `UPSTREAMS.lock` is the human-readable lock record.

## Runtime / source dependencies

- `merbanan/rtl_433` — RF decoding.
- `matthewwall/weewx-sdr` — WeeWX SDR station driver and WH65B/WH32-family packet mappings.
- `uajqq/weewx-belchertown-new` — initial responsive dashboard skin.
- `felddy/weewx-docker` — reference/source for the `felddy/weewx:5` container used as the base image.
- `hertzg/rtl_433_docker` — Gate-1 and diagnostic receiver image/reference.

## Fork policy

The connected GitHub integration used to create this scaffold cannot create GitHub repositories or forks. The gitlinks currently point to upstream repositories. When user-owned forks are created, repoint only the components that will carry Lakehouse-specific modifications; leave reference-only dependencies pointed upstream.

Recommended user forks:

1. `RMF112018/weewx-sdr` only if code changes are required after real packet mapping.
2. `RMF112018/weewx-belchertown-new` for Lakehouse-specific UI/branding changes.

`weewx-docker` and `rtl_433_docker` should normally remain upstream references unless a real patch is necessary.
