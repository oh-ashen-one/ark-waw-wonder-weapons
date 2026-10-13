#!/usr/bin/env python3
"""Headless re-import verification of the zombie FBX files produced by waw_character_fbx.py (no rendering).

  blender -b --factory-startup --python verify_character.py -- --assets <dump> --dir <fbxdir> \
      --stage model|anim|skin [--shard i/n] [--only name,name]

model : re-imports every character / part FBX with BOTH Blender importers (python io_scene_fbx + native
        ufbx): bone count, mesh stats, bind-pose bone heads vs expected WaW x 2.54, raw FBX axis/unit
        settings, LimbNode count.  Head/hat ATTACH check by bind pose: imported head vertices vs an
        independent numpy placement of the OAT head vertices (rigid transform from the shared bones),
        head-bone-relative bbox, neck seam gap to the body mesh, standing height.
anim  : for every animation FBX (in-place and root-motion twin) compares ALL bone world positions and
        orientations at ALL frames against forward kinematics (numpy) of the decoded xanim (+ delta for
        the root-motion twin); frame count, fps, duration, bones moved; both importers.
skin  : model FBX driven by an animation FBX pose: evaluated deformed meshes vs a numpy linear-blend
        skinning reference built straight from the OAT vertex/weight data and the decoded xanim.
Writes verify_character_<stage>[_shardI].json next to the FBXes and prints a PASS/FAIL line.
"""
import argparse
import glob
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_fbx as V                 # noqa: E402  (fresh_scene, import_fbx)
import waw_character_fbx as C          # noqa: E402
import waw_viewmodel_fbx as W          # noqa: E402
import waw_xanim as X                  # noqa: E402

INCH = W.INCH_TO_CM


def import_ufbx(path):
    before = set(bpy.data.objects.keys())
    bpy.ops.wm.fbx_import(filepath=path, use_anim=True, global_scale=1.0, ignore_leaf_bones=False)
    return [bpy.data.objects[n] for n in bpy.data.objects.keys() if n not in before]


def raw_fbx_info(path):
    from io_scene_fbx import parse_fbx
    root, ver = parse_fbx.parse(path)
    gs = [c for c in root.elems if c.id == b'GlobalSettings'][0]
    gp = {p.props[0].decode(): p.props[4:] for p in [c for c in gs.elems if c.id == b'Properties70'][0].elems}
    objs = [c for c in root.elems if c.id == b'Objects'][0]
    nl = sum(1 for m in objs.elems if m.id == b'Model' and m.props[2] == b'LimbNode')
    return dict(version=ver, up=[gp['UpAxis'][0], gp['UpAxisSign'][0]], front=[gp['FrontAxis'][0], gp['FrontAxisSign'][0]],
                coord=[gp['CoordAxis'][0], gp['CoordAxisSign'][0]], unit_scale=gp['UnitScaleFactor'][0], limb_nodes=nl)


def mesh_world_cm(mo):
    me = mo.data
    co = np.array([v.co[:] for v in me.vertices])
    wm = np.array(mo.matrix_world)
    return co @ wm[:3, :3].T + wm[:3, 3]


# ------------------------------------------------------------------------------------------
def expected_parts(cfg, mdir):
    """Independent numpy placement of OAT vertices into body space (inches): {kind: (P(n,3), tri_count)}."""
    asm = C.assemble(cfg, mdir)
    out = {}
    vb = list(asm['body']['vbufs'].values())[0]
    out['body'] = vb['P'].copy()
    for p in asm['parts']:
        vbp = list(p['model']['vbufs'].values())[0]
        M = np.array(p['M'])
        out[p['kind']] = vbp['P'] @ M[:3, :3].T + M[:3, 3]
    return asm, out


