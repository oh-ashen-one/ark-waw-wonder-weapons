#!/usr/bin/env python3
"""Build UE4-importable FBX files for the Call of Duty: World at War (Der Riese) ZOMBIE character
from assets dumped by OpenAssetTools: a skinned character (body + head [+ hat]) on ONE skeleton and
one FBX per AI animation, with root-motion analysis.  Companion of waw_viewmodel_fbx.py (weapons);
it reuses that module's GLB reader, armature/mesh/action/export code unchanged.

Run headless inside Blender (no rendering, no UI):

  blender -b --factory-startup --python waw_character_fbx.py -- \
      --assets <dump>/nazi_zombie_factory --scripts <extracted>/nazi_zombie_factory --out <outdir> \
      --stage model|anim [--png-textures] [--shard i/n] [--only name,name]

Stages
  model : character FBX variants + part FBXes (bodies, heads) + textures + skeleton/model JSON
  anim  : one in-place FBX per animation (anim/) plus a root-motion twin (anim_rootmotion/) when the
          animation carries a delta (root motion) track; writes zombie_animations.shardI.json
Merge the shard JSONs and write REPORT.txt with waw_character_report.py.

Inputs (never committed)
  <assets>/model_export/<model>_lod0.glb   OAT glTF per xmodel (skinned; one skin per file)
  <assets>/xanim/<anim>                    OAT compiled-xanim v17
  <scripts>/maps/*.gsc                     game scripts (animation alias names: walk1 -> ai_zombie_walk_v1)

How the character is put together (verified numerically, see verify_character.py)
  * The Der Riese AI zombie (aitype axis_zombie_ger_ber_sshonor -> character/char_ger_honorguard*_zombies.gsc)
    is a char_ger_honorgd_bodyz{1,2}_{1,2} body with `self attach(head, "", true)` where the head is a
    random char_ger_honorgd_zombiehead{1..4}_{1..6}.  There is no hat on this character.
  * `attach(model, "")` skins the attachment to the PARENT's bones by name.  The head/hat xmodel is
    authored in the bind space of its own root bone (j_spine4 resp. j_head at the model origin), so its
    vertices need the rigid transform M = W_body(root) * inverse(W_part(root)) to land in body space.
    M is the same for every shared bone (max deviation 0.0013 inch) - that is the attach proof.
  * Head-only bones (23 facial/jaw/eye joints) are appended to the body skeleton (parent chain kept).
  * xanim tracks are parent-relative absolute local TR per bone (as for weapons).  The *delta* track is
    the entity (tag_origin) motion: cumulative translation + yaw relative to frame 0.  The in-place FBX
    leaves tag_origin at identity; the root-motion FBX keys tag_origin with the delta.
Conventions are identical to the weapon converter: inches x 2.54 = cm, FBX Up=+Z Front=-Y, the zombie
faces +X.
"""
import argparse
import glob
import json
import math
import os
import re
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import waw_viewmodel_fbx as W  # noqa: E402
import waw_xanim as X          # noqa: E402

INCH = W.INCH_TO_CM
LOAD_TOL = 0.05    # IBM self-test tolerance (character bodies reach 1.7e-3 because of ~12-deep chains)

HEAD_MODEL_RE = re.compile(r'^char_ger_honorgd_zombiehead(\d)_(\d)$')

# name -> dict(body, head, hat).  `zombie_character` is the real Der Riese AI zombie.
CHARACTERS = {
    'zombie_character': dict(body='char_ger_honorgd_bodyz1_1', head='char_ger_honorgd_zombiehead1_1', hat=None,
                             note='Der Riese AI zombie (honor guard body z1_1 + head 1_1); no hat on this character'),
    'zombie_character_hat': dict(body='char_ger_honorgd_bodyz1_1', head='char_ger_honorgd_zombiehead1_1',
                                 hat='char_ger_waffen_officercap1_zomb',
                                 note='NOT used by the Der Riese AI: same character + officer cap from the zone (skinned to '
                                      'j_head/j_jaw/j_helmet, fits the skeleton) for use as a hat/gear example'),
    'zombie_character_ansel': dict(body='char_ger_ansel_body_zomb', head='char_ger_ansel_head_zomb',
                                   hat='char_ger_waffen_officercap1_zomb',
                                   note='NOT the AI zombie: "Ansel" zone zombie (79-bone variant with pelvis/back_*/neck helper '
                                        'bones that the ai_zombie xanims do not key); bind pose only'),
}
BODY_PARTS = ['char_ger_honorgd_bodyz1_1', 'char_ger_honorgd_bodyz1_2',
              'char_ger_honorgd_bodyz2_1', 'char_ger_honorgd_bodyz2_2']
