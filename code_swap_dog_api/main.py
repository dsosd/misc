import io
import json
import PIL.Image as pyimg
import requests

###globals

#toggles cache of image urls. images are NOT cached
#enable only after one run or there will be no data
cache_enabled = False

###

#wrapper for sending requests to the api
def send_req(endpoint):
	res = requests.get("https://dog.ceo/api/{}".format(endpoint))
	return res.json()["message"]

#downloads the image and converts it into a 2d array of rgb-tuple values (each value in [0, 255])
def get_image(url):
	res = requests.get(url)

	ram_file = io.BytesIO(res.content)
	image = pyimg.open(ram_file)
	image = image.convert("RGB")

	return [
		[image.getpixel((x, y)) for x in range(image.width)]
		for y in range(image.height)
	]

#gets list of breed tuples, each either as:
#a single element tuple `(breed)`, if there are no sub-breeds
#or a `(breed, sub_breed)` tuple, for each sub-breed
def get_breeds():
	data = send_req("breeds/list/all")

	ret = [
		[[k, x] for x in v] if len(v) else [[k]]
		for k, v in data.items()
	]
	return [tuple(y) for x in ret for y in x]

#gets sorted list of images for each breed in breeds, optionally taking at most n images from each
def get_image_list(breeds, n = None):
	#selects n elements evenly throughout the list, but selects as many as possible if len(data) < n
	def choose_n(data, n):
		stride = max(len(data) // n, 1)
		return [data[i*stride] for i in range(min(n, len(data)))]

	#MAGIC default value of 5
	if n is None:
		n = 5

	return {
		x: choose_n(
			sorted(send_req("breed/{}/images".format("/".join(x)))),
			n
		)
		for x in breeds
	}

#NOTE feel free to choose a different procedure to calculate a representative color if this is too complicated
#calculates a representative color of the entire image by:
#1 - normalizing each pixel's rgb values to [1, 2, 4, ..., 128, 255] (powers of 2, except 256 because the range is [0, 255])
#2 - counting frequency of each pixel, with pixels in the middle third of the image (horizontally and vertically) counting 5 times each
#3 - discarding pixels that have a below average (arithmetic mean) frequency
#4 - take the average of all pixels element-wise
def get_image_fingerprint(image):
	#setup
	normalized_values = ([2**i for i in range(8)] + [255])[::-1]
	val_to_norm = {}

	for i in range(256):
		factors = [
			#MAGIC prevent division by zero by making denominator at least 1
			x / max(i, 1) if x >= i else i / x
			for x in normalized_values
		]

		#choose normalized value that is closest geometrically and the largest one, if any are equal
		val_to_norm[i] = normalized_values[factors.index(min(factors))]

	#step 1
	image = [
		[
			tuple([val_to_norm[z] for z in y])
			for y in x
		]
		for x in image
	]

	#step 2
	freq = {}
	width = len(image[0])
	height = len(image)

	for i in range(height):
		for j in range(width):
			if image[i][j] not in freq:
				freq[image[i][j]] = 0

			if i >= height // 3 and i <= height // 3 * 2 \
					and j >= width // 3 and j <= width // 3 * 2:
				freq[image[i][j]] += 5
			else:
				freq[image[i][j]] += 1

	#step 3
	temp = [v for k, v in freq.items()]
	avg_freq = sum(temp) / len(temp)
	freq = {k: v for k, v in freq.items() if v >= avg_freq}

	#step 4
	ret = tuple([
		sum([x[i] for x in freq.keys()]) / len(freq)
		#MAGIC 3 values per pixel
		for i in range(3)
	])

	#clamp to integer values and [0, 255]
	ret = tuple([min(max(round(x), 0), 255) for x in ret])
	return ret

if not cache_enabled:
	breeds = get_breeds()
	image_list = get_image_list(breeds)

	with open("image_url_cache", "w") as file:
		json.dump({" ".join(k): v for k, v in image_list.items()}, file)
else:
	with open("image_url_cache") as file:
		image_list = {tuple(k.split(" ")): v for k, v in json.load(file).items()}

for k, v in image_list.items():
	fingerprints = []

	for x in v:
		image = get_image(x)
		fingerprint = get_image_fingerprint(image)
		fingerprints.append(fingerprint)

	print("{}: {}".format("/".join(k), json.dumps(sorted(fingerprints))))