def check_model(a, name, cfg, expect_bones, res, use_ufbx):
    fail = 0
    mdir = os.path.join(a.assets, 'model_export')
    asm, expP = expected_parts(cfg, mdir)
    path = os.path.join(a.dir, name + '.fbx')
    print('=' * 100)
    print('MODEL FBX', name, '(%s)' % cfg.get('note', ''))
    rec = {}
    for imp_name, imp in (('python', V.import_fbx), ('ufbx', import_ufbx)):
        if imp_name == 'ufbx' and not use_ufbx:
            continue
        V.fresh_scene()
        objs = imp(path)
        arms = [o for o in objs if o.type == 'ARMATURE']
        meshes = [o for o in objs if o.type == 'MESH']
        nb = sum(len(o.data.bones) for o in arms)
        print('[%s] objects=%s armature bones=%d (expected %d)' % (imp_name, [(o.name, o.type) for o in objs], nb, expect_bones))
        if nb != expect_bones:
            fail += 1
        rest = W.world_matrices(asm['bones'], INCH)
        ao = arms[0]
        if imp_name == 'python':
            err = max(((ao.matrix_world @ b.head_local) - rest[b.name].translation).length for b in ao.data.bones)
        else:
            err = max((b.head_local - rest[b.name].translation).length for b in ao.data.bones)
        print('[%s] bind pose: max bone-head deviation vs expected WaW x 2.54: %.5f cm' % (imp_name, err))
        if err > 0.01:
            fail += 1
        mrec = {}
        for mo in meshes:
            kind = mo.name.split('_')[-1]
            co = mesh_world_cm(mo) if imp_name == 'python' else np.array([v.co[:] for v in mo.data.vertices])
            if imp_name == 'ufbx':      # ufbx keeps the cm->m unit factor on the object matrix; vertex data is cm
                co = np.array([v.co[:] for v in mo.data.vertices])
            row = dict(verts=len(mo.data.vertices), tris=sum(len(p.vertices) - 2 for p in mo.data.polygons),
                       materials=[m.name for m in mo.data.materials], vgroups=len(mo.vertex_groups),
                       bbox_min=np.round(co.min(0), 2).tolist(), bbox_max=np.round(co.max(0), 2).tolist())
            e = expP.get(kind)
            if e is not None and len(e) == len(co):
                d = np.abs(co - e * INCH).max()
                row['max_vertex_dev_cm'] = round(float(d), 5)
                if d > 0.01:
                    fail += 1
            elif e is not None:
                row['vertex_count_mismatch'] = [len(co), len(e)]
                fail += 1
            mrec[kind] = row
            print('[%s] mesh %-5s verts=%d tris=%d vgroups=%d mats=%s bbox_cm %s..%s  per-vertex dev vs numpy placement: %s cm' % (
                imp_name, kind, row['verts'], row['tris'], row['vgroups'], len(row['materials']),
                row['bbox_min'], row['bbox_max'], row.get('max_vertex_dev_cm')))
        rec[imp_name] = dict(bones=nb, bind_head_dev_cm=round(float(err), 5), meshes=mrec)
    raw = raw_fbx_info(path)
    print('raw FBX ver %d  Up=%s Front=%s Coord=%s UnitScaleFactor=%s LimbNodes=%d (expected %d)' % (
        raw['version'], raw['up'], raw['front'], raw['coord'], raw['unit_scale'], raw['limb_nodes'], expect_bones))
    if raw['limb_nodes'] != expect_bones or raw['up'] != [2, 1] or raw['front'] != [1, -1] or raw['coord'] != [0, 1]:
        fail += 1
    rec['raw'] = raw
    # ---- attach proof: head / hat relative to the skeleton at bind pose, neck seam, standing height
    if 'head' in expP:
        body_in, head_in = expP['body'], expP['head']
        w = W.world_matrices(asm['bones'], 1.0)
        jh = np.array(w['j_head'].translation)
        jn = np.array(w['j_neck'].translation)
        jhe = np.array(w['j_head_end'].translation)
        hb = (head_in.min(0) - jh, head_in.max(0) - jh)
        # neck seam: lowest 10% head vertices -> nearest body vertex (inches)
        low = head_in[head_in[:, 2] < head_in[:, 2].min() + 1.5]
        near = body_in[body_in[:, 2] > 56.0]
        gaps = np.array([np.sqrt(((near - p) ** 2).sum(1)).min() for p in low])
        # head vertex cloud centroid vs bones
        cen = head_in.mean(0)
        att = dict(j_head_world_cm=np.round(jh * INCH, 2).tolist(), j_neck_world_cm=np.round(jn * INCH, 2).tolist(),
                   head_mesh_bbox_rel_j_head_cm=[np.round(hb[0] * INCH, 1).tolist(), np.round(hb[1] * INCH, 1).tolist()],
                   head_centroid_minus_j_head_cm=np.round((cen - jh) * INCH, 2).tolist(),
                   head_mesh_z_range_cm=[round(float(head_in[:, 2].min() * INCH), 1), round(float(head_in[:, 2].max() * INCH), 1)],
                   body_mesh_top_z_cm=round(float(body_in[:, 2].max() * INCH), 1),
                   neck_seam_nearest_body_vertex_cm=dict(median=round(float(np.median(gaps) * INCH), 2),
                                                         max=round(float(gaps.max() * INCH), 2), n=len(low)),
                   standing_height_cm=round(float(max(head_in[:, 2].max(), body_in[:, 2].max()) * INCH), 1),
                   bind_head_mesh_inside_body_xy=bool(abs(cen[1]) < 1.0))
        if 'hat' in expP:
            hat_in = expP['hat']
            att['hat_mesh_bbox_rel_j_head_cm'] = [np.round((hat_in.min(0) - jh) * INCH, 1).tolist(),
                                                  np.round((hat_in.max(0) - jh) * INCH, 1).tolist()]
            att['hat_z_range_cm'] = [round(float(hat_in[:, 2].min() * INCH), 1), round(float(hat_in[:, 2].max() * INCH), 1)]
            att['hat_overlaps_head_z'] = bool(hat_in[:, 2].min() < head_in[:, 2].max() and hat_in[:, 2].max() > head_in[:, 2].max() - 8)
        print('ATTACH (bind pose, cm): ' + json.dumps(att))
        for r in asm['attach']:
            print('  attach %-5s %-34s shared bones=%d  max shared-bone deviation after rigid transform %.4f in / %.1e rad' % (
                r['kind'], r['model'], r['shared_bones'], r['attach_max_bone_translation_dev_in'], r['attach_max_bone_rotation_dev_rad']))
        if np.median(gaps) * INCH > 3.0 or abs(cen[1]) > 1.0:
            fail += 1
        rec['attach'] = att
    res[name] = rec
    return fail