ANIM_GLOBS = ['ai_zombie_*', 'ch_dazed_*']
ADDITIVE_ASSET_TYPE = 6          # idle_v1 / idle_crawl: additive layers over idle_base / idle_crawl_base
ROOT_MOTION_MIN_CM = 0.5
ROOT_MOTION_MIN_DEG = 0.5


# ------------------------------------------------------------------------------------------
# FBX exporter precision fix (process-local monkeypatch; the weapon path is untouched)
# ------------------------------------------------------------------------------------------
# Blender's FBX exporter decomposes each bone's local matrix with float32 math and writes Euler XYZ.  WaW
# facial bones (j_jaw, j_lip_*, j_brow_*, j_cheek_*, j_levator_*, j_mouth_* ...) sit at Euler Y = -89.995 deg
# (gimbal lock) relative to j_head, where float32 Euler extraction is off by up to 0.2 deg (0.5 mm on the lips).
# `exact_tx` redoes the decomposition in float64: polar-decompose the 3x3 (removes float32 shear/scale noise),
# derive Euler XYZ in double and, within 3e-3 of the lock, take x+z (or x-z) - the well-conditioned combination -
# from the matrix and keep z continuous with the previous frame.
def _euler_xyz(R, prev):
    """R = Rz(z) Ry(y) Rx(x) (Blender 'XYZ').  Stable for any R: away from the lock (cos y >= 0.1) the textbook
    atan2 formulas; near it x+z (y~-90) or x-z (y~+90), taken from the O(1) elements of the 2x2 block
    ((R01 -+ R12), (R11 +- R02)), fix the rotation and z is the free parameter, kept continuous with `prev`.
    Like Blender's compat mode both Euler solutions are tried and the one closest to `prev` wins."""
    from math import atan2, hypot, pi
    cy = hypot(R[0, 0], R[1, 0])
    sy = -R[2, 0]
    y = atan2(sy, cy)

    def wrap(a, b):
        return b + ((a - b + pi) % (2 * pi) - pi)
    if cy >= 0.1:
        sols = [(atan2(R[2, 1], R[2, 2]), y, atan2(R[1, 0], R[0, 0])),
                (atan2(-R[2, 1], -R[2, 2]), atan2(sy, -cy), atan2(-R[1, 0], -R[0, 0]))]
    else:
        z0 = atan2(R[1, 0], R[0, 0]) if cy > 1e-12 else None
        if prev is None:
            z = z0 if z0 is not None else 0.0
        elif z0 is None or abs(wrap(z0, prev[2]) - prev[2]) * cy <= 2e-6:
            z = prev[2]                  # holding z changes the rotation by <= 2e-6 rad
        else:
            z = wrap(z0, prev[2])
        if sy < 0:                       # y ~ -90: x+z well conditioned
            x = atan2(-(R[0, 1] + R[1, 2]), R[1, 1] - R[0, 2]) - z
        else:                            # y ~ +90: x-z well conditioned
            x = atan2(R[0, 1] - R[1, 2], R[1, 1] + R[0, 2]) + z
        sols = [(x, y, z), (x + pi, (pi - y) if y >= 0 else (-pi - y), z + pi)]
    if prev is None:
        return min(sols, key=lambda t: abs(t[0]) + abs(t[1]) + abs(t[2]))
    best, bs = None, None
    for sol in sols:
        u = tuple(wrap(a, b) for a, b in zip(sol, prev))
        sc_ = sum(abs(a - b) for a, b in zip(u, prev))
        if bs is None or sc_ < bs:
            best, bs = u, sc_
    return best


