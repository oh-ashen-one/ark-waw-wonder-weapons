#!/usr/bin/env python3
"""Build UE4-importable FBX files (skinned viewmodel + one FBX per animation) for a
Call of Duty: World at War first-person weapon from assets dumped by OpenAssetTools.

Run headless inside Blender (no rendering, no UI):

  blender -b --factory-startup --python waw_viewmodel_fbx.py -- \
      --assets <dump>/nazi_zombie_factory --out <outdir> --weapon ray_gun|tesla [--png-textures]

Inputs (all produced by OAT Unlinker, never committed):
  <assets>/model_export/viewmodel_usa_marine_arms_lod0.glb   hands/arms rig (root tag_view)
  <assets>/model_export/viewmodel_usa_<gun>_lod0.glb         gun rig (root j_gun)
  <assets>/xanim/viewmodel_<weapon>_<anim>                   OAT compiled-xanim v17 files

Conventions
  * WaW units are inches, right-handed, X forward / Y left / Z up.  We keep the data in
    that axis system and multiply by 2.54 -> centimetres (1 UE4 unit = 1 cm).
  * Blender's native axes equal the FBX system ('Z' up, 'Y' forward in the exporter UI)
    which declares FBX Up=+Z, Front=-Y, Coord=+X.  That is exactly the system the UE4 FBX
    importer converts to, so UE4 performs no rotation and only the usual RH->LH Y flip:
    barrel along +X in WaW stays +X in UE4, WaW-left (+Y) becomes UE4-left (-Y).
  * OAT's glTF writer wraps the *root bone* of every model in Rx(-90deg) (Z-up -> Y-up)
    and converts vertices (x,y,z)->(x,z,-y).  We undo both here (see load_model).
  * xanim tracks are absolute parent-relative local TR per bone; a missing track means
    "use the model's default (bind) local value".  Bone scale is always 1.
  * Animations are baked to every integer frame 0..num_frames at the xanim frame rate.
"""
import argparse
import json
import math
import os
import struct
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import waw_dds  # noqa: E402
import waw_xanim  # noqa: E402

INCH_TO_CM = 2.54
RX_P90 = Quaternion((1.0, 0.0, 0.0), math.radians(90.0))   # undo OAT's Z-up->Y-up on roots

WEAPONS = {
    'ray_gun': {
        'gun_model': 'viewmodel_usa_ray_gun',
        'anim_prefix': 'viewmodel_ray_gun_',
        'anims': ['idle', 'fire', 'reload', 'raise', 'quick_raise', 'drop', 'quick_drop',
                  'ads_up', 'ads_down'],
        'idle': 'idle',
    },
    'tesla': {
        'gun_model': 'viewmodel_usa_tesla_gun',
        'anim_prefix': 'viewmodel_tesla_',
        'anims': ['idle', 'fire', 'ads_fire', 'reload', 'first_raise', 'pullout', 'pullout_fast',
                  'putaway', 'putaway_fast', 'ads_up', 'ads_down'],
        'idle': 'idle',
    },
}
# Pack-a-Punched variants use another gun mesh on the SAME bone set and the SAME animations, so
# only the model FBX is exported for them (animation FBXes of the base weapon apply as-is).
WEAPONS['ray_gun_upgraded'] = dict(WEAPONS['ray_gun'], gun_model='viewmodel_zombie_raygun_up', anims=[])
WEAPONS['tesla_upgraded'] = dict(WEAPONS['tesla'], gun_model='viewmodel_zombie_tesla_up', anims=[])
ARMS_MODEL = 'viewmodel_usa_marine_arms'

COMP = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