def stage_model(a):
    fail = 0
    res = {}
    for cname, cfg in C.CHARACTERS.items():
        exp = 96 if cname != 'zombie_character_ansel' else 102
        fail += check_model(a, cname, cfg, exp, res, True)
    parts = glob.glob(os.path.join(a.dir, 'parts', 'zombie_*.fbx'))
    pj = json.load(open(os.path.join(a.dir, 'zombie_model.json'))).get('_parts', {})
    print('=' * 100)
    print('PART FBXes: %d files' % len(parts))
    for pf in sorted(parts):
        pname = os.path.basename(pf)[:-4]
        V.fresh_scene()
        objs = V.import_fbx(pf)
        nb = sum(len(o.data.bones) for o in objs if o.type == 'ARMATURE')
        ms = [o for o in objs if o.type == 'MESH']
        raw = raw_fbx_info(pf)
        ok = nb == 96 and raw['limb_nodes'] == 96 and len(ms) == 1
        fail += not ok
        res[pname] = dict(bones=nb, meshes=[(m.name, len(m.data.vertices), len(m.vertex_groups)) for m in ms], ok=bool(ok))
        print('  %-24s bones=%d meshes=%s %s' % (pname, nb, res[pname]['meshes'], 'OK' if ok else 'FAIL'))
    print('=' * 100)
    print('VERIFY MODEL RESULT:', 'PASS' if fail == 0 else 'FAIL (%d)' % fail)
    json.dump(dict(fail=fail, results=res), open(os.path.join(a.dir, 'verify_character_model.json'), 'w'), indent=1)


