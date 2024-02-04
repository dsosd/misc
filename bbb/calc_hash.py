import pysodium as crypto
import heapq
import os
import sys

import dump_tree

#TODO have option of non-hardcoded hmac key
#default hmac key is all zeros
#MAGIC hmac key is 256 bits = 32 bytes
g_hmac_key = bytes([0] * 32)

def hash_data(data):
	if type(data) != bytes:
		raise Exception()

	#MAGIC 32 bytes = 256 bits
	return crypto.crypto_generichash(data, g_hmac_key, 32)

def hash_string(data):
	return hash_data(data.encode("utf-8"))

#TODO stop reimplementing this over and over again
def collate(data):
	ret = {}

	for k, v in data:
		if k not in ret:
			ret[k] = []

		ret[k].append(v)
	return ret

class Graph:
	def __init__(self, strict_mode = True):
		self.vertices = set()
		#src to set of dests
		self.edges = {}
		self.strict_mode = strict_mode

	def add_vertex(self, name):
		if name not in self.vertices:
			self.vertices.add(name)
			self.edges[name] = set()
			return True

		return False

	def add_edge(self, src, dest):
		if src not in self.vertices or dest not in self.vertices:
			if self.strict_mode:
				raise Exception()
			else:
				self.add_vertex(src)
				self.add_vertex(dest)

		if dest not in self.edges[src]:
			self.edges[src].add(dest)
			return True
		return False

	def remove_edge(self, src, dest):
		if src not in self.vertices or dest not in self.vertices:
			if self.strict_mode:
				raise Exception()
			else:
				self.add_vertex(src)
				self.add_vertex(dest)

		if dest in self.edges[src]:
			self.edges[src].remove(dest)
			return True
		return False

	def get_inverse(self):
		ret = Graph()

		for x in self.vertices:
			ret.add_vertex(x)

		for k, v in self.edges.items():
			for x in v:
				ret.add_edge(x, k)

		return ret

	def calc_in_out_degrees(self):
		in_degrees = {x: 0 for x in self.vertices}
		out_degrees = {x: 0 for x in self.vertices}

		for k, v in self.edges.items():
			for x in v:
				out_degrees[k] += 1
				in_degrees[x] += 1

		return in_degrees, out_degrees

	#kahn's topo sort with vertices in order when possible
	def topo_sort(self):
		ret = []
		queue = []

		def queue_push(ele):
			heapq.heappush(queue, ele)

		def queue_pop():
			return heapq.heappop(queue)

		vertex_to_in_degree = self.calc_in_out_degrees()[0]

		for k, v in vertex_to_in_degree.items():
			if not v:
				queue_push(k)

		while len(queue):
			ele = queue_pop()
			ret.append(ele)

			for x in self.edges[ele]:
				vertex_to_in_degree[x] -= 1
				if not vertex_to_in_degree[x]:
					queue_push(x)

		#sanity check
		if len(ret) != len(self.vertices):
			raise Exception()

		return ret

	def dependency_topo_sort(self):
		return self.get_inverse().topo_sort()

#TODO move to dedicated test suite script
def test_dependency_topo_sort():
	graph = Graph(False)
	edges = [
		["c", "b"],
		["c", "f"],
		["d", "e"],
		["f", "g"],
		["g", "b"],
		["a", "g"]
	]

	[graph.add_edge(*x) for x in edges]
	if "".join(graph.dependency_topo_sort()) != "bedgafc":
		raise Exception()

def u32_to_big_endian(num):
	if num < 0 or num >= 2**32:
		raise Exception()

	ret = []
	for i in range(4):
		ret.append(num % 2**8)
		num //= 2**8

	return bytes(ret[::-1])

def get_file_ast(file):
	data = dump_tree.Stream_file(file)
	lexer = dump_tree.Lexer(data)
	tokens = dump_tree.Token_stream(lexer)

	parser = dump_tree.Parser(tokens)
	listener = dump_tree.Basic_listener()
	parser.addParseListener(listener)

	parser.basic_binary_buffer()
	data = listener.curr

	dump_tree.simplify_pack(data)

	data.children[0].validate()

	return data

g_type_schema_hash_to_type_hash_cache = {}

