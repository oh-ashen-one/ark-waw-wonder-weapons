"""Frame-time stats from Metal HUD log lines (MTL_HUD_ENABLED=1 MTL_HUD_LOG_ENABLED=1; Wine stderr).
Usage: python3 -I tools/hudstats.py <wine.log> [last_n_seconds]
Line format: frame#, ?, mem, then (frame_interval_ms, gpu_ms) pairs."""
import sys, statistics as st
lines = [l for l in open(sys.argv[1], errors='ignore') if 'metal-HUD:' in l]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 30
fi, gp = [], []
for l in lines[-n:]:
    v = [float(x) for x in l.split('metal-HUD:')[1].strip().split(',')]
    p = v[3:]; fi += p[0::2]; gp += p[1::2]
fi = [x for x in fi if x > 0]
if not fi: sys.exit("no data")
s = sorted(fi); k = max(1, len(s)//100)
print(f"seconds={min(n,len(lines))} frames={len(fi)} avg_fps={1000/st.mean(fi):.1f} median_ms={st.median(fi):.2f} "
      f"p95_ms={s[int(len(s)*.95)]:.2f} p99_ms={s[int(len(s)*.99)]:.2f} 1%low_fps={1000/st.mean(s[-k:]):.1f} "
      f">33ms={sum(x>33.4 for x in fi)} gpu_median_ms={st.median(gp):.2f}")