# ------------------------------------------------------------------------------------------
def verify_one_anim(sc, ao, importer, anim, bones, samples, nm, exp, fr_expect, root_expect):
    """Walk every frame of the imported action and compare against numpy FK.  Returns dict."""
    act = ao.animation_data.action
    fr = tuple(act.frame_range)
    fps = sc.render.fps / sc.render.fps_base
    n = anim.num_frames + 1
    f0 = int(round(fr[0]))
    worst, worst_rot = 0.0, 0.0
    first, maxdev = {}, {}
    names = [pb.name for pb in ao.pose.bones]
    for fi in range(n):
        sc.frame_set(f0 + fi)
        bpy.context.view_layer.update()
        for pb in ao.pose.bones:
            mw = (ao.matrix_world @ pb.matrix) if importer == 'python' else pb.matrix
            e = exp[pb.name][fi]
            et = e[:3, 3]
            d = mw.translation - Vector((et[0], et[1], et[2]))
            worst = max(worst, d.length)
            em = Matrix(((e[0][0], e[0][1], e[0][2]), (e[1][0], e[1][1], e[1][2]), (e[2][0], e[2][1], e[2][2])))
            dr = mw.to_3x3() @ em.inverted()
            worst_rot = max(worst_rot, abs(dr.to_quaternion().angle))
            if fi == 0:
                first[pb.name] = mw.translation.copy()
            maxdev[pb.name] = max(maxdev.get(pb.name, 0.0), (mw.translation - first[pb.name]).length)
    moved = sum(1 for k in maxdev if maxdev[k] > 1e-3)
    root = [b.name for b in bones if b.parent is None][0]
    return dict(frames=int(round(fr[1])) - f0 + 1, fps=round(fps, 3), expected_frames=n, expected_fps=anim.fps,
                max_head_err_cm=round(worst, 5), max_rot_err_rad=round(worst_rot, 6), bones_moved=moved,
                bones=len(names), root_moved_cm=round(float(maxdev.get(root, 0.0)), 3),
                ok=bool((int(round(fr[1])) - f0 + 1 == n) and int(round(fps)) == anim.fps and worst < 0.05 and worst_rot < 0.01))


def stage_anim(a):
    meta = json.load(open(os.path.join(a.dir, 'zombie_animations.json')))['animations']
    asm = C.assemble(C.CHARACTERS['zombie_character'], os.path.join(a.assets, 'model_export'))
    bones = asm['bones']
    bind = W.bind_pose(bones)
    names = sorted(meta, key=lambda k: -meta[k]['num_frames'])
    if a.only:
        want = set(x for x in a.only.split(',') if x)
        names = [n for n in names if n in want]
    si, sn = (int(x) for x in a.shard.split('/')) if a.shard else (0, 1)
    names = [n for i, n in enumerate(names) if i % sn == si]
    fail, rows = 0, {}
    for nm in sorted(names):
        m = meta[nm]
        anim = X.parse_xanim(os.path.join(a.assets, 'xanim', nm))
        samples, keyed, _ = C.pose_samples_char(anim, bones, bind)
        n = anim.num_frames + 1
        variants = [('inplace', m['fbx_inplace'], samples)]
        if m.get('fbx_rootmotion'):
            rs, _ = C.with_rootmotion(samples, anim, bones)
            variants.append(('rootmotion', m['fbx_rootmotion'], rs))
        for vname, fbx, smp in variants:
            exp = C.fk_world(bones, smp, n)
            rec = {}
            for imp_name, imp in (('python', V.import_fbx), ('ufbx', import_ufbx)):
                sc = V.fresh_scene()
                objs = imp(os.path.join(a.dir, fbx))
                ao = [o for o in objs if o.type == 'ARMATURE'][0]
                rec[imp_name] = verify_one_anim(sc, ao, imp_name, anim, bones, smp, nm, exp, n, None)
            ok = rec['python']['ok'] and rec['ufbx']['ok']
            if vname == 'inplace' and rec['python']['root_moved_cm'] > 1e-3:
                ok = False
            if vname == 'inplace':
                # loop seam: pose at the last keyed frame vs frame 0 (entity frame, non-tag bones), cm / rad
                cl = max(float(np.linalg.norm(exp[b.name][n - 1][:3, 3] - exp[b.name][0][:3, 3]))
                         for b in bones if not b.name.startswith('tag_'))
                rec['loop_closure_cm'] = round(cl, 4)
                rec['looped'] = bool(anim.looped)
            if vname == 'rootmotion':
                dist = m['delta']['horizontal_distance_cm']
                rec['root_moved_cm_expected'] = round(float(np.linalg.norm(
                    (C.bake_delta(anim)[0] - C.bake_delta(anim)[0][0]), axis=1).max()), 3)
            rows['%s|%s' % (nm, vname)] = rec
            fail += not ok
            print('%-44s %-10s frames=%4d fps=%g  FK max head err py/ufbx %.5f/%.5f cm  rot %.5f/%.5f rad  moved=%d  root_moved=%.1f cm  %s' % (
                nm, vname, rec['python']['frames'], rec['python']['fps'], rec['python']['max_head_err_cm'],
                rec['ufbx']['max_head_err_cm'], rec['python']['max_rot_err_rad'], rec['ufbx']['max_rot_err_rad'],
                rec['python']['bones_moved'], rec['python']['root_moved_cm'], 'OK' if ok else 'FAIL'))
            sys.stdout.flush()
    print('VERIFY ANIM RESULT (shard %s):' % (a.shard or 'all'), 'PASS' if fail == 0 else 'FAIL (%d)' % fail)
    json.dump(dict(fail=fail, results=rows), open(os.path.join(a.dir, 'verify_character_anim%s.json' % (
        '_shard%d' % si if a.shard else '')), 'w'), indent=1)


