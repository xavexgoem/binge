import bpy, mathutils
import os, sys
from struct import pack, unpack
from bpy_extras.image_utils import load_image
from bpy.props import StringProperty, FloatProperty, BoolProperty, EnumProperty, IntProperty
from math import pi as PI

# TODO
# * gif alpha
# * gif deinterlacing (uuuuuuuuuuuuuuuuuuuuuuuuuuuugh ok it's not actually difficult but WHY?!?!?!?!)
# * however we'll manage transforms on subobjects
# * image.pack doesn't seem to work - might be textures?
# * rgb materials
# * paths, recursive search, etc, for images

# returns list of (r,g,b,a) tuples
# * assumes sane raster data, and performs few checks
# * does not deinterlace 
# * cannot have any extension blocks 
# * Outputs 1.0 alpha for every pixel; no transparency
# * will only return the first frame of an animated gif
def get_gif_pixels(f):
    # just classes to cram values
    class ImgData: pass
    class GIFHeader: pass
    class GIFImage: pass

    header = GIFHeader()
    palette = []
    (header.tag, header.width, header.height, header.flags,
     header.transparent_index, header.pixel_aspect) = unpack("< 6s 2H 3B", f.read(13))
    if header.tag not in (b'GIF87a', b'GIF89a'):
        raise ValueError("Not a valid GIF")

    color_table_size = 1 << ((header.flags & 0x07) + 1)
    color_table_depth = (header.flags & 0x70) + 1 # will this ever matter? It might.
    color_table_present = bool(header.flags & 0x80)
    if(color_table_present):
        for i in range(color_table_size):
            r,g,b = unpack("<3B",f.read(3))
            palette.append((float(r/255.0), float(g/255.0), float(b/255.0), float(1.0)))

    # todo - like vfig's, should at least allow that one fixed-size extension block
    # but this might never matter
    sentinel = unpack("<B", f.read(1))[0]
    if sentinel != 0x2C:
        raise ValueError("Image Descriptor must immediately follow GIF header")

    img = GIFImage()
    img.left, img.top, img.width, img.height, img.flags = unpack("<4H B", f.read(9))
    img.color_table_present = bool(img.flags & 1)
    img.color_table_size = 1<<((img.flags&0x07)+1)
    img.interlaced = bool(img.flags & 2)
    img.color_table_depth = ((img.flags & 0x70) >> 4) + 1

    if(img.color_table_present):
        palette = []
        for i in range(img.color_table_size):
            r,g,b = unpack("<3B",f.read(3))
            palette.append((r/255.0, g/255.0, b/255.0, 1.0))

    if palette == []:
        raise ValueError("No color table present")

    def clear_table(base_width):
        table = [bytes((i,)) for i in range((1 << (base_width)))]
        table.append('CLEAR')
        table.append('END')
        return table

    def get_code(block, bit_cursor, code_width):
        byte_cursor = int(bit_cursor / 8)
        offset_into_byte = int(bit_cursor % 8)
        b1 = block[byte_cursor]
        b2 = block[byte_cursor + 1]
        b3 = int(0)
        if offset_into_byte + code_width > 16:
            b3 = block[byte_cursor + 2]
        mask = ((1<<code_width) - 1) << offset_into_byte
        code = ((b1 | (b2<<8) | (b3<<16)) & mask) >> offset_into_byte
        return code

    base_width = unpack("<1B", f.read(1))[0]
    code_width = base_width + 1 

    block = ()
    while True:
        num_bytes = unpack("<1B", f.read(1))[0]
        if num_bytes != 0:
            block += unpack("<"+str(num_bytes) + "B", f.read(num_bytes))
        else:
            break
            
    table = clear_table(base_width)
    clear_code = 1<<base_width
    end_code = clear_code + 1

    bit_cursor = 0
    prev_code = get_code(block, bit_cursor, code_width)
    if prev_code == clear_code:
        bit_cursor += code_width
        prev_code = get_code(block, bit_cursor, code_width)
    prev_output = table[prev_code]
    result = table[prev_code]

    bit_cursor += code_width
    next_output = None
    while True:
        next_code = get_code(block, bit_cursor, code_width)
        
        if next_code < len(table):
            if next_code == clear_code:
                table = clear_table(base_width)
                bit_cursor += code_width
                code_width = base_width + 1
                prev_code = get_code(block, bit_cursor, code_width)
                prev_output = table[prev_code]
                result += table[prev_code]
                bit_cursor += code_width
                continue
            elif next_code == end_code:
                break
            else:
                next_output = table[next_code]
                table.append(prev_output + next_output[:1])
        else:
            next_output = table[prev_code] + table[prev_code][:1]
            table.append(next_output)

        result += next_output
        
        prev_code = next_code
        prev_output = next_output

        bit_cursor += code_width
        
        if len(table) == 1<<code_width:
            if code_width < 12:
                code_width += 1
    
    pixels = []
    for i in result:
        pixels.append(palette[i])
        
    imgdata = ImgData()
    imgdata.pixels = pixels
    imgdata.width = img.width
    imgdata.height = img.height
    return imgdata