def get_type_hash(node):
	if node.type == "bbb":
		type_ = dump_tree.Type_t.struct
		eles = node.children[0].elements[1:]
	elif node.type.type in dump_tree.Type_t.aggregate:
		type_ = node.type.type
		eles = node.type.rest[0].elements
	else:
		type_ = node.type.type
		eles = []

	type_schema = "{}({})".format(type_, eles)
	hash_ = hash_string(type_schema)
	if hash_ in g_type_schema_hash_to_type_hash_cache:
		return g_type_schema_hash_to_type_hash_cache[hash_]

	if not len(eles):
		ret = hash_data(str(type_).encode("utf-8"))
	else:
		#add a space separator to isolate the type from the elements' data
		#not necessary due to all valid aggregate type names being at most 6 bytes (struct) and each element's data having fixed width that exceeds that (32 bytes for name hash, 16 bytes for type hash, 4 bytes for min len, 4 bytes for max len), but it doesn't hurt to do this anyways
		temp = [str(type_).encode("utf-8"), b" "]

		for x in eles:
			if type(x) == dump_tree.Forward_type:
				raise Exception("found unresolved forward type {}".format(x.hash))

		eles = [
			[
				hash_string(x.name),
				get_type_hash(x),
				#MAGIC range being None means non-vector member, i.e. range is [1, 2)
				u32_to_big_endian(x.type.range.start if x.type.range is not None else 1),
				u32_to_big_endian(x.type.range.end if x.type.range is not None else 2)
			]
			for x in eles
		]

		temp += [b"".join(x) for x in eles]
		ret = hash_data(b"".join(temp))

	#MAGIC truncate type hashes to 16 bytes bc they are 128 bits
	g_type_schema_hash_to_type_hash_cache[hash_] = ret[:16]
	return g_type_schema_hash_to_type_hash_cache[hash_]

def patch_ast_hash(ast, hash_):
	ast.children[0].elements[0].hash = hash_.hex()

def extract_bbb_types(node, ret = None):
	is_bbb = node.type == "bbb"
	is_member = type(node) == dump_tree.Member and node.type.rest is not None

	if ret is not None and get_type_hash(node) in ret:
		return ret if is_bbb else None

	if is_bbb:
		ret = {}

		temp = []
		children = node.children[0].elements[1:]
		#hash is already included as first ele of node.children[0].elements
		size_bounds = (node.children[0].min_size(), node.children[0].max_size())
	elif is_member:
		temp = []
		children = node.type.rest[0].elements
		#MAGIC 16 bytes for hash
		size_bounds = (16 + node.type.rest[0].min_size(), 16 + node.type.rest[0].max_size())
	else:
		return

	print(">>>", get_type_hash(node).hex())
	aggregate_type = dump_tree.Type_t.struct if is_bbb else node.type.type
	anon_count = 0

	for x in children:
		hash_ = get_type_hash(x)
		type_ = x.type.type if x.type.type in dump_tree.Type_t.primitive + [dump_tree.Type_t._] else hash_

		if x.name != "_":
			name = x.name
		else:
			name = "_{}".format(anon_count)
			anon_count += 1

		range_ = [x.type.range.start, x.type.range.end] if x.type.range is not None else None

		if range_ == [1, 2] or range_ is None:
			temp.append([type_, name])
		else:
			temp.append([type_, name, *range_])

	ret[(get_type_hash(node), aggregate_type)] = [temp, size_bounds]

	[extract_bbb_types(y, ret) for y in children]

	if is_bbb:
		return ret