# --------------------------------------------------------------------------------------
# GLB parsing (no Blender importer: we need the exact OAT bone data, not Blender heuristics)
# --------------------------------------------------------------------------------------
class Glb:
    def __init__(self, path):
        b = open(path, 'rb').read()
        magic, ver, _ln = struct.unpack('<4sII', b[:12])
        assert magic == b'glTF' and ver == 2
        cl, ct = struct.unpack('<II', b[12:20])
        self.j = json.loads(b[20:20 + cl])
        o = 20 + cl
        bl, bt = struct.unpack('<II', b[o:o + 8])
        self.bin = b[o + 8:o + 8 + bl]

    def accessor(self, idx):
        a = self.j['accessors'][idx]
        bv = self.j['bufferViews'][a['bufferView']]
        fmt, sz = COMP[a['componentType']]
        n = NCOMP[a['type']]
        off = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        stride = bv.get('byteStride', n * sz)
        cnt = a['count']
        if stride == n * sz:
            arr = np.frombuffer(self.bin, dtype=np.dtype('<' + fmt), count=cnt * n, offset=off)
            return arr.reshape(cnt, n).copy()
        out = np.empty((cnt, n), dtype=np.dtype('<' + fmt))
        for i in range(cnt):
            out[i] = np.frombuffer(self.bin, dtype=np.dtype('<' + fmt), count=n, offset=off + i * stride)
        return out


class Bone:
    def __init__(self, name, parent, t, q):
        self.name = name
        self.parent = parent          # bone name or None
        self.t = Vector(t)            # WaW local translation, inches
        self.q = q                    # WaW local rotation Quaternion


def load_model(path, tol=1e-3):
    """-> dict(bones=[Bone], surfaces=[...]) in WaW axes (inches), root conversion undone."""
    g = Glb(path)
    j = g.j
    nodes = j['nodes']
    skin = j['skins'][0]
    joints = skin['joints']
    node_parent = {}
    for i, n in enumerate(nodes):
        for c in n.get('children', []):
            node_parent[c] = i
    jset = set(joints)
    bones = []
    for ni in joints:
        n = nodes[ni]
        t = n.get('translation', [0.0, 0.0, 0.0])
        r = n.get('rotation', [0.0, 0.0, 0.0, 1.0])
        q = Quaternion((r[3], r[0], r[1], r[2]))
        tv = Vector(t)
        par = node_parent.get(ni)
        if par in jset:
            parent = nodes[par]['name']
        else:
            parent = None
            q = RX_P90 @ q                 # undo OAT Lhc->Rhc root rotation
            tv = RX_P90 @ tv
        bones.append(Bone(n['name'], parent, tv, q))

    # --- self test: glTF inverse bind matrices must invert our reconstructed world matrices
    ibm = g.accessor(skin['inverseBindMatrices'])
    world = world_matrices(bones, scale=1.0)
    rx_m90 = Quaternion((1, 0, 0), math.radians(-90)).to_matrix().to_4x4()
    err = 0.0
    for i, b in enumerate(bones):
        m = np.array(ibm[i]).reshape(4, 4).T          # glTF is column-major
        prod = np.array(Matrix(m.tolist())) @ np.array(rx_m90 @ world[b.name])
        err = max(err, float(np.abs(prod - np.eye(4)).max()))
    print('[%s] IBM self-test max error: %.2e (bones=%d)' % (os.path.basename(path), err, len(bones)))
    assert err < tol, 'bone reconstruction does not match glTF inverse bind matrices'

    # NOTE: OAT writes ONE shared vertex buffer per model; every surface (glTF primitive) points
    # at the same accessors and only differs by its index list.  Keep the buffer shared (keyed
    # by accessor indices) so we do not duplicate the whole vertex set once per surface.
    vbufs = {}
    surfaces = []
    for ni, n in enumerate(nodes):
        if 'mesh' not in n:
            continue
        for prim in j['meshes'][n['mesh']]['primitives']:
            at = prim['attributes']
            key = tuple(sorted(at.items()))
            if key not in vbufs:
                pos = g.accessor(at['POSITION']).astype(np.float64)
                nor = g.accessor(at['NORMAL']).astype(np.float64)
                uv = g.accessor(at['TEXCOORD_0']).astype(np.float64)
                jn = g.accessor(at['JOINTS_0']).astype(np.int64)
                wt = g.accessor(at['WEIGHTS_0']).astype(np.float64)
                col = g.accessor(at['COLOR_0']).astype(np.float64) if 'COLOR_0' in at else None
                # glTF (Y-up) -> WaW (Z-up):  (a,b,c) -> (a,-c,b)
                P = np.stack([pos[:, 0], -pos[:, 2], pos[:, 1]], axis=1)
                N = np.stack([nor[:, 0], -nor[:, 2], nor[:, 1]], axis=1)
                vbufs[key] = dict(P=P, N=N, UV=uv, J=jn, W=wt, C=col)
            idx = g.accessor(prim['indices']).reshape(-1, 3).astype(np.int64)
            mat = j['materials'][prim['material']]['name'].split('/')[-1]
            surfaces.append(dict(name=n['name'], vkey=key, F=idx, mat=mat))
    print('[%s] surfaces=%d shared vertex buffers=%d verts=%s' % (
        os.path.basename(path), len(surfaces), len(vbufs), [len(v['P']) for v in vbufs.values()]))
    return dict(bones=bones, surfaces=surfaces, vbufs=vbufs, glb=g)