def install_exact_tx():
    from io_scene_fbx import fbx_utils
    OW = fbx_utils.ObjectWrapper
    if getattr(OW, '_waw_exact_tx', False):
        return

    def fbx_object_tx(self, scene_data, rest=False, rot_euler_compat=None):
        matrix = self.fbx_object_matrix(scene_data, rest=rest)
        m = np.array(matrix, dtype=np.float64)
        M3 = m[:3, :3]
        sc = np.linalg.norm(M3, axis=0)
        sc = np.where(sc < 1e-12, 1.0, sc)
        if np.linalg.det(M3) < 0:
            sc = -sc
        Rn = M3 / sc
        U, _S, Vt = np.linalg.svd(Rn)
        R = U @ Vt
        if np.linalg.det(R) < 0:
            R = -R
        sc = tuple(1.0 if abs(abs(v) - 1.0) < 1e-4 else float(v) for v in sc)   # bones have unit scale
        prev = None if rot_euler_compat is None else tuple(rot_euler_compat)
        eul = _euler_xyz(R, prev)
        return (tuple(float(v) for v in m[:3, 3]), eul, sc, matrix, Matrix(R.tolist()))
    OW.fbx_object_tx = fbx_object_tx
    OW._waw_exact_tx = True


# ------------------------------------------------------------------------------------------
# model assembly
# ------------------------------------------------------------------------------------------
def load(mdir, name):
    return W.load_model(os.path.join(mdir, name + '_lod0.glb'), tol=LOAD_TOL)


def assemble(cfg, mdir):
    """-> dict(bones, body, parts=[dict(kind,name,model,M,root,...)], attach=[report rows])"""
    body = load(mdir, cfg['body'])
    bones = list(body['bones'])
    names = {b.name for b in bones}
    parts, attach = [], []
    for kind in ('head', 'hat'):
        mname = cfg.get(kind)
        if not mname:
            continue
        part = load(mdir, mname)
        roots = [b for b in part['bones'] if b.parent is None]
        assert len(roots) == 1, (mname, [b.name for b in roots])
        rn = roots[0].name
        wcur = W.world_matrices(bones, 1.0)
        assert rn in wcur, '%s root bone %s is not in the body skeleton' % (mname, rn)
        wp = W.world_matrices(part['bones'], 1.0)
        M = wcur[rn] @ wp[rn].inverted()
        worst_t, worst_r, shared = 0.0, 0.0, 0
        for b in part['bones']:
            if b.name in wcur:
                d = M @ wp[b.name]
                worst_t = max(worst_t, (d.translation - wcur[b.name].translation).length)
                worst_r = max(worst_r, abs((wcur[b.name].to_3x3().inverted() @ d.to_3x3()).to_quaternion().angle))
                shared += 1
        new = [b.name for b in part['bones'] if b.name not in names]
        for b in part['bones']:
            if b.name not in names:
                assert b.parent in names, (b.name, b.parent)
                bones.append(W.Bone(b.name, b.parent, b.t.copy(), b.q.copy()))
                names.add(b.name)
        rec = dict(kind=kind, model=mname, root_bone=rn, shared_bones=shared, new_bones=new,
                   attach_max_bone_translation_dev_in=worst_t, attach_max_bone_rotation_dev_rad=worst_r,
                   M_translation_in=[round(c, 4) for c in M.translation],
                   M_euler_deg=[round(math.degrees(c), 3) for c in M.to_euler()])
        assert worst_t < 0.02 and worst_r < 1e-3, ('attach inconsistent', rec)
        attach.append(rec)
        parts.append(dict(kind=kind, name=mname, model=part, M=M))
        print('[attach] %-5s %-34s root=%s shared=%d new=%d  max dev %.4f in / %.1e rad' % (
            kind, mname, rn, shared, len(new), worst_t, worst_r))
    return dict(bones=bones, body=body, body_name=cfg['body'], parts=parts, attach=attach)


def texmap_for(asm):
    tm = {}
    tm.update(W.texture_map(asm['body']['glb']))
    for p in asm['parts']:
        tm.update(W.texture_map(p['model']['glb']))
    return tm


def build_character(asm, rig_name, texmap, pngs, kinds=('body', 'head', 'hat')):
    """Armature (+ skinned meshes of the requested kinds).  kinds=() -> armature only."""
    arm_obj, rest, rest_local = W.build_armature(asm['bones'], rig_name + '_skeleton')
    objs, info = [], {}
    if 'body' in kinds:
        o, inf = W.build_mesh_object(rig_name + '_body', asm['body'], [b.name for b in asm['body']['bones']],
                                     arm_obj, Matrix.Identity(4), texmap, pngs)
        objs.append(o)
        info['body'] = dict(inf, model=asm['body_name'])
    for p in asm['parts']:
        if p['kind'] in kinds:
            o, inf = W.build_mesh_object('%s_%s' % (rig_name, p['kind']), p['model'],
                                         [b.name for b in p['model']['bones']], arm_obj, p['M'], texmap, pngs)
            objs.append(o)
            info[p['kind']] = dict(inf, model=p['name'])
    return arm_obj, rest, rest_local, objs, info


