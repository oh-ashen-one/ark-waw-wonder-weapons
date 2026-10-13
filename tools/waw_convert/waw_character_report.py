#!/usr/bin/env python3
"""Merge the per-shard animation JSONs of waw_character_fbx.py and write the plain-text REPORT.txt.
Pure python 3 (stdlib only).

  python3 waw_character_report.py merge  --out <fbxdir> --assets <dump>
  python3 waw_character_report.py report --out <fbxdir> --assets <dump>

No game data lives in this file; it only formats numbers computed from the dump.
"""
import argparse
import collections
import glob
import json
import os
import re

INCH = 2.54


def load(p):
    return json.load(open(p))


def merge(a):
    anims, skipped = {}, []
    for p in sorted(glob.glob(os.path.join(a.out, 'zombie_animations.shard*.json'))) + \
            sorted(glob.glob(os.path.join(a.out, 'zombie_animations.all.json'))):
        d = load(p)
        anims.update(d['animations'])
        skipped += d.get('skipped_additive', [])
    anims = dict(sorted(anims.items()))
    json.dump(dict(animations=anims, skipped_additive=sorted(set(skipped))), open(os.path.join(a.out, 'zombie_animations.json'), 'w'), indent=1)
    json.dump({k: dict(fps=v['fps'], num_frames=v['num_frames'], duration_s=round(v['duration_s'], 4), notetracks=v['notetracks'])
               for k, v in anims.items()}, open(os.path.join(a.out, 'zombie_notetracks.json'), 'w'), indent=1)
    alias = collections.OrderedDict()
    for k, v in anims.items():
        for al in v.get('aliases', []):
            alias.setdefault(al, []).append(k)
    json.dump(alias, open(os.path.join(a.out, 'zombie_aliases.json'), 'w'), indent=1)
    print('merged %d animations (%d additive layers skipped: %s)' % (len(anims), len(set(skipped)), sorted(set(skipped))))


# ------------------------------------------------------------------------------------------
LOCO_GROUPS = [
    ('WALK  (alias walk1-8)', lambda n: re.match(r'ai_zombie_walk_v\d+$', n)),
    ('RUN   (alias run1-3 = walk_fast_v1-3; run4-6 = run_v2/v4/v3; run_v1 unreferenced)',
     lambda n: re.match(r'ai_zombie_(walk_fast_v\d+|run_v\d+)$', n)),
    ('SPRINT (alias sprint1-4)', lambda n: re.match(r'ai_zombie_sprint_v\d+$', n)),
    ('CRAWL (legless / on hands; alias crawl1-6, crawl_hand_1-2, crawl_sprint1-3)',
     lambda n: re.match(r'ai_zombie_(crawl$|crawl_v\d+$|crawl_sprint|walk_on_hands_[ab]$)', n)),
    ('DAZED stagger loops (generic AI, ch_dazed_*)', lambda n: re.match(r'ch_dazed_[a-d]$', n)),
]


def short(n):
    return n.replace('ai_zombie_', '')


def bone_groups(bones):
    g = collections.OrderedDict((k, []) for k in ('root/sync', 'spine+neck+head', 'arms', 'fingers', 'legs', 'facial', 'helpers', 'tags'))
    for b in bones:
        n = b['name']
        if n in ('tag_origin', 'tag_sync', 'j_mainroot'):
            g['root/sync'].append(n)
        elif n.startswith('tag_'):
            g['tags'].append(n)
        elif re.search(r'bulge|twist|raise', n):
            g['helpers'].append(n)
        elif re.search(r'index|mid_|pinky|ring|thumb', n):
            g['fingers'].append(n)
        elif re.search(r'brow|cheek|eye|lip|mouth|jaw|levator|chin', n):
            g['facial'].append(n)
        elif re.search(r'hip|knee|ankle|ball', n):
            g['legs'].append(n)
        elif re.search(r'clavicle|shoulder|elbow|wrist', n):
            g['arms'].append(n)
        else:
            g['spine+neck+head'].append(n)
    return g


