import sys

#TODO maybe move Type_t out of dump_tree
import dump_tree

g_primitive_types = set([str(x) for x in dump_tree.Type_t.primitive])

def field_enum_str(vars):
	ret_template = """
	class Field_t(enum.IntEnum):
		DUMMY = -1
%frag%
		SIZE = enum.auto()

	field_t_underlying_type = Bbb.Int.Type_t.%underlying%"""[1:]

	member_template = """
		m_%var% = enum.auto()"""[1:]

	#MAGIC +1 to account for "SIZE"
	underlying_type = "u64"
	underlying_type = "u32" if len(vars) + 1 <= 2**32 else underlying_type
	underlying_type = "u16" if len(vars) + 1 <= 2**16 else underlying_type
	underlying_type = "u8" if len(vars) + 1 <= 2**8 else underlying_type

	return (ret_template
		.replace(
			"%frag%",
			"\n".join([
				member_template
					.replace("%var%", x[1])
				for x in vars
			])
		)
		.replace("%underlying%", underlying_type)
	)

def union_str(id_, name, vars, size_bounds):
	class_decl_template = """
class %%(Bbb.Serdes_base):
%field_enum%

	def __init__(self):
		self.keys = [False] * self.Field_t.SIZE
		self.vals = {}

	@property
	def id(self):
%id%

	@property
	def min_size(self):
		return %min_size%

	@property
	def max_size(self):
		return %max_size%

	def unset(self):
%unset_frag%

%class_decl_frag%

	def check(self, field):
		if type(field) != self.Field_t:
			raise Exception()

		return self.keys[field.value]

	def curr_fields(self):
		return [self.Field_t(i) for i, x in enumerate(self.keys) if x]

	def internal_serialize(self, ret):
		ret += bytearray(Bbb.vec_bool_to_vec_u8(self.keys))

%serialize_frag%

	def internal_deserialize(self, data, pos):
		self.unset()

		temp, pos = Bbb.read(data, pos, Bbb.calc_bit_packing_num_bytes(self.Field_t.SIZE))
		self.keys = Bbb.vec_u8_to_vec_bool(temp, self.Field_t.SIZE)

%deserialize_key_frag%

%deserialize_frag%

		return pos"""[1:]

	id_frag_template = """
		return bytes([%bytes%])"""[1:]

	unset_frag_template = """
		self.unset_%var%()"""[1:]

	class_decl_frag_template = """
	def set_%var%(self):
		if not self.keys[%index%]:
			self.keys[%index%] = True
			self.vals[%index%] = %default_init%

	def unset_%var%(self):
		if self.keys[%index%]:
			self.keys[%index%] = False
			del self.vals[%index%]

	@property
	def get_%var%(self):
		if not self.keys[%index%]:
			raise Exception()

		return self.vals[%index%]

	@get_%var%.setter
	def get_%var%(self, rhs):
		if not self.keys[%index%]:
			raise Exception()

		self.vals[%index%] = rhs"""[1:]

	anon_funcs_template = """
	def set_%var%(self):
		if not self.keys[%index%]:
			self.keys[%index%] = True

	def unset_%var%(self):
		if self.keys[%index%]:
			self.keys[%index%] = False"""[1:]

	internal_serialize_primitive_frag_template = """
		if self.keys[%index%]:
			Bbb.primitive_serialize(%type%, self.vals[%index%], ret)"""[1:]

	internal_serialize_nonprimitive_frag_template = """
		if self.keys[%index%]:
			self.vals[%index%].internal_serialize(ret)"""[1:]

	internal_serialize_array_frag_template = """
		if self.keys[%index%]:
			Bbb.vec_serialize(%type%, %min%, %max%, ret, self.vals[%index%])"""[1:]

	internal_deserialize_key_frag_template = """
		if self.keys[%index%]:
			self.keys[%index%] = False
			self.set_%var%()"""[1:]

	internal_deserialize_primitive_frag_template = """
		if self.keys[%index%]:
			self.vals[%index%], pos = Bbb.primitive_deserialize(%type%, data, pos)"""[1:]

	internal_deserialize_nonprimitive_frag_template = """
		if self.keys[%index%]:
			pos = self.vals[%index%].internal_deserialize(data, pos)"""[1:]

	internal_deserialize_array_frag_template = """
		if self.keys[%index%]:
			self.vals[%index%], pos = Bbb.vec_deserialize(%type%, %min%, %max%, data, pos)"""[1:]

	ret = []

	ret.append(
		class_decl_template
			.replace(
				"%unset_frag%",
				"\n".join([
					unset_frag_template
						.replace("%var%", x[1])
					for x in vars
				])
			)
			.replace(
				"%class_decl_frag%",
				"\n\n".join([
					[class_decl_frag_template, anon_funcs_template][x[0] == "_"]
						.replace("%var%", x[1])
						.replace("%index%", str(i))
						.replace("%default_init%", ("0" if x[0] in g_primitive_types else "Bbb_types.{}()".format(x[0])) if len(x) < 3 else "[]")
					for i, x in enumerate(vars)
				])
			)
			.replace(
				"%serialize_frag%",
				"\n".join([
					[internal_serialize_primitive_frag_template, internal_serialize_nonprimitive_frag_template, internal_serialize_array_frag_template][(0 if x[0] in g_primitive_types else 1) if len(x) < 3 else 2]
						.replace("%index%", str(i))
						.replace("%var%", x[1])
						.replace("%type%", "Bbb_types.{}".format(x[0]) if x[0] not in g_primitive_types else "Bbb.Int.Type_t.{}".format(x[0]))
						.replace("%min%", "" if len(x) < 3 else str(x[2]))
						.replace("%max%", "" if len(x) < 3 else str(x[3]))
					for i, x in enumerate(vars)
					if x[0] != "_"
				])
			)
			.replace(
				"%deserialize_key_frag%",
				"\n".join([
					internal_deserialize_key_frag_template
						.replace("%index%", str(i))
						.replace("%var%", x[1])
					for i, x in enumerate(vars)
					if x[0] != "_"
				])
			)
			.replace(
				"%deserialize_frag%",
				"\n".join([
					[internal_deserialize_primitive_frag_template, internal_deserialize_nonprimitive_frag_template, internal_deserialize_array_frag_template][(0 if x[0] in g_primitive_types else 1) if len(x) < 3 else 2]
						.replace("%index%", str(i))
						.replace("%var%", x[1])
						.replace("%type%", "Bbb_types.{}".format(x[0]) if x[0] not in g_primitive_types else "Bbb.Int.Type_t.{}".format(x[0]))
						.replace("%min%", "" if len(x) < 3 else str(x[2]))
						.replace("%max%", "" if len(x) < 3 else str(x[3]))
					for i, x in enumerate(vars)
					if x[0] != "_"
				])
			)
			.replace(
				"%id%",
				id_frag_template
					.replace("%bytes%", ", ".join(["0x{:02x}".format(x) for x in id_]))
			)
			.replace("%min_size%", str(size_bounds[0]))
			.replace("%max_size%", str(size_bounds[1]))
			.replace("%%", name)
			.replace("%field_enum%", field_enum_str(vars))
	)

	return "\n\n".join(ret)

