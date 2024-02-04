import sys

from lib_bbb import Bbb
from generated import Bbb_types

def main__entrypoint():
	Kb_page = Bbb_types.Type_311a4f75_01f60029_7f97607e_1719ca59

	page = Kb_page()

	page.get_header.set_full()
	header = page.get_header.get_full

	header.get_id = list(range(16))
	header.get_human_id = list("moaner-reaper-lunge-vetted-blame".encode("utf-8"))
	header.get_canonical_name.get_name = list("foo".encode("utf-8"))

	print(page.serialize().hex())

def entrypoint(args):
	return main__entrypoint(*args)

if __name__ == "__main__":
	entrypoint(sys.argv[1:])
