#
#   BlendexDMX > Fixture
#   Base class for a lighting fixture
#
#   http://www.github.com/hugoaboud/BlenderDMX
#

import bpy
import math
import mathutils

from dmx.material import getEmitterMaterial
from dmx.model import DMX_Model
from dmx.logging import DMX_Log

from dmx.param import DMX_Param, DMX_Model_Param
from dmx import pygdtf

from dmx.gdtf import DMX_GDTF
from dmx.data import DMX_Data
from dmx.util import cmy_to_rgb
from dmx.util import sanitize_obj_name

from bpy.props import (IntProperty,
                       FloatProperty,
                       BoolProperty,
                       FloatVectorProperty,
                       PointerProperty,
                       StringProperty,
                       CollectionProperty)

from bpy.types import (PropertyGroup,
                       Collection,
                       Object,
                       Material)

# Shader Nodes default labels
# Blender API naming convention is inconsistent for internationalization
# Every label used is listed here, so it's easier to fix it on new API updates
STRENGTH = "Strength"
COLOR = "Color"

class DMX_Fixture_Object(PropertyGroup):
    object: PointerProperty(
        name = "Fixture > Object",
        type = Object)

class DMX_Emitter_Material(PropertyGroup):
    material: PointerProperty(
        name = "Emitter > Material",
        type = Material)

class DMX_Fixture_Channel(PropertyGroup):
    id: StringProperty(
        name = "Fixture > Channel > ID",
        default = '')
    default: IntProperty(
        name = "Fixture > Channel > Default",
        default = 0)
    geometry: StringProperty(
        name = "Fixture > Geometry",
        default = '')