def world_matrices(bones, scale):
    """Rest world matrices keyed by bone name; translations multiplied by scale."""
    byname = {b.name: b for b in bones}
    out = {}

    def rec(b):
        if b.name in out:
            return out[b.name]
        loc = Matrix.Translation(b.t * scale) @ b.q.to_matrix().to_4x4()
        out[b.name] = loc if b.parent is None else rec(byname[b.parent]) @ loc
        return out[b.name]
    for b in bones:
        rec(b)
    return out


def combine_rig(arms, gun):
    """Combined viewmodel skeleton: arms rig + gun rig attached under tag_weapon (how the
    engine attaches the weapon model to the hands model)."""
    names = [b.name for b in arms['bones']]
    for b in gun['bones']:
        assert b.name not in names, 'duplicate bone name %s' % b.name
    bones = list(arms['bones'])
    root = [b for b in gun['bones'] if b.parent is None]
    assert len(root) == 1 and root[0].name == 'j_gun', root
    g_root_local = (root[0].t.length, root[0].q)
    assert g_root_local[0] < 1e-4 and abs(abs(root[0].q.w) - 1.0) < 1e-4, 'j_gun default local not identity'
    for b in gun['bones']:
        nb = Bone(b.name, b.parent if b.parent else 'tag_weapon', b.t.copy(), b.q.copy())
        bones.append(nb)
    return bones


# --------------------------------------------------------------------------------------
# Blender scene construction
# --------------------------------------------------------------------------------------
def reset_scene(fps):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 0.01          # 1 Blender unit == 1 cm
    sc.unit_settings.length_unit = 'CENTIMETERS'
    sc.render.fps = int(fps)
    sc.render.fps_base = 1.0
    return sc


def build_armature(bones, name):
    sc = bpy.context.scene
    arm = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, arm)
    sc.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    world = world_matrices(bones, INCH_TO_CM)
    kids = {}
    for b in bones:
        kids.setdefault(b.parent, []).append(b.name)
    eb = {}
    for b in bones:
        M = world[b.name]
        # bone length: distance to nearest child (cosmetic only), clamped
        ln = 1.0
        if b.name in kids:
            d = min((world[c].translation - M.translation).length for c in kids[b.name])
            ln = max(min(d, 6.0), 0.5)
        y_axis = M.to_3x3() @ Vector((0, 1, 0))
        axis, roll = bpy.types.Bone.AxisRollFromMatrix(M.to_3x3(), axis=y_axis)
        e = arm.edit_bones.new(b.name)
        e.head = M.translation
        e.tail = M.translation + axis.normalized() * ln
        e.roll = roll
        eb[b.name] = e
    for b in bones:
        if b.parent is not None:
            eb[b.name].parent = eb[b.parent]
    # verify exact orientation preserved
    worst = 0.0
    for b in bones:
        m3 = eb[b.name].matrix.to_3x3()
        want = world[b.name].to_3x3()
        worst = max(worst, max(abs(m3[i][k] - want[i][k]) for i in range(3) for k in range(3)))
    print('[armature] max bone-orientation deviation: %.2e' % worst)
    assert worst < 1e-3
    bpy.ops.object.mode_set(mode='OBJECT')
    # rest matrices in armature space + rest-local per bone
    rest = {}
    for pb in obj.pose.bones:
        rest[pb.name] = pb.bone.matrix_local.copy()
    rest_local = {}
    for b in bones:
        rest_local[b.name] = (rest[b.name] if b.parent is None else rest[b.parent].inverted() @ rest[b.name])
    for pb in obj.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return obj, rest, rest_local


