import json
import matplotlib.pyplot as plotter
import re
import sys

if len(sys.argv) == 2:
	key_re = re.compile(sys.argv[1])
else:
	key_re = re.compile("^.*$")

data = []

for line in sys.stdin:
	line = line[:-1]

	pos = line.index(": ")

	#MAGIC ": " has len 2
	key, val = line[:pos], json.loads(line[pos + 2:])

	if key_re.search(key):
		#reencode inner elements to tuples
		val = [tuple(x) for x in val]

		data.append(val)

figure = plotter.figure()
plot_3d = figure.add_subplot(projection = "3d")

#generates a uniformly distributed color set based on number of colors desired
def gen_colors(num):
	return [
		#MAGIC rgb is out of 255 and opacity is 1.0/1.0
		[min(max(round(255 * i / num) / 255, 0.0), 1.0)] * 3 + [1.0]
		for i in range(num)
	]

#repeats element-wise
#ex. [1, 4, 3], [2, 1, 2] => [1, 1, 4, 3, 3]
def repeat(data, ns):
	ret = [[x] * n for x, n in zip(data, ns)]

	return [y for x in ret for y in x]

plot_3d.scatter(*zip(*[y for x in data for y in x]), c = repeat(gen_colors(len(data)), [len(x) for x in data]))

plot_3d.set_xlabel("R")
plot_3d.set_ylabel("G")
plot_3d.set_zlabel("B")

figure.savefig("plot.png", bbox_inches = "tight")
