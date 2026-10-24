# Super Batch Render

Render queue for Blender 4.2+ (tested on 5.2). Based on [RenderCue](https://github.com/usamasq/RenderCue)
by Usama Bin Shahid, GPL-3.0.

Panel: **Properties > Output > Super Batch Render**.

## Install (with automatic updates)
1. Blender: **Edit > Preferences > Get Extensions > Repositories (top right) > + > Add Remote Repository**.
2. URL: `https://raw.githubusercontent.com/adriendelmas/super-batch-render/main/repo/index.json`
   and tick **Check for Updates on Startup**.
3. Search "Super Batch Render" in Get Extensions and click Install.

Blender then offers each new version as an update.

## Release a new version
1. Bump `version` in `super_batch_render/blender_manifest.toml`.
2. Run `.\release.ps1` (builds `repo/super_batch_render-<version>.zip` and `repo/index.json` with Blender's CLI).
3. Commit and push. GitHub's raw cache can take ~5 minutes before Blender sees it.

## What it adds over RenderCue
- **Naming templates** for folder and file name, with tokens:
  `{blend} {scene} {job} {index} {camera} {viewlayer} {engine} {samples} {res} {width} {height} {format} {frames} {date} {time} {user} {version}`.
  Python format specs work (`{index:03d}`). `#` places the frame number and its padding.
  `{version}` takes the first unused `v001`, `v002`... so a re-render never overwrites.
  The resolved path of the active job is shown live under the job.
- **Global overrides** applied to every job; a job override wins over the global one.
- **About 140 typed overrides**, grouped like Blender's panels: Engine (device, CPU threads, tiling,
  persistent data), Sampling (adaptive, noise threshold, denoiser, seed, light tree), Light Paths (every
  bounce type, clamps, caustics), Cycles Advanced (path guiding, fast GI, volumes, dicing, culling, pixel
  filter, denoiser options, scrambling), EEVEE and EEVEE Advanced (ray tracing, shadows, GI, horizon scan,
  clamps, volumetrics, bokeh, overscan), Workbench (AA, lighting, color, cavity, shadows), Motion Blur &
  Simplify, Scene (camera, world, view layer, film, compositing, freestyle), Metadata (burn-in, fields,
  note), Frames & Size (range, step, resolution, fps, render region), Output & Misc (pixel aspect, dither,
  hair, compositor device, sequencer, single layer, stereo), File (format incl. EXR multilayer and video,
  depth, codec, overwrite, placeholders), Color (view transform, look, exposure, gamma, white balance).
- **Collections & objects per job**: hide or force-show collections and objects in the render,
  globally or per job.
- **Custom RNA path overrides** for anything else: `cycles.max_bounces = 4`,
  `bpy.data.objects["Tree"].hide_render = True`. Paths are checked before the render starts.
- **Every override is undone after each job**, so two jobs on the same scene don't leak settings
  into each other (RenderCue keeps the first job's settings).
- **Render modes per job**: animation (native, so video formats and skip-existing work),
  current frame, or a frame list (`1, 12, 40-60, 100-200x10`).
- **Quick add**: current scene, all scenes, one job per camera, one job per camera marker
  (each marker bound to a camera renders until the next marker).
- Enable/disable jobs, duplicate, copy overrides to all jobs.
- **Renders a snapshot** of the file as it is now (unsaved changes included), so you keep working.
- One failing job no longer stops the queue; per-job error and a `worker.log` you can open.
- Checks before rendering: missing camera/world/view layer, broken template, two jobs writing the same
  files, video format with stills, unresolvable custom paths.
- Export / import the queue as JSON.

Not kept from RenderCue: desktop notifications, webhooks, summary popup, 3D view and sequencer panels,
renumbering of stepped frames.

## How it renders
1. The queue is validated, then each job is compiled into a list of `(rna_path, value)` operations
   and a resolved output path (`manifest.json` in Blender's temp folder).
2. A copy of the current file is saved next to the .blend (`.<name>.blend.sbr_snapshot.blend`, deleted at the end).
3. `blender -b snapshot --python worker.py -- manifest status` applies each job's operations, renders,
   restores the values, and writes `status.json`, which the panel reads every second.
