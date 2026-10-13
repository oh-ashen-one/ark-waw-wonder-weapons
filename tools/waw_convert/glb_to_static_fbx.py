"""Headless Blender: WaW rigid GLB (OAT export) -> static FBX for UE4 (cm, Z up, X forward).
Usage: blender -b --factory-startup --python glb_to_static_fbx.py -- <in.glb> <out.fbx>"""
import bpy, sys, mathutils
a = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=a[0])
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
for o in bpy.context.scene.objects: o.select_set(o in meshes)
bpy.context.view_layer.objects.active = meshes[0]
# bake transforms, drop armature parenting/modifiers so it's a plain static mesh
for o in meshes:
    for m in list(o.modifiers): o.modifiers.remove(m)
    mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
for o in list(bpy.context.scene.objects):
    if o.type != 'MESH': bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.object.join()
o = bpy.context.view_layer.objects.active
# OAT glTF: undo its Y-up conversion (glTF importer already maps to Blender Z-up); WaW inches -> cm
o.scale = (2.54, 2.54, 2.54)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bb = [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
print("BBOX_CM", [round(min(v[i] for v in bb),2) for i in range(3)], [round(max(v[i] for v in bb),2) for i in range(3)], "verts", len(o.data.vertices), "mats", [m.name for m in o.data.materials])
if len(a) > 2:  # optional base-colour PNG -> single material with image texture
    img = bpy.data.images.load(a[2]); mat = bpy.data.materials.new('M_' + bpy.path.display_name_from_filepath(a[1])); mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'); tex = mat.node_tree.nodes.new('ShaderNodeTexImage'); tex.image = img
    mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color']); o.data.materials.clear(); o.data.materials.append(mat)
bpy.ops.export_scene.fbx(filepath=a[1], path_mode='COPY', embed_textures=True, use_selection=True, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y', axis_up='Z', mesh_smooth_type='FACE', add_leaf_bones=False, bake_anim=False)
