# SPDX-License-Identifier: GPL-3.0-or-later
# Data model. Job/queue structure adapted from RenderCue by Usama Bin Shahid (GPL-3.0).
import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty,
                       IntProperty, IntVectorProperty, PointerProperty, StringProperty)

_engine_items = []  # keep a reference: Blender crashes if dynamic enum strings are garbage collected


def engine_items(self, context):
    _engine_items[:] = [('BLENDER_EEVEE', "EEVEE", ""), ('BLENDER_WORKBENCH', "Workbench", "")] + [
        (c.bl_idname, getattr(c, "bl_label", c.bl_idname), "")
        for c in bpy.types.RenderEngine.__subclasses__() if getattr(c, "bl_idname", None)]
    return _engine_items


FORMATS = ['PNG', 'JPEG', 'OPEN_EXR', 'OPEN_EXR_MULTILAYER', 'TIFF', 'WEBP', 'AVIF', 'JPEG2000',
           'TARGA', 'BMP', 'HDR', 'DPX', 'CINEON', 'FFMPEG']

# One row per override: (key, section, property, scene-relative RNA paths).
# A vector property maps element by element onto its paths; a scalar is written to every path
# (samples go to Cycles and EEVEE, only the active engine reads it). paths=None -> special case in core.
SPECS = [
    ("engine", "Render", EnumProperty(name="Engine", items=engine_items), ["render.engine"]),
    ("device", "Render", EnumProperty(name="Device", items=[('CPU', "CPU", ""), ('GPU', "GPU", "")], default='GPU'), ["cycles.device"]),
    ("samples", "Render", IntProperty(name="Samples", default=128, min=1, soft_max=8192), ["cycles.samples", "eevee.taa_render_samples"]),
    ("noise_threshold", "Render", FloatProperty(name="Noise Threshold", default=0.01, min=0.0, precision=4), ["cycles.adaptive_threshold"]),
    ("denoise", "Render", BoolProperty(name="Denoise", default=True), ["cycles.use_denoising"]),
    ("max_bounces", "Render", IntProperty(name="Max Bounces", default=12, min=0), ["cycles.max_bounces"]),
    ("time_limit", "Render", FloatProperty(name="Time Limit (s)", default=0.0, min=0.0), ["cycles.time_limit"]),
    ("motion_blur", "Render", BoolProperty(name="Motion Blur"), ["render.use_motion_blur"]),
    ("simplify", "Render", BoolProperty(name="Simplify"), ["render.use_simplify"]),
    ("persistent_data", "Render", BoolProperty(name="Persistent Data"), ["render.use_persistent_data"]),

    ("camera", "Scene", StringProperty(name="Camera"), None),
    ("world", "Scene", StringProperty(name="World"), None),
    ("view_layer", "Scene", StringProperty(name="View Layer", description="Render only this view layer"), None),
    ("transparent", "Scene", BoolProperty(name="Transparent Film"), ["render.film_transparent"]),
    ("compositor", "Scene", BoolProperty(name="Compositing", default=True), ["render.use_compositing"]),

    ("frame_range", "Frames & Size", IntVectorProperty(name="Frame Range", size=2, default=(1, 250)), ["frame_start", "frame_end"]),
    ("frame_step", "Frames & Size", IntProperty(name="Frame Step", default=1, min=1), ["frame_step"]),
    ("resolution", "Frames & Size", IntVectorProperty(name="Resolution", size=2, default=(1920, 1080), min=4), ["render.resolution_x", "render.resolution_y"]),
    ("resolution_percentage", "Frames & Size", IntProperty(name="Scale %", default=100, min=1, max=10000, soft_max=200), ["render.resolution_percentage"]),
    ("fps", "Frames & Size", IntProperty(name="FPS", default=24, min=1), ["render.fps"]),

    ("file_format", "File", EnumProperty(name="Format", items=[(f, f.replace('_', ' ').title(), "") for f in FORMATS]), None),
    ("color_mode", "File", EnumProperty(name="Color", items=[(c, c, "") for c in ('BW', 'RGB', 'RGBA')], default='RGBA'), ["render.image_settings.color_mode"]),
    ("color_depth", "File", EnumProperty(name="Depth", items=[(d, d, "") for d in ('8', '10', '12', '16', '32')], default='16'), ["render.image_settings.color_depth"]),
    ("exr_codec", "File", EnumProperty(name="EXR Codec", items=[(c, c, "") for c in ('NONE', 'ZIP', 'PIZ', 'DWAA', 'DWAB', 'ZIPS', 'RLE', 'PXR24', 'B44', 'B44A')], default='ZIP'), ["render.image_settings.exr_codec"]),
    ("quality", "File", IntProperty(name="Quality", default=90, min=0, max=100), ["render.image_settings.quality"]),
    ("overwrite", "File", BoolProperty(name="Overwrite", default=True, description="Off = skip frames that already exist"), ["render.use_overwrite"]),
    ("placeholder", "File", BoolProperty(name="Placeholders", description="Write empty files at frame start (for several machines on one sequence)"), ["render.use_placeholder"]),

    ("view_transform", "Color", StringProperty(name="View Transform", default="AgX"), ["view_settings.view_transform"]),
    ("look", "Color", StringProperty(name="Look", default="None"), ["view_settings.look"]),
    ("exposure", "Color", FloatProperty(name="Exposure", default=0.0), ["view_settings.exposure"]),
    ("gamma", "Color", FloatProperty(name="Gamma", default=1.0), ["view_settings.gamma"]),
]
SECTIONS = list(dict.fromkeys(s[1] for s in SPECS))

