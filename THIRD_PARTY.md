# Source lineage and licenses

Integrated from the owner's existing repositories:

- `exirhub/xupdate`, commit `6bfab810e04feaa9ad6d1c9b545bd4605056cc38`: staged database import, dedicated Nginx, gRPC forwarding, lifecycle checks and bootstrap foundation.
- `exirhub/xrm-1`, commit `5869c79ac757902fe485eb7ae857295598453af3`: DNS, swap, TCP keepalive/buffer profile and UFW installation behavior. Its website and gateway behavior were not retained.

`vendor/3x-ui/x-ui.sh` is the upstream management script from [MHSanaei/3x-ui v3.8.5](https://github.com/MHSanaei/3x-ui/blob/v3.8.5/x-ui.sh). Its GPL-3.0 license is included in [`vendor/3x-ui/LICENSE`](vendor/3x-ui/LICENSE). Installation verifies its hash before copying it to `/usr/bin/x-ui`.

Panel/Xray archives are downloaded from the pinned upstream release and verified with [`upstream.lock.json`](upstream.lock.json). Upstream copyright notices and licenses remain applicable; this repository does not redistribute the binary archive.

Website images are original generative artwork; music is original procedural synthesis without sampled recordings. See [`website/ASSETS.md`](website/ASSETS.md). The uploaded database is included at the project owner's request and is not an upstream default database.
