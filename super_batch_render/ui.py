# SPDX-License-Identifier: GPL-3.0-or-later
# Panels in Properties > Output. Layout inspired by RenderCue by Usama Bin Shahid (GPL-3.0).
import bpy

from . import core
from .props import SECTIONS, SPECS, STATUS_ITEMS

STATUS_ICON = {i[0]: i[3] for i in STATUS_ITEMS}


class SBR_UL_jobs(bpy.types.UIList):
    def draw_item(self, context, layout, data, job, icon, active_data, active_prop, index):
        row = layout.row(align=True)
        row.prop(job, "enabled", text="")
        sub = row.row()
        sub.active = job.enabled
        sub.prop(job, "name", text="", emboss=False, icon=STATUS_ICON[job.status])
        sub.label(text=job.scene.name if job.scene else "no scene")
        n = sum(getattr(job.overrides, "use_" + k) for k, *_ in SPECS) + sum(c.enabled for c in job.custom)
        if n:
            sub.label(text=f"{n} ovr", icon='MODIFIER')
        if job.total:
            sub.label(text=f"{job.done}/{job.total}")


class OutputPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"


class SBR_PT_main(OutputPanel, bpy.types.Panel):
    bl_label = "Super Batch Render"

    def draw(self, context):
        layout = self.layout
        s = context.window_manager.sbr
        if s.is_rendering:
            row = layout.row(align=True)
            row.operator("sbr.pause", text="Resume" if s.is_paused else "Pause",
                         icon='PLAY' if s.is_paused else 'PAUSE')
            row.operator("sbr.stop", icon='CANCEL')
            layout.progress(factor=s.done / s.total if s.total else 0, text=f"{s.done}/{s.total}  ETA {s.eta or '--'}")
        else:
            row = layout.row(align=True)
            row.scale_y = 1.4
            row.operator("sbr.render", icon='RENDER_ANIMATION')
            row.operator("sbr.validate", text="", icon='CHECKMARK')
        if s.message:
            row = layout.row()
            row.label(text=s.message)
            if s.log_path:
                row.operator("sbr.open", text="", icon='TEXT').what = 'LOG'

        row = layout.row()
        row.template_list("SBR_UL_jobs", "", s, "jobs", s, "active", rows=5)
        col = row.column(align=True)
        col.operator_menu_enum("sbr.add_job", "what", text="", icon='ADD')
        col.operator("sbr.job_action", text="", icon='REMOVE').action = 'REMOVE'
        col.operator("sbr.job_action", text="", icon='DUPLICATE').action = 'DUPLICATE'
        col.separator()
        col.operator("sbr.job_action", text="", icon='TRIA_UP').action = 'UP'
        col.operator("sbr.job_action", text="", icon='TRIA_DOWN').action = 'DOWN'
        col.separator()
        col.menu("SBR_MT_queue", text="", icon='DOWNARROW_HLT')


class SBR_MT_queue(bpy.types.Menu):
    bl_label = "Queue"

    def draw(self, context):
        layout = self.layout
        layout.operator("sbr.export", icon='EXPORT')
        layout.operator("sbr.import", icon='IMPORT')
        layout.separator()
        layout.operator("sbr.copy_overrides", icon='COPYDOWN')
        layout.operator("sbr.job_action", text="Reset Status", icon='LOOP_BACK').action = 'RESET'
        layout.operator("sbr.job_action", text="Clear Queue", icon='TRASH').action = 'CLEAR'


def draw_templates(layout, owner):
    layout.prop(owner, "output_dir")
    layout.prop(owner, "file_name")


def draw_tokens(layout):
    header, body = layout.panel("sbr_tokens", default_closed=True)
    header.label(text="Tokens", icon='INFO')
    if body:
        col = body.column(align=True)
        for k, desc in core.TOKENS.items():
            col.label(text=f"{{{k}}}  {desc}")
        col.label(text="Python format specs work: {index:03d}, {camera:.8}")
        col.label(text="'#' sets the frame position and padding, else padding is appended")


