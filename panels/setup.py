#
#   BlendexDMX > Panels > Setup
#
#   - Setup a DMX collection and data structure to store the DMX parameters
#   - Change background color
#   - Create/Update a Box that fits the whole scene with a Volume Scatter
#   shader, and control it's visibility and density (for simulating haze)
#
#   http://www.github.com/open-stage/BlenderDMX
#

import bpy
import os
import shutil
from bpy.types import Operator, Panel
from dmx.material import getVolumeScatterMaterial
from dmx.util import getSceneRect
from dmx.gdtf import *
import dmx.panels.profiles as Profiles
import dmx.blender_utils as blender_utils
from dmx import bl_info as application_info
from bpy.props import (StringProperty, CollectionProperty)
from dmx.logging import DMX_Log

from dmx.i18n import DMX_Lang
_ = DMX_Lang._
# Operators #

class DMX_OT_Setup_NewShow(Operator):
    bl_label = _("DMX > Setup > New Show")
    bl_description = _("Clear any existing DMX data and create a new show.")
    bl_idname = "dmx.new_show"
    bl_options = {'UNDO'}

    def execute(self, context):
        # DMX setup
        context.scene.dmx.new()

        return {'FINISHED'}

class DMX_OT_Fixture_Set_Cycles_Beams_Size_Small(Operator):
    bl_label = _("Beam diameter small")
    bl_idname = "dmx.fixture_set_cycles_beam_size_small"

    def execute(self, context):
        dmx = context.scene.dmx
        selected = dmx.selectedFixtures()
        for fixture in selected:
            for light in fixture.lights:
                light_obj = light.object
                light_obj.data["beam_radius_pin_sized_for_gobos"] = True
                fixture.dmx_cache_dirty = True
                fixture.render(skip_cache=True)
        return {'FINISHED'}

class DMX_OT_Fixture_Set_Cycles_Beams_Size_Normal(Operator):
    bl_label = _("Beam diameter normal")
    bl_idname = "dmx.fixture_set_cycles_beam_size_normal"

    def execute(self, context):
        dmx = context.scene.dmx
        selected = dmx.selectedFixtures()
        for fixture in selected:
            for light in fixture.lights:
                light_obj = light.object
                light_obj.data["beam_radius_pin_sized_for_gobos"] = False
                fixture.dmx_cache_dirty = True
                fixture.render(skip_cache=True)
        return {'FINISHED'}

class DMX_OT_Setup_Volume_Create(Operator):
    bl_label = _("DMX > Setup > Create/Update Volume Box")
    bl_description = _("Create/Update a Box on the scene bounds with a Volume Scatter shader")
    bl_idname = "dmx.create_volume"
    bl_options = {'UNDO'}

    def execute(self, context):
        dmx = context.scene.dmx
        # Get scene bounds
        min, max = getSceneRect()
        pos = [min[i]+(max[i]-min[i])/2 for i in range(3)]
        scale = [max[i]-min[i] for i in range(3)]
        # Remove old DMX collection if present
        if ("DMX_Volume" not in bpy.data.objects):
            bpy.ops.mesh.primitive_cube_add(size=1.0)
            dmx.volume = bpy.context.selected_objects[0]
            dmx.volume.name = "DMX_Volume"
            dmx.volume.display_type = 'WIRE'
            material = getVolumeScatterMaterial()
            dmx.volume.data.materials.append(material)
        else:
            dmx.volume = bpy.data.objects["DMX_Volume"]

        if len(dmx.volume.data.materials):
            dmx.volume_nodetree = dmx.volume.data.materials[0].node_tree
        else:
            material = getVolumeScatterMaterial()
            dmx.volume.data.materials.append(material)
            dmx.volume_nodetree = dmx.volume.data.materials[0].node_tree

        old_collections = dmx.volume.users_collection
        if (dmx.collection not in old_collections):
            dmx.collection.objects.link(dmx.volume)
            for collection in old_collections:
                collection.objects.unlink(dmx.volume)

        dmx.volume.location = pos
        dmx.volume.scale = scale

        return {'FINISHED'}

