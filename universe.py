#
#   BlendexDMX > Universe
#   A DMX Universe, which contains a number ID, a name and an input source
#
#   http://www.github.com/open-stage/BlenderDMX
#

import bpy

from bpy.props import (IntProperty,
                       StringProperty,
                       EnumProperty)

from bpy.types import (ID,
                       Property,
                       PropertyGroup,
                       CollectionProperty)

network_options_list = (("BLENDERDMX", "BlenderDMX", "Set DMX buffer from the Programmer"), ("ARTNET", "ArtNet", "Read DMX buffer from ArtNet"), ("sACN", "sACN", "Read DMX buffer from sACN"))

class DMX_Universe(PropertyGroup):

    id: IntProperty(
        name = "ID",
        description = "Number of the universe",
        default = 0
    )

    name: StringProperty (
        name = "Name",
        description = "Name of the universe",
        default = "Universe 0"
    )

    input: EnumProperty (
        name = "Input",
        description = "Input source of the universe",
        default = "BLENDERDMX",
        items = network_options_list)

    input_settings: StringProperty (
        default = "Input Settings"
    )

    @staticmethod
    def add(dmx, id, name):
        dmx.universes.add()
        universe = dmx.universes[-1]
        universe.id = id
        universe.name = name
        return universe

    @staticmethod
    def remove(dmx, i):
         if (i >= 0 and i < len(dmx.universes)):
            dmx.universes.remove(i)
