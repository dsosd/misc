import enum

class Bbb:
	def read_check(data, pos, size):
		if len(data) < pos + size:
			raise Exception()

	def read(data, pos, size):
		Bbb.read_check(data, pos, size)

		return data[pos:pos + size], pos + size

	class Int:
		class Type_t(enum.Enum):
			u1 = enum.auto()
			u8 = enum.auto()
			u16 = enum.auto()
			u32 = enum.auto()
			u64 = enum.auto()
			i8 = enum.auto()
			i16 = enum.auto()
			i32 = enum.auto()
			i64 = enum.auto()

		def __init__(self, type_, val = 0):
			if type(type_) != self.Type_t:
				raise Exception()

			if type_ == self.Type_t.u1 and type(val) == bool:
				val = int(val)

			if type(val) != int:
				raise Exception()

			self.type = type_
			self.val = val

			self.force_into_range()

		def get_byte_count(self):
			return {
				self.Type_t.u1: 1,
				self.Type_t.u8: 1,
				self.Type_t.u16: 2,
				self.Type_t.u32: 4,
				self.Type_t.u64: 8,
				self.Type_t.i8: 1,
				self.Type_t.i16: 2,
				self.Type_t.i32: 4,
				self.Type_t.i64: 8
			}[self.type]

		def get_range(self):
			return {
				self.Type_t.u1: [0, 2**1],
				self.Type_t.u8: [0, 2**8],
				self.Type_t.u16: [0, 2**16],
				self.Type_t.u32: [0, 2**32],
				self.Type_t.u64: [0, 2**64],
				self.Type_t.i8: [-2**7, 2**7],
				self.Type_t.i16: [-2**15, 2**15],
				self.Type_t.i32: [-2**31, 2**31],
				self.Type_t.i64: [-2**63, 2**63]
			}[self.type]

		def force_into_range(self):
			range_ = self.get_range()
			self.val %= range_[1] - range_[0]

			#shift signed ints to negative range on overflow
			if self.val >= range_[1]:
				self.val -= range_[1] - range_[0]

		def primitive_serialize(self, ret):
			self.force_into_range()

			val = self.val
			#rely on 2's complement and ensure val is non-negative
			range_ = self.get_range()
			val %= range_[1] - range_[0]

			ret += bytearray([
				val >> (self.get_byte_count() - 1 - i) * 8 & 0xff
				for i in range(self.get_byte_count())
			])

		def primitive_deserialize(self, data, pos):
			temp, pos = Bbb.read(data, pos, self.get_byte_count())

			self.val = sum([
				temp[i] << (self.get_byte_count() - 1 - i) * 8
				for i in range(self.get_byte_count())
			])

			self.force_into_range()

			if self.type == self.Type_t.u1:
				self.val = bool(self.val)

			return pos

	def calc_bit_packing_num_bytes(bits):
		return bits // 8 + (bits % 8 > 0)

	def vec_bool_to_vec_u8(data):
		bytes_ = len(data) // 8

		ret = [
			sum([
				x << (7 - j)
				for j, x in enumerate(data[i*8:(i + 1)*8])
			])
			for i in range(bytes_)
		]

		if len(data) % 8:
			ret.append(
				sum([
					x << (7 - j)
					#MAGIC pad right side with False up to 7 times to ensure at least 8 elements
					for j, x in enumerate([*data[bytes_*8:(bytes_ + 1)*8], *[False] * 7][:8])
				])
			)

		return ret

	def vec_u8_to_vec_bool(data, expected_size):
		if len(data) != expected_size // 8 + (expected_size % 8 > 0):
			raise Exception()

		ret = [
			[1 << (7 - i) & x > 0 for i in range(8)]
			for x in data
		]

		ret = [y for x in ret for y in x]

		if expected_size % 8:
			if any(ret[-(expected_size % 8):]):
				raise Exception()

			return ret[:expected_size % 8]
		else:
			return ret

	def type_check(val, expected_type_id):
		if type(expected_type_id) == Bbb.Int.Type_t:
			if expected_type_id == Bbb.Int.Type_t.u1 and type(val) == bool:
				pass
			elif type(val) != int:
				raise Exception()
		elif val.id != expected_type_id:
			raise Exception()

	def primitive_serialize(type_, data, ret):
		Bbb.Int(type_, data).primitive_serialize(ret)

	def primitive_deserialize(type_, data, pos):
		temp = Bbb.Int(type_)

		pos = temp.primitive_deserialize(data, pos)
		return temp.val, pos

	#size should be in [min_size, max_size)
	def vec_check(val, expected_type_id, min_size, max_size):
		if len(val) not in range(min_size, max_size):
			raise Exception()

		[Bbb.type_check(x, expected_type_id) for x in val]

	def vec_serialize(type_, min_size, max_size, ret, data):
		Bbb.vec_check(data, type_, min_size, max_size)

		max_size_diff = max_size - min_size
		size_diff = len(data) - min_size

		if max_size_diff <= 1 << 0:
			pass
		elif max_size_diff <= 1 << 8:
			Bbb.primitive_serialize(Bbb.Int.Type_t.u8, size_diff, ret)
		elif max_size_diff <= 1 << 16:
			Bbb.primitive_serialize(Bbb.Int.Type_t.u16, size_diff, ret)
		elif max_size_diff <= 1 << 32:
			Bbb.primitive_serialize(Bbb.Int.Type_t.u32, size_diff, ret)
		else:
			raise Exception()

		if type(type_) == Bbb.Int.Type_t:
			if type_ != Bbb.Int.Type_t.u1:
				[Bbb.primitive_serialize(type_, x, ret) for x in data]
			else:
				temp = Bbb.vec_bool_to_vec_u8(data)
				[Bbb.primitive_serialize(Bbb.Int.Type_t.u8, x, ret) for x in temp]
		else:
			[x.internal_serialize(ret) for x in data]

	def vec_deserialize(type_, min_size, max_size, data, pos):
		max_size_diff = max_size - min_size
		size_diff = 0

		if max_size_diff <= 1 << 0:
			pass
		elif max_size_diff <= 1 << 8:
			size_diff, pos = Bbb.primitive_deserialize(Bbb.Int.Type_t.u8, data, pos)
		elif max_size_diff <= 1 << 16:
			size_diff, pos = Bbb.primitive_deserialize(Bbb.Int.Type_t.u16, data, pos)
		elif max_size_diff <= 1 << 32:
			size_diff, pos = Bbb.primitive_deserialize(Bbb.Int.Type_t.u32, data, pos)
		else:
			raise Exception()

		if size_diff >= max_size_diff:
			raise Exception()

		ret = []

		if type(type_) == Bbb.Int.Type_t:
			if type_ != Bbb.Int.Type_t.u1:
				for i in range(min_size + size_diff):
					temp, pos = Bbb.primitive_deserialize(type_, data, pos)
					ret.append(temp)
			else:
				num_bytes = (min_size + size_diff) // 8 + ((min_size + size_diff) % 8 > 0)

				temp, pos = Bbb.read(data, pos, num_bytes)
				ret = Bbb.vec_u8_to_vec_bool(temp, min_size + size_diff)
		else:
			for i in range(min_size + size_diff):
				temp = type_()
				pos = temp.internal_deserialize(data, pos)
				ret.append(temp)

		Bbb.vec_check(ret, type_, min_size, max_size)

		return ret, pos

	class Serdes_base:
		def serialize(self):
			ret = bytearray()

			ret += self.id
			self.internal_serialize(ret)

			return ret

		def deserialize(self, data):
			pos = 0
			id_, pos = Bbb.read(data, pos, 16)

			if id_ != self.id:
				raise Exception()

			pos = self.internal_deserialize(data, pos)

			if len(data) != pos:
				raise Exception()
