#!/usr/bin/env python3
"""Second, independent re-import check using Blender's native ufbx-based importer
(bpy.ops.wm.fbx_import) instead of the Python io_scene_fbx add-on that verify_fbx.py uses.
  blender -b --factory-startup --python verify_ufbx.py -- --assets <dump> --dir <fbxdir> --weapon ray_gun|tesla
Prints bone count / frame range / fps and compares ALL bone head positions at ALL frames of
every animation against forward kinematics computed from the decoded xanim.  No rendering."""
import argparse
import json
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_fbx as V          # noqa: E402
import waw_viewmodel_fbx as W   # noqa: E402
import waw_xanim                # noqa: E402


def imp(path):
    before = set(bpy.data.objects.keys())
    bpy.ops.wm.fbx_import(filepath=path, use_anim=True, global_scale=1.0, ignore_leaf_bones=False)
    return [bpy.data.objects[n] for n in bpy.data.objects.keys() if n not in before]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--assets', required=True)
    ap.add_argument('--dir', required=True)
    ap.add_argument('--weapon', required=True, choices=sorted(W.WEAPONS))
    a = ap.parse_args(argv)
    cfg = W.WEAPONS[a.weapon]
    mdir = os.path.join(a.assets, 'model_export')
    arms = W.load_model(os.path.join(mdir, W.ARMS_MODEL + '_lod0.glb'))
    gun = W.load_model(os.path.join(mdir, cfg['gun_model'] + '_lod0.glb'))
    bones = W.combine_rig(arms, gun)
    bind = W.bind_pose(bones)
    idle = waw_xanim.parse_xanim(os.path.join(a.assets, 'xanim', cfg['anim_prefix'] + cfg['idle']))
    isamp, _, _ = W.pose_samples(idle, bones, None, bind)
    idle_base = {n: isamp[n][0] for n in isamp}
    meta = json.load(open(os.path.join(a.dir, '%s_animations.json' % a.weapon)))
    fail = 0
    V.fresh_scene()
    objs = imp(os.path.join(a.dir, '%s_viewmodel.fbx' % a.weapon))
    print('[ufbx] MODEL objects:', [(o.name, o.type) for o in objs])
    arm = [o for o in objs if o.type == 'ARMATURE'][0]
    print('[ufbx] model armature bones=%d (expected %d)' % (len(arm.data.bones), len(bones)))
    fail += len(arm.data.bones) != len(bones)
    for mo in [o for o in objs if o.type == 'MESH']:
        print('[ufbx] mesh %s verts=%d polys=%d vgroups=%d mats=%d' % (
            mo.name, len(mo.data.vertices), len(mo.data.polygons), len(mo.vertex_groups), len(mo.data.materials)))
    rest = W.world_matrices(bones, W.INCH_TO_CM)
    # ufbx puts the cm->m unit factor on the armature OBJECT (scale 0.01) and keeps data in cm, so
    # compare in armature space (which is centimetres, identical to the FBX numbers).
    print('[ufbx] armature object scale = %s (unit factor), rotation = %s' % (
        tuple(round(x, 4) for x in arm.matrix_world.to_scale()),
        tuple(round(x, 4) for x in arm.matrix_world.to_euler())))
    err = max((b.head_local - rest[b.name].translation).length for b in arm.data.bones)
    print('[ufbx] bind pose max head deviation: %.4f cm' % err)
    fail += err > 0.01
    for an, m in meta['animations'].items():
        V.fresh_scene()
        objs = imp(os.path.join(a.dir, m['fbx']))
        ao = [o for o in objs if o.type == 'ARMATURE'][0]
        act = ao.animation_data.action
        fr = tuple(act.frame_range)
        sc = bpy.context.scene
        anim = waw_xanim.parse_xanim(os.path.join(a.assets, 'xanim', cfg['anim_prefix'] + an))
        smp, keyed, _ = W.pose_samples(anim, bones, None, idle_base if m['partial_layered_anim'] else bind)
        n = anim.num_frames + 1
        exp = V.fk_expected(bones, smp, n)
        f0 = int(round(fr[0]))
        worst = 0.0
        moved = 0
        first = {}
        maxdev = {}
        for fi in range(n):
            sc.frame_set(f0 + fi)
            bpy.context.view_layer.update()
            for pb in ao.pose.bones:
                mw = pb.matrix            # armature space == cm
                worst = max(worst, (mw.translation - exp[fi][pb.name].translation).length)
                if fi == 0:
                    first[pb.name] = mw.translation.copy()
                maxdev[pb.name] = max(maxdev.get(pb.name, 0.0), (mw.translation - first[pb.name]).length)
        moved = sum(1 for k in maxdev if maxdev[k] > 1e-3)
        ok = (int(round(fr[1])) - f0 + 1 == n) and worst < 0.05
        fail += not ok
        print('[ufbx] %-13s bones=%d frame_range=(%g, %g) fps=%.1f key_frames=%d  FK max head err %.5f cm  bones moving=%d  %s' % (
            an, len(ao.data.bones), fr[0], fr[1], sc.render.fps / sc.render.fps_base, n, worst, moved,
            'OK' if ok else 'FAIL'))
    print('[ufbx] VERIFY RESULT:', 'PASS' if fail == 0 else 'FAIL (%d)' % fail)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    main(argv)
