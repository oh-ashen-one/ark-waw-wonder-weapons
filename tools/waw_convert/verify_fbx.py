#!/usr/bin/env python3
"""Headless re-import verification of the FBX files produced by waw_viewmodel_fbx.py.
No rendering.  Run:

  blender -b --factory-startup --python verify_fbx.py -- \
      --assets <dump>/nazi_zombie_factory --dir <fbxdir> --weapon ray_gun|tesla

For every animation FBX it re-imports the file in Blender, prints bone count, frame range,
fps and a few bone transforms at the first/last frame, then compares ALL bone world
positions at ALL frames against an independent forward-kinematics evaluation computed
straight from the decoded xanim data (no Blender in that path).  It also imports the model
FBX, drives its armature with an animation FBX's action and prints the deformed mesh bbox
per frame to prove that skin weights, bones and animation agree.
"""
import argparse
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import waw_viewmodel_fbx as W   # noqa: E402
import waw_xanim                # noqa: E402

INCH_TO_CM = W.INCH_TO_CM


def fresh_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 0.01
    sc.unit_settings.length_unit = 'CENTIMETERS'
    return sc


def import_fbx(path):
    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(filepath=path, use_anim=True, global_scale=1.0,
                             automatic_bone_orientation=False, ignore_leaf_bones=False,
                             force_connect_children=False)
    return [bpy.data.objects[n] for n in bpy.data.objects.keys() if n not in before]


