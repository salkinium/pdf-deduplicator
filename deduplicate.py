#!/usr/bin/env python3
# Copyright 2018 Niklas Hauser, BSD 3-clause

from pdf2image import convert_from_bytes
from PyPDF2 import PdfFileWriter, PdfFileReader
import io, sys, argparse, multiprocessing
from pathlib import Path
from PIL import Image, ImageFilter, ImageChops, ImageStat, ImageDraw

def deduplicate(input_file, masks, threshold, dpi, suffix):
    name = input_file[:-4]
    debug=False
    if debug: Path(name).mkdir(exist_ok=True)

    pages = []
    bwpages = []
    current = None

    last_page = 0
    diff_pages = 1

    new_pages = []
    mask = None

    inp = PdfFileReader(input_file, "rb")
    for nr, page in enumerate(inp.pages):
        wrt = PdfFileWriter()
        wrt.addPage(page)
        r = io.BytesIO()
        wrt.write(r)
        pages.append(convert_from_bytes(r.getvalue(), fmt="png", dpi=dpi)[0])
        r.close()
        bwpages.append(pages[nr].convert('L').filter(ImageFilter.FIND_EDGES))
        bwpages[nr] = Image.eval(bwpages[nr], lambda px: 0 if px == 0 else 255).convert('1')
        if mask is None:
            mask = Image.eval(bwpages[nr], lambda px: 1)
            draw = ImageDraw.Draw(mask)
            for m in masks:
                draw.rectangle([mask.width*m[0], mask.height*m[1], mask.width*m[2], mask.height*m[3]], fill=0)
            del draw
        bwpages[nr] = ImageChops.logical_and(bwpages[nr], mask)
        if debug: bwpages[nr].save("{}/o{}.png".format(name, nr));
        if debug: pages[nr].save("{}/i{}.png".format(name, nr));
        if nr == 0:
            current = bwpages[0]
        else:
            diff = ImageChops.difference(bwpages[nr], bwpages[nr-1])
            if debug: diff.save("{}/d{}.png".format(name, nr-1))

            anded = ImageChops.logical_and(current, diff)
            if debug: anded.save("{}/a{}.png".format(name, nr-1));

            stat = ImageStat.Stat(anded)
            if (sum(stat.sum) / sum(stat.count)) > threshold:
                last_page = nr - 1
                new_pages.append(last_page)
                if debug: pages[last_page].save("{}/n{}.png".format(name, last_page));
                if debug: print(last_page, diff_pages);
                current = bwpages[nr]
                diff_pages = 1
            else:
                diff_pages += 1
                current = ImageChops.add(current, diff)
            if debug: current.save("{}/c{}.png".format(name, nr-1));
        # if nr > 10:
        #   break

    if debug: print(nr, diff_pages);
    if debug: pages[nr].save("{}/n{}.png".format(name, nr))
    new_pages.append(nr)

    outp = PdfFileWriter()
    for page in new_pages:
        outp.addPage(inp.getPage(page))
    with open(name + suffix + ".pdf", 'wb') as outfile:
        outp.write(outfile)

    input_pages = inp.getNumPages()
    output_pages = outp.getNumPages()
    dedup = input_pages - output_pages
    print("{:15} {:3d} ({:2d}%) slides removed: {:3d} -> {:3d}".format(input_file, dedup, int(100*dedup / input_pages), input_pages, output_pages))
    return (input_pages, output_pages)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Deduplicate PDF slides')
    parser.add_argument('--dpi', dest='dpi', type=int, default=150,
                        help='DPI resolution to perform the diff with.')
    parser.add_argument('--suffix', dest='suffix', default="-dedup",
                        help='Suffix appended to the deduplicated slide.')
    parser.add_argument('--threshold', dest='threshold', type=float, default=0.05,
                        help='Maximum difference between slides to be considered the same slide.')
    parser.add_argument('--mask', dest='masks', action='append',
                        help='Mask out differences in parts of the slide: `x1,y1,x2,y2`. '
                             'Example: `--mask "0.92,0.96,1.0,1.0"` (lower right corner).')
    parser.add_argument(dest='slides', nargs='+',
                        help='The PDF slides to deduplicate.')

    args = parser.parse_args()

    masks = [eval("({})".format(m)) for m in args.masks]
    def dedup(f):
        return deduplicate(f, masks=masks, threshold=args.threshold, dpi=args.dpi, suffix=args.suffix)
    with multiprocessing.Pool() as p:
        pages = p.map(dedup, args.slides)
    all_input_pages = sum(p[0] for p in pages)
    all_output_pages = sum(p[1] for p in pages)

    print("Total: {:3d} ({:2d}%) slides removed: {:3d} -> {:3d}".format(all_input_pages - all_output_pages,
                                                                        int(100 * (all_input_pages - all_output_pages) / all_input_pages),
                                                                        all_input_pages,
                                                                        all_output_pages))
