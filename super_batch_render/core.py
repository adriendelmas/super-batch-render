# SPDX-License-Identifier: GPL-3.0-or-later
# Naming tokens, override compilation, validation and queue persistence.
import ast
import getpass
import glob
import json
import os
import re
from datetime import datetime

import bpy

from .props import SPECS

TEXT_BLOCK = ".super_batch_render.json"
RNA_PATH = re.compile(r'^(?:(.*)\.)?([A-Za-z_]\w*)(?:\[(\d+)\])?$')
BAD_CHARS = re.compile(r'[<>:"/\\|?*]')
MEDIA = {'OPEN_EXR_MULTILAYER': 'MULTI_LAYER_IMAGE', 'FFMPEG': 'VIDEO'}
ENGINE_NAMES = {'BLENDER_EEVEE': "EEVEE", 'BLENDER_WORKBENCH': "Workbench", 'CYCLES': "Cycles"}
TOKENS = {
    "blend": "blend file name", "scene": "scene name", "job": "job name", "index": "job number (1, 2...; {index:02d})",
    "camera": "camera name", "viewlayer": "view layer", "engine": "Cycles, EEVEE...", "samples": "sample count",
    "res": "1920x1080 (after scale %)", "width": "final width", "height": "final height", "format": "file format",
    "frames": "first-last frame", "date": "YYYY-MM-DD", "time": "HHMM", "user": "OS user name",
    "version": "v001, v002... first unused",
}


def settings():
    return bpy.context.window_manager.sbr


# ---------------------------------------------------------------- effective values

def eff(s, job, key, default):
    """Value of an override: job wins over global, else the scene default."""
    for ov in (job.overrides, s.overrides):
        if getattr(ov, "use_" + key):
            return getattr(ov, key)
    return default


def frame_range(s, job):
    sc = job.scene
    if job.mode == 'STILL':
        return [sc.frame_current]
    if job.mode == 'FRAMES':
        return parse_frames(job.frames)
    start, end = eff(s, job, "frame_range", (sc.frame_start, sc.frame_end))
    return list(range(start, end + 1, eff(s, job, "frame_step", sc.frame_step)))


def parse_frames(text):
    """'1, 5, 10-14, 20-40x10' -> [1, 5, 10, 11, 12, 13, 14, 20, 30, 40]"""
    frames = []
    for part in filter(None, (p.strip() for p in text.replace(";", ",").split(","))):
        m = re.fullmatch(r'(-?\d+)(?:\s*-\s*(-?\d+)(?:\s*x\s*(\d+))?)?', part)
        if not m:
            raise ValueError(f"bad frame list item '{part}'")
        a, b, step = m.groups()
        frames += [int(a)] if b is None else list(range(int(a), int(b) + 1, int(step or 1)))
    return sorted(set(frames))


def tokens(s, job, index):
    sc = job.scene
    r = sc.render
    engine = eff(s, job, "engine", r.engine)
    cam = eff(s, job, "camera", sc.camera.name if sc.camera else "")
    rx, ry = eff(s, job, "resolution", (r.resolution_x, r.resolution_y))
    pct = eff(s, job, "resolution_percentage", r.resolution_percentage)
    w, h = rx * pct // 100, ry * pct // 100
    if engine == 'CYCLES':
        samples = getattr(getattr(sc, "cycles", None), "samples", 0)
    else:
        samples = sc.eevee.taa_render_samples
    samples = eff(s, job, "samples", samples)
    layer = eff(s, job, "view_layer", next((v.name for v in sc.view_layers if v.use), ""))
    try:
        frames = frame_range(s, job)
        span = f"{frames[0]}-{frames[-1]}" if frames else ""
    except ValueError:
        span = ""
    now = datetime.now()
    values = dict(blend=os.path.splitext(os.path.basename(bpy.data.filepath))[0] or "untitled",
                  scene=sc.name, job=job.name, index=index + 1, camera=cam, viewlayer=layer,
                  engine=ENGINE_NAMES.get(engine, engine), samples=samples, res=f"{w}x{h}", width=w, height=h,
                  format=eff(s, job, "file_format", r.image_settings.file_format).lower(), frames=span,
                  date=now.strftime("%Y-%m-%d"), time=now.strftime("%H%M"), user=getpass.getuser())
    return {k: BAD_CHARS.sub("_", v) if isinstance(v, str) else v for k, v in values.items()}