def fk_expected(bones, samples, nframes):
    """Independent FK: world matrix per bone per frame, cm, WaW axes."""
    byname = {b.name: b for b in bones}
    order = []
    seen = set()

    def visit(b):
        if b.name in seen:
            return
        if b.parent:
            visit(byname[b.parent])
        seen.add(b.name)
        order.append(b)
    for b in bones:
        visit(b)
    out = []
    for f in range(nframes):
        w = {}
        for b in order:
            t, q = samples[b.name][f]
            L = Matrix.Translation(t) @ q.to_matrix().to_4x4()
            w[b.name] = L if b.parent is None else w[b.parent] @ L
        out.append(w)
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--assets', required=True)
    ap.add_argument('--dir', required=True)
    ap.add_argument('--weapon', required=True, choices=sorted(W.WEAPONS))
    ap.add_argument('--probe', default='tag_weapon,j_wrist_le,j_wrist_ri,j_elbow_ri,tag_flash')
    ap.add_argument('--model-only', action='store_true', help='only check the model FBX (used for *_upgraded)')
    a = ap.parse_args(argv)
    cfg = W.WEAPONS[a.weapon]
    probes = [p for p in a.probe.split(',') if p]
    mdir = os.path.join(a.assets, 'model_export')
    arms = W.load_model(os.path.join(mdir, W.ARMS_MODEL + '_lod0.glb'))
    gun = W.load_model(os.path.join(mdir, cfg['gun_model'] + '_lod0.glb'))
    bones = W.combine_rig(arms, gun)
    bind = W.bind_pose(bones)
    idle_anim = waw_xanim.parse_xanim(os.path.join(a.assets, 'xanim', cfg['anim_prefix'] + cfg['idle']))
    idle_samples, _, _ = W.pose_samples(idle_anim, bones, None, bind)
    idle_base = {n: idle_samples[n][0] for n in idle_samples}
    fail = 0

    print('=' * 100)
    print('MODEL FBX', a.weapon)
    fresh_scene()
    objs = import_fbx(os.path.join(a.dir, '%s_viewmodel.fbx' % a.weapon))
    arm_objs = [o for o in objs if o.type == 'ARMATURE']
    mesh_objs = [o for o in objs if o.type == 'MESH']
    print('objects:', [(o.name, o.type) for o in objs])
    for ao in arm_objs:
        print('armature %s: bones=%d' % (ao.name, len(ao.data.bones)))
    nb = sum(len(ao.data.bones) for ao in arm_objs)
    if nb != len(bones):
        print('FAIL: bone count %d != expected %d' % (nb, len(bones)))
        fail += 1
    for mo in mesh_objs:
        me = mo.data
        co = np.array([v.co[:] for v in me.vertices])
        wm = np.array(mo.matrix_world)
        co = (co @ wm[:3, :3].T) + wm[:3, 3]
        print('mesh %s: verts=%d tris=%d mats=%s vgroups=%d bbox_cm min=%s max=%s uv=%s' % (
            mo.name, len(me.vertices), sum(len(p.vertices) - 2 for p in me.polygons),
            [m.name for m in me.materials], len(mo.vertex_groups),
            np.round(co.min(0), 1).tolist(), np.round(co.max(0), 1).tolist(),
            [u.name for u in me.uv_layers]))
    ao = arm_objs[0]
    rest_world = W.world_matrices(bones, INCH_TO_CM)
    err = 0.0
    for b in ao.data.bones:
        h = ao.matrix_world @ b.head_local
        err = max(err, (h - rest_world[b.name].translation).length)
    print('bind pose: max bone-head deviation vs expected WaW*2.54: %.4f cm' % err)
    if err > 0.01:
        fail += 1

    # ---- raw FBX content (independent of Blender's importer): global settings + raw units
    from io_scene_fbx import parse_fbx
    root, ver = parse_fbx.parse(os.path.join(a.dir, '%s_viewmodel.fbx' % a.weapon))
    gs = [c for c in root.elems if c.id == b'GlobalSettings'][0]
    gprops = {p.props[0].decode(): p.props[4:] for p in [c for c in gs.elems if c.id == b'Properties70'][0].elems}
    print('raw FBX ver %d  UpAxis=%s/%s FrontAxis=%s/%s CoordAxis=%s/%s UnitScaleFactor=%s' % (
        ver, gprops['UpAxis'], gprops['UpAxisSign'], gprops['FrontAxis'], gprops['FrontAxisSign'],
        gprops['CoordAxis'], gprops['CoordAxisSign'], gprops['UnitScaleFactor']))
    objs_e = [c for c in root.elems if c.id == b'Objects'][0]
    nlimb = 0
    for m in objs_e.elems:
        if m.id == b'Model' and m.props[2] == b'LimbNode':
            nlimb += 1
            nm = m.props[1].split(b'\x00')[0].decode()
            if nm in ('tag_weapon', 'j_shoulder_le', 'j_elbow_le'):
                for pp in [c for c in m.elems if c.id == b'Properties70'][0].elems:
                    if pp.props[0] == b'Lcl Translation':
                        want = [x for x in [b for b in bones if b.name == nm][0].t]
                        print('raw FBX LimbNode %-14s Lcl Translation (cm) = %s   expected WaW local x2.54 = %s' % (
                            nm, [round(v, 3) for v in pp.props[4:7]], [round(v * INCH_TO_CM, 3) for v in want]))
    print('raw FBX LimbNode count = %d (expected %d)' % (nlimb, len(bones)))
    if nlimb != len(bones):
        fail += 1

    if a.model_only:
        print('VERIFY RESULT (model only):', 'PASS' if fail == 0 else 'FAIL (%d)' % fail)
        return

    # ---- animation FBXes
    meta = json.load(open(os.path.join(a.dir, '%s_animations.json' % a.weapon)))
    for an, m in meta['animations'].items():
        print('-' * 100)
        print('ANIM', an, m['fbx'])
        sc = fresh_scene()
        objs = import_fbx(os.path.join(a.dir, m['fbx']))
        ao = [o for o in objs if o.type == 'ARMATURE'][0]
        act = ao.animation_data.action
        fr = tuple(act.frame_range)
        fps = sc.render.fps / sc.render.fps_base
        print('bones=%d action=%s frame_range=%s scene_fps=%.3f expected_key_frames=%d expected_fps=%d' % (
            len(ao.data.bones), act.name, fr, fps, m['key_frames'], m['fps']))
        path = os.path.join(a.assets, 'xanim', cfg['anim_prefix'] + an)
        anim = waw_xanim.parse_xanim(path)
        base = idle_base if m['partial_layered_anim'] else bind
        samples, keyed, _ = W.pose_samples(anim, bones, None, base)
        n = anim.num_frames + 1
        exp = fk_expected(bones, samples, n)
        f0 = int(round(fr[0]))
        if int(round(fr[1])) - f0 + 1 != n or int(round(fps)) != anim.fps:
            print('FAIL: frame range/fps mismatch')
            fail += 1
        worst = 0.0
        worst_rot = 0.0
        moved = 0
        first = {}
        last = {}
        maxdev = {}
        for fi in range(n):
            sc.frame_set(f0 + fi)
            bpy.context.view_layer.update()
            for pb in ao.pose.bones:
                mw = ao.matrix_world @ pb.matrix
                e = exp[fi][pb.name]
                worst = max(worst, (mw.translation - e.translation).length)
                # orientation: importer keeps the FBX bone frames, so compare rotation too
                d = (mw.to_3x3() @ e.to_3x3().inverted())
                worst_rot = max(worst_rot, abs(d.to_quaternion().angle))
                if fi == 0:
                    first[pb.name] = mw.translation.copy()
                if fi == n - 1:
                    last[pb.name] = mw.translation.copy()
                maxdev[pb.name] = max(maxdev.get(pb.name, 0.0), (mw.translation - first[pb.name]).length)
        for k in first:
            if maxdev[k] > 1e-3:
                moved += 1
        print('FK check over %d frames x %d bones: max head error %.5f cm, max orientation error %.5f rad' % (
            n, len(ao.data.bones), worst, worst_rot))
        print('bones whose world position differs from frame 0 at ANY frame: %d / %d ; keyed (xanim) bones: %d' % (
            moved, len(first), len(keyed)))
        for p in probes:
            if p in first:
                print('  %-14s f%02d %s -> f%02d %s' % (p, f0, np.round(first[p][:], 2).tolist(),
                                                       f0 + n - 1, np.round(last[p][:], 2).tolist()))
        if worst > 0.05 or worst_rot > 0.01:
            print('FAIL: re-imported pose differs from xanim FK')
            fail += 1
        if n > 2 and moved == 0:
            print('FAIL: animation is trivial')
            fail += 1

    # ---- skinned mesh follows animation (model FBX driven by an anim FBX action)
    print('=' * 100)
    print('SKIN CHECK (model FBX + action from anim FBX)')
    pick = [x for x in ('reload', 'fire') if x in meta['animations']][0]
    fresh_scene()
    objs = import_fbx(os.path.join(a.dir, '%s_viewmodel.fbx' % a.weapon))
    ao = [o for o in objs if o.type == 'ARMATURE'][0]
    meshes = [o for o in objs if o.type == 'MESH']
    objs2 = import_fbx(os.path.join(a.dir, meta['animations'][pick]['fbx']))
    ao2 = [o for o in objs2 if o.type == 'ARMATURE'][0]
    act = ao2.animation_data.action
    # NOTE: Blender cannot reliably re-target an imported action onto a second imported armature
    # (euler/quaternion channel set-up differs), so we copy the *evaluated world pose* of the
    # animation-FBX armature at each frame onto the model-FBX armature (parents first).
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

    def drive_model_from_anim(frame):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        wm = {pb.name: (ao2.matrix_world @ pb.matrix).copy() for pb in ao2.pose.bones}
        inv = ao.matrix_world.inverted()
        for b in order:
            ao.pose.bones[b.name].matrix = inv @ wm[b.name]
            bpy.context.view_layer.update()

    n = meta['animations'][pick]['key_frames']
    # independent linear-blend-skinning reference computed with numpy from the decoded xanim
    # + OAT bone/vertex data (no Blender): v' = sum_i w_i * W_i(f) * inv(Bind_i) * v
    anim = waw_xanim.parse_xanim(os.path.join(a.assets, 'xanim', cfg['anim_prefix'] + pick))
    smp, _, _ = W.pose_samples(anim, bones, None, bind)
    expw = fk_expected(bones, smp, n)
    bind_w = W.world_matrices(bones, INCH_TO_CM)

    def lbs(model, jnames, to_world, f):
        out = []
        vb = list(model['vbufs'].values())[0]
        M3 = np.array(to_world.to_3x3())
        T = np.array(to_world.translation)
        P = (vb['P'] @ M3.T + T) * INCH_TO_CM
        skin = {nm: np.array(expw[f][nm] @ bind_w[nm].inverted()) for nm in jnames}
        res = np.zeros_like(P)
        for vi in range(len(P)):
            acc = np.zeros(3)
            tot = 0.0
            for k in range(4):
                w = vb['W'][vi][k]
                if w > 1e-6:
                    m = skin[jnames[int(vb['J'][vi][k])]]
                    acc += w * (m[:3, :3] @ P[vi] + m[:3, 3])
                    tot += w
            res[vi] = acc / (tot or 1.0)
        return res

    dg = bpy.context.evaluated_depsgraph_get()
    wr = W.world_matrices(bones, 1.0)
    skin_worst = 0.0
    for f in sorted(set([0, n // 4, n // 2, 3 * n // 4, n - 1])):
        drive_model_from_anim(int(round(act.frame_range[0])) + f)
        dg = bpy.context.evaluated_depsgraph_get()
        line = []
        for mo in meshes:
            ev = mo.evaluated_get(dg)
            me = ev.to_mesh()
            co = np.array([v.co[:] for v in me.vertices])
            mw = np.array(ev.matrix_world)
            co = co @ mw[:3, :3].T + mw[:3, 3]        # object -> world (import may add object transforms)
            if mo.name.endswith('_arms'):
                ref = lbs(arms, [b.name for b in arms['bones']], Matrix.Identity(4), f)
            else:
                ref = lbs(gun, [b.name for b in gun['bones']], wr['tag_weapon'], f)
            d_c = np.abs(co.mean(0) - ref.mean(0)).max()
            d_b = max(np.abs(co.max(0) - ref.max(0)).max(), np.abs(co.min(0) - ref.min(0)).max())
            same_order = len(co) == len(ref)
            d_v = float(np.abs(co - ref).max()) if same_order else float('nan')
            skin_worst = max(skin_worst, d_c, d_b)
            line.append('%s centroid=%s |d_centroid|=%.4f |d_bbox|=%.4f per-vertex max=%.4f cm' % (
                mo.name.split('_')[-1], np.round(co.mean(0), 2).tolist(), d_c, d_b, d_v))
            ev.to_mesh_clear()
        print('%s frame %3d: %s' % (pick, f, ' | '.join(line)))
    print('skin check worst centroid/bbox deviation vs numpy LBS reference: %.4f cm' % skin_worst)
    if skin_worst > 0.1:
        fail += 1
    print('=' * 100)
    print('VERIFY RESULT:', 'PASS' if fail == 0 else 'FAIL (%d)' % fail)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    main(argv)
