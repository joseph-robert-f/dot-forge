"""Reviewed Blender entry point. Inputs are bounded declarative JSON, never code.

This file runs only inside Blender. All Blender units here are millimetres.
"""
import json
import math
import sys
import time
from pathlib import Path
import bpy
from mathutils import Vector


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def meshes():
    return [o for o in bpy.context.scene.objects if o.type == 'MESH']


def bounds(objects):
    points = [o.matrix_world @ v.co for o in objects for v in o.data.vertices]
    if not points or not all(math.isfinite(x) for p in points for x in p):
        raise ValueError('empty or nonfinite scene')
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    return low, high


def generate(run, request):
    model_started = time.perf_counter()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    dimensions = [float(request['parameters'][k]) for k in ('width_mm','depth_mm','height_mm')]
    if any(not math.isfinite(d) or not 5 <= d <= 100 for d in dimensions):
        raise ValueError('calibration dimensions out of bounds')
    if request['generator_id'] == 'calibration-block':
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, dimensions[2]/2))
        obj = bpy.context.object
        obj.name = 'Calibration_Block'
        obj.dimensions = dimensions
    elif request['generator_id'] == 'geometric-mascot':
        # Original single-piece extruded robot silhouette, with two integral ears.
        # Counter-clockwise X/Z perimeter, never unions or hidden intersecting shells.
        w,d,h=dimensions
        outline=[(-.5,0),(.5,0),(.5,.12),(.30,.12),(.30,.43),(.18,.43),
                 (.18,.52),(.44,.52),(.44,.82),(.34,1),(.20,.82),
                 (-.20,.82),(-.34,1),(-.44,.82),(-.44,.52),(-.18,.52),
                 (-.18,.43),(-.30,.43),(-.30,.12),(-.5,.12)]
        vertices=[(x*w,y*d/2,z*h) for y in (-1,1) for x,z in outline]
        n=len(outline)
        faces=[tuple(range(n)),tuple(reversed(range(n,2*n)))]
        faces += [(i,i+n,(i+1)%n+n,(i+1)%n) for i in range(n)]
        mesh=bpy.data.meshes.new('Integral_Mascot');mesh.from_pydata(vertices,[],faces);mesh.update()
        obj=bpy.data.objects.new('Integral_Mascot',mesh);bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active=obj;obj.select_set(True)
    else:
        raise ValueError('unsupported native generator')
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = .001
    model_seconds = time.perf_counter() - model_started
    export_started = time.perf_counter()
    bpy.ops.wm.save_as_mainfile(filepath=str(run/'native/model.blend'))
    bpy.ops.wm.stl_export(filepath=str(run/'exports/model.stl'), export_selected_objects=True,
                          apply_modifiers=True, global_scale=1.0, use_scene_unit=False)
    dump(run/'native/generation.json', {'status':'pass','generator':request['generator_id']+'@1',
         'dimensions_mm':dimensions,'mesh_objects':1,'blender_version':bpy.app.version_string,
         'python_version':sys.version.split()[0], 'unit_scale_metres':.001, 'model_construction_seconds':model_seconds, 'native_save_and_stl_export_seconds':time.perf_counter()-export_started})


def reopen(run):
    bpy.ops.wm.open_mainfile(filepath=str(run/'native/model.blend'), load_ui=False, use_scripts=False)
    objs=meshes(); low,high=bounds(objs)
    native_dimensions=list(high-low)
    native_count=len(objs)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.stl_import(filepath=str(run/'exports/model.stl'), use_scene_unit=False)
    objs=meshes(); low,high=bounds(objs)
    export_dimensions=list(high-low)
    if any(abs(a-b)>1e-4 for a,b in zip(native_dimensions,export_dimensions)):
        raise ValueError('native/export bounds disagree')
    dump(run/'native/reopen.json',{'status':'pass','fresh_process':True,
         'native_mesh_objects':native_count,'stl_mesh_objects':len(objs),
         'native_dimensions_mm':native_dimensions,'stl_dimensions_mm':export_dimensions,
         'method':'fresh Blender BLEND load with scripts disabled and clean STL import'})


def preview(run):
    # Render the actual printing mesh, not potentially different display geometry.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.stl_import(filepath=str(run/'exports/model.stl'), use_scene_unit=False)
    objects=meshes(); low,high=bounds(objects); center=(low+high)/2
    extent=max(high-low); distance=extent*3
    scene=bpy.context.scene
    scene.render.engine='BLENDER_WORKBENCH'
    scene.render.resolution_x=512; scene.render.resolution_y=512
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.display.shading.light='STUDIO'
    scene.display.shading.color_type='SINGLE'
    scene.display.shading.single_color=(.15,.55,.62)
    scene.display.shading.show_shadows=True
    scene.display.shading.show_cavity=True
    scene.display.shading.background_type='WORLD'
    scene.world=bpy.data.worlds.new("Review_World")
    scene.world.color=(.07,.07,.07)
    camera=bpy.data.objects.new('Review_Camera',bpy.data.cameras.new('Review_Camera'))
    scene.collection.objects.link(camera);scene.camera=camera
    camera.data.type='ORTHO';camera.data.ortho_scale=extent*1.65
    camera.data.clip_end=distance*10
    request=json.loads((run/'request.json').read_text())
    oblique=(-1,-1,.8) if request.get('backend') == 'freecad' else (1,-1,.8)
    for name,direction in [('front',(0,-1,0)),('side',(1,0,0)),('back',(0,1,0)),
                           ('top',(0,0,1)),('oblique',oblique)]:
        camera.location=center+Vector(direction).normalized()*distance
        camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(run/'previews'/f'{name}.png')
        bpy.ops.render.render(write_still=True)
    dump(run/'previews/preview.json',{'status':'pass','subject':'exact exported printing STL',
         'views':['front','side','back','top','oblique'],'renderer':'BLENDER_WORKBENCH',
         'human_visual_completeness':'unknown'})


if __name__ == '__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    mode, directory=args
    run=Path(directory).resolve()
    for name in ('native','exports','previews'):(run/name).mkdir(exist_ok=True)
    if mode=='generate':generate(run,json.loads((run/'request.json').read_text()))
    elif mode=='reopen':reopen(run)
    elif mode=='preview':preview(run)
    else:raise ValueError('unsupported reviewed operation')