def type_to_frontend_typename(data):
	#primitive
	if type(data) == dump_tree.Type_t_internal:
		return str(data)
	#aggregate, so we have a hash
	else:
		ret = data.hex()
		return "Type_{}".format("_".join([ret[i*8:(i + 1)*8] for i in range(len(ret) // 8)]))

def calc_generic_spec(extracted_bbb_types):
	classes = []
	type_to_dep_types = {}
	type_to_vec_types = {}

	for k, v in extracted_bbb_types.items():
		type_ = type_to_frontend_typename(k[0])
		vars_ = []

		for x in v[0]:
			if len(x) > 2:
				if type_ not in type_to_vec_types:
					type_to_vec_types[type_] = set()

				type_to_vec_types[type_].add(type_to_frontend_typename(x[0]))
			elif x[0] not in dump_tree.Type_t.primitive + [dump_tree.Type_t._]:
				if type_ not in type_to_dep_types:
					type_to_dep_types[type_] = set()

				type_to_dep_types[type_].add(type_to_frontend_typename(x[0]))

			vars_.append([type_to_frontend_typename(x[0]), *x[1:]])
		classes.append([k[1], k[0], type_, vars_, v[1]])

	return classes, type_to_dep_types, type_to_vec_types

def get_extracted_bbb_types_from_files_and_save_schemas(files, schema_out_dir):
	ret = {}

	#TODO extract unresolved ids and make graph to process them more efficiently
	curr_queue = files
	prev_queue = []

	print(curr_queue)

	hash_to_ast = {}

	while len(curr_queue):
		curr_len = len(curr_queue)

		for x in curr_queue:
			ast = get_file_ast(x)

			if not ast.fully_resolved():
				ast.resolve(hash_to_ast)
				#do validity check bc forward type resolution can produce duplicate member names
				ast.children[0].validate()

			if ast.fully_resolved():
				ast_hash = get_type_hash(ast)
				patch_ast_hash(ast, ast_hash)

				#TODO add non top-level hashes as well
				#TODO maybe not, we want to enforce aggregates only
				hash_to_ast[ast_hash.hex()] = ast.children[0].elements[1:]

				ret.update(extract_bbb_types(ast))

				#TODO fix potential TOCTOU bug
				with open(x) as in_:
					data = "".join(in_.readlines())
					hash_ = ast_hash.hex()

					with open("{}/{}".format(schema_out_dir, hash_), "w") as out:
						#MAGIC hash is 128 bits = 32 hex chars
						out.write(hash_ + data[32:])
			else:
				prev_queue.append(x)

		if len(prev_queue) == curr_len:
			raise Exception("not making progress with remaining files: {}".format([x.encode("utf-8") for x in sorted(prev_queue)]))

		curr_queue = prev_queue
		prev_queue = []

	return ret

def translate_to_cpp_frontend_spec(extracted_bbb_types):
	classes, type_to_dep_types, type_to_vec_types = calc_generic_spec(extracted_bbb_types)

	dep_type_to_types = collate([(x, k) for k, v in type_to_dep_types.items() for x in v])
	vec_type_to_types = collate([(x, k) for k, v in type_to_vec_types.items() for x in v])

	dep_graph = Graph()
	[dep_graph.add_vertex(x[2]) for x in classes]
	[dep_graph.add_edge(k, x) for k, v in type_to_dep_types.items() for x in v]

	topo_order = dep_graph.dependency_topo_sort()

	classes = {x[2]: x for x in classes}
	forward_decl = sorted(classes.keys())

	vec_friend_proxy = []

	for x in [*[str(x) for x in dump_tree.Type_t.primitive], *topo_order]:
		if x in vec_type_to_types:
			vec_friend_proxy.append([x, sorted(vec_type_to_types[x])])

	struct_enum_union = [
		[
			classes[x],
			sorted(dep_type_to_types[x]) if x in dep_type_to_types else [],
			x in vec_type_to_types
		]
		for x in topo_order
	]

	return forward_decl, vec_friend_proxy, struct_enum_union

def translate_to_python_frontend_spec(extracted_bbb_types):
	#reuse cpp frontend spec code
	return [x[0] for x in translate_to_cpp_frontend_spec(extracted_bbb_types)[-1]]

#TODO replace with updated version from dsosd/file
def ls_files(dir_):
	if dir_[-1] != "/":
		dir_ += "/"

	ret = ["{}{}".format(dir_, x) for x in sorted(os.listdir(dir_))]
	return [x for x in ret if os.path.isfile(x)]

def main(schema_in_dir, schema_out_dir, cache_dir = None):
	#TODO utilize cache dir
	if cache_dir is not None:
		raise Exception()

	extracted_bbb_types = get_extracted_bbb_types_from_files_and_save_schemas(ls_files(schema_in_dir), schema_out_dir)

	print(translate_to_cpp_frontend_spec(extracted_bbb_types))

if __name__ == "__main__":
	main(*sys.argv[1:])
