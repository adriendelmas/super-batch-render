# SPDX-License-Identifier: GPL-3.0-or-later
# Background render worker, run as:
#   blender -b snapshot.blend --python worker.py -- manifest.json status.json [part parts pause_file]
# With `part parts`, this worker is one of `parts` Blenders (one per GPU) and renders every
# `parts`-th frame starting at the `part`-th: together they cover each frame exactly once.
# Standalone on purpose (bpy + stdlib only): the main process compiles every
# override into plain (root, rna_path, value) operations, this script only applies them.
# Architecture (manifest + status file + pause signal) adapted from RenderCue by Usama Bin Shahid.

import bpy
import json
import os
import re
import sys
import time
import traceback

ARGS = sys.argv[sys.argv.index("--") + 1:]
MANIFEST_PATH, STATUS_PATH = ARGS[:2]
PART, PARTS = (int(ARGS[2]), int(ARGS[3])) if len(ARGS) > 3 else (0, 1)
PAUSE_PATH = ARGS[4] if len(ARGS) > 4 else STATUS_PATH + ".pause"
RNA_PATH = re.compile(r'^(?:(.*)\.)?([A-Za-z_]\w*)(?:\[(\d+)\])?$')

with open(MANIFEST_PATH, encoding="utf-8") as f:
    MANIFEST = json.load(f)

state = {
    "current": -1,
    "message": "Starting",
    "finished": False,
    "jobs": [{"state": "PENDING", "done": 0, "total": j["total"], "error": "", "start": 0.0, "end": 0.0}
             for j in MANIFEST["jobs"]],
}


def write_status():
    tmp = STATUS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, STATUS_PATH)


def log(msg):
    print(f"[Super Batch Render] {msg}", flush=True)


def set_path(scene, root, path, value, undo):
    """Set one RNA property and remember its old value in `undo`."""
    base = bpy.data if root == "data" else scene
    owner_path, attr, index = RNA_PATH.match(path).groups()
    owner = base.path_resolve(owner_path) if owner_path else base
    if isinstance(value, dict):  # ID reference by name
        value = getattr(bpy.data, value["id"])[value["name"]]
    if index is None:
        undo.append((owner, attr, None, getattr(owner, attr)))
        setattr(owner, attr, value)
    else:
        array = getattr(owner, attr)
        undo.append((owner, attr, int(index), array[int(index)]))
        array[int(index)] = value


def restore(undo):
    """Put back every value a job changed, so the next job starts from the file state."""
    for owner, attr, index, old in reversed(undo):
        try:
            if index is None:
                setattr(owner, attr, old)
            else:
                getattr(owner, attr)[index] = old
        except Exception:
            pass


def on_render_pre(*_args):
    if os.path.exists(PAUSE_PATH):
        state["message"] = "Paused"
        write_status()
        while os.path.exists(PAUSE_PATH):
            time.sleep(1)


def on_render_post(scene, *_args):
    job = state["jobs"][state["current"]]
    job["done"] += 1
    state["message"] = f"{MANIFEST['jobs'][state['current']]['name']} - frame {scene.frame_current}"
    write_status()


def frame_filepath(template, frame):
    # write_still does not expand '#', so do it the way Blender does for animations
    return re.sub(r"#+", lambda m: str(frame).zfill(len(m.group(0))), template)


def run_job(job):
    scene = bpy.data.scenes.get(job["scene"])
    if scene is None:
        raise RuntimeError(f"Scene '{job['scene']}' not found")
    undo = []
    try:
        for root, path, value in job["ops"]:
            try:
                set_path(scene, root, path, value, undo)
            except Exception as e:
                log(f"WARNING override '{path}' = {value!r} skipped: {e}")
        os.makedirs(os.path.dirname(job["filepath"]), exist_ok=True)
        if job["mode"] == "ANIM":
            set_path(scene, "scene", "render.filepath", job["filepath"], undo)
            if PARTS > 1 and getattr(scene.render, "is_movie_format", False):
                if PART:
                    return  # one movie file cannot be shared: the first Blender renders it alone
            elif PARTS > 1:
                start, step = scene.frame_start + PART * scene.frame_step, scene.frame_step
                if start > scene.frame_end:
                    return  # fewer frames than Blenders
                set_path(scene, "scene", "frame_start", start, undo)
                set_path(scene, "scene", "frame_step", step * PARTS, undo)
            bpy.ops.render.render(animation=True, scene=scene.name)
        else:
            for frame in job["frames"][PART::PARTS]:
                scene.frame_set(frame)
                set_path(scene, "scene", "render.filepath", frame_filepath(job["filepath"], frame), undo)
                bpy.ops.render.render(write_still=True, scene=scene.name)
    finally:
        restore(undo)


def use_own_gpu():
    """Per-GPU worker: enable the one GPU this process sees. The preferences on disk can be older than
    the session that started the render (devices ticked but not saved), which silently meant CPU rendering."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = MANIFEST["compute"]
    for device in prefs.get_devices_for_type(MANIFEST["compute"]):
        device.use = device.type != 'CPU'
        log(f"Device {device.name}: {'on' if device.use else 'off'}")


def main():
    if PARTS > 1 and MANIFEST.get("compute"):
        use_own_gpu()
    bpy.app.handlers.render_pre.append(on_render_pre)
    bpy.app.handlers.render_post.append(on_render_post)
    for i, job in enumerate(MANIFEST["jobs"]):
        js = state["jobs"][i]
        state["current"] = i
        state["message"] = f"Starting {job['name']}"
        js["state"] = "RENDERING"
        js["start"] = time.time()
        write_status()
        log(f"Job {i + 1}/{len(MANIFEST['jobs'])}: {job['name']} -> {job['filepath']}")
        try:
            run_job(job)
            js["state"] = "COMPLETED"
        except Exception as e:
            js["state"] = "FAILED"
            js["error"] = str(e)
            log(traceback.format_exc())
        js["end"] = time.time()
        write_status()
    state["finished"] = True
    state["message"] = "All jobs done"
    write_status()


main()
