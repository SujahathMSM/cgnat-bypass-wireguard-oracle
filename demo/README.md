# Demos

| File | Length | What it shows |
|---|---|---|
| [`explainer.mp4`](explainer.mp4) / [`explainer.gif`](explainer.gif) | 50 s | Animated walkthrough: the CGNAT problem, the tunnel, one HTTPS request hop by hop with its NAT rewrites, the two main bugs, and the result |
| [`terminal-01-wireguard-handshake.mp4`](terminal-01-wireguard-handshake.mp4) / [`.gif`](terminal-01-wireguard-handshake.gif) | 22 s | Debugging the missing handshake: `ping` fails, `wg` shows 0 B received, `tcpdump` is silent, then the Security List fix and the handshake packets |
| [`terminal-02-port-forward.mp4`](terminal-02-port-forward.mp4) / [`.gif`](terminal-02-port-forward.gif) | 29 s | Debugging the public port timeout: backend works, NAT table empty, FORWARD only REJECTs, then the rules loaded after the fix and a reboot |

## About the terminal replays

The terminal videos replay the real command output from the build sessions, rendered as a terminal recording. Public IPs, WireGuard keys and the hostname were replaced with placeholders such as `<oracle-public-ip>` and `<home-cgnat>`. Lines starting with `#`, and the `<-` annotation, are narration added for the demo; they weren't printed by the machines.

## Regenerating

All three videos are generated from code, so they can be edited and re-rendered:

```bash
python3 tools/make_explainer.py          # demo/explainer.mp4
python3 tools/make_terminal_demos.py     # demo/terminal-*.mp4 and .gif
python3 tools/make_packet_flow.py        # diagrams/packet-flow.svg
```

They need Python 3 with Pillow, ffmpeg, the Inter font and DejaVu Sans Mono. Add `--preview` to either video script to write a few still frames instead of rendering.