def build_mesh_object(name, model, joint_names, arm_obj, to_world, texmap, pngs):
    """Join all surfaces of one model into a single skinned mesh object (one material slot per
    distinct material).  to_world: 4x4 Matrix (WaW inches) placing model space into rig space."""
    surfaces, vbufs = model['surfaces'], model['vbufs']
    mats = []
    for s in surfaces:
        if s['mat'] not in mats:
            mats.append(s['mat'])
    M3 = np.array(to_world.to_3x3())
    T = np.array(to_world.translation)
    has_color = any(v['C'] is not None for v in vbufs.values())
    base, bases = 0, {}
    V, Nn, UV, Cc, Jn, Wt = [], [], [], [], [], []
    for key, v in vbufs.items():
        bases[key] = base
        V.append((v['P'] @ M3.T + T) * INCH_TO_CM)
        n = v['N'] @ M3.T
        Nn.append(n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12))
        UV.append(np.stack([v['UV'][:, 0], 1.0 - v['UV'][:, 1]], axis=1))   # WaW/glTF V down -> Blender V up
        if has_color:
            Cc.append(v['C'] if v['C'] is not None else np.ones((len(v['P']), 4)))
        Jn.append(v['J'])
        Wt.append(v['W'])
        base += len(v['P'])
    V, Nn, UV = np.concatenate(V), np.concatenate(Nn), np.concatenate(UV)
    Jn, Wt = np.concatenate(Jn), np.concatenate(Wt)
    Cc = np.concatenate(Cc) if has_color else None
    faces, mat_idx = [], []
    for s in surfaces:
        faces.append(s['F'] + bases[s['vkey']])
        mat_idx.append(np.full(len(s['F']), mats.index(s['mat']), dtype=np.int32))
    Fc, MI = np.concatenate(faces), np.concatenate(mat_idx)

    # winding check against vertex normals (Blender front faces are CCW)
    a, b, c = V[Fc[:, 0]], V[Fc[:, 1]], V[Fc[:, 2]]
    agree = (np.cross(b - a, c - a) * (Nn[Fc[:, 0]] + Nn[Fc[:, 1]] + Nn[Fc[:, 2]])).sum(axis=1)
    ccw, cw = int((agree > 0).sum()), int((agree < 0).sum())
    flip = cw > ccw
    print('[%s] triangle winding vs normals: ccw=%d cw=%d -> %s' % (name, ccw, cw, 'flipping' if flip else 'keeping'))
    if flip:
        Fc = Fc[:, ::-1].copy()

    # drop vertices no triangle references (keeps the FBX free of orphan points)
    used = np.zeros(len(V), dtype=bool)
    used[Fc.ravel()] = True
    orphan = int((~used).sum())
    remap = np.cumsum(used) - 1
    V, Nn, UV, Jn, Wt = V[used], Nn[used], UV[used], Jn[used], Wt[used]
    Cc = Cc[used] if Cc is not None else None
    Fc = remap[Fc]
    print('[%s] verts=%d (orphans dropped: %d) tris=%d materials=%s' % (name, len(V), orphan, len(Fc), mats))

    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], Fc.tolist())
    me.polygons.foreach_set('material_index', MI)
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    uvl = me.uv_layers.new(name='UVMap')
    lv = np.empty(len(me.loops), dtype=np.int32)
    me.loops.foreach_get('vertex_index', lv)
    uvl.data.foreach_set('uv', UV[lv].reshape(-1))
    if has_color:
        ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
        ca.data.foreach_set('color', Cc[lv].reshape(-1))
    me.validate()
    me.normals_split_custom_set_from_vertices(Nn.tolist())
    for mn in mats:
        m = bpy.data.materials.get(mn) or bpy.data.materials.new(mn)
        me.materials.append(m)
        if mn in texmap:
            m['waw_textures'] = json.dumps(texmap[mn])
            bc = texmap[mn].get('base_color')
            if bc and bc in pngs and m.node_tree is None:
                m.use_nodes = True
            if bc and bc in pngs and m.node_tree is not None:
                nt = m.node_tree
                bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                if bsdf is not None:
                    tex = nt.nodes.new('ShaderNodeTexImage')
                    tex.image = bpy.data.images.load(pngs[bc], check_existing=True)
                    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    # vertex groups (skin weights); <=4 influences per vertex, normalised
    groups = {}
    for vi in range(len(V)):
        infl = [(joint_names[int(Jn[vi][k])], float(Wt[vi][k])) for k in range(4) if Wt[vi][k] > 1e-6]
        tot = sum(w for _, w in infl) or 1.0
        for bn, w in infl:
            if bn not in groups:
                groups[bn] = obj.vertex_groups.new(name=bn)
            groups[bn].add([vi], w / tot, 'REPLACE')
    mod = obj.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm_obj
    obj.parent = arm_obj
    return obj, dict(verts=len(V), tris=len(Fc), materials=mats, groups=len(groups),
                     orphan_vertices_dropped=orphan, winding_flipped=bool(flip))


