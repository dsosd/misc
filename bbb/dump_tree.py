import enum
import math
import re
import sys

from antlr4 import FileStream as Stream_file, StdinStream as Stream_stdin, CommonTokenStream as Token_stream

from out.bbbLexer import bbbLexer as Lexer
from out.bbbListener import bbbListener as Listener
from out.bbbParser import bbbParser as Parser

def override_enforce_internal(debug = False):
	def ret(func):
		class_name = ".".join(func.__qualname__.split(".")[:-1])

		def wrapper(*args, **kwargs):
			class_ = globals()[class_name]
			if debug:
				print(class_)
				print(class_.__bases__)
				print(func.__name__)

			if func.__name__ != "__init__":
				raise Exception("@override_enforce/@override_enforce_internal(...) should be added to only __init__()")

			#check all class methods
			for x in vars(class_):
				member = getattr(class_, x)

				#replace wrapper with original function
				if hasattr(member, "_tul_override_wrapper_"):
					orig_func = member(debug)
					setattr(class_, x, orig_func)

			#TODO maybe replace __init__(...) before returning
			return func(*args, **kwargs)
		return wrapper
	return ret

def override_enforce(func):
	return override_enforce_internal()(func)

def override(func):
	class_name = ".".join(func.__qualname__.split(".")[:-1])

	#this wrapper is necessary bc of cyclic dependency issue
	#@override can't see a class with globals() until it's defined
	#method can't have @override decorator until it's defined
	def wrapper(debug):
		class_ = globals()[class_name]
		if debug:
			print(class_)
			print(class_.__bases__)
			print(func.__name__)

		exist_bases = [x for x in class_.__bases__ if hasattr(x, func.__name__)]

		if not len(exist_bases):
			raise Exception("@override cannot find overridden function for func {} in class {} with base classes {}".format(
				func.__name__.encode("utf-8"),
				class_.__name__.encode("utf-8"),
				[x.__name__.encode("utf-8") for x in class_.__bases__]
			))

		valid_bases = [x for x in exist_bases if callable(getattr(x, func.__name__))]

		if not len(valid_bases):
			raise Exception("@override cannot find callable override for func {} in class {} with base classes {}. found non-callable variables in base classes {}".format(
				func.__name__.encode("utf-8"),
				class_.__name__.encode("utf-8"),
				[x.__name__.encode("utf-8") for x in class_.__bases__],
				[x.__name__.encode("utf-8") for x in exist_bases]
			))

		return func

	setattr(wrapper, "_tul_override_wrapper_", None)
	return wrapper

#TODO remove
#globals

debug_ast = False
debug_sizes = False

#^

