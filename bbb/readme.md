## `bbb`

`bbb` is a project that generates code for serialization/deserialization (serdes) based on schema files. **It is currently still in development and not recommended for serious use.**

### Building
The following steps are for a generic Linux distro.

Dependencies:
- the antlr4 runtime
- python libs:
	- antlr4-python3-runtime

1. Install the antlr4 runtime which can be found in distro package managers and on the official website at [https://www.antlr.org/download.html](https://www.antlr.org/download.html).
2. Ensure `antlr4` is in your `PATH`.
3. Install the python library **that corresponds to the version** of the antlr4 runtime from step 1. For example, if you have version 4.13.0, you should be running a command similar to `pip3 install antlr4-python3-runtime==4.13.0`.
4. Change to the `bbb` directory within this repo. `cd bbb`
5. Run `compile_bbb.sh`. `./compile_bbb.sh`
6. See example usage in `run.sh`. `./run.sh`

### License
This project is under the MIT license. See `license` for the full license.
