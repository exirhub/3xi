# EOF diagnosis and the 100,000-connection target

**The current single-node defaults are not certified for 100,000 concurrent connections.** Installation and browser tests are functional checks, not load tests. A working `/healthz` or HTTP/2 handshake does not measure authenticated tunnel capacity.

## Collect evidence on the affected server

From your repository checkout, during the disconnects:

```bash
git pull --ff-only
sudo python3 scripts/diagnose-capacity.py
```

This standalone script runs from the checkout, including when `/opt/3xi` is older. It uses Python 3 and existing system utilities. It does not install packages, connect to the network, read the database, change sysctls or restart/reload services. No reinstall or `--clean-install` is needed.

The JSON includes actual service/process FD limits and counts, Nginx workers and Xray children, RAM/swap/disk availability, namespace TCP states, ephemeral-port range, conntrack occupancy when available, a CPU/network sample, and classified recent errors. Private URLs and raw log messages are not printed.

Optional: `--minutes 60 --sample-seconds 10`. The default log window is 30 minutes with at least 5 seconds of activity sampling. Nginx files are bounded to their last 2 MiB / 5,000 lines; rotated files are not read. Journals are bounded to 5,000 entries each and command timeouts. Truncation, missing data and unparsed lines are reported. High-volume logs may cover only part of the window. CPU/network activity includes other services; virtual interfaces can double count bytes.

Also retain **the exact client EOF error, client/core version and timestamp/timezone**, whether traffic was idle or active, and approximate time from connection establishment to failure. Collect another report during a recurrence. Access-log entries appear after requests finish and the existing format includes website/panel/gRPC routes; duration percentiles are not gRPC-only latency measurements.

## Current limits

| Layer | Committed default | Interpretation |
| --- | --- | --- |
| Nginx workers | `worker_processes auto` | Normally follows CPU cores; check actual process counts. |
| Connection slots | `worker_connections 4096` per worker | Includes upstream connections. Four workers give 16,384 configured slots before other constraints, not 16,384 users. Worker distribution matters. |
| Nginx FD ceiling | `worker_rlimit_nofile 65536`; service `LimitNOFILE=65536` | Raising this alone does not change the 4,096-slot setting. |
| Xray FD ceiling | Inherits `LimitNOFILE=65536` from `x-ui.service` unless changed | One process cannot hold 100,000 TCP sockets under this limit. Both inbound/outbound sockets count. Inspect the core child's actual limits, not the shell's `ulimit`. |
| Frontend HTTP/2 | `http2_max_concurrent_streams 128` | Per HTTP/2 connection, not a global 128-user limit. |
| Internal gRPC | `grpc_pass grpc://127.0.0.1:10001` | In the Nginx 1.28 implementation, active proxied requests consume upstream connections. Frontend multiplexing does not remove that budget. |
| gRPC I/O timeouts | Read/send/body/send-to-client `3600s` | Inactivity limits, not a guaranteed one-hour stream lifetime. |
| Network backlog | `net.core.netdev_max_backlog=100000` | A packet input queue, not support for 100,000 established connections. |

Count users, client-to-CDN TCP connections, CDN-to-origin TCP connections, gRPC requests and logical sessions inside `multiMode` separately. One gRPC request can carry several logical sessions; origin socket counts cannot recover client-side concurrency through Cloudflare.

Linux's default source-port range `32768–60999` gives **28,232 candidate ports** for a fixed source-IP/destination-IP/destination-port combination. Reservations and occupied tuples reduce availability. Nginx workers share this range in the same namespace. Increasing workers/FD limits or tuning TIME_WAIT cannot provide 100,000 simultaneous TCP connections on that one tuple family. This is a scaling constraint, not proof of the present EOF cause; read the actual server range before drawing conclusions.

## Interpret the evidence