class _Keep(dict):
    def __missing__(self, key):  # unknown tokens stay visible instead of crashing
        return "{" + key + "}"


def output_path(s, job, index, version="v###"):
    """Absolute output path, '#' marks the frame number. Raises ValueError on a broken template."""
    tok = _Keep(tokens(s, job, index), version=version)
    folder, name = (job.output_dir, job.file_name) if job.use_output else (s.output_dir, s.file_name)
    path = os.path.join(bpy.path.abspath(folder.format_map(tok)), name.format_map(tok))
    if "#" not in os.path.basename(path):
        path += "#" * s.frame_padding
    return os.path.normpath(path)


def next_version(s, job, index):
    folder, name = (job.output_dir, job.file_name) if job.use_output else (s.output_dir, s.file_name)
    if "{version}" not in folder + name:
        return "v001"
    for n in range(1, 1000):
        v = f"v{n:03d}"
        if not glob.glob(glob.escape(output_path(s, job, index, v).split("#")[0]) + "*"):
            return v
    return "v999"


# ---------------------------------------------------------------- overrides -> operations

def parse_value(text):
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text  # bare words like AgX are taken as strings


def custom_ops(s, job):
    ops = []
    for c in list(s.custom) + list(job.custom):  # job entries last: they win
        if c.enabled and c.path.strip():
            path = c.path.strip()
            root = "data" if path.startswith("bpy.data.") else "scene"
            ops.append([root, path[len("bpy.data."):] if root == "data" else path, parse_value(c.value)])
    return ops


def compile_ops(s, job):
    """Effective overrides of a job as [root, rna_path, value] operations for the worker."""
    sc = job.scene
    ops = []
    for key, _section, _prop, paths in SPECS:
        ov = next((o for o in (job.overrides, s.overrides) if getattr(o, "use_" + key)), None)
        if ov is None:
            continue
        val = getattr(ov, key)
        if key == "camera":
            ops.append(["scene", "camera", {"id": "objects", "name": val}])
        elif key == "world":
            ops.append(["scene", "world", {"id": "worlds", "name": val}])
        elif key == "view_layer":
            ops += [["scene", f'view_layers["{bpy.utils.escape_identifier(vl.name)}"].use', vl.name == val]
                    for vl in sc.view_layers]
        elif key == "file_format":
            ops += [["scene", "render.image_settings.media_type", MEDIA.get(val, 'IMAGE')],
                    ["scene", "render.image_settings.file_format", val]]
        else:
            vals = list(val) if len(paths) > 1 and hasattr(val, "__len__") and not isinstance(val, str) else [val] * len(paths)
            ops += [["scene", p, v] for p, v in zip(paths, vals)]
    return ops + custom_ops(s, job)


def check_op(scene, root, path):
    """Error text if an RNA path cannot be set, else ''."""
    m = RNA_PATH.match(path)
    if not m:
        return f"invalid path '{path}'"
    owner_path, attr, _index = m.groups()
    try:
        base = bpy.data if root == "data" else scene
        owner = base.path_resolve(owner_path) if owner_path else base
    except ValueError:
        return f"'{owner_path}' not found"
    return "" if hasattr(owner, attr) else f"'{type(owner).__name__}' has no '{attr}'"


# ---------------------------------------------------------------- validation & manifest