class DMX_PT_Setup_Volume(Panel):
    bl_label = _("Beam Volume")
    bl_idname = "DMX_PT_Setup_Volume"
    bl_parent_id = "DMX_PT_Setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DMX"
    bl_context = "objectmode"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        dmx = context.scene.dmx

        box = layout.column().box()
        box.prop(context.scene.dmx, 'volume_preview')
        box.prop(context.scene.dmx, 'disable_overlays')

        box = layout.column().box()
        box.operator("dmx.create_volume", text = (_("Update Volume Box") if dmx.volume else _("Create Volume Box")), icon='MESH_CUBE')

        row = box.row()
        row.prop(context.scene.dmx, 'volume_enabled')
        row.enabled = (dmx.volume != None)

        row_den = box.row()
        row_den.prop(context.scene.dmx, 'volume_density')
        row_scale = box.row()
        row_scale.prop(context.scene.dmx, 'volume_noise_scale')
        row_den.enabled = row_scale.enabled = (dmx.volume != None)

        selected = dmx.selectedFixtures()
        enabled = len(selected) > 0
        box = layout.column().box()
        row = box.row()
        col1 = row.column()
        col1.prop(context.scene.dmx, "reduced_beam_diameter_in_cycles")
        col2 = row.column()
        col2.operator('wm.url_open', text="", icon="HELP").url="https://blenderdmx.eu/docs/setup/#beam-lens-diameter-in-cycles"

        if bpy.context.scene.dmx.reduced_beam_diameter_in_cycles == "CUSTOM":
            row0 = box.row()
            row1 = box.row()
            row2 = box.row()
            row0.label(text = _("Set on selected fixtures"))
            row1.operator("dmx.fixture_set_cycles_beam_size_normal", icon="CONE")
            row2.operator("dmx.fixture_set_cycles_beam_size_small", icon="LIGHT_SPOT")
            row0.enabled = row1.enabled = row2.enabled = enabled
        box = layout.column().box()
        row = box.row()
        col1 = row.column()
        col1.prop(context.window_manager.dmx, 'collections_list')
        col2 = row.column()
        col2.operator('wm.url_open', text="", icon="HELP").url="https://blenderdmx.eu/docs/laser/"


class DMX_PT_Setup_Viewport(Panel):
    bl_label = _("Viewport")
    bl_idname = "DMX_PT_Setup_Viewport"
    bl_parent_id = "DMX_PT_Setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DMX"
    bl_context = "objectmode"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        dmx = context.scene.dmx
        row = layout.row()
        row.label(text = _("Background Color"))
        row = layout.row()
        row.prop(context.scene.dmx,'background_color',text='')
        row = layout.row()
        row.prop(context.window_manager.dmx, 'pause_render')
        row = layout.row()
        row.prop(context.scene.dmx,'display_2D')
        row = layout.row()
        row.prop(context.scene.dmx,'display_pigtails')
        row = layout.row()
        row.prop(context.scene.dmx,'select_geometries')

class DMX_PT_Setup_Extras(Panel):
    bl_label = _("Extras")
    bl_idname = "DMX_PT_Setup_Extras"
    bl_parent_id = "DMX_PT_Setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DMX"
    bl_context = "objectmode"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        dmx = context.scene.dmx
        layout.operator("dmx.check_version", text=_("Check for BlenderDMX updates"), icon="SHADING_WIRE")
        row = layout.row()
        col1 = row.column()
        col1.label(text = _("Status: {}").format(context.window_manager.dmx.release_version_status))
        col2 = row.column()
        col2.operator('wm.url_open', text="", icon="SHADING_WIRE").url="https://github.com/open-stage/blender-dmx/releases/latest"

class DMX_PT_Setup_Import(Panel):
    bl_label = _("Import")
    bl_idname = "DMX_PT_Setup_Import"
    bl_parent_id = "DMX_PT_Setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DMX"
    bl_context = "objectmode"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        dmx = context.scene.dmx
        # "Import GDTF Profile"
        row = layout.row()
        row.operator(DMX_OT_Setup_Import_GDTF.bl_idname, text=_("Import GDTF Profile"), icon="IMPORT")

        # "Import MVR scene"
        row = layout.row()
        row.operator(DMX_OT_Setup_Import_MVR.bl_idname, text=_("Import MVR Scene"), icon="IMPORT")

        # export project data
        row = layout.row()
        row.operator("dmx.import_custom_data", text=_("Import Project data"), icon="IMPORT")