# for cramming data, because I want dot notation
class vec3: pass
class Model: pass
class Subobject: pass
class Material: pass
class Vhot: pass
class Light: pass 
class Poly: pass

def blend2intermediate():
    m = Model()
    
    # for now, focusing ONLY on 3chair
    
    # mesh contains list of vertices, list of polygons
    # polygons index into list of vertices
    # then there's uv layer, which I don't understand atm
    
    blobject = [blo for blo in bpy.context.scene.objects if blo.visible_get()]
    for blo in blobject:
        if blo.type == "MESH":
            print(blo.name)
    

def bin2intermediate(f): 
    
    signature = unpack("<4s", f.read(4))[0]
    if signature.decode('ascii') != "LGMD":
        raise ValueError("Incorrect signature for .bin file")
    
    m = Model()

    m.bounds_max = vec3()
    m.bounds_min = vec3()
    m.center = vec3()

    (m.version, m.name,
     m.min_radius, m.max_radius,
     m.bounds_max.x, m.bounds_max.y, m.bounds_max.z,
     m.bounds_min.x, m.bounds_min.y, m.bounds_min.z,
     m.center.x, m.center.y, m.center.z,
     m.n_polys, m.n_points, m.n_parms, m.n_mats, m.n_calls, m.n_vhots, m.n_subobjects,
     m.o_subobjects, m.o_mats, m.o_uvs, m.o_vhots, m.o_points, m.o_lights, m.o_normals, m.o_polys, m.o_nodes,
     m.size_bytes) = unpack("< I 8s 11f 3H 4B 10I", f.read(106))

    m.name = m.name.decode('ascii').rstrip('\x00')
         
    if m.version == 4:
        m.mat_ex_flags, m.o_mat_ex, m.mat_ex_size = unpack("<III", f.read(12))

    ##### subobjects #####
    f.seek(m.o_subobjects)
    m.subobjects = []

    for _ in range(m.n_subobjects):
        o = Subobject()
        
        o.trans_a = vec3()
        o.trans_b = vec3()
        o.trans_c = vec3()
        o.trans_vec = vec3()
        
        o.polys = [] 
        o.vhots = []
        o.parent = None
        
        (o.name, o.type, o.parm, o.min_range, o.max_range,
         o.trans_a.x, o.trans_a.y, o.trans_a.z,
         o.trans_b.x, o.trans_b.y, o.trans_b.z,
         o.trans_c.x, o.trans_c.y, o.trans_c.z,
         o.trans_vec.x, o.trans_vec.y, o.trans_vec.z,
         o.child, o.sibling,
         o.vhot_start, o.vhot_num, o.point_start, o.point_num,
         o.light_start, o.light_num, o.norm_start, o.norm_num,
         o.node_start, o.node_num) = unpack("< 8s B i 14f hh 10H", f.read(93))

        o.name = o.name.decode('ascii').rstrip('\x00')
        m.subobjects.append(o)

    ## subobject relationships
    for idx,o in enumerate(m.subobjects):
        if o.child != -1:
            m.subobjects[o.child].parent = m.subobjects[idx]


    ##### Materials #####
    f.seek(m.o_mats)
    m.materials = {} # {slot: mat}

    for _ in range(m.n_mats):
        mt = Material()
        mt.name, mt.type, mt.num = unpack("< 16s Bb", f.read(18))
        mt.name = mt.name.decode('ascii').rstrip('\x00')
        mt.dbl = False
        if mt.type == 0x0: 
            mt.type = "tmap"
            mt.handle, mt.uv = unpack("< If", f.read(8))
        if mt.type == 0x1: 
            mt.type = "rgb"
            mt.b, mt.g, mt.r, pad, mt.pal = unpack("< 4B I", f.read(8))
        m.materials[mt.num] = mt
        
    ## version 4 material extension
    if m.version == 4:
        f.seek(m.o_mat_ex)
        for mt in m.materials.values():
            mt.trans, mt.illum = unpack("<2f", f.read(8)) 
            if m.mat_ex_size > 8: # see eg eleclgh2.bin, which only encodes trans and illum
                mt.max_texel_u, mt.max_texel_v = unpack("<2f", f.read(8))

    ##### UVs #####
    f.seek(m.o_uvs)
    m.uvs = []
    # is it even necessary for vhots to be after UVs? Assuming so.
    while f.tell() + 8 <= m.o_vhots:
        u, v = unpack("<ff", f.read(8))
        m.uvs.append((u,v))

    ##### Vhots #####
    f.seek(m.o_vhots)
    m.vhots = []
    if m.n_vhots > 0:
        for i in range(m.n_vhots):
            vhot = Vhot()
            vhot.vec = vec3()
            vhot.id, vhot.vec.x, vhot.vec.y, vhot.vec.z = unpack("< I 3f", f.read(16))
            for o in m.subobjects:
                if i >= o.vhot_start and i < o.vhot_start + o.vhot_num:
                    o.vhots.append(vhot)
                    break
            m.vhots.append(vhot)

    ##### Points #####
    f.seek(m.o_points)
    m.points = []
    for _ in range(m.n_points):
        x,y,z = unpack("< 3f", f.read(12))
        m.points.append((x,y,z))

    ##### Lights #####
    # Blender gives very little control over its vertex normals, so this doesn't do anything atm
    f.seek(m.o_lights)
    m.lights = []
    while f.tell() + 8 <= m.o_normals: 
        light = Light()
        light.mat_idx, light.point_idx, packed_normal = unpack("<HHI", f.read(8))
        
        #define X_NORM(norm) ((short)((norm>>16)&0xFFC0))/16384.0
        #define Y_NORM(norm) ((short)((norm>>6)&0xFFC0))/16384.0
        #define Z_NORM(norm)  ((short)((norm<<4)&0xFFC0))/16384.0
        light.normal = vec3()
        light.normal.x = ((packed_normal>>16) & 0xFFC0) / 16384.0
        light.normal.y = ((packed_normal>>6)  & 0xFFC0) / 16384.0
        light.normal.z = ((packed_normal<<4)  & 0xFFC0) / 16384.0
        
        m.lights.append(light)

    ##### Normals #####
    f.seek(m.o_normals)
    m.normals = []
    while f.tell() + 12 <= m.o_polys:
        x,y,z = unpack("< 3f", f.read(12))
        m.normals.append((x,y,z))

    ##### Polys #####
    f.seek(m.o_polys)
    m.polys = []
    for _ in range(m.n_polys):
        poly = Poly()
        (poly.id, poly.mat_id, poly.type,
         poly.n_points, poly.norm, poly.plane) = unpack("< HH BB H f", f.read(12))
        poly.points = []
        poly.lights = []
        poly.uvs = []
        
        if(poly.type & 3 == 3): # if this is a texture mapped poly
            has_uvs = True
        else:
            has_uvs = False # todo - whatever else we need for rgb and pal

        poly_subobj = None
        for __ in range(poly.n_points):
            point_idx = unpack("< H", f.read(2))[0]

            # subobjects do not have reference to their polys at all, which is annoying.
            # so we need to go through every face's points and determine if those
            # points are within the range of points for the given subobject.
            # if _any_ of the face's points are in the range,
            # consider the whole face to be part of the subobject
            # TODO - wait, what if a face shares a vertex with another object? 
            # It'd be weird, but you could do it. Thief might not like it.
            for o in m.subobjects:
                if (point_idx >= o.point_start) and (point_idx < (o.point_start + o.point_num)):
                    poly_subobj = o
                    break
            
            # in blender, polys index points in their own subobject, not the global list of points,
            # so the indices must be adjusted down
            poly.points.append(point_idx - poly_subobj.point_start)
            
        # unwind the other way, or normals are all reversed:
        poly.points.reverse() 
            
        poly_subobj.polys.append(poly)
        for __ in range(poly.n_points):
            idx = unpack("< H", f.read(2))[0]
            poly.lights.append(idx)
        if has_uvs:
            for __ in range(poly.n_points):
                idx = unpack("< H", f.read(2))[0]
                poly.uvs.append(m.uvs[idx])
            poly.uvs.reverse()
        
        if m.version == 4:
            poly.mat_idx = unpack("<B", f.read(1))[0]
            
        m.polys.append(poly)

    # hilariously inefficient double-sided check
    for o in m.subobjects:
        for i, p1 in enumerate(o.polys):
            sort1 = sorted(p1.points)
            for j, p2 in enumerate(o.polys):
                if i == j:
                    continue
                else:
                    if sort1 == sorted(p2.points):
                        m.materials[p1.mat_id].dbl = True


    return m