def draw_overrides(layout, ov, prefix, scene=None, fallback=None):
    for section in SECTIONS:
        keys = [k for k, sec, *_ in SPECS if sec == section]
        active = sum(getattr(ov, "use_" + k) for k in keys)
        header, body = layout.panel(f"sbr_{prefix}_{section}", default_closed=True)
        header.label(text=f"{section}  ({active})" if active else section)
        if not body:
            continue
        col = body.column(align=True)
        for key in keys:
            row = col.row(align=True)
            row.prop(ov, "use_" + key, text="")
            sub = row.row(align=True)
            sub.active = getattr(ov, "use_" + key)
            if key == "camera":
                sub.prop_search(ov, key, bpy.data, "objects", icon='CAMERA_DATA')
            elif key == "world":
                sub.prop_search(ov, key, bpy.data, "worlds")
            elif key == "view_layer" and scene:
                sub.prop_search(ov, key, scene, "view_layers")
            else:
                sub.prop(ov, key)
            if fallback and not getattr(ov, "use_" + key) and getattr(fallback, "use_" + key):
                row.label(text="", icon='WORLD')  # global override applies


def draw_custom(layout, owner, target):
    header, body = layout.panel(f"sbr_custom_{target}", default_closed=not owner.custom)
    header.label(text=f"Custom RNA Paths  ({len(owner.custom)})" if owner.custom else "Custom RNA Paths")
    if not body:
        return
    for i, c in enumerate(owner.custom):
        row = body.row(align=True)
        row.prop(c, "enabled", text="")
        row.prop(c, "path", text="")
        row.prop(c, "value", text="")
        op = row.operator("sbr.custom", text="", icon='X')
        op.target, op.index = target, i
    op = body.operator("sbr.custom", text="Add Path", icon='ADD')
    op.target, op.index = target, -1


class SBR_PT_output(OutputPanel, bpy.types.Panel):
    bl_label = "Naming & Output"
    bl_parent_id = "SBR_PT_main"

    def draw(self, context):
        s = context.window_manager.sbr
        layout = self.layout
        layout.use_property_split = True
        draw_templates(layout, s)
        layout.prop(s, "frame_padding")
        layout.prop(s, "use_snapshot")
        draw_tokens(layout)


class SBR_PT_global(OutputPanel, bpy.types.Panel):
    bl_label = "Global Overrides"
    bl_parent_id = "SBR_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        s = context.window_manager.sbr
        self.layout.label(text="Applied to every job, a job override wins", icon='WORLD')
        draw_overrides(self.layout, s.overrides, "global")
        draw_custom(self.layout, s, 'GLOBAL')


class SBR_PT_job(OutputPanel, bpy.types.Panel):
    bl_label = "Active Job"
    bl_parent_id = "SBR_PT_main"

    @classmethod
    def poll(cls, context):
        s = context.window_manager.sbr
        return 0 <= s.active < len(s.jobs)

    def draw(self, context):
        s = context.window_manager.sbr
        job = s.jobs[s.active]
        layout = self.layout
        col = layout.column()
        col.use_property_split = True
        col.prop(job, "scene")
        col.prop(job, "mode")
        if job.mode == 'FRAMES':
            col.prop(job, "frames")
        col.prop(job, "use_output")
        if job.use_output:
            draw_templates(col, job)
        if job.scene:
            try:
                path = core.output_path(s, job, s.active)
            except (ValueError, IndexError, KeyError) as e:
                path = f"template error: {e}"
            box = layout.box()
            box.label(text=path, icon='FILE_FOLDER')
            box.operator("sbr.open", text="Open Folder", icon='FOLDER_REDIRECT').what = 'JOB'
        if job.error:
            layout.label(text=job.error, icon='ERROR')
        draw_overrides(layout, job.overrides, "job", job.scene, s.overrides)
        draw_custom(layout, job, 'JOB')


classes = (SBR_UL_jobs, SBR_MT_queue, SBR_PT_main, SBR_PT_output, SBR_PT_global, SBR_PT_job)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