_ann = {}
for _key, _section, _prop, _paths in SPECS:
    _ann["use_" + _key] = BoolProperty(name="Override " + _key.replace('_', ' ').title())
    _ann[_key] = _prop
SBR_Overrides = type("SBR_Overrides", (bpy.types.PropertyGroup,), {"__annotations__": _ann})


class SBR_CustomOverride(bpy.types.PropertyGroup):
    enabled: BoolProperty(name="Enabled", default=True)
    path: StringProperty(name="Path", description="RNA path relative to the scene (cycles.max_bounces, "
                         "render.resolution_x) or absolute from bpy.data (bpy.data.objects[\"Cube\"].hide_render)")
    value: StringProperty(name="Value", description="Python literal: 12, 0.5, True, 'AgX', (1, 0, 0)")


STATUS_ITEMS = [('PENDING', "Pending", "", 'RADIOBUT_OFF', 0), ('RENDERING', "Rendering", "", 'RENDER_STILL', 1),
                ('COMPLETED', "Completed", "", 'CHECKMARK', 2), ('FAILED', "Failed", "", 'ERROR', 3),
                ('CANCELLED', "Cancelled", "", 'CANCEL', 4)]


class SBR_Job(bpy.types.PropertyGroup):
    # `name` (built in) is the job name, used by the {job} token
    enabled: BoolProperty(name="Enabled", default=True, description="Render this job")
    scene: PointerProperty(type=bpy.types.Scene, name="Scene")
    mode: EnumProperty(name="Mode", items=[
        ('ANIM', "Animation", "Frame range (with step), works with video formats"),
        ('STILL', "Current Frame", "Only the scene's current frame"),
        ('FRAMES', "Frame List", "Explicit frames, e.g. 1, 12, 40-60, 100-200x10"),
    ])
    frames: StringProperty(name="Frames", default="1")
    use_output: BoolProperty(name="Own Output", description="Use this job's folder/name templates instead of the global ones")
    output_dir: StringProperty(name="Folder", default="//renders/{blend}/{job}/")
    file_name: StringProperty(name="File Name", default="{job}_")
    overrides: PointerProperty(type=SBR_Overrides)
    custom: CollectionProperty(type=SBR_CustomOverride)
    ui_custom_index: IntProperty(options={'SKIP_SAVE'})
    # runtime
    status: EnumProperty(name="Status", items=STATUS_ITEMS, options={'SKIP_SAVE'})
    done: IntProperty(options={'SKIP_SAVE'})
    total: IntProperty(options={'SKIP_SAVE'})
    error: StringProperty(options={'SKIP_SAVE'})
    elapsed: FloatProperty(options={'SKIP_SAVE'})


class SBR_Settings(bpy.types.PropertyGroup):
    jobs: CollectionProperty(type=SBR_Job)
    active: IntProperty(name="Active Job")
    output_dir: StringProperty(name="Folder", default="//renders/{blend}/{job}/",
                               description="Output folder template, see Tokens")
    file_name: StringProperty(name="File Name", default="{job}_", description="File name template, see Tokens")
    frame_padding: IntProperty(name="Frame Padding", default=4, min=1, max=10,
                               description="Number of # appended when the file name has none")
    use_snapshot: BoolProperty(name="Render Unsaved Changes", default=True,
                               description="Render a copy of the file as it is now. Off: render the saved .blend "
                               "directly (no copy, faster for big files)")
    overrides: PointerProperty(type=SBR_Overrides)
    custom: CollectionProperty(type=SBR_CustomOverride)
    # runtime
    is_rendering: BoolProperty(options={'SKIP_SAVE'})
    is_paused: BoolProperty(options={'SKIP_SAVE'})
    message: StringProperty(options={'SKIP_SAVE'})
    done: IntProperty(options={'SKIP_SAVE'})
    total: IntProperty(options={'SKIP_SAVE'})
    eta: StringProperty(options={'SKIP_SAVE'})
    log_path: StringProperty(options={'SKIP_SAVE'})


classes = (SBR_Overrides, SBR_CustomOverride, SBR_Job, SBR_Settings)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.sbr = PointerProperty(type=SBR_Settings)


def unregister():
    del bpy.types.WindowManager.sbr
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