class Pack:
	def __init__(self):
		self.type = "<void>"
		self.data = []
		self.children = []

	def __repr__(self):
		return "Pack({}, {}, {})".format(self.type, self.data, self.children)

	def set_type(self, type):
		self.type = type

	def add_data(self, data):
		self.data.append(data)

	def validate(self):
		raise Exception("pure virtual func")

	def iterator(self):
		for x in self.children:
			yield x

	def min_size(self):
		raise Exception("pure virtual func")

	def max_size(self):
		raise Exception("pure virtual func")

	def find_type(self, type):
		try:
			return [x.type == type for x in self.children].index(True)
		except ValueError:
			return -1

	def collapse_ranges(self):
		if self.type == "type":
			open_pos = None
			if self.find_type("open_bracket") != -1:
				open_pos = self.find_type("open_bracket")
			elif self.find_type("open_paren") != -1:
				open_pos = self.find_type("open_paren")

			temp = Range()
			#range would only exist if open_pos is set, bc paren or bracket required to open
			if open_pos is not None:
				close_pos = None
				if self.find_type("close_bracket") != -1:
					close_pos = self.find_type("close_bracket")
				elif self.find_type("close_paren") != -1:
					close_pos = self.find_type("close_paren")

				if close_pos is None:
					raise Exception("range not closed")

				#numbers are right after/before the symbol
				temp.start = int(self.children[open_pos + 1].data[0])
				temp.end = int(self.children[close_pos - 1].data[0])

				#adjust bounds to be inclusive start and exclusive end
				if self.children[open_pos].type == "open_paren":
					temp.start += 1
				if self.children[close_pos].type == "close_bracket":
					temp.end += 1

				self.children = self.children[:open_pos] + [temp] + self.children[close_pos + 1:]
			else:
				#MAGIC default range of [1, 2) aka exactly 1 element
				temp.start = 1
				temp.end = 2

				#MAGIC should be in second position (bc after member name)
				self.children = self.children[:1] + [temp] + self.children[1:]

		for x in self.iterator():
			if x is not None:
				x.collapse_ranges()

	def collapse_types(self):
		if self.type == "type":
			#MAGIC should have at least a base/aggregate/anon type and a range. at most type, range, and struct/enum/union description
			if len(self.children) not in range(2, 3 + 1):
				raise Exception("incorrect num of children")

			temp = Type()
			temp.type = Type_t.from_str(self.children[0].data[0])
			temp.range = self.children[1]

			#handle anon type
			if temp.type == Type_t._:
				#if self.range is not the default range from collapse_ranges()
				if temp.range.start != 1 or temp.range.end != 2:
					raise Exception("anon type has range")
				temp.range = None

			#extract children from brace pack
			temp.rest = self.children[2].children if len(self.children) > 2 else None

			self.children = [temp]

		for x in self.iterator():
			if x is not None:
				x.collapse_types()

	def collapse_hashes(self):
		if self.type == "hash":
			temp = Hash()
			temp.hash = self.data[0]

			self.children = [temp]

		for x in self.iterator():
			if x is not None:
				x.collapse_hashes()

	def collapse_members(self):
		if self.type == "member":
			#MAGIC should have name and type or at_sign and hash
			if len(self.children) != 2:
				raise Exception("incorrect num of children")

			temp = None
			if self.children[1].type == "hash":
				temp = Forward_type()
				temp.hash = self.children[1].data[0]
			else:
				temp = Member()
				temp.name = self.children[0].data[0]
				temp.type = self.children[1].children[0]

			self.children = [temp]

		for x in self.iterator():
			if x is not None:
				x.collapse_members()

	def collapse_aggregates(self):
		if self.type == "bbb":
			temp = Aggregate()
			temp.elements = []

			for x in self.children:
				if x.type == "member":
					temp.elements.append(x.children[0])
				elif x.type == "hash":
					temp.elements.append(x.children[0])
				else:
					raise Exception("invalid child type: {}".format(x.type.encode("utf-8")))

			self.children = [temp]
		elif type(self) == Member and self.type.type in Type_t.aggregate:
			temp = Aggregate()
			temp.elements = [x.children[0] for x in self.type.rest]

			self.type.rest = [temp]

		for x in self.iterator():
			if x is not None:
				x.collapse_aggregates()

	def fully_resolved(self):
		for x in self.iterator():
			if x is not None:
				if not x.fully_resolved():
					return False

		return True

	def resolve(self, hash_to_ast):
		for x in self.iterator():
			if x is not None:
				x.resolve(hash_to_ast)

class Range(Pack):
	@override_enforce
	def __init__(self):
		super().__init__()
		#inclusive
		self.start = 0
		#exclusive
		self.end = 0

	def __repr__(self):
		return "[{}, {})".format(self.start, self.end)

	@override
	def validate(self):
		if self.start >= self.end:
			raise Exception("range [{}, {}) is empty".format(self.start, self.end))

	@override
	def iterator(self):
		yield None

	#reflects size of count (read: num of elements), not actual bytes
	@override
	def min_size(self):
		return self.start

	#^
	#inclusive. not exclusive like self.end
	@override
	def max_size(self):
		return self.end - 1

class Hash(Pack):
	@override_enforce
	def __init__(self):
		super().__init__()
		self.hash = None

	def __repr__(self):
		return "{}".format(self.hash)

	@override
	def validate(self):
		#TODO make a better check. should actually hash the canon data and compare, if this is hash of the file
		if self.hash is None:
			raise Exception()

	@override
	def iterator(self):
		yield None

	@override
	def min_size(self):
		return self.max_size()

	@override
	def max_size(self):
		return 16

class Type_t_internal(enum.Enum):
	u1 = enum.auto()
	u8 = enum.auto()
	u16 = enum.auto()
	u32 = enum.auto()
	u64 = enum.auto()
	i8 = enum.auto()
	i16 = enum.auto()
	i32 = enum.auto()
	i64 = enum.auto()
	_ = enum.auto()
	struct = enum.auto()
	enum_ = enum.auto()
	union = enum.auto()

	def __str__(self):
		return Type_t.to_str(self)