| Evidence | Investigation |
| --- | --- |
| `worker_connections are not enough` | Per-worker connection slots and load distribution. |
| `Too many open files` | Actual FD limits/occupancy of the failing process, including Xray. |
| `Cannot assign requested address` on the loopback upstream | Source address/port allocation, bind configuration and occupied tuples. |
| `upstream timed out` | Affected upstream, read/write phase, inactivity duration and Xray health. |
| `upstream prematurely closed connection` | Core restarts, OOM and server transport errors. |
| `GOAWAY`, `RST_STREAM`, `too_many_pings` | HTTP/2 close reason and keepalive policy; increasing PING frequency can worsen rejection. |
| HTTP 499 or frontend reset | Downstream closure; behind the CDN the immediate peer is Cloudflare, not necessarily the original cause. |
| HTTP 200 with EOF | Headers may precede a later stream failure. HTTP 200 does not prove gRPC success; check trailers/client errors. |
| Empty origin error sample | Correlate client logs, Cloudflare events and local checks; a bounded sample cannot exclude origin involvement. |

The `75s` HTTP keepalive setting concerns idle connections, not a universal lifetime for active streams. `grpc_socket_keepalive` enables TCP keepalive toward Xray, not a heartbeat traversing Cloudflare. The route timer reloads only when generated configuration changes.

Cloudflare has separate client and origin connections with its own lifecycle and limits. Nginx timeouts cannot override those limits. Full/Full (strict) controls origin-certificate verification, not connection capacity. CDN maintenance, client connectivity, core restarts, saturation and protocol close handling need contemporaneous evidence.

## Engineering for 100,000 sessions

1. **Define the workload.** Identify which layer reaches 100,000, idle/active proportion, bitrate, new sessions per second, lifetime and acceptable disconnect rate. For example, 100,000 active sessions averaging 100 kbit/s require 10 Gbit/s of payload in that direction, before overhead and spare capacity. At 1 Mbit/s each the demand is 100 Gbit/s. Idle capacity is not throughput capacity.
2. **Remove the single loopback TCP endpoint bottleneck.** Evaluate Unix-domain gRPC sockets with the exact panel/core build, or distribute backends across addresses/ports/processes/nodes. A Unix socket requires compatible panel generation, permissions, startup ordering and health checks. Changing only `grpc_pass` breaks the current backend contract; installer, refresh and doctor must migrate together. This diagnostic update makes no such migration.
3. **Budget the whole node.** Size connection slots and process FD limits from observed upstream/downstream use. Measure memory per stream, TLS CPU, outbound sockets, packet rate, NIC throughput, conntrack if enabled, and logging overhead. Larger maximum buffers or swap do not create processing capacity. Verify effective limits after any planned service transition.
4. **Distribute load with spare capacity.** Benchmark each node, then size a pool that carries the target even with one node unavailable. Keep account provisioning consistent and aggregate usage/quota accounting explicitly; cloned seed databases do not provide shared runtime accounting. Do not share a live SQLite file between nodes. Site media also uses origin resources unless served/cached separately.
5. **Test authenticated traffic end to end.** Use controlled load generators with actual VLESS/gRPC sessions. Ramp concurrency (for example 1k, 5k, 10k, 25k, 50k, 100k), stopping when defined error/latency/resource limits are exceeded. Test origin and CDN paths separately with appropriate TLS trust. Measure throughput, unexpected closes, active streams, FD/memory, CPU, drops and reconnection rates. Include idle-to-active transitions, long duration, graceful reload and node failure. A mass reconnect must fit the remaining capacity.

No 100,000-session load test, upstream-socket migration or production capacity guarantee is included in this release.

## Primary references

- [Nginx worker_connections and process limits](https://nginx.org/en/docs/ngx_core_module.html#worker_connections)
- [Nginx HTTP/2 stream limit](https://nginx.org/en/docs/http/ngx_http_v2_module.html#http2_max_concurrent_streams)
- [Nginx gRPC timeouts and socket keepalive](https://nginx.org/en/docs/http/ngx_http_grpc_module.html)
- [Nginx 1.28.0 gRPC source: request/upstream handling](https://github.com/nginx/nginx/blob/release-1.28.0/src/http/modules/ngx_http_grpc_module.c)
- [Linux source-port range and reservations](https://www.kernel.org/doc/html/latest/networking/ip-sysctl.html#ip-variables)
- [Cloudflare connection limits](https://developers.cloudflare.com/fundamentals/reference/connection-limits/)
- [Cloudflare HTTP/2 to origin](https://developers.cloudflare.com/speed/optimization/protocol/http2-to-origin/)