# ------------------------------------------------------------------------------------------
def stage_skin(a):
    """Model FBX + pose from animation FBX vs independent numpy LBS (OAT vertex data + decoded xanim)."""
    picks = [x for x in (a.only.split(',') if a.only else
                         ['ai_zombie_walk_v1', 'ai_zombie_walk_fast_v1', 'ai_zombie_sprint_v1', 'ai_zombie_death_v1',
                          'ai_zombie_attack_v2', 'ai_zombie_crawl', 'ai_zombie_tesla_death_a', 'ai_zombie_boardtear_m_1',
                          'ai_zombie_idle_v1_delta', 'ch_dazed_a']) if x]
    meta = json.load(open(os.path.join(a.dir, 'zombie_animations.json')))['animations']
    cfg = C.CHARACTERS['zombie_character_hat']        # 3 meshes: body + head + hat
    asm = C.assemble(cfg, os.path.join(a.assets, 'model_export'))
    bones = asm['bones']
    bind = W.bind_pose(bones)
    bind_w = W.world_matrices(bones, INCH)
    fail = 0
    rows = {}
    ref_models = [('body', asm['body'], Matrix.Identity(4))] + [(p['kind'], p['model'], p['M']) for p in asm['parts']]

    def lbs(model, to_world, expw, f):
        vb = list(model['vbufs'].values())[0]
        jn = [b.name for b in model['bones']]
        M3 = np.array(to_world.to_3x3())
        T = np.array(to_world.translation)
        P = (vb['P'] @ M3.T + T) * INCH
        skin = {nm: np.array(expw[nm][f] @ np.array(bind_w[nm].inverted())) for nm in jn}
        res = np.zeros_like(P)
        J, Wt = vb['J'], vb['W']
        for vi in range(len(P)):
            acc = np.zeros(3)
            tot = 0.0
            for k in range(4):
                w = Wt[vi][k]
                if w > 1e-6:
                    m = skin[jn[int(J[vi][k])]]
                    acc += w * (m[:3, :3] @ P[vi] + m[:3, 3])
                    tot += w
            res[vi] = acc / (tot or 1.0)
        return res

    worst_all = 0.0
    for nm in picks:
        if nm not in meta:
            continue
        m = meta[nm]
        for vname in ('inplace', 'rootmotion'):
            fbx = m['fbx_inplace'] if vname == 'inplace' else m.get('fbx_rootmotion')
            if not fbx:
                continue
            V.fresh_scene()
            objs = V.import_fbx(os.path.join(a.dir, 'zombie_character_hat.fbx'))
            ao = [o for o in objs if o.type == 'ARMATURE'][0]
            meshes = [o for o in objs if o.type == 'MESH']
            objs2 = V.import_fbx(os.path.join(a.dir, fbx))
            ao2 = [o for o in objs2 if o.type == 'ARMATURE'][0]
            act = ao2.animation_data.action
            anim = X.parse_xanim(os.path.join(a.assets, 'xanim', nm))
            smp, _, _ = C.pose_samples_char(anim, bones, bind)
            if vname == 'rootmotion':
                smp, _ = C.with_rootmotion(smp, anim, bones)
            n = anim.num_frames + 1
            expw = C.fk_world(bones, smp, n)
            order = C.topo(bones)

            def drive(frame):
                bpy.context.scene.frame_set(frame)
                bpy.context.view_layer.update()
                wm = {pb.name: (ao2.matrix_world @ pb.matrix).copy() for pb in ao2.pose.bones}
                inv = ao.matrix_world.inverted()
                for b in order:
                    ao.pose.bones[b.name].matrix = inv @ wm[b.name]
                    bpy.context.view_layer.update()
            worst = 0.0
            frames = sorted(set([0, n // 4, n // 2, 3 * n // 4, n - 1]))
            line = []
            zr = [1e9, -1e9]
            for f in frames:
                drive(int(round(act.frame_range[0])) + f)
                dg = bpy.context.evaluated_depsgraph_get()
                for mo in meshes:
                    kind = mo.name.split('_')[-1]
                    ev = mo.evaluated_get(dg)
                    me = ev.to_mesh()
                    co = np.array([v.co[:] for v in me.vertices])
                    mw = np.array(ev.matrix_world)
                    co = co @ mw[:3, :3].T + mw[:3, 3]
                    mdl = [r for r in ref_models if r[0] == kind][0]
                    ref = lbs(mdl[1], mdl[2], expw, f)
                    d_v = float(np.abs(co - ref).max()) if len(co) == len(ref) else float('nan')
                    d_c = float(np.abs(co.mean(0) - ref.mean(0)).max())
                    worst = max(worst, d_v if d_v == d_v else 9e9, d_c)
                    if f == 0:
                        zr = [min(zr[0], float(co[:, 2].min())), max(zr[1], float(co[:, 2].max()))]
                    ev.to_mesh_clear()
                    if f in (0, frames[len(frames) // 2], frames[-1]):
                        line.append('%s f%d |d_vertex|max=%.4f' % (kind, f, d_v))
            worst_all = max(worst_all, worst)
            ok = worst < 0.1
            fail += not ok
            rows['%s|%s' % (nm, vname)] = dict(worst_cm=round(worst, 5), frames_checked=frames, ok=bool(ok),
                                               skinned_z_range_cm_frame0=[round(zr[0], 1), round(zr[1], 1)])
            print('%-34s %-10s frames %s worst per-vertex/centroid dev vs numpy LBS: %.4f cm  %s   skinned z-range at frame 0: %.1f..%.1f cm' % (
                nm, vname, frames, worst, 'OK' if ok else 'FAIL', zr[0], zr[1]))
            print('     ' + ' | '.join(line))
            sys.stdout.flush()
    print('skin check worst deviation: %.4f cm' % worst_all)
    print('VERIFY SKIN RESULT:', 'PASS' if fail == 0 else 'FAIL (%d)' % fail)
    json.dump(dict(fail=fail, worst_cm=worst_all, results=rows), open(os.path.join(a.dir, 'verify_character_skin.json'), 'w'), indent=1)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--assets', required=True)
    ap.add_argument('--dir', required=True)
    ap.add_argument('--stage', required=True, choices=['model', 'anim', 'skin'])
    ap.add_argument('--shard', default='')
    ap.add_argument('--only', default='')
    a = ap.parse_args(argv)
    {'model': stage_model, 'anim': stage_anim, 'skin': stage_skin}[a.stage](a)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    main(argv)
