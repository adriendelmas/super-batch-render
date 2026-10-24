# SPDX-License-Identifier: GPL-3.0-or-later
# Operators. Background process + status polling adapted from RenderCue by Usama Bin Shahid (GPL-3.0).
import atexit
import json
import os
import subprocess
import sys
import time

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from . import core

WORKER = os.path.join(os.path.dirname(__file__), "worker.py")
_run = {}  # proc, status, manifest, snapshot, start, stopped


def _kill():
    proc = _run.get("proc")
    if proc and proc.poll() is None:
        proc.kill()


atexit.register(_kill)


def _idle(cls, context):
    return not context.window_manager.sbr.is_rendering


def _redraw():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type in {'PROPERTIES', 'VIEW_3D'}:
                area.tag_redraw()


# ---------------------------------------------------------------- queue editing

class SBR_OT_add_job(bpy.types.Operator):
    """Add jobs to the queue"""
    bl_idname = "sbr.add_job"
    bl_label = "Add Job"
    bl_options = {'UNDO'}
    what: EnumProperty(items=[('CURRENT', "Current Scene", ""),
                              ('ALL', "All Scenes", "Every scene with a camera that is not queued yet"),
                              ('CAMERAS', "One Job per Camera", "Every camera of the current scene, camera overridden"),
                              ('MARKERS', "One Job per Camera Marker", "Each timeline marker bound to a camera renders its own range")])
    poll = classmethod(_idle)

    def execute(self, context):
        s = context.window_manager.sbr
        sc = context.scene

        def add(scene, name):
            job = s.jobs.add()
            job.scene, job.name = scene, core.unique_name(name, s.jobs)
            return job

        if self.what == 'CURRENT':
            add(sc, sc.name)
        elif self.what == 'ALL':
            queued = {j.scene for j in s.jobs}
            new = [scene for scene in bpy.data.scenes if scene.camera and scene not in queued]
            for scene in new:
                add(scene, scene.name)
            if not new:
                self.report({'WARNING'}, "No new scene with a camera")
                return {'CANCELLED'}
            self.report({'INFO'}, f"Added {len(new)} scenes")
        elif self.what == 'CAMERAS':
            for cam in sorted((o for o in sc.objects if o.type == 'CAMERA'), key=lambda o: o.name):
                job = add(sc, f"{sc.name}_{cam.name}")
                job.overrides.use_camera, job.overrides.camera = True, cam.name
        else:
            markers = sorted((m for m in sc.timeline_markers if m.camera), key=lambda m: m.frame)
            for m, nxt in zip(markers, markers[1:] + [None]):
                job = add(sc, f"{sc.name}_{m.name}")
                job.overrides.use_camera, job.overrides.camera = True, m.camera.name
                job.overrides.use_frame_range = True
                job.overrides.frame_range = (m.frame, nxt.frame - 1 if nxt else max(m.frame, sc.frame_end))
        s.active = len(s.jobs) - 1
        return {'FINISHED'}


class SBR_OT_job_action(bpy.types.Operator):
    """Remove, duplicate or move the active job"""
    bl_idname = "sbr.job_action"
    bl_label = "Job Action"
    bl_options = {'UNDO'}
    action: EnumProperty(items=[('REMOVE', "Remove", ""), ('DUPLICATE', "Duplicate", ""), ('UP', "Up", ""),
                                ('DOWN', "Down", ""), ('CLEAR', "Clear Queue", ""), ('RESET', "Reset Status", "")])
    poll = classmethod(_idle)

    def execute(self, context):
        s = context.window_manager.sbr
        i = s.active
        if self.action == 'CLEAR':
            s.jobs.clear()
        elif self.action == 'RESET':
            for job in s.jobs:
                job.status, job.done, job.error = 'PENDING', 0, ""
        elif not 0 <= i < len(s.jobs):
            return {'CANCELLED'}
        elif self.action == 'REMOVE':
            s.jobs.remove(i)
            s.active = min(i, len(s.jobs) - 1)
        elif self.action == 'DUPLICATE':
            new = s.jobs.add()
            core.from_dict(new, core.to_dict(s.jobs[i]))
            new.name = core.unique_name(s.jobs[i].name, s.jobs)
            s.jobs.move(len(s.jobs) - 1, i + 1)
            s.active = i + 1
        else:
            j = i - 1 if self.action == 'UP' else i + 1
            if 0 <= j < len(s.jobs):
                s.jobs.move(i, j)
                s.active = j
        return {'FINISHED'}