def texture_map(glb):
    """material name -> {slot: image filename} from the glTF material/texture tables."""
    j = glb.j
    out = {}
    for m in j.get('materials', []):
        name = m['name'].split('/')[-1]
        d = {}
        bc = m.get('pbrMetallicRoughness', {}).get('baseColorTexture')
        if bc is not None:
            d['base_color'] = os.path.basename(j['images'][j['textures'][bc['index']]['source']]['uri'])
        nt = m.get('normalTexture')
        if nt is not None:
            d['normal'] = os.path.basename(j['images'][j['textures'][nt['index']]['source']]['uri'])
        out[name] = d
    return out


# --------------------------------------------------------------------------------------
# Animation baking
# --------------------------------------------------------------------------------------
def pose_samples(anim, bones, rest_local, base_pose):
    """Return {bone: list over frames of (Vector loc_cm, Quaternion q)} parent-relative WaW,
    plus sets of keyed / skipped bone names.  Unkeyed channels fall back to base_pose[bone]
    (which defaults to the model's bind local pose)."""
    baked = waw_xanim.bake(anim)
    n = anim.num_frames + 1
    rig_names = {b.name for b in bones}
    keyed, skipped = set(), []
    out = {}
    for bname, d in baked.items():
        if bname not in rig_names:
            skipped.append(bname)
    for b in bones:
        bt, bq = base_pose[b.name]
        d = baked.get(b.name)
        seq = []
        if d is not None and (d['q'] is not None or d['t'] is not None):
            keyed.add(b.name)
        prev = None
        for f in range(n):
            t = bt
            q = bq
            if d is not None:
                if d['t'] is not None:
                    tt = d['t'][f]
                    t = Vector((tt[0], tt[1], tt[2])) * INCH_TO_CM
                if d['q'] is not None:
                    qq = d['q'][f]
                    q = Quaternion((qq[3], qq[0], qq[1], qq[2]))
            if prev is not None and prev.dot(q) < 0:
                q = Quaternion((-q.w, -q.x, -q.y, -q.z))
            prev = q
            seq.append((t, q))
        out[b.name] = seq
    return out, keyed, skipped


def bind_pose(bones):
    return {b.name: (b.t * INCH_TO_CM, b.q.copy()) for b in bones}


def apply_action(arm_obj, bones, samples, rest_local, nframes, action_name):
    """Key matrix_basis = rest_local^-1 @ desired_local for every bone and frame."""
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()
    act = bpy.data.actions.new(action_name)
    arm_obj.animation_data.action = act
    inv_rest = {b.name: rest_local[b.name].inverted() for b in bones}
    pbs = {pb.name: pb for pb in arm_obj.pose.bones}
    for f in range(nframes):
        for b in bones:
            t, q = samples[b.name][f]
            L = Matrix.Translation(t) @ q.to_matrix().to_4x4()
            B = inv_rest[b.name] @ L
            pb = pbs[b.name]
            pb.location = B.to_translation()
            pb.rotation_quaternion = B.to_quaternion()
            pb.keyframe_insert('location', frame=f, group=b.name)
            pb.keyframe_insert('rotation_quaternion', frame=f, group=b.name)
    act.use_fake_user = True          # stays in bpy.data.actions while unassigned during export
    return act


def reset_pose(arm_obj):
    for pb in arm_obj.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.scale = (1, 1, 1)


def clear_action(arm_obj, act=None):
    if arm_obj.animation_data:
        arm_obj.animation_data.action = None
    reset_pose(arm_obj)
    for a in list(bpy.data.actions):
        if act is None or a == act:
            a.use_fake_user = False
            bpy.data.actions.remove(a)


