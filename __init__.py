bl_info = {
    'name': 'Dark Bin Loader',
    'version': (1, 1),
    'blender': (3, 6, 4),
    'location': 'File > Import-Export',
    'description': 'Import bin files and textures',
    'category': 'Import-Export'
}

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.

if 'bpy' in locals():
    import importlib
    if 'import_bin' in locals():
        importlib.reload(import_bin)

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, FloatProperty, BoolProperty, EnumProperty, IntProperty
from bpy.types import Operator

class DarkMaterialProperties(bpy.types.Panel):
    bl_idname = 'DE_MATPANEL_PT_dark_engine_exporter'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'material'
    bl_label = 'Dark Engine Materials (NewDark Toolkit)'
    
    def draw(self, context):
        activeMat = context.active_object.active_material
        layout = self.layout
        layout.row().prop(activeMat, 'transp')
        layout.row().prop(activeMat, 'illum')
        layout.row().prop(activeMat, 'dbl')
        layout.row().separator()
        layout.row().operator('material.import_from_custom', icon = 'MATERIAL')

from import_bin import import_bin
class ImportBin(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "import_scene.binfile"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import Bin File"

    # ImportHelper mixin class uses this
    filename_ext = ".bin"

    filter_glob: StringProperty(
        default="*.bin",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    use_setting: BoolProperty(
        name="Example Boolean",
        description="Example Tooltip",
        default=True,
    )

    type: EnumProperty(
        name="Example Enum",
        description="Choose between two items",
        items=(
            ('OPT_A', "First Option", "Description one"),
            ('OPT_B', "Second Option", "Description two"),
        ),
        default='OPT_A',
    )

    def execute(self, context):
        return import_bin(context, self.filepath, self.use_setting)


# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    self.layout.operator(ImportBin.bl_idname, text="Dark bin")

# Register and add to the "file selector" menu (required to use F3 search "Text Import Operator" for quick access)
def register():
    bpy.utils.register_class(ImportBin)

    
    bpy.types.Material.shader = EnumProperty(name='Shader Type', description='Face/vertex brigtness type.',
        items = [ 
            ('PHONG', 'PHONG', 'Face brightness smoothly blended between brightness of each vertex. Smooth edges. [Note: true Phong is not supported by the Dark Engine, it will automatically use Gouraud.'), 
            ('GOURAUD', 'GOURAUD', 'Face brightness smoothly blended between brightness of each vertex. Smooth edges.'),
            ('FLAT', 'FLAT', 'Face evenly lit, using the brightness of the centre. Hard edges.') 
        ]
    )
    bpy.types.Material.transp = FloatProperty(name='Transparency', description='How transpent this material is. 0 = opaque (default), 100 = transparent', min=0.0, max=1.0)
    bpy.types.Material.illum = FloatProperty(name='Illumination', description='Material brightness. 0 = use natural lighting (default), 100 = fully illuminated', min=0.0, max=1.0)
    bpy.types.Material.dbl = BoolProperty(name='Double Sided', description='Draw material from front and back of face')
    bpy.types.Material.nocopy = BoolProperty(name='Do Not Copy Texture', description='Do not copy this texture when the object is exported. E.g. select this if the texture is orginally from a .crf file, or you don\'t want to overwrite it in txt16')
    bpy.utils.register_class(DarkMaterialProperties)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportBin)
    bpy.utils.unregister_class(DarkMaterialProperties)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
    # test call
    #bpy.ops.import_test.some_data('INVOKE_DEFAULT')
    #blend2intermediate()
