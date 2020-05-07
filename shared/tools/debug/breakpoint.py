from weakref import WeakValueDictionary
from collections import defaultdict



class Breakpoint(object):
	"""Note that breakpoints are explicit, while a trap is much more commonly
	  evaluated. Traps are rooting about for a situation while the debugger
	  effectively brings the situation to the breakpoint to be verified.
	"""
	__slots__ = ('_id', '_filename', '_line_number', '_function_name',
				 'temporary', 'condition', 'hits', 
				 'enabled', 'ignored',
				 'note',
				 )

	_id_counter = 0

	_instances = {}
	_break_locations = {}


	def __init__(self, filename, location, 
				 temporary=False, condition=None, note=''):

		self.note = note

		self._filename = filename
		try:
			line_number = int(location)
			self._line_number = line_number
			self._function_name = ''
		except ValueError:
			self._line_number = None
			self._function_name = location

		self.temporary = temporary # this is a bit jank if more than one debugger scans it
		self.condition = condition

		self.hits = 0

		# use Tracer/PDB instance as key for number of hits
		self.enabled = defaultdict(bool) # no one is interested by default
		self.ignored = defaultdict(int) 


	# Properties that should not change once set
	@property
	def filename(self):
		return self._filename
	
	@property
	def line_number(self):
		return self._line_number

	@property
	def function_name(self):
		return self._function_name
	
	
	@property
	def id(self):
		return self._id


	@classmethod
	def next_id(cls):
		cls._id_counter += 1
		return cls._id_counter

	@property
	def location(self):
		return (self.filename, self.function_name or self.line_number)


	@classmethod
	def resolve_breakpoints(cls, breakpoint_ids):
		# coerce to iterable, if needed
		if not isinstance(breakpoint_ids, (list, tuple, set)):
			breakpoint_ids = [breakpoint_ids] 

		breakpoints = []
		for breakpoint in breakpoint_ids:
			if isinstance(breakpoint, Breakpoint):
				breakpoints.append(breakpoint)
			elif isinstance(breakpoint, (long, int)):
				breakpoints.append(cls._instances[breakpoint])
			elif isinstance(breakpoint, (str, unicode)):
				breakpoints.extend(cls._break_locations[breakpoint])
		return breakpoints


	def _add(self):
		"""Add the breakpoint to the class' tracking. If set leave it."""
		try:
			if self._id:
				return
		except AttributeError:
			if self.location in self._break_locations:
				self._break_locations[self.location].add(self)
			else:
				self._break_locations[self.location] = set([self])
			
			self._id = self.next_id()
			self._instances[self.id] = self 

	def _remove(self):
		self.enabled.clear()
		del self._instances[self.id]
		self._break_locations[self.location].remove(self)


	def trip(self, frame):
		"""Determine if the breakpoint should trip given the frame context."""
		
		# Breakpoint set by line
		if not self.function_name:
			return self.line_number == frame.f_lineno

		# Fail if the function name's wrong
		if self.function_name != frame.f_code.co_name:
			return False

		# Correct frame and correct function
		# Check if this is the first line of the function (call)
		try:
			return frame.f_lineno == self._function_first_line(frame)
		except KeyError:
			return False # in case of lookup in previous scope error, such as for a lambda?


	def _function_first_line(self, frame_scope):
		"""Grab the function's first line number from the frame scope."""
		try:
			function = frame_scope.f_back.f_locals[self.function_name]
		except KeyError:
			function = frame_scope.f_back.f_globals[self.function_name]
		return function.func_code.co_firstlineno


	@staticmethod
	def frame_location_by_line(frame):
		return (frame.f_code.co_filename, frame.f_lineno)

	@staticmethod
	def frame_location_by_function(frame):
		return (frame.f_code.co_filename, frame.f_code.co_name)


	def enable(self, interested_party):
		"""Enable the breakpoint for the interested_party"""
		self.enabled[interested_party] = True
		
	def disable(self, interested_party):
		"""Disable the breakpoint for the interested_party (this is the default state)"""
		self.enabled[interested_party] = False

	def ignore(self, interested_party, num_passes=0):
		"""Ignore this breakpoint for num_passes times for the interested_party"""
		self.ignored[interested_party] = num_passes


	@classmethod
	def relevant_breakpoints(cls, frame, interested_party=None):
		relevant = set()

		possible = ( cls._break_locations.get(cls.frame_location_by_line(frame), [])
			       + cls._break_locations.get(cls.frame_location_by_function(frame), []) )

		# Check candidate locations
		for breakpoint in possible:
			if not breakpoint.enabled[interested_party]:
				continue

			if not breakpoint.trip(frame):
				continue

			# Count each pass over the breakpoint while it's enabled
			#   Note 
			breakpoint.hits += 1

			if not breakpoint.condition:

				# If interested_party chose to ignore the breakpoint,
				#   decrement the counter and pass on...
				if breakpoint.ignored[interested_party] > 0:
					breakpoint.ignored[interested_party] -= 1
					continue
				# ... otherwise add it
				else:
					relevant.add(breakpoint)
					if breakpoint.temporary:
						breakpoint._remove()
					continue

			else:
				# Attempt to evaluate the condition
				try:
					# eval is evil, but we're in debug, so all bets are off
					result = eval(breakpoint.condition, 
								  frame.f_globals,
								  frame.f_locals)
					if result:
						if breakpoint.ignored[interested_party] > 0:
							breakpoint.ignored[interested_party] -= 1
							continue
						else:
							relevant.add(breakpoint)
							if breakpoint.temporary:
								breakpoint._remove()
							continue							
				# If the condition fails to eval, then break just to be safe
				#   but don't modify the ignore settings, also to be safe.
				except:
					relevant.add(breakpoint)
					continue

		return relevant


	def __str__(self):
		meta = []
		if self.temporary:
			meta.append('temporary')
		if self.condition:
			meta.append('conditional')

		meta = (' %r' % meta) if meta else ''

		func = (' for %s' % self.function) if self.function else ''

		return '<Breakpoint %sin %s at %s%s>' % (func, self.filename, self.line_number, meta)


	def __repr__(self):
		return self.__str__() # for now... should add conditional 


def set_breakpoint(note=''):
	import sys
	frame = sys._getframe(1)
	Breakpoint(frame.f_code.co_filename, frame.f_lineno, note=note)