class Type_t:
	u1 = Type_t_internal.u1
	u8 = Type_t_internal.u8
	u16 = Type_t_internal.u16
	u32 = Type_t_internal.u32
	u64 = Type_t_internal.u64
	i8 = Type_t_internal.i8
	i16 = Type_t_internal.i16
	i32 = Type_t_internal.i32
	i64 = Type_t_internal.i64
	_ = Type_t_internal._
	struct = Type_t_internal.struct
	enum = Type_t_internal.enum_
	union = Type_t_internal.union

	primitive = [u1, u8, u16, u32, u64, i8, i16, i32, i64]
	aggregate = [struct, enum, union]

	all = [*primitive, _, *aggregate]

	type_to_str = {
		u1: "u1",
		u8: "u8",
		u16: "u16",
		u32: "u32",
		u64: "u64",
		i8: "i8",
		i16: "i16",
		i32: "i32",
		i64: "i64",
		_: "_",
		struct: "struct",
		enum: "enum",
		union: "union"
	}

	str_to_type = {v: k for k, v in type_to_str.items()}

	@classmethod
	def to_str(self, data):
		return self.type_to_str[data]

	@classmethod
	def from_str(self, data):
		return self.str_to_type[data]

class Type(Pack):
	@override_enforce
	def __init__(self):
		super().__init__()
		self.type = None
		self.range = Range()
		self.rest = None

	def __repr__(self):
		if self.rest is not None:
			return "{} {} {{{}}}".format(self.type, self.range, " ".join([x.__repr__() for x in self.rest]))
		elif self.range is not None:
			return "{} {}".format(self.type, self.range)
		else:
			return self.name

	@override
	def validate(self):
		#anonymous type
		if self.type == Type_t._:
			if self.range is not None or self.rest is not None:
				raise Exception("anonymous type has extra info")
			return

		#aggregate and base types
		if self.type in Type_t.primitive + Type_t.aggregate:
			self.range.validate()

			if self.rest is not None:
				for x in self.rest:
					x.validate()
		else:
			raise Exception("invalid type: {}".format(self.type))

	@override
	def iterator(self):
		if self.range is not None:
			yield self.range
		if self.rest is not None:
			for x in self.rest:
				yield x

	@staticmethod
	def store_num_in_bits(num):
		ret = 0
		temp = num
		while temp != 1:
			temp //= 2
			ret += 1

		if 2**ret < num:
			ret += 1

		return ret

	@staticmethod
	def store_bits_in_bytes(bits):
		return bits // 8 + (1 if bits % 8 else 0)

	@override
	def min_size(self):
		base_size = 0
		overhead = 0

		if self.type == Type_t._:
			return 0
		elif self.type == Type_t.struct:
			base_size = sum([x.min_size() for x in self.rest])
		elif self.type == Type_t.enum:
			base_size = min([x.min_size() for x in self.rest])

			#MAGIC need 2 extra bits to indicate how many additional bytes we need to read enum size
			overhead = self.store_bits_in_bytes(2 + self.store_num_in_bits(len(self.rest)))
		elif self.type == Type_t.union:
			base_size = 0

			#MAGIC 1 bit per element
			overhead = self.store_bits_in_bytes(len(self.rest))
		elif self.type == Type_t.u1:
			#bit packing calculated below
			pass
		elif self.type in [Type_t.u8, Type_t.i8]:
			base_size = 1
		elif self.type in [Type_t.u16, Type_t.i16]:
			base_size = 2
		elif self.type in [Type_t.u32, Type_t.i32]:
			base_size = 4
		elif self.type in [Type_t.u64, Type_t.i64]:
			base_size = 8
		else:
			raise Exception("invalid type: {}".format(self.type))

		count_overhead = self.store_bits_in_bytes(self.store_num_in_bits(self.range.max_size() - self.range.min_size() + 1))

		if self.type != Type_t.u1:
			ret = self.range.min_size() * (base_size + overhead) + count_overhead
		else:
			ret = self.store_bits_in_bytes(self.range.min_size()) + count_overhead

		if debug_sizes:
			print(self.__repr__(), ret, "|", self.range.min_size(), base_size, overhead, count_overhead)
		return ret

	@override
	def max_size(self):
		base_size = 0
		overhead = 0

		if self.type == Type_t._:
			return 0
		elif self.type == Type_t.struct:
			base_size = sum([x.max_size() for x in self.rest])
		elif self.type == Type_t.enum:
			base_size = max([x.max_size() for x in self.rest])

			#MAGIC need 2 extra bits to indicate how many additional bytes we need to read enum size
			overhead = self.store_bits_in_bytes(2 + self.store_num_in_bits(len(self.rest)))
		elif self.type == Type_t.union:
			base_size = sum([x.max_size() for x in self.rest])

			#MAGIC 1 bit per element
			overhead = self.store_bits_in_bytes(len(self.rest))
		elif self.type == Type_t.u1:
			#bit packing calculated below
			pass
		elif self.type in [Type_t.u8, Type_t.i8]:
			base_size = 1
		elif self.type in [Type_t.u16, Type_t.i16]:
			base_size = 2
		elif self.type in [Type_t.u32, Type_t.i32]:
			base_size = 4
		elif self.type in [Type_t.u64, Type_t.i64]:
			base_size = 8
		else:
			raise Exception("invalid type: {}".format(self.type))

		count_overhead = self.store_bits_in_bytes(self.store_num_in_bits(self.range.max_size() - self.range.min_size() + 1))

		if self.type != Type_t.u1:
			ret = self.range.max_size() * (base_size + overhead) + count_overhead
		else:
			ret = self.store_bits_in_bytes(self.range.max_size()) + count_overhead

		if debug_sizes:
			print(self.__repr__(), ret, "|", self.range.max_size(), base_size, overhead, count_overhead)
		return ret