def export_fbx(path, objs, bake_anim, nframes=None, all_actions=False):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    sc = bpy.context.scene
    sc.frame_start = 0
    sc.frame_end = max(1, (nframes or 2) - 1)
    types = {'ARMATURE', 'MESH'} if any(o.type == 'MESH' for o in objs) else {'ARMATURE'}
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types=types,
        global_scale=1.0,
        apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_NONE',
        axis_forward='Y', axis_up='Z',         # Blender native == FBX Up=+Z Front=-Y Coord=+X (UE4 import system)
        use_space_transform=True,
        bake_space_transform=False,
        use_mesh_modifiers=False,
        mesh_smooth_type='OFF',                # write (custom) normals
        use_tspace=False,
        add_leaf_bones=False,
        primary_bone_axis='Y', secondary_bone_axis='X',
        use_armature_deform_only=False,        # keep tag_* sockets
        armature_nodetype='NULL',
        bake_anim=bake_anim,
        bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=all_actions,
        bake_anim_force_startend_keying=True,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
        path_mode='STRIP',
        embed_textures=False,
        use_custom_props=False,
    )


def convert_textures(assets, texnames, outdir):
    """DDS (DXT1/DXT5) -> PNG next to the FBX files with our own numpy decoder
    (Blender cannot read these DDS files).  Returns {dds filename: png path}."""
    os.makedirs(outdir, exist_ok=True)
    done = {}
    for fn in sorted(texnames):
        src = os.path.join(assets, 'images', fn)
        dst = os.path.join(outdir, os.path.splitext(fn)[0] + '.png')
        if not os.path.exists(src):
            print('texture missing', fn)
            continue
        try:
            waw_dds.write_png(dst, waw_dds.decode_dds(src))
            done[fn] = dst
        except Exception as e:  # noqa
            print('texture convert failed', fn, e)
    return done