class DMX_PT_Setup_Export(Panel):
    bl_label = _("Export")
    bl_idname = "DMX_PT_Setup_Export"
    bl_parent_id = "DMX_PT_Setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DMX"
    bl_context = "objectmode"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        dmx = context.scene.dmx

        # export project data
        row = layout.row()
        row.operator("dmx.export_custom_data", text=_("Export Project data"), icon="EXPORT")

class DMX_OT_Setup_Open_LogFile(Operator):
    bl_label = _("Show logging directory")
    bl_description = _("Show logging directory")
    bl_idname = "dmx.print_logging_path"
    bl_options = {'UNDO'}

    def execute(self, context):
        # DMX setup
        current_path = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(current_path, "..")
        path = os.path.abspath(path)
        self.report({"INFO"}, f"Path with a log file: {path}")

        return {'FINISHED'}

class DMX_PT_Setup_Logging(Panel):
    bl_label = _("Logging")
    bl_idname = "DMX_PT_Setup_Logging"
    bl_parent_id = "DMX_PT_Setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DMX"
    bl_context = "objectmode"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        # DMX setup
        ADDON_PATH = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(ADDON_PATH, "blenderDMX.log")

        layout = self.layout
        dmx = context.scene.dmx
        row = layout.row()
        row.prop(context.scene.dmx, 'logging_level')
        row = layout.row()
        row.label(text=_("Log filter"))
        row = layout.row(align=True)
        row.prop(context.window_manager.dmx, "logging_filter_mvr_xchange", toggle=True)
        row.prop(context.window_manager.dmx, "logging_filter_dmx_in", toggle=True)
        row.prop(context.window_manager.dmx, "logging_filter_fixture", toggle=True)
        row = layout.row()
        layout.operator("dmx.print_logging_path")

# Panel #

class DMX_PT_Setup(Panel):
    bl_label = _("Setup")
    bl_idname = "DMX_PT_Setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DMX"
    bl_context = "objectmode"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        dmx = context.scene.dmx
        if (not dmx.collection):
            if not bpy.app.version >= (3, 4):
                layout.label(text = _("Error! Blender 3.4 or higher required."), icon="ERROR")
            layout.operator("dmx.new_show", text=_("Create New Show"), icon="LIGHT")
            layout.operator('wm.url_open', text="User Guide Online", icon="HELP").url="https://blenderdmx.eu/docs/faq/"

class DMX_OT_VersionCheck(Operator):
    bl_label = _("Check version")
    bl_description = _("Check if there is new release of BlenderDMX")
    bl_idname = "dmx.check_version"
    bl_options = {'UNDO'}

    def callback(self, data, context):
        temp_data = context.window_manager.dmx
        text = _("Unknown version error")
        if "error" in data:
            text = data["error"]
        else:
            try:
                current_version = application_info["version"]
                new_version = data["name"]
                res = blender_utils.version_compare(current_version, new_version)
            except Exception as e:
                text = f"{e.__class__.__name__} {e}"
            else:
                if res < 0:
                    text = _("New version {} available").format(new_version)
                elif res > 0:
                    text = _("You are using pre-release version")
                else:
                    text = _("You are using latest version of BlenderDMX")

        self.report({"INFO"}, f"{text}")
        temp_data.release_version_status = text

    def execute(self, context):
        temp_data = context.window_manager.dmx
        temp_data.release_version_status = _("Checking...")
        blender_utils.get_latest_release(self.callback, context)
        return {'FINISHED'}

