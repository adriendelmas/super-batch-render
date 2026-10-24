# SPDX-License-Identifier: GPL-3.0-or-later
# Data model. Job/queue structure adapted from RenderCue by Usama Bin Shahid (GPL-3.0).
import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, IntVectorProperty, PointerProperty, StringProperty)

_engine_items = []  # keep a reference: Blender crashes if dynamic enum strings are garbage collected


def engine_items(self, context):
    _engine_items[:] = [('BLENDER_EEVEE', "EEVEE", ""), ('BLENDER_WORKBENCH', "Workbench", "")] + [
        (c.bl_idname, getattr(c, "bl_label", c.bl_idname), "")
        for c in bpy.types.RenderEngine.__subclasses__() if getattr(c, "bl_idname", None)]
    return _engine_items


STAMP_FIELDS = ['DATE', 'TIME', 'RENDER_TIME', 'FRAME', 'FRAME_RANGE', 'MEMORY', 'HOSTNAME', 'CAMERA', 'LENS',
                'SCENE', 'MARKER', 'FILENAME', 'SEQUENCER_STRIP']
FORMATS = ['PNG', 'JPEG', 'OPEN_EXR', 'OPEN_EXR_MULTILAYER', 'TIFF', 'WEBP', 'AVIF', 'JPEG2000',
           'TARGA', 'BMP', 'HDR', 'DPX', 'CINEON', 'FFMPEG']

