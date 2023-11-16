from struct import pack, unpack

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