import sys

#import bbb_cpp_frontend as cpp_frontend
import calc_hash as engine
import bbb_py_frontend as py_frontend

def main__entrypoint(lang, schema_in_dir, schema_out_dir, code_gen_out):
	extracted_bbb_types = engine.get_extracted_bbb_types_from_files_and_save_schemas(engine.ls_files(schema_in_dir), schema_out_dir)

	if lang == "cpp":
		spec = engine.translate_to_cpp_frontend_spec(extracted_bbb_types)

		with open(code_gen_out, "w") as file:
			file.write(cpp_frontend.spec_str(*spec))
	elif lang == "py":
		spec = engine.translate_to_python_frontend_spec(extracted_bbb_types)

		with open(code_gen_out, "w") as file:
			file.write(py_frontend.spec_str(spec))
	else:
		raise Exception()

def entrypoint(args):
	return main__entrypoint(*args)

if __name__ == "__main__":
	entrypoint(sys.argv[1:])