def write_pngs(assets, texmap, outdir):
    names = {fn for d in texmap.values() for fn in d.values()}
    return W.convert_textures(assets, names, outdir)


def skeleton_json(bones, path):
    wcm = W.world_matrices(bones, INCH)
    with open(path, 'w') as fh:
        json.dump(dict(units='cm', axes='X forward, Y left, Z up (WaW, right-handed); UE4 import flips Y',
                       root=[b.name for b in bones if b.parent is None][0],
                       bones=[dict(name=b.name, parent=b.parent,
                                   local_translation_cm=[round(c * INCH, 5) for c in b.t],
                                   local_rotation_xyzw=[round(b.q.x, 6), round(b.q.y, 6), round(b.q.z, 6), round(b.q.w, 6)],
                                   world_translation_cm=[round(c, 5) for c in wcm[b.name].translation])
                              for b in bones]), fh, indent=1)


# ------------------------------------------------------------------------------------------
# analysis (numpy forward kinematics; independent of Blender)
# ------------------------------------------------------------------------------------------
def quat_wxyz_to_rot(q):
    q = q / np.maximum(np.linalg.norm(q, axis=-1, keepdims=True), 1e-12)
    w, x, y, z = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    R = np.empty(q.shape[:-1] + (3, 3))
    R[..., 0, 0] = 1 - 2 * (y * y + z * z)
    R[..., 0, 1] = 2 * (x * y - z * w)
    R[..., 0, 2] = 2 * (x * z + y * w)
    R[..., 1, 0] = 2 * (x * y + z * w)
    R[..., 1, 1] = 1 - 2 * (x * x + z * z)
    R[..., 1, 2] = 2 * (y * z - x * w)
    R[..., 2, 0] = 2 * (x * z - y * w)
    R[..., 2, 1] = 2 * (y * z + x * w)
    R[..., 2, 2] = 1 - 2 * (x * x + y * y)
    return R


def topo(bones):
    byname = {b.name: b for b in bones}
    order, seen = [], set()

    def visit(b):
        if b.name in seen:
            return
        if b.parent:
            visit(byname[b.parent])
        seen.add(b.name)
        order.append(b)
    for b in bones:
        visit(b)
    return order


def fk_world(bones, samples, n):
    """-> {bone: (n,4,4) world matrices}, cm, WaW axes, entity (tag_origin) frame."""
    out = {}
    for b in topo(bones):
        s = samples[b.name]
        t = np.array([[v[0].x, v[0].y, v[0].z] for v in s])
        q = np.array([[v[1].w, v[1].x, v[1].y, v[1].z] for v in s])
        L = np.zeros((n, 4, 4))
        L[:, :3, :3] = quat_wxyz_to_rot(q)
        L[:, :3, 3] = t
        L[:, 3, 3] = 1.0
        out[b.name] = L if b.parent is None else np.matmul(out[b.parent], L)
    return out


def bake_delta(anim):
    """Entity motion (root motion): (t_cm (n,3), q_wxyz (n,4)) per frame 0..num_frames, relative to frame 0.
    No delta tracks -> zeros / identity.  Translation tracks are cumulative offsets in frame-0 coordinates."""
    n = anim.num_frames + 1
    t = np.zeros((n, 3))
    q = np.zeros((n, 4))
    q[:, 0] = 1.0
    d = anim.delta
    if d:
        if d['trans']:
            tr = d['trans']
            t = np.array([X.sample_track(tr['idx'], tr['t'], f, 't') for f in range(n)]) * INCH
        if d['quat']:
            tr = d['quat']
            qq = [X._normalize(X.sample_track(tr['idx'], tr['q'], f, 'q')) for f in range(n)]
            for i in range(1, n):                       # sign continuity
                if X._dot(qq[i - 1], qq[i]) < 0:
                    qq[i] = X._flip(qq[i])
            q = np.array([[c[3], c[0], c[1], c[2]] for c in qq])
    return t, q