class Member(Pack):
	@override_enforce
	def __init__(self):
		super().__init__()
		self.name = ""
		self.type = Type()

	def __repr__(self):
		return "{}: {}".format(self.name, self.type)

	@override
	def validate(self):
		#not anonymous name, aka specific name
		if self.name != "_":
			name_re = re.compile("^[a-zaA-Z0-9][a-z0-9_]*$")
			if not name_re.search(self.name):
				raise Exception("invalid member name: {}".format(self.name.encode("utf-8")))

		self.type.validate()

	@override
	def iterator(self):
		yield self.type

	@override
	def min_size(self):
		return self.type.min_size()

	@override
	def max_size(self):
		return self.type.max_size()

class Aggregate(Pack):
	@override_enforce
	def __init__(self):
		super().__init__()
		self.elements = []

	def __repr__(self):
		return " ".join([x.__repr__() for x in self.elements])

	@override
	def validate(self):
		#aggregate must have at least one element
		if not len(self.elements):
			raise Exception("empty aggregate")

		member_names = [x.name for x in self.elements if type(x) == Member]
		specific_names = [x for x in member_names if x != "_"]

		if len(set(specific_names)) != len(specific_names):
			name_count = {}
			for x in specific_names:
				if x not in name_count:
					name_count[x] = 0
				name_count[x] += 1

			dupe_names = [k for k, v in name_count.items() if v > 1]

			raise Exception("redefinition of member {} in aggregate".format(dupe_names[0].encode("utf-8")))

		for x in self.elements:
			x.validate()

	@override
	def iterator(self):
		for x in self.elements:
			yield x

	@override
	def min_size(self):
		return sum([x.min_size() for x in self.elements])

	@override
	def max_size(self):
		return sum([x.max_size() for x in self.elements])

	@override
	def resolve(self, hash_to_ast):
		mutated = False

		for i in range(len(self.elements)):
			if type(self.elements[i]) == Forward_type and self.elements[i].hash in hash_to_ast:
				mutated = True
				self.elements[i] = hash_to_ast[self.elements[i].hash]

		if mutated:
			self.elements = [[x] if type(x) != list else x for x in self.elements]
			self.elements = [y for x in self.elements for y in x]

		for x in self.iterator():
			if x is not None:
				x.resolve(hash_to_ast)


class Forward_type(Pack):
	@override_enforce
	def __init__(self):
		super().__init__()
		self.hash = None

	def __repr__(self):
		return "@{}".format(self.hash)

	@override
	def validate(self):
		#TODO make a better check (incl check no conflict on member names)
		if self.hash is None:
			raise Exception()

	@override
	def iterator(self):
		yield None

	@override
	def min_size(self):
		#TODO retrieve size from type
		ret = 0

		if debug_sizes:
			print(self.__repr__(), ret, "|", 1, ret, 0, 0)
		return ret

	@override
	def max_size(self):
		#TODO retrieve size from type
		ret = math.inf

		if debug_sizes:
			print(self.__repr__(), ret, "|", 1, ret, 0, 0)
		return ret

	@override
	def fully_resolved(self):
		return False