class DMX_Fixture(PropertyGroup):

    # Blender RNA #

    collection: PointerProperty(
        name = "Fixture > Collection",
        type = Collection)

    objects: CollectionProperty(
        name = "Fixture > Objects",
        type = DMX_Fixture_Object
    )

    lights: CollectionProperty(
        name = "Fixture > Lights",
        type = DMX_Fixture_Object
    )

    emitter_materials: CollectionProperty(
        name = "Fixture > Materials",
        type = DMX_Emitter_Material)

    # DMX properties

    profile: StringProperty(
        name = "Fixture > Profile",
        default = "")
    
    mode : StringProperty(
        name = "Fixture > Mode",
        description="Fixture DMX Mode",
        default = '')
    
    channels: CollectionProperty(
        name = "Fixture > Channels",
        type = DMX_Fixture_Channel
    )

    universe : IntProperty(
        name = "Fixture > Universe",
        description="Fixture DMX Universe",
        default = 0,
        min = 0,
        max = 511)

    address : IntProperty(
        name = "Fixture > Address",
        description="Fixture DMX Address",
        default = 1,
        min = 1,
        max = 512)
        
    display_beams: BoolProperty(
        name = "Display beams",
        description="Display beam projection and cone",
        default = True)

    gel_color: FloatVectorProperty(
        name = "Gel Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (1.0,1.0,1.0,1.0))

    def build(self, name, profile, mode, universe, address, gel_color, display_beams, mvr_position = None):

        # (Edit) Store objects positions
        old_pos = {obj.name:obj.object.location.copy() for obj in self.objects}
        old_rot = {obj.name:obj.object.rotation_euler.copy() for obj in self.objects}
        
        # (Edit) Collection with this name already exists, delete it
        if (self.name in bpy.data.collections):
            for obj in bpy.data.collections[self.name].objects:
                bpy.data.objects.remove(obj)
            bpy.data.collections.remove(bpy.data.collections[self.name])

        # Data Properties
        self.name = name
        self.profile = profile
        self.mode = mode

        # DMX Properties
        self.universe = universe
        self.address = address
        self.gel_color = list(gel_color)
        self.display_beams = display_beams

        # (Edit) Clear links and channel cache
        self.lights.clear()
        self.objects.clear()
        self.channels.clear()

        # Create clean Collection
        # (Blender creates the collection with selected objects/collections)
        bpy.ops.collection.create(name=name)
        self.collection = bpy.data.collections[name]

        for c in self.collection.objects:
            self.collection.objects.unlink(c)
        for c in self.collection.children:
            self.collection.children.unlink(c)

        # Import and deep copy Fixture Model Collection
        gdtf_profile = DMX_GDTF.loadProfile(profile)
        model_collection = DMX_Model.getFixtureModelCollection(gdtf_profile, self.mode, self.display_beams)

        # Build DMX channels cache
        dmx_channels = pygdtf.utils.get_dmx_channels(gdtf_profile, self.mode)
        # Merge all DMX breaks together
        dmx_channels_flattened = [channel for break_channels in dmx_channels for channel in break_channels]
        for ch in dmx_channels_flattened:
            self.channels.add()
            self.channels[-1].id = ch['id']
            self.channels[-1].geometry = ch['geometry']

            # Set shutter to 0, we don't want strobing by default
            # and are not reading real world values yet
            if "shutter" in ch['id'].lower():
                self.channels[-1].default = 0
            else:
                self.channels[-1].default = ch['default']

        links = {}
        base = self.get_root(model_collection)
        head = self.get_tilt(model_collection)
        DMX_Log.log.info(f"Head: {head}, Base: {base}")

        for obj in model_collection.objects:
            # Copy object
            links[obj.name] = obj.copy()
            # If light, copy object data, 
            # Cache access to base (root) and head for faster rendering.
            # Fixtures with multiple pan/tilts will still have issues
            # but that would anyway require geometry → attribute approach
            if obj.type == 'LIGHT':
                links[obj.name].data = obj.data.copy()
                self.lights.add()
                light_name=f'Light{len(self.lights)}'
                self.lights[-1].name = light_name
                self.lights[light_name].object = links[obj.name]
            elif 'Target' in obj.name:
                self.objects.add()
                self.objects[-1].name = 'Target'
                self.objects['Target'].object = links[obj.name]
            elif base.name == obj.name:
                self.objects.add()
                self.objects[-1].name = "Root"
                self.objects["Root"].object = links[obj.name]
            elif head is not None and head.name == obj.name:
                self.objects.add()
                self.objects[-1].name = "Head"
                self.objects["Head"].object = links[obj.name]

            # Link all other object to collection
            self.collection.objects.link(links[obj.name])

        # Relink constraints
        for obj in self.collection.objects:
            for constraint in obj.constraints:
                constraint.target = links[constraint.target.name]

        # (Edit) Reload old positions and rotations
        bpy.context.view_layer.update()
        for obj in self.objects:
            if obj.name in old_pos:
                obj.object.location = old_pos[obj.name]

            if obj.object.get("geometry_root", False):
                if obj.name in old_rot:
                    obj.object.rotation_mode = 'XYZ'
                    obj.object.rotation_euler = old_rot[obj.name]

        # Set position from MVR
        if mvr_position is not None:
            for obj in self.objects:
                if obj.object.get("geometry_root", False):
                    obj.object.matrix_world=mvr_position

        # Setup emitter
        for obj in self.collection.objects:
            if "beam" in obj.get("geometry_type", ""):
                emitter = obj
                self.emitter_materials.add()
                self.emitter_materials[-1].name = obj.name

                emitter_material = getEmitterMaterial(obj.name)
                emitter.active_material = emitter_material
                emitter.material_slots[0].link = 'OBJECT'
                emitter.material_slots[0].material = emitter_material
                emitter.material_slots[0].material.shadow_method = 'NONE' # eevee
                self.emitter_materials[-1].material = emitter_material


        # Link collection to DMX collection
        bpy.context.scene.dmx.collection.children.link(self.collection)

        # Set Pigtail visibility
        for obj in self.collection.objects:
            if "pigtail" in obj.get("geometry_type", ""):
                obj.hide_set(not bpy.context.scene.dmx.display_pigtails)
 
        self.clear()
        bpy.context.scene.dmx.render()
    
    # Interface Methods #

    def setDMX(self, pvalues):
        channels = [c.id for c in self.channels]
        for param, value in pvalues.items():
            for idx, channel in enumerate(channels):
                if channel == param:
                    DMX_Log.log.info(("Set DMX data", channel, value))
                    DMX_Data.set(self.universe, self.address+idx, value)

    def render(self):
        channels = [c.id for c in self.channels]
        data = DMX_Data.get(self.universe, self.address, len(channels))
        shutterDimmer = [None, None]
        panTilt = [None,None]
        rgb = [None,None,None]
        cmy = [None,None,None]
        zoom = None
        mixing={} #for now, only RGB mixing is per geometry
        for c in range(len(channels)):
            geometry=self.channels[c].geometry
            if geometry not in mixing.keys():
                mixing[geometry]=[None, None, None]
            if (channels[c] == 'Dimmer'): shutterDimmer[1] = data[c]
            elif (channels[c] == 'Shutter1'): shutterDimmer[0] = data[c]
            elif (channels[c] == 'ColorAdd_R'): mixing[geometry][0] = data[c]
            elif (channels[c] == 'ColorAdd_G'): mixing[geometry][1] = data[c]
            elif (channels[c] == 'ColorAdd_B'): mixing[geometry][2] = data[c]
            elif (channels[c] == 'ColorSub_C'): cmy[0] = data[c]
            elif (channels[c] == 'ColorSub_M'): cmy[1] = data[c]
            elif (channels[c] == 'ColorSub_Y'): cmy[2] = data[c]
            elif (channels[c] == 'Pan'): panTilt[0] = data[c]
            elif (channels[c] == 'Tilt'): panTilt[1] = data[c]
            elif (channels[c] == 'Zoom'): zoom = data[c]
       
        for geometry, rgb in mixing.items():
            if (rgb[0] != None and rgb[1] != None and rgb[2] != None):
                if len(mixing) == 1 or not self.light_object_for_geometry_exists(mixing):
                    # do not apply for simple devices as trickle down is not implemented...
                    self.updateRGB(rgb, None)
                else:
                    self.updateRGB(rgb, geometry)
        
        if (cmy[0] != None and cmy[1] != None and cmy[2] != None):
            self.updateCMY(cmy)

        if panTilt[0] != None or panTilt[1] != None:
            if panTilt[0] is None:
                panTilt[0] = 191 # if the device doesn't have pan, align head with base
            if panTilt[1] is None:
                panTilt[1] = 190 # FIXME maybe: adjust this if you find a device that doesn't have tilt

            self.updatePanTilt(panTilt[0], panTilt[1])

        if (zoom != None):
            self.updateZoom(zoom)

        if shutterDimmer[0] is not None or shutterDimmer[1] is not None:
            if shutterDimmer[0] is None:
                shutterDimmer[0] = 0 # if device doesn't have shutter, set default value
            self.updateShutterDimmer(shutterDimmer[0], shutterDimmer[1])

    def light_object_for_geometry_exists(self, mixing):
        """Check if there is any light or emitter matching geometry name of a color attribute"""
        for geo in mixing.keys():
            for light in self.lights:
                if geo in light.object.data.name:
                    return True
            for emitter_material in self.emitter_materials:
                if geo in emitter_material.name:
                    return True
        return False

    def get_channel_by_attribute(self, attribute):
        for channel in self.channels:
            if channel.id == attribute:
                return channel

    def updateShutterDimmer(self, shutter, dimmer):
        last_shutter_value = 0
        last_dimmer_value = 0
        try:
            for emitter_material in self.emitter_materials:
                if shutter > 0:
                    break # no need to do the expensive value settings if we do this anyway in shutter timer
                emitter_material.material.node_tree.nodes[1].inputs[STRENGTH].default_value = 10*(dimmer/255.0)

            for light in self.lights:
                last_shutter_value = light.object.data['shutter_value']
                last_dimmer_value = light.object.data['shutter_dimmer_value']
                light.object.data['shutter_value']=shutter
                light.object.data['shutter_dimmer_value']=dimmer
                if shutter > 0:
                    break # no need to do the expensive value settings if we do this anyway in shutter timer
                light.object.data.energy = (dimmer/255.0) * light.object.data['flux']

        except Exception as e:
            print("Error updating dimmer", e)

        if (last_shutter_value == 0 or last_dimmer_value == 0) and shutter != 0:
                bpy.app.timers.register(self.runStrobe)
                DMX_Log.log.info("Register shutter timer")

        return dimmer
    
    def runStrobe(self):
        try:

            exit_timer = False
            dimmer_value = 0 # reused also for emitter

            for light in self.lights:
                if light.object.data['shutter_value'] == 0:
                    exit_timer= True
                if light.object.data['shutter_dimmer_value'] == 0:
                    exit_timer = True
                dimmer_value = 0
                if light.object.data['shutter_counter'] == 1:
                    dimmer_value = light.object.data['shutter_dimmer_value']
                if light.object.data['shutter_counter'] > light.object.data['shutter_value']:
                    light.object.data['shutter_counter'] = 0

                light.object.data.energy = (dimmer_value/255.0) * light.object.data['flux']
                light.object.data['shutter_counter'] +=1

            # Here we can reuse data we got from the light object...
            for emitter_material in self.emitter_materials:
                emitter_material.material.node_tree.nodes[1].inputs[STRENGTH].default_value = 10*(dimmer_value/255.0)

            if exit_timer:
                DMX_Log.log.info("Killing shutter timer")
                return None # exit the timer

        except Exception as e:
            DMX_Log.log.error("Error updating lights and emitters", e)
            DMX_Log.log.info("Killing shutter timer")
            return None # kills the timer
        return 1.0/24.0

    def updateRGB(self, rgb, geometry):
        DMX_Log.log.info(("color change for geometry", geometry))
        try:
            rgb = [c/255.0-(1-gel) for (c, gel) in zip(rgb, self.gel_color[:3])]
            #rgb = [c/255.0 for c in rgb]
            for emitter_material in self.emitter_materials:
                DMX_Log.log.info(("emitter:", emitter_material.name))
                if geometry is not None:
                    if f"{geometry}" in emitter_material.name:
                        DMX_Log.log.info("matched emitter")
                        emitter_material.material.node_tree.nodes[1].inputs[COLOR].default_value = rgb + [1]
                else:
                    emitter_material.material.node_tree.nodes[1].inputs[COLOR].default_value = rgb + [1]
            for light in self.lights:
                if geometry is not None:
                    DMX_Log.log.info(("light:", light.object.data.name))
                    if f"{geometry}" in light.object.data.name:
                        DMX_Log.log.info("matched light")
                        light.object.data.color = rgb
                else:
                    light.object.data.color = rgb
        except Exception as e:
            print("Error updating RGB", e)
        return rgb


    def updateCMY(self, cmy):
        rgb=[0,0,0]
        rgb=cmy_to_rgb(cmy)
        rgb = [c/255.0-(1-gel) for (c, gel) in zip(rgb, self.gel_color[:3])]
        #rgb = [c/255.0 for c in rgb]
        for emitter_material in self.emitter_materials:
            emitter_material.material.node_tree.nodes[1].inputs[COLOR].default_value = rgb + [1]
        for light in self.lights:
            light.object.data.color = rgb
        return cmy

    def updateZoom(self, zoom):
        try:
            spot_size=zoom*3.1415/180.0
            for light in self.lights:
                light.object.data.spot_size=spot_size
        except Exception as e:
            print("Error updating zoom", e)
        return zoom


    def updatePanTilt(self, pan, tilt):
        pan = (pan/127.0-1)*355*(math.pi/360)
        tilt = (tilt/127.0-1)*130*(math.pi/180)

        base = self.objects["Root"].object
        try:
            head = self.objects["Head"].object
        except:
            return

        head_location = head.matrix_world.translation
        pan = pan + base.rotation_euler[2] # take base z rotation into consideration

        target = self.objects['Target'].object
        
        eul = mathutils.Euler((0.0,base.rotation_euler[1]+tilt,base.rotation_euler[0]+pan), 'XYZ')
        vec = mathutils.Vector((0.0,0.0,-(target.location-head_location).length))
        vec.rotate(eul)

        target.location = vec + head_location

    def get_root(self, model_collection):
        for obj in model_collection.objects:
            if obj.get("geometry_root", False):
                return obj

    def get_tilt(self, model_collection):
        for obj in model_collection.objects:
            for channel in self.channels:
                if "Tilt" == channel.id and channel.geometry == obj.get("original_name", "None"):
                    return obj


    def getProgrammerData(self):
        channels = [c.id for c in self.channels]
        data = DMX_Data.get(self.universe, self.address, len(channels))
        params = {}
        for c in range(len(channels)):
            params[channels[c]] = data[c]
        return params

    def select(self):
        self.objects["Root"].object.select_set(True)
    
    def unselect(self):
        self.objects["Root"].object.select_set(False)
        if ('Target' in self.objects):
            self.objects['Target'].object.select_set(False)

    def toggleSelect(self):
        selected = False
        for obj in self.objects:
            if (obj.object in bpy.context.selected_objects):
                selected = True
                break
        if (selected): self.unselect()
        else: self.select()

    def clear(self):
        for i, ch in enumerate(self.channels):
            data = DMX_Data.set(self.universe, self.address+i, ch.default)

    def onDepsgraphUpdate(self):
        # Check if any object was deleted
        for obj in self.objects:
            if (not len(obj.object.users_collection)):
                bpy.context.scene.dmx.removeFixture(self)
                break