ABSOLUTE_ASSET_TYPE = 1     # viewmodel anims.  Zombie anims are assetType 2: translation tracks are OFFSETS from
                            # the model's bind-local translation (rotations stay absolute).  Evidence: with absolute
                            # reading j_mainroot sits at z=-1.5 (character 94 cm underground); with bind+offset the
                            # feet land at z=0.7 cm (bind ball-joint height 0.84 cm) in every standing anim.


def pose_samples_char(anim, bones, base_pose):
    """{bone: [(Vector loc_cm, Quaternion q)] per frame}, keyed set, anim-only bone names.
    Same as waw_viewmodel_fbx.pose_samples except for the translation semantics above."""
    baked = X.bake(anim)
    rel = anim.asset_type != ABSOLUTE_ASSET_TYPE
    n = anim.num_frames + 1
    rig = {b.name for b in bones}
    keyed = set()
    skipped = [k for k in baked if k not in rig]
    out = {}
    for b in bones:
        bt, bq = base_pose[b.name]
        d = baked.get(b.name)
        if d is not None and (d['q'] is not None or d['t'] is not None):
            keyed.add(b.name)
        seq, prev = [], None
        for f in range(n):
            t, q = bt, bq
            if d is not None:
                if d['t'] is not None:
                    tt = d['t'][f]
                    off = Vector((tt[0], tt[1], tt[2])) * INCH
                    t = (bt + off) if rel else off
                if d['q'] is not None:
                    qq = d['q'][f]
                    q = Quaternion((qq[3], qq[0], qq[1], qq[2]))
            if prev is not None and prev.dot(q) < 0:
                q = Quaternion((-q.w, -q.x, -q.y, -q.z))
            prev = q
            seq.append((t, q))
        out[b.name] = seq
    return out, keyed, skipped


def yaw_deg(qwxyz):
    return np.degrees(2.0 * np.arctan2(qwxyz[:, 3], qwxyz[:, 0]))      # delta quats rotate about Z only