def intermediate2bin(): pass

def intermediate2blend(): pass
        
def import_bin(context, filepath, use_some_setting):
    
    filepath = filepath.replace('\\','/')
    f = open(filepath, 'rb')
    m = bin2intermediate(f)    

    
        
    ##### Blenderize Materials #####
    pwd = os.path.dirname(filepath)
    for mat in m.materials.values():
        if mat.name not in bpy.data.materials:

            bmat = bpy.data.materials.new(mat.name)
            bmat.use_nodes = True
            nodes = bmat.node_tree.nodes
            
            nodes.remove(nodes.get('Principled BSDF'))
            
            shader_node = nodes.new(type='ShaderNodeBsdfDiffuse')
            output_node = nodes.get('Material Output')
            
            links = nodes.data.links
            links.new(shader_node.outputs[0], output_node.inputs[0])

            if mat.type == "tmap":
     
                imgpath = pwd + "/txt16/" + mat.name
                try:
                    imgfile = open(imgpath, "rb")
                except FileNotFoundError:
                    imgpath = pwd + "/txt/" + mat.name
                    imgfile = open(imgpath, "rb")
                
                imgdata = get_gif_pixels(imgfile)
                imgfile.close()
                
                image_data = [comp for rgba in imgdata.pixels for comp in rgba]
                
                image = bpy.data.images.new(mat.name, imgdata.width, imgdata.height, alpha=True)
                
                from array import array
                image_data = array('f', image_data)
                image.pixels = image_data  
                image.pack()     
                
                texture = bpy.data.textures.new(mat.name, type='IMAGE')
                texture.image = image
                
                nodes.new("ShaderNodeTexImage")
                tex_node = nodes.get("Image Texture")
                tex_node.image = image
                links = bmat.node_tree.links
                links.new(tex_node.outputs[0], shader_node.inputs[0])
            else: # rgb
                print("yo")
                shader_node.inputs[0].default_value = (mat.r / 255.0, mat.g / 255.0, mat.b / 255.0, 1.0)
            
            bmat.dbl = mat.dbl
            if(m.version == 4):
                bmat.transp = mat.trans
                bmat.illum = mat.illum
            
        else: 
            bmat = bpy.data.materials[mat.name]
        
    ##### Blenderize Objects #####
    for o in m.subobjects:
        o.points = [p for idx, p in enumerate(m.points) if idx >= o.point_start and idx < o.point_start + o.point_num]
        
        new_obj = bpy.data.objects.new(o.name, bpy.data.meshes.new(o.name))
        new_obj.data.from_pydata(o.points, [], [p.points for p in o.polys])
        o.instance = new_obj
        
        for p, bp in zip(o.polys, new_obj.data.polygons):          
            if m.materials[p.mat_id].name not in new_obj.data.materials:
                new_obj.data.materials.append(bpy.data.materials[m.materials[p.mat_id].name])
            bp.material_index = new_obj.data.materials.find(m.materials[p.mat_id].name)
            
        
        uv_data = [uv for p in o.polys for uv in p.uvs]       
        uv_map = new_obj.data.uv_layers.new(do_init=False)
        if uv_data is not None:
            for loop, uv in zip(uv_map.data, uv_data):
                loop.uv = uv
                
        #### VHOTs ####
        for vhot in o.vhots:
            bpy.ops.object.empty_add(type="PLAIN_AXES", location=(vhot.vec.x, vhot.vec.y, vhot.vec.z))
            bpy.context.object.name = "vhot_" + str(vhot.id)            
            bpy.context.object.parent = new_obj  
    
               
        new_obj.data.validate(verbose=True) 
        bpy.data.collections[0].objects.link(new_obj)
    
    for o in m.subobjects:

        if o.type == 1: # rotation
            bpy.ops.object.empty_add(type="CIRCLE", rotation=(0,0,PI/2.0), radius=2)
            bpy.context.object.parent = o.instance    
            bpy.context.object.name = "rotator"
        elif o.type == 2: # translation  
            bpy.ops.object.empty_add(type="SINGLE_ARROW", rotation=(0,0,0))
            bpy.context.object.parent = o.instance    
            bpy.context.object.name = "translator"

        if o.parent:
                        
            # note - I haven't checked if the matrix is identity by default,
            # and it's conceivable that if the subobj requires no transform
            # that this is therefore a zero matrix. I highly doubt this, but
            # if subobjects disappear/look weird, it might be because of this (but probably not)
            rows = []
            rows.append([o.trans_a.x, o.trans_a.y, o.trans_a.z, 0.0])
            rows.append([o.trans_b.x, o.trans_b.y, o.trans_b.z, 0.0])
            rows.append([o.trans_c.x, o.trans_c.y, o.trans_c.z, 0.0])
            rows.append([o.trans_vec.x, o.trans_vec.y, o.trans_vec.z, 1.0])
            trans = mathutils.Matrix(rows)
            trans.transpose()
            o.instance.parent = o.parent.instance
            o.instance.matrix_world = trans

            

    return {'FINISHED'}


# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
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
        layout.row().prop(activeMat, 'shader')
        layout.row().prop(activeMat, 'transp')
        layout.row().prop(activeMat, 'illum')
        layout.row().prop(activeMat, 'dbl')
        layout.row().prop(activeMat, 'nocopy')
        layout.row().separator()
        layout.row().operator('material.import_from_custom', icon = 'MATERIAL')

class ImportSomeData(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "import_test.some_data"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import Some Data"

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
    self.layout.operator(ImportSomeData.bl_idname, text="Text Import Operator")

# Register and add to the "file selector" menu (required to use F3 search "Text Import Operator" for quick access)
def register():
    bpy.utils.register_class(ImportSomeData)
    
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
    #bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportSomeData)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
    # test call
    bpy.ops.import_test.some_data('INVOKE_DEFAULT')
    #blend2intermediate()