def enum_str(id_, name, vars, size_bounds):
	class_decl_template = """
class %%(Bbb.Serdes_base):
%field_enum%

	def __init__(self):
		self.field_num = -1
		self.field = None

	@property
	def id(self):
%id%

	@property
	def min_size(self):
		return %min_size%

	@property
	def max_size(self):
		return %max_size%

	def unset(self):
		if self.field_num != -1:
			[
%unset_frag%
			][self.field_num]()

%class_decl_frag%

	def internal_serialize(self, ret):
		if self.field_num == -1:
			raise Exception()

		Bbb.primitive_serialize(self.field_t_underlying_type, self.field_num, ret)

		if False:
			pass
%serialize_frag%

	def check(self, field):
		if type(field) != self.Field_t:
			raise Exception()

		return self.field_num == field.value

	def curr_field(self):
		return self.Field_t(self.field_num) if self.field_num != -1 else None

	def internal_deserialize(self, data, pos):
		self.unset()

		self.field_num, pos = Bbb.primitive_deserialize(self.field_t_underlying_type, data, pos)

		if self.field_num >= self.Field_t.SIZE:
			raise Exception()

		if False:
			pass
%deserialize_frag%

		return pos"""[1:]

	id_frag_template = """
		return bytes([%bytes%])"""[1:]

	unset_frag_template = """
				self.unset_%var%,"""[1:]

	class_decl_frag_template = """
	def set_%var%(self):
		if self.field_num == -1:
			self.field_num = %index%
			self.field = %default_init%

	def unset_%var%(self):
		if self.field_num == %index%:
			self.field_num = -1
			self.field = None

	@property
	def get_%var%(self):
		if self.field_num != %index%:
			raise Exception()

		return self.field

	@get_%var%.setter
	def get_%var%(self, rhs):
		if self.field_num != %index%:
			raise Exception()

		self.field = rhs"""[1:]

	anon_funcs_template = """
	def set_%var%(self):
		if self.field_num == -1:
			self.field_num = %index%

	def unset_%var%(self):
		if self.field_num == %index%:
			self.field_num = -1"""[1:]

	internal_serialize_primitive_frag_template = """
		elif self.field_num == %index%:
			Bbb.primitive_serialize(%type%, self.field, ret)"""[1:]

	internal_serialize_nonprimitive_frag_template = """
		elif self.field_num == %index%:
			self.field.internal_serialize(ret)"""[1:]

	internal_serialize_array_frag_template = """
		elif self.field_num == %index%:
			Bbb.vec_serialize(%type%, %min%, %max%, ret, self.field)"""[1:]

	internal_deserialize_primitive_frag_template = """
		elif self.field_num == %index%:
			self.field, pos = Bbb.primitive_deserialize(%type%, data, pos)"""[1:]

	internal_deserialize_nonprimitive_frag_template = """
		elif self.field_num == %index%:
			pos = self.field.internal_deserialize(data, pos)"""[1:]

	internal_deserialize_array_frag_template = """
		elif self.field_num == %index%:
			self.field, pos = Bbb.vec_deserialize(%type%, %min%, %max%, data, pos)"""[1:]

	ret = []

	ret.append(
		class_decl_template
			.replace(
				"%unset_frag%",
				"\n".join([
					unset_frag_template
						.replace("%var%", x[1])
					for x in vars
				])
			)
			.replace(
				"%class_decl_frag%",
				"\n\n".join([
					[class_decl_frag_template, anon_funcs_template][x[0] == "_"]
						.replace("%var%", x[1])
						.replace("%index%", str(i))
						.replace("%default_init%", ("0" if x[0] in g_primitive_types else "Bbb_types.{}()".format(x[0])) if len(x) < 3 else "[]")
					for i, x in enumerate(vars)
				])
			)
			.replace(
				"%serialize_frag%",
				"\n".join([
					[internal_serialize_primitive_frag_template, internal_serialize_nonprimitive_frag_template, internal_serialize_array_frag_template][(0 if x[0] in g_primitive_types else 1) if len(x) < 3 else 2]
						.replace("%index%", str(i))
						.replace("%var%", x[1])
						.replace("%type%", "Bbb_types.{}".format(x[0]) if x[0] not in g_primitive_types else "Bbb.Int.Type_t.{}".format(x[0]))
						.replace("%min%", "" if len(x) < 3 else str(x[2]))
						.replace("%max%", "" if len(x) < 3 else str(x[3]))
					for i, x in enumerate(vars)
					if x[0] != "_"
				])
			)
			.replace(
				"%deserialize_frag%",
				"\n".join([
					[internal_deserialize_primitive_frag_template, internal_deserialize_nonprimitive_frag_template, internal_deserialize_array_frag_template][(0 if x[0] in g_primitive_types else 1) if len(x) < 3 else 2]
						.replace("%index%", str(i))
						.replace("%var%", x[1])
						.replace("%type%", "Bbb_types.{}".format(x[0]) if x[0] not in g_primitive_types else "Bbb.Int.Type_t.{}".format(x[0]))
						.replace("%min%", "" if len(x) < 3 else str(x[2]))
						.replace("%max%", "" if len(x) < 3 else str(x[3]))
					for i, x in enumerate(vars)
					if x[0] != "_"
				])
			)
			.replace(
				"%id%",
				id_frag_template
					.replace("%bytes%", ", ".join(["0x{:02x}".format(x) for x in id_]))
			)
			.replace("%min_size%", str(size_bounds[0]))
			.replace("%max_size%", str(size_bounds[1]))
			.replace("%%", name)
			.replace("%field_enum%", field_enum_str(vars))
	)

	return "\n\n".join(ret)

