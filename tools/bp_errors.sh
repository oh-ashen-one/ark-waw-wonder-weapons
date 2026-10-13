#!/bin/sh
# bp_errors.sh [min_count] : print error summary of the newest Blueprint compile in the editor log.
# Waits (up to 3 min) until the log holds at least min_count "Compile of" lines (log flushes lazily).
N=${1:-0}; L=$(ls -t ~/ARKDevKit/Projects/ShooterGame/Saved/Logs/ShooterGame*.log | head -1)
for i in $(seq 1 90); do c=$(tr '\r' '\n' < "$L" | grep -a -c "Compile of"); [ "$c" -ge "$N" ] && break; sleep 2; done
tr '\r' '\n' < "$L" | grep -a "LogBlueprint" | python3 -c "
import sys
from collections import Counter
L=sys.stdin.read().splitlines(); idx=[i for i,l in enumerate(L) if 'Compile of' in l]
a=idx[-2]+1 if len(idx)>1 else 0; b=idx[-1]
c=Counter(l.split('[compiler] ',1)[-1] for l in L[a:b] if 'deprecated' not in l)
for k,v in c.most_common(40): print(v,k[:200])
print(L[b][:170]); print('compiles in log:',len(idx))"