def hierarchy(bones, maxdepth=4):
    kids = collections.defaultdict(list)
    for b in bones:
        kids[b['parent']].append(b['name'])
    out = []

    def rec(n, d):
        if d > maxdepth:
            return
        out.append('  ' * d + n + (' (+%d children)' % len(kids[n]) if d == maxdepth and kids[n] else ''))
        for c in kids[n]:
            rec(c, d + 1)
    for r in kids[None]:
        rec(r, 0)
    return out


def fmt_notes(notes, keep=None, maxn=14):
    items = [(n['frame'], n['name'].replace('sndnt#', 's#')) for n in notes if keep is None or keep(n['name'])]
    s = ', '.join('%s@%d' % (nm, f) for f, nm in items[:maxn])
    return s + (' ...(+%d)' % (len(items) - maxn) if len(items) > maxn else '')


def report(a):
    anims = load(os.path.join(a.out, 'zombie_animations.json'))['animations']
    skipped = load(os.path.join(a.out, 'zombie_animations.json')).get('skipped_additive', [])
    model = load(os.path.join(a.out, 'zombie_model.json'))
    skel = load(os.path.join(a.out, 'zombie_skeleton.json'))
    L = []
    P = L.append

    def vj(name):
        p = os.path.join(a.out, name)
        return load(p) if os.path.exists(p) else None

    keyed = [v['keyed_bones'] for v in anims.values()]
    not_in_rig = sorted({b for v in anims.values() for b in v['anim_bones_not_in_rig']})
    n_delta_flag = sum(1 for v in anims.values() if v['has_delta_flag'])
    upright = [v for k, v in anims.items() if re.match(r'ai_zombie_(walk_v|walk_fast|run_v|sprint_v|idle_base|idle_v1_delta)', k)]
    bz = [v['ball_z_min_cm'] for v in upright if 'ball_z_min_cm' in v]
    loops = [v for v in anims.values() if v['looped'] and 'j_mainroot_trans_range_cm' in v]
    net = max((max(abs(c) for c in v['j_mainroot_trans_range_cm']['net_first_to_last']) for v in loops), default=0.0)
    walkx = sorted(v['j_mainroot_trans_range_cm']['max'][0] - v['j_mainroot_trans_range_cm']['min'][0]
                   for k, v in anims.items() if re.match(r'ai_zombie_(walk_v|walk_fast|run_v|sprint_v)', k))
    rv1 = anims.get('ai_zombie_run_v1', {}).get('foot_contact_check')
    P('WaW Der Riese ZOMBIE -> FBX   (generated by tools/waw_convert/waw_character_fbx.py, Blender 5.2 headless, no rendering)')
    P('Owned game assets only (OAT v0.33.0 dump of nazi_zombie_factory).  Files are git-ignored, never committed.')
    P('=' * 110)
    P('')
    P('1. WHAT IS THE DER RIESE ZOMBIE')
    P('  aitype/axis_zombie_ger_ber_sshonor.gsc -> character/char_ger_honorguard_zombies.gsc | char_ger_honorguard2_zombies.gsc')
    P('  body  = char_ger_honorgd_bodyz{1,2}_{1,2}  (xmodelalias char_ger_honorgd_bodyzalias / honorgd2_bodyzalias; 4 bodies, all one 73-bone rig)')
    P('  head  = char_ger_honorgd_zombiehead{1..4}_{1..6} via  self attach(head, "", true)   (24 heads = 4 geometries x 6 skin materials)')
    P('  hat   = NONE on the Der Riese AI (spawner only has a generic `if isdefined(self.hatmodel) detach` for other maps).')
    P('  The task brief named char_ger_ansel_body_zomb / char_ger_ansel_head_zomb / char_ger_waffen_officercap1_zomb: these exist in the zone')
    P('  (zombie cast models: ansel, polonsky, chernova, impinf officer) but NO script of this map spawns them; the ai_zombie_* xanims also')
    P('  do not key the ansel-only helper bones (pelvis, torso_stabilizer, back_low, back_mid, neck, head).  Built anyway as bind-pose variants.')
    P('  Gore models (char_ger_honorgd_body1_g_*, *_zomb_behead, limb spawns) exist in the dump; NOT converted here (separate task).')
    P('')
    P('2. FILES  (all under %s)' % a.out)
    for k, v in model.items():
        if k.startswith('_'):
            continue
        P('  %-30s %3d bones   meshes: %s' % (v['fbx'], v['bones'], ', '.join('%s %d verts/%d tris' % (m, i['verts'], i['tris']) for m, i in v['meshes'].items())))
        P('      %s' % v['note'])
    parts = model.get('_parts', {})
    P('  parts/zombie_body_*.fbx (4) and parts/zombie_head_*.fbx (24): ONE skinned mesh each on the same 96-bone skeleton '
      '(import against the zombie_character skeleton); parts/ holds the PNGs they reference')
    n_in = len(glob.glob(os.path.join(a.out, 'anim', '*.fbx')))
    n_rm = len(glob.glob(os.path.join(a.out, 'anim_rootmotion', '*.fbx')))
    P('  anim/<xanim name>.fbx            %d animations, IN-PLACE (tag_origin stays at identity)' % n_in)
    P('  anim_rootmotion/<xanim name>.fbx %d animations, ROOT-MOTION twin (tag_origin keyed with the xanim delta track); only written when the'
      ' delta moves/turns the entity' % n_rm)
    P('  zombie_animations.json (all stats below, per anim)  zombie_notetracks.json  zombie_aliases.json  zombie_skeleton.json  zombie_model.json')
    P('  *.png: DXT1/DXT5 -> PNG (own numpy decoder).  base colour linked in the FBX materials; *_n.png are the raw decoded WaW normal maps (NOT linked,')
    P('         WaW packs normals differently from UE4 - needs a channel fix in the material).')
    P('')
    P('3. FORMAT')
    P('  FBX 7.4 binary (Blender exporter).  Units: WaW inches x 2.54 = cm (1 UE4 unit = 1 cm).  Axes: FBX Up=+Z, Front=-Y, Coord=+X (identical to the weapons)')
    P('  -> the zombie faces +X, WaW-left (+Y) becomes UE4-left after UE\'s usual handedness flip.  Leave UE4 "Force Front X Axis" OFF.')
    P('  Skeleton: %d bones, root `tag_origin` (WaW entity origin at ground level, identity), j_mainroot = pelvis at z=%.1f cm.' % (
        len(skel['bones']), [b for b in skel['bones'] if b['name'] == 'j_mainroot'][0]['world_translation_cm'][2]))
    P('  Bind pose = T-pose (arms out along +-Y), standing height 181 cm incl. head.  30 fps, one take per FBX (take name = xanim name), every frame baked.')
    P('  Skin: <=4 weights/vertex; body 3519 verts (shared vertex buffer, 4 surfaces), head 1398 verts (face skin + eyes), all LOD0 only.')
    g = bone_groups(skel['bones'])
    P('  Bone groups: ' + '; '.join('%s %d' % (k, len(v)) for k, v in g.items()))
    for k, v in g.items():
        P('     %-16s %s' % (k, ', '.join(v) if len(' '.join(v)) < 400 else ', '.join(v[:14]) + ' ... (%d)' % len(v)))
    P('  Hierarchy (depth<=4):')
    for ln in hierarchy(skel['bones'], 4):
        P('     ' + ln)
    P('')
    P('4. HEAD / HAT ATTACHMENT (verified by bind pose)')
    P('  Head and hat xmodels are authored in the bind space of their OWN root bone (head: j_spine4 at the model origin, hat: j_head at the origin), the engine')
    P('  skins them to the parent skeleton BY BONE NAME.  Rigid transform M = W_body(root) x inverse(W_part(root)); the SAME M maps every shared bone (j_neck, j_head,')
    P('  j_head_end, j_helmet ...) onto the body skeleton to within 0.0013 inch / 0 rad, for all 24 heads, the ansel head and the cap.  Not attached to a single socket:')
    P('  the head mesh is skinned to j_neck/j_head/j_jaw/facial bones, the 23 head-only bones (facial/eye/jaw) are appended under j_head / j_jaw.')
    vm = vj('verify_character_model.json')
    if vm:
        att = vm['results']['zombie_character_hat']['attach']
        P('  bind-pose numbers (cm): j_head at %s, j_neck at %s; head mesh z-range %s (body mesh top %s, neck seam: head-bottom verts to nearest body vertex median %.2f cm, max %.2f cm);' % (
            att['j_head_world_cm'], att['j_neck_world_cm'], att['head_mesh_z_range_cm'], att['body_mesh_top_z_cm'],
            att['neck_seam_nearest_body_vertex_cm']['median'], att['neck_seam_nearest_body_vertex_cm']['max']))
        P('  head bbox relative to j_head: %s ; head centroid - j_head = %s ; hat z-range %s (sits on top of the head: %s)' % (
            att['head_mesh_bbox_rel_j_head_cm'], att['head_centroid_minus_j_head_cm'], att.get('hat_z_range_cm'), att.get('hat_overlaps_head_z')))
    P('  The body model ALSO contains the (exposed skin) hand surfaces textured with the head material (mtl_char_ger_headz1_N): body z{1,2}_{1,2} pick the hand skin tone.')
    P('')
    P('5. ANIMATION DATA CONVENTIONS FOUND (read this before using the anims)')
    P('  * 168 ai_zombie_* + 8 ch_dazed_* xanims parse cleanly (v17, 0 trailing bytes), all 30 fps.  Anims key %d-%d of the %d bones; %d anim-only bones' % (
        min(keyed), max(keyed), len(skel['bones']), len(not_in_rig)))
    P('    (%s) belong to other body models and are dropped (listed per anim in the JSON).' % ', '.join(not_in_rig))
    P('  * assetType 2 (all ai_zombie, ch_dazed): ROTATIONS absolute parent-relative, but TRANSLATION tracks are OFFSETS added to the bind-local translation')
    P('    (empirical finding - OAT does not document assetType; found by testing both readings against the physics below)')
    P('    (assetType 1 = viewmodels = absolute).  Proof: absolute reading puts j_mainroot at z=-1.5 in (character 94 cm underground); bind+offset gives pelvis z~90 cm,')
    P('    ball-of-foot z=%.2f-%.2f cm in all %d upright zombie clips (walk/run/sprint/idle; bind ball height 0.84 cm; the generic ch_dazed rig stands ~1-3 cm lower)%s.' % (
        min(bz), max(bz), len(bz), (' and run_v1 planted-foot world slip median %.1f percent of speed' % (rv1['median_slip_over_speed'] * 100)) if rv1 else ''))
    P('    The same offset rule makes the facial bones (lips/mouth/cheek/brow, translation tracks of ~1 cm) and the bulge/shoulderraise helpers land on the right place.')
    P('  * assetType 6 (ai_zombie_idle_v1, ai_zombie_idle_crawl): ADDITIVE layers over idle_base / idle_crawl_base.  NOT exported (composition rule unverified):')
    P('    skipped = %s.  The absolute loops ai_zombie_idle_v1_delta / ai_zombie_idle_crawl_delta / *_base ARE exported and are the usable idles.' % skipped)
    P('  * ROOT MOTION = the xanim DELTA track (flag bit 2, set in %d of %d files): cumulative entity translation (in frame-0 coordinates) + yaw about Z,' % (n_delta_flag, len(anims)))
    P('    relative to frame 0.  Bone poses (incl. j_mainroot) are in the entity frame, so the hips do NOT carry travel: j_mainroot net first->last displacement is <= %.2f cm in' % net)
    P('    every loop; it only surges around the constant-velocity entity (x range of the pelvis in walk/run/sprint loops: median %.0f cm, max %.0f cm; see j_mainroot ranges in the JSON).  In-place FBX = bones only.  Root-motion FBX' % (
        walkx[len(walkx) // 2] if walkx else 0, walkx[-1] if walkx else 0))
    P('    = same bones + tag_origin keyed with the delta (translation cm, yaw).  Entity speed = |delta xy| / duration.')
    n_t = sum(1 for v in anims.values() if v['delta']['has_translation'])
    n_r = sum(1 for v in anims.values() if v['delta']['has_rotation'])
    n_rm = sum(1 for v in anims.values() if v['fbx_rootmotion'])
    n_loop = sum(1 for v in anims.values() if v['looped'])
    P('  * tag_origin (the skeleton root) is keyed in NO xanim.  Delta translation present in %d of %d exported anims, delta yaw in %d; %d have a root-motion twin; '
      '%d clips are loops (their delta = exactly one cycle).' % (n_t, len(anims), n_r, n_rm, n_loop))
    P('  * Looped clips carry num_frames+1 keyed frames (frame N == frame 0); duration = num_frames/fps.  Use frames 0..N-1 as the UE4 loop (or accept a 1-frame stall).')
    P('  * tag_sync, tag_inhand, tag_weapon_right/left/chest, j_gun carry non-physical tracks (hundreds of cm away, per-anim): sync/prop locators, unskinned.')
    P('    Exported as decoded; ignore them for gameplay (use j_wrist_* for hand sockets).')
    P('')
    P('6. GAME-SCRIPT ALIASES (maps/_zombiemode.gsc + nazi_zombie_factory.gsc anim_override_func)')
    al = load(os.path.join(a.out, 'zombie_aliases.json')) if os.path.exists(os.path.join(a.out, 'zombie_aliases.json')) else {}
    inv = collections.defaultdict(list)
    for k, v in al.items():
        for x in v:
            inv[x].append(k)
    for grp in ('walk', 'run', 'sprint', 'crawl', 'death'):
        row = sorted((k, short(x)) for k, v in al.items() for x in v if re.match(r'%s(\d|_hand|_sprint)' % grp, k))
        P('  %-7s %s' % (grp, ', '.join('%s=%s' % (k, x) for k, x in row)))
    other = sorted((k, short(x)) for k, v in al.items() for x in v if not re.match(r'(walk|run|sprint|crawl|death)(\d|_hand|_sprint)', k))
    P('  other   ' + ', '.join('%s=%s' % (k, x) for k, x in other))
    P('  spawner also uses: boardtear_{l,m,r}_1-6 (+crawl_ variants), door_tear_*, window_attack_arm_{l,r}_out, taunts_4 (board taunt), traverse_ground_* (rise from ground),')
    P('  jump_down_*/traverse_* (barriers/ledges), tesla_death_a-e, tesla_crawl_death_a-b, walk_on_hands_shot_a/b (stumpy melee), ch_dazed_{a-d}_death (standing death at spawn).')
    P('  Move-speed class at runtime: rand = randomintrange(level.zombie_move_speed, +35): <=35 walk (walk1-7), <=70 run (run1-5), else sprint (sprint1-3).')
    P('')
    # ---------------------------------------------------------------- locomotion table
    P('7. LOCOMOTION: DISTANCE PER CYCLE AND TRUE WaW SPEED (from the delta track; cm/s == UE4 units/s; WaW units/s = cm/s / 2.54)')
    P('  %-26s %-9s %5s %6s %8s %9s %8s %7s %9s  %s' % ('anim', 'alias', 'frames', 'dur s', 'dist cm', 'cm/s', 'WaW u/s', 'yaw deg', 'plant slip', 'pelvis x range cm (entity frame)'))
    P('  ' + '-' * 118)
    for title, pred in LOCO_GROUPS:
        rows = [(k, v) for k, v in anims.items() if pred(k)]
        if not rows:
            continue
        P('  ' + title)
        for k, v in rows:
            d = v['delta']
            fc = v.get('foot_contact_check')
            slip = ('%5.1f%%' % (fc['median_slip_over_speed'] * 100)) if fc and fc.get('valid') else '  n/a'
            al_s = ','.join(x for x in v['aliases'] if re.match(r'(walk|run|sprint|crawl)(\d|_hand|_sprint)', x))
            mr = v.get('j_mainroot_trans_range_cm', {})
            xr = ('%.0f..%.0f' % (mr['min'][0], mr['max'][0])) if mr else ''
            P('  %-26s %-13s %5d %6.2f %8.1f %9.1f %8.1f %7.1f %9s  %s%s' % (
                short(k), al_s[:13], v['num_frames'], v['duration_s'], d['horizontal_distance_cm'], d['speed_horizontal_cm_s'],
                d['speed_horizontal_cm_s'] / INCH, d['yaw_total_deg'], slip, xr, '' if v['looped'] else '   (not a loop)'))
    P('  dist = |delta xy| over one full cycle (looped clips) / whole clip; speeds are constant-velocity unless the delta has several keys (speed_peak in JSON).')
    P('  plant slip = median world speed of planted joints (ball of foot, lowest 1.5 cm) as percent of entity speed: small = delta and pose agree (feet do not skate).')
    P('  WaW runtime scales entity speed by moveplaybackrate (0.8 only in one special case in the spawner); level.zombie_move_speed picks the class, not a number.')
    P('')
    # ---------------------------------------------------------------- melee
    P('8. ATTACKS / MELEE HIT FRAMES  (notetrack "fire" = damage frame; "sndnt#attack_whoosh" = swing sound; frames at 30 fps, time = frame/30)')
    P('  Attack lists in the script: _zombie_melee[0..6] = attack_forward_v1, attack_forward_v2, attack_v1, attack_v2, attack_v1, attack_v4, attack_v6;')
    P('  _zombie_run_melee[0..2] = run_attack_v1-3; _zombie_walk_melee[0..3] = walk_attack_v1-4; crawl melee = attack_crawl, attack_crawl_lunge; window = window_attack_arm_l/r_out.')
    P('  %-26s %6s %6s %8s  %-40s %s' % ('anim', 'frames', 'dur s', 'move cm', 'fire (hit) frames [s]', 'other notetracks'))
    for k, v in anims.items():
        if re.search(r'attack', k):
            fires = [n for n in v['notetracks'] if n['name'] == 'fire']
            fs = ', '.join('%d [%.2fs]' % (n['frame'], n['time_s']) for n in fires) or '(none - unreferenced by the scripts)'
            P('  %-26s %6d %6.2f %8.1f  %-40s %s' % (short(k), v['num_frames'], v['duration_s'], v['delta']['horizontal_distance_cm'], fs,
                                                    fmt_notes(v['notetracks'], keep=lambda n: n != 'fire', maxn=8)))
    P('  move cm = root motion of the clip: pure in-place melee (attack_v1/v3/v4/v6, attack_crawl*) = 0; attack_forward_*, walk_attack_*, run_attack_* travel with the entity (use the _rootmotion twin).')
    P('')
    # ---------------------------------------------------------------- deaths
    P('9. DEATHS (incl. tesla)  - "start_ragdoll" = switch to ragdoll frame')
    P('  %-34s %6s %6s %9s %9s  %s' % ('anim', 'frames', 'dur s', 'dist cm', 'yaw deg', 'notetracks'))
    for k, v in anims.items():
        if re.search(r'death|^ch_dazed_[a-d]_death|shot_', k):
            P('  %-34s %6d %6.2f %9.1f %9.1f  %s' % (short(k), v['num_frames'], v['duration_s'], v['delta']['horizontal_distance_cm'],
                                                    v['delta']['yaw_total_deg'], fmt_notes(v['notetracks'])))
    P('')
    # ---------------------------------------------------------------- footsteps
    P('10. FOOTSTEP NOTETRACKS (footstep_left/right_large|small + sndnt#step_zombie; locomotion)')
    for title, pred in LOCO_GROUPS[:4]:
        for k, v in anims.items():
            if pred(k):
                has_foot = any('foot' in n['name'] for n in v['notetracks'])
                kp = (lambda n: 'foot' in n) if has_foot else (lambda n: 'step_zombie' in n or 'crawl_hands' in n)
                P('  %-24s %s' % (short(k), fmt_notes(v['notetracks'], keep=kp, maxn=14)))
    P('')
    # ---------------------------------------------------------------- everything else
    P('11. ALL EXPORTED ANIMATIONS  (frames = keyed frames; net/path = root-motion displacement / path length, yaw total; RM = root-motion twin exists (written when delta excursion > 0.5 cm or yaw > 0.5 deg); keyed = bones with tracks of 96; moved = bones that move)')
    P('  %-42s %6s %6s %3s %8s %8s %7s %3s %5s %5s  notetracks' % ('anim', 'frames', 'dur s', 'loop', 'net cm', 'path cm', 'yaw', 'RM', 'keyed', 'moved'))
    cats = collections.OrderedDict([
        ('idle / base poses', r'idle'),
        ('walk/run/sprint/crawl loops + generic dazed', r'(walk_v|walk_fast|run_v\d|sprint_v|crawl$|crawl_v\d|crawl_sprint|walk_on_hands_[ab]$|ch_dazed_[a-d]$)'),
        ('melee', r'.*attack'), ('death / hit reactions', r'.*(death|shot_)'), ('barrier / door / window', r'(boardtear|door_|window)'),
        ('traverse / jump / ladder / climb / rise', r'(traverse|jump|ladder|climb|lighthouse)'), ('taunts', r'taunts')])
    used = set()
    for cat, rx in cats.items():
        rows = [(k, v) for k, v in anims.items() if k not in used and re.match(rx, short(k))]
        if not rows:
            continue
        P('  [%s]' % cat)
        for k, v in rows:
            used.add(k)
            P('  %-42s %6d %6.2f %3s %8.1f %8.1f %7.1f %3s %5d %5d  %s' % (
                short(k), v['key_frames'], v['duration_s'], 'Y' if v['looped'] else '', v['delta']['horizontal_distance_cm'],
                v['delta']['path_length_cm'], v['delta']['yaw_total_deg'], 'RM' if v['fbx_rootmotion'] else '', v['keyed_bones'], v['bones_moved'],
                fmt_notes(v['notetracks'], maxn=6)))
    rest = [k for k in anims if k not in used]
    if rest:
        P('  [other] ' + ', '.join(short(k) for k in rest))
    P('')
    # ---------------------------------------------------------------- verification
    P('12. VERIFICATION (headless Blender re-import, two importers: python io_scene_fbx + native ufbx)')
    av = []
    for p in sorted(glob.glob(os.path.join(a.out, 'verify_character_anim_shard*.json'))) + sorted(glob.glob(os.path.join(a.out, 'verify_character_anim.json'))):
        av.append(load(p))
    if av:
        rows = {}
        fail = 0
        for d in av:
            rows.update(d['results'])
            fail += d['fail']
        eh = [max(r['python']['max_head_err_cm'], r['ufbx']['max_head_err_cm']) for r in rows.values()]
        er = [max(r['python']['max_rot_err_rad'], r['ufbx']['max_rot_err_rad']) for r in rows.values()]
        fr_bad = sum(1 for r in rows.values() if r['python']['frames'] != r['python']['expected_frames'] or round(r['python']['fps']) != r['python']['expected_fps'])
        P('  anim FBXes re-imported: %d (in-place + root-motion);  frames x 96 bones compared against numpy FK of the decoded xanim:' % len(rows))
        P('    max bone-head error %.5f cm (py/ufbx worst of all), max orientation error %.6f rad, frame-count/fps mismatches %d, failures %d' % (max(eh), max(er), fr_bad, fail))
        mv = [r['python']['bones_moved'] for r in rows.values()]
        P('    bones moved per anim: min %d  median %d  max %d (of 96; tag_origin moves only in the root-motion twins)' % (min(mv), sorted(mv)[len(mv) // 2], max(mv)))
        lc = [(r.get('loop_closure_cm', 0.0), k.split('|')[0]) for k, r in rows.items() if r.get('looped')]
        if lc:
            lc.sort(reverse=True)
            P('    loop seam (looped clips, pose at last frame vs frame 0, non-tag bones): max %.4f cm (%s); %d of %d loops closed within 0.5 cm' % (
                lc[0][0], short(lc[0][1]), sum(1 for v, _ in lc if v <= 0.5), len(lc)))
        rm_ok = all(r['python']['root_moved_cm'] > 0.0 for k, r in rows.items() if k.endswith('|rootmotion'))
        ip_ok = all(r['python']['root_moved_cm'] < 1e-3 for k, r in rows.items() if k.endswith('|inplace'))
        P('    in-place twins: root bone stays at origin in all = %s; root-motion twins: tag_origin travels in all = %s' % (ip_ok, rm_ok))
    else:
        P('  (anim verification results not found)')
    if vm:
        P('  model FBXes: %s' % ('PASS' if vm['fail'] == 0 else 'FAIL (%d)' % vm['fail']))
        for cn in ('zombie_character', 'zombie_character_hat', 'zombie_character_ansel'):
            r = vm['results'][cn]
            P('    %-24s bones py/ufbx %d/%d  bind-head dev %.5f/%.5f cm  per-vertex dev vs numpy placement %s cm  raw FBX Up=%s Front=%s Coord=%s unit=%s limbs=%d' % (
                cn, r['python']['bones'], r['ufbx']['bones'], r['python']['bind_head_dev_cm'], r['ufbx']['bind_head_dev_cm'],
                {k: m.get('max_vertex_dev_cm') for k, m in r['python']['meshes'].items()}, r['raw']['up'], r['raw']['front'], r['raw']['coord'],
                r['raw']['unit_scale'], r['raw']['limb_nodes']))
        P('    parts: %d body/head FBXes re-imported, all 96 bones + 1 mesh: %s' % (
            len([k for k in vm['results'] if k.startswith('zombie_body') or k.startswith('zombie_head')]),
            all(r['ok'] for k, r in vm['results'].items() if k.startswith('zombie_body') or k.startswith('zombie_head'))))
    sk = vj('verify_character_skin.json')
    if sk:
        P('  skinning: evaluated deformed body+head+hat vs numpy linear-blend skinning from OAT weights + decoded xanim (%d clip/frame sets): worst %.4f cm -> %s' % (
            len(sk['results']), sk['worst_cm'], 'PASS' if sk['fail'] == 0 else 'FAIL'))
    if sk:
        idl = sk['results'].get('ai_zombie_idle_v1_delta|inplace')
        if idl:
            P('  skinned standing pose (idle loop frame 0, body+head+cap): z range %s cm (soles at the ground, head/cap above; bind T-pose range is -0.3..186.7 cm with cap).' % (
                idl['skinned_z_range_cm_frame0'],))
    P('  UE4/ARK import itself is NOT tested (no editor may be launched in this run).')
    P('')
    P('13. GAPS / CAVEATS')
    P('  * Additive idles (idle_v1, idle_crawl) not exported; absolute idle loops are.  taunt/board/traverse anims exported as-is (traverse clips move the entity along')
    P('    ledge geometry; use the root-motion twin only with matching geometry).')
    P('  * The head attaches by bone name only (WaW engine behaviour); UE4: import head meshes as separate skeletal meshes against the shared skeleton, or merge in-engine.')
    P('  * Base-colour textures only are wired; WaW normal maps are provided raw; no specular/gloss.  LOD0 only.  Gore/dismember models not converted.')
    P('  * Eyes: material mtl_char_ger_nazizombie_eyes uses zombie_eye.png (alpha/glow not wired); tesla/eye FX tags (tag_eye, j_eyeball_*) are present as bones.')
    P('  * Footstep/hit notetracks are JSON only (not FBX animation notifies).  Frame numbers are xanim frames; the engine also adds an implicit "end" at the last frame.')
    P('  * Body base-colour texture (char_ger_honorguard_body1_c) contains real-world insignia (swastika armband, SS runes, iron cross): fine for private use, but a')
    P('    reskin is needed before any public/workshop release.')
    P('  * Zombie DOG animations (zombie_dog_*, other skeleton) and the Pack-a-Punch/viewmodel assets are out of scope here.')
    out = os.path.join(a.out, 'REPORT.txt')
    open(out, 'w').write('\n'.join(L) + '\n')
    print('wrote', out, len(L), 'lines')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['merge', 'report'])
    ap.add_argument('--out', required=True)
    ap.add_argument('--assets', default='')
    a = ap.parse_args()
    {'merge': merge, 'report': report}[a.cmd](a)