class SBR_OT_custom(bpy.types.Operator):
    """Add or remove a custom RNA path override"""
    bl_idname = "sbr.custom"
    bl_label = "Custom Override"
    bl_options = {'UNDO'}
    target: EnumProperty(items=[('GLOBAL', "Global", ""), ('JOB', "Job", "")])
    index: IntProperty(default=-1)

    def execute(self, context):
        s = context.window_manager.sbr
        owner = s if self.target == 'GLOBAL' else s.jobs[s.active]
        if self.index < 0:
            owner.custom.add()
        else:
            owner.custom.remove(self.index)
        return {'FINISHED'}


class SBR_OT_copy_overrides(bpy.types.Operator):
    """Copy the active job's overrides and custom overrides to every other job"""
    bl_idname = "sbr.copy_overrides"
    bl_label = "Copy Overrides to All Jobs"
    bl_options = {'UNDO'}
    poll = classmethod(_idle)

    def execute(self, context):
        s = context.window_manager.sbr
        src = s.jobs[s.active]
        data = core.to_dict(src)
        for job in s.jobs:
            if job != src:
                core.from_dict(job.overrides, data["overrides"])
                core.from_dict(job, {"custom": data["custom"]})
        return {'FINISHED'}


# ---------------------------------------------------------------- queue files

class SBR_OT_export(bpy.types.Operator, ExportHelper):
    """Save the queue (jobs, templates, overrides) to a JSON preset"""
    bl_idname = "sbr.export"
    bl_label = "Export Queue"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(core.to_dict(context.window_manager.sbr), f, indent=1)
        return {'FINISHED'}


class SBR_OT_import(bpy.types.Operator, ImportHelper):
    """Load a queue preset (replaces the current queue; scenes are matched by name)"""
    bl_idname = "sbr.import"
    bl_label = "Import Queue"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    poll = classmethod(_idle)

    def execute(self, context):
        s = context.window_manager.sbr
        with open(self.filepath, encoding="utf-8") as f:
            data = json.load(f)
        s.jobs.clear()
        s.custom.clear()
        core.from_dict(s, data)
        return {'FINISHED'}


# ---------------------------------------------------------------- render

class SBR_OT_validate(bpy.types.Operator):
    """Check the queue for problems (cameras, templates, duplicate outputs, custom paths)"""
    bl_idname = "sbr.validate"
    bl_label = "Check Queue"

    def execute(self, context):
        issues = core.validate(context.window_manager.sbr)
        for is_error, msg in issues:
            self.report({'ERROR' if is_error else 'WARNING'}, msg)
        if not issues:
            self.report({'INFO'}, "Queue OK")
        return {'FINISHED'}


class SBR_OT_render(bpy.types.Operator):
    """Render every enabled job in a background Blender. You can keep working, the current state of the file is rendered"""
    bl_idname = "sbr.render"
    bl_label = "Batch Render"
    poll = classmethod(_idle)

    def execute(self, context):
        s = context.window_manager.sbr
        errors = [m for e, m in core.validate(s) if e]
        if errors:
            for m in errors:
                self.report({'ERROR'}, m)
            return {'CANCELLED'}
        manifest = core.build_manifest(s)

        base = bpy.data.filepath
        run_dir = os.path.join(bpy.app.tempdir, "super_batch_render")
        os.makedirs(run_dir, exist_ok=True)
        if s.use_snapshot:
            # snapshot next to the .blend so relative texture/cache paths stay valid
            snapshot = os.path.join(os.path.dirname(base), f".{os.path.basename(base)}.sbr_snapshot.blend")
            bpy.ops.wm.save_as_mainfile(filepath=snapshot, copy=True)
        else:
            snapshot = base
            if bpy.data.is_dirty:
                self.report({'WARNING'}, "Unsaved changes are not rendered (Render Unsaved Changes is off)")
        manifest_path = os.path.join(run_dir, "manifest.json")
        status_path = os.path.join(run_dir, "status.json")
        log_path = os.path.join(run_dir, "worker.log")
        for p in (status_path, status_path + ".pause"):
            if os.path.exists(p):
                os.remove(p)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=1)

        for job in s.jobs:
            job.status, job.done, job.error, job.elapsed = 'PENDING', 0, "", 0.0
            job.total = 0
        for mj in manifest["jobs"]:
            s.jobs[mj["queue_index"]].total = mj["total"]
        s.is_rendering, s.is_paused, s.done, s.eta = True, False, 0, ""
        s.total = sum(j["total"] for j in manifest["jobs"])
        s.message, s.log_path = "Starting background Blender...", log_path

        log = open(log_path, "w", encoding="utf-8")
        cmd = [bpy.app.binary_path, "-b", snapshot, "--python", WORKER, "--", manifest_path, status_path]
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        _run.update(proc=subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, creationflags=flags),
                    log=log, status=status_path, manifest=manifest, snapshot=snapshot, is_copy=s.use_snapshot,
                    start=time.time(), stopped=False)
        bpy.app.timers.register(_poll, first_interval=1.0)
        return {'FINISHED'}


