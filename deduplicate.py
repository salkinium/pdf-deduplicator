#!/usr/bin/env python3
# Copyright 2018 Niklas Hauser, BSD 3-clause

from pdf2image import convert_from_bytes
from PyPDF2 import PdfFileWriter, PdfFileReader
import io
import sys
from pathlib import Path
from PIL import Image, ImageFilter, ImageChops, ImageStat, ImageDraw

debug = False
dpi = 100

all_input_pages = 0
all_output_pages = 0

def deduplicate(input_file):
	global all_input_pages
	global all_output_pages
	name = input_file[:-4]
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
			draw.rectangle([mask.width*0.92, mask.height*0.95, mask.width, mask.height], fill=0)
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
			if (sum(stat.sum) / sum(stat.count)) > 0.05:
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
		# 	break

	if debug: print(nr, diff_pages);
	if debug: pages[nr].save("{}/n{}.png".format(name, nr))
	new_pages.append(nr)

	outp = PdfFileWriter()
	for page in new_pages:
		outp.addPage(inp.getPage(page))
	with open(name + "-dedup.pdf", 'wb') as outfile:
		outp.write(outfile)

	dedup = inp.getNumPages() - outp.getNumPages()
	all_input_pages += inp.getNumPages()
	all_output_pages += outp.getNumPages()
	print("{:15} {:3d} ({:2d}%) slides removed: {:3d} -> {:3d}".format(input_file, dedup, int(100*dedup / inp.getNumPages()), inp.getNumPages(), outp.getNumPages()))

for file in sys.argv[1:]:
	deduplicate(file)

print("Total: {:3d} ({:2d}%) slides removed: {:3d} -> {:3d}".format(all_input_pages - all_output_pages,
                                                                    int(100 * (all_input_pages - all_output_pages) / all_input_pages),
                                                                    all_input_pages,
                                                                    all_output_pages))