def analyse(anim, bones, samples, notes_fps):
    """Per-animation statistics.  Distances in cm (WaW inches x 2.54), speeds cm/s."""
    n = anim.num_frames + 1
    dur = anim.num_frames / float(anim.fps) if anim.fps else 0.0
    dt_, dq_ = bake_delta(anim)
    disp = dt_[-1] - dt_[0]
    seg = np.linalg.norm(np.diff(dt_[:, :2], axis=0), axis=1) if n > 1 else np.zeros(0)
    yaw = yaw_deg(dq_)
    has_t = bool(np.abs(dt_).max() > 1e-6)
    has_r = bool(np.abs(yaw).max() > 1e-4)
    d = dict(
        duration_s=dur, key_frames=n, num_frames=anim.num_frames, fps=anim.fps, looped=anim.looped,
        flags=anim.flags, asset_type=anim.asset_type, has_delta_flag=anim.has_delta,
        delta=dict(
            has_translation=has_t, has_rotation=has_r,
            displacement_cm=[round(float(c), 3) for c in disp],
            horizontal_distance_cm=round(float(np.linalg.norm(disp[:2])), 3),
            path_length_cm=round(float(seg.sum()), 3),
            vertical_cm=round(float(disp[2]), 3),
            forward_x_cm=round(float(disp[0]), 3),
            lateral_y_cm=round(float(disp[1]), 3),
            yaw_total_deg=round(float(yaw[-1] - yaw[0]), 3),
            speed_horizontal_cm_s=round(float(np.linalg.norm(disp[:2]) / dur), 3) if dur else 0.0,
            speed_path_cm_s=round(float(seg.sum() / dur), 3) if dur else 0.0,
            speed_forward_x_cm_s=round(float(disp[0] / dur), 3) if dur else 0.0,
            speed_peak_cm_s=round(float(seg.max() * anim.fps), 3) if len(seg) else 0.0,
        ))
    # pose-level root: j_mainroot (hips) translation range (cm) in the entity frame; tag_sync locator
    bn = {b.name for b in bones}
    for nm in ('j_mainroot', 'tag_sync'):
        if nm in samples:
            tr = np.array([[v[0].x, v[0].y, v[0].z] for v in samples[nm]])
            d[nm + '_trans_range_cm'] = dict(min=[round(float(c), 2) for c in tr.min(0)],
                                            max=[round(float(c), 2) for c in tr.max(0)],
                                            net_first_to_last=[round(float(c), 2) for c in (tr[-1] - tr[0])])
    # FK: bones that move, foot contact slip against the delta (plausibility of speed + pose decode)
    Wd = fk_world(bones, samples, n)
    moved = 0
    for nm, Mx in Wd.items():
        if np.linalg.norm(Mx[:, :3, 3] - Mx[0, :3, 3], axis=1).max() > 1e-3:
            moved += 1
    d['bones_moved'] = moved
    if 'j_head_end' in Wd:
        d['head_end_z_cm'] = [round(float(Wd['j_head_end'][:, 2, 3].min()), 1), round(float(Wd['j_head_end'][:, 2, 3].max()), 1)]
    cands = [k for k in ('j_ball_le', 'j_ball_ri', 'j_wrist_le', 'j_wrist_ri', 'j_knee_le', 'j_knee_ri') if k in Wd]
    if 'j_ball_le' in Wd and 'j_ball_ri' in Wd:
        d['ball_z_min_cm'] = round(float(min(Wd['j_ball_le'][:, 2, 3].min(), Wd['j_ball_ri'][:, 2, 3].min())), 2)
    if cands and has_t and n > 2 and dur:
        # Ground-contact plausibility of the delta: world positions of the joints that touch the ground
        # (ball of foot; wrists/knees for crawls).  Joints within 1.5 cm of the lowest point of the clip count
        # as planted; a planted joint must not move in world space if delta + pose are consistent.
        R = quat_wxyz_to_rot(dq_)
        gmin = min(float(Wd[k][:, 2, 3].min()) for k in cands)
        slips, contact = [], 0
        for key in cands:
            P = Wd[key][:, :3, 3]
            world = np.einsum('nij,nj->ni', R, P) + dt_
            for f in range(n - 1):
                if P[f, 2] < gmin + 1.5 and P[f + 1, 2] < gmin + 1.5:
                    contact += 1
                    slips.append(np.linalg.norm(world[f + 1, :2] - world[f, :2]) * anim.fps)
        if slips:
            sp = d['delta']['speed_horizontal_cm_s'] or 1e-9
            d['foot_contact_check'] = dict(
                joints=cands, ground_z_cm=round(gmin, 2), contact_samples=contact,
                median_slip_cm_s=round(float(np.median(slips)), 2), mean_slip_cm_s=round(float(np.mean(slips)), 2),
                median_slip_over_speed=round(float(np.median(slips) / sp), 3),
                valid=bool(0.0 <= gmin <= 1.5 and contact >= 20))      # upright gaits only; crawls plant knees/wrists
    return d


# ------------------------------------------------------------------------------------------
# animations
# ------------------------------------------------------------------------------------------
def list_anims(assets):
    names = []
    for g in ANIM_GLOBS:
        names += [os.path.basename(p) for p in glob.glob(os.path.join(assets, 'xanim', g))]
    return sorted(set(names))


def parse_aliases(scripts):
    """xanim -> [alias] from the game scripts, e.g. level.scr_anim["zombie"]["walk1"] = %ai_zombie_walk_v1;
    -> walk1;  level._zombie_melee["zombie"][2] = %ai_zombie_attack_v1; -> melee[2]."""
    out = {}
    if not scripts or not os.path.isdir(scripts):
        return out
    pat = re.compile(r'^\s*level\.(\w+)((?:\s*\[[^\]]*\])+)\s*=\s*%(\w+)\s*;')
    files = [os.path.join(scripts, 'maps', f) for f in ('_zombiemode.gsc', 'nazi_zombie_factory.gsc')]
    for fp in files:
        if not os.path.exists(fp):
            continue
        for ln in open(fp, errors='replace'):
            if ln.lstrip().startswith('//'):
                continue
            m = pat.match(ln)
            if not m:
                continue
            idx = [i.strip().strip('"') for i in re.findall(r'\[([^\]]*)\]', m.group(2))]
            idx = [i for i in idx if i != 'zombie']
            base = m.group(1)
            if base == 'scr_anim' and idx:
                alias = idx[0]
            else:
                alias = re.sub(r'^_?zombie_', '', base) + ''.join('[%s]' % i for i in idx)
            lst = out.setdefault(m.group(3), [])
            if alias not in lst:
                lst.append(alias)
    return out