def _jobs_of_run(s):
    """(manifest job, queue job) pairs; skips jobs gone from the queue (another file opened meanwhile)."""
    return [(mj, s.jobs[mj["queue_index"]]) for mj in _run["manifest"]["jobs"]
            if mj["queue_index"] < len(s.jobs) and s.jobs[mj["queue_index"]].name == mj["name"]]


def _poll():
    s = core.settings()
    proc, manifest = _run["proc"], _run["manifest"]
    try:
        with open(_run["status"], encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = None
    if st:
        states = {mj["queue_index"]: js for mj, js in zip(manifest["jobs"], st["jobs"])}
        for mj, job in _jobs_of_run(s):
            js = states[mj["queue_index"]]
            job.status, job.done, job.error = js["state"], js["done"], js["error"]
            if js["start"]:
                job.elapsed = (js["end"] or time.time()) - js["start"]
        s.done = sum(js["done"] for js in st["jobs"])
        s.message = st["message"]
        s.is_paused = st["message"] == "Paused"
        elapsed = time.time() - _run["start"]
        if s.done:
            s.eta = time.strftime("%H:%M:%S", time.gmtime(elapsed / s.done * (s.total - s.done)))
    finished = proc.poll() is not None
    if finished:
        _run["log"].close()
        for _mj, job in _jobs_of_run(s):
            if job.status in {'PENDING', 'RENDERING'}:
                job.status = 'CANCELLED' if _run["stopped"] else 'FAILED'
                if not _run["stopped"]:
                    job.error = f"Background Blender exited with code {proc.returncode}, see worker.log"
        ok = sum(1 for js in st["jobs"] if js["state"] == 'COMPLETED') if st else 0
        s.message = f"Done: {ok}/{len(manifest['jobs'])} jobs in " \
                    f"{time.strftime('%H:%M:%S', time.gmtime(time.time() - _run['start']))}"
        s.is_rendering = s.is_paused = False
        if _run["is_copy"]:  # never delete the user's own file
            try:
                os.remove(_run["snapshot"])
            except OSError:
                pass
    _redraw()
    return None if finished else 1.0


class SBR_OT_stop(bpy.types.Operator):
    """Stop the background render (frames already written are kept)"""
    bl_idname = "sbr.stop"
    bl_label = "Stop"

    def execute(self, context):
        _run["stopped"] = True
        pause = _run.get("status", "") + ".pause"
        if os.path.exists(pause):
            os.remove(pause)
        _kill()
        return {'FINISHED'}


class SBR_OT_pause(bpy.types.Operator):
    """Pause / resume after the frame being rendered"""
    bl_idname = "sbr.pause"
    bl_label = "Pause"

    def execute(self, context):
        pause = _run["status"] + ".pause"
        if os.path.exists(pause):
            os.remove(pause)
            context.window_manager.sbr.message = "Resuming..."
        else:
            open(pause, "w").close()
            context.window_manager.sbr.message = "Pausing after this frame..."
        return {'FINISHED'}


class SBR_OT_open(bpy.types.Operator):
    """Open a folder in the file browser"""
    bl_idname = "sbr.open"
    bl_label = "Open Folder"
    what: EnumProperty(items=[('JOB', "Job Output", ""), ('LOG', "Worker Log", "")])

    def execute(self, context):
        s = context.window_manager.sbr
        if self.what == 'LOG':
            path = os.path.dirname(s.log_path)
        else:
            path = os.path.dirname(core.output_path(s, s.jobs[s.active], s.active, "v001"))
            # with {version} in the folder, show its parent
            while path and not os.path.isdir(path):
                path = os.path.dirname(path)
        if not path or not os.path.isdir(path):
            self.report({'WARNING'}, "Folder does not exist yet")
            return {'CANCELLED'}
        bpy.ops.wm.path_open(filepath=path)
        return {'FINISHED'}


classes = (SBR_OT_add_job, SBR_OT_job_action, SBR_OT_custom, SBR_OT_copy_overrides, SBR_OT_export,
           SBR_OT_import, SBR_OT_validate, SBR_OT_render, SBR_OT_stop, SBR_OT_pause, SBR_OT_open)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    _kill()
    if bpy.app.timers.is_registered(_poll):
        bpy.app.timers.unregister(_poll)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