# One row per override: (key, section, property, scene-relative RNA paths).
# A vector property maps element by element onto its paths; a scalar is written to every path
# (samples go to Cycles and EEVEE, only the active engine reads it). paths=None -> special case in core.
SPECS = [
    ("engine", "Engine", EnumProperty(name="Engine", items=engine_items), ["render.engine"]),
    ("device", "Engine", EnumProperty(name="Device", items=[('CPU', "CPU", ""), ('GPU', "GPU", "")], default='GPU'), ["cycles.device"]),
    ("persistent_data", "Engine", BoolProperty(name="Persistent Data"), ["render.use_persistent_data"]),
    ("threads", "Engine", IntProperty(name="CPU Threads", default=0, min=0, max=1024, description="0 = auto. Lower it to keep the machine usable while rendering"), None),
    ("auto_tile", "Engine", BoolProperty(name="Use Tiling", default=True), ["cycles.use_auto_tile"]),
    ("tile_size", "Engine", IntProperty(name="Tile Size", default=2048, min=8, max=8192), ["cycles.tile_size"]),

    ("samples", "Sampling", IntProperty(name="Samples", default=128, min=1, soft_max=8192), ["cycles.samples", "eevee.taa_render_samples"]),
    ("adaptive", "Sampling", BoolProperty(name="Adaptive Sampling", default=True), ["cycles.use_adaptive_sampling"]),
    ("noise_threshold", "Sampling", FloatProperty(name="Noise Threshold", default=0.01, min=0.0, precision=4), ["cycles.adaptive_threshold"]),
    ("adaptive_min_samples", "Sampling", IntProperty(name="Min Samples", default=0, min=0), ["cycles.adaptive_min_samples"]),
    ("time_limit", "Sampling", FloatProperty(name="Time Limit (s)", default=0.0, min=0.0), ["cycles.time_limit"]),
    ("denoise", "Sampling", BoolProperty(name="Denoise", default=True), ["cycles.use_denoising"]),
    ("denoiser", "Sampling", EnumProperty(name="Denoiser", items=[('OPENIMAGEDENOISE', "OpenImageDenoise", ""), ('OPTIX', "OptiX", "")]), ["cycles.denoiser"]),
    ("denoise_gpu", "Sampling", BoolProperty(name="Denoise on GPU", default=True), ["cycles.denoising_use_gpu"]),
    ("seed", "Sampling", IntProperty(name="Seed", default=0, min=0), ["cycles.seed"]),
    ("animated_seed", "Sampling", BoolProperty(name="Animated Seed"), ["cycles.use_animated_seed"]),
    ("light_tree", "Sampling", BoolProperty(name="Light Tree", default=True), ["cycles.use_light_tree"]),

    ("max_bounces", "Light Paths", IntProperty(name="Max Bounces", default=12, min=0), ["cycles.max_bounces"]),
    ("diffuse_bounces", "Light Paths", IntProperty(name="Diffuse", default=4, min=0), ["cycles.diffuse_bounces"]),
    ("glossy_bounces", "Light Paths", IntProperty(name="Glossy", default=4, min=0), ["cycles.glossy_bounces"]),
    ("transmission_bounces", "Light Paths", IntProperty(name="Transmission", default=12, min=0), ["cycles.transmission_bounces"]),
    ("volume_bounces", "Light Paths", IntProperty(name="Volume", default=0, min=0), ["cycles.volume_bounces"]),
    ("transparent_bounces", "Light Paths", IntProperty(name="Transparent", default=8, min=0), ["cycles.transparent_max_bounces"]),
    ("clamp_direct", "Light Paths", FloatProperty(name="Clamp Direct", default=0.0, min=0.0), ["cycles.sample_clamp_direct"]),
    ("clamp_indirect", "Light Paths", FloatProperty(name="Clamp Indirect", default=10.0, min=0.0), ["cycles.sample_clamp_indirect"]),
    ("filter_glossy", "Light Paths", FloatProperty(name="Filter Glossy", default=1.0, min=0.0), ["cycles.blur_glossy"]),
    ("caustics_reflective", "Light Paths", BoolProperty(name="Reflective Caustics", default=True), ["cycles.caustics_reflective"]),
    ("caustics_refractive", "Light Paths", BoolProperty(name="Refractive Caustics", default=True), ["cycles.caustics_refractive"]),
    ("transparent_glass", "Light Paths", BoolProperty(name="Transparent Glass"), ["cycles.film_transparent_glass"]),

    ("guiding", "Cycles Advanced", BoolProperty(name="Path Guiding"), ["cycles.use_guiding"]),
    ("guiding_surface", "Cycles Advanced", BoolProperty(name="Surface Guiding", default=True), ["cycles.use_surface_guiding"]),
    ("guiding_volume", "Cycles Advanced", BoolProperty(name="Volume Guiding", default=True), ["cycles.use_volume_guiding"]),
    ("guiding_samples", "Cycles Advanced", IntProperty(name="Training Samples", default=128, min=0), ["cycles.guiding_training_samples"]),
    ("fast_gi", "Cycles Advanced", BoolProperty(name="Fast GI Approximation"), ["cycles.use_fast_gi"]),
    ("fast_gi_method", "Cycles Advanced", EnumProperty(name="Fast GI Method", items=[('REPLACE', "Replace", ""), ('ADD', "Add", "")]), ["cycles.fast_gi_method"]),
    ("ao_bounces", "Cycles Advanced", IntProperty(name="AO Bounces", default=1, min=0), ["cycles.ao_bounces_render"]),
    ("light_threshold", "Cycles Advanced", FloatProperty(name="Light Threshold", default=0.01, min=0.0, max=1.0, precision=4), ["cycles.light_sampling_threshold"]),
    ("volume_step_rate", "Cycles Advanced", FloatProperty(name="Volume Step Rate", default=1.0, min=0.01, max=100.0), ["cycles.volume_step_rate"]),
    ("volume_max_steps", "Cycles Advanced", IntProperty(name="Volume Max Steps", default=1024, min=2, max=65536), ["cycles.volume_max_steps"]),
    ("dicing_rate", "Cycles Advanced", FloatProperty(name="Dicing Rate", default=1.0, min=0.1, max=1000.0), ["cycles.dicing_rate"]),
    ("max_subdivisions", "Cycles Advanced", IntProperty(name="Max Subdivisions (dicing)", default=12, min=0, max=16), ["cycles.max_subdivisions"]),
    ("offscreen_dicing", "Cycles Advanced", FloatProperty(name="Offscreen Dicing Scale", default=4.0, min=1.0), ["cycles.offscreen_dicing_scale"]),
    ("camera_cull", "Cycles Advanced", BoolProperty(name="Camera Culling"), ["cycles.use_camera_cull"]),
    ("camera_cull_margin", "Cycles Advanced", FloatProperty(name="Camera Cull Margin", default=0.1, min=0.0, max=5.0), ["cycles.camera_cull_margin"]),
    ("distance_cull", "Cycles Advanced", BoolProperty(name="Distance Culling"), ["cycles.use_distance_cull"]),
    ("distance_cull_margin", "Cycles Advanced", FloatProperty(name="Cull Distance", default=50.0, min=0.0), ["cycles.distance_cull_margin"]),
    ("pixel_filter", "Cycles Advanced", EnumProperty(name="Pixel Filter", items=[('BLACKMAN_HARRIS', "Blackman-Harris", ""), ('GAUSSIAN', "Gaussian", ""), ('BOX', "Box", "")]), ["cycles.pixel_filter_type"]),
    ("filter_width", "Cycles Advanced", FloatProperty(name="Filter Width (px)", default=1.5, min=0.01, max=10.0), ["cycles.filter_width"]),
    ("denoise_prefilter", "Cycles Advanced", EnumProperty(name="Denoise Prefilter", items=[(i, i.title(), "") for i in ('ACCURATE', 'FAST', 'NONE')]), ["cycles.denoising_prefilter"]),
    ("denoise_quality", "Cycles Advanced", EnumProperty(name="Denoise Quality", items=[(i, i.title(), "") for i in ('HIGH', 'BALANCED', 'FAST')]), ["cycles.denoising_quality"]),
    ("denoise_passes", "Cycles Advanced", EnumProperty(name="Denoise Passes", items=[('RGB_ALBEDO_NORMAL', "Albedo + Normal", ""), ('RGB_ALBEDO', "Albedo", ""), ('RGB', "None", "")]), ["cycles.denoising_input_passes"]),
    ("auto_scrambling", "Cycles Advanced", BoolProperty(name="Automatic Scrambling"), ["cycles.auto_scrambling_distance"]),
    ("scrambling_distance", "Cycles Advanced", FloatProperty(name="Scrambling Distance", default=1.0, min=0.0, max=1.0), ["cycles.scrambling_distance"]),

    ("eevee_raytracing", "EEVEE", BoolProperty(name="Ray Tracing"), ["eevee.use_raytracing"]),
    ("eevee_shadows", "EEVEE", BoolProperty(name="Shadows", default=True), ["eevee.use_shadows"]),
    ("shadow_rays", "EEVEE", IntProperty(name="Shadow Rays", default=1, min=1, max=4), ["eevee.shadow_ray_count"]),
    ("shadow_steps", "EEVEE", IntProperty(name="Shadow Steps", default=6, min=1, max=16), ["eevee.shadow_step_count"]),
    ("shadow_resolution", "EEVEE", FloatProperty(name="Shadow Resolution", default=1.0, min=0.0, max=1.0), ["eevee.shadow_resolution_scale"]),
    ("volume_samples", "EEVEE", IntProperty(name="Volume Samples", default=64, min=1), ["eevee.volumetric_samples"]),
    ("volume_tile", "EEVEE", EnumProperty(name="Volume Tile Size", items=[(t, t + " px", "") for t in ('1', '2', '4', '8', '16')], default='8'), ["eevee.volumetric_tile_size"]),
    ("volume_shadows", "EEVEE", BoolProperty(name="Volume Shadows"), ["eevee.use_volumetric_shadows"]),
    ("overscan", "EEVEE", BoolProperty(name="Overscan"), ["eevee.use_overscan"]),

    ("gi_bounces", "EEVEE Advanced", IntProperty(name="GI Diffuse Bounces", default=3, min=0), ["eevee.gi_diffuse_bounces"]),
    ("gi_cubemap", "EEVEE Advanced", EnumProperty(name="Cubemap Size", items=[(i, i, "") for i in ('128', '256', '512', '1024', '2048', '4096')], default='512'), ["eevee.gi_cubemap_resolution"]),
    ("gi_visibility", "EEVEE Advanced", EnumProperty(name="Visibility Size", items=[(i, i, "") for i in ('8', '16', '32', '64')], default='32'), ["eevee.gi_visibility_resolution"]),
    ("gi_pool", "EEVEE Advanced", EnumProperty(name="Irradiance Pool (MB)", items=[(i, i, "") for i in ('16', '32', '64', '128', '256', '512', '1024')], default='16'), ["eevee.gi_irradiance_pool_size"]),
    ("horizon_scan", "EEVEE Advanced", BoolProperty(name="Fast GI (Horizon Scan)"), ["eevee.use_fast_gi"]),
    ("horizon_method", "EEVEE Advanced", EnumProperty(name="Fast GI Method", items=[('GLOBAL_ILLUMINATION', "Global Illumination", ""), ('AMBIENT_OCCLUSION_ONLY', "AO Only", "")]), ["eevee.fast_gi_method"]),
    ("horizon_resolution", "EEVEE Advanced", EnumProperty(name="Fast GI Resolution", items=[(i, "1:" + i, "") for i in ('1', '2', '4', '8', '16')], default='2'), ["eevee.fast_gi_resolution"]),
    ("horizon_rays", "EEVEE Advanced", IntProperty(name="Fast GI Rays", default=2, min=1, max=16), ["eevee.fast_gi_ray_count"]),
    ("horizon_steps", "EEVEE Advanced", IntProperty(name="Fast GI Steps", default=8, min=1, max=64), ["eevee.fast_gi_step_count"]),
    ("horizon_quality", "EEVEE Advanced", FloatProperty(name="Fast GI Precision", default=0.25, min=0.0, max=1.0), ["eevee.fast_gi_quality"]),
    ("horizon_distance", "EEVEE Advanced", FloatProperty(name="Fast GI Distance", default=0.0, min=0.0), ["eevee.fast_gi_distance"]),
    ("clamp_surface_direct", "EEVEE Advanced", FloatProperty(name="Clamp Surface Direct", default=0.0, min=0.0), ["eevee.clamp_surface_direct"]),
    ("clamp_surface_indirect", "EEVEE Advanced", FloatProperty(name="Clamp Surface Indirect", default=10.0, min=0.0), ["eevee.clamp_surface_indirect"]),
    ("clamp_volume_direct", "EEVEE Advanced", FloatProperty(name="Clamp Volume Direct", default=0.0, min=0.0), ["eevee.clamp_volume_direct"]),
    ("clamp_volume_indirect", "EEVEE Advanced", FloatProperty(name="Clamp Volume Indirect", default=0.0, min=0.0), ["eevee.clamp_volume_indirect"]),
    ("volume_range", "EEVEE Advanced", BoolProperty(name="Custom Volume Range"), ["eevee.use_volume_custom_range"]),
    ("volume_start_end", "EEVEE Advanced", FloatVectorProperty(name="Volume Start / End", size=2, default=(0.1, 100.0), min=0.000001), ["eevee.volumetric_start", "eevee.volumetric_end"]),
    ("bokeh_max", "EEVEE Advanced", FloatProperty(name="Bokeh Max Size (px)", default=100.0, min=0.0, max=2000.0), ["eevee.bokeh_max_size"]),
    ("bokeh_threshold", "EEVEE Advanced", FloatProperty(name="Bokeh Threshold", default=1.0, min=0.0), ["eevee.bokeh_threshold"]),
    ("bokeh_jitter", "EEVEE Advanced", BoolProperty(name="Jitter Camera (DOF)"), ["eevee.use_bokeh_jittered"]),
    ("eevee_light_threshold", "EEVEE Advanced", FloatProperty(name="Light Threshold", default=0.01, min=0.0, precision=4), ["eevee.light_threshold"]),
    ("overscan_size", "EEVEE Advanced", FloatProperty(name="Overscan Size %", default=3.0, min=0.0, max=50.0), ["eevee.overscan_size"]),

    ("workbench_aa", "Workbench", EnumProperty(name="Anti-Aliasing", items=[(i, i, "") for i in ('OFF', 'FXAA', '5', '8', '11', '16', '32')], default='8'), ["display.render_aa"]),
    ("workbench_lighting", "Workbench", EnumProperty(name="Lighting", items=[(i, i.title(), "") for i in ('STUDIO', 'MATCAP', 'FLAT')]), ["display.shading.light"]),
    ("workbench_color", "Workbench", EnumProperty(name="Color", items=[(i, i.title(), "") for i in ('MATERIAL', 'OBJECT', 'RANDOM', 'VERTEX', 'TEXTURE', 'SINGLE')]), ["display.shading.color_type"]),
    ("workbench_single_color", "Workbench", FloatVectorProperty(name="Single Color", subtype='COLOR', size=3, default=(0.8, 0.8, 0.8), min=0.0, max=1.0), ["display.shading.single_color"]),
    ("workbench_cavity", "Workbench", BoolProperty(name="Cavity"), ["display.shading.show_cavity"]),
    ("workbench_cavity_type", "Workbench", EnumProperty(name="Cavity Type", items=[(i, i.title(), "") for i in ('WORLD', 'SCREEN', 'BOTH')]), ["display.shading.cavity_type"]),
    ("workbench_shadows", "Workbench", BoolProperty(name="Shadows"), ["display.shading.show_shadows"]),

    ("motion_blur", "Motion Blur & Simplify", BoolProperty(name="Motion Blur"), ["render.use_motion_blur"]),
    ("shutter", "Motion Blur & Simplify", FloatProperty(name="Shutter", default=0.5, min=0.0), ["render.motion_blur_shutter"]),
    ("motion_steps", "Motion Blur & Simplify", IntProperty(name="EEVEE Blur Steps", default=1, min=1), ["eevee.motion_blur_steps"]),
    ("simplify", "Motion Blur & Simplify", BoolProperty(name="Simplify"), ["render.use_simplify"]),
    ("max_subdiv", "Motion Blur & Simplify", IntProperty(name="Max Subdivision", default=6, min=0), ["render.simplify_subdivision_render"]),
    ("child_particles", "Motion Blur & Simplify", FloatProperty(name="Child Particles", default=1.0, min=0.0, max=1.0), ["render.simplify_child_particles_render"]),
    ("volume_resolution", "Motion Blur & Simplify", FloatProperty(name="Volume Resolution", default=1.0, min=0.0, max=1.0), ["render.simplify_volumes"]),
    ("texture_limit", "Motion Blur & Simplify", EnumProperty(name="Texture Limit", items=[(t, t, "") for t in ('OFF', '128', '256', '512', '1024', '2048', '4096', '8192')]), ["cycles.texture_limit_render"]),

    ("camera", "Scene", StringProperty(name="Camera"), None),
    ("world", "Scene", StringProperty(name="World"), None),
    ("view_layer", "Scene", StringProperty(name="View Layer", description="Render only this view layer"), None),
    ("transparent", "Scene", BoolProperty(name="Transparent Film"), ["render.film_transparent"]),
    ("compositor", "Scene", BoolProperty(name="Compositing", default=True), ["render.use_compositing"]),
    ("freestyle", "Scene", BoolProperty(name="Freestyle"), ["render.use_freestyle"]),

    ("stamp", "Metadata", BoolProperty(name="Burn Into Image", description="Burn the metadata into the image"), ["render.use_stamp"]),
    ("stamp_fields", "Metadata", EnumProperty(name="Fields", options={'ENUM_FLAG'}, default={'DATE', 'TIME', 'RENDER_TIME', 'FRAME', 'CAMERA', 'SCENE', 'FILENAME'},
                                              items=[(f, f.replace('_', ' ').title(), "") for f in STAMP_FIELDS]), None),
    ("stamp_note", "Metadata", StringProperty(name="Note", description="Empty = no note. Tokens are not expanded here"), None),
    ("stamp_font_size", "Metadata", IntProperty(name="Font Size", default=12, min=8, max=64), ["render.stamp_font_size"]),

    ("pixel_aspect", "Output & Misc", FloatVectorProperty(name="Pixel Aspect X / Y", size=2, default=(1.0, 1.0), min=1.0, max=200.0), ["render.pixel_aspect_x", "render.pixel_aspect_y"]),
    ("dither", "Output & Misc", FloatProperty(name="Dither", default=1.0, min=0.0), ["render.dither_intensity"]),
    ("hair_type", "Output & Misc", EnumProperty(name="Hair Shape", items=[(i, i.title(), "") for i in ('STRIP', 'STRAND', 'CYLINDER')]), ["render.hair_type"]),
    ("hair_subdiv", "Output & Misc", IntProperty(name="Hair Subdivisions", default=0, min=0, max=3), ["render.hair_subdiv"]),
    ("compositor_device", "Output & Misc", EnumProperty(name="Compositor Device", items=[('GPU', "GPU", ""), ('CPU', "CPU", "")]), ["render.compositor_device"]),
    ("compositor_precision", "Output & Misc", EnumProperty(name="Compositor Precision", items=[('AUTO', "Auto", ""), ('FULL', "Full", "")]), ["render.compositor_precision"]),
    ("sequencer", "Output & Misc", BoolProperty(name="Sequencer", default=True), ["render.use_sequencer"]),
    ("single_layer", "Output & Misc", BoolProperty(name="Single Layer"), ["render.use_single_layer"]),
    ("multiview", "Output & Misc", BoolProperty(name="Stereoscopy"), ["render.use_multiview"]),
    ("views_format", "Output & Misc", EnumProperty(name="Views Format", items=[('STEREO_3D', "Stereo 3D", ""), ('MULTIVIEW', "Multi-View", "")]), ["render.views_format"]),

    ("frame_range", "Frames & Size", IntVectorProperty(name="Frame Range", size=2, default=(1, 250)), ["frame_start", "frame_end"]),
    ("frame_step", "Frames & Size", IntProperty(name="Frame Step", default=1, min=1), ["frame_step"]),
    ("resolution", "Frames & Size", IntVectorProperty(name="Resolution", size=2, default=(1920, 1080), min=4), ["render.resolution_x", "render.resolution_y"]),
    ("resolution_percentage", "Frames & Size", IntProperty(name="Scale %", default=100, min=1, max=10000, soft_max=200), ["render.resolution_percentage"]),
    ("fps", "Frames & Size", IntProperty(name="FPS", default=24, min=1), ["render.fps"]),
    ("region", "Frames & Size", BoolProperty(name="Render Region"), ["render.use_border"]),
    ("region_box", "Frames & Size", FloatVectorProperty(name="Region (min X, min Y, max X, max Y)", size=4, default=(0.0, 0.0, 1.0, 1.0), min=0.0, max=1.0), ["render.border_min_x", "render.border_min_y", "render.border_max_x", "render.border_max_y"]),
    ("crop_region", "Frames & Size", BoolProperty(name="Crop to Region"), ["render.use_crop_to_border"]),

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
    ("white_balance", "Color", BoolProperty(name="White Balance"), ["view_settings.use_white_balance"]),
    ("wb_temperature", "Color", FloatProperty(name="Temperature", default=6500.0, min=1800.0, max=100000.0), ["view_settings.white_balance_temperature"]),
    ("wb_tint", "Color", FloatProperty(name="Tint", default=10.0, min=-500.0, max=500.0), ["view_settings.white_balance_tint"]),
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


class SBR_Visibility(bpy.types.PropertyGroup):
    enabled: BoolProperty(name="Enabled", default=True)
    kind: EnumProperty(name="Type", items=[('COLLECTION', "Collection", "", 'OUTLINER_COLLECTION', 0),
                                           ('OBJECT', "Object", "", 'OBJECT_DATA', 1)])
    target: StringProperty(name="Name")
    hide: BoolProperty(name="Hide", default=True, description="On = hidden in the render, off = forced visible")


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
    visibility: CollectionProperty(type=SBR_Visibility)
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
    visibility: CollectionProperty(type=SBR_Visibility)
    # runtime
    is_rendering: BoolProperty(options={'SKIP_SAVE'})
    is_paused: BoolProperty(options={'SKIP_SAVE'})
    message: StringProperty(options={'SKIP_SAVE'})
    done: IntProperty(options={'SKIP_SAVE'})
    total: IntProperty(options={'SKIP_SAVE'})
    eta: StringProperty(options={'SKIP_SAVE'})
    log_path: StringProperty(options={'SKIP_SAVE'})


classes = (SBR_Overrides, SBR_CustomOverride, SBR_Visibility, SBR_Job, SBR_Settings)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.sbr = PointerProperty(type=SBR_Settings)


def unregister():
    del bpy.types.WindowManager.sbr
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