def with_rootmotion(samples, anim, bones):
    """samples with tag_origin keyed by the delta (translation cm + yaw about Z)."""
    dt_, dq_ = bake_delta(anim)
    out = dict(samples)
    root = [b.name for b in bones if b.parent is None][0]
    seq = []
    prev = None
    for i in range(len(dt_)):
        q = Quaternion((float(dq_[i][0]), float(dq_[i][1]), float(dq_[i][2]), float(dq_[i][3])))
        if prev is not None and prev.dot(q) < 0:
            q = Quaternion((-q.w, -q.x, -q.y, -q.z))
        prev = q
        seq.append((Vector((float(dt_[i][0]), float(dt_[i][1]), float(dt_[i][2]))), q))
    out[root] = seq
    return out, root


def run_anims(a, bones, arm_obj, rest_local):
    names = list_anims(a.assets)
    if a.only:
        want = set(x for x in a.only.split(',') if x)
        names = [n for n in names if n in want or n.replace('ai_zombie_', '') in want]
    # balance shards: biggest first, round robin
    si, sn = 0, 1
    if a.shard:
        si, sn = [int(x) for x in a.shard.split('/')]
    sizes = {}
    for nm in names:
        sizes[nm] = X.parse_xanim(os.path.join(a.assets, 'xanim', nm)).num_frames
    ordered = sorted(names, key=lambda k: -sizes[k])
    mine = [nm for i, nm in enumerate(ordered) if i % sn == si]
    aliases = parse_aliases(a.scripts)
    base_bind = W.bind_pose(bones)
    rig_names = {b.name for b in bones}
    os.makedirs(os.path.join(a.out, 'anim'), exist_ok=True)
    os.makedirs(os.path.join(a.out, 'anim_rootmotion'), exist_ok=True)
    meta, skipped_add = {}, []
    for nm in sorted(mine):
        anim = X.parse_xanim(os.path.join(a.assets, 'xanim', nm))
        if anim.asset_type == ADDITIVE_ASSET_TYPE:
            skipped_add.append(nm)
            print('skip additive layer', nm)
            continue
        samples, keyed, skipped = pose_samples_char(anim, bones, base_bind)
        nfr = anim.num_frames + 1
        st = analyse(anim, bones, samples, anim.fps)
        rm_needed = (np.linalg.norm(np.array(st['delta']['displacement_cm'])) > ROOT_MOTION_MIN_CM or
                     abs(st['delta']['yaw_total_deg']) > ROOT_MOTION_MIN_DEG or
                     (st['delta']['has_translation'] and
                      np.abs(bake_delta(anim)[0]).max() > ROOT_MOTION_MIN_CM))
        variants = [('inplace', 'anim', samples)]
        if rm_needed:
            rs, root = with_rootmotion(samples, anim, bones)
            variants.append(('rootmotion', 'anim_rootmotion', rs))
        files = {}
        for vname, sub, smp in variants:
            W.clear_action(arm_obj)
            act = W.apply_action(arm_obj, bones, smp, rest_local, nfr, '%s' % nm)
            arm_obj.animation_data.action = None
            W.reset_pose(arm_obj)
            bpy.context.scene.frame_set(0)
            out = os.path.join(a.out, sub, nm + '.fbx')
            W.export_fbx(out, [arm_obj], bake_anim=True, nframes=nfr, all_actions=True)
            W.clear_action(arm_obj, act)
            files[vname] = os.path.join(sub, nm + '.fbx')
        meta[nm] = dict(
            source='xanim/' + nm, fbx_inplace=files['inplace'], fbx_rootmotion=files.get('rootmotion'),
            aliases=aliases.get(nm, []),
            keyed_bones=len(keyed), anim_bones_total=len(anim.bones),
            anim_bones_not_in_rig=sorted(skipped), rig_bones_not_keyed=sorted(rig_names - keyed),
            notetracks=[dict(name=x['name'], frame=x['frame'], time_s=x['frame'] / float(anim.fps)) for x in anim.notes],
            **st)
        print('wrote %-44s frames %4d  dist %7.1f cm  %7.1f cm/s  keyed %3d  moved %3d %s' % (
            nm, nfr, st['delta']['horizontal_distance_cm'], st['delta']['speed_horizontal_cm_s'],
            len(keyed), st['bones_moved'], 'RM' if rm_needed else ''))
    tag = ('shard%d' % si) if a.shard else 'all'
    with open(os.path.join(a.out, 'zombie_animations.%s.json' % tag), 'w') as fh:
        json.dump(dict(animations=meta, skipped_additive=skipped_add), fh, indent=1)