# --------------------------------------------------------------------------------------
def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--assets', required=True, help='OAT dump dir (contains model_export/, xanim/, images/)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--weapon', required=True, choices=sorted(WEAPONS))
    ap.add_argument('--png-textures', action='store_true')
    ap.add_argument('--only', default='', help='comma list of anim names (default all)')
    a = ap.parse_args(argv)
    cfg = WEAPONS[a.weapon]
    os.makedirs(a.out, exist_ok=True)
    mdir = os.path.join(a.assets, 'model_export')

    arms = load_model(os.path.join(mdir, ARMS_MODEL + '_lod0.glb'))
    gun = load_model(os.path.join(mdir, cfg['gun_model'] + '_lod0.glb'))
    bones = combine_rig(arms, gun)
    print('combined rig bones:', len(bones))

    # the combined rig is validated against the anim bone list
    idle_anim = waw_xanim.parse_xanim(os.path.join(a.assets, 'xanim', cfg['anim_prefix'] + cfg['idle']))
    fps = idle_anim.fps
    reset_scene(fps)
    rig_name = 'viewmodel_%s' % a.weapon
    arm_obj, rest, rest_local = build_armature(bones, rig_name + '_skeleton')

    # textures (optional) + meshes
    world_rest = {k: v for k, v in world_matrices(bones, 1.0).items()}      # inches
    texmap = {}
    texmap.update(texture_map(arms['glb']))
    texmap.update(texture_map(gun['glb']))
    pngs = {}
    if a.png_textures:
        names = {fn for d in texmap.values() for fn in d.values()}
        pngs = convert_textures(a.assets, names, a.out)
    arms_obj, arms_info = build_mesh_object(rig_name + '_arms', arms, [b.name for b in arms['bones']],
                                            arm_obj, Matrix.Identity(4), texmap, pngs)
    gun_obj, gun_info = build_mesh_object(rig_name + '_gun', gun, [b.name for b in gun['bones']],
                                          arm_obj, world_rest['tag_weapon'], texmap, pngs)

    summary = dict(weapon=a.weapon, rig_bones=len(bones), arms=arms_info, gun=gun_info,
                   units='centimetres (WaW inches x 2.54)', fps=fps, textures=texmap,
                   png={k: os.path.basename(v) for k, v in pngs.items()})

    # ---- model FBX (bind pose, no animation)
    model_fbx = os.path.join(a.out, '%s_viewmodel.fbx' % a.weapon)
    export_fbx(model_fbx, [arm_obj, arms_obj, gun_obj], bake_anim=False)
    print('wrote', model_fbx)
    summary['model_fbx'] = os.path.basename(model_fbx)

    # ---- animations (armature only, baked)
    want = [x for x in a.only.split(',') if x] if a.only else cfg['anims']
    base_bind = bind_pose(bones)
    # idle frame 0 = hip pose, used as base for partial (layered) anims such as ads_up/ads_down
    idle_samples, _, _ = pose_samples(idle_anim, bones, rest_local, base_bind)
    idle_base = {n: idle_samples[n][0] for n in idle_samples}
    anim_meta = {}
    for an in want:
        path = os.path.join(a.assets, 'xanim', cfg['anim_prefix'] + an)
        anim = waw_xanim.parse_xanim(path)
        partial = len(anim.bones) < 10
        base = idle_base if partial else base_bind
        samples, keyed, skipped = pose_samples(anim, bones, rest_local, base)
        nfr = anim.num_frames + 1
        clear_action(arm_obj)
        act = apply_action(arm_obj, bones, samples, rest_local, nfr, '%s_%s' % (a.weapon, an))
        # Export with NO action assigned (armature at its rest pose, so the FBX node transforms
        # are the bind pose) and let the exporter bake the stored action as the take.
        arm_obj.animation_data.action = None
        reset_pose(arm_obj)
        bpy.context.scene.frame_set(0)
        out = os.path.join(a.out, '%s_%s.fbx' % (a.weapon, an))
        export_fbx(out, [arm_obj], bake_anim=True, nframes=nfr, all_actions=True)
        clear_action(arm_obj, act)
        anim_meta[an] = dict(
            fbx=os.path.basename(out), source='xanim/' + cfg['anim_prefix'] + an,
            fps=anim.fps, key_frames=nfr, num_frames=anim.num_frames,
            duration_s=anim.num_frames / float(anim.fps) if anim.fps else 0.0,
            looped=anim.looped, flags=anim.flags, has_delta=anim.has_delta,
            partial_layered_anim=partial,
            base_pose='idle frame 0' if partial else 'model bind pose',
            keyed_bones=sorted(keyed), anim_bones_not_in_rig=sorted(skipped),
            notetracks=[dict(name=n['name'], frame=n['frame'], time_s=n['frame'] / float(anim.fps))
                        for n in anim.notes],
            notetrack_note='raw notetracks only; the engine appends an implicit "end" notify at the last frame')
        print('wrote', out, 'frames', nfr, 'fps', anim.fps, 'keyed', len(keyed), 'notes', len(anim.notes))
    summary['animations'] = anim_meta
    if not want:        # *_upgraded: model only, base weapon's JSONs/animations apply
        return
    with open(os.path.join(a.out, '%s_animations.json' % a.weapon), 'w') as fh:
        json.dump(summary, fh, indent=1)
    # notetracks only (frame numbers are xanim frames at the anim fps; time_s = frame / fps)
    with open(os.path.join(a.out, '%s_notetracks.json' % a.weapon), 'w') as fh:
        json.dump({k: dict(fps=v['fps'], num_frames=v['num_frames'], notetracks=v['notetracks'])
                   for k, v in anim_meta.items()}, fh, indent=1)
    # skeleton: hierarchy + bind-pose local transforms in cm (WaW axes), for retargeting / sockets
    wcm = world_matrices(bones, INCH_TO_CM)
    with open(os.path.join(a.out, '%s_skeleton.json' % a.weapon), 'w') as fh:
        json.dump(dict(units='cm', axes='X forward, Y left, Z up (WaW, right-handed); UE4 import flips Y',
                       root=[b.name for b in bones if b.parent is None][0],
                       bones=[dict(name=b.name, parent=b.parent,
                                   local_translation_cm=[round(c * INCH_TO_CM, 5) for c in b.t],
                                   local_rotation_xyzw=[round(b.q.x, 6), round(b.q.y, 6), round(b.q.z, 6), round(b.q.w, 6)],
                                   world_translation_cm=[round(c, 5) for c in wcm[b.name].translation])
                              for b in bones]), fh, indent=1)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    main(argv)
