## Code swap submission

### Overview

`main.py` does three things:

- download the image urls of each dog breed (can use cached urls after running once and then setting `cache_enabled` to true)
- for each breed, calculate image "fingerprints" for a few images
- dump the fingerprints to stdout

`plot.py` also does three things:

- select breeds based on a regex, optionally given as the first argument (i.e. `python3 plot.py '^(hound|terrier)(/.*|$)'`) and defaulting to all breeds
- plot the fingerprints for each selected breed using matplotlib
- write image to `plot.png`

### Required libraries

```
matplotlib
pillow
```

### Running

Note: `main.py` can take around 15 minutes to finish running, probably due to rate limiting from the api site.

(recommended)

Run the first line once and the second line as many times as you want.

```
python3 main.py >temp
cat temp | python3 plot.py '{REGEX_HERE}'
```

(not recommended, but works)

```
python3 main.py | python3 plot.py '{REGEX_HERE}'
```