# ------------------------------------------------------------------------------------------
def stage_model(a):
    mdir = os.path.join(a.assets, 'model_export')
    os.makedirs(a.out, exist_ok=True)
    summary = {}
    canon = None
    for cname, cfg in CHARACTERS.items():
        asm = assemble(cfg, mdir)
        W.reset_scene(30)
        texmap = texmap_for(asm)
        pngs = write_pngs(a.assets, texmap, a.out) if a.png_textures else {}
        arm_obj, rest, rest_local, objs, info = build_character(asm, cname, texmap, pngs)
        out = os.path.join(a.out, cname + '.fbx')
        W.export_fbx(out, [arm_obj] + objs, bake_anim=False)
        print('wrote', out, 'bones', len(asm['bones']))
        summary[cname] = dict(fbx=cname + '.fbx', note=cfg['note'], bones=len(asm['bones']), meshes=info,
                              attach=asm['attach'], textures=texmap,
                              png={k: os.path.basename(v) for k, v in pngs.items()})
        if cname == 'zombie_character':
            skeleton_json(asm['bones'], os.path.join(a.out, 'zombie_skeleton.json'))
            canon = asm
    # ---- parts: bodies and heads as separate skinned meshes on the SAME 96-bone skeleton (UE4: import each
    # against the zombie_character skeleton).  Heads: 4 distinct geometries x 6 skin materials.
    if a.parts:
        pdir = os.path.join(a.out, 'parts')
        os.makedirs(pdir, exist_ok=True)
        canon_head = CHARACTERS['zombie_character']['head']
        heads = sorted(os.path.basename(p)[:-9] for p in glob.glob(os.path.join(mdir, 'char_ger_honorgd_zombiehead*_lod0.glb')))
        jobs = [('zombie_body_' + b.replace('char_ger_honorgd_', ''), dict(body=b, head=canon_head, hat=None), ('body',))
                for b in BODY_PARTS]
        jobs += [('zombie_head_' + h.replace('char_ger_honorgd_zombiehead', ''), dict(body=BODY_PARTS[0], head=h, hat=None), ('head',))
                 for h in heads]
        parts_meta = {}
        for pname, cfg, kinds in jobs:
            asm = assemble(cfg, mdir)
            W.reset_scene(30)
            texmap = texmap_for(asm)
            pngs = write_pngs(a.assets, texmap, pdir) if a.png_textures else {}
            arm_obj, rest, rest_local, objs, info = build_character(asm, pname, texmap, pngs, kinds=kinds)
            out = os.path.join(pdir, pname + '.fbx')
            W.export_fbx(out, [arm_obj] + objs, bake_anim=False)
            parts_meta[pname] = dict(fbx='parts/%s.fbx' % pname, bones=len(asm['bones']), kind=kinds[0],
                                     materials={k: v['materials'] for k, v in info.items()},
                                     verts={k: v['verts'] for k, v in info.items()})
            print('wrote', out)
        summary['_parts'] = parts_meta
    with open(os.path.join(a.out, 'zombie_model.json'), 'w') as fh:
        json.dump(summary, fh, indent=1)


def stage_anim(a):
    mdir = os.path.join(a.assets, 'model_export')
    asm = assemble(CHARACTERS['zombie_character'], mdir)
    W.reset_scene(30)
    arm_obj, rest, rest_local, _, _ = build_character(asm, 'zombie_character', {}, {}, kinds=())
    run_anims(a, asm['bones'], arm_obj, rest_local)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--assets', required=True, help='OAT dump dir (model_export/, xanim/, images/)')
    ap.add_argument('--scripts', default='', help='extracted gsc dir (alias names); optional')
    ap.add_argument('--out', required=True)
    ap.add_argument('--stage', required=True, choices=['model', 'anim'])
    ap.add_argument('--png-textures', action='store_true')
    ap.add_argument('--parts', action='store_true', help='model stage: also export body/head parts')
    ap.add_argument('--shard', default='', help='anim stage: i/n')
    ap.add_argument('--only', default='', help='anim stage: comma list of anim names')
    a = ap.parse_args(argv)
    install_exact_tx()
    if a.stage == 'model':
        stage_model(a)
    else:
        stage_anim(a)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    main(argv)