class DMX_OT_Import_Custom_Data(Operator):
    bl_label = _("Import Custom Data")
    bl_idname = "dmx.import_custom_data"
    bl_description = _("Unzip previously exported custom data from a zip file. This will overwrite current data!")
    bl_options = {'UNDO'}

    filter_glob: StringProperty(default="*.zip", options={'HIDDEN'})

    directory: StringProperty(
        name=_("File Path"),
        maxlen= 1024,
        default= "" )

    files: CollectionProperty(
        name=_("Files"),
        type=bpy.types.OperatorFileListElement
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "files")

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        print("print", self.directory, self.files[0].name)
        file_name = self.files[0].name
        if file_name != "" and len(file_name)>1:
            result = blender_utils.import_custom_data(self.directory, file_name)
        else:
            self.report({'ERROR'}, _("Incorrect file name!"))
            return {'FINISHED'}

        if result.ok:
            import_filename = os.path.join(self.directory, file_name)
            self.report({'INFO'}, _("Data imported from: {}").format(import_filename))
        else:
            self.report({'ERROR'}, result.error)

        return {'FINISHED'}

class DMX_OT_Export_Custom_Data(Operator):
    bl_label = _("Export Custom Data")
    bl_idname = "dmx.export_custom_data"
    bl_description = _("Zip and Export custom data from BlenderDMX addon directory.")
    bl_options = {'UNDO'}

    filter_glob: StringProperty(default="*.zip", options={'HIDDEN'})

    directory: StringProperty(
        name=_("File Path"),
        maxlen= 1024,
        default= "" )

    files: CollectionProperty(
        name=_("Files"),
        type=bpy.types.OperatorFileListElement
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "files")

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        file_name = self.files[0].name
        if file_name[-4:].lower() == ".zip":
            file_name = file_name[:-4]
        if file_name != "" and len(file_name)>1:
            result = blender_utils.export_custom_data(self.directory, file_name)
        else:
            self.report({'ERROR'}, _("Incorrect file name!"))
            return {'FINISHED'}

        if result.ok:
            export_filename = os.path.join(self.directory, f"{file_name}.zip")
            self.report({'INFO'}, _("Data exported to: {}").format(export_filename))
        else:
            self.report({'ERROR'}, result.error)

        return {'FINISHED'}

class DMX_OT_Setup_Import_GDTF(Operator):
    bl_label = _("Import GDTF Profile")
    bl_idname = "dmx.import_gdtf_profile"
    bl_description = _("Import fixture from GDTF Profile")
    bl_options = {'UNDO'}

    filter_glob: StringProperty(default="*.gdtf", options={'HIDDEN'})

    directory: StringProperty(
        name=_("File Path"),
        maxlen= 1024,
        default= "" )

    files: CollectionProperty(
        name=_("Files"),
        type=bpy.types.OperatorFileListElement
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "files")

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        folder_path = os.path.dirname(os.path.realpath(__file__))
        folder_path = os.path.join(folder_path, '..', 'assets', 'profiles')
        for file in self.files:
            file_path = os.path.join(self.directory, file.name)
            DMX_Log.log.info('Importing GDTF Profile: %s' % file_path)
            shutil.copy(file_path, folder_path)
        DMX_GDTF.getManufacturerList()
        Profiles.DMX_Fixtures_Local_Profile.loadLocal()
        return {'FINISHED'}


class DMX_OT_Setup_Import_MVR(Operator):
    bl_label = _("Import MVR scene")
    bl_idname = "dmx.import_mvr_scene"
    bl_description = _("Import data MVR scene file. This may take a long time!")
    bl_options = {'UNDO'}

    filter_glob: StringProperty(default="*.mvr", options={'HIDDEN'})

    directory: StringProperty(
        name=_("File Path"),
        maxlen= 1024,
        default= "" )

    files: CollectionProperty(
        name=_("Files"),
        type=bpy.types.OperatorFileListElement
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "files")

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        folder_path = os.path.dirname(os.path.realpath(__file__))
        folder_path = os.path.join(folder_path, '..', 'assets', 'profiles')
        for file in self.files:
            file_path = os.path.join(self.directory, file.name)
            print("INFO", f'Processing MVR file: {file_path}')
            dmx = context.scene.dmx
            dmx.addMVR(file_path)
            #shutil.copy(file_path, folder_path)
        # https://developer.blender.org/T86803
        #self.report({'WARNING'}, 'Restart Blender to load the profiles.')
        return {'FINISHED'}