def validate(s):
    """[(is_error, message)] for the enabled jobs."""
    issues = []
    seen = {}
    jobs = [(i, j) for i, j in enumerate(s.jobs) if j.enabled]
    if not jobs:
        issues.append((True, "No enabled job"))
    if not bpy.data.filepath:
        issues.append((True, "Save the .blend file once before rendering"))
    for i, job in jobs:
        tag = f"[{job.name}]"
        if job.scene is None:
            issues.append((True, f"{tag} no scene"))
            continue
        sc = job.scene
        cam = eff(s, job, "camera", sc.camera.name if sc.camera else "")
        if not cam:
            issues.append((True, f"{tag} no camera"))
        elif bpy.data.objects.get(cam) is None or bpy.data.objects[cam].type != 'CAMERA':
            issues.append((True, f"{tag} camera '{cam}' not found"))
        world = eff(s, job, "world", None)
        if world is not None and world not in bpy.data.worlds:
            issues.append((True, f"{tag} world '{world}' not found"))
        layer = eff(s, job, "view_layer", None)
        if layer is not None and layer not in sc.view_layers:
            issues.append((True, f"{tag} view layer '{layer}' not in scene"))
        try:
            frames = frame_range(s, job)
            if not frames:
                issues.append((True, f"{tag} no frame to render"))
        except ValueError as e:
            issues.append((True, f"{tag} {e}"))
        fmt = eff(s, job, "file_format", sc.render.image_settings.file_format)
        if fmt == 'FFMPEG' and job.mode != 'ANIM':
            issues.append((True, f"{tag} video format needs Animation mode"))
        try:
            path = output_path(s, job, i)
        except (ValueError, IndexError, KeyError) as e:
            issues.append((True, f"{tag} bad name template: {e}"))
            continue
        if path in seen:
            issues.append((True, f"{tag} same output as [{seen[path]}], add {{job}} or {{camera}} to the name"))
        seen[path] = job.name
        for root, p, _v in custom_ops(s, job):
            err = check_op(sc, root, p)
            if err:
                issues.append((True, f"{tag} custom override: {err}"))
    return issues


def build_manifest(s):
    jobs = []
    for i, job in enumerate(s.jobs):
        if not job.enabled:
            continue
        frames = frame_range(s, job)
        jobs.append({"queue_index": i, "name": job.name, "scene": job.scene.name,
                     "mode": 'ANIM' if job.mode == 'ANIM' else 'FRAMES', "frames": frames, "total": len(frames),
                     "filepath": output_path(s, job, i, next_version(s, job, i)), "ops": compile_ops(s, job)})
    return {"jobs": jobs}


# ---------------------------------------------------------------- persistence (generic RNA <-> dict)

def to_dict(pg):
    d = {}
    for p in pg.bl_rna.properties:
        k = p.identifier
        if k == "rna_type" or p.is_skip_save or (p.is_readonly and p.type not in {'POINTER', 'COLLECTION'}):
            continue
        v = getattr(pg, k)
        if p.type == 'POINTER':
            d[k] = to_dict(v) if isinstance(v, bpy.types.PropertyGroup) else (v.name if v else None)
        elif p.type == 'COLLECTION':
            d[k] = [to_dict(item) for item in v]
        elif getattr(p, "is_array", False):
            d[k] = list(v)
        elif p.type == 'ENUM' and p.is_enum_flag:
            d[k] = sorted(v)
        else:
            d[k] = v
    return d


def from_dict(pg, d):
    for k, v in d.items():
        p = pg.bl_rna.properties.get(k)
        if p is None:
            continue
        try:
            if p.type == 'POINTER':
                if isinstance(v, dict):
                    from_dict(getattr(pg, k), v)
                else:
                    setattr(pg, k, bpy.data.scenes.get(v) if v else None)  # only ID pointer is Job.scene
            elif p.type == 'COLLECTION':
                coll = getattr(pg, k)
                coll.clear()
                for item in v:
                    from_dict(coll.add(), item)
            else:
                setattr(pg, k, set(v) if p.type == 'ENUM' and p.is_enum_flag else v)
        except (TypeError, ValueError, AttributeError):
            pass  # value from another version or an engine that is not loaded: keep the default


def save_to_text():
    data = json.dumps(to_dict(settings()), indent=1)
    text = bpy.data.texts.get(TEXT_BLOCK) or bpy.data.texts.new(TEXT_BLOCK)
    text.from_string(data)


def load_from_text():
    s = settings()
    text = bpy.data.texts.get(TEXT_BLOCK)
    s.jobs.clear()
    s.custom.clear()
    for key, *_rest in SPECS:
        setattr(s.overrides, "use_" + key, False)
    if text:
        try:
            from_dict(s, json.loads(text.as_string()))
        except json.JSONDecodeError:
            pass


def unique_name(name, jobs):
    names = {j.name for j in jobs}
    out, n = name, 1
    while out in names:
        out, n = f"{name}.{n:03d}", n + 1
    return out