class Basic_listener(Listener):
	@override_enforce
	def __init__(self):
		self.data = []
		self.curr = Pack()

	def __repr__(self):
		return "Basic_listener({}, {})".format(self.data, self.curr)

	def push(self):
		self.data.append(self.curr)
		self.curr = Pack()

	def pop(self):
		self.data[-1].children.append(self.curr)
		self.data, self.curr = self.data[:-1], self.data[-1]

	@override
	def enterBasic_binary_buffer(self, ctx):
		self.curr.set_type("bbb")

	@override
	def exitBasic_binary_buffer(self, ctx):
		pass

	@override
	def enterOpen_brace(self, ctx):
		self.push()
		self.curr.set_type("brace")

	@override
	def enterClose_brace(self, ctx):
		self.pop()

#NOTE autogen vvv
	@override
	def enterMember_name(self, ctx):
		self.push()
		self.curr.set_type("member_name")

	@override
	def exitMember_name(self, ctx):
		self.curr.add_data(ctx.getText())
		self.pop()

	@override
	def enterBase_type(self, ctx):
		self.push()
		self.curr.set_type("base_type")

	@override
	def exitBase_type(self, ctx):
		self.curr.add_data(ctx.getText())
		self.pop()

	@override
	def enterAggregate_type(self, ctx):
		self.push()
		self.curr.set_type("aggregate_type")

	@override
	def exitAggregate_type(self, ctx):
		self.curr.add_data(ctx.getText())
		self.pop()

	@override
	def enterHash_(self, ctx):
		self.push()
		self.curr.set_type("hash")

	@override
	def exitHash_(self, ctx):
		self.curr.add_data(ctx.getText())
		self.pop()

	@override
	def enterOpen_paren(self, ctx):
		self.push()
		self.curr.set_type("open_paren")

	@override
	def exitOpen_paren(self, ctx):
		self.curr.add_data(ctx.getText())
		self.pop()

	@override
	def enterClose_paren(self, ctx):
		self.push()
		self.curr.set_type("close_paren")

	@override
	def exitClose_paren(self, ctx):
		self.curr.add_data(ctx.getText())
		self.pop()

	@override
	def enterOpen_bracket(self, ctx):
		self.push()
		self.curr.set_type("open_bracket")

	@override
	def exitOpen_bracket(self, ctx):
		self.curr.add_data(ctx.getText())
		self.pop()

	@override
	def enterClose_bracket(self, ctx):
		self.push()
		self.curr.set_type("close_bracket")

	@override
	def exitClose_bracket(self, ctx):
		self.curr.add_data(ctx.getText())
		self.pop()

	@override
	def enterCanon_natural_num(self, ctx):
		self.push()
		self.curr.set_type("canon_natural_num")

	@override
	def exitCanon_natural_num(self, ctx):
		self.curr.add_data(ctx.getText())
		self.pop()

	@override
	def enterUnderscore(self, ctx):
		self.push()
		self.curr.set_type("underscore")

	@override
	def exitUnderscore(self, ctx):
		self.curr.add_data(ctx.getText())
		self.pop()

	@override
	def enterAt_sign(self, ctx):
		self.push()
		self.curr.set_type("at_sign")

	@override
	def exitAt_sign(self, ctx):
		self.curr.add_data(ctx.getText())
		self.pop()

	@override
	def enterMember(self, ctx):
		self.push()
		self.curr.set_type("member")

	@override
	def exitMember(self, ctx):
		self.pop()

	@override
	def enterType_(self, ctx):
		self.push()
		self.curr.set_type("type")

	@override
	def exitType_(self, ctx):
		self.pop()
#^^^

#debug only
def dump_pack(data, level = 0):
	prefix = "\t" * level

	try:
		print(prefix + str(data.type) + str(data.data))

		for x in data.children:
			dump_pack(x, level + 1)
	except AttributeError:
		print(prefix + str(data))

def simplify_pack(data):
	#TODO document implicit dependencies
	data.collapse_ranges()
	data.collapse_types()
	data.collapse_hashes()
	data.collapse_members()
	data.collapse_aggregates()

def main(stats):
	data = Stream_stdin()
	lexer = Lexer(data)
	tokens = Token_stream(lexer)

	parser = Parser(tokens)
	listener = Basic_listener()
	parser.addParseListener(listener)

	parser.basic_binary_buffer()
	data = listener.curr

	if debug_ast:
		dump_pack(data)

	simplify_pack(data)

	if debug_ast:
		print("###########################")
		print(data)

	data = data.children[0]
	print(data)

	data.validate()

	if stats:
		print("min size: {} bytes".format(data.min_size()))
		print("max size: {} bytes".format(data.max_size()))

if __name__ == "__main__":
	stats = False

	if len(sys.argv) >= 2 and sys.argv[1] == "stats":
		stats = True

	main(stats)