def struct_str(id_, name, vars, size_bounds):
	class_decl_template = """
class %%(Bbb.Serdes_base):
%field_enum%

	def __init__(self):
%member_frag%

	@property
	def id(self):
%id%

	@property
	def min_size(self):
		return %min_size%

	@property
	def max_size(self):
		return %max_size%

%class_decl_frag%

	def internal_serialize(self, ret):
%serialize_frag%

	def internal_deserialize(self, data, pos):
%deserialize_frag%

		return pos"""[1:]

	id_frag_template = """
		return bytes([%bytes%])"""[1:]

	class_decl_frag_template = """
	@property
	def get_%var%(self):
		return self.var_%var%

	@get_%var%.setter
	def get_%var%(self, rhs):
		self.var_%var% = rhs"""[1:]

	class_decl_member_frag_template = """
		self.var_%var% = %default_init%"""[1:]

	internal_serialize_primitive_frag_template = """
		Bbb.primitive_serialize(%type%, self.var_%var%, ret)"""[1:]

	internal_serialize_nonprimitive_frag_template = """
		self.var_%var%.internal_serialize(ret)"""[1:]

	internal_serialize_array_frag_template = """
		Bbb.vec_serialize(%type%, %min%, %max%, ret, self.var_%var%)"""[1:]

	internal_deserialize_primitive_frag_template = """
		self.var_%var%, pos = Bbb.primitive_deserialize(%type%, data, pos)"""[1:]

	internal_deserialize_nonprimitive_frag_template = """
		pos = self.var_%var%.internal_deserialize(data, pos)"""[1:]

	internal_deserialize_array_frag_template = """
		self.var_%var%, pos = Bbb.vec_deserialize(%type%, %min%, %max%, data, pos)"""[1:]

	ret = []

	ret.append(
		class_decl_template
			.replace(
				"%class_decl_frag%",
				"\n\n".join([
					class_decl_frag_template
						.replace("%var%", x[1])
					for x in vars
					if x[0] != "_"
				])
			)
			.replace(
				"%member_frag%",
				"\n".join([
					class_decl_member_frag_template
						.replace("%var%", x[1])
						.replace("%default_init%", ("0" if x[0] in g_primitive_types else "Bbb_types.{}()".format(x[0])) if len(x) < 3 else "[]")
					for x in vars
					if x[0] != "_"
				])
			)
			.replace(
				"%serialize_frag%",
				"\n\n".join([
					[internal_serialize_primitive_frag_template, internal_serialize_nonprimitive_frag_template, internal_serialize_array_frag_template][(0 if x[0] in g_primitive_types else 1) if len(x) < 3 else 2]
						.replace("%var%", x[1])
						.replace("%type%", "Bbb_types.{}".format(x[0]) if x[0] not in g_primitive_types else "Bbb.Int.Type_t.{}".format(x[0]))
						.replace("%min%", "" if len(x) < 3 else str(x[2]))
						.replace("%max%", "" if len(x) < 3 else str(x[3]))
					for x in vars
					if x[0] != "_"
				])
			)
			.replace(
				"%deserialize_frag%",
				"\n\n".join([
					[internal_deserialize_primitive_frag_template, internal_deserialize_nonprimitive_frag_template, internal_deserialize_array_frag_template][(0 if x[0] in g_primitive_types else 1) if len(x) < 3 else 2]
						.replace("%var%", x[1])
						.replace("%type%", "Bbb_types.{}".format(x[0]) if x[0] not in g_primitive_types else "Bbb.Int.Type_t.{}".format(x[0]))
						.replace("%min%", "" if len(x) < 3 else str(x[2]))
						.replace("%max%", "" if len(x) < 3 else str(x[3]))
					for x in vars
					if x[0] != "_"
				])
			)
			.replace(
				"%id%",
				id_frag_template
					.replace("%bytes%", ", ".join(["0x{:02x}".format(x) for x in id_]))
			)
			.replace("%min_size%", str(size_bounds[0]))
			.replace("%max_size%", str(size_bounds[1]))
			.replace("%%", name)
			.replace("%field_enum%", field_enum_str(vars))
	)

	return "\n\n".join(ret)

def indent_newline_str(data, size):
	indent = "\t" * size

	return "\n".join([
		indent + x if len(x) else x
		for x in data.split("\n")
	])

def spec_str(struct_enum_union):
	ret_template = """
#TODO figure out a way to do raw includes like c++
from lib_bbb import enum, Bbb

class Bbb_types:
%struct_enum_union_frag%"""[1:]

	return (ret_template
		.replace(
			"%struct_enum_union_frag%",
			indent_newline_str(
				"\n\n".join([
					[struct_str, enum_str, union_str][dump_tree.Type_t.aggregate.index(x[0])](
						*x[1:]
					)
					for x in struct_enum_union
				]),
				1
			)
		)
	)

if __name__ == "__main__":
	#TODO fix missing size bounds
	#TODO move to dedicated test suite script
	if len(sys.argv) == 1:
		vars_ = [
			["u8", "a"],
			["i8", "b"],
			["u64", "d"],
			["u8", "e", 0, 20],
			["_", "x"],
			["u1", "_0"],
			["_", "_1"]
		]

		print(spec_str([
			["union", b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f", "X", vars_],
			["enum", b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f", "Y", vars_],
			["struct", b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f", "Z", vars_]
		]))
