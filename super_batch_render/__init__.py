# SPDX-License-Identifier: GPL-3.0-or-later
# Super Batch Render : render queue with naming templates, global/per-job overrides and custom RNA overrides.
# Derived from RenderCue by Usama Bin Shahid (https://github.com/usamasq/RenderCue), GPL-3.0-or-later.
import bpy
from bpy.app.handlers import persistent

from . import core, ops, props, ui


@persistent
def _save_pre(*_args):
    core.save_to_text()


@persistent
def _load_post(*_args):
    core.load_from_text()


def _load_on_enable():
    try:
        if core.TEXT_BLOCK in bpy.data.texts:  # don't wipe a queue built since enabling
            core.load_from_text()
    except AttributeError:  # context not ready yet
        return 0.2
    return None


def register():
    props.register()
    ops.register()
    ui.register()
    bpy.app.handlers.save_pre.append(_save_pre)
    bpy.app.handlers.load_post.append(_load_post)
    bpy.app.timers.register(_load_on_enable, first_interval=0.1)


def unregister():
    for handlers, fn in ((bpy.app.handlers.save_pre, _save_pre), (bpy.app.handlers.load_post, _load_post)):
        if fn in handlers:
            handlers.remove(fn)
    ui.unregister()
    ops.unregister()
    props.unregister()
